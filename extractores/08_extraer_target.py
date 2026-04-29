"""
08_extraer_target.py
═══════════════════════════════════════════════════════════════
Descarga los tres datasets de etiquetado (target) para entrenamiento:
  1. EVA — Evaluaciones Agropecuarias Municipales (2007-2024)
  2. Monitoreo Satelital de Cultivos UPRA (polígonos georreferenciados)
  3. Zonificación de Aptitud SIPRA (aptitud Alta/Media/Baja/No Apta)

Fuentes: datos.gov.co (SODA API) y geoservicios.upra.gov.co (ArcGIS REST)
Salida: CSV para EVA, GeoJSON para monitoreo y SIPRA

Uso:
    python 08_extraer_target.py                   # Descarga los 3 datasets
    python 08_extraer_target.py --step eva         # Solo EVA
    python 08_extraer_target.py --step monitoreo   # Solo Monitoreo UPRA
    python 08_extraer_target.py --step sipra       # Solo Aptitud SIPRA

pip install requests pandas geopandas
"""

import argparse
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
            'where': f"c_digo_dane_departamento='{DEPT_DANE}'",
            'file': 'eva_upra_2019_2024_cundinamarca.csv',
            'label': 'EVA UPRA (2019-2024)',
        },
        {
            'id': SODA_DATASETS['calendario_nacional'],
            'where': '1=1',
            'file': 'calendario_nacional_siembras_cosechas_2023_2024.csv',
            'label': 'Calendario Nacional Siembras/Cosechas 2023-2024',
        },
        {
            'id': SODA_DATASETS['calendario_depto'],
            'where': '1=1',
            'file': 'calendario_depto_siembras_cosechas_2023_2024.csv',
            'label': 'Calendario Departamental Siembras/Cosechas 2023-2024',
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
                if r.status_code == 404:
                    print(f"  Dataset no encontrado (404). El ID puede haber sido eliminado.")
                    break
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.HTTPError as e:
                print(f"  Error HTTP: {e}. Saltando dataset.")
                break
            except Exception as e:
                print(f"  Error: {e}. Reintentando en 15s...")
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
def descargar_capa_arcgis(url, output_path, filtro_depto=True, max_features=50000,
                          page_size=1000, use_bbox=True):
    """
    Descarga una Feature Layer de ArcGIS REST en formato GeoJSON con:
      - Filtro espacial por bbox Cundinamarca (server-side, ahorra ancho de banda)
      - Fallback a filtro por campo cod_depart/COD_DEPTO si el bbox falla
      - Checkpointing a `{output_path}.part.json` cada 10 páginas (resume)
      - Reintentos con backoff exponencial (10→20→40→80→160s, máx 5)

    Retorna True si descargó datos, False si el servicio no existe o está vacío.
    """
    if os.path.exists(output_path):
        print(f"  Ya existe: {output_path}")
        return True

    # ── Checkpoint: si hay .part previo, reanudar ──
    part_path = output_path + '.part.json'
    all_features = []
    offset = 0
    if os.path.exists(part_path):
        try:
            with open(part_path, 'r', encoding='utf-8') as f:
                cp = json.load(f)
            all_features = cp.get('features', [])
            offset = cp.get('next_offset', len(all_features))
            print(f"  Reanudando desde checkpoint: {len(all_features):,} features,"
                  f" offset={offset}")
        except Exception as e:
            print(f"  Checkpoint corrupto ({e}); empezando desde 0.")
            all_features = []
            offset = 0

    # ── Opciones de filtrado (primero bbox, luego campo depto, luego todo) ──
    where_options = []
    geom_params_options = []

    if use_bbox:
        # Filtro espacial: envelope Cundinamarca en EPSG:4326
        xmin, ymin, xmax, ymax = BBOX_WGS84
        geom_params_options.append({
            'geometry': f'{xmin},{ymin},{xmax},{ymax}',
            'geometryType': 'esriGeometryEnvelope',
            'inSR': '4326',
            'spatialRel': 'esriSpatialRelIntersects',
        })

    if filtro_depto:
        where_options = [
            f"cod_depart = '{DEPT_DANE}'",
            f"COD_DEPTO = '{DEPT_DANE}'",
            'OBJECTID>0',
        ]
    else:
        where_options = ['OBJECTID>0']

    # Índices del filtro actual
    geom_idx = 0  # qué geom_params estamos usando (0..len-1) o -1 = sin bbox
    where_idx = 0

    def _params_actuales():
        p = {
            'where': where_options[where_idx],
            'outFields': '*',
            'f': 'geojson',
            'returnGeometry': 'true',
            'resultOffset': offset,
            'resultRecordCount': page_size,
            'outSR': '4326',
        }
        if geom_idx >= 0 and geom_idx < len(geom_params_options):
            p.update(geom_params_options[geom_idx])
        return p

    errores_consecutivos = 0
    backoffs = [10, 20, 40, 80, 160]  # 5 reintentos

    while True:
        try:
            r = requests.get(f"{url}/query", params=_params_actuales(), timeout=180,
                             headers=HEADERS_GOV)
            if not r.content:
                raise ValueError("Respuesta vacía del servidor")
            data = r.json()
        except Exception as e:
            if errores_consecutivos >= len(backoffs):
                print(f"    Servicio no disponible tras {len(backoffs)} intentos: {e}")
                # Guardar checkpoint antes de abortar (resume en próxima ejecución)
                _guardar_checkpoint(part_path, all_features, offset)
                return False
            wait = backoffs[errores_consecutivos]
            errores_consecutivos += 1
            print(f"    Error en offset {offset}: {e}. Reintentando en {wait}s"
                  f" ({errores_consecutivos}/{len(backoffs)})...")
            time.sleep(wait)
            continue

        # Error lógico de ArcGIS (campo inválido, servicio no soporta bbox, etc.)
        if 'error' in data:
            err_msg = data['error'].get('message', '')
            err_code = data['error'].get('code', 0)

            # Si el bbox falla (ej. servicio no soporta geometry), probar sin él
            if geom_idx >= 0:
                print(f"    Filtro bbox falló ({err_msg}); reintentando sin bbox.")
                geom_idx = -1
                errores_consecutivos = 0
                continue

            # Probar siguiente where si hay
            if filtro_depto and where_idx < len(where_options) - 1:
                where_idx += 1
                print(f"    Filtro falló ({err_msg}); probando: {where_options[where_idx]}")
                errores_consecutivos = 0
                continue

            print(f"    Error ArcGIS [{err_code}]: {err_msg}. Abortando capa.")
            return False

        errores_consecutivos = 0
        features = data.get('features', [])
        if not features:
            break

        all_features.extend(features)
        print(f"    -> {len(features)} features (total: {len(all_features):,})")

        # Checkpoint cada 10 páginas
        offset += page_size
        if (offset // page_size) % 10 == 0:
            _guardar_checkpoint(part_path, all_features, offset)

        if len(all_features) >= max_features:
            print(f"    Alcanzado max_features={max_features:,}; deteniendo.")
            break

        time.sleep(1)

    if all_features:
        geojson = {'type': 'FeatureCollection', 'features': all_features}
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f)
        print(f"  Guardado: {output_path} ({len(all_features):,} features)")
        # Limpiar checkpoint
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass
        return True
    else:
        print(f"  Sin features para esta capa (puede no haber datos en Cundinamarca).")
        return False


def _guardar_checkpoint(part_path, features, next_offset):
    """Persiste el progreso de descarga para poder reanudar."""
    try:
        cp = {'features': features, 'next_offset': next_offset}
        with open(part_path, 'w', encoding='utf-8') as f:
            json.dump(cp, f)
    except Exception as e:
        print(f"    [WARN] No se pudo guardar checkpoint: {e}")


def descargar_monitoreo():
    """Descarga polígonos de monitoreo UPRA: Papa en Cundinamarca (única cobertura)."""
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
    parser = argparse.ArgumentParser(
        description='Descarga datasets de etiquetado (target) del proyecto.'
    )
    parser.add_argument(
        '--step',
        choices=['eva', 'monitoreo', 'sipra'],
        default=None,
        help='Dataset a descargar. Sin --step descarga los 3.'
    )
    args = parser.parse_args()

    crear_directorios()

    print("="*70)
    print("DESCARGA DE DATOS DE ETIQUETADO (TARGET)")
    print("="*70)

    if args.step == 'eva':
        print("\n" + "-"*50)
        print("1. EVA — Evaluaciones Agropecuarias Municipales")
        print("-"*50)
        descargar_eva()
    elif args.step == 'monitoreo':
        print("\n" + "-"*50)
        print("2. MONITOREO SATELITAL DE CULTIVOS (UPRA)")
        print("-"*50)
        descargar_monitoreo()
    elif args.step == 'sipra':
        print("\n" + "-"*50)
        print("3. ZONIFICACIÓN DE APTITUD (SIPRA)")
        print("-"*50)
        descargar_sipra()
    else:
        print("\n" + "-"*50)
        print("1. EVA — Evaluaciones Agropecuarias Municipales")
        print("-"*50)
        descargar_eva()

        print("\n" + "-"*50)
        print("2. MONITOREO SATELITAL DE CULTIVOS (UPRA)")
        print("-"*50)
        descargar_monitoreo()

        print("\n" + "-"*50)
        print("3. ZONIFICACIÓN DE APTITUD (SIPRA)")
        print("-"*50)
        descargar_sipra()

    print("\n" + "="*70)
    print("DESCARGA DE TARGETS COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
