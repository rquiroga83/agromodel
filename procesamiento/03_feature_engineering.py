"""
03_feature_engineering.py
═══════════════════════════════════════════════════════════════
Calcula variables derivadas a partir de capas armonizadas.

Entrada : processed/ y processed/temporal/
Salida  : processed/engineered/

Features derivados:
  1. piso_termico       — Clasificación altitudinal colombiana (0-3)
  2. amplitud_termica   — Rango de temperatura (max - min) por semestre
  3. indice_fertilidad  — Índice compuesto de fertilidad del suelo
  4. anomalia_precip    — Desviación estandarizada de precipitación vs normales
  5. ndvi_max_semestre  — Máximo NDVI mensual dentro del semestre
  6. ndvi_integral      — Integral de NDVI (proxy de productividad primaria)
  7. indice_aridez      — Relación precipitación / evapotranspiración potencial

Nota: temp_ajustada_altitud ya se calcula en 01_armonizar_espacial.py
(corrección adiabática en el Kriging de temperatura).

Uso:
    python 03_feature_engineering.py               # Calcula todos
    python 03_feature_engineering.py --step piso    # Solo piso térmico
    python 03_feature_engineering.py --step amplitud
    python 03_feature_engineering.py --step fertilidad
    python 03_feature_engineering.py --step anomalia
    python 03_feature_engineering.py --step ndvi
    python 03_feature_engineering.py --step aridez

pip install rasterio numpy pandas
"""

import argparse
import os
import sys
import glob
import warnings

import numpy as np

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extractores'))
from config import YEAR_START, YEAR_END, SEMESTRES, RESOLUCION_M

# ══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, 'processed')
TEMP_DIR = os.path.join(PROC_DIR, 'temporal')
ENG_DIR  = os.path.join(PROC_DIR, 'engineered')
NODATA   = -9999.0


def _leer_banda(path, banda=1):
    """Lee un GeoTIFF y retorna (array_float32, profile). NoData → NaN."""
    import rasterio
    with rasterio.open(path) as src:
        arr = src.read(banda).astype(np.float32)
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        arr[arr == NODATA] = np.nan
        return arr, src.profile.copy()


def _escribir(path, data, profile, dtype='float32'):
    """Escribe array 2D como GeoTIFF."""
    import rasterio
    out = np.where(np.isnan(data), NODATA, data).astype(dtype)
    nodata_val = NODATA if dtype == 'float32' else 0
    profile.update(dtype=dtype, count=1, nodata=nodata_val,
                   compress='deflate', driver='GTiff')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(path, 'w', **profile) as dst:
        dst.write(out, 1)


def meses_de_semestre(label):
    year = int(label[:4])
    if label.endswith('A'):
        return [f'{year}_{m:02d}' for m in range(1, 7)]
    else:
        return [f'{year}_{m:02d}' for m in range(7, 13)]


# ══════════════════════════════════════════════════════════════════
# 1. PISO TÉRMICO — Clasificación altitudinal colombiana
# ══════════════════════════════════════════════════════════════════

def calcular_piso_termico():
    """
    Clasifica cada píxel por piso térmico según elevación:
      0 = Cálido     (< 1000 m)
      1 = Templado    (1000–2000 m)
      2 = Frío        (2000–3000 m)
      3 = Páramo      (> 3000 m)
    """
    print("\n" + "="*70)
    print("1. PISO TÉRMICO")
    print("="*70)

    dem_path = os.path.join(PROC_DIR, 'topo', f'dem_elevacion_{RESOLUCION_M}m.tif')
    out_path = os.path.join(ENG_DIR, 'piso_termico.tif')

    if os.path.exists(out_path):
        print("  Ya existe. Saltando.")
        return

    if not os.path.exists(dem_path):
        print(f"  DEM no encontrado: {dem_path}")
        return

    elev, profile = _leer_banda(dem_path)

    piso = np.full_like(elev, np.nan)
    piso[elev < 1000]                        = 0
    piso[(elev >= 1000) & (elev < 2000)]     = 1
    piso[(elev >= 2000) & (elev < 3000)]     = 2
    piso[elev >= 3000]                        = 3

    _escribir(out_path, piso, profile, dtype='int8')
    print("  OK → piso_termico.tif")


# ══════════════════════════════════════════════════════════════════
# 2. AMPLITUD TÉRMICA — Por semestre
# ══════════════════════════════════════════════════════════════════

def calcular_amplitud_termica():
    """amplitud = temp_max_semestral - temp_min_semestral"""
    print("\n" + "="*70)
    print("2. AMPLITUD TÉRMICA")
    print("="*70)

    for sem in SEMESTRES:
        label = sem['label']
        out_path = os.path.join(ENG_DIR, f'amplitud_termica_{label}.tif')
        if os.path.exists(out_path):
            continue

        max_path = os.path.join(TEMP_DIR, 'clima', 'ideam', f'temperatura_max_{label}.tif')
        min_path = os.path.join(TEMP_DIR, 'clima', 'ideam', f'temperatura_min_{label}.tif')

        if not os.path.exists(max_path) or not os.path.exists(min_path):
            print(f"  [{label}] Faltan rásteres de temp max/min. Saltando.")
            continue

        t_max, profile = _leer_banda(max_path)
        t_min, _ = _leer_banda(min_path)

        amplitud = t_max - t_min
        _escribir(out_path, amplitud, profile)
        print(f"  [{label}] OK")

    print("  Amplitud térmica calculada.")


# ══════════════════════════════════════════════════════════════════
# 3. ÍNDICE DE FERTILIDAD — Compuesto ponderado
# ══════════════════════════════════════════════════════════════════

def calcular_indice_fertilidad():
    """
    Índice compuesto de fertilidad usando SoilGrids y/o IGAC.
    Usa nitrogen, phh2o, cec, soc de SoilGrids (0-5 cm) normalizados 0-1.
    fertilidad = 0.25*N_norm + 0.25*pH_opt + 0.25*CEC_norm + 0.25*SOC_norm
    donde pH_opt = 1 - abs(pH - 6.5) / 3.5 (óptimo en pH 6.5)
    """
    print("\n" + "="*70)
    print("3. ÍNDICE DE FERTILIDAD")
    print("="*70)

    out_path = os.path.join(ENG_DIR, 'indice_fertilidad.tif')
    if os.path.exists(out_path):
        print("  Ya existe. Saltando.")
        return

    sg_dir = os.path.join(PROC_DIR, 'suelo', 'soilgrids')

    paths = {
        'nitrogen': os.path.join(sg_dir, 'soilgrids_nitrogen_0_5cm.tif'),
        'phh2o':    os.path.join(sg_dir, 'soilgrids_phh2o_0_5cm.tif'),
        'cec':      os.path.join(sg_dir, 'soilgrids_cec_0_5cm.tif'),
        'soc':      os.path.join(sg_dir, 'soilgrids_soc_0_5cm.tif'),
    }

    for name, p in paths.items():
        if not os.path.exists(p):
            print(f"  Falta {name}: {p}. Saltando índice de fertilidad.")
            return

    nitrogen, profile = _leer_banda(paths['nitrogen'])
    phh2o, _ = _leer_banda(paths['phh2o'])
    cec, _   = _leer_banda(paths['cec'])
    soc, _   = _leer_banda(paths['soc'])

    # SoilGrids nitrogen: cg/kg; phh2o: pH×10; cec: mmol(c)/kg; soc: dg/kg
    phh2o = phh2o / 10.0  # convertir a pH real

    # Normalizar cada componente a [0, 1]
    def _norm(arr):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            vmin = np.nanpercentile(arr, 2)
            vmax = np.nanpercentile(arr, 98)
            if vmax <= vmin:
                return np.zeros_like(arr)
            return np.clip((arr - vmin) / (vmax - vmin), 0, 1)

    n_norm   = _norm(nitrogen)
    cec_norm = _norm(cec)
    soc_norm = _norm(soc)

    # pH óptimo: 6.5; penalización proporcional a la distancia
    ph_opt = 1.0 - np.clip(np.abs(phh2o - 6.5) / 3.5, 0, 1)

    fertilidad = 0.25 * n_norm + 0.25 * ph_opt + 0.25 * cec_norm + 0.25 * soc_norm

    _escribir(out_path, fertilidad, profile)
    print("  OK → indice_fertilidad.tif")


# ══════════════════════════════════════════════════════════════════
# 4. ANOMALÍA DE PRECIPITACIÓN — Desviación estandarizada
# ══════════════════════════════════════════════════════════════════

def calcular_anomalia_precip():
    """
    anomalia = (precip_semestre - normal_semestre) / std_semestre
    Normal calculada como la media de todos los semestres disponibles.
    """
    print("\n" + "="*70)
    print("4. ANOMALÍA DE PRECIPITACIÓN")
    print("="*70)

    # Calcular la "normal" de precipitación a partir de los datos CHIRPS disponibles
    chirps_acum_dir = os.path.join(TEMP_DIR, 'clima', 'chirps')

    # Agrupar por tipo de semestre (A o B)
    for sem_tipo in ['A', 'B']:
        sems = [s for s in SEMESTRES if s['label'].endswith(sem_tipo)]
        arrays = []
        profile = None

        for sem in sems:
            path = os.path.join(chirps_acum_dir, f"chirps_acum_{sem['label']}.tif")
            if os.path.exists(path):
                arr, prof = _leer_banda(path)
                arrays.append(arr)
                if profile is None:
                    profile = prof

        if len(arrays) < 2:
            print(f"  [Semestres {sem_tipo}] Insuficientes datos ({len(arrays)}). Saltando.")
            continue

        stack = np.stack(arrays, axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            normal = np.nanmean(stack, axis=0)
            std = np.nanstd(stack, axis=0)
            std[std < 1.0] = 1.0  # evitar división por cero

        # Calcular anomalía para cada semestre
        for i, sem in enumerate(sems):
            out_path = os.path.join(ENG_DIR, f"anomalia_precip_{sem['label']}.tif")
            if os.path.exists(out_path):
                continue

            path = os.path.join(chirps_acum_dir, f"chirps_acum_{sem['label']}.tif")
            if not os.path.exists(path):
                continue

            arr, _ = _leer_banda(path)
            anomalia = (arr - normal) / std

            _escribir(out_path, anomalia, profile)
            print(f"  [anomalia {sem['label']}] OK")

    print("  Anomalía de precipitación calculada.")


# ══════════════════════════════════════════════════════════════════
# 5. NDVI MAX + INTEGRAL POR SEMESTRE
# ══════════════════════════════════════════════════════════════════

def calcular_ndvi_features():
    """
    ndvi_max_semestre = max(NDVI mensual en el semestre)
    ndvi_integral = sum(NDVI_mensual × 30)  (proxy de productividad primaria neta)
    """
    import rasterio
    print("\n" + "="*70)
    print("5. NDVI MAX + INTEGRAL")
    print("="*70)

    s2_dir = os.path.join(PROC_DIR, 'satelite', 'sentinel2')
    # NDVI es la banda 1 en los archivos s2_indices_YYYY_MM.tif

    for sem in SEMESTRES:
        label = sem['label']
        out_max  = os.path.join(ENG_DIR, f'ndvi_max_{label}.tif')
        out_int  = os.path.join(ENG_DIR, f'ndvi_integral_{label}.tif')

        if os.path.exists(out_max) and os.path.exists(out_int):
            continue

        meses = meses_de_semestre(label)
        ndvi_stack = []
        profile = None

        for mes in meses:
            path = os.path.join(s2_dir, f"s2_indices_{mes}.tif")
            if not os.path.exists(path):
                continue
            with rasterio.open(path) as src:
                if profile is None:
                    profile = src.profile.copy()
                ndvi = src.read(1).astype(np.float32)  # Banda 1 = NDVI
                ndvi[ndvi == 0] = np.nan  # 0 = sin datos (nubes)
                ndvi_stack.append(ndvi)

        if len(ndvi_stack) < 2 or profile is None:
            print(f"  [NDVI {label}] Insuficientes meses ({len(ndvi_stack)}). Saltando.")
            continue

        stack = np.stack(ndvi_stack, axis=0)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Máximo NDVI del semestre
            if not os.path.exists(out_max):
                ndvi_max = np.nanmax(stack, axis=0)
                _escribir(out_max, ndvi_max, profile)

            # Integral NDVI (suma × 30 días por mes)
            if not os.path.exists(out_int):
                ndvi_sum = np.nansum(stack, axis=0) * 30.0
                _escribir(out_int, ndvi_sum, profile)

        print(f"  [NDVI {label}] OK ({len(ndvi_stack)} meses)")

    print("  NDVI max + integral calculados.")


# ══════════════════════════════════════════════════════════════════
# 6. ÍNDICE DE ARIDEZ
# ══════════════════════════════════════════════════════════════════

def calcular_indice_aridez():
    """
    indice_aridez = precip_anual / ETP
    Sin datos de evapotranspiración, se usa la estimación de Hargreaves:
      ETP_mes ≈ 0.0023 × (temp_media + 17.8) × (temp_max - temp_min)^0.5 × Ra
    donde Ra ≈ 15 MJ/m²/día (radiación extraterrestre media para trópico ~5°N).

    Simplificación: ETP semestral estimada desde temp media, max, min semestrales.
    """
    print("\n" + "="*70)
    print("6. ÍNDICE DE ARIDEZ")
    print("="*70)

    RA_TROPICO = 15.0   # MJ/m²/día aprox para latitud 5°N
    DIAS_SEMESTRE = 182  # aprox

    for sem in SEMESTRES:
        label = sem['label']
        out_path = os.path.join(ENG_DIR, f'indice_aridez_{label}.tif')
        if os.path.exists(out_path):
            continue

        # Precipitación acumulada del semestre
        precip_path = os.path.join(TEMP_DIR, 'clima', 'chirps', f'chirps_acum_{label}.tif')
        tmedia_path = os.path.join(TEMP_DIR, 'clima', 'ideam', f'temperatura_media_{label}.tif')
        tmax_path   = os.path.join(TEMP_DIR, 'clima', 'ideam', f'temperatura_max_{label}.tif')
        tmin_path   = os.path.join(TEMP_DIR, 'clima', 'ideam', f'temperatura_min_{label}.tif')

        if not all(os.path.exists(p) for p in [precip_path, tmedia_path, tmax_path, tmin_path]):
            print(f"  [{label}] Faltan rásteres. Saltando.")
            continue

        precip, profile = _leer_banda(precip_path)
        tmedia, _ = _leer_banda(tmedia_path)
        tmax, _   = _leer_banda(tmax_path)
        tmin, _   = _leer_banda(tmin_path)

        # Hargreaves ETP (mm/semestre)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            delta_t = np.clip(tmax - tmin, 0, None)
            etp = 0.0023 * (tmedia + 17.8) * np.sqrt(delta_t) * RA_TROPICO * DIAS_SEMESTRE

            # Evitar división por cero
            etp[etp < 1.0] = 1.0
            aridez = precip / etp

        _escribir(out_path, aridez, profile)
        print(f"  [{label}] OK")

    print("  Índice de aridez calculado.")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Feature engineering: variables derivadas en processed/engineered/'
    )
    parser.add_argument(
        '--step',
        choices=['piso', 'amplitud', 'fertilidad', 'anomalia', 'ndvi', 'aridez'],
        default=None,
        help='Feature a calcular. Sin --step calcula todos.'
    )
    args = parser.parse_args()

    os.makedirs(ENG_DIR, exist_ok=True)

    pasos = {
        'piso':       calcular_piso_termico,
        'amplitud':   calcular_amplitud_termica,
        'fertilidad': calcular_indice_fertilidad,
        'anomalia':   calcular_anomalia_precip,
        'ndvi':       calcular_ndvi_features,
        'aridez':     calcular_indice_aridez,
    }

    if args.step:
        pasos[args.step]()
    else:
        for fn in pasos.values():
            fn()

    print("\n" + "="*70)
    print("FEATURE ENGINEERING COMPLETADO")
    print(f"Salida: {ENG_DIR}")
    print("="*70)


if __name__ == '__main__':
    main()
