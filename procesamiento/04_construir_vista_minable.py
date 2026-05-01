"""
04_construir_vista_minable.py
===================================================================
Construye la tabla rectangular (vista minable) que alimenta los modelos ML.

Cada fila = un (pixel, semestre).  Cada columna = un feature o target.

Clasificacion multiclase (20 clases, alineada con EVA Cundinamarca 2019-2024):
    Papa, Cana_Panelera, Cafe, Maiz, Platano, Mango, Frijol, Cacao,
    Arveja, Palma, Banano, Citricos, Mora, Zanahoria, Tomate_Arbol,
    Yuca, Habichuela, Hortalizas, Otros_cultivos, No_apto

Etiquetado jerárquico de 3 niveles (con `sample_weight = confianza`):
    L1 Monitoreo UPRA      → hard label,  confianza=1.0
    L2 EVA municipal       → hard label = cultivo dominante del municipio,
                              confianza = area_cultivo / area_agricola (0.3–0.7)
    L3 No_apto (proxy)     → hard label,  confianza=0.4
                              (SIPRA "No apta" en >=3 capas Y/O NDVI_max < 0.15)

Entradas:
  - processed/                   → capas estáticas y mensuales armonizadas
  - processed/temporal/          → estadísticos semestrales
  - processed/engineered/        → features derivadas (incluye ndvi_max, piso_termico)
  - extractores/raw/target/eva/       → CSV EVA UPRA + histórica
  - extractores/raw/target/monitoreo/ → GeoJSON polígonos UPRA
  - extractores/raw/target/sipra/     → GeoJSON aptitud (solo para No_apto)
  - extractores/raw/target/mgn/       → GeoJSON municipios DANE

Salida:
  - vista_minable/vista_minable_full.parquet
  - vista_minable/catalogo_cultivos.json  (id estable según MODEL_CLASSES)

Prerequisitos:
    1. Haber ejecutado extractores (01-09) para generar raw/
    2. Haber ejecutado procesamiento/01_armonizar_espacial.py
    3. Haber ejecutado procesamiento/02_armonizar_temporal.py
    4. Haber ejecutado procesamiento/03_feature_engineering.py

Uso:
    cd d:\\trabajo\\agroplus
    uv run procesamiento/04_construir_vista_minable.py                     # Pipeline completo
    uv run procesamiento/04_construir_vista_minable.py --step preparar    # Máscaras + rasterización
    uv run procesamiento/04_construir_vista_minable.py --step muestrear   # Muestreo píxeles
    uv run procesamiento/04_construir_vista_minable.py --max-pixeles 200000

Dependencias (ya en pyproject.toml):
    uv sync
"""

import argparse
import json
import os
import sys
import glob
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extractores'))
from config import (
    SEMESTRES, BBOX_WGS84, DEPT_DANE, RESOLUCION_M,
    EVA_TOP_CULTIVOS, MODEL_CLASSES,
)

# ==================================================================
# CONFIGURACION
# ==================================================================

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR   = os.path.join(BASE_DIR, 'processed')
TEMP_DIR   = os.path.join(PROC_DIR, 'temporal')
ENG_DIR    = os.path.join(PROC_DIR, 'engineered')
RAW_DIR    = os.path.join(BASE_DIR, 'extractores', 'raw')
OUT_DIR    = os.path.join(BASE_DIR, 'vista_minable')
NODATA     = -9999.0
TARGET_CRS = 'EPSG:3116'

MAX_PIXELES_DEFAULT = 500_000  # por semestre, reducido luego por estratificación


# ==================================================================
# UTILIDADES
# ==================================================================

def _leer_raster(path, banda=1):
    """Lee GeoTIFF, retorna (array, profile). NoData → NaN."""
    import rasterio
    with rasterio.open(path) as src:
        arr = src.read(banda).astype(np.float32)
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        arr[arr == NODATA] = np.nan
        return arr, src.profile.copy()


def _get_transform_shape():
    """Lee el transform y shape del grid de referencia desde el DEM."""
    import rasterio
    dem_path = os.path.join(PROC_DIR, 'topo', f'dem_elevacion_{RESOLUCION_M}m.tif')
    with rasterio.open(dem_path) as src:
        return src.transform, src.height, src.width, src.crs, src.profile.copy()


# ==================================================================
# NORMALIZACION DE NOMBRES DE CULTIVO
# ==================================================================

def _sin_acentos(s):
    """Remueve acentos y normaliza usando unicodedata (robusto a cualquier encoding)."""
    import unicodedata
    s = unicodedata.normalize('NFD', str(s))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


# Reglas de mapeo EVA/monitoreo -> clase canonica del modelo.
# Se evaluan en orden; el primer prefijo que matchee gana.
# IMPORTANTE: prefijos mas especificos antes que los generales
# (ej. 'tomate de arbol' antes que 'tomate' generico).
# La entrada ya viene en minusculas y sin acentos (ver _normalizar_cultivo).
_REGLAS_NORMALIZACION = [
    ('papa',           'Papa'),
    ('cana',           'Cana_Panelera'),  # cana panelera, cana azucarera, cana miel
    ('cafe',           'Cafe'),
    ('maiz',           'Maiz'),
    ('platano',        'Platano'),
    ('mango',          'Mango'),
    ('frijol',         'Frijol'),
    ('cacao',          'Cacao'),
    ('arveja',         'Arveja'),
    ('palma',          'Palma'),          # palma africana, palma aceitera
    ('banano',         'Banano'),

    # --- Grupo Citricos ---
    # Agrupa Naranja, Mandarina, Limon, Tangelo y Otros citricos porque:
    # (1) son indistinguibles espectralmente a 50m (dosel perenne similar),
    # (2) comparten nicho climatico de piedemonte calido (800-1800 msnm),
    # (3) en EVA aparecen reportados de forma inconsistente por municipio.
    # EVA 2019-2024 Cundinamarca: ~62K ha en 53 municipios.
    ('naranja',        'Citricos'),
    ('mandarina',      'Citricos'),
    ('limon',          'Citricos'),       # limon (sin tilde tras _sin_acentos)
    ('tangelo',        'Citricos'),
    ('otros citri',    'Citricos'),       # "Otros citricos" EVA

    ('mora',           'Mora'),
    ('zanahoria',      'Zanahoria'),

    # tomate de arbol ANTES de 'tomate' generico para evitar colision
    ('tomate de arbol','Tomate_Arbol'),
    ('tomate arbol',   'Tomate_Arbol'),   # variante sin 'de'
    ('tomate de a',    'Tomate_Arbol'),   # variante abreviada EVA

    ('yuca',           'Yuca'),
    ('habichuela',     'Habichuela'),

    # --- Grupo Hortalizas ---
    # Agrupa cultivos de ciclo corto intensivo de la Sabana de Bogota y
    # valles interandinos (Mosquera, Cota, Cajica, Tocancipa, Fomeque, etc.)
    # porque: (1) comparten firma espectral de dosel bajo con alta reflectancia
    # en verde y NDVI moderado (0.3-0.6), (2) el ciclo corto (<4 meses) genera
    # alta variabilidad temporal del NDVI diferenciadora del resto de cultivos,
    # (3) muchos se producen bajo invernadero o polytunnel con patron SAR/optico
    # caracteristico. EVA 2019-2024: ~72K ha en 90 municipios; domina en
    # 10 municipios que antes caian en Otros_cultivos.
    ('cebolla',        'Hortalizas'),     # cebolla de bulbo, cebolla de rama
    ('lechuga',        'Hortalizas'),
    ('tomate',         'Hortalizas'),     # tomate chonto/larga vida (tomate de arbol ya resuelto)
    ('otras horta',    'Hortalizas'),     # "Otras hortalizas" EVA
    ('cilantro',       'Hortalizas'),
    ('ahuyama',        'Hortalizas'),
    ('calabac',        'Hortalizas'),     # calabacin, calabaza
    ('espinaca',       'Hortalizas'),
    ('apio',           'Hortalizas'),
    ('repollo',        'Hortalizas'),
    ('pimenton',       'Hortalizas'),     # pimenton (sin tilde)
    ('pepino',         'Hortalizas'),     # pepino cohombro, pepino guiso
    ('remolacha',      'Hortalizas'),
    ('brocoli',        'Hortalizas'),     # brocoli (sin tilde)
    ('acelga',         'Hortalizas'),
    ('ajo',            'Hortalizas'),
    ('esparrago',      'Hortalizas'),     # esparrago (sin tilde)
    ('rabano',         'Hortalizas'),     # rabano (sin tilde)
    ('haba',           'Hortalizas'),     # haba (habichuela ya resuelta arriba)
]


def _normalizar_cultivo(nombre_raw):
    """Mapea nombre EVA/monitoreo -> clase canonica del modelo (MODEL_CLASSES).

    Cualquier cultivo sin regla cae en 'Otros_cultivos'.
    """
    if nombre_raw is None or (isinstance(nombre_raw, float) and np.isnan(nombre_raw)):
        return 'Otros_cultivos'
    n = _sin_acentos(str(nombre_raw).strip().lower())
    for prefijo, clase in _REGLAS_NORMALIZACION:
        if n.startswith(prefijo):
            return clase
    return 'Otros_cultivos'


# ==================================================================
# PASO 1: MASCARA VALIDA + MUNICIPIOS
# ==================================================================

def crear_mascara_valida():
    """
    Crea máscara booleana del departamento: píxeles con datos válidos en DEM.
    Retorna (mascara_2d, transform, height, width, crs, profile).
    """
    print("\n" + "=" * 70)
    print("PASO 1: MASCARA VÁLIDA DEL DEPARTAMENTO")
    print("=" * 70)

    dem_path = os.path.join(PROC_DIR, 'topo', f'dem_elevacion_{RESOLUCION_M}m.tif')
    if not os.path.exists(dem_path):
        raise FileNotFoundError(f"DEM requerido: {dem_path}")

    elev, profile = _leer_raster(dem_path)
    mascara = ~np.isnan(elev)

    n_validos = np.count_nonzero(mascara)
    print(f"  Píxeles válidos: {n_validos:,} de {mascara.size:,} "
          f"({100 * n_validos / mascara.size:.1f}%)")

    return mascara, profile


# ==================================================================
# PASO 2: RASTERIZAR MONITOREO UPRA → mapa de cultivos por semestre
# ==================================================================

def _parsear_semestre_monitoreo(nombre_archivo):
    """
    Extrae (cultivo, semestre_label) del nombre del archivo de monitoreo.
    Ej: monitoreo_papa_2021_s1.geojson → ('Papa', '2021A')
        monitoreo_maiz_2022_1.geojson  → ('Maíz', '2022A')
        monitoreo_cacao_2020.geojson   → ('Cacao', '2020A')
    """
    base = nombre_archivo.replace('monitoreo_', '').replace('.geojson', '')
    partes = base.split('_')

    # Extraer cultivo (puede ser multi-palabra antes de los números)
    cultivo_partes = []
    num_start = 0
    for i, p in enumerate(partes):
        if p.isdigit() and len(p) == 4:  # año
            num_start = i
            break
        cultivo_partes.append(p)

    cultivo = ' '.join(cultivo_partes).title()
    resto = partes[num_start:]

    if len(resto) == 1:
        # Solo año (cacao_2020) → semestre A
        return cultivo, f"{resto[0]}A"
    elif len(resto) >= 2:
        year = resto[0]
        sem_raw = resto[1].lower()
        # s1, 1, s2, 2 → A o B
        if sem_raw in ('s1', '1'):
            return cultivo, f"{year}A"
        elif sem_raw in ('s2', '2'):
            return cultivo, f"{year}B"

    return cultivo, f"{resto[0]}A" if resto else None


def rasterizar_monitoreo(profile):
    """
    Rasteriza polígonos de monitoreo UPRA.
    Retorna dict: {semestre_label: [(cultivo, mascara_bool), ...]}
    """
    import rasterio
    from rasterio.features import rasterize
    import geopandas as gpd

    print("\n" + "=" * 70)
    print("PASO 2: RASTERIZAR MONITOREO UPRA")
    print("=" * 70)

    mon_dir = os.path.join(RAW_DIR, 'target', 'monitoreo')
    if not os.path.exists(mon_dir):
        print("  Directorio de monitoreo no encontrado. Saltando.")
        return {}

    archivos = sorted(glob.glob(os.path.join(mon_dir, 'monitoreo_*.geojson')))
    if not archivos:
        print("  Sin archivos de monitoreo.")
        return {}

    transform = profile['transform']
    height = profile['height']
    width = profile['width']

    monitoreo_por_semestre = defaultdict(list)
    total_poligonos = 0

    for fpath in archivos:
        nombre = os.path.basename(fpath)
        cultivo, sem_label = _parsear_semestre_monitoreo(nombre)
        if sem_label is None:
            print(f"  No se pudo parsear semestre de {nombre}. Saltando.")
            continue

        try:
            gdf = gpd.read_file(fpath)
        except Exception as e:
            print(f"  Error leyendo {nombre}: {e}")
            continue

        if gdf.empty:
            continue

        # Reproyectar a EPSG:3116 si es necesario
        if gdf.crs is None or str(gdf.crs).upper() != TARGET_CRS:
            gdf = gdf.to_crs(TARGET_CRS)

        # Usar el campo 'cultivo' del GeoJSON si existe, sino del nombre
        if 'cultivo' in gdf.columns:
            cultivo_col = gdf['cultivo'].iloc[0]
            if isinstance(cultivo_col, str) and cultivo_col.strip():
                cultivo = cultivo_col.strip().title()

        # Rasterizar: 1 donde hay polígono, 0 donde no
        geometries = [(geom, 1) for geom in gdf.geometry if geom is not None and geom.is_valid]
        if not geometries:
            continue

        raster = rasterize(
            geometries,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            dtype='uint8',
        )

        mascara = raster > 0
        n_pixeles = np.count_nonzero(mascara)

        if n_pixeles > 0:
            monitoreo_por_semestre[sem_label].append((cultivo, mascara))
            total_poligonos += len(geometries)
            print(f"  [{cultivo} {sem_label}] {n_pixeles:,} píxeles "
                  f"({len(geometries)} polígonos)")

    print(f"\n  Total: {total_poligonos:,} polígonos rasterizados en "
          f"{len(monitoreo_por_semestre)} semestres")

    return monitoreo_por_semestre


# ==================================================================
# PASO 3: CARGAR EVA MUNICIPAL (solo rendimiento, no etiqueta)
# ==================================================================

def cargar_eva():
    """
    Carga EVA y retorna:
      - eva_agg: DataFrame con (cod_mun, semestre, cultivo_norm, area, score, rend).
      - eva_top_dict: dict {(cod_mun, semestre): {cultivo_norm, score, rendimiento}}
        con el cultivo dominante (mayor área) — usado por etiquetado hard (compat).
      - eva_dist_dict: dict {(cod_mun, semestre): {cultivo_norm: score, ...}}
        con la DISTRIBUCIÓN COMPLETA de cultivos — usado por etiquetado soft
        (Alternativa A, Learning from Label Proportions).

    El agregado a clase canónica es clave: si un municipio tiene
    "Papa Comun" + "Papa Criolla" + "Papa Parda", todos son 'Papa' y
    su score combinado puede superar al segundo cultivo.
    """
    print("\n" + "=" * 70)
    print("PASO 3: CARGAR EVA MUNICIPAL")
    print("=" * 70)

    eva_dir = os.path.join(RAW_DIR, 'target', 'eva')

    dfs = []

    # EVA UPRA 2019-2024
    upra_path = os.path.join(eva_dir, 'eva_upra_2019_2024_cundinamarca.csv')
    if os.path.exists(upra_path):
        df = pd.read_csv(upra_path, dtype=str, encoding='utf-8')
        df_clean = pd.DataFrame({
            'cod_mun': df['c_digo_dane_municipio'].str.strip().str.zfill(5),
            'year': pd.to_numeric(df['a_o'], errors='coerce'),
            'cultivo': df['cultivo'].str.strip(),
            'rendimiento': pd.to_numeric(df['rendimiento'], errors='coerce'),
            'area_cosechada': pd.to_numeric(df['rea_cosechada'], errors='coerce'),
            'area_sembrada': pd.to_numeric(df['rea_sembrada'], errors='coerce'),
            'ciclo': df['ciclo_del_cultivo'].str.strip() if 'ciclo_del_cultivo' in df.columns else 'Transitorio',
        })
        dfs.append(df_clean)
        print(f"  EVA UPRA: {len(df_clean):,} registros")

    # EVA Histórica 2007-2018
    hist_path = os.path.join(eva_dir, 'eva_historica_2007_2018_cundinamarca.csv')
    if os.path.exists(hist_path):
        df = pd.read_csv(hist_path, dtype=str, encoding='utf-8')
        df_clean = pd.DataFrame({
            'cod_mun': df['c_d_mun'].str.strip().str.zfill(5),
            'year': pd.to_numeric(df['a_o'], errors='coerce'),
            'cultivo': df['cultivo'].str.strip(),
            'rendimiento': pd.to_numeric(df['rendimiento_t_ha'], errors='coerce'),
            'area_cosechada': pd.to_numeric(df['rea_cosechada_ha'], errors='coerce'),
            'area_sembrada': pd.to_numeric(df['rea_sembrada_ha'], errors='coerce'),
            'ciclo': df['ciclo_de_cultivo'].str.strip() if 'ciclo_de_cultivo' in df.columns else 'Transitorio',
        })
        dfs.append(df_clean)
        print(f"  EVA Histórica: {len(df_clean):,} registros")

    if not dfs:
        print("  Sin datos EVA.")
        return pd.DataFrame(), {}, {}

    eva = pd.concat(dfs, ignore_index=True)
    eva = eva.dropna(subset=['cod_mun', 'year', 'cultivo'])
    eva['year'] = eva['year'].astype(int)

    # Normalizar cultivo -> una de las 14 clases
    eva['cultivo_norm'] = eva['cultivo'].apply(_normalizar_cultivo)
    eva['area_cosechada'] = eva['area_cosechada'].fillna(0)

    # Expandir cada registro a los dos semestres del año (transitorios siembran A y B).
    # Nota: perennes (cacao, cafe, palma) realmente cosechan todo el año; esta
    # duplicación está bien porque representamos presencia del cultivo, no siembra.
    rows_a = eva.copy(); rows_a['semestre'] = eva['year'].astype(str) + 'A'
    rows_b = eva.copy(); rows_b['semestre'] = eva['year'].astype(str) + 'B'
    eva_sem = pd.concat([rows_a, rows_b], ignore_index=True)

    # Agrupar por (cod_mun, semestre, cultivo_norm): sumar áreas.
    eva_agg = (
        eva_sem.groupby(['cod_mun', 'semestre', 'cultivo_norm'], as_index=False)
        .agg(area_cosechada=('area_cosechada', 'sum'),
             rendimiento=('rendimiento', 'median'))
    )

    # score_aptitud = área_de_esta_clase / área_agrícola_total_del_municipio_semestre
    total = eva_agg.groupby(['cod_mun', 'semestre'])['area_cosechada'].transform('sum')
    eva_agg['score_aptitud'] = np.where(total > 0, eva_agg['area_cosechada'] / total, 0.0)

    # Top cultivo (mayor área normalizada) por municipio-semestre
    eva_sorted = eva_agg.sort_values('area_cosechada', ascending=False)
    eva_top = eva_sorted.groupby(['cod_mun', 'semestre']).head(1)

    eva_top_dict = {}
    for _, r in eva_top.iterrows():
        eva_top_dict[(r['cod_mun'], r['semestre'])] = {
            'cultivo_norm': r['cultivo_norm'],
            'score': float(r['score_aptitud']),
            'rendimiento': (float(r['rendimiento']) if pd.notna(r['rendimiento']) else None),
        }

    # Distribución L2 por (cod_mun, semestre) — para etiquetado soft (LLP).
    # Se EXCLUYEN Papa y No_apto: Papa la modela L1 (monitoreo UPRA pixel-level,
    # confianza=1.0) y No_apto la modela L3 (proxy SIPRA+NDVI).
    # Incluir Papa en la distribución L2 contamina las proporciones porque las
    # hectareas EVA de Papa son las mismas que L1 ya etiqueto con mayor precision.
    # La renormalizacion ocurre en asignar_target (prob_vec /= s), asi que basta
    # con omitir estas clases aqui y las proporciones quedaran correctamente
    # distribuidas entre los cultivos no-Papa no-No_apto.
    L2_EXCLUIR = {'Papa', 'No_apto'}
    eva_dist_dict = {}
    for (cod, sem), grp in eva_agg.groupby(['cod_mun', 'semestre']):
        dist = {r['cultivo_norm']: float(r['score_aptitud']) for _, r in grp.iterrows()
                if r['score_aptitud'] > 0 and r['cultivo_norm'] not in L2_EXCLUIR}
        if dist:
            eva_dist_dict[(cod, sem)] = dist

    n_mun = eva_agg['cod_mun'].nunique()
    print(f"  EVA agregado: {len(eva_agg):,} (mun,sem,clase), "
          f"{n_mun} municipios, {eva_agg['cultivo_norm'].nunique()} clases canónicas")
    print(f"  Top-cultivo por (mun,sem): {len(eva_top_dict):,} entradas")
    print(f"  Distribución completa por (mun,sem): {len(eva_dist_dict):,} entradas "
          f"(promedio {np.mean([len(d) for d in eva_dist_dict.values()]):.1f} cultivos/mun)")

    return eva_agg, eva_top_dict, eva_dist_dict


# ==================================================================
# PASO 3b: RASTERIZAR MGN-DANE (municipios) — lookup cod_mun por pixel
# ==================================================================

def rasterizar_municipios(profile):
    """
    Rasteriza el shapefile MGN-DANE al grid del proyecto.
    Cada píxel contiene int(cod_dane) del municipio (0 = fuera de Cundinamarca).

    Retorna ndarray int32 o None si el MGN no está descargado.
    """
    import geopandas as gpd
    from rasterio.features import rasterize

    print("\n" + "=" * 70)
    print("PASO 3b: RASTERIZAR MGN-DANE")
    print("=" * 70)

    mgn_path = os.path.join(RAW_DIR, 'target', 'mgn', 'municipios_cundinamarca.geojson')
    if not os.path.exists(mgn_path):
        print(f"  MGN-DANE no encontrado: {mgn_path}")
        print("  Ejecutar: python extractores/09_extraer_municipios_dane.py")
        print("  Se omitirá el nivel L2 (EVA municipal) del etiquetado.")
        return None

    gdf = gpd.read_file(mgn_path)
    if gdf.crs is None or str(gdf.crs).upper() != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)

    if 'cod_dane' not in gdf.columns:
        print(f"  MGN sin columna 'cod_dane'; columnas disponibles: {list(gdf.columns)}")
        return None

    gdf['cod_int'] = gdf['cod_dane'].astype(str).str.zfill(5).astype(int)
    shapes = [
        (geom, int(cod)) for geom, cod in zip(gdf.geometry, gdf['cod_int'])
        if geom is not None and geom.is_valid
    ]
    if not shapes:
        print("  Sin geometrías válidas en MGN.")
        return None

    raster = rasterize(
        shapes,
        out_shape=(profile['height'], profile['width']),
        transform=profile['transform'],
        fill=0,
        dtype='int32',
    )
    n_pixeles = np.count_nonzero(raster)
    n_mpios = gdf['cod_dane'].nunique()
    print(f"  Municipios rasterizados: {n_mpios} ({n_pixeles:,} píxeles)")
    return raster


# ==================================================================
# PASO 3c: RASTERIZAR SIPRA "No apta" — proxy para clase No_apto
# ==================================================================

def rasterizar_sipra_noapta(profile):
    """
    Rasteriza todas las capas SIPRA presentes. Retorna un raster int16 con
    el CONTEO de capas que declaran 'No apta' en cada píxel. Un valor alto
    (>=3) indica que ese píxel es no apto para múltiples cultivos.

    Se usa junto con NDVI_max bajo para detectar la clase No_apto en
    asignar_target() (nivel L3). Este uso es defensible respecto al
    problema original de fuga (cuando SIPRA se usaba para asignar cultivos
    positivos): aquí solo se identifica la NEGACIÓN/ausencia de aptitud,
    no se reinyecta información sobre qué cultivo corresponde donde.

    Retorna ndarray int16 o None si no hay SIPRA disponible.
    """
    import geopandas as gpd
    from rasterio.features import rasterize

    print("\n" + "=" * 70)
    print("PASO 3c: RASTERIZAR SIPRA (solo para proxy No_apto)")
    print("=" * 70)

    sipra_dir = os.path.join(RAW_DIR, 'target', 'sipra')
    if not os.path.exists(sipra_dir):
        print("  Directorio SIPRA no encontrado.")
        return None

    archivos = sorted(glob.glob(os.path.join(sipra_dir, 'aptitud_*.geojson')))
    if not archivos:
        print("  Sin archivos SIPRA.")
        return None

    # Campos típicos que contienen la etiqueta de aptitud
    campos_aptitud = [
        'aptitud', 'apt_uso', 'apt_general', 'categoria', 'clase',
        'APTITUD', 'APT_USO', 'APT_GENERAL', 'CATEGORIA', 'CLASE',
    ]

    conteo_noapta = np.zeros((profile['height'], profile['width']), dtype=np.int16)
    n_capas = 0

    for fpath in archivos:
        nombre = os.path.basename(fpath)
        try:
            gdf = gpd.read_file(fpath)
        except Exception as e:
            print(f"  Error leyendo {nombre}: {e}")
            continue

        if gdf.empty:
            continue

        if gdf.crs is None or str(gdf.crs).upper() != TARGET_CRS:
            gdf = gdf.to_crs(TARGET_CRS)

        col_apt = next((c for c in campos_aptitud if c in gdf.columns), None)
        if col_apt is None:
            print(f"    [{nombre}] sin campo de aptitud; omitiendo.")
            continue

        mask_no = gdf[col_apt].astype(str).str.lower().str.contains('no apta', na=False)
        gdf_no = gdf[mask_no]
        if gdf_no.empty:
            continue

        shapes = [(g, 1) for g in gdf_no.geometry if g is not None and g.is_valid]
        if not shapes:
            continue

        raster = rasterize(
            shapes,
            out_shape=(profile['height'], profile['width']),
            transform=profile['transform'],
            fill=0,
            dtype='uint8',
        )
        conteo_noapta += raster
        n_capas += 1
        print(f"    [{nombre}] No-apta rasterizada")

    if n_capas == 0:
        print("  SIPRA sin datos válidos; no se usará proxy No_apto via SIPRA.")
        return None

    print(f"  SIPRA consolidado: {n_capas} capas, max conteo = {conteo_noapta.max()}")
    return conteo_noapta


def cargar_ndvi_max_ultimo_anio():
    """
    Carga el NDVI_max más reciente disponible para usarlo en el proxy No_apto.
    Se agrega (max) los semestres del último año; si no existe engineered,
    retorna None.
    """
    eng_ndvi_dir = ENG_DIR
    # Último año disponible = penúltimo en SEMESTRES (el último suele estar incompleto)
    candidatos = []
    for sem in reversed(SEMESTRES):
        path = os.path.join(eng_ndvi_dir, f'ndvi_max_{sem["label"]}.tif')
        if os.path.exists(path):
            candidatos.append(path)
        if len(candidatos) >= 4:  # ~2 años
            break

    if not candidatos:
        print("  NDVI_max no disponible; se omitirá ese criterio en proxy No_apto.")
        return None

    stack = []
    for p in candidatos:
        arr, _ = _leer_raster(p)
        stack.append(arr)
    arr_max = np.fmax.reduce(stack)
    print(f"  NDVI_max global (últimos {len(candidatos)} semestres) cargado.")
    return arr_max


# ==================================================================
# PASO 3e: VARIABILIDAD TEMPORAL DEL NDVI (MASCARA AGRICOLA)
# ==================================================================

def calcular_sigma_ndvi_temporal(profile):
    """
    Calcula la variabilidad temporal del NDVI_max por pixel usando todos los
    semestres disponibles en processed/temporal/satelite/sentinel2/.

    Para cada pixel produce:
      ndvi_sigma_temporal : std de s2_ndvi_max a lo largo del eje temporal
      ndvi_mean_temporal  : media de s2_ndvi_max a lo largo del eje temporal

    Interpretacion:
      - sigma alto  + media moderada => ciclo de cultivo detectable (transitorio)
      - sigma bajo  + media alta     => vegetacion densa y estable => bosque
      - sigma bajo  + media baja     => suelo desnudo / urbano / agua (ya en L3)
      - Cultivos perennes (Cafe, Cacao, Palma): sigma moderado, media 0.55-0.75

    Los rasters se guardan en processed/engineered/ y se reutilizan si ya existen.
    Requiere >= 2 semestres con datos para calcular sigma; retorna (None, None) si no.
    """
    s2_dir = os.path.join(TEMP_DIR, 'satelite', 'sentinel2')
    sigma_path = os.path.join(ENG_DIR, 'ndvi_sigma_temporal.tif')
    mean_path  = os.path.join(ENG_DIR, 'ndvi_mean_temporal.tif')

    if os.path.exists(sigma_path) and os.path.exists(mean_path):
        print("  ndvi_sigma_temporal y ndvi_mean_temporal ya existen, cargando.")
        sigma_arr, _ = _leer_raster(sigma_path)
        mean_arr,  _ = _leer_raster(mean_path)
        return sigma_arr, mean_arr

    print("\n" + "=" * 70)
    print("PASO 3e: CALCULAR SIGMA NDVI TEMPORAL")
    print("=" * 70)

    # Leer un raster por semestre (s2_ndvi_max ya es el maximo dentro del semestre)
    capas = []
    for sem in SEMESTRES:
        path = os.path.join(s2_dir, f's2_ndvi_max_{sem["label"]}.tif')
        if os.path.exists(path):
            arr, _ = _leer_raster(path)
            capas.append(arr)

    if len(capas) < 2:
        print(f"  Solo {len(capas)} semestre(s) disponible(s). "
              f"Se necesitan >= 2 para calcular sigma. Saltando.")
        return None, None

    print(f"  Semestres cargados: {len(capas)}")
    stack = np.stack(capas, axis=0)          # (T, H, W)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sigma_arr = np.nanstd(stack,  axis=0).astype(np.float32)
        mean_arr  = np.nanmean(stack, axis=0).astype(np.float32)

    # Pixeles donde todos los semestres son NaN -> resultado NaN
    all_nan_mask = np.all(np.isnan(stack), axis=0)
    sigma_arr[all_nan_mask] = np.nan
    mean_arr[all_nan_mask]  = np.nan

    print(f"  ndvi_sigma_temporal: "
          f"p10={np.nanpercentile(sigma_arr, 10):.3f}  "
          f"p50={np.nanpercentile(sigma_arr, 50):.3f}  "
          f"p90={np.nanpercentile(sigma_arr, 90):.3f}")
    print(f"  ndvi_mean_temporal:  "
          f"p10={np.nanpercentile(mean_arr, 10):.3f}  "
          f"p50={np.nanpercentile(mean_arr, 50):.3f}  "
          f"p90={np.nanpercentile(mean_arr, 90):.3f}")

    # Guardar como GeoTIFF en engineered/ para reutilizacion y extraccion en parquet
    import rasterio
    out_profile = profile.copy()
    out_profile.update(dtype='float32', count=1, nodata=NODATA, compress='lzw')

    for arr, path, nombre in [
        (sigma_arr, sigma_path, 'ndvi_sigma_temporal'),
        (mean_arr,  mean_path,  'ndvi_mean_temporal'),
    ]:
        data = arr.copy()
        data[np.isnan(data)] = NODATA
        with rasterio.open(path, 'w', **out_profile) as dst:
            dst.write(data, 1)
        print(f"  Guardado: {os.path.relpath(path)}")

    return sigma_arr, mean_arr


# ==================================================================
# PASO 5: MUESTREO ESTRATIFICADO
# ==================================================================

def muestrear_pixeles(mascara_valida, profile, monitoreo_por_semestre,
                      max_pixeles=MAX_PIXELES_DEFAULT):
    """
    Muestreo estratificado de píxeles.
    Estratos: piso_termico (4) × pendiente_clase (4) × tiene_monitoreo (2)
    = 32 estratos.

    Retorna DataFrame con columnas: row, col, x, y, piso_termico, pendiente_clase
    """
    print("\n" + "=" * 70)
    print("PASO 5: MUESTREO ESTRATIFICADO")
    print("=" * 70)

    transform = profile['transform']

    # Cargar piso térmico para estratificación
    piso_path = os.path.join(ENG_DIR, 'piso_termico.tif')
    pend_path = os.path.join(PROC_DIR, 'topo', f'dem_pendiente_{RESOLUCION_M}m.tif')

    if not os.path.exists(piso_path):
        print("  Calculando piso térmico al vuelo desde DEM...")
        elev, _ = _leer_raster(os.path.join(PROC_DIR, 'topo', f'dem_elevacion_{RESOLUCION_M}m.tif'))
        piso = np.full_like(elev, np.nan)
        piso[elev < 1000] = 0
        piso[(elev >= 1000) & (elev < 2000)] = 1
        piso[(elev >= 2000) & (elev < 3000)] = 2
        piso[elev >= 3000] = 3
    else:
        piso, _ = _leer_raster(piso_path)

    if os.path.exists(pend_path):
        pendiente, _ = _leer_raster(pend_path)
        # Clasificar pendiente: 0=plano(<5°), 1=suave(5-15°), 2=moderado(15-30°), 3=escarpado(>30°)
        pend_clase = np.full_like(pendiente, np.nan)
        pend_clase[pendiente < 5] = 0
        pend_clase[(pendiente >= 5) & (pendiente < 15)] = 1
        pend_clase[(pendiente >= 15) & (pendiente < 30)] = 2
        pend_clase[pendiente >= 30] = 3
    else:
        print("  Sin pendiente. Usando estrato uniforme.")
        pend_clase = np.zeros_like(piso)

    # Máscara combinada de monitoreo (cualquier semestre)
    mascara_monitoreo = np.zeros(mascara_valida.shape, dtype=bool)
    for sem_label, cultivos in monitoreo_por_semestre.items():
        for cultivo, masc in cultivos:
            mascara_monitoreo |= masc

    # Índices de píxeles válidos
    rows_v, cols_v = np.where(mascara_valida)

    # Construir array de estrato para cada píxel válido
    piso_v = piso[rows_v, cols_v]
    pend_v = pend_clase[rows_v, cols_v]
    mon_v = mascara_monitoreo[rows_v, cols_v].astype(np.float32)

    # Combinar en ID de estrato (NaN → -1 para poder castear a int)
    _piso_safe = np.nan_to_num(piso_v, nan=-1)
    _pend_safe = np.nan_to_num(pend_v, nan=-1)
    estrato = (_piso_safe * 100 + _pend_safe * 10 + mon_v).astype(np.int16)

    # Contar por estrato
    estratos_unicos, counts = np.unique(estrato[~np.isnan(piso_v)], return_counts=True)
    print(f"  {len(estratos_unicos)} estratos encontrados")
    for eu, c in sorted(zip(estratos_unicos, counts), key=lambda x: -x[1])[:10]:
        print(f"    Estrato {eu}: {c:,} píxeles")

    # Incluir TODOS los píxeles con monitoreo + muestrear del resto
    idx_monitoreo = np.where(mon_v > 0)[0]
    idx_no_monitoreo = np.where((mon_v == 0) & (~np.isnan(piso_v)))[0]

    print(f"  Píxeles con monitoreo: {len(idx_monitoreo):,}")
    print(f"  Píxeles sin monitoreo: {len(idx_no_monitoreo):,}")

    # Calcular cuántos muestrear del no-monitoreo
    restante = max(0, max_pixeles - len(idx_monitoreo))

    if restante > 0 and len(idx_no_monitoreo) > 0:
        # Muestreo estratificado proporcional
        est_no_mon = estrato[idx_no_monitoreo]
        est_uniq, est_counts = np.unique(est_no_mon[~np.isnan(est_no_mon.astype(float))],
                                          return_counts=True)

        total_no_mon = est_counts.sum()
        rng = np.random.RandomState(42)
        idx_muestreados = []

        for eu, ec in zip(est_uniq, est_counts):
            n_muestra = max(1, int(restante * ec / total_no_mon))
            idx_estrato = idx_no_monitoreo[est_no_mon == eu]
            if len(idx_estrato) <= n_muestra:
                idx_muestreados.append(idx_estrato)
            else:
                idx_muestreados.append(rng.choice(idx_estrato, n_muestra, replace=False))

        idx_muestreados = np.concatenate(idx_muestreados)
    else:
        idx_muestreados = np.array([], dtype=int)

    # Combinar monitoreo + muestreados
    idx_final = np.concatenate([idx_monitoreo, idx_muestreados]).astype(int)
    idx_final = np.unique(idx_final)

    # Construir DataFrame de coordenadas
    rows_sel = rows_v[idx_final]
    cols_sel = cols_v[idx_final]

    # Convertir row, col a coordenadas X, Y (centro del píxel)
    xs = transform.c + cols_sel * transform.a + transform.a / 2
    ys = transform.f + rows_sel * transform.e + transform.e / 2

    _piso_sel = np.nan_to_num(piso[rows_sel, cols_sel], nan=-1).astype(np.int8)
    _pend_sel = np.nan_to_num(pend_clase[rows_sel, cols_sel], nan=-1).astype(np.int8)

    df_pixeles = pd.DataFrame({
        'row': rows_sel,
        'col': cols_sel,
        'x': xs,
        'y': ys,
        'piso_termico': _piso_sel,
        'pendiente_clase': _pend_sel,
        'tiene_monitoreo': mascara_monitoreo[rows_sel, cols_sel].astype(np.int8),
    })

    print(f"\n  Píxeles muestreados: {len(df_pixeles):,}")
    print(f"    Con monitoreo: {df_pixeles['tiene_monitoreo'].sum():,}")
    print(f"    Sin monitoreo: {(~df_pixeles['tiene_monitoreo'].astype(bool)).sum():,}")

    return df_pixeles


# ==================================================================
# PASO 6: EXTRAER FEATURES DE RASTERS
# ==================================================================

# Capas a excluir explícitamente de la vista minable
EXCLUIR_CAPAS = {
    'dem_cundinamarca',   # Alias de dem_elevacion, ya incluido como 'elevacion'
    # IGAC excluidos: cardinalidad extrema o redundantes con SoilGrids/topografía
    'igac_subgrupo',      # 1109 clases taxonomía USDA — redundante con propiedades suelo
    'igac_ucsuelo',       # ~500+ unidades cartográficas — similar a subgrupo
    'igac_clima',         # ~34 clases climáticas — ya capturado por IDEAM/CHIRPS
    'igac_paisaje',       # ~20 tipos — ya capturado por topografía
    'igac_material',      # ~15 tipos material parental — no afecta directamente al cultivo
    'igac_relieve',       # ~10 tipos — ya capturado por topografía
    'igac_calificacion',  # ~10 clases — redundante con fertilidad
    'igac_suma_bases',    # ~10 clases — correlacionado con CEC y fertilidad
}

# Índices Sentinel-2 excluidos del análisis estadístico
# (correlación alta con NDVI, ruido, o poca aportación diferencial)
S2_INDICES_EXCLUIR = {
    'evi',   # Alta correlación con NDVI (r>0.95); NDVI es más estable
    'ndwi',  # Mide contenido de agua en vegetación — redundante con humedad IDEAM e índice aridez
}

# Variables topográficas excluidas
TOPO_EXCLUIR = {
    'curvatura',  # Distribución casi uniforme ≈ 0; sin poder discriminante
}

# Variables SoilGrids excluidas
SOILGRIDS_PROPS_EXCLUIR = {
    'ocd',  # Densidad de carbono orgánico — altamente correlacionado con SOC (r>0.9)
}


def _definir_capas_estaticas():
    """Define las capas estáticas (no cambian por semestre)."""
    topo_dir = os.path.join(PROC_DIR, 'topo')
    sg_dir = os.path.join(PROC_DIR, 'suelo', 'soilgrids')
    igac_dir = os.path.join(PROC_DIR, 'suelo', 'igac')

    capas = {}

    # Topográficas (excluyendo alias como dem_cundinamarca, aspecto original y curvatura)
    # NOTA: 'aspecto' se excluye — usar aspecto_sin y aspecto_cos (engineered)
    # NOTA: 'curvatura' excluida — distribución casi uniforme ≈ 0, sin poder discriminante
    for var in ['elevacion', 'pendiente', 'twi']:
        path = os.path.join(topo_dir, f'dem_{var}_{RESOLUCION_M}m.tif')
        if os.path.exists(path) and var not in EXCLUIR_CAPAS:
            capas[var] = (path, 1)

    # SoilGrids 0-5 cm (profundidad principal para agricultura)
    # NOTA: ocd excluido — altamente correlacionado con SOC (r>0.9)
    for prop in ['phh2o', 'soc', 'nitrogen', 'cec', 'bdod']:
        path = os.path.join(sg_dir, f'soilgrids_{prop}_0_5cm.tif')
        if os.path.exists(path):
            capas[f'sg_{prop}'] = (path, 1)

    # SoilGrids texturas normalizadas 0-5 cm
    for tex in ['clay', 'sand', 'silt']:
        path = os.path.join(sg_dir, f'soilgrids_{tex}_0_5cm_norm.tif')
        if os.path.exists(path):
            capas[f'sg_{tex}'] = (path, 1)

    # IGAC — solo los que NO están en EXCLUIR_CAPAS
    igac_excluidos = []
    for f in glob.glob(os.path.join(igac_dir, 'igac_*.tif')):
        nombre = os.path.basename(f).replace('.tif', '')
        if nombre in EXCLUIR_CAPAS:
            igac_excluidos.append(nombre)
        else:
            capas[nombre] = (f, 1)
    if igac_excluidos:
        print(f"  IGAC excluidos ({len(igac_excluidos)}): {', '.join(igac_excluidos)}")

    # Features derivadas estáticas (incluye aspecto descompuesto sin/cos)
    for nombre in ['piso_termico', 'indice_fertilidad', 'aspecto_sin', 'aspecto_cos']:
        path = os.path.join(ENG_DIR, f'{nombre}.tif')
        if os.path.exists(path):
            capas[nombre] = (path, 1)

    # Variabilidad temporal del NDVI (mascara agricola).
    # ndvi_sigma_temporal: std de NDVI_max entre semestres por pixel.
    #   - Alta => ciclo de cultivo detectable (transitorios).
    #   - Baja  => vegetacion estable (bosque) o suelo desnudo.
    # ndvi_mean_temporal: media del NDVI_max entre semestres por pixel.
    #   - Combinado con sigma: bosque = mean alto + sigma bajo.
    # Generados por calcular_sigma_ndvi_temporal() en PASO 3e.
    for nombre in ['ndvi_sigma_temporal', 'ndvi_mean_temporal']:
        path = os.path.join(ENG_DIR, f'{nombre}.tif')
        if os.path.exists(path):
            capas[nombre] = (path, 1)

    return capas


def _definir_capas_semestrales(sem_label):
    """Define las capas que varían por semestre."""
    capas = {}

    # Agregados temporales IDEAM
    # NOTA: precipitacion_acum de IDEAM se excluye (100% ceros - kriging fallido).
    #       Se usa CHIRPS como fuente de precipitación (chirps_acum).
    ideam_dir = os.path.join(TEMP_DIR, 'clima', 'ideam')
    for var in ['temperatura_media', 'temperatura_max', 'temperatura_min',
                'humedad_media']:
        path = os.path.join(ideam_dir, f'{var}_{sem_label}.tif')
        if os.path.exists(path):
            capas[var] = (path, 1)

    # CHIRPS acumulado
    chirps_path = os.path.join(TEMP_DIR, 'clima', 'chirps', f'chirps_acum_{sem_label}.tif')
    if os.path.exists(chirps_path):
        capas['chirps_acum'] = (chirps_path, 1)

    # Sentinel-2 estadísticos semestrales
    # NOTA: EVI excluido — alta correlación con NDVI (r>0.95)
    # NOTA: NDWI excluido — redundante con humedad IDEAM e índice de aridez
    s2_dir = os.path.join(TEMP_DIR, 'satelite', 'sentinel2')
    for indice in ['ndvi', 'gndvi', 'msavi', 'bsi', 'savi']:
        for agg in ['media', 'max', 'std']:
            path = os.path.join(s2_dir, f's2_{indice}_{agg}_{sem_label}.tif')
            if os.path.exists(path):
                capas[f's2_{indice}_{agg}'] = (path, 1)

    # NOTA: Sentinel-1 EXCLUIDO de la vista minable.
    # Razón: 53% de datos faltantes (2022-2025) por fallo Sentinel-1B (dic 2021).
    # Solo aporta 3 features (VV, VH, VH/VV ratio) que son redundantes con:
    #   - Vegetación: Sentinel-2 (NDVI, GNDVI, SAVI, MSAVI, BSI — 5 índices)
    #   - Humedad: IDEAM + CHIRPS + índice de aridez
    # Para reincorporar, descomentar y re-ejecutar:
    # s1_dir = os.path.join(TEMP_DIR, 'satelite', 'sentinel1')
    # for banda in ['vv', 'vh', 'vh_vv_ratio']:
    #     path = os.path.join(s1_dir, f's1_{banda}_media_{sem_label}.tif')
    #     if os.path.exists(path):
    #         capas[f's1_{banda}_media'] = (path, 1)

    # Features derivadas por semestre
    for feat in ['amplitud_termica', 'anomalia_precip', 'ndvi_max',
                 'ndvi_integral', 'indice_aridez']:
        path = os.path.join(ENG_DIR, f'{feat}_{sem_label}.tif')
        if os.path.exists(path):
            capas[feat] = (path, 1)

    return capas


def extraer_features(df_pixeles, sem_label, capas_estaticas_cache=None):
    """
    Extrae valores de todas las capas raster para los píxeles muestreados.
    Retorna DataFrame con una columna por capa.
    """
    import rasterio

    rows = df_pixeles['row'].values
    cols = df_pixeles['col'].values

    # Capas estáticas (se cachean entre semestres)
    if capas_estaticas_cache is None:
        capas_estaticas_cache = {}
        capas_est = _definir_capas_estaticas()
        print(f"  Cargando {len(capas_est)} capas estáticas...")
        for nombre, (path, banda) in capas_est.items():
            try:
                arr, _ = _leer_raster(path, banda)
                capas_estaticas_cache[nombre] = arr
            except Exception as e:
                print(f"    Error cargando {nombre}: {e}")

    # Capas semestrales
    capas_sem = _definir_capas_semestrales(sem_label)

    # Extraer valores
    resultados = {}

    # Estáticas
    for nombre, arr in capas_estaticas_cache.items():
        resultados[nombre] = arr[rows, cols]

    # Semestrales
    for nombre, (path, banda) in capas_sem.items():
        try:
            arr, _ = _leer_raster(path, banda)
            resultados[nombre] = arr[rows, cols]
        except Exception as e:
            print(f"    Error cargando {nombre} [{sem_label}]: {e}")

    df_features = pd.DataFrame(resultados)
    return df_features, capas_estaticas_cache


# ==================================================================
# PASO 7: ASIGNAR ETIQUETAS TARGET
# ==================================================================

def asignar_target(df_pixeles, sem_label, monitoreo_por_semestre, eva_agg,
                   eva_top_dict, eva_dist_dict, mun_raster, sipra_noapta,
                   ndvi_max_global, profile):
    """
    Asigna etiquetas en 3 niveles + DISTRIBUCIÓN DE PROBABILIDAD (soft labels).

    Para cada píxel produce:
      - `cultivo`: argmax de la distribución (compat con pipeline hard-label actual)
      - `confianza`: meta-confianza de la fuente (1.0/0.7/0.4 según L1/L2/L3)
      - `prob_<cultivo>`: 14 columnas con la distribución P(clase | píxel)

    Lógica por nivel:

      L1 Monitoreo UPRA (conf=1.0)
         Distribución one-hot: P(cultivo_UPRA) = 1.0, resto = 0

      L2 EVA municipal (conf=0.7)
         Distribución completa del municipio-semestre:
           P(c) = area_cosechada_c / area_agrícola_total  para c ∈ EVA_municipio
         Esto implementa Learning from Label Proportions (LLP):
         en lugar de mentir diciendo "este pixel es Papa", decimos
         "este pixel tiene 40% Papa, 35% Café, 25% Frijol" (las proporciones
         reales del municipio según EVA).

      L3 No_apto (conf=0.4)
         Distribución one-hot: P(No_apto) = 1.0, resto = 0
         Se activa cuando SIPRA (>=3 capas "No apta") Y/O NDVI_max < 0.15.

    Píxeles sin etiqueta quedan con prob=0 en todas las clases y se filtran.
    """
    n = len(df_pixeles)
    K = len(MODEL_CLASSES)
    cultivo_a_id = {c: i for i, c in enumerate(MODEL_CLASSES)}
    id_otros = cultivo_a_id['Otros_cultivos']

    # Matriz de probabilidades (N × 14) — core del etiquetado soft
    prob_matrix = np.zeros((n, K), dtype=np.float32)

    # Compat: hard-label derivados (para notebooks viejos)
    cultivo = np.full(n, '', dtype=object)
    confianza = np.zeros(n, dtype=np.float32)
    fuente = np.full(n, '', dtype=object)
    rendimiento = np.full(n, np.nan, dtype=np.float32)

    rows = df_pixeles['row'].values
    cols = df_pixeles['col'].values

    # cod_mun por píxel (para GroupKFold espacial downstream). 0 = fuera de MGN.
    if mun_raster is not None:
        cod_mun_arr = mun_raster[rows, cols].astype(np.int32)
    else:
        cod_mun_arr = np.zeros(n, dtype=np.int32)

    # ───────── L1: Monitoreo UPRA (one-hot, conf=1.0) ─────────
    if sem_label in monitoreo_por_semestre:
        for cult_raw, masc in monitoreo_por_semestre[sem_label]:
            cult_norm = _normalizar_cultivo(cult_raw)
            k = cultivo_a_id.get(cult_norm, id_otros)
            hits = masc[rows, cols]
            idx_hits = np.where(hits & (confianza < 1.0))[0]
            if len(idx_hits) == 0:
                continue

            prob_matrix[idx_hits, :] = 0.0
            prob_matrix[idx_hits, k] = 1.0
            cultivo[idx_hits] = cult_norm
            confianza[idx_hits] = 1.0
            fuente[idx_hits] = 'monitoreo'

            # Rendimiento desde EVA agregado
            if eva_agg is not None and not eva_agg.empty:
                m = eva_agg[(eva_agg['semestre'] == sem_label) &
                            (eva_agg['cultivo_norm'] == cult_norm)]
                if not m.empty:
                    rend_val = m['rendimiento'].median()
                    if pd.notna(rend_val):
                        rendimiento[idx_hits] = float(rend_val)

    # ───────── L2: EVA municipal (DISTRIBUCIÓN completa, conf=0.7) ─────────
    # Cambio vs diseño hard-label: ya NO asignamos solo el cultivo dominante.
    # Asignamos la distribución completa según proporciones EVA del municipio.
    if mun_raster is not None and eva_dist_dict:
        idx_libres = np.where(confianza == 0)[0]
        if len(idx_libres) > 0:
            cod_pix = mun_raster[rows[idx_libres], cols[idx_libres]]
            mun_unicos, inv = np.unique(cod_pix, return_inverse=True)

            for i_mun, cod in enumerate(mun_unicos):
                if cod == 0:
                    continue  # fuera de Cundinamarca
                cod_str = str(int(cod)).zfill(5)
                dist = eva_dist_dict.get((cod_str, sem_label))
                if dist is None:
                    continue  # sin datos EVA para este mun-sem

                # Construir vector de probabilidad (14 clases) desde dist
                prob_vec = np.zeros(K, dtype=np.float32)
                for c_norm, score in dist.items():
                    k = cultivo_a_id.get(c_norm, id_otros)
                    prob_vec[k] += float(score)

                s = prob_vec.sum()
                if s <= 0:
                    continue
                prob_vec /= s  # normalizar a suma=1

                idx_en_mun = idx_libres[inv == i_mun]
                prob_matrix[idx_en_mun] = prob_vec

                # Hard-label derivado: argmax (para compat backward)
                k_max = int(np.argmax(prob_vec))
                cultivo[idx_en_mun] = MODEL_CLASSES[k_max]
                # Meta-confianza fija por fuente (la distribución captura
                # la concentración dentro del municipio)
                confianza[idx_en_mun] = 0.70
                fuente[idx_en_mun] = 'eva_municipal'

                # Rendimiento del cultivo dominante (para compat)
                top = eva_top_dict.get((cod_str, sem_label)) if eva_top_dict else None
                if top and top.get('rendimiento') is not None:
                    rendimiento[idx_en_mun] = top['rendimiento']

    # ───────── L3: No_apto (one-hot, conf=0.4) ─────────
    k_noapto = cultivo_a_id['No_apto']
    idx_libres = np.where(confianza == 0)[0]
    if len(idx_libres) > 0:
        es_noapto = np.zeros(len(idx_libres), dtype=bool)

        if sipra_noapta is not None:
            voto = sipra_noapta[rows[idx_libres], cols[idx_libres]]
            es_noapto |= (voto >= 3)

        if ndvi_max_global is not None:
            ndvi_pix = ndvi_max_global[rows[idx_libres], cols[idx_libres]]
            es_noapto |= (ndvi_pix < 0.15) & ~np.isnan(ndvi_pix)

        idx_noapto = idx_libres[es_noapto]
        if len(idx_noapto) > 0:
            prob_matrix[idx_noapto, :] = 0.0
            prob_matrix[idx_noapto, k_noapto] = 1.0
            cultivo[idx_noapto] = 'No_apto'
            confianza[idx_noapto] = 0.40
            fuente[idx_noapto] = 'noapto_proxy'

    # Construir DataFrame final: meta + hard-label + soft-label
    df_out = pd.DataFrame({
        'cod_mun': cod_mun_arr,
        'cultivo': cultivo,
        'confianza': confianza,
        'fuente': fuente,
        'rendimiento_tha': rendimiento,
    })
    # Añadir 14 columnas prob_<cultivo>
    for k, c in enumerate(MODEL_CLASSES):
        df_out[f'prob_{c}'] = prob_matrix[:, k]

    return df_out


# ==================================================================
# PASO 8: CONSTRUIR Y EXPORTAR VISTA MINABLE
# ==================================================================

def construir_vista_minable(max_pixeles=MAX_PIXELES_DEFAULT):
    """Pipeline completo: máscara → muestreo → extracción → target → parquet."""

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'vista_minable_full.parquet')

    if os.path.exists(out_path):
        print(f"\n  Ya existe: {out_path}")
        print("  Eliminar manualmente para regenerar.")
        return

    # Paso 1: Máscara
    mascara, profile = crear_mascara_valida()

    # Paso 2: Monitoreo UPRA (L1 - confianza=1.0)
    monitoreo = rasterizar_monitoreo(profile)

    # Paso 3: EVA agregado por clase canónica (L2 - alimenta etiqueta municipal)
    # eva_dist_dict: distribución completa por (mun, sem) — soft labels LLP
    eva_agg, eva_top_dict, eva_dist_dict = cargar_eva()

    # Paso 3b: MGN-DANE (lookup cod_mun por píxel, requerido por L2)
    mun_raster = rasterizar_municipios(profile)

    # Paso 3c: SIPRA consolidado (L3 - proxy No_apto)
    sipra_noapta = rasterizar_sipra_noapta(profile)

    # Paso 3d: NDVI_max global (L3 - proxy No_apto)
    ndvi_max_global = cargar_ndvi_max_ultimo_anio()

    # Paso 3e: Sigma NDVI temporal (mascara agricola -> columnas del parquet)
    # Genera ndvi_sigma_temporal.tif y ndvi_mean_temporal.tif en engineered/.
    # Si ya existen, los carga; si no hay >= 2 semestres, retorna (None, None).
    # Las columnas llegan al parquet via _definir_capas_estaticas() de forma
    # automatica; no se necesita pasarlas explicitamente a extraer_features().
    calcular_sigma_ndvi_temporal(profile)

    # Paso 5: Muestreo
    df_pixeles = muestrear_pixeles(mascara, profile, monitoreo, max_pixeles)

    # Paso 6-7: Iterar por semestre
    print("\n" + "=" * 70)
    print("PASO 6-7: EXTRAER FEATURES + ASIGNAR TARGET POR SEMESTRE")
    print("=" * 70)

    all_dfs = []
    capas_cache = None
    pixel_id_base = 0

    for sem in SEMESTRES:
        sem_label = sem['label']
        print(f"\n  --- Semestre {sem_label} ---")

        # Extraer features
        df_feat, capas_cache = extraer_features(df_pixeles, sem_label, capas_cache)

        # Asignar target (3 niveles: monitoreo -> EVA municipal -> No_apto)
        df_target = asignar_target(
            df_pixeles, sem_label, monitoreo, eva_agg, eva_top_dict,
            eva_dist_dict, mun_raster, sipra_noapta, ndvi_max_global, profile,
        )

        # Combinar (piso_termico ya viene en df_feat como feature estática)
        df_sem = pd.concat([
            df_pixeles[['x', 'y']].reset_index(drop=True),
            df_feat.reset_index(drop=True),
            df_target.reset_index(drop=True),
        ], axis=1)

        df_sem['semestre'] = sem_label
        df_sem['pixel_id'] = range(pixel_id_base, pixel_id_base + len(df_sem))
        pixel_id_base += len(df_sem)

        # Filtrar filas sin cultivo asignado
        df_sem = df_sem[df_sem['cultivo'].str.len() > 0]

        if len(df_sem) > 0:
            all_dfs.append(df_sem)
            n_mon = (df_sem['fuente'] == 'monitoreo').sum()
            print(f"  {sem_label}: {len(df_sem):,} filas etiquetadas "
                  f"(monitoreo={n_mon:,})")

    if not all_dfs:
        print("\n  Sin datos para generar la vista minable.")
        return

    # Paso 8: Concatenar y exportar
    print("\n" + "=" * 70)
    print("PASO 8: EXPORTAR VISTA MINABLE")
    print("=" * 70)

    vista = pd.concat(all_dfs, ignore_index=True)

    # Label encode cultivos usando MODEL_CLASSES (orden estable e independiente
    # de qué clases aparezcan en la muestra). Garantiza el mismo ID entre runs.
    cultivo_a_id = {c: i for i, c in enumerate(MODEL_CLASSES)}
    # Cualquier valor fuera del catálogo canónico cae a 'Otros_cultivos'
    # (no debería suceder porque asignar_target ya normaliza, pero es defensa).
    vista['cultivo'] = vista['cultivo'].where(
        vista['cultivo'].isin(MODEL_CLASSES), 'Otros_cultivos'
    )
    vista['cultivo_id'] = vista['cultivo'].map(cultivo_a_id).astype(np.int16)

    # Eliminar columnas duplicadas (seguridad)
    vista = vista.loc[:, ~vista.columns.duplicated()]

    # Reordenar columnas: metadata → features → target (hard) → prob (soft)
    meta_cols = ['pixel_id', 'x', 'y', 'semestre', 'cod_mun']
    target_cols = ['cultivo', 'cultivo_id', 'confianza', 'fuente', 'rendimiento_tha']
    prob_cols = [f'prob_{c}' for c in MODEL_CLASSES if f'prob_{c}' in vista.columns]
    feature_cols = [c for c in vista.columns
                    if c not in meta_cols + target_cols + prob_cols]

    vista = vista[meta_cols + feature_cols + target_cols + prob_cols]

    # Estadísticas
    print(f"\n  Dimensiones: {vista.shape[0]:,} filas × {vista.shape[1]} columnas")
    print(f"  Clases en muestra: {vista['cultivo'].nunique()} de {len(MODEL_CLASSES)} posibles")
    print(f"  Semestres: {vista['semestre'].nunique()}")

    # NaN report
    nan_pct = vista[feature_cols].isna().mean() * 100
    high_nan = nan_pct[nan_pct > 30]
    if len(high_nan) > 0:
        print(f"\n  ADVERTENCIA: {len(high_nan)} features con >30% NaN:")
        for col, pct in high_nan.sort_values(ascending=False).head(10).items():
            print(f"    {col}: {pct:.1f}%")

    # Distribución de fuentes
    print(f"\n  Distribución de fuentes:")
    for f, c in vista['fuente'].value_counts().items():
        print(f"    {f}: {c:,} ({100 * c / len(vista):.1f}%)")

    # Top 10 cultivos (hard-label, argmax)
    print(f"\n  Top 10 cultivos (hard-label):")
    for cult, c in vista['cultivo'].value_counts().head(10).items():
        print(f"    {cult}: {c:,}")

    # Masa de probabilidad total por clase (soft-label)
    # Suma de prob_<c> sobre todas las filas; refleja "área esperada" por clase.
    if prob_cols:
        print(f"\n  Masa soft-label por clase (suma de prob_<clase>):")
        soft_mass = vista[prob_cols].sum().sort_values(ascending=False)
        for col, mass in soft_mass.head(10).items():
            pct = 100 * mass / soft_mass.sum()
            print(f"    {col}: {mass:,.1f} ({pct:.1f}%)")
        # Entropía media por fuente — diagnóstico de ruido en etiquetas
        p_mat = vista[prob_cols].values.astype(np.float32)
        with np.errstate(divide='ignore', invalid='ignore'):
            p_clip = np.clip(p_mat, 1e-9, 1.0)
            entropia = -np.sum(p_mat * np.log(p_clip), axis=1)
        print(f"\n  Entropía media de distribución por fuente:")
        for f in vista['fuente'].unique():
            mask_f = (vista['fuente'] == f).values
            if mask_f.any():
                print(f"    {f:<15} H_mean={entropia[mask_f].mean():.3f} "
                      f"(0 = one-hot, {np.log(len(prob_cols)):.3f} = uniforme)")

    # Guardar catálogo de cultivos
    catalogo_path = os.path.join(OUT_DIR, 'catalogo_cultivos.json')
    with open(catalogo_path, 'w', encoding='utf-8') as f:
        json.dump(cultivo_a_id, f, ensure_ascii=False, indent=2)

    # Guardar parquet
    vista.to_parquet(out_path, index=False, compression='snappy')
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"\n  Guardado: {out_path} ({size_mb:.1f} MB)")
    print(f"  Catálogo: {catalogo_path}")

    return vista


# ==================================================================
# MAIN
# ==================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Construir vista minable: tabla rectangular para ML'
    )
    parser.add_argument(
        '--step',
        choices=['preparar', 'muestrear', 'extraer', 'exportar'],
        default=None,
        help='Paso a ejecutar. Sin --step ejecuta el pipeline completo.'
    )
    parser.add_argument(
        '--max-pixeles',
        type=int, default=MAX_PIXELES_DEFAULT,
        help=f'Máximo de píxeles a muestrear (default: {MAX_PIXELES_DEFAULT:,})'
    )
    args = parser.parse_args()

    print("=" * 70)
    print("CONSTRUCCIÓN DE VISTA MINABLE")
    print(f"Máximo píxeles: {args.max_pixeles:,}")
    print("=" * 70)

    if args.step is None:
        # Pipeline completo
        construir_vista_minable(args.max_pixeles)
    elif args.step == 'preparar':
        mascara, profile = crear_mascara_valida()
        monitoreo = rasterizar_monitoreo(profile)
        mun_raster = rasterizar_municipios(profile)
        sipra_noapta = rasterizar_sipra_noapta(profile)
        ndvi_max_g = cargar_ndvi_max_ultimo_anio()
        print(f"\n  Preparación completada:")
        print(f"    Semestres con monitoreo: {len(monitoreo)}")
        print(f"    MGN disponible: {mun_raster is not None}")
        print(f"    SIPRA No-apta disponible: {sipra_noapta is not None}")
        print(f"    NDVI_max disponible: {ndvi_max_g is not None}")
    elif args.step == 'muestrear':
        mascara, profile = crear_mascara_valida()
        monitoreo = rasterizar_monitoreo(profile)
        df = muestrear_pixeles(mascara, profile, monitoreo, args.max_pixeles)
        print(f"\n  Muestreo completado: {len(df):,} píxeles")
    elif args.step == 'extraer':
        print("  El paso 'extraer' requiere el pipeline completo. Use sin --step.")
    elif args.step == 'exportar':
        print("  El paso 'exportar' requiere el pipeline completo. Use sin --step.")

    print("\n" + "=" * 70)
    print("VISTA MINABLE COMPLETADA")
    print(f"Salida: {OUT_DIR}")
    print("=" * 70)


if __name__ == '__main__':
    main()
