"""Operaciones espaciales: filtrado por poligono y conversion CRS."""
from typing import List, Tuple
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Polygon, Point

from api.config import TARGET_CRS, WGS84


_to_3116 = Transformer.from_crs(WGS84, TARGET_CRS, always_xy=True)
_to_wgs = Transformer.from_crs(TARGET_CRS, WGS84, always_xy=True)


def wgs_polygon_to_3116(coords_wgs84: List[List[List[float]]]) -> Polygon:
    """Convierte coordenadas GeoJSON [lon,lat] a poligono shapely en EPSG:3116."""
    if not coords_wgs84 or not coords_wgs84[0]:
        raise ValueError("Poligono vacio")
    ring = coords_wgs84[0]
    xs, ys = zip(*[(p[0], p[1]) for p in ring])
    xs_3116, ys_3116 = _to_3116.transform(xs, ys)
    return Polygon(list(zip(xs_3116, ys_3116)))


def xy_3116_to_latlon(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Convierte arrays de (x,y) en EPSG:3116 a (lat,lon) WGS84."""
    lon, lat = _to_wgs.transform(x, y)
    return np.asarray(lat), np.asarray(lon)


def filtrar_pixeles_en_poligono(
    df: pd.DataFrame, poligono_3116: Polygon
) -> pd.DataFrame:
    """
    Filtra el dataframe a pixeles cuyo (x,y) esta dentro del poligono.
    Pre-filtra por bbox para acelerar antes de la prueba contains() exacta.
    """
    minx, miny, maxx, maxy = poligono_3116.bounds

    bbox_mask = (
        (df["x"] >= minx) & (df["x"] <= maxx) &
        (df["y"] >= miny) & (df["y"] <= maxy)
    )
    sub = df.loc[bbox_mask].copy()
    if sub.empty:
        return sub

    contains = np.array([
        poligono_3116.contains(Point(xi, yi))
        for xi, yi in zip(sub["x"].values, sub["y"].values)
    ])
    return sub.loc[contains]
