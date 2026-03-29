"""
03_extraer_suelo_igac.py
═══════════════════════════════════════════════════════════════
Descarga datos de suelo del IGAC para Colombia.
Dos capas:
  1. Propiedades Químicas del Territorio Nacional (pH, Al, P, K, fertilidad)
  2. Vocación de Uso del Territorio Nacional (18 clases de aptitud)

Fuente: ArcGIS REST Services del IGAC (mapas.igac.gov.co)
Formato de salida: GeoJSON

NOTA: El WAF del IGAC bloquea 'where=1=1'. Usar 'OBJECTID>0'.
Se pagina de a 2000 registros con resultOffset.

pip install requests
"""

import requests
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DIRS, HEADERS_IGAC, crear_directorios


# URLs de las capas del IGAC
CAPAS_IGAC = {
    'quimica': {
        'url': 'https://mapas.igac.gov.co/server/rest/services/agrologia/distribucionycalidaddelaspropiedadesquimicasterritorionacional/MapServer/0/query',
        'output': 'propiedades_quimicas_suelo.geojson',
        'dir_key': 'suelo_igac',
        'descripcion': 'Propiedades Químicas (pH, Aluminio, Fósforo, Potasio, Fertilidad)',
    },
    'vocacion': {
        'url': 'https://mapas.igac.gov.co/server/rest/services/agrologia/vocaciondeusodelastitierras/MapServer/0/query',
        'output': 'vocacion_uso_suelo.geojson',
        'dir_key': 'suelo_vocacion',
        'descripcion': 'Vocación de Uso (Agrícola, Ganadera, Forestal, Conservación)',
    },
}

PAGE_SIZE = 2000


def descargar_capa_igac(capa_key):
    """Descarga una capa IGAC completa con paginación y soporte de reanudación."""
    capa = CAPAS_IGAC[capa_key]
    query_url = capa['url']
    output_file = os.path.join(DIRS[capa['dir_key']], capa['output'])

    print(f"\n{'='*70}")
    print(f"Descargando: {capa['descripcion']}")
    print(f"Fuente: {query_url}")
    print(f"Salida: {output_file}")
    print(f"{'='*70}")

    params = {
        'where': 'OBJECTID>0',
        'outFields': '*',
        'f': 'geojson',
        'outSR': '4326',       # WGS84 para compatibilidad
        'resultOffset': 0,
        'resultRecordCount': PAGE_SIZE,
    }

    # Detectar descarga previa
    total = 0
    resuming = False

    if os.path.exists(output_file):
        try:
            with open(output_file, 'r') as f:
                content = f.read()
            if content.rstrip().endswith(']}'):
                test = json.loads(content)
                total = len(test.get('features', []))
            if total > 0:
                resuming = True
                params['resultOffset'] = total
                print(f"  Reanudando: {total} registros previos, desde offset {total}")
        except Exception:
            total = 0

    session = requests.Session()
    session.headers.update(HEADERS_IGAC)

    # Obtener cookies
    try:
        service_url = query_url.rsplit('/query', 1)[0]
        session.get(service_url, params={'f': 'json'}, timeout=30)
    except Exception:
        pass

    # Abrir archivo
    if resuming:
        f = open(output_file, 'r+')
        content = f.read()
        pos = content.rstrip().rfind(']}')
        if pos > 0:
            f.seek(pos)
            f.truncate()
        else:
            f.seek(0, 2)
    else:
        f = open(output_file, 'w')
        f.write('{"type":"FeatureCollection","features":[\n')

    try:
        while True:
            print(f"  Descargando desde registro {params['resultOffset']}...")

            try:
                response = session.get(query_url, params=params, timeout=120)
            except requests.exceptions.RequestException as e:
                print(f"  Error de conexión: {e}")
                print("  Reintentando en 30 segundos...")
                time.sleep(30)
                continue

            if response.headers.get('Content-Type', '').startswith('text/html'):
                print("  Error: WAF bloqueó la solicitud. Esperando 60s...")
                time.sleep(60)
                continue

            try:
                data = response.json()
            except json.JSONDecodeError:
                print("  Error: respuesta no es JSON válido")
                print(f"  Status: {response.status_code}")
                break

            features = data.get('features', [])
            if not features:
                break

            for feat in features:
                if total > 0:
                    f.write(',\n')
                json.dump(feat, f)
                total += 1

            f.flush()
            print(f"  -> {len(features)} registros (total: {total:,})")
            params['resultOffset'] += PAGE_SIZE
            time.sleep(2)  # Cortesía con el servidor

    except KeyboardInterrupt:
        print("\n  Descarga interrumpida por el usuario.")
    finally:
        f.write('\n]}')
        f.close()

    print(f"  Total descargado: {total:,} registros → {output_file}")


def main():
    crear_directorios()

    descargar_capa_igac('quimica')
    descargar_capa_igac('vocacion')

    print("\n" + "="*70)
    print("DESCARGA IGAC COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
