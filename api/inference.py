"""Carga de modelos L1/L2 y pipeline de inferencia."""
from typing import Dict, List, Optional, Tuple
import logging

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

from api.config import (
    L1_PATH, L2_PATH, SCALER_PATH, VISTA_MINABLE,
    DEFAULT_SEMESTRE, CLASES_FINALES, CROP_COLORS,
)

log = logging.getLogger(__name__)


class MLPEncoder(nn.Module):
    """Replica exacta del encoder definido en CRISP_DM_AgroPlus_LLP_Co_V1.ipynb."""

    def __init__(self, n_features, hidden_dims=(256, 128, 64), emb_dim=512, dropout=0.2):
        super().__init__()
        layers = []
        in_dim = n_features
        for h in hidden_dims:
            layers += [nn.Linear(in_dim, h), nn.LayerNorm(h), nn.GELU(), nn.Dropout(dropout)]
            in_dim = h
        layers += [nn.Linear(in_dim, emb_dim)]
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        z = self.net(x)
        return F.normalize(z, dim=-1)


class Prototypes(nn.Module):
    def __init__(self, K, emb_dim=512):
        super().__init__()
        W = torch.randn(emb_dim, K)
        Q, _ = torch.linalg.qr(W)
        self.V = nn.Parameter(Q[:, :K].T)

    def normed(self):
        return F.normalize(self.V, dim=-1)


class ModelStore:
    """Singleton que mantiene los modelos cargados en memoria."""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.l1 = None
        self.l1_scaler = None
        self.l1_imputer = None
        self.l1_features: List[str] = []
        self.l1_threshold = 0.5

        self.l2_encoder: Optional[MLPEncoder] = None
        self.l2_prototypes: Optional[Prototypes] = None
        self.l2_scaler = None
        self.l2_features: List[str] = []
        self.l2_classes: List[str] = []
        self.l2_tau = 0.05

        self.df: Optional[pd.DataFrame] = None
        self.semestres: List[str] = []
        self.medianas_features: Dict[str, float] = {}

    def cargar(self):
        log.info("Cargando modelo L1 desde %s", L1_PATH)
        l1_artifact = joblib.load(L1_PATH)
        self.l1 = l1_artifact["model"]
        self.l1_scaler = l1_artifact.get("scaler")
        self.l1_imputer = l1_artifact.get("imputer")
        self.l1_features = l1_artifact["feature_cols"]
        self.l1_threshold = float(l1_artifact.get("threshold_op", 0.5))
        log.info("L1 cargado: %d features, threshold=%.2f",
                 len(self.l1_features), self.l1_threshold)

        log.info("Cargando modelo L2 desde %s", L2_PATH)
        ckpt = torch.load(L2_PATH, map_location=self.device, weights_only=False)
        cfg = ckpt["config"]
        n_feat = cfg["n_features"]
        K = cfg["K"]
        emb_dim = cfg["emb_dim"]
        self.l2_tau = float(cfg["tau"])
        self.l2_features = ckpt["feature_cols"]
        self.l2_classes = ckpt["classes"]

        self.l2_encoder = MLPEncoder(n_feat, emb_dim=emb_dim).to(self.device)
        self.l2_encoder.load_state_dict(ckpt["encoder_state"])
        self.l2_encoder.eval()

        self.l2_prototypes = Prototypes(K, emb_dim=emb_dim).to(self.device)
        self.l2_prototypes.load_state_dict(ckpt["prototypes_state"])
        self.l2_prototypes.eval()
        log.info("L2 cargado: K=%d, emb=%d, %d features, tau=%.4f",
                 K, emb_dim, n_feat, self.l2_tau)

        if SCALER_PATH.exists():
            self.l2_scaler = joblib.load(SCALER_PATH)
            log.info("Scaler L2 cargado desde %s", SCALER_PATH)
        else:
            log.warning("Scaler L2 NO encontrado en %s — se reconstruira", SCALER_PATH)

        log.info("Cargando vista minable %s", VISTA_MINABLE)
        self.df = pd.read_parquet(VISTA_MINABLE)
        self.semestres = sorted(self.df["semestre"].unique().tolist())
        log.info("Vista minable cargada: %d filas, semestres=%s",
                 len(self.df), self.semestres)

        union_features = sorted(set(self.l1_features) | set(self.l2_features))
        for c in union_features:
            if c in self.df.columns:
                self.medianas_features[c] = float(np.nanmedian(self.df[c].values))

        if self.l2_scaler is None:
            self._fit_scaler_fallback()

    def _fit_scaler_fallback(self):
        from sklearn.preprocessing import StandardScaler

        log.warning("Reconstruyendo scaler L2 desde la vista minable")
        sub = self.df[self.df["fuente"].isin({"eva_municipal", "monitoreo"})]
        X = sub[self.l2_features].values.astype(np.float32).copy()
        for j, col in enumerate(self.l2_features):
            if np.isnan(X[:, j]).any():
                X[np.isnan(X[:, j]), j] = self.medianas_features.get(col, 0.0)
        self.l2_scaler = StandardScaler().fit(X)
        log.info("Scaler L2 reconstruido sobre %d filas", len(X))

    def _imputar(self, X: np.ndarray, feature_cols: List[str]) -> np.ndarray:
        out = X.astype(np.float32, copy=True)
        for j, col in enumerate(feature_cols):
            if np.isnan(out[:, j]).any():
                out[np.isnan(out[:, j]), j] = self.medianas_features.get(col, 0.0)
        return out

    @torch.no_grad()
    def predecir_l2(self, X_features: np.ndarray) -> np.ndarray:
        X_imp = self._imputar(X_features, self.l2_features)
        X_scaled = self.l2_scaler.transform(X_imp).astype(np.float32)
        x = torch.from_numpy(X_scaled).to(self.device)
        z = self.l2_encoder(x)
        scores = z @ self.l2_prototypes.normed().T
        P = F.softmax(scores / self.l2_tau, dim=1)
        return P.cpu().numpy()

    def predecir_l1(self, X_features: np.ndarray) -> np.ndarray:
        X_imp = X_features.astype(np.float32, copy=True)
        if self.l1_imputer is not None:
            X_imp = self.l1_imputer.transform(X_imp)
        if self.l1_scaler is not None:
            X_imp = self.l1_scaler.transform(X_imp)
        return self.l1.predict_proba(X_imp)[:, 1]

    def predecir_combinado(
        self, df_pixeles: pd.DataFrame
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Combina L1 (Papa) con L2 (18 cultivos) sustituyendo prob_Papa por L1.
        Retorna (matriz_probabilidades NxK, lista_de_clases).
        """
        X_l2 = df_pixeles[self.l2_features].values
        P_l2 = self.predecir_l2(X_l2)

        X_l1 = df_pixeles[self.l1_features].values
        p_papa_l1 = self.predecir_l1(X_l1)

        idx_papa = self.l2_classes.index("Papa")
        P = P_l2.copy()
        P[:, idx_papa] = p_papa_l1
        row_sums = P.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums > 0, row_sums, 1.0)
        P = P / row_sums

        return P, self.l2_classes


def construir_ranking(P: np.ndarray, clases: List[str]) -> List[Dict]:
    """Agrega la matriz de probabilidades a un ranking ordenado."""
    prob_media = P.mean(axis=0)
    prob_max = P.max(axis=0)

    items = []
    for k, cls in enumerate(clases):
        items.append({
            "cultivo": cls,
            "prob_media": float(prob_media[k]),
            "prob_max": float(prob_max[k]),
            "color": CROP_COLORS.get(cls, "#888888"),
        })
    items.sort(key=lambda x: x["prob_media"], reverse=True)
    return items


_store: Optional[ModelStore] = None


def get_store() -> ModelStore:
    global _store
    if _store is None:
        _store = ModelStore()
        _store.cargar()
    return _store
