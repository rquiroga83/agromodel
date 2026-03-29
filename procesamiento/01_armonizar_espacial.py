"""
01_armonizar_espacial.py
═══════════════════════════════════════════════════════════════
Armonización espacial de todas las fuentes de datos crudas.

Entrada : extractores/raw/  (múltiples CRS, resoluciones, formatos)
Salida  : processed/        (todas las capas en EPSG:3116, 10 m × 10 m)

Operaciones por fuente:
  1. Estaciones IDEAM  → Kriging ordinario + corrección gradiente adiabático
  2. CHIRPS            → Reproyección + resampling bilineal desde ~5.3 km
  3. SoilGrids         → Bilineal (continuos) / nearest-neighbor (texturas)
  4. IGAC vectorial    → Rasterización de polígonos categóricos
  5. Sentinel-2        → Reproyección (bandas 20 m → bilineal a 10 m)
  6. Sentinel-1        → Solo reproyección (ya en 10 m nativo)
  7. DEM + derivadas   → Derivadas a 30 m PRIMERO, luego resamplear a 10 m

Uso:
    python 01_armonizar_espacial.py                # Armoniza todo
    python 01_armonizar_espacial.py --step ideam   # Solo estaciones IDEAM
    python 01_armonizar_espacial.py --step chirps
    python 01_armonizar_espacial.py --step soilgrids
    python 01_armonizar_espacial.py --step igac
    python 01_armonizar_espacial.py --step sentinel2
    python 01_armonizar_espacial.py --step sentinel1
    python 01_armonizar_espacial.py --step dem

pip install rasterio geopandas pykrige scipy numpy pyproj
"""

import argparse
import os
import sys
import glob
import warnings

import numpy as np

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extractores'))
from config import BBOX_WGS84, DIRS, SEMESTRES, crear_directorios

# ══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN ESPACIAL DEL PROYECTO
# ══════════════════════════════════════════════════════════════════

CRS_PROYECTO    = 'EPSG:3116'   # MAGNA-SIRGAS Colombia Bogotá
RESOLUCION_M    = 10            # 10 m × 10 m (alineado con Sentinel-2)
NODATA_RASTER   = -9999.0

# Directorio base del repositorio
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR     = os.path.join(BASE_DIR, 'extractores', 'raw')
PROC_DIR    = os.path.join(BASE_DIR, 'processed')

# Subdirectorios de salida
PROC_DIRS = {
    'ideam':      os.path.join(PROC_DIR, 'clima', 'ideam'),
    'chirps':     os.path.join(PROC_DIR, 'clima', 'chirps'),
    'soilgrids':  os.path.join(PROC_DIR, 'suelo', 'soilgrids'),
    'igac':       os.path.join(PROC_DIR, 'suelo', 'igac'),
    'sentinel2':  os.path.join(PROC_DIR, 'satelite', 'sentinel2'),
    'sentinel1':  os.path.join(PROC_DIR, 'satelite', 'sentinel1'),
    'dem':        os.path.join(PROC_DIR, 'topo'),
}


def crear_dirs_procesamiento():
    for path in PROC_DIRS.values():
        os.makedirs(path, exist_ok=True)
    print(f"Directorios de salida creados en: {PROC_DIR}")


# ══════════════════════════════════════════════════════════════════
# UTILIDADES COMUNES
# ══════════════════════════════════════════════════════════════════

def get_grid_cundinamarca():
    """
    Calcula el transform y dimensiones del grid objetivo:
    CRS_PROYECTO, RESOLUCION_M × RESOLUCION_M.

    Retorna (transform, width, height, crs)
    """
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds
    from pyproj import Transformer

    # Reproyectar bbox WGS84 → EPSG:3116
    transformer = Transformer.from_crs('EPSG:4326', CRS_PROYECTO, always_xy=True)
    west, south = transformer.transform(BBOX_WGS84[0], BBOX_WGS84[1])
    east, north = transformer.transform(BBOX_WGS84[2], BBOX_WGS84[3])

    width  = int((east - west)  / RESOLUCION_M)
    height = int((north - south) / RESOLUCION_M)
    transform = from_bounds(west, south, east, north, width, height)
    crs = CRS.from_epsg(3116)

    return transform, width, height, crs


def reproyectar_raster(src_path, dst_path, resampling_method='bilinear', dtype=None):
    """
    Reproyecta y remuestrea un GeoTIFF al grid objetivo del proyecto.

    Args:
        src_path        : ruta del raster de entrada
        dst_path        : ruta del raster de salida
        resampling_method: 'bilinear' | 'nearest' | 'cubic'
        dtype           : tipo de dato de salida (None = mismo que entrada)
    """
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    RESAMPLING = {
        'bilinear': Resampling.bilinear,
        'nearest':  Resampling.nearest,
        'cubic':    Resampling.cubic,
    }

    dst_transform, dst_width, dst_height, dst_crs = get_grid_cundinamarca()

    with rasterio.open(src_path) as src:
        src_dtype = dtype or src.dtypes[0]
        profile = src.profile.copy()
        profile.update(
            crs=dst_crs,
            transform=dst_transform,
            width=dst_width,
            height=dst_height,
            dtype=src_dtype,
            nodata=NODATA_RASTER,
            compress='deflate',
            driver='GTiff',
        )

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with rasterio.open(dst_path, 'w', **profile) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=RESAMPLING[resampling_method],
                )


# ══════════════════════════════════════════════════════════════════
# 1. ESTACIONES IDEAM — KRIGING + CORRECCIÓN ADIABÁTICA
# ══════════════════════════════════════════════════════════════════

def armonizar_ideam():
    """
    Interpola estaciones IDEAM a ráster 10 m usando Kriging Ordinario.

    Variables: temperatura (con corrección adiabática), precipitación, humedad.
    Salida: un GeoTIFF por variable×semestre en processed/clima/ideam/
    Requiere: DEM armonizado para la corrección de temperatura por altitud.
    """
    print("\n" + "="*70)
    print("1. ESTACIONES IDEAM → KRIGING")
    print("="*70)

    try:
        import pandas as pd
        import geopandas as gpd
        import rasterio
        from rasterio.transform import from_bounds
        from pykrige.ok import OrdinaryKriging
        from pyproj import Transformer
        from rasterio.crs import CRS
    except ImportError as e:
        print(f"  DEPENDENCIA FALTANTE: {e}")
        print("  Instalar: pip install pykrige geopandas pandas rasterio pyproj")
        return

    dst_transform, dst_width, dst_height, dst_crs = get_grid_cundinamarca()
    transformer = Transformer.from_crs('EPSG:4326', CRS_PROYECTO, always_xy=True)

    # Crear coordenadas del grid destino (centros de píxel)
    xs = np.arange(dst_width)  * RESOLUCION_M + dst_transform.c + RESOLUCION_M / 2
    ys = np.arange(dst_height) * (-RESOLUCION_M) + dst_transform.f - RESOLUCION_M / 2
    grid_x, grid_y = np.meshgrid(xs, ys)

    # ── Cargar DEM armonizado si existe (para corrección adiabática) ──
    dem_path = os.path.join(PROC_DIRS['dem'], 'dem_cundinamarca_10m.tif')
    dem_grid = None
    if os.path.exists(dem_path):
        with rasterio.open(dem_path) as src:
            dem_grid = src.read(1).astype(np.float32)
            dem_grid[dem_grid == src.nodata] = np.nan
        print("  DEM cargado para corrección adiabática de temperatura")
    else:
        print("  AVISO: DEM no encontrado, la temperatura NO tendrá corrección adiabática")
        print(f"         Ejecutar primero: python 01_armonizar_espacial.py --step dem")

    variables = {
        'temperatura': {
            'patron': os.path.join(RAW_DIR, 'clima', 'ideam_temperatura', '*.csv'),
            'col_valor':  'valorobservado',
            'col_lat':    'latitud',
            'col_lon':    'longitud',
            'col_fecha':  'fechaobservacion',
            'col_alt':    'altitud',        # columna de altitud en estación (puede no existir)
            'adiabático': True,             # aplicar corrección -6°C/1000m
            'variogram':  'spherical',
        },
        'precipitacion': {
            'patron': os.path.join(RAW_DIR, 'clima', 'ideam_precipitacion', '*.csv'),
            'col_valor':  'valorobservado',
            'col_lat':    'latitud',
            'col_lon':    'longitud',
            'col_fecha':  'fechaobservacion',
            'col_alt':    'altitud',
            'adiabático': False,
            'variogram':  'spherical',
        },
        'humedad': {
            'patron': os.path.join(RAW_DIR, 'clima', 'ideam_humedad', '*.csv'),
            'col_valor':  'valorobservado',
            'col_lat':    'latitud',
            'col_lon':    'longitud',
            'col_fecha':  'fechaobservacion',
            'col_alt':    'altitud',
            'adiabático': False,
            'variogram':  'spherical',
        },
    }

    for var_name, cfg in variables.items():
        archivos = glob.glob(cfg['patron'])
        if not archivos:
            print(f"  [{var_name}] Sin archivos en {cfg['patron']}. Saltando.")
            continue

        print(f"\n  Cargando {var_name} ({len(archivos)} archivos)...")
        try:
            dfs = []
            for f in archivos:
                df = pd.read_csv(f, low_memory=False)
                dfs.append(df)
            df_all = pd.concat(dfs, ignore_index=True)
        except Exception as e:
            print(f"  Error cargando CSVs: {e}")
            continue

        # Limpiar y convertir tipos
        for col in [cfg['col_valor'], cfg['col_lat'], cfg['col_lon']]:
            df_all[col] = pd.to_numeric(df_all[col], errors='coerce')
        df_all[cfg['col_fecha']] = pd.to_datetime(df_all[cfg['col_fecha']], errors='coerce')
        df_all = df_all.dropna(subset=[cfg['col_valor'], cfg['col_lat'],
                                        cfg['col_lon'], cfg['col_fecha']])

        # Reproyectar coordenadas de estaciones a EPSG:3116
        ex, ey = transformer.transform(df_all[cfg['col_lon']].values,
                                        df_all[cfg['col_lat']].values)
        df_all['_x_3116'] = ex
        df_all['_y_3116'] = ey

        # Columna altitud de estación (si existe)
        if cfg['col_alt'] in df_all.columns:
            df_all[cfg['col_alt']] = pd.to_numeric(df_all[cfg['col_alt']], errors='coerce')

        # Procesar por semestre
        for sem in SEMESTRES:
            label   = sem['label']
            t_start = pd.Timestamp(sem['start'])
            t_end   = pd.Timestamp(sem['end'])

            out_file = os.path.join(PROC_DIRS['ideam'],
                                    f"{var_name}_{label}_kriging.tif")
            if os.path.exists(out_file):
                print(f"  [{var_name} {label}] Ya existe. Saltando.")
                continue

            # Filtrar semestre y agregar por estación (mediana)
            mask = (df_all[cfg['col_fecha']] >= t_start) & \
                   (df_all[cfg['col_fecha']] <= t_end)
            df_sem = df_all[mask]
            if df_sem.empty:
                print(f"  [{var_name} {label}] Sin datos.")
                continue

            cols_group = ['_x_3116', '_y_3116']
            if cfg['col_alt'] in df_sem.columns:
                cols_group.append(cfg['col_alt'])

            estaciones = df_sem.groupby(cols_group, as_index=False)[cfg['col_valor']].median()
            estaciones = estaciones.dropna()

            if len(estaciones) < 4:
                print(f"  [{var_name} {label}] Menos de 4 estaciones ({len(estaciones)}). "
                      f"Insuficiente para Kriging.")
                continue

            x_est = estaciones['_x_3116'].values
            y_est = estaciones['_y_3116'].values
            z_est = estaciones[cfg['col_valor']].values

            # Corrección adiabática de temperatura (-6°C por cada 1000m sobre la estación)
            if cfg['adiabático'] and cfg['col_alt'] in estaciones.columns:
                alt_est = estaciones[cfg['col_alt']].values
                alt_est = np.where(np.isnan(alt_est), 0, alt_est)
                alt_ref = np.nanmedian(alt_est)
                z_est = z_est - 0.006 * (alt_est - alt_ref)

            print(f"  [{var_name} {label}] Kriging con {len(estaciones)} estaciones...",
                  end=' ', flush=True)

            try:
                ok = OrdinaryKriging(
                    x_est, y_est, z_est,
                    variogram_model=cfg['variogram'],
                    verbose=False,
                    enable_plotting=False,
                )
                z_pred, z_var = ok.execute('grid', xs, ys[::-1])  # ys invertido (N→S)
                z_pred = np.flipud(z_pred.data.astype(np.float32))

                # Reaplicar corrección adiabática sobre el grid con DEM
                if cfg['adiabático'] and dem_grid is not None:
                    alt_ref = float(np.nanmedian(estaciones.get(cfg['col_alt'],
                                                                 pd.Series([0])).values))
                    dem_valid = np.where(np.isnan(dem_grid), alt_ref, dem_grid)
                    z_pred = z_pred - 0.006 * (dem_valid - alt_ref)

                z_pred = z_pred.astype(np.float32)
                z_pred[np.isnan(z_pred)] = NODATA_RASTER

                profile = dict(
                    driver='GTiff', dtype='float32', count=1,
                    crs=dst_crs, transform=dst_transform,
                    width=dst_width, height=dst_height,
                    nodata=NODATA_RASTER, compress='deflate',
                )
                os.makedirs(PROC_DIRS['ideam'], exist_ok=True)
                with rasterio.open(out_file, 'w', **profile) as dst:
                    dst.write(z_pred, 1)
                print(f"guardado.")
            except Exception as e:
                print(f"error: {e}")

    print("\n  IDEAM armonizado.")


# ══════════════════════════════════════════════════════════════════
# 2. CHIRPS — BILINEAL DESDE ~5.3 KM
# ══════════════════════════════════════════════════════════════════

def armonizar_chirps():
    """
    Reproyecta y remuestrea los GeoTIFF mensuales de CHIRPS (~5.3 km)
    al grid 10 m del proyecto con resampling bilineal.
    """
    print("\n" + "="*70)
    print("2. CHIRPS → BILINEAL A 10 m")
    print("="*70)

    patron = os.path.join(RAW_DIR, 'clima', 'chirps', '*.tif')
    archivos = sorted(glob.glob(patron))

    if not archivos:
        print(f"  Sin archivos CHIRPS en {patron}. Saltando.")
        return

    print(f"  {len(archivos)} archivos encontrados.")
    for src_path in archivos:
        nombre = os.path.basename(src_path)
        dst_path = os.path.join(PROC_DIRS['chirps'], nombre)

        if os.path.exists(dst_path):
            print(f"  Ya existe: {nombre}")
            continue

        print(f"  Reproyectando: {nombre}...", end=' ', flush=True)
        try:
            reproyectar_raster(src_path, dst_path, resampling_method='bilinear')
            print("OK")
        except Exception as e:
            print(f"Error: {e}")

    print("  CHIRPS armonizado.")


# ══════════════════════════════════════════════════════════════════
# 3. SOILGRIDS — BILINEAL (CONTINUOS) / NEAREST (TEXTURAS)
# ══════════════════════════════════════════════════════════════════

def armonizar_soilgrids():
    """
    Reproyecta SoilGrids de 250 m a 10 m.
    - Propiedades continuas (ph, soc, bdod, cec, nitrogen, ocd): bilineal
    - Texturas (clay, sand, silt): nearest-neighbor + normalización a 100%
    """
    print("\n" + "="*70)
    print("3. SOILGRIDS → 10 m")
    print("="*70)

    TEXTURA_PROPS = {'clay', 'sand', 'silt'}

    patron = os.path.join(RAW_DIR, 'suelo', 'soilgrids', '*.tif')
    archivos = sorted(glob.glob(patron))

    if not archivos:
        print(f"  Sin archivos SoilGrids en {patron}. Saltando.")
        return

    print(f"  {len(archivos)} archivos encontrados.")
    arrays_textura = {}  # para normalización

    for src_path in archivos:
        nombre = os.path.basename(src_path)
        dst_path = os.path.join(PROC_DIRS['soilgrids'], nombre)

        if os.path.exists(dst_path):
            print(f"  Ya existe: {nombre}")
            continue

        # Determinar tipo de resampling
        es_textura = any(t in nombre.lower() for t in TEXTURA_PROPS)
        metodo = 'nearest' if es_textura else 'bilineal'
        metodo_rasterio = 'nearest' if es_textura else 'bilinear'

        print(f"  {nombre} ({metodo})...", end=' ', flush=True)
        try:
            reproyectar_raster(src_path, dst_path, resampling_method=metodo_rasterio)
            print("OK")
        except Exception as e:
            print(f"Error: {e}")

    # Normalizar texturas para que clay+sand+silt=100% por píxel
    _normalizar_texturas_soilgrids()
    print("  SoilGrids armonizado.")


def _normalizar_texturas_soilgrids():
    """Para cada profundidad, normaliza clay+sand+silt a 100%."""
    import rasterio

    profundidades = ['0_5', '5_15', '15_30']
    for prof in profundidades:
        paths = {
            t: os.path.join(PROC_DIRS['soilgrids'], f'soilgrids_{t}_{prof}cm.tif')
            for t in ['clay', 'sand', 'silt']
        }
        if not all(os.path.exists(p) for p in paths.values()):
            continue

        arrays = {}
        profile = None
        for t, p in paths.items():
            with rasterio.open(p) as src:
                arrays[t] = src.read(1).astype(np.float32)
                arrays[t][arrays[t] == NODATA_RASTER] = np.nan
                if profile is None:
                    profile = src.profile.copy()

        total = arrays['clay'] + arrays['sand'] + arrays['silt']
        for t in arrays:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                arrays[t] = np.where(total > 0, arrays[t] / total * 100, np.nan)
            out_path = os.path.join(PROC_DIRS['soilgrids'], f'soilgrids_{t}_{prof}cm_norm.tif')
            arr = np.where(np.isnan(arrays[t]), NODATA_RASTER, arrays[t]).astype(np.float32)
            with rasterio.open(out_path, 'w', **profile) as dst:
                dst.write(arr, 1)

    print("  Texturas SoilGrids normalizadas (clay+sand+silt=100%).")


# ══════════════════════════════════════════════════════════════════
# 4. IGAC VECTORIAL → RASTERIZACIÓN
# ══════════════════════════════════════════════════════════════════

def armonizar_igac():
    """
    Rasteriza los GeoJSON del IGAC al grid 10 m del proyecto.
    - Propiedades Químicas: fertilidad (categórico), pH (continuo), Al, P, K
    - Vocación de Uso: código de vocación (categórico)
    """
    print("\n" + "="*70)
    print("4. IGAC VECTORIAL → RASTERIZACIÓN A 10 m")
    print("="*70)

    try:
        import geopandas as gpd
        import rasterio
        from rasterio.features import rasterize
        from rasterio.crs import CRS
    except ImportError as e:
        print(f"  DEPENDENCIA FALTANTE: {e}. pip install geopandas rasterio")
        return

    dst_transform, dst_width, dst_height, dst_crs = get_grid_cundinamarca()

    capas = [
        {
            'input': os.path.join(RAW_DIR, 'suelo', 'igac_quimica',
                                  'propiedades_quimicas_suelo.geojson'),
            'campos': {
                'FERTIL':    ('fertilidad_igac.tif',    'int16',  'nearest'),
                'PH_AGUA':   ('ph_agua_igac.tif',        'float32', 'bilinear'),
                'SAT_AL':    ('sat_aluminio_igac.tif',   'float32', 'bilinear'),
                'FOSFORO':   ('fosforo_igac.tif',        'float32', 'bilinear'),
                'POTASIO':   ('potasio_igac.tif',        'float32', 'bilinear'),
            },
        },
        {
            'input': os.path.join(RAW_DIR, 'suelo', 'igac_vocacion',
                                  'vocacion_uso_suelo.geojson'),
            'campos': {
                'VOCACION':  ('vocacion_uso_igac.tif',   'int16',  'nearest'),
            },
        },
    ]

    for capa in capas:
        if not os.path.exists(capa['input']):
            print(f"  No encontrado: {capa['input']}. Saltando.")
            continue

        print(f"  Cargando: {os.path.basename(capa['input'])}...", end=' ', flush=True)
        try:
            gdf = gpd.read_file(capa['input'])
            gdf = gdf.to_crs(CRS_PROYECTO)
            print(f"{len(gdf)} polígonos")
        except Exception as e:
            print(f"Error: {e}")
            continue

        for campo, (out_nombre, dtype, _) in capa['campos'].items():
            out_path = os.path.join(PROC_DIRS['igac'], out_nombre)
            if os.path.exists(out_path):
                print(f"  Ya existe: {out_nombre}")
                continue

            # Buscar el campo con variantes de nombre (IGAC a veces cambia el case)
            col = next((c for c in gdf.columns if c.upper() == campo.upper()), None)
            if col is None:
                print(f"  Campo '{campo}' no encontrado. Columnas disponibles: "
                      f"{list(gdf.columns[:10])}")
                continue

            print(f"  Rasterizando '{col}' → {out_nombre}...", end=' ', flush=True)
            try:
                gdf_valid = gdf[[col, 'geometry']].dropna()

                if dtype == 'int16':
                    # Codificar categóricos a enteros
                    gdf_valid = gdf_valid.copy()
                    cats = {v: i+1 for i, v in enumerate(gdf_valid[col].unique())}
                    gdf_valid['_code'] = gdf_valid[col].map(cats).astype('float32')
                    col_rast = '_code'
                    nodata_val = 0
                else:
                    gdf_valid['_val'] = pd.to_numeric(gdf_valid[col], errors='coerce')
                    gdf_valid = gdf_valid.dropna(subset=['_val'])
                    col_rast = '_val'
                    nodata_val = NODATA_RASTER

                shapes = (
                    (geom, val)
                    for geom, val in zip(gdf_valid.geometry, gdf_valid[col_rast])
                    if geom is not None and not np.isnan(float(val))
                )

                rast = rasterize(
                    shapes,
                    out_shape=(dst_height, dst_width),
                    transform=dst_transform,
                    fill=nodata_val,
                    dtype=dtype,
                )

                profile = dict(
                    driver='GTiff', dtype=dtype, count=1,
                    crs=dst_crs, transform=dst_transform,
                    width=dst_width, height=dst_height,
                    nodata=nodata_val, compress='deflate',
                )
                os.makedirs(PROC_DIRS['igac'], exist_ok=True)
                with rasterio.open(out_path, 'w', **profile) as dst_f:
                    dst_f.write(rast, 1)

                # Guardar tabla de códigos para categóricos
                if dtype == 'int16' and '_code' in gdf_valid.columns:
                    import json
                    tabla_path = out_path.replace('.tif', '_tabla_codigos.json')
                    with open(tabla_path, 'w') as f:
                        json.dump({str(v): k for k, v in cats.items()}, f,
                                  ensure_ascii=False, indent=2)
                print("OK")
            except Exception as e:
                print(f"Error: {e}")

    print("  IGAC armonizado.")


# ══════════════════════════════════════════════════════════════════
# 5. SENTINEL-2 — REPROYECCIÓN + BANDAS 20 m → 10 m
# ══════════════════════════════════════════════════════════════════

def armonizar_sentinel2():
    """
    Reproyecta GeoTIFF de Sentinel-2 al CRS y resolución del proyecto.
    Bandas nativas a 10 m: reproyectar.
    Bandas nativas a 20 m: bilineal + reproyectar.
    """
    print("\n" + "="*70)
    print("5. SENTINEL-2 → REPROYECCIÓN A EPSG:3116 / 10 m")
    print("="*70)

    patron = os.path.join(RAW_DIR, 'satelite', 'sentinel2', '*.tif')
    archivos = sorted(glob.glob(patron))

    if not archivos:
        print(f"  Sin archivos Sentinel-2 en {patron}. Saltando.")
        return

    print(f"  {len(archivos)} archivos encontrados.")
    for src_path in archivos:
        nombre = os.path.basename(src_path)
        dst_path = os.path.join(PROC_DIRS['sentinel2'], nombre)

        if os.path.exists(dst_path):
            print(f"  Ya existe: {nombre}")
            continue

        print(f"  {nombre}...", end=' ', flush=True)
        try:
            # Bilineal: válido tanto para bandas 10 m como 20 m (upsampling fino)
            reproyectar_raster(src_path, dst_path, resampling_method='bilinear')
            print("OK")
        except Exception as e:
            print(f"Error: {e}")

    print("  Sentinel-2 armonizado.")


# ══════════════════════════════════════════════════════════════════
# 6. SENTINEL-1 — SOLO REPROYECCIÓN
# ══════════════════════════════════════════════════════════════════

def armonizar_sentinel1():
    """
    Reproyecta Sentinel-1 GRD al CRS del proyecto.
    Ya está en resolución 10 m nativa → solo cambio de CRS.
    """
    print("\n" + "="*70)
    print("6. SENTINEL-1 → REPROYECCIÓN A EPSG:3116")
    print("="*70)

    patron = os.path.join(RAW_DIR, 'satelite', 'sentinel1', '*.tif')
    archivos = sorted(glob.glob(patron))

    if not archivos:
        print(f"  Sin archivos Sentinel-1 en {patron}. Saltando.")
        return

    print(f"  {len(archivos)} archivos encontrados.")
    for src_path in archivos:
        nombre = os.path.basename(src_path)
        dst_path = os.path.join(PROC_DIRS['sentinel1'], nombre)

        if os.path.exists(dst_path):
            print(f"  Ya existe: {nombre}")
            continue

        print(f"  {nombre}...", end=' ', flush=True)
        try:
            reproyectar_raster(src_path, dst_path, resampling_method='bilinear')
            print("OK")
        except Exception as e:
            print(f"Error: {e}")

    print("  Sentinel-1 armonizado.")


# ══════════════════════════════════════════════════════════════════
# 7. DEM + DERIVADAS TOPOGRÁFICAS
# ══════════════════════════════════════════════════════════════════

def armonizar_dem():
    """
    Reproyecta el DEM Copernicus GLO-30 (30 m) a 10 m.

    Estrategia: calcular derivadas (pendiente, aspecto, curvatura, TWI)
    a la resolución ORIGINAL de 30 m PRIMERO, luego resamplear todo a 10 m.
    Esto evita artefactos de interpolación en derivadas de segundo orden.
    """
    print("\n" + "="*70)
    print("7. DEM COPERNICUS → DERIVADAS A 30 m + RESAMPLING A 10 m")
    print("="*70)

    try:
        import rasterio
        from scipy.ndimage import convolve
    except ImportError as e:
        print(f"  DEPENDENCIA FALTANTE: {e}")
        return

    # El extractor guarda un multibanda con [elev, pendiente, aspecto, curvatura, twi]
    src_path = os.path.join(RAW_DIR, 'topo', 'dem_glo30', 'cundinamarca_topografia.tif')
    if not os.path.exists(src_path):
        # Intentar con el DEM sin derivadas
        src_path = os.path.join(RAW_DIR, 'topo', 'dem_glo30', 'dem_cundinamarca.tif')
        if not os.path.exists(src_path):
            print(f"  DEM no encontrado en {os.path.dirname(src_path)}. Saltando.")
            return

    nombres_bandas = ['elevacion', 'pendiente', 'aspecto', 'curvatura', 'twi']

    with rasterio.open(src_path) as src:
        n_bandas = src.count
        print(f"  DEM: {src.width}×{src.height} px, {n_bandas} banda(s), CRS: {src.crs}")

    # Reproyectar cada banda individualmente
    for i, nombre in enumerate(nombres_bandas[:n_bandas], start=1):
        out_path = os.path.join(PROC_DIRS['dem'], f'dem_{nombre}_10m.tif')
        if os.path.exists(out_path):
            print(f"  Ya existe: {os.path.basename(out_path)}")
            continue

        print(f"  Banda {i} ({nombre})...", end=' ', flush=True)
        try:
            import rasterio
            from rasterio.warp import reproject, Resampling

            dst_transform, dst_width, dst_height, dst_crs = get_grid_cundinamarca()

            with rasterio.open(src_path) as src:
                data_src = src.read(i).astype(np.float32)
                nodata_src = src.nodata or NODATA_RASTER

                profile = dict(
                    driver='GTiff', dtype='float32', count=1,
                    crs=dst_crs, transform=dst_transform,
                    width=dst_width, height=dst_height,
                    nodata=NODATA_RASTER, compress='deflate',
                )
                os.makedirs(PROC_DIRS['dem'], exist_ok=True)
                with rasterio.open(out_path, 'w', **profile) as dst:
                    reproject(
                        source=data_src,
                        destination=rasterio.band(dst, 1),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=dst_transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear,
                        src_nodata=nodata_src,
                        dst_nodata=NODATA_RASTER,
                    )
            print("OK")
        except Exception as e:
            print(f"Error: {e}")

    # Archivo de elevación para uso en corrección adiabática de temperatura
    elev_src = os.path.join(PROC_DIRS['dem'], 'dem_elevacion_10m.tif')
    elev_dst = os.path.join(PROC_DIRS['dem'], 'dem_cundinamarca_10m.tif')
    if os.path.exists(elev_src) and not os.path.exists(elev_dst):
        import shutil
        shutil.copy2(elev_src, elev_dst)
        print(f"  Alias DEM creado: {os.path.basename(elev_dst)}")

    print("  DEM armonizado.")


# ══════════════════════════════════════════════════════════════════
# VALIDACIÓN DE SALIDAS
# ══════════════════════════════════════════════════════════════════

def validar_capas():
    """
    Verifica que todas las capas procesadas compartan extent, resolución y CRS.
    También valida rangos físicos esperados.
    """
    import rasterio

    print("\n" + "="*70)
    print("VALIDACIÓN DE CAPAS ARMONIZADAS")
    print("="*70)

    dst_transform, dst_width, dst_height, dst_crs = get_grid_cundinamarca()

    RANGOS = {
        'temperatura': (-5, 40),
        'precipitacion': (0, 800),
        'humedad': (0, 100),
        'elevacion': (100, 4000),
        'pendiente': (0, 90),
        'ph': (3, 9),
    }

    archivos = glob.glob(os.path.join(PROC_DIR, '**', '*.tif'), recursive=True)
    errores = []
    ok = 0

    for path in archivos:
        nombre = os.path.relpath(path, PROC_DIR)
        try:
            with rasterio.open(path) as src:
                match_crs = src.crs.to_epsg() == 3116
                match_w   = src.width == dst_width
                match_h   = src.height == dst_height

                if not (match_crs and match_w and match_h):
                    errores.append(
                        f"  ✗ {nombre}: CRS={src.crs.to_epsg()} "
                        f"({dst_width}×{dst_height} esperado, "
                        f"got {src.width}×{src.height})"
                    )
                else:
                    ok += 1

                # Validar rangos físicos
                for kw, (vmin, vmax) in RANGOS.items():
                    if kw in nombre.lower():
                        data = src.read(1)
                        data_valid = data[data != src.nodata] if src.nodata else data.ravel()
                        if len(data_valid) > 0:
                            dmin, dmax = float(data_valid.min()), float(data_valid.max())
                            if dmin < vmin or dmax > vmax:
                                errores.append(
                                    f"  ⚠ {nombre}: rango {dmin:.1f}–{dmax:.1f} "
                                    f"fuera de [{vmin}, {vmax}]"
                                )
        except Exception as e:
            errores.append(f"  ✗ {nombre}: {e}")

    print(f"  Capas OK: {ok}")
    if errores:
        print(f"  Problemas ({len(errores)}):")
        for e in errores:
            print(e)
    else:
        print("  Todas las capas son consistentes.")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Armonización espacial de datos crudos → processed/ (EPSG:3116, 10 m)'
    )
    parser.add_argument(
        '--step',
        choices=['ideam', 'chirps', 'soilgrids', 'igac',
                 'sentinel2', 'sentinel1', 'dem', 'validar'],
        default=None,
        help='Paso a ejecutar. Sin --step ejecuta todos.'
    )
    args = parser.parse_args()

    crear_dirs_procesamiento()

    pasos = {
        'ideam':     armonizar_ideam,
        'chirps':    armonizar_chirps,
        'soilgrids': armonizar_soilgrids,
        'igac':      armonizar_igac,
        'sentinel2': armonizar_sentinel2,
        'sentinel1': armonizar_sentinel1,
        'dem':       armonizar_dem,
        'validar':   validar_capas,
    }

    if args.step:
        pasos[args.step]()
    else:
        # Orden importante: DEM primero (lo usa la corrección adiabática de IDEAM)
        for nombre in ['dem', 'ideam', 'chirps', 'soilgrids',
                       'igac', 'sentinel2', 'sentinel1', 'validar']:
            pasos[nombre]()

    print("\n" + "="*70)
    print("ARMONIZACIÓN ESPACIAL COMPLETADA")
    print(f"Salida: {PROC_DIR}")
    print("="*70)


if __name__ == '__main__':
    # pandas importado aquí para no fallar si no está en el scope de armonizar_igac
    try:
        import pandas as pd
    except ImportError:
        pass
    main()
