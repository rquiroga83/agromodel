"""
Analisis Estadistico Completo de Datos Procesados para Vista Minable
=====================================================================
Examina todos los rasteres en processed/ y genera un informe con:
  - Estadisticos descriptivos por variable
  - Porcentaje de nulos/NoData/ceros
  - Alertas de variables problematicas
  - Correlaciones entre variables
  - Balance de clases en categoricas
  - Recomendaciones de exclusion para vista minable

Uso:
    python notebooks/analisis_estadistico_vista_minable.py
"""

import os
import sys
import glob
import json
import warnings
import numpy as np
from collections import defaultdict

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, 'processed')
NODATA = -9999.0


def leer_raster(path, banda=1):
    """Lee un raster y retorna (array_valido, array_completo, perfil, total_pixels)."""
    import rasterio
    with rasterio.open(path) as src:
        arr = src.read(banda).astype(np.float32)
        profile = src.profile
        total_pixels = arr.size
        nodata_mask = (arr == NODATA)
        if src.nodata is not None and src.nodata != NODATA:
            nodata_mask = nodata_mask | (arr == src.nodata)
        arr[nodata_mask] = np.nan
        valid = arr[~np.isnan(arr)]
        return valid, arr, profile, total_pixels


def stats_basicos(valid):
    """Calcula estadisticos basicos de un array 1D de valores validos."""
    if len(valid) == 0:
        return None
    n = len(valid)
    mean_val = float(np.mean(valid))
    std_val = float(np.std(valid))
    return {
        'n': n,
        'mean': mean_val,
        'std': std_val,
        'min': float(np.min(valid)),
        'p25': float(np.percentile(valid, 25)),
        'p50': float(np.percentile(valid, 50)),
        'p75': float(np.percentile(valid, 75)),
        'max': float(np.max(valid)),
        'cv': std_val / (abs(mean_val) + 1e-9),
        'n_zeros': int(np.sum(valid == 0)),
        'pct_zeros': float(np.sum(valid == 0) / n * 100),
    }


def analizar_capas_estaticas():
    """Analiza todas las capas estaticas (topo, suelo)."""
    print("=" * 80)
    print("ANALISIS DE CAPAS ESTATICAS")
    print("=" * 80)

    capas = {
        'topografia': {
            'dir': os.path.join(PROC_DIR, 'topo'),
            'patrones': ['dem_*_50m.tif'],
        },
        'soilgrids': {
            'dir': os.path.join(PROC_DIR, 'suelo', 'soilgrids'),
            'patrones': ['soilgrids_*.tif'],
        },
        'igac': {
            'dir': os.path.join(PROC_DIR, 'suelo', 'igac'),
            'patrones': ['igac_*.tif'],
        },
    }

    resultados = {}
    alertas = []

    for grupo, cfg in capas.items():
        print(f"\n--- {grupo.upper()} ---")
        for patron in cfg['patrones']:
            archivos = sorted(glob.glob(os.path.join(cfg['dir'], patron)))
            for fpath in archivos:
                nombre = os.path.basename(fpath)
                base = nombre.replace('.tif', '')
                # Para texturas, solo analizar las _norm
                skip = False
                for tex in ['clay', 'sand', 'silt']:
                    if f'_{tex}_' in base and not base.endswith('_norm'):
                        skip = True
                        break
                if skip:
                    continue

                try:
                    valid, arr, profile, total = leer_raster(fpath)
                    st = stats_basicos(valid)
                    if st is None:
                        print(f"  {nombre}: SIN DATOS VALIDOS")
                        alertas.append(f"CRITICO: {nombre} - 0% datos validos")
                        continue

                    pct_nodata = (1 - st['n'] / total) * 100
                    st['total_pixels'] = total
                    st['pct_nodata'] = pct_nodata
                    st['archivo'] = nombre
                    st['grupo'] = grupo
                    resultados[base] = st

                    print(f"  {nombre}: n={st['n']:,} ({100-pct_nodata:.1f}% valido), "
                          f"mean={st['mean']:.3f}, std={st['std']:.3f}, "
                          f"range=[{st['min']:.3f}, {st['max']:.3f}], "
                          f"zeros={st['pct_zeros']:.1f}%")

                    if pct_nodata > 50:
                        alertas.append(f"ALTO NODATA: {nombre} - {pct_nodata:.1f}% pixeles sin datos")
                    if pct_nodata > 90:
                        alertas.append(f"CRITICO NODATA: {nombre} - {pct_nodata:.1f}% pixeles sin datos. Considerar excluir.")
                    if st['pct_zeros'] > 50:
                        alertas.append(f"ALTO CEROS: {nombre} - {st['pct_zeros']:.1f}% pixeles en cero")
                    if st['cv'] < 0.01 and st['std'] < 0.001:
                        alertas.append(f"VARIANZA CERO: {nombre} - variable practicamente constante (std={st['std']:.6f}). EXCLUIR.")
                    if st['n'] > 0 and st['min'] == st['max']:
                        alertas.append(f"CONSTANTE: {nombre} - todos los valores son iguales ({st['min']}). EXCLUIR.")

                except Exception as e:
                    print(f"  {nombre}: ERROR - {e}")
                    alertas.append(f"ERROR: {nombre} - {e}")

    return resultados, alertas


def analizar_capas_mensuales():
    """Analiza una muestra de capas mensuales (1 mes por semestre)."""
    print("\n" + "=" * 80)
    print("ANALISIS DE CAPAS MENSUALES (MUESTRA: ENERO Y JULIO DE CADA ANO)")
    print("=" * 80)

    capas_mensuales = {
        'ideam_temperatura': {
            'dir': os.path.join(PROC_DIR, 'clima', 'ideam'),
            'patron': 'temperatura_{}_kriging.tif',
        },
        'ideam_precipitacion': {
            'dir': os.path.join(PROC_DIR, 'clima', 'ideam'),
            'patron': 'precipitacion_{}_kriging.tif',
        },
        'ideam_humedad': {
            'dir': os.path.join(PROC_DIR, 'clima', 'ideam'),
            'patron': 'humedad_{}_kriging.tif',
        },
        'chirps': {
            'dir': os.path.join(PROC_DIR, 'clima', 'chirps'),
            'patron': 'chirps_{}.tif',
        },
        'sentinel2': {
            'dir': os.path.join(PROC_DIR, 'satelite', 'sentinel2'),
            'patron': 's2_indices_{}.tif',
            'multibanda': True,
            'bandas': ['NDVI', 'GNDVI', 'EVI', 'NDWI', 'MSAVI', 'BSI', 'SAVI'],
        },
        'sentinel1': {
            'dir': os.path.join(PROC_DIR, 'satelite', 'sentinel1'),
            'patron': 's1_backscatter_{}.tif',
            'multibanda': True,
            'bandas': ['VV_dB', 'VH_dB', 'VH_VV_ratio_dB'],
        },
    }

    muestras = []
    for y in range(2020, 2026):
        muestras.append(f'{y}_01')
        muestras.append(f'{y}_07')

    resultados = {}
    alertas = []
    disponibilidad = {}

    for var_name, cfg in capas_mensuales.items():
        print(f"\n--- {var_name.upper()} ---")

        for mes in muestras:
            fpath = os.path.join(cfg['dir'], cfg['patron'].format(mes))
            if not os.path.exists(fpath):
                print(f"  {mes}: NO ENCONTRADO")
                continue

            multibanda = cfg.get('multibanda', False)

            if multibanda:
                import rasterio
                with rasterio.open(fpath) as src:
                    n_bandas = src.count
                    bandas = cfg.get('bandas', [f'banda_{i+1}' for i in range(n_bandas)])
                    for b_idx, b_name in enumerate(bandas):
                        if b_idx + 1 > n_bandas:
                            continue
                        valid, arr, profile, total = leer_raster(fpath, banda=b_idx + 1)
                        st = stats_basicos(valid)
                        if st is None:
                            print(f"  {mes}/{b_name}: SIN DATOS VALIDOS")
                            alertas.append(f"CRITICO: {var_name}/{b_name} {mes} - 0% datos validos")
                            continue

                        pct_nodata = (1 - st['n'] / total) * 100
                        key = f"{var_name}_{b_name}_{mes}"
                        st['total_pixels'] = total
                        st['pct_nodata'] = pct_nodata
                        resultados[key] = st

                        print(f"  {mes}/{b_name}: n={st['n']:,} ({100-pct_nodata:.1f}% valido), "
                              f"mean={st['mean']:.4f}, std={st['std']:.4f}, "
                              f"range=[{st['min']:.4f}, {st['max']:.4f}], zeros={st['pct_zeros']:.1f}%")

                        if pct_nodata > 80:
                            alertas.append(f"ALTO NODATA: {var_name}/{b_name} {mes} - {pct_nodata:.1f}% sin datos")
                        if st['pct_zeros'] > 80:
                            alertas.append(f"ALTO CEROS: {var_name}/{b_name} {mes} - {st['pct_zeros']:.1f}% ceros (posible evalscript bug)")
            else:
                valid, arr, profile, total = leer_raster(fpath)
                st = stats_basicos(valid)
                if st is None:
                    print(f"  {mes}: SIN DATOS VALIDOS")
                    alertas.append(f"CRITICO: {var_name} {mes} - 0% datos validos")
                    continue

                pct_nodata = (1 - st['n'] / total) * 100
                key = f"{var_name}_{mes}"
                st['total_pixels'] = total
                st['pct_nodata'] = pct_nodata
                resultados[key] = st

                print(f"  {mes}: n={st['n']:,} ({100-pct_nodata:.1f}% valido), "
                      f"mean={st['mean']:.3f}, std={st['std']:.3f}, "
                      f"range=[{st['min']:.3f}, {st['max']:.3f}], zeros={st['pct_zeros']:.1f}%")

                if pct_nodata > 50:
                    alertas.append(f"ALTO NODATA: {var_name} {mes} - {pct_nodata:.1f}% sin datos")
                if st['pct_zeros'] > 50:
                    alertas.append(f"ALTO CEROS: {var_name} {mes} - {st['pct_zeros']:.1f}% ceros")

        # Verificar disponibilidad total
        patron_full = cfg['patron'].format('*')
        all_files = glob.glob(os.path.join(cfg['dir'], patron_full))
        all_files = [f for f in all_files if f.endswith('.tif')]
        total_6_years = 72
        disponibilidad[var_name] = {
            'archivos_encontrados': len(all_files),
            'archivos_esperados': total_6_years,
            'cobertura_pct': len(all_files) / total_6_years * 100,
        }

    return resultados, alertas, disponibilidad


def analizar_categoricas_igac():
    """Analiza variables categoricas del IGAC con sus tablas de codigos."""
    print("\n" + "=" * 80)
    print("ANALISIS DE VARIABLES CATEGORICAS IGAC (BALANCE DE CLASES)")
    print("=" * 80)

    igac_dir = os.path.join(PROC_DIR, 'suelo', 'igac')
    resultados = {}
    alertas = []

    tif_files = sorted(glob.glob(os.path.join(igac_dir, 'igac_*.tif')))
    for tif_path in tif_files:
        nombre = os.path.basename(tif_path).replace('.tif', '')
        tabla_path = tif_path.replace('.tif', '_tabla_codigos.json')

        try:
            valid, arr, profile, total = leer_raster(tif_path)
            if len(valid) == 0:
                print(f"  {nombre}: SIN DATOS VALIDOS")
                alertas.append(f"CRITICO: IGAC {nombre} - 0% datos validos")
                continue

            unique, counts = np.unique(valid.astype(int), return_counts=True)
            n_clases = len(unique)
            pct_nodata = (1 - len(valid) / total) * 100

            idx_max = np.argmax(counts)
            clase_dominante = int(unique[idx_max])
            pct_dominante = counts[idx_max] / len(valid) * 100

            codigos = None
            if os.path.exists(tabla_path):
                with open(tabla_path, 'r', encoding='utf-8') as f:
                    codigos = json.load(f)

            resultados[nombre] = {
                'n_clases': n_clases,
                'clases': {int(u): int(c) for u, c in zip(unique, counts)},
                'pct_nodata': pct_nodata,
                'clase_dominante': clase_dominante,
                'pct_dominante': pct_dominante,
                'codigos': codigos,
            }

            print(f"\n  {nombre}: {n_clases} clases, {pct_nodata:.1f}% NoData, "
                  f"clase dominante ({clase_dominante}): {pct_dominante:.1f}%")

            if codigos:
                for val, count in sorted(zip(unique, counts), key=lambda x: -x[1]):
                    label = codigos.get(str(int(val)), str(int(val)))
                    pct = count / len(valid) * 100
                    print(f"    {int(val):3d} ({str(label)[:50]:50s}): {count:>10,} ({pct:5.1f}%)")
            else:
                for val, count in sorted(zip(unique, counts), key=lambda x: -x[1]):
                    pct = count / len(valid) * 100
                    print(f"    {int(val):3d}: {count:>10,} ({pct:5.1f}%)")

            if pct_dominante > 90:
                alertas.append(f"DESBALANCE EXTREMO: {nombre} - clase {clase_dominante} domina al {pct_dominante:.1f}%")
            if pct_dominante > 70:
                alertas.append(f"DESBALANCE: {nombre} - clase dominante al {pct_dominante:.1f}%")
            if n_clases == 1:
                alertas.append(f"CONSTANTE: {nombre} - solo 1 clase. EXCLUIR.")
            if n_clases > 50:
                alertas.append(f"ALTA CARDINALIDAD: {nombre} - {n_clases} clases. Considerar agrupar.")

        except Exception as e:
            print(f"  {nombre}: ERROR - {e}")

    return resultados, alertas


def analizar_correlaciones():
    """Calcula correlaciones entre variables estaticas usando una muestra de pixeles."""
    print("\n" + "=" * 80)
    print("ANALISIS DE CORRELACIONES ENTRE VARIABLES ESTATICAS")
    print("=" * 80)

    import rasterio
    import pandas as pd

    SAMPLE_SIZE = 50000

    capas_para_correlar = {}

    # Topografia
    for f in sorted(glob.glob(os.path.join(PROC_DIR, 'topo', 'dem_*_50m.tif'))):
        nombre = os.path.basename(f).replace('.tif', '').replace('dem_', '').replace('_50m', '')
        capas_para_correlar[f'topo_{nombre}'] = f

    # SoilGrids (solo 0_5cm y _norm para texturas)
    for f in sorted(glob.glob(os.path.join(PROC_DIR, 'suelo', 'soilgrids', 'soilgrids_*_0_5cm*.tif'))):
        nombre = os.path.basename(f).replace('.tif', '').replace('soilgrids_', '')
        skip = False
        for tex in ['clay', 'sand', 'silt']:
            if nombre.startswith(f'{tex}_') and not nombre.endswith('_norm'):
                skip = True
                break
        if skip:
            continue
        capas_para_correlar[f'sg_{nombre}'] = f

    # IGAC
    for f in sorted(glob.glob(os.path.join(PROC_DIR, 'suelo', 'igac', 'igac_*.tif'))):
        nombre = os.path.basename(f).replace('.tif', '')
        capas_para_correlar[f'igac_{nombre}'] = f

    print(f"  Leyendo {len(capas_para_correlar)} capas...")

    arrays = {}
    ref_shape = None
    for nombre, path in capas_para_correlar.items():
        try:
            with rasterio.open(path) as src:
                arr = src.read(1).astype(np.float32)
                nodata_val = src.nodata if src.nodata else NODATA
                arr[arr == nodata_val] = np.nan
                arr[arr == NODATA] = np.nan
                if ref_shape is None:
                    ref_shape = arr.shape
                if arr.shape == ref_shape:
                    arrays[nombre] = arr.ravel()
                else:
                    print(f"  {nombre}: shape diferente ({arr.shape} vs {ref_shape}), saltando")
        except Exception as e:
            print(f"  {nombre}: ERROR - {e}")

    if not arrays:
        print("  No se pudieron leer capas para correlacion.")
        return [], []

    nombres_vars = list(arrays.keys())
    data_matrix = np.column_stack([arrays[n] for n in nombres_vars])
    df = pd.DataFrame(data_matrix, columns=nombres_vars)

    print(f"  Total pixeles: {len(df):,}")
    df_valid = df.dropna()
    print(f"  Pixeles completos (sin NaN en ninguna columna): {len(df_valid):,}")

    if len(df_valid) > SAMPLE_SIZE:
        df_sample = df_valid.sample(n=SAMPLE_SIZE, random_state=42)
    else:
        df_sample = df_valid

    print(f"  Muestra para correlacion: {len(df_sample):,} pixeles")

    corr_matrix = df_sample.corr()

    alertas = []
    pares_corr = []

    for i in range(len(nombres_vars)):
        for j in range(i + 1, len(nombres_vars)):
            c = float(corr_matrix.iloc[i, j])
            if abs(c) > 0.7:
                pares_corr.append((nombres_vars[i], nombres_vars[j], c))
                if abs(c) > 0.95:
                    alertas.append(f"CORRELACION EXTREMA (r={c:.3f}): {nombres_vars[i]} <-> {nombres_vars[j]}. EXCLUIR UNA.")
                elif abs(c) > 0.85:
                    alertas.append(f"CORRELACION ALTA (r={c:.3f}): {nombres_vars[i]} <-> {nombres_vars[j]}. Considerar excluir una.")

    pares_corr.sort(key=lambda x: -abs(x[2]))

    print(f"\n  Pares con |r| > 0.7 ({len(pares_corr)}):")
    for v1, v2, c in pares_corr[:30]:
        print(f"    {v1:40s} <-> {v2:40s}  r = {c:+.4f}")

    if len(pares_corr) > 30:
        print(f"    ... y {len(pares_corr) - 30} pares mas.")

    return alertas, pares_corr


def verificar_disponibilidad_temporal():
    """Verifica la disponibilidad de datos mensuales y temporales."""
    print("\n" + "=" * 80)
    print("DISPONIBILIDAD TEMPORAL DE DATOS")
    print("=" * 80)

    alertas = []

    temp_dir = os.path.join(PROC_DIR, 'temporal')
    if os.path.exists(temp_dir):
        temp_files = glob.glob(os.path.join(temp_dir, '**', '*.tif'), recursive=True)
        if temp_files:
            print(f"  processed/temporal/: {len(temp_files)} archivos encontrados")
        else:
            print(f"  processed/temporal/: VACIO - 02_armonizar_temporal.py NO se ha ejecutado o fallo!")
            alertas.append("CRITICO: processed/temporal/ vacio. Ejecutar 02_armonizar_temporal.py")
    else:
        print(f"  processed/temporal/: NO EXISTE")
        alertas.append("CRITICO: Directorio processed/temporal/ no existe. Ejecutar 02_armonizar_temporal.py")

    fuentes = {
        'IDEAM Temperatura': os.path.join(PROC_DIR, 'clima', 'ideam', 'temperatura_*_kriging.tif'),
        'IDEAM Precipitacion': os.path.join(PROC_DIR, 'clima', 'ideam', 'precipitacion_*_kriging.tif'),
        'IDEAM Humedad': os.path.join(PROC_DIR, 'clima', 'ideam', 'humedad_*_kriging.tif'),
        'CHIRPS': os.path.join(PROC_DIR, 'clima', 'chirps', 'chirps_*.tif'),
        'Sentinel-2': os.path.join(PROC_DIR, 'satelite', 'sentinel2', 's2_indices_*.tif'),
        'Sentinel-1': os.path.join(PROC_DIR, 'satelite', 'sentinel1', 's1_backscatter_*.tif'),
    }

    esperados = 72

    for nombre, patron in fuentes.items():
        archivos = glob.glob(patron)
        n = len(archivos)
        pct = n / esperados * 100
        print(f"  {nombre:30s}: {n:3d}/{esperados} meses ({pct:.0f}%)")

        meses = set()
        for f in archivos:
            base = os.path.basename(f).replace('.tif', '')
            # Parsear YYYY_MM del nombre
            parts = base.split('_')
            for i, p in enumerate(parts):
                if len(p) == 4 and p.isdigit() and i + 1 < len(parts) and len(parts[i+1]) == 2 and parts[i+1].isdigit():
                    meses.add(f"{p}_{parts[i+1]}")

        todos_meses = set()
        for y in range(2020, 2026):
            for m in range(1, 13):
                todos_meses.add(f"{y}_{m:02d}")

        faltantes = sorted(todos_meses - meses)
        if faltantes:
            print(f"    Meses faltantes: {', '.join(faltantes[:10])}{'...' if len(faltantes) > 10 else ''}")
            alertas.append(f"GAPS TEMPORALES: {nombre} falta {len(faltantes)} meses")

    return alertas


def analizar_rangos_fisicos(resultados):
    """Verifica que los valores esten en rangos fisicos esperados."""
    print("\n" + "=" * 80)
    print("VALIDACION DE RANGOS FISICOS")
    print("=" * 80)

    RANGOS = {
        'topo_elevacion': (0, 4500, 'm.s.n.m.'),
        'topo_pendiente': (0, 100, '%'),
        'topo_aspecto': (0, 360, 'grados'),
        'topo_curvatura': (-50, 50, 'adim'),
        'topo_twi': (0, 30, 'adim'),
        'sg_phh2o': (2, 12, 'pH'),
        'sg_soc': (0, 300, 'g/kg'),
        'sg_nitrogen': (0, 20, 'g/kg'),
        'sg_cec': (0, 200, 'cmol/kg'),
        'sg_bdod': (0, 3, 'g/cm3'),
        'sg_ocd': (0, 200, 'g/dm3'),
        'sg_clay': (0, 100, '%'),
        'sg_sand': (0, 100, '%'),
        'sg_silt': (0, 100, '%'),
    }

    alertas = []
    for key, st in resultados.items():
        for prefijo, (vmin, vmax, unidad) in RANGOS.items():
            if key.startswith(prefijo):
                if st['min'] < vmin or st['max'] > vmax:
                    msg = (f"FUERA DE RANGO: {key} = [{st['min']:.2f}, {st['max']:.2f}] "
                           f"esperado [{vmin}, {vmax}] {unidad}")
                    print(f"  ALERTA: {msg}")
                    alertas.append(msg)
                break

    if not alertas:
        print("  Todas las variables dentro de rangos fisicos esperados.")
    return alertas


def generar_informe(alertas_estaticas, alertas_mensuales, alertas_categoricas,
                    alertas_correlacion, alertas_temporal, alertas_rangos,
                    disponibilidad, pares_corr, resultados_estaticos,
                    resultados_categoricos):
    """Genera el informe final consolidado."""

    print("\n\n")
    print("#" * 80)
    print("# INFORME CONSOLIDADO DE ANALISIS ESTADISTICO")
    print("# PARA LA VISTA MINABLE - PROYECTO QUE SEMBRAR?")
    print("#" * 80)

    todas_alertas = []
    todas_alertas.extend([(a, 'CRITICO') for a in alertas_estaticas])
    todas_alertas.extend([(a, 'CRITICO') for a in alertas_temporal])
    todas_alertas.extend([(a, 'ALTO') for a in alertas_mensuales])
    todas_alertas.extend([(a, 'MEDIO') for a in alertas_categoricas])
    todas_alertas.extend([(a, 'MEDIO') for a in alertas_correlacion])
    todas_alertas.extend([(a, 'BAJO') for a in alertas_rangos])

    criticas = [a for a, s in todas_alertas if s == 'CRITICO' or 'CRITICO' in a or 'EXCLUIR' in a]
    altas = [a for a, s in todas_alertas if s == 'ALTO' and a not in criticas]
    medias = [a for a, s in todas_alertas if s == 'MEDIO' and a not in criticas and a not in altas]

    print(f"\n{'='*80}")
    print(f"RESUMEN DE ALERTAS: {len(todas_alertas)} total")
    print(f"  CRITICAS: {len(criticas)}")
    print(f"  ALTAS:    {len(altas)}")
    print(f"  MEDIAS:   {len(medias)}")
    print(f"{'='*80}")

    if criticas:
        print("\n--- ALERTAS CRITICAS ---")
        for a in criticas:
            print(f"  >> {a}")

    if altas:
        print("\n--- ALERTAS ALTAS ---")
        for a in altas:
            print(f"  >> {a}")

    if medias:
        print("\n--- ALERTAS MEDIAS ---")
        for a in medias:
            print(f"  >> {a}")

    print(f"\n{'='*80}")
    print("DISPONIBILIDAD DE DATOS POR FUENTE")
    print(f"{'='*80}")
    for nombre, info in disponibilidad.items():
        print(f"  {nombre:30s}: {info['archivos_encontrados']:3d}/{info['archivos_esperados']} "
              f"({info['cobertura_pct']:.0f}%)")

    # ---- Variables a EXCLUIR ----
    print(f"\n{'='*80}")
    print("RECOMENDACION: VARIABLES A EXCLUIR DE LA VISTA MINABLE")
    print(f"{'='*80}")

    excluir = []
    mantener = []
    revisar = []

    for key, st in resultados_estaticos.items():
        if st['pct_nodata'] > 95:
            excluir.append((key, f">95% NoData ({st['pct_nodata']:.1f}%)"))
            continue
        if st['cv'] < 0.01 and st['std'] < 0.001:
            excluir.append((key, f"Varianza practicamente cero (std={st['std']:.6f})"))
            continue
        if st['n'] > 0 and abs(float(st['min']) - float(st['max'])) < 0.001:
            excluir.append((key, f"Variable constante (valor={st['mean']:.4f})"))
            continue

        if st['pct_nodata'] > 50:
            revisar.append((key, f"Alto NoData ({st['pct_nodata']:.1f}%) - verificar causa"))
        elif st['pct_zeros'] > 30:
            revisar.append((key, f"Alto porcentaje de ceros ({st['pct_zeros']:.1f}%) - posible problema de datos"))
        elif st['pct_nodata'] > 20:
            revisar.append((key, f"NoData moderado ({st['pct_nodata']:.1f}%) - evaluar imputacion"))
        else:
            mantener.append(key)

    for key, info in resultados_categoricos.items():
        if info['pct_nodata'] > 95:
            excluir.append((key, f">95% NoData ({info['pct_nodata']:.1f}%)"))
        elif info['n_clases'] == 1:
            excluir.append((key, "Solo 1 clase - variable constante"))
        elif info['pct_dominante'] > 95:
            revisar.append((key, f"Desbalance extremo: clase dominante al {info['pct_dominante']:.1f}%"))
        elif info['n_clases'] > 100:
            revisar.append((key, f"Alta cardinalidad: {info['n_clases']} clases"))
        else:
            mantener.append(key)

    if pares_corr:
        vars_ya_excluidas = set(v for v, _ in excluir)
        for v1, v2, r in pares_corr:
            if v1 not in vars_ya_excluidas and v2 not in vars_ya_excluidas:
                if abs(r) > 0.95:
                    revisar.append((f"{v1} o {v2}",
                                   f"Correlacion extrema (r={r:.3f}). Mantener solo UNA."))

    print("\n  VARIABLES POR PROFUNDIDAD DE SoilGrids:")
    print("  >> EXCLUIR: Profundidades 5_15cm y 15_30cm para vista minable.")
    print("     Razon: La documentacion indica usar solo 0_5cm (horizonte agricola).")
    print("     EXCLUIR: soilgrids_*_5_15cm.tif, soilgrids_*_15_30cm.tif")
    print("     EXCLUIR: soilgrids_{clay,sand,silt}_*_0_5cm.tif (usar solo _norm)")

    print("\n  EXCLUIR (variables con problemas criticos):")
    for var, razon in excluir:
        print(f"    - {var}: {razon}")

    print("\n  REVISAR (variables con problemas potenciales):")
    for var, razon in revisar:
        print(f"    - {var}: {razon}")

    print(f"\n  MANTENER ({len(mantener)} variables sin problemas detectados)")

    # ---- Recomendaciones de tratamiento ----
    print(f"\n{'='*80}")
    print("RECOMENDACIONES DE TRATAMIENTO POR VARIABLE")
    print(f"{'='*80}")

    print("""
  1. VARIABLES CON NODATA ALTO (>20%):
     - Tratamiento: Imputar con mediana regional o KNN imputer.
     - Si >90% NoData: EXCLUIR (no hay suficiente senal).
     - Para IGAC: NoData=0 significa que el pixel no tiene poligono IGAC.
       Considerar crear categoria "Sin datos IGAC" (cod=0).

  2. VARIABLES CON CEROS ALTOS:
     - Sentinel-2: Ceros = nubosidad o evalscript bug. Tratar como NaN.
     - Precipitacion: Ceros son validos (meses secos). NO imputar.
     - Sentinel-1: Ceros probablemente invalidos. Verificar y tratar como NaN.

  3. VARIABLES CORRELACIONADAS (|r| > 0.85):
     - Mantener SOLO UNA del par para evitar multicolinealidad.
     - Criterio: mantener la de mayor interpretacion agronomica.
     - Ej: NDVI vs GNDVI (r>0.95) -> mantener NDVI.
     - Ej: MSAVI vs SAVI (r>0.95) -> mantener MSAVI.

  4. VARIABLES CATEGORICAS DESBALANCEADAS:
     - Si una clase >90%: considerar binarizar o excluir.
     - IGAC con alta cardinalidad (>50 clases): agrupar por categoria superior.
     - Para variables IGAC con muchas clases raras: agrupar clases <1% en "Otros".

  5. VARIABLES CON ALTA ASIMETRIA (skewness > 2):
     - Aplicar transformacion log1p o Box-Cox.
     - Especialmente: precipitacion, SOC, nitrogen, CEC.

  6. VARIABLES DERIVADAS (feature engineering):
     - indice_fertilidad ya resume ph, N, CEC, SOC. EXCLUIR las 4 componentes
       si se incluye el indice (o viceversa).
     - piso_termico ya resume elevacion. EXCLUIR elevacion si se usa piso_termico
       (o mantener elevacion y excluir piso_termico para modelos que captan
       no linealidades).

  7. SENTINEL-2:
     - NDVI y GNDVI muy correlacionados -> mantener NDVI.
     - EVI y SAVI correlacionados -> mantener EVI.
     - MSAVI y SAVI muy correlacionados -> mantener MSAVI.
     - Sugerencia: mantener NDVI, EVI, NDWI, MSAVI, BSI (5 de 7 indices).

  8. SoilGrids PROFUNDIDADES:
     - Usar SOLO 0_5cm para vista minable (horizonte agricola).
     - Las profundidades 5_15cm y 15_30cm solo para modelos de profundidad.

  9. ASPECTO CIRCULAR:
     - Aspecto es circular (0=360=Norte). Transformar a sin(aspecto) y cos(aspecto).
     - Sin transformacion, el modelo interpretaria 359 y 1 como muy diferentes.

  10. TEMPORAL:
     - CRITICO: Ejecutar 02_armonizar_temporal.py para generar agregados semestrales.
     - Los datos mensuales NO se usan directamente en la vista minable tabular.
     - Solo se usan los estadisticos semestrales (media, max, std, acum).
""")

    print(f"{'='*80}")
    print("ESTRUCTURA SUGERIDA DE LA VISTA MINABLE (COLUMNAS FINALES)")
    print(f"{'='*80}")
    print("""
  COLUMNAS DE IDENTIFICACION:
    pixel_id, row, col, lon, lat, semestre

  FEATURES ESTATICOS (~20 variables):
    Topografia (4): elevacion, pendiente, twi, aspecto_sin, aspecto_cos
    SoilGrids 0_5cm (6): phh2o, soc, nitrogen, cec, bdod, clay_norm
    IGAC (3-5): igac_ph, igac_fosforo, igac_potasio, igac_vocacion, igac_fertilidad
    Derivados (1-2): piso_termico, indice_fertilidad

  Features DINAMICOS por semestre (~20-25 variables):
    Clima (5): temp_media, temp_max, temp_min, humedad_media, precip_acum
    CHIRPS (1): chirps_acum
    Sentinel-2 (10): NDVI_mean, NDVI_max, NDVI_std, EVI_mean, EVI_max,
                     NDWI_mean, MSAVI_mean, BSI_mean, SAVI_mean, SAVI_std
    Sentinel-1 (3): vv_media, vh_media, vh_vv_ratio_media
    Derivados (4): amplitud_termica, anomalia_precip, ndvi_max, indice_aridez

  TARGET (4):
    cultivo_id, cultivo_nombre, confianza_label, fuente_label

  TOTAL ESTIMADO: ~50-55 features (reducido de ~74 originales)
""")


def main():
    print("ANALISIS ESTADISTICO COMPLETO - PROCESSED/")
    print(f"Directorio: {PROC_DIR}")
    print()

    resultados_estaticos, alertas_estaticas = analizar_capas_estaticas()
    resultados_mensuales, alertas_mensuales, disponibilidad = analizar_capas_mensuales()
    resultados_categoricos, alertas_categoricas = analizar_categoricas_igac()
    alertas_corr, pares_corr = analizar_correlaciones()
    alertas_temporal = verificar_disponibilidad_temporal()
    alertas_rangos = analizar_rangos_fisicos(resultados_estaticos)

    generar_informe(
        alertas_estaticas, alertas_mensuales, alertas_categoricas,
        alertas_corr, alertas_temporal, alertas_rangos,
        disponibilidad, pares_corr, resultados_estaticos,
        resultados_categoricos
    )


if __name__ == '__main__':
    main()