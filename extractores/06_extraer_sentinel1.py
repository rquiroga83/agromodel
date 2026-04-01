"""
06_extraer_sentinel1.py
═══════════════════════════════════════════════════════════════
Descarga backscatter SAR Sentinel-1 GRD a 10 m real, por mes.
Fuente: Copernicus Data Space (CDSE) via SentinelHub API.

3 bandas: VV, VH, ratio VH/VV (dB)
Compositing: media mensual (SAR no tiene problema de nubes)
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
import threading
import numpy as np
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    CDSE_CLIENT_ID, CDSE_CLIENT_SECRET, CDSE_BASE_URL, CDSE_TOKEN_URL,
    BBOX_WGS84, MESES, DIRS, SENTINEL_TILES, crear_directorios
)

from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, BBox, CRS, MimeType
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_bounds

sh_config = SHConfig()
sh_config.sh_client_id     = CDSE_CLIENT_ID
sh_config.sh_client_secret = CDSE_CLIENT_SECRET
sh_config.sh_base_url      = CDSE_BASE_URL
sh_config.sh_token_url     = CDSE_TOKEN_URL

S1_CDSE = DataCollection.SENTINEL1_IW_ASC.define_from(
    "SENTINEL1_IW_ASC_CDSE",
    service_url=CDSE_BASE_URL,
)

EVALSCRIPT_S1 = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["VV", "VH"], orthorectify: true }],
    output: { bands: 3, sampleType: "FLOAT32" },
    mosaicking: "ORBIT"
  };
}

function evaluatePixel(samples) {
  var vv_sum = 0, vh_sum = 0, count = 0;
  for (var i = 0; i < samples.length; i++) {
    var s = samples[i];
    if (s.VV > 0 && s.VH > 0) {
      vv_sum += 10 * Math.log10(s.VV);
      vh_sum += 10 * Math.log10(s.VH);
      count++;
    }
  }
  if (count == 0) return [0, 0, 0];
  var vv_mean = vv_sum / count;
  var vh_mean = vh_sum / count;
  return [vv_mean, vh_mean, vh_mean - vv_mean];
}
"""

BAND_NAMES_S1 = ['VV_dB', 'VH_dB', 'VH_VV_ratio_dB']
N_BANDS = len(BAND_NAMES_S1)
NODATA = 0.0


def _tile_valido(path):
    """Retorna True si el tile existe y tiene contenido (>0 bytes)."""
    return os.path.exists(path) and os.path.getsize(path) > 0


def descargar_tile(tile, mes, tile_dir):
    """Descarga un tile individual para un mes. Retorna ruta si exitoso, None si falla."""
    tile_file = os.path.join(tile_dir, f"tile_{tile['label']}.tif")

    if _tile_valido(tile_file):
        return tile_file

    t_bbox = BBox(bbox=tile['bbox'], crs=CRS.WGS84)
    w_px, h_px = tile['size']

    try:
        request = SentinelHubRequest(
            evalscript=EVALSCRIPT_S1,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=S1_CDSE,
                    time_interval=(mes['start'], mes['end']),
                )
            ],
            responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
            bbox=t_bbox,
            size=(w_px, h_px),
            config=sh_config,
        )

        data = request.get_data()
        arr = data[0].astype(np.float32)

        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]

        height, width = arr.shape[0], arr.shape[1]
        n_bands = arr.shape[2]
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
                dst.write(arr[:, :, b], b + 1)

        return tile_file

    except Exception as e:
        print(f"\n    ERROR tile {tile['label']}: {e}")
        return None


def merge_tiles(tile_dir, out_file):
    """Fusiona todos los tiles de un mes en un único GeoTIFF."""
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
            BIGTIFF='YES',
        )

        with rasterio.open(out_file, 'w', **profile) as dst:
            dst.write(mosaic)
            for b in range(min(mosaic.shape[0], len(BAND_NAMES_S1))):
                dst.update_tags(b + 1, name=BAND_NAMES_S1[b])

        return True
    finally:
        for ds in src_datasets:
            ds.close()


def descargar_mes(mes, tiles, workers=5):
    """Descarga todos los tiles de un mes en paralelo y los fusiona."""
    out_dir = DIRS['sat_sentinel1']
    out_file = os.path.join(out_dir, f"s1_backscatter_{mes['label']}.tif")

    if os.path.exists(out_file):
        print(f"  [{mes['label']}] Ya existe. Saltando.")
        return

    tile_dir = os.path.join(out_dir, f"_tiles_{mes['label']}")
    os.makedirs(tile_dir, exist_ok=True)

    # Tiles pendientes: faltantes o con 0 bytes (descarga interrumpida)
    pendientes = [t for t in tiles
                  if not _tile_valido(os.path.join(tile_dir, f"tile_{t['label']}.tif"))]
    existentes = len(tiles) - len(pendientes)

    if not pendientes:
        print(f"  [{mes['label']}] Todos los tiles ya existen -> merge...", end='', flush=True)
    else:
        print(f"  [{mes['label']}] {existentes}/{len(tiles)} existentes, "
              f"descargando {len(pendientes)} con {workers} workers...", end='', flush=True)

    lock = threading.Lock()
    ok_count = [existentes]
    fail_count = [0]

    def _descargar(tile):
        result = descargar_tile(tile, mes, tile_dir)
        with lock:
            if result:
                ok_count[0] += 1
            else:
                fail_count[0] += 1
            done = ok_count[0] + fail_count[0]
            if done % 10 == 0:
                print(f" {ok_count[0]}/{len(tiles)}", end='', flush=True)
        return result

    if pendientes:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(_descargar, pendientes))

    print(f" -> {ok_count[0]}/{len(tiles)} tiles", end='', flush=True)

    if fail_count[0] > 0:
        print(f" ({fail_count[0]} fallidos)")
        print(f"    Tiles guardados en {tile_dir}. Reejecutar para reintentar.")
        return

    print(" -> merge...", end='', flush=True)
    if merge_tiles(tile_dir, out_file):
        size_mb = os.path.getsize(out_file) / (1024 * 1024)
        print(f" OK ({size_mb:.0f} MB)")
    else:
        print(" ERROR en merge")


def main():
    parser = argparse.ArgumentParser(
        description='Descarga Sentinel-1 backscatter SAR a 10 m real (mensual).'
    )
    parser.add_argument(
        '--mes', type=str, default=None,
        help='Mes específico a descargar (formato: YYYY_MM, ej: 2020_01)'
    )
    parser.add_argument(
        '--workers', type=int, default=5,
        help='Número de tiles en paralelo por mes (default: 5, max recomendado: 10)'
    )
    args = parser.parse_args()

    crear_directorios()

    tiles = SENTINEL_TILES
    print("=" * 70)
    print("DESCARGA SENTINEL-1 BACKSCATTER SAR — 10 m REAL (TILES)")
    print(f"Bandas: {', '.join(BAND_NAMES_S1)}")
    print(f"Tiles por mes: {len(tiles)}  |  Workers: {args.workers}")
    if args.mes:
        meses = [m for m in MESES if m['label'] == args.mes]
        if not meses:
            print(f"Mes '{args.mes}' no encontrado. Opciones: {MESES[0]['label']} a {MESES[-1]['label']}")
            return
        print(f"Mes seleccionado: {args.mes}")
    else:
        meses = MESES
        print(f"Meses: {len(meses)} ({meses[0]['label']} a {meses[-1]['label']})")
    t_tile = 4.0
    t_total = (len(meses) * len(tiles) * t_tile) / args.workers / 60
    print(f"Tiempo estimado: ~{t_total:.0f} min")
    print("=" * 70)

    for mes in meses:
        descargar_mes(mes, tiles, workers=args.workers)

    print("\n" + "=" * 70)
    print("DESCARGA SENTINEL-1 COMPLETADA")
    print("=" * 70)


if __name__ == '__main__':
    main()
