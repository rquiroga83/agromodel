"""
01_armonizar_espacial.py
═══════════════════════════════════════════════════════════════
Armonización espacial de todas las fuentes de datos crudas.

Entrada : extractores/raw/  (múltiples CRS, resoluciones, formatos)
Salida  : processed/        (todas las capas en EPSG:3116, {RESOLUCION_M} m)

Operaciones por fuente:
  1. Estaciones IDEAM  → Kriging ordinario + corrección gradiente adiabático
  2. CHIRPS            → Reproyección + resampling bilineal desde ~5.3 km
  3. SoilGrids         → Bilineal (continuos) / nearest-neighbor (texturas)
  4. IGAC vectorial    → Rasterización de polígonos categóricos
  5. Sentinel-2        → Reproyección a resolución objetivo
  6. Sentinel-1        → Solo reproyección a resolución objetivo
  7. DEM + derivadas   → Derivadas a 30 m PRIMERO, luego resamplear a resolución objetivo

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
from config import BBOX_WGS84, DIRS, YEAR_START, YEAR_END, RESOLUCION_M, crear_directorios

# ══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN ESPACIAL DEL PROYECTO
# ══════════════════════════════════════════════════════════════════

CRS_PROYECTO    = 'EPSG:3116'   # MAGNA-SIRGAS Colombia Bogotá
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


def reproyectar_raster_nativo(src_path, dst_path, resampling_method='bilinear'):
    """
    Reproyecta un GeoTIFF a EPSG:3116 conservando la resolución nativa.
    No fuerza el grid del proyecto — calcula el transform óptimo
    para la resolución original del archivo.
    """
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.crs import CRS

    RESAMPLING = {
        'bilinear': Resampling.bilinear,
        'nearest':  Resampling.nearest,
        'cubic':    Resampling.cubic,
    }

    dst_crs = CRS.from_epsg(3116)

    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )

        profile = src.profile.copy()
        profile.update(
            crs=dst_crs,
            transform=transform,
            width=width,
            height=height,
            nodata=src.nodata or NODATA_RASTER,
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
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=RESAMPLING[resampling_method],
                )


# ══════════════════════════════════════════════════════════════════
# 1. ESTACIONES IDEAM — KRIGING + CORRECCIÓN ADIABÁTICA
# ══════════════════════════════════════════════════════════════════

def armonizar_ideam(variable=None):
    """
    Interpola estaciones IDEAM a ráster usando Kriging Ordinario.

    Variables: temperatura (con corrección adiabática), precipitación, humedad.
    Salida: un GeoTIFF por variable×semestre en processed/clima/ideam/
    Requiere: DEM armonizado para la corrección de temperatura por altitud.

    Args:
        variable: 'temperatura' | 'precipitacion' | 'humedad' | None (todas)
    """
    print("\n" + "="*70)
    titulo = f"1. ESTACIONES IDEAM → KRIGING{f' ({variable.upper()})' if variable else ''}"
    print(titulo)
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

    # ── Resolución de Kriging (intermedia) ────────────────────────
    # Con 30-60 estaciones sobre 24,000 km² el radio de influencia es
    # del orden de decenas de km. Hacer Kriging a resolución final crearía un grid
    # demasiado grande en RAM.
    # Solución: Kriging a 1 km (grid de ~480 × 550 = 264K píxeles)
    # luego resampling bilineal a resolución del proyecto.
    RESOLUCION_KRIGING_M = 1000

    dst_transform, dst_width, dst_height, dst_crs = get_grid_cundinamarca()
    transformer = Transformer.from_crs('EPSG:4326', CRS_PROYECTO, always_xy=True)

    # Grid de Kriging a 1 km
    from rasterio.transform import from_bounds as _from_bounds
    krig_west  = dst_transform.c
    krig_north = dst_transform.f
    krig_east  = krig_west  + dst_width  * RESOLUCION_M
    krig_south = krig_north - dst_height * RESOLUCION_M
    krig_width  = max(1, int((krig_east - krig_west)   / RESOLUCION_KRIGING_M))
    krig_height = max(1, int((krig_north - krig_south) / RESOLUCION_KRIGING_M))
    krig_transform = _from_bounds(krig_west, krig_south, krig_east, krig_north,
                                   krig_width, krig_height)

    xs_k = np.array([krig_transform.c + (i + 0.5) * RESOLUCION_KRIGING_M
                     for i in range(krig_width)])
    ys_k = np.array([krig_transform.f - (j + 0.5) * RESOLUCION_KRIGING_M
                     for j in range(krig_height)])

    print(f"  Grid Kriging: {krig_width}×{krig_height} px a {RESOLUCION_KRIGING_M} m "
          f"→ bilineal a {RESOLUCION_M} m")

    # ── Cargar DEM a resolución de Kriging (para corrección adiabática) ──
    dem_path = os.path.join(PROC_DIRS['dem'], f'dem_cundinamarca_{RESOLUCION_M}m.tif')
    dem_krig = None
    if os.path.exists(dem_path):
        from rasterio.warp import reproject as _reproject, Resampling as _Resampling
        with rasterio.open(dem_path) as src:
            dem_krig = np.empty((krig_height, krig_width), dtype=np.float32)
            _reproject(
                source=rasterio.band(src, 1),
                destination=dem_krig,
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=krig_transform, dst_crs=dst_crs,
                resampling=_Resampling.bilinear,
            )
            dem_krig[dem_krig == NODATA_RASTER] = np.nan
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

    if variable is not None and variable not in variables:
        print(f"  Variable '{variable}' no reconocida. Opciones: {list(variables)}")
        return

    items = [(variable, variables[variable])] if variable else list(variables.items())

    for var_name, cfg in items:
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

        # Procesar por mes
        periodos = [
            (year, mes)
            for year in range(YEAR_START, YEAR_END + 1)
            for mes in range(1, 13)
        ]

        for year, mes in periodos:
            label   = f"{year}_{mes:02d}"
            t_start = pd.Timestamp(year=year, month=mes, day=1)
            t_end   = t_start + pd.offsets.MonthEnd(0)

            out_file = os.path.join(PROC_DIRS['ideam'],
                                    f"{var_name}_{label}_kriging.tif")
            if os.path.exists(out_file):
                print(f"  [{var_name} {label}] Ya existe. Saltando.")
                continue

            # Filtrar mes y agregar por estación (mediana)
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
                # Varianza cero (o casi) → el optimizador de scipy no puede ajustar el variograma.
                # Ocurre en semestres secos donde la mayoría de estaciones reportan 0 mm.
                _coef_variacion = np.std(z_est) / (np.abs(np.mean(z_est)) + 1e-9)
                if np.std(z_est) < 1e-6 or _coef_variacion < 0.01:
                    valor_constante = float(np.median(z_est))
                    z_krig = np.full((krig_height, krig_width), valor_constante, dtype=np.float32)
                    print(f"varianza≈0, ráster constante ({valor_constante:.3f})...",
                          end=' ', flush=True)
                else:
                    # ── Paso 1: Kriging a 1 km (~264K píxeles, manejable en RAM) ──
                    try:
                        ok = OrdinaryKriging(
                            x_est, y_est, z_est,
                            variogram_model=cfg['variogram'],
                            verbose=False,
                            enable_plotting=False,
                        )
                        # ys_k invertido (N→S) para que el resultado sea top-down
                        z_krig, _ = ok.execute('grid', xs_k, ys_k[::-1])
                        z_krig = np.flipud(z_krig.data.astype(np.float32))
                    except Exception as e_krig:
                        if 'bound' in str(e_krig).lower() or 'variogram' in str(e_krig).lower():
                            # Fallback: variograma no ajustable → ráster constante
                            valor_constante = float(np.median(z_est))
                            z_krig = np.full((krig_height, krig_width),
                                            valor_constante, dtype=np.float32)
                            print(f"variograma no ajustable, constante ({valor_constante:.3f})...",
                                  end=' ', flush=True)
                        else:
                            raise

                # Corrección adiabática a resolución de Kriging con DEM 1 km
                if cfg['adiabático'] and dem_krig is not None:
                    alt_col = cfg['col_alt']
                    alt_vals = estaciones[alt_col].values if alt_col in estaciones.columns else np.array([0.0])
                    alt_ref  = float(np.nanmedian(alt_vals))
                    dem_valid = np.where(np.isnan(dem_krig), alt_ref, dem_krig)
                    z_krig = z_krig - 0.006 * (dem_valid - alt_ref)

                z_krig[np.isnan(z_krig)] = NODATA_RASTER

                # ── Paso 2: Resamplear de 1 km a resolución del proyecto ──
                from rasterio.warp import reproject as _reproject, Resampling as _Resampling

                profile_krig = dict(
                    driver='GTiff', dtype='float32', count=1,
                    crs=dst_crs, transform=krig_transform,
                    width=krig_width, height=krig_height,
                    nodata=NODATA_RASTER, compress='deflate',
                )
                profile_dst = dict(
                    driver='GTiff', dtype='float32', count=1,
                    crs=dst_crs, transform=dst_transform,
                    width=dst_width, height=dst_height,
                    nodata=NODATA_RASTER, compress='deflate',
                )

                os.makedirs(PROC_DIRS['ideam'], exist_ok=True)

                # Resamplear directamente en memoria de 1 km a resolución del proyecto
                z_dst = np.empty((dst_height, dst_width), dtype=np.float32)
                _reproject(
                    source=z_krig,
                    destination=z_dst,
                    src_transform=krig_transform, src_crs=dst_crs,
                    dst_transform=dst_transform,  dst_crs=dst_crs,
                    src_nodata=NODATA_RASTER, dst_nodata=NODATA_RASTER,
                    resampling=_Resampling.bilinear,
                )

                with rasterio.open(out_file, 'w', **profile_dst) as dst:
                    dst.write(z_dst, 1)
                print(f"guardado ({krig_width}x{krig_height} px Kriging -> {dst_width}x{dst_height} px {RESOLUCION_M}m).")
            except Exception as e:
                print(f"error: {e}")

    print("\n  IDEAM armonizado.")


# ══════════════════════════════════════════════════════════════════
# 2. CHIRPS — BILINEAL DESDE ~5.3 KM
# ══════════════════════════════════════════════════════════════════

def armonizar_chirps():
    """
    Reproyecta y remuestrea los GeoTIFF mensuales de CHIRPS (~5.3 km)
    al grid del proyecto con resampling bilineal.
    """
    print("\n" + "="*70)
    print(f"2. CHIRPS -> BILINEAL A {RESOLUCION_M} m")
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
    Reproyecta SoilGrids de 250 m a resolución del proyecto.
    - Propiedades continuas (ph, soc, bdod, cec, nitrogen, ocd): bilineal
    - Texturas (clay, sand, silt): nearest-neighbor + normalización a 100%
    """
    print("\n" + "="*70)
    print(f"3. SOILGRIDS -> {RESOLUCION_M} m")
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
    Rasteriza los GeoJSON del IGAC al grid del proyecto.
    - Propiedades (suelo): UCSuelo, subgrupo taxonómico, paisaje, clima, relieve, material parental
    - Vocación de Uso: código de vocación (categórico)

    Los nombres de campo se buscan de forma flexible (case-insensitive y por prefijo)
    para tolerar variaciones entre versiones del dataset IGAC.
    """
    print("\n" + "="*70)
    print(f"4. IGAC VECTORIAL -> RASTERIZACION A {RESOLUCION_M} m")
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

    # Campos por capa: clave = nombre canónico (case-insensitive), valor = (archivo_salida, dtype)
    # El script buscará cada campo de forma flexible antes de rasterizar.
    capas = [
        {
            'input': os.path.join(RAW_DIR, 'suelo', 'igac_quimica',
                                  'propiedades_quimicas_suelo.geojson'),
            'campos': {
                # Clasificación del suelo
                'UCSuelo':       ('igac_ucsuelo.tif',          'int16'),
                'SUBGRUPO':      ('igac_subgrupo.tif',         'int16'),
                'PAISAJE':       ('igac_paisaje.tif',          'int16'),
                'CLIMA_1':       ('igac_clima.tif',            'int16'),
                'TIPO_RELIE':    ('igac_relieve.tif',          'int16'),
                'MATERIAL_P':    ('igac_material.tif',         'int16'),
                # Propiedades químicas (valores en rangos de texto → int16 con tabla de códigos)
                'pH':            ('igac_ph.tif',               'int16'),
                'P':             ('igac_fosforo.tif',          'int16'),
                'K':             ('igac_potasio.tif',          'int16'),
                'F_SAL':         ('igac_fertilidad.tif',       'int16'),
                '_SB':           ('igac_suma_bases.tif',       'int16'),
                'Calificacion_1':('igac_calificacion.tif',     'int16'),
            },
        },
        {
            'input': os.path.join(RAW_DIR, 'suelo', 'igac_vocacion',
                                  'vocacion_uso_suelo.geojson'),
            'campos': {
                # El script busca 'VOCACION' exacto y también por prefijo (ej. VOCACION_USO)
                'VOCACION':      ('igac_vocacion.tif',         'int16'),
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

        cols_upper = {c.upper(): c for c in gdf.columns}

        for campo, (out_nombre, dtype) in capa['campos'].items():
            out_path = os.path.join(PROC_DIRS['igac'], out_nombre)
            if os.path.exists(out_path):
                print(f"  Ya existe: {out_nombre}")
                continue

            # Búsqueda flexible: exacta (case-insensitive) → por prefijo → ausente
            col = cols_upper.get(campo.upper())
            if col is None:
                # Intentar por prefijo (ej. 'VOCACION' encuentra 'VOCACION_USO')
                col = next((c for cu, c in cols_upper.items()
                            if cu.startswith(campo.upper())), None)
            if col is None:
                # Campo no existe en este dataset — omitir silenciosamente
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
# 5. SENTINEL-2 — REPROYECCIÓN CRS (resolución nativa)
# ══════════════════════════════════════════════════════════════════

def _limpiar_indices_extremos(path):
    """
    Limpia valores extremos de índices espectrales en GeoTIFFs reproyectados.
    EVI y NDWI válido: [-1, 1]. Valores fuera de rango → NoData.

    El overflow ocurre cuando el evalscript calcula índices sobre píxeles donde
    el denominador ≈ 0, produciendo divisiones cercanas a cero.
    """
    import rasterio

    nombre = os.path.basename(path).lower()

    # Solo procesar archivos de EVI o NDWI (banda individual)
    es_evi = '_evi_' in nombre
    es_ndwi = '_ndwi_' in nombre
    if not (es_evi or es_ndwi):
        return 0, ''

    tag = 'EVI' if es_evi else 'NDWI'

    with rasterio.open(path, 'r+') as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata if src.nodata else NODATA_RASTER
        mascara_valido = data != nodata
        mascara_overflow = mascara_valido & ((data < -1.0) | (data > 1.0))
        n_overflow = int(np.count_nonzero(mascara_overflow))
        if n_overflow > 0:
            data[mascara_overflow] = nodata
            src.write(data, 1)
    return n_overflow, tag


def armonizar_sentinel2():
    """
    Reproyecta GeoTIFF de Sentinel-2 de WGS84 a EPSG:3116.
    Conserva la resolución nativa — no fuerza al grid del proyecto.

    Post-procesamiento:
      - EVI: los valores fuera del rango [-1, 1] se reemplazan con NoData
        (previene overflow del evalscript original).
    """
    import rasterio

    print("\n" + "="*70)
    print("5. SENTINEL-2 -> REPROYECCION CRS A EPSG:3116 (resolucion nativa)")
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
            print(f"  Ya existe: {nombre}", end='')
        else:
            print(f"  {nombre}...", end=' ', flush=True)
            try:
                reproyectar_raster_nativo(src_path, dst_path, resampling_method='bilinear')
                print("OK", end='')
            except Exception as e:
                print(f"Error: {e}")
                continue

        # Limpiar EVI/NDWI con valores extremos (overflow del evalscript)
        try:
            n_overflow, tag = _limpiar_indices_extremos(dst_path)
            if n_overflow > 0:
                print(f" | {tag} limpiado: {n_overflow:,} valores fuera de [-1,1] → NoData")
            else:
                print()  # salto de línea
        except Exception as e:
            print(f" | limpieza error: {e}")

    print("  Sentinel-2 armonizado.")


# ══════════════════════════════════════════════════════════════════
# 6. SENTINEL-1 — REPROYECCIÓN CRS (resolución nativa)
# ══════════════════════════════════════════════════════════════════

def armonizar_sentinel1():
    """
    Reproyecta Sentinel-1 GRD de WGS84 a EPSG:3116.
    Conserva la resolución nativa — solo cambio de CRS.
    """
    print("\n" + "="*70)
    print("6. SENTINEL-1 -> REPROYECCION CRS A EPSG:3116 (resolucion nativa)")
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
            reproyectar_raster_nativo(src_path, dst_path, resampling_method='bilinear')
            print("OK")
        except Exception as e:
            print(f"Error: {e}")

    print("  Sentinel-1 armonizado.")


# ══════════════════════════════════════════════════════════════════
# 7. DEM + DERIVADAS TOPOGRÁFICAS
# ══════════════════════════════════════════════════════════════════

def armonizar_dem():
    """
    Reproyecta el DEM Copernicus GLO-30 (30 m) a resolución del proyecto.

    Estrategia: calcular derivadas (pendiente, aspecto, curvatura, TWI)
    a la resolución ORIGINAL de 30 m PRIMERO, luego resamplear.
    Esto evita artefactos de interpolación en derivadas de segundo orden.
    """
    print("\n" + "="*70)
    print(f"7. DEM COPERNICUS -> DERIVADAS A 30 m + RESAMPLING A {RESOLUCION_M} m")
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
        out_path = os.path.join(PROC_DIRS['dem'], f'dem_{nombre}_{RESOLUCION_M}m.tif')
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
    elev_src = os.path.join(PROC_DIRS['dem'], f'dem_elevacion_{RESOLUCION_M}m.tif')
    elev_dst = os.path.join(PROC_DIRS['dem'], f'dem_cundinamarca_{RESOLUCION_M}m.tif')
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
        description=f'Armonizacion espacial de datos crudos -> processed/ (EPSG:3116, {RESOLUCION_M} m)'
    )
    parser.add_argument(
        '--step',
        choices=['ideam', 'chirps', 'soilgrids', 'igac',
                 'sentinel2', 'sentinel1', 'dem', 'validar'],
        default=None,
        help='Paso a ejecutar. Sin --step ejecuta todos.'
    )
    parser.add_argument(
        '--variable',
        choices=['temperatura', 'precipitacion', 'humedad'],
        default=None,
        help='(Solo con --step ideam) Variable a procesar. Sin --variable procesa las tres.'
    )
    args = parser.parse_args()

    if args.variable and args.step != 'ideam':
        parser.error('--variable solo es válido con --step ideam')

    crear_dirs_procesamiento()

    pasos = {
        'ideam':     lambda: armonizar_ideam(variable=args.variable),
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
