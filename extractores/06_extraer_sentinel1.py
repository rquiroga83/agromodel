"""
06_extraer_sentinel1.py
═══════════════════════════════════════════════════════════════
Descarga backscatter SAR Sentinel-1 GRD por mes.
Fuente: Copernicus Data Space (CDSE) via SentinelHub API.

3 bandas: VV, VH, ratio VH/VV (dB)
Compositing: media mensual (SAR no tiene problema de nubes)
72 meses (2020-2025) × 1 GeoTIFF de 3 bandas = 72 archivos

Reanudación automática: saltea archivos ya descargados.

pip install sentinelhub numpy rasterio
"""

import os
import sys
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    CDSE_CLIENT_ID, CDSE_CLIENT_SECRET, CDSE_BASE_URL, CDSE_TOKEN_URL,
    BBOX_WGS84, MESES, DIRS, crear_directorios
)

from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, BBox, CRS, MimeType
import rasterio
from rasterio.transform import from_bounds

config = SHConfig()
config.sh_client_id     = CDSE_CLIENT_ID
config.sh_client_secret = CDSE_CLIENT_SECRET
config.sh_base_url      = CDSE_BASE_URL
config.sh_token_url     = CDSE_TOKEN_URL

S1_CDSE = DataCollection.SENTINEL1_IW_ASC.define_from(
    "SENTINEL1_IW_ASC_CDSE",
    service_url=CDSE_BASE_URL,
)

bbox = BBox(bbox=BBOX_WGS84, crs=CRS.WGS84)
SIZE = (1200, 1400)

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


def descargar_mes_s1(mes):
    out_dir = DIRS['sat_sentinel1']
    out_file = os.path.join(out_dir, f"s1_backscatter_{mes['label']}.tif")

    if os.path.exists(out_file):
        print(f"  Ya existe: {os.path.basename(out_file)}")
        return

    print(f"  Descargando Sentinel-1 {mes['label']} "
          f"({mes['start']} → {mes['end']})...", end=' ', flush=True)

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
            bbox=bbox,
            size=SIZE,
            config=config,
        )

        data = request.get_data()
        arr = data[0].astype(np.float32)

        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]

        height, width = arr.shape[0], arr.shape[1]
        n_bands = arr.shape[2]
        transform = from_bounds(
            BBOX_WGS84[0], BBOX_WGS84[1], BBOX_WGS84[2], BBOX_WGS84[3],
            width, height
        )

        with rasterio.open(
            out_file, 'w', driver='GTiff',
            height=height, width=width, count=n_bands,
            dtype='float32', crs='EPSG:4326',
            transform=transform, compress='deflate',
        ) as dst:
            for b in range(n_bands):
                dst.write(arr[:, :, b], b + 1)
                dst.update_tags(b + 1, name=BAND_NAMES_S1[b])

        print(f"OK ({width}×{height}, {n_bands} bandas)")
    except Exception as e:
        print(f"ERROR: {e}")


def main():
    crear_directorios()
    print("="*70)
    print("DESCARGA SENTINEL-1 BACKSCATTER SAR — COMPOSITES MENSUALES")
    print(f"Bandas: {', '.join(BAND_NAMES_S1)}")
    print(f"Meses: {len(MESES)} ({MESES[0]['label']} a {MESES[-1]['label']})")
    print("="*70)

    for mes in MESES:
        descargar_mes_s1(mes)

    print("\nDESCARGA SENTINEL-1 COMPLETADA")


if __name__ == '__main__':
    main()
