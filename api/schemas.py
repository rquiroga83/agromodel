"""Esquemas Pydantic para la API."""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class GeoJSONPolygon(BaseModel):
    type: str = Field(..., pattern="^Polygon$")
    coordinates: List[List[List[float]]]


class RecomendarRequest(BaseModel):
    poligono: GeoJSONPolygon
    semestre: Optional[str] = None


class CultivoRanking(BaseModel):
    cultivo: str
    prob_media: float
    prob_max: float
    color: str


class PixelPrediccion(BaseModel):
    lat: float
    lon: float
    cultivo_top1: str
    probabilidades: Dict[str, float]


class RecomendarResponse(BaseModel):
    n_pixeles: int
    semestre: str
    ranking: List[CultivoRanking]
    pixeles: List[PixelPrediccion]


class HealthResponse(BaseModel):
    status: str
    modelos_cargados: bool
    n_pixeles_vista_minable: int
    semestres_disponibles: List[str]
    cultivos_soportados: List[str]
