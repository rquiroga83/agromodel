"""
05_extraer_sentinel2.py
═══════════════════════════════════════════════════════════════
Descarga índices espectrales Sentinel-2 L2A a 10 m real, por mes.
Fuente: Copernicus Data Space (CDSE) via SentinelHub API.

7 índices: NDVI, GNDVI, EVI, NDWI, MSAVI, BSI, SAVI
Compositing: mediana mensual libre de nubes (filtro SCL)
Estrategia: descarga por tiles (~80 tiles × 72 meses), merge por mes.

Reanudación automática:
  - Si el GeoTIFF final del mes existe → salta el mes entero
  - Si solo faltan tiles → descarga los faltantes y hace merge

pip install sentinelhub numpy rasterio
"""

import argparse
import os
import sys
import time
import random
import shutil
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    CDSE_CLIENT_ID, CDSE_CLIENT_SECRET, CDSE_BASE_URL, CDSE_TOKEN_URL,
    BBOX_WGS84, MESES, DIRS, SENTINEL_TILES, crear_directorios
)

from sentinelhub import (
    SHConfig, SentinelHubRequest,
    DataCollection, BBox, CRS, MimeType
)
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_bounds


# ─────────────────────────────────────────────
# CONFIGURACIÓN CDSE
# ─────────────────────────────────────────────
sh_config = SHConfig()
sh_config.sh_client_id     = CDSE_CLIENT_ID
sh_config.sh_client_secret = CDSE_CLIENT_SECRET
sh_config.sh_base_url      = CDSE_BASE_URL
sh_config.sh_token_url     = CDSE_TOKEN_URL

S2_CDSE = DataCollection.SENTINEL2_L2A.define_from(
    "SENTINEL2_L2A_CDSE",
    service_url=CDSE_BASE_URL,
)

# ─────────────────────────────────────────────
# EVALSCRIPT — 7 índices espectrales
# Mediana mensual libre de nubes (filtro SCL)
# ─────────────────────────────────────────────
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input:  [{ bands: ["B02", "B03", "B04", "B08", "B11", "SCL", "dataMask"] }],
    output: { bands: 7, sampleType: "FLOAT32" },
    mosaicking: "ORBIT"
  };
}

function preProcessScenes(collections) {
  collections.scenes.orbits = collections.scenes.orbits.filter(function(orbit) {
    return orbit.tiles.length > 0;
  });
  return collections;
}

function evaluatePixel(samples) {
  var ndvi_vals = [], gndvi_vals = [], evi_vals = [];
  var ndwi_vals = [], msavi_vals = [], bsi_vals = [], savi_vals = [];

  for (var i = 0; i < samples.length; i++) {
    var s = samples[i];
    if (s.dataMask == 0) continue;
    var scl = s.SCL;
    if (scl == 3 || scl == 8 || scl == 9 || scl == 10) continue;

    var B2=s.B02, B3=s.B03, B4=s.B04, B8=s.B08, B11=s.B11;
    var eps = 1e-10;

    ndvi_vals.push((B8-B4)/(B8+B4+eps));
    gndvi_vals.push((B8-B3)/(B8+B3+eps));
    evi_vals.push(2.5*(B8-B4)/(B8+6*B4-7.5*B2+1+eps));
    ndwi_vals.push((B3-B8)/(B3+B8+eps));
    msavi_vals.push((2*B8+1-Math.sqrt(Math.pow(2*B8+1,2)-8*(B8-B4)))/2);
    bsi_vals.push(((B11+B4)-(B8+B2))/((B11+B4)+(B8+B2)+eps));
    savi_vals.push(((B8-B4)/(B8+B4+0.5+eps))*1.5);
  }

  function median(arr) {
    if (arr.length == 0) return 0;
    arr.sort(function(a,b){return a-b;});
    var mid = Math.floor(arr.length/2);
    return arr.length % 2 ? arr[mid] : (arr[mid-1]+arr[mid])/2;
  }

  return [
    median(ndvi_vals),
    median(gndvi_vals),
    median(evi_vals),
    median(ndwi_vals),
    median(msavi_vals),
    median(bsi_vals),
    median(savi_vals)
  ];
}
"""

BAND_NAMES = ['NDVI', 'GNDVI', 'EVI', 'NDWI', 'MSAVI', 'BSI', 'SAVI']
N_BANDS = len(BAND_NAMES)
NODATA = 0.0


def descargar_tile(tile, mes, tile_dir):
    """
    Descarga un tile individual para un mes.
    Retorna la ruta del archivo si exitoso, None si falla.
    """
    tile_file = os.path.join(tile_dir, f"tile_{tile['label']}.tif")

    if os.path.exists(tile_file):
        return tile_file

    t_bbox = BBox(bbox=tile['bbox'], crs=CRS.WGS84)
    w_px, h_px = tile['size']

    try:
        request = SentinelHubRequest(
            evalscript=EVALSCRIPT,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=S2_CDSE,
                    time_interval=(mes['start'], mes['end']),
                )
            ],
            responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
            bbox=t_bbox,
            size=(w_px, h_px),
            config=sh_config,
        )

        data = request.get_data()
        arr = data[0]  # (H, W, 7)

        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]

        height, width = arr.shape[0], arr.shape[1]
        n_bands = arr.shape[2] if arr.ndim == 3 else 1
        transform = from_bounds(
            tile['bbox'][0], tile['bbox'][1],
            tile['bbox'][2], tile['bbox'][3],
            width, height
        )

        with rasterio.open(
            tile_file, 'w', driver='GTiff',
            height=height, width=width,
            count=n_bands, dtype='float32',
            crs='EPSG:4326', transform=transform,
            compress='deflate', nodata=NODATA,
        ) as dst:
            for b in range(n_bands):
                band_data = arr[:, :, b] if arr.ndim == 3 else arr
                dst.write(band_data.astype(np.float32), b + 1)

        return tile_file

    except Exception as e:
        print(f"\n    ERROR tile {tile['label']}: {e}")
        return None


def merge_tiles(tile_dir, out_file, n_bands=N_BANDS):
    """
    Fusiona todos los tiles de un mes en un único GeoTIFF.
    """
    tile_files = sorted([
        os.path.join(tile_dir, f)
        for f in os.listdir(tile_dir)
        if f.startswith('tile_') and f.endswith('.tif')
    ])

    if not tile_files:
        print("\n    Sin tiles para merge.")
        return False

    src_datasets = [rasterio.open(f) for f in tile_files]
    try:
        mosaic, mosaic_transform = merge(src_datasets, nodata=NODATA)

        profile = src_datasets[0].profile.copy()
        profile.update(
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=mosaic_transform,
            count=mosaic.shape[0],
            compress='deflate',
            nodata=NODATA,
        )

        with rasterio.open(out_file, 'w', **profile) as dst:
            dst.write(mosaic)
            for b in range(min(mosaic.shape[0], len(BAND_NAMES))):
                dst.update_tags(b + 1, name=BAND_NAMES[b])

        return True
    finally:
        for ds in src_datasets:
            ds.close()


def descargar_mes(mes, tiles):
    """Descarga todos los tiles de un mes y los fusiona."""
    out_dir = DIRS['sat_sentinel2']
    out_file = os.path.join(out_dir, f"s2_indices_{mes['label']}.tif")

    if os.path.exists(out_file):
        print(f"  [{mes['label']}] Ya existe. Saltando.")
        return

    tile_dir = os.path.join(out_dir, f"_tiles_{mes['label']}")
    os.makedirs(tile_dir, exist_ok=True)

    # Contar tiles ya descargados
    existentes = sum(1 for t in tiles
                     if os.path.exists(os.path.join(tile_dir, f"tile_{t['label']}.tif")))

    print(f"  [{mes['label']}] {existentes}/{len(tiles)} tiles...", end='', flush=True)

    ok_count = existentes
    fail_count = 0

    for i, tile in enumerate(tiles):
        tile_file = os.path.join(tile_dir, f"tile_{tile['label']}.tif")
        if os.path.exists(tile_file):
            continue

        result = descargar_tile(tile, mes, tile_dir)
        if result:
            ok_count += 1
        else:
            fail_count += 1

        # Progreso cada 10 tiles
        if (i + 1) % 10 == 0:
            print(f" {ok_count}/{len(tiles)}", end='', flush=True)

        # Delay entre requests para no saturar la API
        time.sleep(random.uniform(0.5, 1.5))

    print(f" → {ok_count}/{len(tiles)} tiles", end='', flush=True)

    if fail_count > 0:
        print(f" ({fail_count} fallidos)")
        print(f"    Tiles guardados en {tile_dir}. Reejecutar para reintentar.")
        return

    # Merge
    print(" → merge...", end='', flush=True)
    if merge_tiles(tile_dir, out_file):
        # Limpiar tiles individuales
        shutil.rmtree(tile_dir, ignore_errors=True)
        size_mb = os.path.getsize(out_file) / (1024 * 1024)
        print(f" OK ({size_mb:.0f} MB)")
    else:
        print(" ERROR en merge")


def main():
    parser = argparse.ArgumentParser(
        description='Descarga Sentinel-2 índices espectrales a 10 m real (mensual).'
    )
    parser.add_argument(
        '--mes', type=str, default=None,
        help='Mes específico a descargar (formato: YYYY_MM, ej: 2020_01)'
    )
    args = parser.parse_args()

    crear_directorios()

    tiles = SENTINEL_TILES
    print("=" * 70)
    print("DESCARGA SENTINEL-2 ÍNDICES ESPECTRALES — 10 m REAL (TILES)")
    print(f"Índices: {', '.join(BAND_NAMES)}")
    print(f"Tiles por mes: {len(tiles)}")
    if args.mes:
        meses = [m for m in MESES if m['label'] == args.mes]
        if not meses:
            print(f"Mes '{args.mes}' no encontrado. Opciones: {MESES[0]['label']} a {MESES[-1]['label']}")
            return
        print(f"Mes seleccionado: {args.mes}")
    else:
        meses = MESES
        print(f"Meses: {len(meses)} ({meses[0]['label']} a {meses[-1]['label']})")
    print(f"Total requests estimados: {len(meses) * len(tiles):,}")
    print("=" * 70)

    for mes in meses:
        descargar_mes(mes, tiles)

    print("\n" + "=" * 70)
    print("DESCARGA SENTINEL-2 COMPLETADA")
    print("=" * 70)


if __name__ == '__main__':
    main()
