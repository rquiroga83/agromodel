"""Configuracion central de la API AgroPlus."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CKPT_DIR = PROJECT_ROOT / "modelado" / "checkpoints"
L1_PATH = CKPT_DIR / "l1_upra_papa_v3.joblib"
L2_PATH = CKPT_DIR / "l2_llp_co.pt"
SCALER_PATH = CKPT_DIR / "l2_scaler.joblib"

VISTA_MINABLE = PROJECT_ROOT / "vista_minable" / "vista_minable_full.parquet"

TARGET_CRS = "EPSG:3116"
WGS84 = "EPSG:4326"

DEFAULT_SEMESTRE = "2024A"

CLASES_FINALES = [
    "Cana_Panelera", "Cafe", "Maiz", "Platano", "Mango",
    "Frijol", "Cacao", "Arveja", "Palma", "Banano", "Citricos",
    "Mora", "Zanahoria", "Tomate_Arbol", "Yuca", "Habichuela",
    "Hortalizas", "Papa",
]

CROP_COLORS = {
    "Papa": "#8B4513",
    "Cafe": "#6F4E37",
    "Maiz": "#FFD700",
    "Cana_Panelera": "#9ACD32",
    "Platano": "#FFFF66",
    "Mango": "#FFA500",
    "Frijol": "#A0522D",
    "Cacao": "#7B3F00",
    "Arveja": "#7CFC00",
    "Palma": "#228B22",
    "Banano": "#FFE135",
    "Citricos": "#FFA07A",
    "Mora": "#8B0000",
    "Zanahoria": "#FF8C00",
    "Tomate_Arbol": "#FF6347",
    "Yuca": "#DEB887",
    "Habichuela": "#90EE90",
    "Hortalizas": "#3CB371",
}

CORS_ORIGINS = ["*"]
