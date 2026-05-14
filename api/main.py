"""API REST de inferencia AgroPlus - Que Sembrar."""
import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.config import CORS_ORIGINS, DEFAULT_SEMESTRE
from api.inference import get_store, construir_ranking
from api.schemas import (
    RecomendarRequest, RecomendarResponse,
    CultivoRanking, PixelPrediccion, HealthResponse,
)
from api.spatial import (
    wgs_polygon_to_3116, filtrar_pixeles_en_poligono, xy_3116_to_latlon,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("agroplus.api")

app = FastAPI(
    title="AgroPlus - Que Sembrar?",
    description="API de recomendacion de cultivos para Cundinamarca",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    log.info("Inicializando ModelStore...")
    get_store()
    log.info("ModelStore listo. API operativa.")


@app.get("/health", response_model=HealthResponse)
def health():
    store = get_store()
    return HealthResponse(
        status="ok",
        modelos_cargados=(store.l1 is not None and store.l2_encoder is not None),
        n_pixeles_vista_minable=len(store.df) if store.df is not None else 0,
        semestres_disponibles=store.semestres,
        cultivos_soportados=store.l2_classes,
    )


@app.get("/cultivos", response_model=List[str])
def cultivos():
    return get_store().l2_classes


@app.post("/recomendar", response_model=RecomendarResponse)
def recomendar(req: RecomendarRequest):
    store = get_store()

    semestre = req.semestre or DEFAULT_SEMESTRE
    if semestre not in store.semestres:
        raise HTTPException(
            status_code=400,
            detail=f"Semestre '{semestre}' no disponible. Opciones: {store.semestres}",
        )

    try:
        polygon = wgs_polygon_to_3116(req.poligono.coordinates)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Poligono invalido: {e}")

    df_sem = store.df[store.df["semestre"] == semestre]
    df_sub = filtrar_pixeles_en_poligono(df_sem, polygon)

    if df_sub.empty:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron pixeles en el poligono dado para ese semestre.",
        )

    log.info("Inferencia: %d pixeles en poligono (semestre=%s)", len(df_sub), semestre)

    P, clases = store.predecir_combinado(df_sub)

    ranking_dicts = construir_ranking(P, clases)
    ranking = [CultivoRanking(**r) for r in ranking_dicts]

    lat, lon = xy_3116_to_latlon(df_sub["x"].values, df_sub["y"].values)
    top1_idx = P.argmax(axis=1)

    pixeles: List[PixelPrediccion] = []
    for i in range(len(df_sub)):
        prob_dict = {clases[k]: float(P[i, k]) for k in range(len(clases))}
        pixeles.append(PixelPrediccion(
            lat=float(lat[i]),
            lon=float(lon[i]),
            cultivo_top1=clases[int(top1_idx[i])],
            probabilidades=prob_dict,
        ))

    return RecomendarResponse(
        n_pixeles=len(df_sub),
        semestre=semestre,
        ranking=ranking,
        pixeles=pixeles,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
