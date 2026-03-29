"""
04_extraer_soilgrids.py
═══════════════════════════════════════════════════════════════
Descarga propiedades del suelo desde SoilGrids 2.0 (ISRIC).
Resolución 250 m, cobertura global.

Propiedades: phh2o, soc, clay, sand, silt, bdod, cec, nitrogen, ocd
Profundidades: 0-5cm, 5-15cm, 15-30cm

Fuente: REST API de ISRIC o descarga WebDAV de tiles COG (Cloud Optimized GeoTIFF)
Salida: GeoTIFF por propiedad×profundidad en raw/suelo/soilgrids/

pip install requests rasterio numpy
"""

import os
import sys
import requests
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BBOX_WGS84, DIRS, SOILGRIDS_PROPS, SOILGRIDS_DEPTHS, crear_directorios


# SoilGrids WebDAV para descarga masiva de tiles COG
SOILGRIDS_COG_BASE = "https://files.isric.org/soilgrids/latest/data"

# Mapeo de nombres de propiedades a rutas WebDAV
PROP_PATHS = {
    'phh2o':    'phh2o',
    'soc':      'soc',
    'clay':     'clay',
    'sand':     'sand',
    'silt':     'silt',
    'bdod':     'bdod',
    'cec':      'cec',
    'nitrogen': 'nitrogen',
    'ocd':      'ocd',
}

# Mapeo de profundidades a nombres de archivos
DEPTH_MAP = {
    '0-5cm':   '0-5cm_mean',
    '5-15cm':  '5-15cm_mean',
    '15-30cm': '15-30cm_mean',
}


def descargar_soilgrids_wcs():
    """
    Descarga SoilGrids via WCS (Web Coverage Service).
    Recorta al bbox de Cundinamarca durante la descarga.

    NOTA: WCS 2.0 usa SUBSET dos veces (Long y Lat). Como Python dict no permite
    claves duplicadas, se pasan los parámetros como lista de tuplas.
    """
    crear_directorios()
    out_dir = DIRS['suelo_soilgrids']

    wcs_base = "https://maps.isric.org/mapserv"

    for prop in SOILGRIDS_PROPS:
        for depth in SOILGRIDS_DEPTHS:
            depth_label = depth.replace('-', '_').replace('cm', '')
            out_file = os.path.join(out_dir, f"soilgrids_{prop}_{depth_label}cm.tif")

            if os.path.exists(out_file):
                print(f"  Ya existe: {out_file}")
                continue

            layer_name = f"{prop}_{depth}_mean"
            print(f"  Descargando {prop} @ {depth}...")

            try:
                # Lista de tuplas para permitir SUBSET duplicado (requerido por WCS 2.0)
                params = [
                    ('SERVICE', 'WCS'),
                    ('VERSION', '2.0.1'),
                    ('REQUEST', 'GetCoverage'),
                    ('COVERAGEID', layer_name),
                    ('FORMAT', 'image/tiff'),
                    ('SUBSET', f'Long({BBOX_WGS84[0]},{BBOX_WGS84[2]})'),
                    ('SUBSET', f'Lat({BBOX_WGS84[1]},{BBOX_WGS84[3]})'),
                    ('SUBSETTINGCRS', 'http://www.opengis.net/def/crs/EPSG/0/4326'),
                    ('OUTPUTCRS', 'http://www.opengis.net/def/crs/EPSG/0/4326'),
                ]
                url = f"{wcs_base}?map=/map/{prop}.map"
                response = requests.get(url, params=params, timeout=300, stream=True)

                if response.status_code == 200 and 'tiff' in response.headers.get('Content-Type', ''):
                    with open(out_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"  -> Guardado (WCS): {out_file}")
                else:
                    print(f"  Error WCS: status={response.status_code}")
                    descargar_cog_directo(prop, depth, out_file)

            except Exception as e:
                print(f"  Error WCS: {e}")
                descargar_cog_directo(prop, depth, out_file)

            time.sleep(2)


def descargar_cog_directo(prop, depth, out_file):
    """
    Descarga COG (Cloud Optimized GeoTIFF) directamente desde files.isric.org.
    El archivo es global, se recorta localmente con rasterio.

    IMPORTANTE: SoilGrids 2.0 usa proyección Homolosine (no WGS84).
    El bbox debe transformarse a la CRS nativa del dataset antes de calcular
    la ventana, de lo contrario se obtiene un recorte 0×0.
    """
    depth_label = DEPTH_MAP.get(depth, depth)
    cog_url = f"{SOILGRIDS_COG_BASE}/{prop}/{prop}_{depth_label}.vrt"

    print(f"  Intentando descarga COG: {cog_url}")
    print(f"  NOTA: Los archivos COG son globales. Puede tardar varios minutos.")

    try:
        import rasterio
        from rasterio.windows import from_bounds
        from rasterio.warp import transform_bounds

        with rasterio.open(f'/vsicurl/{cog_url}') as src:
            # SoilGrids 2.0 usa proyección Homolosine — transformar bbox a la CRS nativa
            left, bottom, right, top = transform_bounds(
                'EPSG:4326', src.crs,
                BBOX_WGS84[0], BBOX_WGS84[1],
                BBOX_WGS84[2], BBOX_WGS84[3],
            )
            window = from_bounds(left, bottom, right, top, src.transform)

            if window.width <= 0 or window.height <= 0:
                raise ValueError(
                    f"Ventana vacía tras reproyección "
                    f"({window.width:.1f}×{window.height:.1f}). "
                    f"CRS dataset: {src.crs}"
                )

            data = src.read(1, window=window)
            transform = src.window_transform(window)

            profile = src.profile.copy()
            profile.update(
                width=data.shape[1],
                height=data.shape[0],
                transform=transform,
                driver='GTiff',
                compress='deflate',
            )

            with rasterio.open(out_file, 'w', **profile) as dst:
                dst.write(data, 1)
            print(f"  -> Guardado (COG recortado): {out_file}")

    except Exception as e:
        print(f"  Error COG: {e}")
        print(f"  Descarga manual: {SOILGRIDS_COG_BASE}/{prop}/")


def descargar_soilgrids_api_puntos():
    """
    Alternativa: consultar la API REST de SoilGrids punto por punto.
    Útil si WCS/COG no funcionan. Muy lento para muchos puntos.
    """
    import json

    api_url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    out_dir = DIRS['suelo_soilgrids']

    # Generar grilla de puntos (cada 0.01° ≈ 1.1 km)
    import numpy as np
    lons = np.arange(BBOX_WGS84[0], BBOX_WGS84[2], 0.05)
    lats = np.arange(BBOX_WGS84[1], BBOX_WGS84[3], 0.05)
    total_points = len(lons) * len(lats)
    print(f"  Consultando {total_points} puntos en grilla 0.05°...")

    results = []
    count = 0
    for lon in lons:
        for lat in lats:
            params = {
                'lon': round(lon, 4),
                'lat': round(lat, 4),
                'property': SOILGRIDS_PROPS,
                'depth': SOILGRIDS_DEPTHS,
                'value': 'mean',
            }
            try:
                r = requests.get(api_url, params=params, timeout=30)
                if r.status_code == 200:
                    results.append(r.json())
                count += 1
                if count % 100 == 0:
                    print(f"  -> {count}/{total_points} puntos procesados")
                time.sleep(0.5)  # Rate limit
            except Exception:
                continue

    # Guardar resultados
    out_file = os.path.join(out_dir, 'soilgrids_puntos_cundinamarca.json')
    with open(out_file, 'w') as f:
        json.dump(results, f)
    print(f"  Guardado: {out_file} ({len(results)} puntos)")


def main():
    crear_directorios()

    print("="*70)
    print("DESCARGA DE SOILGRIDS 2.0 (ISRIC)")
    print("Propiedades: " + ", ".join(SOILGRIDS_PROPS))
    print("Profundidades: " + ", ".join(SOILGRIDS_DEPTHS))
    print("="*70)

    descargar_soilgrids_wcs()

    print("\n" + "="*70)
    print("DESCARGA SOILGRIDS COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
