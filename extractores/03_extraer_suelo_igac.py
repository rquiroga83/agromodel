"""
03_extraer_suelo_igac.py
═══════════════════════════════════════════════════════════════
Descarga datos de suelo del IGAC para Colombia.
Dos capas:
  1. Propiedades Químicas del Territorio Nacional (pH, Al, P, K, fertilidad)
  2. Vocación de Uso del Territorio Nacional (18 clases de aptitud)

Fuente: ArcGIS REST Services del IGAC (mapas.igac.gov.co)
Formato de salida: GeoJSON con reanudación automática

WAF: El firewall del IGAC bloquea patrones sospechosos. Se usan headers
realistas de navegador, delays variables y backoff progresivo en bloqueos.

Uso:
    python 03_extraer_suelo_igac.py                # Descarga ambas capas
    python 03_extraer_suelo_igac.py --step quimica  # Solo propiedades químicas
    python 03_extraer_suelo_igac.py --step vocacion # Solo vocación de uso

pip install requests
"""

import argparse
import requests
import json
import os
import sys
import time
import random

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

PAGE_SIZE = 1000  # reducido para minimizar bloqueos WAF


# Headers realistas de navegador para evadir el WAF del IGAC
HEADERS_BROWSER = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-CO,es;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://mapas.igac.gov.co/',
    'Origin': 'https://mapas.igac.gov.co',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}


def _estado_archivo(output_file):
    """
    Lee el GeoJSON de salida y devuelve el número de features ya descargadas.
    Retorna 0 si el archivo no existe o está incompleto/corrupto.
    """
    if not os.path.exists(output_file):
        return 0
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # Archivo completo: termina con ]}
        if content.rstrip().endswith(']}'):
            data = json.loads(content)
            total = len(data.get('features', []))
            if total > 0:
                return total
    except Exception:
        pass
    return 0


def descargar_capa_igac(capa_key):
    """
    Descarga una capa IGAC completa con paginación y soporte de reanudación.

    Reanudación: si ya existe un GeoJSON válido, retoma desde el último offset.
    WAF: usa headers de navegador, delays variables (2-5s) y backoff progresivo
         (60s → 120s → 300s) en caso de bloqueo.
    """
    capa = CAPAS_IGAC[capa_key]
    query_url = capa['url']
    output_file = os.path.join(DIRS[capa['dir_key']], capa['output'])

    print(f"\n{'='*70}")
    print(f"Descargando: {capa['descripcion']}")
    print(f"Fuente: {query_url}")
    print(f"Salida: {output_file}")
    print(f"{'='*70}")

    # ── Validar estado previo ──────────────────────────────────
    total_previo = _estado_archivo(output_file)

    if total_previo > 0:
        # Verificar si el archivo ya está completo consultando el total en el servidor
        print(f"  Archivo existente: {total_previo:,} registros.")
        print(f"  Verificando si la descarga está completa...")
        try:
            r = requests.get(
                query_url,
                params={'where': 'OBJECTID>0', 'returnCountOnly': 'true', 'f': 'json'},
                headers=HEADERS_BROWSER, timeout=30
            )
            count_data = r.json()
            total_server = count_data.get('count', None)
            if total_server is not None:
                print(f"  Total en servidor: {total_server:,} registros.")
                if total_previo >= total_server:
                    print(f"  Descarga completa. Saltando.")
                    return
                else:
                    print(f"  Faltan {total_server - total_previo:,} registros. Reanudando...")
            else:
                print(f"  No se pudo verificar total. Reanudando desde offset {total_previo:,}...")
        except Exception as e:
            print(f"  No se pudo verificar total ({e}). Reanudando desde offset {total_previo:,}...")

    offset = total_previo
    total = total_previo

    # ── Sesión HTTP ────────────────────────────────────────────
    session = requests.Session()
    session.headers.update(HEADERS_BROWSER)

    # Visita inicial para obtener cookies (reduce bloqueos WAF)
    try:
        service_url = query_url.rsplit('/query', 1)[0]
        session.get(service_url, params={'f': 'json'}, timeout=30)
        time.sleep(1)
    except Exception:
        pass

    # ── Abrir archivo para escritura ───────────────────────────
    if total_previo > 0:
        # Reanudar: abrir en modo r+ y posicionarse antes del cierre ]}
        fh = open(output_file, 'r+', encoding='utf-8')
        content = fh.read()
        pos = content.rstrip().rfind(']}')
        if pos > 0:
            fh.seek(pos)
            fh.truncate()
        else:
            fh.seek(0, 2)
    else:
        fh = open(output_file, 'w', encoding='utf-8')
        fh.write('{"type":"FeatureCollection","features":[\n')

    waf_backoff = 60   # segundos de espera inicial en bloqueo WAF
    waf_bloqueos = 0

    try:
        while True:
            params = {
                'where': 'OBJECTID>0',
                'outFields': '*',
                'f': 'geojson',
                'outSR': '4326',
                'resultOffset': offset,
                'resultRecordCount': PAGE_SIZE,
                'orderByFields': 'OBJECTID ASC',
            }

            print(f"  Offset {offset:,}...", end=' ', flush=True)

            try:
                response = session.get(query_url, params=params, timeout=120)
            except requests.exceptions.RequestException as e:
                print(f"\n  Error de conexión: {e}. Reintentando en 30s...")
                time.sleep(30)
                continue

            # Detectar bloqueo WAF (responde HTML en vez de JSON)
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type or response.status_code in (403, 429):
                waf_bloqueos += 1
                wait = min(waf_backoff * waf_bloqueos, 300)
                print(f"\n  WAF bloqueó la solicitud (bloqueo #{waf_bloqueos}). "
                      f"Esperando {wait}s...")
                time.sleep(wait)
                # Renovar sesión y cookies tras bloqueo
                try:
                    session = requests.Session()
                    session.headers.update(HEADERS_BROWSER)
                    session.get(service_url, params={'f': 'json'}, timeout=30)
                    time.sleep(2)
                except Exception:
                    pass
                continue

            waf_bloqueos = 0  # reset en respuesta exitosa

            try:
                data = response.json()
            except json.JSONDecodeError:
                print(f"\n  Respuesta no es JSON. Status: {response.status_code}. "
                      f"Reintentando en 30s...")
                time.sleep(30)
                continue

            if 'error' in data:
                print(f"\n  Error de la API: {data['error']}. Abortando.")
                break

            features = data.get('features', [])
            if not features:
                print(f"Sin más datos.")
                break

            for feat in features:
                if total > 0:
                    fh.write(',\n')
                json.dump(feat, fh, ensure_ascii=False)
                total += 1

            fh.flush()
            print(f"{len(features):,} registros (total: {total:,})")
            offset += PAGE_SIZE

            # Delay variable para no parecer un bot
            time.sleep(random.uniform(2.0, 4.0))

    except KeyboardInterrupt:
        print("\n  Descarga interrumpida por el usuario. El archivo puede reanudarse.")
    finally:
        fh.write('\n]}')
        fh.close()

    print(f"  Total descargado: {total:,} registros → {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Descarga capas de suelo del IGAC.'
    )
    parser.add_argument(
        '--step',
        choices=['quimica', 'vocacion'],
        default=None,
        help='Capa a descargar. Sin --step descarga ambas.'
    )
    args = parser.parse_args()

    crear_directorios()

    if args.step == 'quimica':
        descargar_capa_igac('quimica')
    elif args.step == 'vocacion':
        descargar_capa_igac('vocacion')
    else:
        descargar_capa_igac('quimica')
        descargar_capa_igac('vocacion')

    print("\n" + "="*70)
    print("DESCARGA IGAC COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
