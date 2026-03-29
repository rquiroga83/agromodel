# 🌱 ¿Qué Sembrar? — Sistema de Recomendación de Cultivos para Cundinamarca

> Plataforma de planificación agrícola basada en inteligencia artificial que recibe un polígono geográfico (la parcela del agricultor) y devuelve un ranking de cultivos ordenados por probabilidad de éxito, fundamentado en la aptitud agroecológica real de esa ubicación específica.

---

## Tabla de Contenido

1. [Resumen del Proyecto](#1-resumen-del-proyecto)
2. [Problema que Resuelve](#2-problema-que-resuelve)
3. [Arquitectura General](#3-arquitectura-general)
4. [Fuentes de Datos](#4-fuentes-de-datos)
5. [Vista Minable — Estructura de Features](#5-vista-minable)
6. [Modelos de IA](#6-modelos-de-ia)
7. [Pipeline de Inferencia](#7-pipeline-de-inferencia)
8. [Estructura del Repositorio](#8-estructura-del-repositorio)
9. [Instalación y Configuración](#9-instalación-y-configuración)
10. [Uso](#10-uso)
11. [Estado del Arte y Justificación Científica](#11-estado-del-arte)
12. [Métricas de Evaluación](#12-métricas-de-evaluación)
13. [Roadmap](#13-roadmap)
14. [Licencia y Créditos](#14-licencia-y-créditos)

---

## 1. Resumen del Proyecto

**¿Qué Sembrar?** es un módulo de inteligencia artificial para la planificación agrícola en el departamento de Cundinamarca, Colombia. Integra cuatro familias de datos geoespaciales —climáticos, edafológicos, satelitales y topográficos— para generar recomendaciones personalizadas de cultivos a nivel de parcela.

| Aspecto | Detalle |
|---------|---------|
| **Región objetivo** | Cundinamarca, Colombia (24,210 km², 116 municipios) |
| **Rango altitudinal** | 200 m (Valle del Magdalena) a 3,500+ m (Páramos) |
| **Ventana temporal** | 2019–2024 (6 años, 12 semestres agrícolas) |
| **Resolución espacial** | 10 m × 10 m (alineada con Sentinel-2) |
| **Catálogo de cultivos** | ~40–200 cultivos (según filtro de frecuencia) |
| **Tiempo de inferencia** | < 2 segundos por consulta |
| **Explainabilidad** | SHAP + LIME + Contrafactuales |

### Flujo de Uso

1. El agricultor dibuja su parcela en un mapa web
2. El sistema extrae automáticamente las 74+ variables agroecológicas de esa ubicación
3. Cinco modelos de ML procesan los datos en paralelo
4. Un meta-learner combina las predicciones
5. El agricultor recibe un ranking: "Papa 87%, Arveja 72%, Maíz 65%..." con explicaciones de por qué

---

## 2. Problema que Resuelve

Los agricultores de Cundinamarca enfrentan decisiones de siembra complejas condicionadas por la alta variabilidad agroecológica del departamento (4 pisos térmicos, suelos ácidos con alta saturación de aluminio, bimodalidad de lluvias). Actualmente las decisiones se basan en tradición familiar o recomendaciones genéricas que no consideran las condiciones específicas de cada parcela.

Este sistema transforma datos públicos abiertos (IDEAM, IGAC, UPRA, Copernicus) en recomendaciones accionables y explicables a nivel de finca.

---

## 3. Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTERFAZ WEB (Frontend)                       │
│  Agricultor dibuja polígono → Recibe ranking de cultivos + XAI   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ GeoJSON del polígono
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API REST (FastAPI)                             │
│  POST /recomendar  →  Extracción geoespacial → Predicción        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Vector (1, 74)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PIPELINE DE PREDICCIÓN                              │
│                                                                  │
│  ┌──────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────┐         │
│  │  RF  │ │ XGBoost │ │ LightGBM │ │ TabNet │ │ LSTM │         │
│  └──┬───┘ └────┬────┘ └────┬─────┘ └───┬────┘ └──┬───┘         │
│     │          │           │            │         │              │
│     └──────────┴───────────┴────────────┴─────────┘              │
│                           │                                      │
│                    Meta-Learner (Stacking)                        │
│                           │                                      │
│                    XAI (SHAP + LIME)                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Ranking + Explicaciones
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              CAPAS GEOESPACIALES PRECALCULADAS                   │
│                                                                  │
│  Clima (IDEAM/CHIRPS) │ Suelo (IGAC/SoilGrids)                  │
│  Satélite (S2/S1)     │ Topografía (Copernicus DEM)             │
│  Target (EVA/UPRA)    │ Aptitud (SIPRA)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Fuentes de Datos

### 4.1 Features (Variables Predictoras)

| Familia | Fuente | Formato | Variables | Cobertura |
|---------|--------|---------|-----------|-----------|
| **Climática** | IDEAM (datos.gov.co) | API SODA → JSON | Temperatura, Precipitación, Humedad | Estaciones puntuales, interpoladas |
| **Climática** | IDEAM Normales | CSV | Medias 1961-2020 (brillo solar, evaporación) | Nacional |
| **Climática** | CHIRPS v2 | GeoTIFF | Precipitación mensual satelital | ~5.3 km, desde 1981 |
| **Edafológica** | IGAC | ArcGIS REST → GeoJSON | pH, Al, P, K, fertilidad, vocación de uso | 1:100.000 |
| **Edafológica** | SoilGrids 2.0 (ISRIC) | GeoTIFF (COG) | Clay, sand, silt, bdod, soc, cec, nitrogen | 250 m global |
| **Satelital** | Sentinel-2 L2A (CDSE) | GeoTIFF via SentinelHub | NDVI, GNDVI, EVI, NDWI, MSAVI, BSI, SAVI | 10 m, 5 días revisita |
| **Satelital** | Sentinel-1 GRD (CDSE) | GeoTIFF via SentinelHub | VV, VH, ratio VH/VV (dB) | 10 m, penetra nubes |
| **Topográfica** | Copernicus DEM GLO-30 | GeoTIFF via CDSE | Elevación, pendiente, aspecto, curvatura, TWI | 30 m |

### 4.2 Target (Etiquetas de Entrenamiento)

| Fuente | Resolución | Periodo | Uso |
|--------|-----------|---------|-----|
| **EVA** (UPRA/MADR) | Municipal | 2007–2024 | Cultivo + rendimiento por municipio-semestre |
| **Monitoreo UPRA** | Parcela (~25 m) | 2021–2023 | Polígonos georreferenciados de papa, maíz, arroz, cacao |
| **SIPRA Aptitud** | 1:100.000 | Estático | Aptitud Alta/Media/Baja/No Apta por cultivo |

---

## 5. Vista Minable

La vista minable es la tabla rectangular que alimenta los modelos. Cada fila = un (píxel, semestre). Cada columna = un feature.

- **~74 features base** (expandible a ~120 con estadísticos temporales)
- **4 columnas target** (cultivo, confianza, fuente, rendimiento)
- **5 columnas metadata** (pixel_id, x, y, cod_mun, semestre)
- **CRS:** EPSG:3116 (MAGNA-SIRGAS Colombia Bogotá)
- **Formato:** Apache Parquet

### Familias de Features

| # | Familia | Features | Tipo |
|---|---------|----------|------|
| 1-35 | 🌤 Climáticas | temp_media, temp_max, temp_min, precip_mensual×12, humedad, brillo_solar | Float |
| 36-51 | 🪨 Edafológicas | pH, sat_aluminio, P, K, arcilla, arena, limo, densidad, CO, N, CIC, vocación | Float + Cat |
| 52-61 | 🛰 Satelitales | NDVI/GNDVI/EVI/NDWI/MSAVI/BSI/SAVI (stats), VV, VH, ratio | Float |
| 62-66 | ⛰ Topográficas | elevación, pendiente, aspecto, curvatura, TWI | Float |
| 67-74 | ⚙️ Derivadas | temp_ajustada, piso_termico, indice_fertilidad, indice_aridez, ndvi_max | Float + Cat |

---

## 6. Modelos de IA

### Arquitectura de Predicción

**Modelos individuales** (procesan los datos en paralelo):
- **Random Forest** — 300 árboles, votación mayoritaria (accuracy 96.7-99.5% en la literatura)
- **XGBoost** — Gradient boosting con regularización L1/L2 (accuracy 98.2-99.3%)
- **LightGBM** — Boosting por histogramas, soporte nativo de categóricos (5-10× más rápido)
- **TabNet** — Red neuronal con atención secuencial para datos tabulares (accuracy 92% DL)
- **LSTM** — Red recurrente para series temporales de NDVI/precipitación mensuales (accuracy >93%)

**Meta-learner** (combina las 5 predicciones):
- Stacking Ensemble con Logistic Regression o SVC lineal como meta-learner

**Explainabilidad**:
- SHAP (explicación global: qué features importan más)
- LIME (explicación local: por qué este cultivo para esta parcela)
- Contrafactuales (alternativas: qué otra cosa podría sembrar)

---

## 7. Pipeline de Inferencia

```
Polígono GeoJSON (entrada del agricultor)
    │
    ▼
Extracción geoespacial (zonal stats sobre capas precalculadas)  ~0.5s
    │
    ▼
Vector numérico (1, 74)
    │
    ├─→ RF          → prob(1, N_clases)  ─┐
    ├─→ XGBoost     → prob(1, N_clases)  ─┤
    ├─→ LightGBM    → prob(1, N_clases)  ─┤  ~0.3s (paralelo)
    ├─→ TabNet      → prob(1, N_clases)  ─┤
    └─→ LSTM        → prob(1, N_clases)  ─┘
                                           │
                                           ▼
                           Meta-learner (Stacking)           ~0.01s
                                           │
                                           ▼
                           SHAP/LIME explicaciones           ~0.3s
                                           │
                                           ▼
                Ranking: Papa 87% | Arveja 72% | Maíz 65%    TOTAL ~1.4s
```

---

## 8. Estructura del Repositorio

```
que-sembrar/
├── README.md                           # Este archivo
├── SPEC.md                             # Especificación técnica para desarrollo
├── requirements.txt                    # Dependencias Python
│
├── extractores/                        # Scripts de descarga de datos crudos
│   ├── config.py                       # Configuración compartida
│   ├── run_all.py                      # Ejecutor maestro
│   ├── 01_extraer_clima_ideam.py
│   ├── 02_extraer_chirps.py
│   ├── 03_extraer_suelo_igac.py
│   ├── 04_extraer_soilgrids.py
│   ├── 05_extraer_sentinel2.py
│   ├── 06_extraer_sentinel1.py
│   ├── 07_extraer_dem_topografia.py
│   ├── 08_extraer_target.py
│   └── raw/                            # Datos crudos descargados (no en git)
│       ├── clima/
│       │   ├── ideam_temperatura/
│       │   ├── ideam_precipitacion/
│       │   ├── ideam_humedad/
│       │   ├── ideam_normales/
│       │   └── chirps/
│       ├── suelo/
│       │   ├── igac_quimica/
│       │   ├── igac_vocacion/
│       │   └── soilgrids/
│       ├── satelite/
│       │   ├── sentinel2/
│       │   └── sentinel1/
│       ├── topo/
│       │   └── dem_glo30/
│       └── target/
│           ├── eva/
│           ├── monitoreo/
│           └── sipra/
│
├── procesamiento/                      # Armonización y feature engineering
│   ├── 01_armonizar_espacial.py        # ✅ Implementado
│   ├── 02_armonizar_temporal.py
│   ├── 03_feature_engineering.py
│   └── 04_construir_vista_minable.py
│
├── entrenamiento/                      # Training pipeline
│   ├── 01_eda_exploratorio.py
│   ├── 02_preprocesamiento_ml.py
│   ├── 03_entrenar_modelos_base.py
│   ├── 04_entrenar_especialistas.py
│   ├── 05_entrenar_stacking.py
│   └── 06_evaluar_modelos.py
│
├── api/                                # API REST de inferencia
│   ├── main.py                         # FastAPI app
│   ├── inference.py                    # Pipeline de predicción
│   ├── geospatial.py                   # Extracción de features del polígono
│   └── explainability.py               # SHAP/LIME
│
├── frontend/                           # Interfaz web
│   └── (React/Vue app con mapa)
│
├── models/                             # Modelos entrenados (.pkl, .pt) — no en git
│
├── processed/                          # Capas armonizadas a 10 m EPSG:3116 — no en git
│   ├── clima/
│   │   ├── ideam/
│   │   └── chirps/
│   ├── suelo/
│   │   ├── soilgrids/
│   │   └── igac/
│   ├── satelite/
│   │   ├── sentinel2/
│   │   └── sentinel1/
│   └── topo/
│
├── vista_minable/                      # Tabla final de entrenamiento — no en git
│
├── docs/                               # Documentación técnica (HTML generados)
│   ├── vista_minable_que_sembrar.html
│   ├── datos_etiquetado_target.html
│   ├── modelos_ia_recomendados.html
│   ├── arquitectura_inferencia.html
│   └── estrategia_preparacion_datos.html
│
└── tests/                              # Tests unitarios y de integración
```

---

## 9. Instalación y Configuración

### Requisitos del Sistema

- Python 3.10+
- 16 GB RAM mínimo (32 GB recomendado para entrenamiento)
- 50 GB de disco para datos crudos
- GPU opcional (acelera TabNet y LSTM, no es requerido)

### Instalación

```bash
git clone https://github.com/<org>/que-sembrar.git
cd que-sembrar
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Dependencias Principales

```
# Geoespacial
rasterio>=1.3
geopandas>=0.14
pyproj>=3.6
sentinelhub>=3.10
pysheds>=0.3

# ML / DL
scikit-learn>=1.4
xgboost>=2.0
lightgbm>=4.0
pytorch-tabnet>=4.1
torch>=2.0
optuna>=3.5

# Explainabilidad
shap>=0.44
lime>=0.2

# API
fastapi>=0.110
uvicorn>=0.27

# Utilidades
pandas>=2.1
numpy>=1.26
requests>=2.31
```

### Configuración de Credenciales

Editar `extractores/config.py`:
- **CDSE (Copernicus):** Las credenciales OAuth ya están configuradas
- **Google Earth Engine (opcional):** Ejecutar `earthengine authenticate`
- **datos.gov.co:** Acceso público, no requiere autenticación

---

## 10. Uso

### Descarga de Datos

```bash
# Ejecutar todos los extractores
uv run extractores/run_all.py

# O ejecutar uno específico con pasos independientes
uv run extractores/run_all.py 01:temp       # Temperatura IDEAM
uv run extractores/run_all.py 01:precip     # Precipitación (por mes)
uv run extractores/run_all.py 03:quimica    # IGAC propiedades químicas
uv run extractores/run_all.py 08:eva        # EVA agropecuaria
```

### Armonización Espacial

```bash
# Armonizar todo (DEM → IDEAM → CHIRPS → SoilGrids → IGAC → Sentinel-2/1)
uv run procesamiento/01_armonizar_espacial.py

# Pasos individuales
uv run procesamiento/01_armonizar_espacial.py --step dem        # Primero siempre
uv run procesamiento/01_armonizar_espacial.py --step ideam      # Kriging estaciones
uv run procesamiento/01_armonizar_espacial.py --step soilgrids
uv run procesamiento/01_armonizar_espacial.py --step igac
uv run procesamiento/01_armonizar_espacial.py --step sentinel2
uv run procesamiento/01_armonizar_espacial.py --step validar    # Verificar consistencia
```

### Entrenamiento

```bash
cd entrenamiento
python 01_eda_exploratorio.py          # Análisis exploratorio
python 02_preprocesamiento_ml.py       # Limpieza, encoding, split
python 03_entrenar_modelos_base.py     # RF, XGBoost, LightGBM
python 04_entrenar_especialistas.py    # TabNet, LSTM
python 05_entrenar_stacking.py         # Meta-learner
python 06_evaluar_modelos.py           # Métricas, confusion matrix, SHAP
```

### Despliegue de API

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Consulta de Ejemplo

```bash
curl -X POST http://localhost:8000/recomendar \
  -H "Content-Type: application/json" \
  -d '{"poligono": {"type":"Polygon","coordinates":[[[-74.1,4.6],[-74.1,4.61],[-74.09,4.61],[-74.09,4.6],[-74.1,4.6]]]}}'
```

---

## 11. Estado del Arte

El diseño del sistema se fundamenta en el análisis de 15+ artículos científicos recientes (2023-2025) en recomendación de cultivos y predicción de rendimiento. Los hallazgos principales que respaldan las decisiones de diseño:

- **Random Forest** es el modelo más desplegado en producción: Emmanuel N. et al. (2024), Patel et al. (2025)
- **XGBoost** alcanza la mayor accuracy puntual (98.25-99.3%): Emmanuel N. et al. (2024), Dey et al. (2024)
- **Stacking Ensemble** mejora sobre modelos individuales: Sharafat et al. (2025), Hasan et al. (2023)
- **TabNet** supera a otros modelos DL en datos tabulares agrícolas: Sharafat et al. (2025)
- **LSTM** captura patrones fenológicos en series Sentinel-2: Iqbal et al. (2023)
- **SHAP/LIME** son esenciales para adopción por agricultores: Kara et al. (2024), Cartolano et al. (2024)
- **Datos multifuente geoespaciales** superan datasets tabulares simples: Bolívar-Santamaría & Reu (2021)

---

## 12. Métricas de Evaluación

| Métrica | Objetivo | Justificación |
|---------|----------|---------------|
| Accuracy | > 95% | Benchmark del estado del arte (RF: 96.7%, XGBoost: 98.25%) |
| F1-score macro | > 0.90 | Maneja desbalance de clases (cultivos minoritarios) |
| AUC-ROC | > 0.95 | Separabilidad entre clases (Sharafat 2025: AUC=1.00) |
| Inferencia | < 2s | Tiempo de respuesta aceptable para uso interactivo |
| Top-3 accuracy | > 98% | El cultivo correcto debe estar en las 3 primeras recomendaciones |

---

## 13. Roadmap

- [x] Definición de arquitectura de datos y vista minable
- [x] Inventario de variables y fuentes de datos
- [x] Diseño de modelos de IA justificado por estado del arte
- [x] Scripts de extracción de datos (8 extractores)
- [x] Estrategia de preparación de datos y construcción de vista minable
- [x] Armonización espacial (`procesamiento/01_armonizar_espacial.py`)
- [ ] Construcción de la vista minable
- [ ] Entrenamiento y evaluación de modelos
- [ ] Desarrollo de API REST (FastAPI)
- [ ] Desarrollo de interfaz web con mapa
- [ ] Validación con agricultores de Cundinamarca
- [ ] Despliegue en producción

---

## 14. Licencia y Créditos

### Datos Abiertos Utilizados

- **IDEAM** — Datos hidrometeorológicos bajo licencia abierta (Ley 1712 de 2014)
- **IGAC** — Cartografía oficial de Colombia
- **UPRA/SIPRA** — Evaluaciones Agropecuarias y Zonificación de Aptitud
- **Copernicus/ESA** — Sentinel-1, Sentinel-2, DEM GLO-30 (licencia abierta)
- **ISRIC SoilGrids** — CC-BY 4.0

### Proyecto Académico

Módulo ¿Qué Sembrar? — Plataforma de Planificación Agrícola para Cundinamarca, Colombia, 2026.
