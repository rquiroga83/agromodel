"""
07_extraer_dem_topografia.py
═══════════════════════════════════════════════════════════════
Variables topográficas desde Copernicus DEM GLO-30 (CDSE).
Calcula: Elevación, Pendiente (%), Aspecto (°), Curvatura, TWI.

Adaptado del script copernicus_dem_terrain.py del usuario.
Guardado en raw/topo/dem_glo30/

pip install sentinelhub rasterio numpy scipy pysheds
"""

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS as RioCRS
from scipy.ndimage import convolve
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    CDSE_CLIENT_ID, CDSE_CLIENT_SECRET, CDSE_BASE_URL, CDSE_TOKEN_URL,
    BBOX_WGS84, DIRS, crear_directorios
)

from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, BBox, CRS, MimeType

config = SHConfig()
config.sh_client_id     = CDSE_CLIENT_ID
config.sh_client_secret = CDSE_CLIENT_SECRET
config.sh_base_url      = CDSE_BASE_URL
config.sh_token_url     = CDSE_TOKEN_URL

DEM_CDSE = DataCollection.DEM_COPERNICUS_30.define_from(
    "DEM_COPERNICUS_30_CDSE", service_url=CDSE_BASE_URL,
)

bbox = BBox(bbox=BBOX_WGS84, crs=CRS.WGS84)
SIZE = (1200, 1500)

EVALSCRIPT_DEM = """
//VERSION=3
function setup() {
  return { input: ["DEM"], output: { bands: 1, sampleType: "FLOAT32" } };
}
function evaluatePixel(s) { return [s.DEM]; }
"""


def descargar_dem(dem_path):
    print("Descargando Copernicus DEM GLO-30 desde CDSE...")
    req = SentinelHubRequest(
        evalscript=EVALSCRIPT_DEM,
        input_data=[SentinelHubRequest.input_data(data_collection=DEM_CDSE)],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=bbox, size=SIZE, config=config,
    )
    arr = req.get_data()[0]
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    arr = arr.astype(np.float32)

    width, height = SIZE
    transform = from_bounds(*BBOX_WGS84, width, height)
    with rasterio.open(
        dem_path, 'w', driver='GTiff',
        height=height, width=width, count=1, dtype='float32',
        crs=RioCRS.from_epsg(4326), transform=transform,
    ) as dst:
        dst.write(arr, 1)
    print(f"  DEM guardado: {dem_path} ({width}×{height})")
    return arr, transform


def gradientes_horn(dem, res_x, res_y):
    kx = np.array([[-1,0,1],[-2,0,2],[-1,0,1]], np.float32) / (8*res_x)
    ky = np.array([[1,2,1],[0,0,0],[-1,-2,-1]], np.float32) / (8*res_y)
    return convolve(dem, kx, mode='nearest'), convolve(dem, ky, mode='nearest')


def calcular_pendiente(dzdx, dzdy):
    return np.sqrt(dzdx**2 + dzdy**2) * 100.0


def calcular_aspecto(dzdx, dzdy):
    asp = np.degrees(np.arctan2(dzdy, -dzdx))
    asp = (asp + 360) % 360
    asp[(dzdx == 0) & (dzdy == 0)] = -1.0
    return asp


def calcular_curvatura(dem, res_x, res_y):
    d2x = convolve(dem, np.array([[0,0,0],[1,-2,1],[0,0,0]], np.float32)/res_x**2, mode='nearest')
    d2y = convolve(dem, np.array([[0,1,0],[0,-2,0],[0,1,0]], np.float32)/res_y**2, mode='nearest')
    return d2x + d2y


def calcular_twi(dem_path):
    print("  Calculando TWI (acumulación de flujo D8)...")
    try:
        # np.in1d fue eliminado en NumPy 2.0; pysheds aún lo usa → monkey-patch
        if not hasattr(np, 'in1d'):
            np.in1d = np.isin
        from pysheds.grid import Grid
        grid = Grid.from_raster(dem_path)
        dem_g = grid.read_raster(dem_path)
        pit_filled = grid.fill_pits(dem_g)
        flooded = grid.fill_depressions(pit_filled)
        inflated = grid.resolve_flats(flooded)
        fdir = grid.flowdir(inflated)
        acc = grid.accumulation(fdir).astype(np.float32)

        cellsize_m = abs(grid.affine.a) * 111_320
        area_m2 = (acc + 1) * cellsize_m**2
        slope_deg = grid.cell_slopes(inflated, fdir)
        slope_rad = np.radians(np.clip(slope_deg, 0.01, 89.99))
        twi = np.log(area_m2 / np.tan(slope_rad)).astype(np.float32)
        return twi
    except ImportError:
        print("  AVISO: pysheds no instalado. TWI será zeros.")
        return None


def main():
    crear_directorios()
    out_dir = DIRS['topo_dem']
    dem_path = os.path.join(out_dir, 'dem_cundinamarca.tif')
    out_path = os.path.join(out_dir, 'cundinamarca_topografia.tif')

    if os.path.exists(out_path):
        print(f"Ya existe: {out_path}")
        return

    print("="*70)
    print("VARIABLES TOPOGRÁFICAS — COPERNICUS DEM GLO-30")
    print("="*70)

    elevacion, transform = descargar_dem(dem_path)

    with rasterio.open(dem_path) as src:
        elevacion = src.read(1).astype(np.float32)
        perfil = src.profile
        res_x = abs(src.transform.a)
        res_y = abs(src.transform.e)

    lat_media = (BBOX_WGS84[1] + BBOX_WGS84[3]) / 2
    res_x_m = res_x * 111_320 * np.cos(np.radians(lat_media))
    res_y_m = res_y * 111_320

    print("Calculando derivadas topográficas...")
    dzdx, dzdy = gradientes_horn(elevacion, res_x_m, res_y_m)
    pendiente = calcular_pendiente(dzdx, dzdy)
    aspecto = calcular_aspecto(dzdx, dzdy)
    curvatura = calcular_curvatura(elevacion, res_x_m, res_y_m)
    twi = calcular_twi(dem_path)

    if twi is None:
        twi = np.zeros_like(elevacion)

    # Guardar GeoTIFF multibanda
    capas = [elevacion, pendiente, aspecto, curvatura, twi]
    nombres = ['Elevacion_m', 'Pendiente_pct', 'Aspecto_deg', 'Curvatura', 'TWI']

    perfil.update(count=5, dtype='float32', driver='GTiff', compress='deflate')
    with rasterio.open(out_path, 'w', **perfil) as dst:
        for i, (arr, nom) in enumerate(zip(capas, nombres), 1):
            dst.write(arr.astype(np.float32), i)
            dst.update_tags(i, name=nom)

    os.remove(dem_path)
    print(f"\nGuardado: {out_path}")
    print("Bandas: 1=Elevación, 2=Pendiente, 3=Aspecto, 4=Curvatura, 5=TWI")


if __name__ == '__main__':
    main()
