"""
02_armonizar_temporal.py
═══════════════════════════════════════════════════════════════
Agregación temporal de capas mensuales → estadísticos semestrales.

Entrada : processed/ (rásteres mensuales en EPSG:3116)
Salida  : processed/temporal/ (estadísticos semestrales alineados con EVA)

Operaciones:
  1. IDEAM temperatura → media, máxima, mínima por semestre
  2. IDEAM precipitación → acumulado semestral
  3. IDEAM humedad → media semestral
  4. CHIRPS → acumulado semestral
  5. Sentinel-2 → media, máxima, desviación por índice por semestre
  6. Sentinel-1 → media semestral por banda

Los rásteres mensuales individuales se conservan en processed/ (necesarios
para features temporales del LSTM). Este script genera los agregados
semestrales que alimentan la vista minable y el feature engineering.

Uso:
    python 02_armonizar_temporal.py                   # Agrega todo
    python 02_armonizar_temporal.py --step ideam       # Solo clima IDEAM
    python 02_armonizar_temporal.py --step chirps      # Solo CHIRPS
    python 02_armonizar_temporal.py --step sentinel2   # Solo Sentinel-2
    python 02_armonizar_temporal.py --step sentinel1   # Solo Sentinel-1

pip install rasterio numpy
"""

import argparse
import os
import sys
import glob

import numpy as np

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extractores'))
from config import YEAR_START, YEAR_END, SEMESTRES

# ══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR  = os.path.join(BASE_DIR, 'processed')
TEMP_DIR  = os.path.join(PROC_DIR, 'temporal')
NODATA    = -9999.0

# Mapeo: semestre → lista de meses (YYYY_MM)
def meses_de_semestre(label):
    """Dado '2020A' retorna ['2020_01', ..., '2020_06']. Dado '2020B' retorna ['2020_07', ..., '2020_12']."""
    year = int(label[:4])
    if label.endswith('A'):
        return [f'{year}_{m:02d}' for m in range(1, 7)]
    else:
        return [f'{year}_{m:02d}' for m in range(7, 13)]


def crear_dirs_temporal():
    subdirs = [
        os.path.join(TEMP_DIR, 'clima', 'ideam'),
        os.path.join(TEMP_DIR, 'clima', 'chirps'),
        os.path.join(TEMP_DIR, 'satelite', 'sentinel2'),
        os.path.join(TEMP_DIR, 'satelite', 'sentinel1'),
    ]
    for d in subdirs:
        os.makedirs(d, exist_ok=True)
    print(f"Directorios temporales creados en: {TEMP_DIR}")


def _leer_rasters_mensuales(patron_base, meses, variable_desc=""):
    """
    Lee una lista de rásteres mensuales y retorna un stack 3D (meses, H, W).
    Descarta meses sin archivo. Retorna (stack, profile, meses_ok).
    """
    import rasterio

    arrays = []
    profile = None
    meses_ok = []

    for mes in meses:
        path = patron_base.format(mes=mes)
        if not os.path.exists(path):
            continue
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.float32)
            arr[arr == NODATA] = np.nan
            if src.nodata is not None and src.nodata != NODATA:
                arr[arr == src.nodata] = np.nan
            arrays.append(arr)
            if profile is None:
                profile = src.profile.copy()
            meses_ok.append(mes)

    if not arrays:
        return None, None, []

    stack = np.stack(arrays, axis=0)  # (N_meses, H, W)
    return stack, profile, meses_ok


def _escribir_raster(path, data, profile):
    """Escribe un array 2D como GeoTIFF con NoData=-9999."""
    import rasterio

    out = np.where(np.isnan(data), NODATA, data).astype(np.float32)
    profile.update(
        dtype='float32', count=1, nodata=NODATA,
        compress='deflate', driver='GTiff',
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(path, 'w', **profile) as dst:
        dst.write(out, 1)


# ══════════════════════════════════════════════════════════════════
# 1. IDEAM — MEDIA/MAX/MIN/ACUM POR SEMESTRE
# ══════════════════════════════════════════════════════════════════

def agregar_ideam():
    """
    Agrega rásteres mensuales de IDEAM por semestre:
      - temperatura: media, máxima media, mínima media
      - precipitación: acumulado (suma)
      - humedad: media
    """
    import warnings
    print("\n" + "="*70)
    print("1. IDEAM → AGREGACIÓN SEMESTRAL")
    print("="*70)

    ideam_dir = os.path.join(PROC_DIR, 'clima', 'ideam')
    out_dir   = os.path.join(TEMP_DIR, 'clima', 'ideam')

    variables = {
        'temperatura': {
            'patron': os.path.join(ideam_dir, 'temperatura_{mes}_kriging.tif'),
            'agregaciones': {
                'media': lambda s: np.nanmean(s, axis=0),
                'max':   lambda s: np.nanmax(s, axis=0),
                'min':   lambda s: np.nanmin(s, axis=0),
            },
        },
        'precipitacion': {
            'patron': os.path.join(ideam_dir, 'precipitacion_{mes}_kriging.tif'),
            'agregaciones': {
                'acum': lambda s: np.nansum(s, axis=0),
            },
        },
        'humedad': {
            'patron': os.path.join(ideam_dir, 'humedad_{mes}_kriging.tif'),
            'agregaciones': {
                'media': lambda s: np.nanmean(s, axis=0),
            },
        },
    }

    for sem in SEMESTRES:
        label = sem['label']
        meses = meses_de_semestre(label)

        for var_name, cfg in variables.items():
            for agg_name, agg_func in cfg['agregaciones'].items():
                out_file = os.path.join(out_dir, f"{var_name}_{agg_name}_{label}.tif")
                if os.path.exists(out_file):
                    continue

                stack, profile, meses_ok = _leer_rasters_mensuales(
                    cfg['patron'], meses, f"{var_name} {label}")

                if stack is None or len(meses_ok) < 3:
                    print(f"  [{var_name} {agg_name} {label}] "
                          f"Insuficientes meses ({len(meses_ok) if stack is not None else 0}/6). Saltando.")
                    continue

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = agg_func(stack)

                _escribir_raster(out_file, result, profile)
                print(f"  [{var_name} {agg_name} {label}] OK ({len(meses_ok)}/6 meses)")

    print("  IDEAM agregado.")


# ══════════════════════════════════════════════════════════════════
# 2. CHIRPS — ACUMULADO SEMESTRAL
# ══════════════════════════════════════════════════════════════════

def agregar_chirps():
    """Agrega precipitación CHIRPS mensual → acumulado semestral."""
    import warnings
    print("\n" + "="*70)
    print("2. CHIRPS → ACUMULADO SEMESTRAL")
    print("="*70)

    chirps_dir = os.path.join(PROC_DIR, 'clima', 'chirps')
    out_dir    = os.path.join(TEMP_DIR, 'clima', 'chirps')
    patron     = os.path.join(chirps_dir, 'chirps_{mes}.tif')

    for sem in SEMESTRES:
        label = sem['label']
        out_file = os.path.join(out_dir, f"chirps_acum_{label}.tif")
        if os.path.exists(out_file):
            continue

        meses = meses_de_semestre(label)
        stack, profile, meses_ok = _leer_rasters_mensuales(patron, meses)

        if stack is None or len(meses_ok) < 3:
            print(f"  [CHIRPS {label}] Insuficientes meses ({len(meses_ok) if stack is not None else 0}/6). Saltando.")
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = np.nansum(stack, axis=0)

        _escribir_raster(out_file, result, profile)
        print(f"  [CHIRPS acum {label}] OK ({len(meses_ok)}/6 meses)")

    print("  CHIRPS agregado.")


# ══════════════════════════════════════════════════════════════════
# 3. SENTINEL-2 — ESTADÍSTICOS SEMESTRALES POR ÍNDICE
# ══════════════════════════════════════════════════════════════════

def agregar_sentinel2():
    """
    Agrega Sentinel-2 mensual → estadísticos semestrales por banda/índice.
    Cada archivo mensual es multibanda (7 índices: NDVI, GNDVI, EVI, NDWI, MSAVI, BSI, SAVI).
    Genera: media, max, std por índice por semestre.
    """
    import rasterio
    import warnings
    print("\n" + "="*70)
    print("3. SENTINEL-2 → ESTADÍSTICOS SEMESTRALES")
    print("="*70)

    s2_dir  = os.path.join(PROC_DIR, 'satelite', 'sentinel2')
    out_dir = os.path.join(TEMP_DIR, 'satelite', 'sentinel2')

    BAND_NAMES = ['NDVI', 'GNDVI', 'EVI', 'NDWI', 'MSAVI', 'BSI', 'SAVI']
    AGGS = {
        'media': lambda s: np.nanmean(s, axis=0),
        'max':   lambda s: np.nanmax(s, axis=0),
        'std':   lambda s: np.nanstd(s, axis=0),
    }

    for sem in SEMESTRES:
        label = sem['label']
        meses = meses_de_semestre(label)

        # Buscar archivos mensuales del semestre
        archivos = []
        for mes in meses:
            path = os.path.join(s2_dir, f"s2_indices_{mes}.tif")
            if os.path.exists(path):
                archivos.append(path)

        if len(archivos) < 2:
            print(f"  [S2 {label}] Solo {len(archivos)} meses disponibles. Saltando.")
            continue

        # Verificar si ya todos los outputs existen
        todos_existen = all(
            os.path.exists(os.path.join(out_dir, f"s2_{bn.lower()}_{agg}_{label}.tif"))
            for bn in BAND_NAMES for agg in AGGS
        )
        if todos_existen:
            continue

        # Leer y apilar por banda
        profile = None
        for b_idx, band_name in enumerate(BAND_NAMES):
            # Stack de esta banda a través de los meses
            band_stack = []
            for fpath in archivos:
                with rasterio.open(fpath) as src:
                    if profile is None:
                        profile = src.profile.copy()
                    if b_idx + 1 <= src.count:
                        arr = src.read(b_idx + 1).astype(np.float32)
                        # Tratar 0 como NoData (evalscript devuelve 0 donde no hay datos)
                        arr[arr == 0] = np.nan
                        band_stack.append(arr)

            if len(band_stack) < 2:
                continue

            stack = np.stack(band_stack, axis=0)

            for agg_name, agg_func in AGGS.items():
                out_file = os.path.join(out_dir, f"s2_{band_name.lower()}_{agg_name}_{label}.tif")
                if os.path.exists(out_file):
                    continue

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = agg_func(stack)

                _escribir_raster(out_file, result, profile)

            print(f"  [S2 {band_name} {label}] OK ({len(band_stack)} meses)")

    print("  Sentinel-2 agregado.")


# ══════════════════════════════════════════════════════════════════
# 4. SENTINEL-1 — MEDIA SEMESTRAL
# ══════════════════════════════════════════════════════════════════

def agregar_sentinel1():
    """
    Agrega Sentinel-1 mensual → media semestral por banda.
    Cada archivo mensual tiene 3 bandas: VV_dB, VH_dB, VH_VV_ratio_dB.
    """
    import rasterio
    import warnings
    print("\n" + "="*70)
    print("4. SENTINEL-1 → MEDIA SEMESTRAL")
    print("="*70)

    s1_dir  = os.path.join(PROC_DIR, 'satelite', 'sentinel1')
    out_dir = os.path.join(TEMP_DIR, 'satelite', 'sentinel1')

    BAND_NAMES = ['vv', 'vh', 'vh_vv_ratio']

    for sem in SEMESTRES:
        label = sem['label']
        meses = meses_de_semestre(label)

        archivos = []
        for mes in meses:
            path = os.path.join(s1_dir, f"s1_backscatter_{mes}.tif")
            if os.path.exists(path):
                archivos.append(path)

        if len(archivos) < 2:
            print(f"  [S1 {label}] Solo {len(archivos)} meses disponibles. Saltando.")
            continue

        # Verificar si ya todos los outputs existen
        todos_existen = all(
            os.path.exists(os.path.join(out_dir, f"s1_{bn}_media_{label}.tif"))
            for bn in BAND_NAMES
        )
        if todos_existen:
            continue

        profile = None
        for b_idx, band_name in enumerate(BAND_NAMES):
            out_file = os.path.join(out_dir, f"s1_{band_name}_media_{label}.tif")
            if os.path.exists(out_file):
                continue

            band_stack = []
            for fpath in archivos:
                with rasterio.open(fpath) as src:
                    if profile is None:
                        profile = src.profile.copy()
                    if b_idx + 1 <= src.count:
                        arr = src.read(b_idx + 1).astype(np.float32)
                        arr[arr == 0] = np.nan
                        band_stack.append(arr)

            if len(band_stack) < 2:
                continue

            stack = np.stack(band_stack, axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = np.nanmean(stack, axis=0)

            _escribir_raster(out_file, result, profile)
            print(f"  [S1 {band_name} {label}] OK ({len(band_stack)} meses)")

    print("  Sentinel-1 agregado.")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Agregación temporal: mensuales → estadísticos semestrales'
    )
    parser.add_argument(
        '--step',
        choices=['ideam', 'chirps', 'sentinel2', 'sentinel1'],
        default=None,
        help='Paso a ejecutar. Sin --step ejecuta todos.'
    )
    args = parser.parse_args()

    crear_dirs_temporal()

    pasos = {
        'ideam':     agregar_ideam,
        'chirps':    agregar_chirps,
        'sentinel2': agregar_sentinel2,
        'sentinel1': agregar_sentinel1,
    }

    if args.step:
        pasos[args.step]()
    else:
        for nombre in ['ideam', 'chirps', 'sentinel2', 'sentinel1']:
            pasos[nombre]()

    print("\n" + "="*70)
    print("AGREGACIÓN TEMPORAL COMPLETADA")
    print(f"Salida: {TEMP_DIR}")
    print("="*70)


if __name__ == '__main__':
    main()
