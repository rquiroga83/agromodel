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

Features de limpieza (pre-procesamiento):
  8. aspecto_circular  — Descomposición sin/cos del aspecto (fix valor -1)
  9. limpiar_soilgrids — Ceros → NaN → imputar → ÷10 (unidades SoilGrids ×10)
  10. limpiar_igac     — IGAC vocación NoData → categoría 0
  11. limpiar_humedad  — IDEAM humedad meses colapsados → interpolar temporalmente
  12. limpiar_pendiente — Pendiente: verificar unidades y convertir a porcentaje

Uso (desde la raíz del proyecto):
    uv run procesamiento/03_feature_engineering.py               # Calcula todos
    uv run procesamiento/03_feature_engineering.py --step aspecto   # Aspecto sin/cos
    uv run procesamiento/03_feature_engineering.py --step soilgrids # Limpiar SoilGrids
    uv run procesamiento/03_feature_engineering.py --step igac      # Limpiar IGAC vocación
    uv run procesamiento/03_feature_engineering.py --step humedad   # Limpiar humedad IDEAM
    uv run procesamiento/03_feature_engineering.py --step pendiente # Verificar pendiente
    uv run procesamiento/03_feature_engineering.py --step piso      # Piso térmico
    uv run procesamiento/03_feature_engineering.py --step amplitud  # Amplitud térmica
    uv run procesamiento/03_feature_engineering.py --step fertilidad
    uv run procesamiento/03_feature_engineering.py --step anomalia
    uv run procesamiento/03_feature_engineering.py --step ndvi
    uv run procesamiento/03_feature_engineering.py --step aridez
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

    # NOTA: limpiar_soilgrids() ya convirtió ÷10 a unidades reales.
    # phh2o ya está en pH real (3.5-6.7), nitrogen en cg/kg, etc.
    # Si phh2o mean > 14, aún no se ejecutó limpiar_soilgrids → convertir aquí
    if np.nanmean(phh2o) > 14:
        print("  ADVERTENCIA: SoilGrids no ha sido limpiado (÷10). Convirtiendo al vuelo...")
        phh2o = phh2o / 10.0
        nitrogen = nitrogen / 10.0
        cec = cec / 10.0
        soc = soc / 10.0

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
# 7. ASPECTO CIRCULAR — Descomposición sin/cos (fix valor -1)
# ══════════════════════════════════════════════════════════════════

def calcular_aspecto_circular():
    """
    Convierte aspecto (0-360°) en dos variables lineales continuas:
      aspecto_sin = sin(aspecto × π/180)
      aspecto_cos = cos(aspecto × π/180)
    
    Los píxeles planos (aspecto = -1, estándar GDAL) se asignan (0, 0),
    indicando sin dirección preferida.
    
    Esto elimina el problema del valor -1 y la discontinuidad 0°/360°.
    La columna 'aspecto' original se descarta de la vista minable.
    """
    print("\n" + "="*70)
    print("7. ASPECTO CIRCULAR (sin/cos)")
    print("="*70)

    asp_path = os.path.join(PROC_DIR, 'topo', f'dem_aspecto_{RESOLUCION_M}m.tif')
    out_sin  = os.path.join(ENG_DIR, 'aspecto_sin.tif')
    out_cos  = os.path.join(ENG_DIR, 'aspecto_cos.tif')

    if os.path.exists(out_sin) and os.path.exists(out_cos):
        print("  Ya existen. Saltando.")
        return

    if not os.path.exists(asp_path):
        print(f"  Aspecto no encontrado: {asp_path}")
        return

    aspecto, profile = _leer_banda(asp_path)

    # Máscara de píxeles planos (aspecto = -1 o NaN)
    planos = (aspecto < 0) | np.isnan(aspecto)

    # Convertir grados a radianes y calcular sin/cos
    rad = np.deg2rad(aspecto)
    sin_arr = np.sin(rad)
    cos_arr = np.cos(rad)

    # Píxeles planos → sin dirección preferida
    sin_arr[planos] = 0.0
    cos_arr[planos] = 0.0

    if not os.path.exists(out_sin):
        _escribir(out_sin, sin_arr, profile)
        print(f"  OK → aspecto_sin.tif")

    if not os.path.exists(out_cos):
        _escribir(out_cos, cos_arr, profile)
        print(f"  OK → aspecto_cos.tif")

    n_planos = np.count_nonzero(planos)
    total = planos.size
    print(f"  Píxeles planos (aspecto=-1): {n_planos:,} ({100*n_planos/total:.1f}%)")


# ══════════════════════════════════════════════════════════════════
# 8. LIMPIAR SOILGRIDS — Ceros inválidos → NaN → imputar mediana
# ══════════════════════════════════════════════════════════════════

def _imputar_mediana_espacial(arr, kernel_size=3):
    """
    Imputa NaN con la mediana de vecinos válidos en un kernel cuadrado.
    Si todos los vecinos son NaN, deja NaN (se imputará con mediana global).
    """
    from scipy.ndimage import median_filter
    import warnings

    mask_nan = np.isnan(arr)
    if not np.any(mask_nan):
        return arr

    # Mediana solo de valores válidos: reemplazar NaN temporalmente
    # con la mediana global para el filtro, luego restaurar solo donde había NaN
    global_median = np.nanmedian(arr)
    arr_filled = np.where(mask_nan, global_median, arr)
    smoothed = median_filter(arr_filled, size=kernel_size, mode='nearest')

    # Reemplazar NaN con la mediana espacial
    result = arr.copy()
    result[mask_nan] = smoothed[mask_nan]

    # Si quedan NaN residuales, usar mediana global
    still_nan = np.isnan(result)
    if np.any(still_nan):
        result[still_nan] = global_median

    return result


def limpiar_soilgrids():
    """
    Reemplaza ceros inválidos (NoData sin marcar) en SoilGrids con NaN,
    luego imputa con mediana espacial de vecinos 3×3.
    
    SoilGrids tiene ~1.1% ceros en phh2o, soc, nitrogen, cec, bdod, ocd
    que son físicamente imposibles (pH=0, SOC=0, etc.).
    Las versiones _norm (clay, sand, silt) ya están limpias.
    """
    import rasterio
    print("\n" + "="*70)
    print("8. LIMPIAR SOILGRIDS (ceros → NaN → imputar)")
    print("="*70)

    sg_dir = os.path.join(PROC_DIR, 'suelo', 'soilgrids')

    # Variables a limpiar (excluyendo _norm que ya están limpias)
    variables = {
        'phh2o':    'soilgrids_phh2o_0_5cm.tif',
        'soc':      'soilgrids_soc_0_5cm.tif',
        'nitrogen': 'soilgrids_nitrogen_0_5cm.tif',
        'cec':      'soilgrids_cec_0_5cm.tif',
        'bdod':     'soilgrids_bdod_0_5cm.tif',
        'ocd':      'soilgrids_ocd_0_5cm.tif',
    }

    for var_name, filename in variables.items():
        src_path = os.path.join(sg_dir, filename)

        if not os.path.exists(src_path):
            print(f"  [{var_name}] No encontrado: {filename}. Saltando.")
            continue

        arr, profile = _leer_banda(src_path)

        # Detectar ceros (inválidos en todas estas variables)
        ceros = (arr == 0) & ~np.isnan(arr)
        n_ceros = np.count_nonzero(ceros)
        pct_ceros = 100 * n_ceros / arr.size

        if n_ceros == 0:
            print(f"  [{var_name}] Sin ceros. OK.")
            continue

        # Reemplazar ceros con NaN
        arr[ceros] = np.nan

        # Imputar con mediana espacial
        arr_limpia = _imputar_mediana_espacial(arr, kernel_size=3)

        # Sobreescribir el archivo original con la versión limpia
        with rasterio.open(src_path, 'w', **profile) as dst:
            out = np.where(np.isnan(arr_limpia), NODATA, arr_limpia).astype(np.float32)
            # Restaurar NoData original
            out[out == NODATA] = NODATA
            dst.write(out, 1)

        print(f"  [{var_name}] {n_ceros:,} ceros ({pct_ceros:.1f}%) → imputados con mediana espacial")

    # ── Conversión ÷10: SoilGrids reporta valores ×10 ──
    # phh2o: pH×10 → pH real (ej: 52 → 5.2)
    # soc: dg/kg ×10 → dg/kg real (ej: 706 → 70.6)
    # nitrogen: cg/kg ×10 → cg/kg real (ej: 435 → 43.5)
    # cec: mmol(c)/kg ×10 → real (ej: 236 → 23.6)
    # bdod: kg/dm³ ×10 → real (ej: 102 → 10.2 → wait, bdod is 100×)
    # ocd: dg/kg ×10 → real
    print("\n  Convirtiendo unidades SoilGrids (÷10 para valores reales)...")
    factores = {
        'phh2o':    ('soilgrids_phh2o_0_5cm.tif',    10.0,  'pH (rango 3.5-6.7)'),
        'soc':      ('soilgrids_soc_0_5cm.tif',      10.0,  'SOC dg/kg (rango ~7-189)'),
        'nitrogen': ('soilgrids_nitrogen_0_5cm.tif',  10.0,  'N cg/kg (rango ~4-93)'),
        'cec':      ('soilgrids_cec_0_5cm.tif',      10.0,  'CEC mmol(c)/kg (rango ~7-74)'),
        'bdod':     ('soilgrids_bdod_0_5cm.tif',     10.0,  'bdod kg/dm³×100 (rango ~0.7-1.5)'),
        'ocd':      ('soilgrids_ocd_0_5cm.tif',      10.0,  'OCD dg/kg'),
    }

    for var_name, (filename, factor, unidad) in factores.items():
        src_path = os.path.join(sg_dir, filename)
        if not os.path.exists(src_path):
            continue

        arr, profile = _leer_banda(src_path)

        # Verificar si ya fue convertido (phh2o real < 14, soc real < 200)
        mean_val = np.nanmean(arr)
        if var_name == 'phh2o' and mean_val < 14:
            print(f"  [{var_name}] Ya en unidades reales (mean={mean_val:.1f}). Sin conversión.")
            continue

        arr_real = arr / factor
        _escribir(src_path, arr_real, profile)
        print(f"  [{var_name}] ÷{factor:.0f} → {unidad} (mean={np.nanmean(arr_real):.2f})")

    print("  SoilGrids limpiado y convertido a unidades reales.")


# ══════════════════════════════════════════════════════════════════
# 9. LIMPIAR IGAC — Vocación NoData → categoría 0
# ══════════════════════════════════════════════════════════════════

def limpiar_igac():
    """
    Reemplaza NoData en IGAC vocación con categoría 0 ("Sin información").
    
    IGAC vocación tiene 50.3% NoData porque zonas urbanas, páramos y 
    bosques protectores no tienen vocación agrícola asignada.
    
    Categoría 0 = "Sin información" es tratada correctamente por modelos
    basados en árboles (RF, XGBoost, LightGBM).
    """
    import rasterio
    print("\n" + "="*70)
    print("9. LIMPIAR IGAC VOCACIÓN (NoData → categoría 0)")
    print("="*70)

    igac_dir = os.path.join(PROC_DIR, 'suelo', 'igac')

    # Buscar archivo de vocación
    vocacion_path = None
    for f in os.listdir(igac_dir) if os.path.isdir(igac_dir) else []:
        if 'vocacion' in f.lower() and f.endswith('.tif'):
            vocacion_path = os.path.join(igac_dir, f)
            break

    if vocacion_path is None:
        print("  Archivo igac_vocacion no encontrado. Saltando.")
        return

    arr, profile = _leer_banda(vocacion_path)

    # Detectar NoData (NaN o valores negativos)
    nodata_mask = np.isnan(arr) | (arr < 0)
    n_nodata = np.count_nonzero(nodata_mask)
    pct_nodata = 100 * n_nodata / arr.size

    if n_nodata == 0:
        print("  IGAC vocación sin NoData. OK.")
        return

    # Reemplazar NoData con categoría 0
    arr[nodata_mask] = 0

    # Convertir a int16 y guardar con nodata=255 (valor que no se usa)
    out = arr.astype(np.int16)
    profile.update(dtype='int16', nodata=255)

    with rasterio.open(vocacion_path, 'w', **profile) as dst:
        dst.write(out, 1)

    print(f"  IGAC vocación: {n_nodata:,} píxeles NoData ({pct_nodata:.1f}%) → categoría 0")
    print("  OK → igac_vocacion limpiado.")


# ══════════════════════════════════════════════════════════════════
# 10. LIMPIAR HUMEDAD IDEAM — Meses colapsados → interpolar temporalmente
# ══════════════════════════════════════════════════════════════════

def limpiar_humedad():
    """
    Detecta meses de humedad IDEAM con varianza casi cero (std < 0.05),
    indicando que el kriging colapsó a un valor constante.
    Reemplaza esos meses con interpolación temporal entre meses adyacentes válidos.
    """
    import rasterio
    print("\n" + "="*70)
    print("10. LIMPIAR HUMEDAD IDEAM (varianza casi cero)")
    print("="*70)

    ideam_dir = os.path.join(PROC_DIR, 'clima', 'ideam')
    if not os.path.isdir(ideam_dir):
        print("  Directorio IDEAM no encontrado. Saltando.")
        return

    # Recolectar todos los archivos mensuales de humedad
    humedad_files = sorted(glob.glob(os.path.join(ideam_dir, 'humedad_*_kriging.tif')))
    if not humedad_files:
        print("  No hay archivos de humedad. Saltando.")
        return

    # Leer todos los meses y detectar colapsados (std < 0.05)
    datos = {}
    profile = None
    colapsados = []

    for fpath in humedad_files:
        nombre = os.path.basename(fpath)
        # Extraer mes: humedad_2020_01_kriging.tif → 2020_01
        partes = nombre.replace('humedad_', '').replace('_kriging.tif', '')
        arr, prof = _leer_banda(fpath)
        datos[partes] = arr
        if profile is None:
            profile = prof

        std_val = np.nanstd(arr)
        if std_val < 0.05:
            colapsados.append(partes)
            print(f"  [{partes}] COLAPSADO (std={std_val:.4f})")
        else:
            print(f"  [{partes}] OK (std={std_val:.4f})")

    if not colapsados:
        print("  Todos los meses de humedad están OK.")
        return

    print(f"  {len(colapsados)} meses colapsados → interpolando temporalmente")

    # Ordenar meses cronológicamente
    meses_ordenados = sorted(datos.keys())

    for mes_col in colapsados:
        idx = meses_ordenados.index(mes_col)

        # Buscar mes válido anterior
        anterior = None
        for i in range(idx - 1, -1, -1):
            if meses_ordenados[i] not in colapsados:
                anterior = meses_ordenados[i]
                break

        # Buscar mes válido siguiente
        siguiente = None
        for i in range(idx + 1, len(meses_ordenados)):
            if meses_ordenados[i] not in colapsados:
                siguiente = meses_ordenados[i]
                break

        if anterior and siguiente:
            # Interpolación lineal entre los dos
            arr_interp = (datos[anterior] + datos[siguiente]) / 2.0
        elif anterior:
            arr_interp = datos[anterior].copy()
        elif siguiente:
            arr_interp = datos[siguiente].copy()
        else:
            print(f"    [{mes_col}] Sin meses adyacentes válidos. Saltando.")
            continue

        # Reemplazar donde era constante (todo el ráster es el mismo valor)
        datos[mes_col] = arr_interp

        # Guardar
        out_path = os.path.join(ideam_dir, f'humedad_{mes_col}_kriging.tif')
        _escribir(out_path, arr_interp, profile)
        nuevo_std = np.nanstd(arr_interp)
        print(f"    [{mes_col}] Interpolado → std={nuevo_std:.4f}")

    print("  Humedad IDEAM limpiada.")


# ══════════════════════════════════════════════════════════════════
# 11. VERIFICAR PENDIENTE — Detectar unidades y convertir
# ══════════════════════════════════════════════════════════════════

def limpiar_pendiente():
    """
    Verifica unidades de pendiente:
    - Si max > 100 → gdaldem produjo grados (0-90°), convertir a porcentaje
      con tan(grados) × 100
    - Si max ≤ 100 → ya está en porcentaje
    
    Pendientes > 100% son posibles geométricamente (cliffs > 45°).
    El valor 244% corresponde a ~68° que es razonable para Cundinamarca.
    """
    import rasterio
    print("\n" + "="*70)
    print("11. VERIFICAR PENDIENTE")
    print("="*70)

    pend_path = os.path.join(PROC_DIR, 'topo', f'dem_pendiente_{RESOLUCION_M}m.tif')
    if not os.path.exists(pend_path):
        print(f"  Pendiente no encontrada: {pend_path}")
        return

    arr, profile = _leer_banda(pend_path)
    max_val = np.nanmax(arr)
    min_val = np.nanmin(arr)
    mean_val = np.nanmean(arr)

    print(f"  Estadísticas actuales: min={min_val:.1f}, mean={mean_val:.1f}, max={max_val:.1f}")

    if max_val > 90 and max_val <= 100:
        # Parecen grados pero el rango es sospechoso
        # GDAL slope produce grados por defecto. Pendiente en grados → convertir
        print(f"  Pendiente parece estar en GRADOS (max={max_val:.1f}°)")
        print(f"  Convirtiendo a porcentaje: % = tan(grados) × 100")

        arr_pct = np.tan(np.deg2rad(arr)) * 100.0
        _escribir(pend_path, arr_pct, profile)

        print(f"  Nuevos valores: min={np.nanmin(arr_pct):.1f}%, "
              f"mean={np.nanmean(arr_pct):.1f}%, max={np.nanmax(arr_pct):.1f}%")
        print("  OK → pendiente convertida a porcentaje")

    elif max_val > 100:
        # Ya está en porcentaje (valores > 100% son normales para cliffs)
        print(f"  Pendiente ya está en PORCENTAJE (max={max_val:.1f}%)")
        print(f"  Valores > 100% son normales para pendientes escarpadas (> 45°)")
        print(f"  244% corresponde a ~68° — razonable para Cundinamarca.")
        print("  Sin cambios necesarios.")

    else:
        # max < 90, probablemente ya en porcentaje
        print(f"  Pendiente en porcentaje (rango normal: 0-{max_val:.1f}%)")
        print("  Sin cambios necesarios.")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Feature engineering: variables derivadas en processed/engineered/'
    )
    parser.add_argument(
        '--step',
        choices=['aspecto', 'soilgrids', 'igac', 'humedad', 'pendiente',
                 'piso', 'amplitud', 'fertilidad', 'anomalia', 'ndvi', 'aridez'],
        default=None,
        help='Feature a calcular. Sin --step calcula todos.'
    )
    args = parser.parse_args()

    os.makedirs(ENG_DIR, exist_ok=True)

    pasos = {
        'aspecto':    calcular_aspecto_circular,
        'soilgrids':  limpiar_soilgrids,
        'igac':       limpiar_igac,
        'humedad':    limpiar_humedad,
        'pendiente':  limpiar_pendiente,
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
        # Ejecutar en orden: primero limpieza, luego derivados
        for fn in pasos.values():
            fn()

    print("\n" + "="*70)
    print("FEATURE ENGINEERING COMPLETADO")
    print(f"Salida: {ENG_DIR}")
    print("="*70)


if __name__ == '__main__':
    main()
