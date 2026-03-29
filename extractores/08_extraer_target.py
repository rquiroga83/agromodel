"""
08_extraer_target.py
═══════════════════════════════════════════════════════════════
Descarga los tres datasets de etiquetado (target) para entrenamiento:
  1. EVA — Evaluaciones Agropecuarias Municipales (2007-2024)
  2. Monitoreo Satelital de Cultivos UPRA (polígonos georreferenciados)
  3. Zonificación de Aptitud SIPRA (aptitud Alta/Media/Baja/No Apta)

Fuentes: datos.gov.co (SODA API) y geoservicios.upra.gov.co (ArcGIS REST)
Salida: CSV para EVA, GeoJSON para monitoreo y SIPRA

pip install requests pandas geopandas
"""

import requests
import pandas as pd
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    SODA_BASE, SODA_DATASETS, DIRS, DEPT_DANE, DEPT_NAME,
    HEADERS_GOV, UPRA_MONITOREO, UPRA_APTITUD,
    BBOX_WGS84, crear_directorios
)


# ═══════════════════════════════════════════════════════════════
# 1. EVA — Evaluaciones Agropecuarias Municipales
# ═══════════════════════════════════════════════════════════════
def descargar_eva():
    """Descarga las EVA históricas (MADR 2007-2018) y UPRA (2019-2024)."""
    out_dir = DIRS['target_eva']

    datasets = [
        {
            'id': SODA_DATASETS['eva_historica'],
            'where': f"c_d_dep='{DEPT_DANE}'",
            'file': 'eva_historica_2007_2018_cundinamarca.csv',
            'label': 'EVA Histórica MADR (2007-2018)',
        },
        {
            'id': SODA_DATASETS['eva_upra'],
            'where': f"codigo_dane_departamento='{DEPT_DANE}'",
            'file': 'eva_upra_2019_2024_cundinamarca.csv',
            'label': 'EVA UPRA (2019-2024)',
        },
        {
            'id': SODA_DATASETS['calendario_22'],
            'where': '1=1',
            'file': 'calendario_siembras_cosechas_2022.csv',
            'label': 'Calendario Siembras/Cosechas 2022',
        },
        {
            'id': SODA_DATASETS['calendario_23'],
            'where': '1=1',
            'file': 'calendario_siembras_cosechas_2023.csv',
            'label': 'Calendario Siembras/Cosechas 2023',
        },
    ]

    for ds in datasets:
        out_file = os.path.join(out_dir, ds['file'])
        if os.path.exists(out_file):
            print(f"  Ya existe: {out_file}")
            continue

        print(f"\n  Descargando {ds['label']}...")
        url = f"{SODA_BASE}/{ds['id']}.json"
        all_data = []
        offset = 0
        limit = 50000

        while True:
            params = {
                '$where': ds['where'],
                '$limit': limit,
                '$offset': offset,
            }
            try:
                r = requests.get(url, params=params, headers=HEADERS_GOV, timeout=120)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"  Error: {e}. Reintentando...")
                time.sleep(15)
                continue

            if not data:
                break

            all_data.extend(data)
            print(f"    -> {len(data)} registros (total: {len(all_data):,})")

            if len(data) < limit:
                break
            offset += limit
            time.sleep(1)

        if all_data:
            df = pd.DataFrame(all_data)
            df.to_csv(out_file, index=False)
            print(f"  Guardado: {out_file} ({len(df):,} registros)")


# ═══════════════════════════════════════════════════════════════
# 2. MONITOREO SATELITAL DE CULTIVOS (UPRA)
# ═══════════════════════════════════════════════════════════════
def descargar_capa_arcgis(url, output_path, filtro_depto=True, max_features=50000):
    """
    Descarga una Feature Layer de ArcGIS REST en formato GeoJSON.
    Pagina de a 2000 registros.
    """
    if os.path.exists(output_path):
        print(f"  Ya existe: {output_path}")
        return

    where = f"cod_depart = '{DEPT_DANE}'" if filtro_depto else 'OBJECTID>0'
    all_features = []
    offset = 0

    while True:
        params = {
            'where': where,
            'outFields': '*',
            'f': 'geojson',
            'returnGeometry': 'true',
            'resultOffset': offset,
            'resultRecordCount': 2000,
            'outSR': '4326',
        }

        try:
            r = requests.get(f"{url}/query", params=params, timeout=120,
                             headers=HEADERS_GOV)
            data = r.json()
        except Exception as e:
            print(f"    Error en offset {offset}: {e}")
            time.sleep(10)
            continue

        features = data.get('features', [])
        if not features:
            break

        all_features.extend(features)
        print(f"    -> {len(features)} features (total: {len(all_features)})")

        if len(all_features) >= max_features:
            break

        offset += 2000
        time.sleep(1)

    if all_features:
        geojson = {
            'type': 'FeatureCollection',
            'features': all_features
        }
        with open(output_path, 'w') as f:
            json.dump(geojson, f)
        print(f"  Guardado: {output_path} ({len(all_features)} features)")


def descargar_monitoreo():
    """Descarga polígonos de monitoreo de cultivos (papa, maíz, arroz, etc.)."""
    out_dir = DIRS['target_monitoreo']

    print("\n  Descargando polígonos de monitoreo de cultivos UPRA...")

    for nombre, url in UPRA_MONITOREO.items():
        out_file = os.path.join(out_dir, f"monitoreo_{nombre}.geojson")
        print(f"\n  Capa: {nombre}")
        descargar_capa_arcgis(url, out_file, filtro_depto=True)


# ═══════════════════════════════════════════════════════════════
# 3. ZONIFICACIÓN DE APTITUD (SIPRA)
# ═══════════════════════════════════════════════════════════════
def descargar_sipra():
    """Descarga capas de aptitud por cultivo desde geoservicios UPRA."""
    out_dir = DIRS['target_sipra']

    print("\n  Descargando zonificaciones de aptitud SIPRA...")

    for nombre, url in UPRA_APTITUD.items():
        out_file = os.path.join(out_dir, f"aptitud_{nombre}.geojson")
        print(f"\n  Capa: {nombre}")
        # Las capas de aptitud son nacionales, filtrar por geometry intersect
        descargar_capa_arcgis(url, out_file, filtro_depto=False, max_features=100000)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    crear_directorios()

    print("="*70)
    print("DESCARGA DE DATOS DE ETIQUETADO (TARGET)")
    print("="*70)

    print("\n" + "─"*50)
    print("1. EVA — Evaluaciones Agropecuarias Municipales")
    print("─"*50)
    descargar_eva()

    print("\n" + "─"*50)
    print("2. MONITOREO SATELITAL DE CULTIVOS (UPRA)")
    print("─"*50)
    descargar_monitoreo()

    print("\n" + "─"*50)
    print("3. ZONIFICACIÓN DE APTITUD (SIPRA)")
    print("─"*50)
    descargar_sipra()

    print("\n" + "="*70)
    print("DESCARGA DE TARGETS COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
