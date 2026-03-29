"""
02_extraer_chirps.py
═══════════════════════════════════════════════════════════════
Descarga precipitación mensual CHIRPS v2 para Cundinamarca (2019-2024).
Fuente: Google Earth Engine (requiere autenticación con cuenta Google).

CHIRPS tiene resolución ~5.3 km y cobertura desde 1981.
Se descarga el acumulado mensual como GeoTIFF recortado al bbox de Cundinamarca.

Salida: Un GeoTIFF por mes en raw/clima/chirps/

pip install earthengine-api geemap rasterio
ee.Authenticate()  # Ejecutar una vez para autenticarse
"""

import ee
import os
import sys
import requests
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BBOX_WGS84, YEAR_START, YEAR_END, DIRS, crear_directorios

# Alternativa sin Google Earth Engine: descarga directa desde CHC UCSB
CHIRPS_DIRECT_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"


def descargar_chirps_directo():
    """
    Descarga CHIRPS mensual directamente del servidor CHC UCSB.
    Cada archivo es un GeoTIFF global; se recorta después con rasterio.
    Si no se tiene GEE, esta es la alternativa.
    """
    crear_directorios()
    out_dir = DIRS['clima_chirps']

    for year in range(YEAR_START, YEAR_END + 1):
        for month in range(1, 13):
            filename = f"chirps-v2.0.{year}.{month:02d}.tif.gz"
            url = f"{CHIRPS_DIRECT_URL}/{filename}"
            local_gz = os.path.join(out_dir, filename)
            local_tif = os.path.join(out_dir, f"chirps_{year}_{month:02d}.tif")

            if os.path.exists(local_tif):
                print(f"  Ya existe: {local_tif}")
                continue

            print(f"  Descargando {filename}...")
            try:
                r = requests.get(url, stream=True, timeout=120)
                r.raise_for_status()
                with open(local_gz, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Descomprimir
                import gzip
                import shutil
                with gzip.open(local_gz, 'rb') as f_in:
                    with open(local_tif.replace('.tif', '_global.tif'), 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(local_gz)

                # Recortar al bbox de Cundinamarca con rasterio
                recortar_raster(
                    local_tif.replace('.tif', '_global.tif'),
                    local_tif,
                    BBOX_WGS84
                )
                os.remove(local_tif.replace('.tif', '_global.tif'))
                print(f"  -> Guardado: {local_tif}")

            except Exception as e:
                print(f"  Error descargando {filename}: {e}")
                continue


def recortar_raster(input_path, output_path, bbox):
    """Recorta un raster global al bbox [west, south, east, north]."""
    try:
        import rasterio
        from rasterio.windows import from_bounds

        with rasterio.open(input_path) as src:
            window = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], src.transform)
            data = src.read(1, window=window)
            transform = src.window_transform(window)

            profile = src.profile.copy()
            profile.update(
                width=data.shape[1],
                height=data.shape[0],
                transform=transform
            )

            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(data, 1)
    except ImportError:
        print("  AVISO: rasterio no instalado. Guardando sin recortar.")
        import shutil
        shutil.copy(input_path, output_path)


def descargar_chirps_gee():
    """
    Descarga CHIRPS mensual desde Google Earth Engine.
    Requiere: ee.Authenticate() y ee.Initialize() previos.
    """
    crear_directorios()

    try:
        ee.Initialize()
    except Exception:
        print("Autenticando con Google Earth Engine...")
        ee.Authenticate()
        ee.Initialize()

    out_dir = DIRS['clima_chirps']
    region = ee.Geometry.Rectangle(BBOX_WGS84)

    for year in range(YEAR_START, YEAR_END + 1):
        for month in range(1, 13):
            out_file = os.path.join(out_dir, f"chirps_{year}_{month:02d}.tif")
            if os.path.exists(out_file):
                print(f"  Ya existe: {out_file}")
                continue

            print(f"  Procesando CHIRPS {year}-{month:02d}...")

            # Filtrar colección CHIRPS para el mes
            start = f'{year}-{month:02d}-01'
            end_month = month + 1 if month < 12 else 1
            end_year = year if month < 12 else year + 1
            end = f'{end_year}-{end_month:02d}-01'

            chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                      .filterDate(start, end)
                      .filterBounds(region))

            # Sumar precipitación diaria → acumulado mensual
            monthly = chirps.sum().clip(region)

            # Generar URL de descarga
            url = monthly.getDownloadURL({
                'scale': 5000,  # ~5 km resolución CHIRPS
                'region': region,
                'format': 'GEO_TIFF',
                'crs': 'EPSG:4326',
            })

            # Descargar
            response = requests.get(url, timeout=300)
            with open(out_file, 'wb') as f:
                f.write(response.content)
            print(f"  -> Guardado: {out_file}")


def main():
    print("="*70)
    print("DESCARGA DE PRECIPITACIÓN CHIRPS (2019-2024)")
    print("="*70)
    print("\nOpciones:")
    print("  1. Descarga directa desde CHC UCSB (sin GEE, más lento)")
    print("  2. Descarga via Google Earth Engine (más rápido, requiere auth)")

    # Intentar GEE primero, si falla usar descarga directa
    try:
        import ee
        ee.Initialize()
        print("\nUsando Google Earth Engine...")
        descargar_chirps_gee()
    except Exception as e:
        print(f"\nGEE no disponible ({e}). Usando descarga directa...")
        descargar_chirps_directo()


if __name__ == '__main__':
    main()
