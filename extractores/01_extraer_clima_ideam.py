"""
01_extraer_clima_ideam.py
═══════════════════════════════════════════════════════════════
Descarga datos climáticos del IDEAM para Cundinamarca (2019-2024).
Tres variables: Temperatura, Precipitación, Humedad del Aire.
Fuente: APIs SODA en datos.gov.co

Los datos son registros horarios (temp, humedad) o cada 10 min (precipitación)
de estaciones automáticas. Cada registro tiene:
  CodigoEstacion, FechaObservacion, ValorObservado, Latitud, Longitud, Municipio

Salida: CSV por variable en raw/clima/ideam_*/

Uso:
    python 01_extraer_clima_ideam.py                  # Ejecuta los 4 pasos
    python 01_extraer_clima_ideam.py --step temp      # Solo temperatura
    python 01_extraer_clima_ideam.py --step precip    # Solo precipitación
    python 01_extraer_clima_ideam.py --step humedad   # Solo humedad
    python 01_extraer_clima_ideam.py --step normales  # Solo normales
    python 01_extraer_clima_ideam.py --step precip --year 2021          # Un año específico
    python 01_extraer_clima_ideam.py --step precip --year 2021 --mes 6  # Un mes específico

pip install requests pandas
"""

import argparse
import requests
import pandas as pd
import os
import time
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    SODA_BASE, SODA_DATASETS, DIRS, DEPT_NAME,
    DATE_START, DATE_END, YEAR_START, YEAR_END, HEADERS_GOV, crear_directorios
)


def descargar_soda_paginado(dataset_id, where_clause, output_path,
                            limit=50000, max_registros=None, timeout_sec=180,
                            max_retries=5, order_field='fechaobservacion ASC'):
    """
    Descarga datos de la API SODA de datos.gov.co con paginación.
    La API SODA tiene un límite de 50.000 registros por request.

    Parámetros:
        timeout_sec  : segundos de espera por request (default 180)
        max_retries  : intentos antes de abandonar una página (default 5)
        order_field  : campo para ordenar resultados. Pasar None si el dataset
                       no tiene esa columna (ej. normales climatológicas).
    """
    url = f"{SODA_BASE}/{dataset_id}.json"
    offset = 0
    all_data = []
    total = 0

    # Si ya existe el archivo, saltarlo (idempotente)
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        print(f"  Archivo existente con {len(existing):,} registros. Saltando...")
        return existing

    print(f"  Descargando {dataset_id}...")
    print(f"  Filtro: {where_clause}")

    while True:
        params = {
            '$where': where_clause,
            '$limit': limit,
            '$offset': offset,
        }
        if order_field:
            params['$order'] = order_field

        retries = 0
        while retries < max_retries:
            try:
                response = requests.get(
                    url, params=params, headers=HEADERS_GOV, timeout=timeout_sec
                )
                response.raise_for_status()
                data = response.json()
                break  # éxito
            except requests.exceptions.Timeout:
                retries += 1
                wait = 30 * retries
                print(f"  TIMEOUT en offset {offset} (intento {retries}/{max_retries}). "
                      f"Esperando {wait}s...")
                time.sleep(wait)
            except requests.exceptions.RequestException as e:
                retries += 1
                wait = 30 * retries
                print(f"  Error HTTP en offset {offset}: {e} (intento {retries}/{max_retries}). "
                      f"Esperando {wait}s...")
                time.sleep(wait)
            except Exception as e:
                print(f"  Error inesperado: {e}")
                retries = max_retries  # salir del loop de retries
                data = None
                break
        else:
            print(f"  Máximo de reintentos alcanzado en offset {offset}. Guardando lo descargado hasta ahora.")
            data = None

        if data is None:
            break

        if not data:
            print(f"  Sin más datos en offset {offset}")
            break

        all_data.extend(data)
        total += len(data)
        print(f"  -> {len(data):,} registros (total acumulado: {total:,})")

        if len(data) < limit:
            break  # Última página

        if max_registros and total >= max_registros:
            print(f"  Alcanzado límite de {max_registros:,} registros")
            break

        offset += limit
        time.sleep(2)  # Cortesía con la API

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(output_path, index=False)
        print(f"  Guardado: {output_path} ({total:,} registros)")
        return df
    else:
        print(f"  No se obtuvieron datos para {dataset_id}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════
# PASOS INDIVIDUALES
# ══════════════════════════════════════════════════════════════════

def paso_temperatura():
    """Descarga temperatura ambiente (registros horarios)."""
    print("\n" + "="*70)
    print("1. TEMPERATURA AMBIENTE DEL AIRE (IDEAM)")
    print("="*70)
    where = (
        f"departamento='{DEPT_NAME}' AND "
        f"fechaobservacion >= '{DATE_START}T00:00:00' AND "
        f"fechaobservacion <= '{DATE_END}T23:59:59'"
    )
    descargar_soda_paginado(
        SODA_DATASETS['temperatura'],
        where,
        os.path.join(DIRS['clima_temp'], f'temperatura_cundinamarca_{YEAR_START}_{YEAR_END}.csv'),
        timeout_sec=180,
    )


def paso_precipitacion(solo_year=None, solo_mes=None):
    """
    Descarga precipitación (registros cada 10 min → volumen muy grande).

    Estrategia: descargar por MES para evitar timeouts y permitir reanudar
    desde el mes exacto donde falló.

    Args:
        solo_year : si se indica, descarga solo ese año (ej. 2021)
        solo_mes  : si se indica junto con solo_year, descarga solo ese mes (1-12)
    """
    print("\n" + "="*70)
    print("2. PRECIPITACIÓN (IDEAM) — descarga mensual")
    print("   NOTA: registros cada 10 min → ~144 obs/estación/día")
    print("="*70)

    # Determinar rango de años/meses a descargar
    years = [solo_year] if solo_year else range(YEAR_START, YEAR_END + 1)

    for year in years:
        meses = [solo_mes] if solo_mes else range(1, 13)
        for mes in meses:
            import calendar
            ultimo_dia = calendar.monthrange(year, mes)[1]
            mes_str = f"{mes:02d}"
            nombre_archivo = f"precipitacion_cund_{year}_{mes_str}.csv"
            output_path = os.path.join(DIRS['clima_precip'], nombre_archivo)

            print(f"\n  Año {year} — Mes {mes_str}:")
            where = (
                f"departamento='{DEPT_NAME}' AND "
                f"fechaobservacion >= '{year}-{mes_str}-01T00:00:00' AND "
                f"fechaobservacion <= '{year}-{mes_str}-{ultimo_dia:02d}T23:59:59'"
            )
            descargar_soda_paginado(
                SODA_DATASETS['precipitacion'],
                where,
                output_path,
                timeout_sec=240,  # más tiempo para precipitación (más datos)
                max_retries=5,
            )


def paso_humedad():
    """Descarga humedad del aire (registros horarios)."""
    print("\n" + "="*70)
    print("3. HUMEDAD DEL AIRE (IDEAM)")
    print("="*70)
    where = (
        f"departamento='{DEPT_NAME}' AND "
        f"fechaobservacion >= '{DATE_START}T00:00:00' AND "
        f"fechaobservacion <= '{DATE_END}T23:59:59'"
    )
    descargar_soda_paginado(
        SODA_DATASETS['humedad'],
        where,
        os.path.join(DIRS['clima_humedad'], f'humedad_cundinamarca_{YEAR_START}_{YEAR_END}.csv'),
        timeout_sec=180,
    )


def paso_normales():
    """Descarga normales climatológicas 1961-2020 (dataset pequeño)."""
    print("\n" + "="*70)
    print("4. NORMALES CLIMATOLÓGICAS 1961-2020 (IDEAM)")
    print("="*70)
    descargar_soda_paginado(
        SODA_DATASETS['normales'],
        "1=1",
        os.path.join(DIRS['clima_normales'], 'normales_climatologicas_colombia.csv'),
        max_registros=100000,
        timeout_sec=120,
        order_field=None,  # dataset estático, no tiene columna fechaobservacion
    )


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Descarga datos climáticos IDEAM para Cundinamarca.'
    )
    parser.add_argument(
        '--step',
        choices=['temp', 'precip', 'humedad', 'normales'],
        default=None,
        help='Paso a ejecutar. Sin --step ejecuta los 4 pasos.'
    )
    parser.add_argument(
        '--year',
        type=int,
        default=None,
        help='Solo para --step precip: descargar un año específico (ej. 2021)'
    )
    parser.add_argument(
        '--mes',
        type=int,
        default=None,
        help='Solo para --step precip + --year: descargar un mes específico (1-12)'
    )
    args = parser.parse_args()

    crear_directorios()

    # Validación
    if args.mes and not args.year:
        parser.error("--mes requiere --year")
    if (args.year or args.mes) and args.step != 'precip':
        parser.error("--year y --mes solo aplican con --step precip")

    if args.step == 'temp':
        paso_temperatura()
    elif args.step == 'precip':
        paso_precipitacion(solo_year=args.year, solo_mes=args.mes)
    elif args.step == 'humedad':
        paso_humedad()
    elif args.step == 'normales':
        paso_normales()
    else:
        # Ejecutar todos los pasos
        paso_temperatura()
        paso_precipitacion()
        paso_humedad()
        paso_normales()

    print("\n" + "="*70)
    print("DESCARGA CLIMÁTICA COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
