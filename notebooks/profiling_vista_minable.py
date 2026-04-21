# -*- coding: utf-8 -*-
"""
Análisis estadístico con ydata-profiling de la vista minable.
Solo usa datos del último año (2025A y 2025B).
Genera reporte HTML interactivo.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from ydata_profiling import ProfileReport

# ── 1. Cargar datos ──────────────────────────────────────────────
print("Cargando vista minable...")
df = pd.read_parquet("vista_minable/vista_minable_full.parquet")
print(f"Total: {len(df):,} filas, {len(df.columns)} columnas")

# ── 2. Filtrar solo último año (2025A, 2025B) ────────────────────
df_latest = df[df["semestre"].isin(["2025A", "2025B"])].copy()
print(f"Filtrado 2025A+2025B: {len(df_latest):,} filas")

# ── 3. Seleccionar columnas relevantes (excluir metadata) ────────
features_cols = [
    # Topografía
    "elevacion", "pendiente", "twi", "aspecto_sin", "aspecto_cos", "piso_termico",
    # SoilGrids
    "sg_phh2o", "sg_soc", "sg_nitrogen", "sg_cec", "sg_bdod",
    "sg_clay", "sg_sand", "sg_silt",
    # IGAC
    "igac_fertilidad", "igac_fosforo", "igac_ph", "igac_potasio", "igac_vocacion",
    # Derivados estáticos
    "indice_fertilidad",
    # Clima
    "temperatura_media", "temperatura_max", "temperatura_min",
    "humedad_media", "chirps_acum",
    "amplitud_termica", "anomalia_precip", "indice_aridez",
    # Sentinel-2
    "s2_ndvi_media", "s2_ndvi_max", "s2_ndvi_std",
    "s2_gndvi_media", "s2_gndvi_max", "s2_gndvi_std",
    "s2_msavi_media", "s2_msavi_max", "s2_msavi_std",
    "s2_bsi_media", "s2_bsi_max", "s2_bsi_std",
    "s2_savi_media", "s2_savi_max", "s2_savi_std",
    # Derivados vegetación
    "ndvi_max", "ndvi_integral",
    # Target
    "cultivo", "confianza", "fuente", "rendimiento_tha",
]

df_profile = df_latest[features_cols].copy()

# Convertir categóricas para mejor profiling
df_profile["cultivo"] = df_profile["cultivo"].astype("category")
df_profile["fuente"] = df_profile["fuente"].astype("category")
df_profile["piso_termico"] = df_profile["piso_termico"].astype("category")

print(f"Dataset para profiling: {len(df_profile):,} filas x {len(df_profile.columns)} columnas")

# ── 4. Generar reporte ───────────────────────────────────────────
print("Generando reporte ydata-profiling (puede tardar varios minutos)...")

profile = ProfileReport(
    df_profile,
    title="Analisis Estadistico - Vista Minable (2025A/2025B)",
    explorative=True,
    minimal=True,
    vars={
        "num": {"low_categorical_threshold": 0},
        "cat": {"length": True, "characters": True, "words": True},
    },
    correlations={
        "auto": {"calculation": {"auto": {"threshold": 0.5}}},
    },
    missing_diagrams={
        "bar": True,
        "matrix": True,
        "dendrogram": True,
        "heatmap": True,
    },
    samples=None,
    progress_bar=True,
)

# ── 5. Guardar reporte ──────────────────────────────────────────
output_path = "docs/vista_minable_profiling.html"
profile.to_file(output_path)
print(f"\nReporte guardado en: {output_path}")
print("Abrir en navegador para ver el reporte interactivo.")