"""
05_extraer_sentinel2.py
═══════════════════════════════════════════════════════════════
Descarga índices espectrales Sentinel-2 L2A por mes.
Fuente: Copernicus Data Space (CDSE) via SentinelHub API.

7 índices: NDVI, GNDVI, EVI, NDWI, MSAVI, BSI, SAVI
Compositing: mediana mensual libre de nubes (filtro SCL)
72 meses (2020-2025) × 1 GeoTIFF de 7 bandas = 72 archivos

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

from sentinelhub import (
    SHConfig, SentinelHubRequest, SentinelHubStatistical,
    DataCollection, BBox, CRS, MimeType
)
import rasterio
from rasterio.transform import from_bounds


# ─────────────────────────────────────────────
# CONFIGURACIÓN CDSE
# ─────────────────────────────────────────────
config = SHConfig()
config.sh_client_id     = CDSE_CLIENT_ID
config.sh_client_secret = CDSE_CLIENT_SECRET
config.sh_base_url      = CDSE_BASE_URL
config.sh_token_url     = CDSE_TOKEN_URL

S2_CDSE = DataCollection.SENTINEL2_L2A.define_from(
    "SENTINEL2_L2A_CDSE",
    service_url=CDSE_BASE_URL,
)

bbox = BBox(bbox=BBOX_WGS84, crs=CRS.WGS84)

# Resolución: ~150 m para todo Cundinamarca (manejable en memoria)
# Para 10 m real se necesitaría dividir en tiles
SIZE = (1200, 1400)

# ─────────────────────────────────────────────
# EVALSCRIPT — 7 índices espectrales
# Compositing por mediana semestral (mosaicking_order + estadísticos)
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

// Filtrar nubes usando Scene Classification Layer (SCL)
function preProcessScenes(collections) {
  collections.scenes.orbits = collections.scenes.orbits.filter(function(orbit) {
    return orbit.tiles.length > 0;
  });
  return collections;
}

function evaluatePixel(samples) {
  // Acumular valores válidos (sin nubes) para calcular mediana
  var ndvi_vals = [], gndvi_vals = [], evi_vals = [];
  var ndwi_vals = [], msavi_vals = [], bsi_vals = [], savi_vals = [];

  for (var i = 0; i < samples.length; i++) {
    var s = samples[i];
    // SCL: 4=vegetation, 5=bare soil, 6=water → válidos
    // Excluir: 3=cloud shadow, 8=cloud medium, 9=cloud high, 10=thin cirrus
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


def descargar_mes(mes):
    """Descarga un composite mensual de 7 índices espectrales."""
    out_dir = DIRS['sat_sentinel2']
    out_file = os.path.join(out_dir, f"s2_indices_{mes['label']}.tif")

    if os.path.exists(out_file):
        print(f"  Ya existe: {os.path.basename(out_file)}")
        return

    print(f"  Descargando Sentinel-2 {mes['label']} "
          f"({mes['start']} → {mes['end']})...", end=' ', flush=True)

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
            bbox=bbox,
            size=SIZE,
            config=config,
        )

        data = request.get_data()
        arr = data[0]  # shape: (H, W, 7)

        if arr.ndim == 2:
            arr = arr[np.newaxis, :, :]

        height, width = arr.shape[0], arr.shape[1]
        n_bands = arr.shape[2] if arr.ndim == 3 else 1
        transform = from_bounds(
            BBOX_WGS84[0], BBOX_WGS84[1], BBOX_WGS84[2], BBOX_WGS84[3],
            width, height
        )

        with rasterio.open(
            out_file, 'w',
            driver='GTiff',
            height=height, width=width,
            count=n_bands,
            dtype='float32',
            crs='EPSG:4326',
            transform=transform,
            compress='deflate',
        ) as dst:
            for b in range(n_bands):
                band_data = arr[:, :, b] if arr.ndim == 3 else arr
                dst.write(band_data.astype(np.float32), b + 1)
                dst.update_tags(b + 1, name=BAND_NAMES[b] if b < len(BAND_NAMES) else f'band_{b+1}')

        print(f"OK ({width}×{height}, {n_bands} bandas)")

    except Exception as e:
        print(f"ERROR: {e}")


def main():
    crear_directorios()

    print("="*70)
    print("DESCARGA SENTINEL-2 ÍNDICES ESPECTRALES — COMPOSITES MENSUALES")
    print(f"Índices: {', '.join(BAND_NAMES)}")
    print(f"Compositing: mediana mensual libre de nubes (SCL filter)")
    print(f"Meses: {len(MESES)} ({MESES[0]['label']} a {MESES[-1]['label']})")
    print("="*70)

    for mes in MESES:
        descargar_mes(mes)

    print("\n" + "="*70)
    print("DESCARGA SENTINEL-2 COMPLETADA")
    print("="*70)


if __name__ == '__main__':
    main()
