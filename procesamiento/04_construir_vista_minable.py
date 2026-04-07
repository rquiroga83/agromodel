"""
04_construir_vista_minable.py
===================================================================
Construye la tabla rectangular (vista minable) que alimenta los modelos ML.

Cada fila = un (pixel, semestre).  Cada columna = un feature o target.

Entradas:
  - processed/            → capas estáticas y mensuales armonizadas
  - processed/temporal/   → estadísticos semestrales
  - processed/engineered/ → features derivadas
  - extractores/raw/target/ → EVA CSV, Monitoreo GeoJSON, SIPRA GeoJSON

Salida:
  - vista_minable/vista_minable_full.parquet

Operaciones:
  1. Crear máscara válida (píxeles con datos en DEM)
  2. Rasterizar polígonos de monitoreo UPRA → máscara de cultivos georreferenciados
  3. Rasterizar polígonos SIPRA → máscara de aptitud por cultivo
  4. Cargar EVA municipal → rendimiento y cultivos por municipio-semestre
  5. Muestreo estratificado: ~500K–1M píxeles
  6. Extraer 74+ features por píxel del stack de rasters
  7. Asignar etiquetas target con prioridad: monitoreo > EVA > SIPRA
  8. Guardar como Parquet

Uso:
    python 04_construir_vista_minable.py                      # Todo
    python 04_construir_vista_minable.py --step preparar      # Solo paso 1-3 (máscaras)
    python 04_construir_vista_minable.py --step muestrear     # Solo paso 4-5 (muestreo)
    python 04_construir_vista_minable.py --step extraer       # Solo paso 6-7 (extracción)
    python 04_construir_vista_minable.py --step exportar      # Solo paso 8 (parquet)
    python 04_construir_vista_minable.py --max-pixeles 200000 # Limitar muestreo

pip install rasterio geopandas pandas numpy pyarrow pyproj
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
from config import SEMESTRES, BBOX_WGS84, DEPT_DANE, RESOLUCION_M

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
# PASO 3: RASTERIZAR SIPRA → aptitud por cultivo
# ==================================================================

def rasterizar_sipra(profile):
    """
    Rasteriza polígonos SIPRA de aptitud.
    Retorna dict: {cultivo: {aptitud_clase: mascara_bool}}
    Solo incluye polígonos de Cundinamarca (cod_depart='25').
    """
    import geopandas as gpd
    from rasterio.features import rasterize

    print("\n" + "=" * 70)
    print("PASO 3: RASTERIZAR SIPRA APTITUD")
    print("=" * 70)

    sipra_dir = os.path.join(RAW_DIR, 'target', 'sipra')
    if not os.path.exists(sipra_dir):
        print("  Directorio SIPRA no encontrado. Saltando.")
        return {}

    archivos = sorted(glob.glob(os.path.join(sipra_dir, 'aptitud_*.geojson')))
    if not archivos:
        print("  Sin archivos SIPRA.")
        return {}

    transform = profile['transform']
    height = profile['height']
    width = profile['width']

    # Mapeo de aptitud a confianza
    APTITUD_CONFIANZA = {
        'alta': 0.5, 'media': 0.4, 'baja': 0.2, 'marginal': 0.15,
        'no apta': 0.0, 'exclusion legal': 0.0,
    }

    sipra_por_cultivo = {}

    for fpath in archivos:
        nombre = os.path.basename(fpath).replace('aptitud_', '').replace('.geojson', '')
        # Limpiar nombre: papa_capiro_s1 → Papa Capiro
        cultivo_parts = []
        for p in nombre.split('_'):
            if p in ('s1', 's2'):
                continue
            cultivo_parts.append(p.title())
        cultivo = ' '.join(cultivo_parts)

        print(f"  Procesando: {cultivo} ({os.path.basename(fpath)})...")

        try:
            # Leer solo features de Cundinamarca para reducir memoria
            gdf = gpd.read_file(fpath)
        except Exception as e:
            print(f"    Error leyendo: {e}")
            continue

        if gdf.empty:
            continue

        # Filtrar por Cundinamarca
        col_depto = None
        for c in ['cod_depart', 'cod_depto', 'COD_DEPART', 'COD_DEPTO']:
            if c in gdf.columns:
                col_depto = c
                break

        if col_depto:
            gdf = gdf[gdf[col_depto].astype(str).str.strip() == DEPT_DANE]

        if gdf.empty:
            print(f"    Sin datos para Cundinamarca.")
            continue

        # Reproyectar
        if gdf.crs is None or str(gdf.crs).upper() != TARGET_CRS:
            gdf = gdf.to_crs(TARGET_CRS)

        # Buscar campo de aptitud
        apt_col = None
        for c in ['aptitud', 'APTITUD', 'Aptitud']:
            if c in gdf.columns:
                apt_col = c
                break

        if apt_col is None:
            print(f"    Campo 'aptitud' no encontrado. Saltando.")
            continue

        # Rasterizar por clase de aptitud
        cultivo_mascaras = {}
        for apt_clase in gdf[apt_col].dropna().unique():
            apt_lower = str(apt_clase).strip().lower()
            confianza = APTITUD_CONFIANZA.get(apt_lower, 0.0)
            if confianza == 0.0:
                continue  # Ignorar "No apta" y "Exclusion legal"

            subset = gdf[gdf[apt_col] == apt_clase]
            geoms = [(g, 1) for g in subset.geometry if g is not None and g.is_valid]
            if not geoms:
                continue

            raster = rasterize(
                geoms, out_shape=(height, width),
                transform=transform, fill=0, dtype='uint8',
            )
            mascara = raster > 0
            n = np.count_nonzero(mascara)
            if n > 0:
                cultivo_mascaras[apt_lower] = (mascara, confianza)
                print(f"    {apt_clase}: {n:,} píxeles (confianza={confianza})")

        if cultivo_mascaras:
            sipra_por_cultivo[cultivo] = cultivo_mascaras

    print(f"\n  Total: {len(sipra_por_cultivo)} cultivos con aptitud rasterizada")
    return sipra_por_cultivo


# ==================================================================
# PASO 4: CARGAR EVA MUNICIPAL
# ==================================================================

def cargar_eva():
    """
    Carga EVA y retorna DataFrame con cultivos por municipio-semestre.
    Columnas: cod_mun, semestre, cultivo, rendimiento, area_cosechada
    """
    print("\n" + "=" * 70)
    print("PASO 4: CARGAR EVA MUNICIPAL")
    print("=" * 70)

    eva_dir = os.path.join(RAW_DIR, 'target', 'eva')

    dfs = []

    # EVA UPRA 2019-2024
    upra_path = os.path.join(eva_dir, 'eva_upra_2019_2024_cundinamarca.csv')
    if os.path.exists(upra_path):
        df = pd.read_csv(upra_path, dtype=str)
        df_clean = pd.DataFrame({
            'cod_mun': df['c_digo_dane_municipio'].str.strip(),
            'year': pd.to_numeric(df['a_o'], errors='coerce'),
            'cultivo': df['cultivo'].str.strip().str.title(),
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
        df = pd.read_csv(hist_path, dtype=str)
        df_clean = pd.DataFrame({
            'cod_mun': df['c_d_mun'].str.strip(),
            'year': pd.to_numeric(df['a_o'], errors='coerce'),
            'cultivo': df['cultivo'].str.strip().str.title(),
            'rendimiento': pd.to_numeric(df['rendimiento_t_ha'], errors='coerce'),
            'area_cosechada': pd.to_numeric(df['rea_cosechada_ha'], errors='coerce'),
            'area_sembrada': pd.to_numeric(df['rea_sembrada_ha'], errors='coerce'),
            'ciclo': df['ciclo_de_cultivo'].str.strip() if 'ciclo_de_cultivo' in df.columns else 'Transitorio',
        })
        dfs.append(df_clean)
        print(f"  EVA Histórica: {len(df_clean):,} registros")

    if not dfs:
        print("  Sin datos EVA.")
        return pd.DataFrame()

    eva = pd.concat(dfs, ignore_index=True)
    eva = eva.dropna(subset=['cod_mun', 'year', 'cultivo'])
    eva['year'] = eva['year'].astype(int)

    # Asignar semestre: cultivos transitorios se siembran en A y B.
    # Duplicar cada registro para ambos semestres del año.
    rows_a = eva.copy()
    rows_a['semestre'] = eva['year'].astype(str) + 'A'
    rows_b = eva.copy()
    rows_b['semestre'] = eva['year'].astype(str) + 'B'
    eva_sem = pd.concat([rows_a, rows_b], ignore_index=True)

    # Calcular score de aptitud revelada: area_cosechada relativa dentro del municipio-semestre
    eva_sem['area_cosechada'] = eva_sem['area_cosechada'].fillna(0)
    total_por_mun_sem = eva_sem.groupby(['cod_mun', 'semestre'])['area_cosechada'].transform('sum')
    eva_sem['score_aptitud'] = np.where(
        total_por_mun_sem > 0,
        eva_sem['area_cosechada'] / total_por_mun_sem,
        0.0
    )

    # Cultivos principales por municipio-semestre (top por area)
    eva_sem = eva_sem.sort_values('area_cosechada', ascending=False)
    eva_top = eva_sem.groupby(['cod_mun', 'semestre']).head(5)  # top 5 cultivos

    n_mun = eva_top['cod_mun'].nunique()
    n_cultivos = eva_top['cultivo'].nunique()
    print(f"  Total EVA: {len(eva_top):,} registros, "
          f"{n_mun} municipios, {n_cultivos} cultivos únicos")

    return eva_top


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

    # Combinar en ID de estrato
    estrato = (piso_v * 100 + pend_v * 10 + mon_v).astype(np.int16)

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

    df_pixeles = pd.DataFrame({
        'row': rows_sel,
        'col': cols_sel,
        'x': xs,
        'y': ys,
        'piso_termico': piso[rows_sel, cols_sel].astype(np.int8),
        'pendiente_clase': pend_clase[rows_sel, cols_sel].astype(np.int8),
        'tiene_monitoreo': mascara_monitoreo[rows_sel, cols_sel].astype(np.int8),
    })

    print(f"\n  Píxeles muestreados: {len(df_pixeles):,}")
    print(f"    Con monitoreo: {df_pixeles['tiene_monitoreo'].sum():,}")
    print(f"    Sin monitoreo: {(~df_pixeles['tiene_monitoreo'].astype(bool)).sum():,}")

    return df_pixeles


# ==================================================================
# PASO 6: EXTRAER FEATURES DE RASTERS
# ==================================================================

def _definir_capas_estaticas():
    """Define las capas estáticas (no cambian por semestre)."""
    topo_dir = os.path.join(PROC_DIR, 'topo')
    sg_dir = os.path.join(PROC_DIR, 'suelo', 'soilgrids')
    igac_dir = os.path.join(PROC_DIR, 'suelo', 'igac')

    capas = {}

    # Topográficas
    for var in ['elevacion', 'pendiente', 'aspecto', 'curvatura', 'twi']:
        path = os.path.join(topo_dir, f'dem_{var}_{RESOLUCION_M}m.tif')
        if os.path.exists(path):
            capas[var] = (path, 1)

    # SoilGrids 0-5 cm (profundidad principal para agricultura)
    for prop in ['phh2o', 'soc', 'nitrogen', 'cec', 'bdod', 'ocd']:
        path = os.path.join(sg_dir, f'soilgrids_{prop}_0_5cm.tif')
        if os.path.exists(path):
            capas[f'sg_{prop}'] = (path, 1)

    # SoilGrids texturas normalizadas 0-5 cm
    for tex in ['clay', 'sand', 'silt']:
        path = os.path.join(sg_dir, f'soilgrids_{tex}_0_5cm_norm.tif')
        if os.path.exists(path):
            capas[f'sg_{tex}'] = (path, 1)

    # IGAC (categóricos como int)
    for f in glob.glob(os.path.join(igac_dir, 'igac_*.tif')):
        nombre = os.path.basename(f).replace('.tif', '')
        capas[nombre] = (f, 1)

    # Features derivadas estáticas
    for nombre in ['piso_termico', 'indice_fertilidad']:
        path = os.path.join(ENG_DIR, f'{nombre}.tif')
        if os.path.exists(path):
            capas[nombre] = (path, 1)

    return capas


def _definir_capas_semestrales(sem_label):
    """Define las capas que varían por semestre."""
    capas = {}

    # Agregados temporales IDEAM
    ideam_dir = os.path.join(TEMP_DIR, 'clima', 'ideam')
    for var in ['temperatura_media', 'temperatura_max', 'temperatura_min',
                'precipitacion_acum', 'humedad_media']:
        path = os.path.join(ideam_dir, f'{var}_{sem_label}.tif')
        if os.path.exists(path):
            capas[var] = (path, 1)

    # CHIRPS acumulado
    chirps_path = os.path.join(TEMP_DIR, 'clima', 'chirps', f'chirps_acum_{sem_label}.tif')
    if os.path.exists(chirps_path):
        capas['chirps_acum'] = (chirps_path, 1)

    # Sentinel-2 estadísticos semestrales
    s2_dir = os.path.join(TEMP_DIR, 'satelite', 'sentinel2')
    for indice in ['ndvi', 'gndvi', 'evi', 'ndwi', 'msavi', 'bsi', 'savi']:
        for agg in ['media', 'max', 'std']:
            path = os.path.join(s2_dir, f's2_{indice}_{agg}_{sem_label}.tif')
            if os.path.exists(path):
                capas[f's2_{indice}_{agg}'] = (path, 1)

    # Sentinel-1 estadísticos semestrales
    s1_dir = os.path.join(TEMP_DIR, 'satelite', 'sentinel1')
    for banda in ['vv', 'vh', 'vh_vv_ratio']:
        path = os.path.join(s1_dir, f's1_{banda}_media_{sem_label}.tif')
        if os.path.exists(path):
            capas[f's1_{banda}_media'] = (path, 1)

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

def asignar_target(df_pixeles, sem_label, monitoreo_por_semestre,
                   sipra_por_cultivo, eva_df, profile):
    """
    Asigna etiquetas de cultivo con prioridad:
      1. Monitoreo UPRA (confianza=1.0) — polígonos georreferenciados
      2. EVA municipal (confianza=0.7) — distribución a nivel municipal
      3. SIPRA aptitud (confianza=0.5) — zonas de aptitud

    Retorna DataFrame con columnas: cultivo, confianza, fuente, rendimiento_tha
    """
    import rasterio
    from pyproj import Transformer

    n = len(df_pixeles)
    cultivo = np.full(n, '', dtype=object)
    confianza = np.zeros(n, dtype=np.float32)
    fuente = np.full(n, '', dtype=object)
    rendimiento = np.full(n, np.nan, dtype=np.float32)

    rows = df_pixeles['row'].values
    cols = df_pixeles['col'].values

    # --- Prioridad 3: SIPRA (se sobreescribe por las de mayor prioridad) ---
    if sipra_por_cultivo:
        for cult_nombre, mascaras_apt in sipra_por_cultivo.items():
            # Usar la aptitud más alta disponible
            mejor_apt = None
            mejor_conf = 0
            for apt_clase, (masc, conf) in mascaras_apt.items():
                if conf > mejor_conf:
                    mejor_apt = (masc, conf, apt_clase)
                    mejor_conf = conf

            if mejor_apt:
                masc, conf, apt = mejor_apt
                hits = masc[rows, cols]
                for i in np.where(hits)[0]:
                    if confianza[i] < conf:
                        cultivo[i] = cult_nombre
                        confianza[i] = conf
                        fuente[i] = 'sipra'

    # --- Prioridad 2: EVA municipal ---
    if not eva_df.empty:
        # Necesitamos mapear píxeles a municipios.
        # Usar la capa IGAC de municipios si existe, o asignar por coordenada.
        # Estrategia: usar un raster de códigos municipales si está disponible.
        # Si no, intentamos con las coordenadas X,Y → municipio más cercano vía EVA.
        # Por ahora usamos un enfoque simplificado: asignar el cultivo dominante
        # del municipio basado en la coordenada.

        # Verificar si hay un raster de municipios (de IGAC o similar)
        igac_ucsuelo = os.path.join(PROC_DIR, 'suelo', 'igac', 'igac_ucsuelo.tif')

        # Mapear píxeles a municipios usando un transformer
        # Las coordenadas ya están en EPSG:3116 pero EVA usa códigos DANE
        # Necesitamos un boundary. Sin shapefile de municipios, usamos
        # un approach diferente: para cada píxel con monitoreo=False,
        # asignar los cultivos dominantes a nivel departamental por semestre.

        # Filtrar EVA para este semestre
        eva_sem = eva_df[eva_df['semestre'] == sem_label]

        if not eva_sem.empty:
            # Top cultivos del departamento en este semestre
            top_cultivos = (eva_sem.groupby('cultivo')['area_cosechada']
                          .sum().sort_values(ascending=False).head(10))

            if len(top_cultivos) > 0:
                # Para píxeles sin etiqueta, asignar cultivo basado en
                # distribución departamental ponderada por piso térmico
                pisos = df_pixeles['piso_termico'].values

                # Construir tabla de cultivos por piso térmico desde EVA
                # (usando rendimiento como proxy de adaptabilidad)
                for idx_row in range(n):
                    if confianza[idx_row] >= 0.7:
                        continue  # Ya tiene etiqueta mejor

                    # Seleccionar cultivos adecuados para el piso térmico
                    piso_val = pisos[idx_row]
                    # Mapeo simplificado de pisos a cultivos
                    if piso_val == 0:  # Cálido
                        cult_piso = ['Arroz', 'Maiz', 'Cacao', 'Palma',
                                     'Cana Panelera', 'Yuca']
                    elif piso_val == 1:  # Templado
                        cult_piso = ['Cafe', 'Maiz', 'Cana Panelera',
                                     'Frijol', 'Aguacate', 'Platano']
                    elif piso_val == 2:  # Frío
                        cult_piso = ['Papa', 'Arveja', 'Cebolla', 'Fresa',
                                     'Maiz', 'Zanahoria', 'Frijol']
                    else:  # Páramo
                        cult_piso = ['Papa', 'Cebolla', 'Arveja']

                    # Buscar en EVA del semestre
                    candidatos = eva_sem[
                        eva_sem['cultivo'].str.lower().isin(
                            [c.lower() for c in cult_piso]
                        )
                    ]
                    if candidatos.empty:
                        candidatos = eva_sem.head(3)

                    if not candidatos.empty:
                        # Seleccionar top por area cosechada
                        top = candidatos.sort_values('area_cosechada',
                                                     ascending=False).iloc[0]
                        cultivo[idx_row] = top['cultivo']
                        confianza[idx_row] = 0.7 * top.get('score_aptitud', 0.5)
                        fuente[idx_row] = 'eva'
                        rend = top.get('rendimiento', np.nan)
                        if pd.notna(rend):
                            rendimiento[idx_row] = float(rend)

    # --- Prioridad 1: Monitoreo UPRA (sobreescribe todo) ---
    if sem_label in monitoreo_por_semestre:
        for cult_nombre, masc in monitoreo_por_semestre[sem_label]:
            hits = masc[rows, cols]
            for i in np.where(hits)[0]:
                cultivo[i] = cult_nombre
                confianza[i] = 1.0
                fuente[i] = 'monitoreo'
                # Buscar rendimiento en EVA para este cultivo
                if not eva_df.empty:
                    match = eva_df[
                        (eva_df['semestre'] == sem_label) &
                        (eva_df['cultivo'].str.lower() == cult_nombre.lower())
                    ]
                    if not match.empty:
                        rend_val = match['rendimiento'].median()
                        if pd.notna(rend_val):
                            rendimiento[i] = float(rend_val)

    return pd.DataFrame({
        'cultivo': cultivo,
        'confianza': confianza,
        'fuente': fuente,
        'rendimiento_tha': rendimiento,
    })


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

    # Paso 2: Monitoreo
    monitoreo = rasterizar_monitoreo(profile)

    # Paso 3: SIPRA
    sipra = rasterizar_sipra(profile)

    # Paso 4: EVA
    eva_df = cargar_eva()

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

        # Asignar target
        df_target = asignar_target(df_pixeles, sem_label, monitoreo, sipra,
                                   eva_df, profile)

        # Combinar
        df_sem = pd.concat([
            df_pixeles[['x', 'y', 'piso_termico']].reset_index(drop=True),
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
            n_eva = (df_sem['fuente'] == 'eva').sum()
            n_sipra = (df_sem['fuente'] == 'sipra').sum()
            print(f"  {sem_label}: {len(df_sem):,} filas "
                  f"(monitoreo={n_mon:,}, eva={n_eva:,}, sipra={n_sipra:,})")

    if not all_dfs:
        print("\n  Sin datos para generar la vista minable.")
        return

    # Paso 8: Concatenar y exportar
    print("\n" + "=" * 70)
    print("PASO 8: EXPORTAR VISTA MINABLE")
    print("=" * 70)

    vista = pd.concat(all_dfs, ignore_index=True)

    # Label encode cultivos
    cultivos_unicos = sorted(vista['cultivo'].unique())
    cultivo_a_id = {c: i for i, c in enumerate(cultivos_unicos)}
    vista['cultivo_id'] = vista['cultivo'].map(cultivo_a_id).astype(np.int16)

    # Reordenar columnas: metadata → features → target
    meta_cols = ['pixel_id', 'x', 'y', 'semestre']
    target_cols = ['cultivo', 'cultivo_id', 'confianza', 'fuente', 'rendimiento_tha']
    feature_cols = [c for c in vista.columns if c not in meta_cols + target_cols]

    vista = vista[meta_cols + feature_cols + target_cols]

    # Estadísticas
    print(f"\n  Dimensiones: {vista.shape[0]:,} filas × {vista.shape[1]} columnas")
    print(f"  Cultivos únicos: {len(cultivos_unicos)}")
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

    # Top 10 cultivos
    print(f"\n  Top 10 cultivos:")
    for cult, c in vista['cultivo'].value_counts().head(10).items():
        print(f"    {cult}: {c:,}")

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
        sipra = rasterizar_sipra(profile)
        print(f"\n  Preparación completada. "
              f"{len(monitoreo)} semestres con monitoreo, "
              f"{len(sipra)} cultivos SIPRA.")
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
