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

pip install requests pandas
"""

import requests
import pandas as pd
import os
import time
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    SODA_BASE, SODA_DATASETS, DIRS, DEPT_NAME,
    DATE_START, DATE_END, HEADERS_GOV, crear_directorios
)


def descargar_soda_paginado(dataset_id, where_clause, output_path,
                            limit=50000, max_registros=None):
    """
    Descarga datos de la API SODA de datos.gov.co con paginación.
    La API SODA tiene un límite de 50.000 registros por request.
    """
    url = f"{SODA_BASE}/{dataset_id}.json"
    offset = 0
    all_data = []
    total = 0

    # Si ya existe el archivo, preguntar si continuar
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        print(f"  Archivo existente con {len(existing)} registros. Saltando...")
        return existing

    print(f"  Descargando {dataset_id}...")
    print(f"  Filtro: {where_clause}")

    while True:
        params = {
            '$where': where_clause,
            '$limit': limit,
            '$offset': offset,
            '$order': 'fechaobservacion ASC',
        }

        try:
            response = requests.get(url, params=params, headers=HEADERS_GOV, timeout=120)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Error en offset {offset}: {e}")
            print("  Esperando 30 segundos y reintentando...")
            time.sleep(30)
            continue
        except Exception as e:
            print(f"  Error inesperado: {e}")
            break

        if not data:
            print(f"  Sin más datos en offset {offset}")
            break

        all_data.extend(data)
        total += len(data)
        print(f"  -> {len(data)} registros (total acumulado: {total:,})")

        if len(data) < limit:
            break  # Última página

        if max_registros and total >= max_registros:
            print(f"  Alcanzado límite de {max_registros:,} registros")
            break

        offset += limit
        time.sleep(1)  # Cortesía con la API

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(output_path, index=False)
        print(f"  Guardado: {output_path} ({total:,} registros)")
        return df
    else:
        print(f"  No se obtuvieron datos para {dataset_id}")
        return pd.DataFrame()


def main():
    crear_directorios()

    # ── 1. TEMPERATURA ──────────────────────────────────────
    print("\n" + "="*70)
    print("1. TEMPERATURA AMBIENTE DEL AIRE (IDEAM)")
    print("="*70)
    where_temp = (
        f"departamento='{DEPT_NAME}' AND "
        f"fechaobservacion >= '{DATE_START}T00:00:00' AND "
        f"fechaobservacion <= '{DATE_END}T23:59:59'"
    )
    descargar_soda_paginado(
        SODA_DATASETS['temperatura'],
        where_temp,
        os.path.join(DIRS['clima_temp'], 'temperatura_cundinamarca_2019_2024.csv')
    )

    # ── 2. PRECIPITACIÓN ────────────────────────────────────
    # NOTA: Precipitación tiene registros cada 10 min → volumen muy grande.
    # Estrategia: descargar por año para manejar el volumen.
    print("\n" + "="*70)
    print("2. PRECIPITACIÓN (IDEAM)")
    print("="*70)
    for year in range(2019, 2025):
        print(f"\n  Año {year}:")
        where_precip = (
            f"departamento='{DEPT_NAME}' AND "
            f"fechaobservacion >= '{year}-01-01T00:00:00' AND "
            f"fechaobservacion <= '{year}-12-31T23:59:59'"
        )
        descargar_soda_paginado(
            SODA_DATASETS['precipitacion'],
            where_precip,
            os.path.join(DIRS['clima_precip'], f'precipitacion_cund_{year}.csv')
        )

    # ── 3. HUMEDAD DEL AIRE ─────────────────────────────────
    print("\n" + "="*70)
    print("3. HUMEDAD DEL AIRE (IDEAM)")
    print("="*70)
    where_hum = (
        f"departamento='{DEPT_NAME}' AND "
        f"fechaobservacion >= '{DATE_START}T00:00:00' AND "
        f"fechaobservacion <= '{DATE_END}T23:59:59'"
    )
    descargar_soda_paginado(
        SODA_DATASETS['humedad'],
        where_hum,
        os.path.join(DIRS['clima_humedad'], 'humedad_cundinamarca_2019_2024.csv')
    )

    # ── 4. NORMALES CLIMATOLÓGICAS 1961-2020 ────────────────
    # Este dataset es pequeño (una fila por estación×parámetro)
    print("\n" + "="*70)
    print("4. NORMALES CLIMATOLÓGICAS 1961-2020 (IDEAM)")
    print("="*70)
    where_norm = "1=1"  # Descargar todo (dataset pequeño)
    descargar_soda_paginado(
        SODA_DATASETS['normales'],
        where_norm,
        os.path.join(DIRS['clima_normales'], 'normales_climatologicas_colombia.csv'),
        max_registros=100000
    )

    print("\n" + "="*70)
    print("DESCARGA CLIMÁTICA COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
