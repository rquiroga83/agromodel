# SPEC.md — Especificación Técnica para Desarrollo
# Módulo «¿Qué Sembrar?» | Versión 1.0

---

## 1. Visión General del Sistema

### 1.1 Objetivo
Construir un sistema que reciba un polígono geográfico y devuelva un ranking de cultivos ordenados por probabilidad de éxito agrícola, basado en la aptitud agroecológica real de esa ubicación en Cundinamarca, Colombia.

### 1.2 Usuarios Objetivo
- **Primario:** Agricultores de Cundinamarca que planifican siembras semestrales
- **Secundario:** Técnicos agropecuarios de UMATAs municipales
- **Terciario:** Analistas de la UPRA y Secretaría de Agricultura de Cundinamarca

### 1.3 Restricciones
- Latencia de respuesta < 2 segundos
- Datos 100% abiertos y gratuitos (sin dependencia de proveedores de pago)
- Explainabilidad obligatoria (SHAP/LIME en cada recomendación)

---

## 2. Componentes del Sistema

### 2.1 Componente 1 — Extractores de Datos (`extractores/`)

**Estado:** ✅ Implementado

**Responsabilidad:** Descargar datos crudos de todas las fuentes y almacenarlos en `raw/` sin transformar.

**Scripts:**

| Script | Entrada | Salida | Dependencias |
|--------|---------|--------|--------------|
| `config.py` | — | Configuración global | — |
| `01_extraer_clima_ideam.py` | API SODA datos.gov.co | CSV en `raw/clima/ideam_*/` | requests, pandas |
| `02_extraer_chirps.py` | GEE o CHC UCSB | GeoTIFF en `raw/clima/chirps/` | earthengine-api o requests, rasterio |
| `03_extraer_suelo_igac.py` | ArcGIS REST IGAC | GeoJSON en `raw/suelo/igac_*/` | requests |
| `04_extraer_soilgrids.py` | WCS/COG ISRIC | GeoTIFF en `raw/suelo/soilgrids/` | requests, rasterio |
| `05_extraer_sentinel2.py` | SentinelHub CDSE | GeoTIFF en `raw/satelite/sentinel2/` | sentinelhub, rasterio |
| `06_extraer_sentinel1.py` | SentinelHub CDSE | GeoTIFF en `raw/satelite/sentinel1/` | sentinelhub, rasterio |
| `07_extraer_dem_topografia.py` | SentinelHub CDSE | GeoTIFF en `raw/topo/dem_glo30/` | sentinelhub, rasterio, scipy, pysheds |
| `08_extraer_target.py` | SODA + ArcGIS REST | CSV + GeoJSON en `raw/target/` | requests, pandas |

**Criterios de aceptación:**
- Cada script es idempotente (verifica existencia antes de descargar)
- Soporta reanudación tras interrupción
- Manejo de errores HTTP, timeouts y rate limits
- Logs de progreso en stdout

---

### 2.2 Componente 2 — Procesamiento Geoespacial (`procesamiento/`)

**Estado:** 🔲 Por implementar

**Responsabilidad:** Transformar datos crudos heterogéneos en capas armonizadas a resolución 10 m en EPSG:3116.

#### 2.2.1 `01_armonizar_espacial.py`

**Entrada:** Archivos en `raw/` (múltiples CRS, resoluciones, formatos)
**Salida:** GeoTIFF por variable en `processed/` (todos en EPSG:3116, 10 m × 10 m)

**Operaciones requeridas:**

| Dato | Resolución Original | Método de Remuestreo | Notas |
|------|---------------------|---------------------|-------|
| Estaciones IDEAM | Puntual | Kriging ordinario + corrección por gradiente adiabático (-6°C/1000m) | Usar `pykrige`. Requiere DEM como covariable. |
| CHIRPS | ~5.3 km | Resampling bilineal | Validar contra estaciones IDEAM |
| SoilGrids | 250 m | Bilineal (continuos) / Nearest-neighbor (texturas) | Texturas deben sumar 100% |
| IGAC vectorial | Polígonos 1:100k | Rasterización con `rasterio.features.rasterize` | Categóricos: vocación, fertilidad |
| Sentinel-2 | 10 m / 20 m | Bandas 20m → bilineal a 10m; 10m: reproyectar | Calcular índices DESPUÉS del resampling |
| Sentinel-1 | 10 m | Solo reproyección | Ya está en resolución nativa |
| DEM Copernicus | 30 m | Calcular derivadas a 30m PRIMERO, luego resamplear a 10m | Evita artefactos de interpolación |

**Dependencias:** rasterio, geopandas, pykrige, scipy, numpy, pyproj

**Criterios de aceptación:**
- Todas las capas comparten exactamente el mismo extent, resolución y CRS
- Sin píxeles de borde con valores NoData parciales
- Tests de validación: verificar que valores caen en rangos físicos esperados

#### 2.2.2 `02_armonizar_temporal.py`

**Entrada:** Series temporales crudas (horarias, diarias, mensuales)
**Salida:** Agregados semestrales alineados con periodos EVA

**Operaciones requeridas:**

| Variable | Agregación | Ventana |
|----------|-----------|---------|
| Temperatura horaria IDEAM | → media mensual → media/max/min anual | Semestre A (ene-jun), B (jul-dic) |
| Precipitación 10-min IDEAM | → acumulado diario → acumulado mensual → semestral/anual | Semestre A/B |
| Humedad horaria IDEAM | → media mensual → media anual | Semestre A/B |
| Sentinel-2 composites | Mediana semestral (ya calculada en extractor) | Ya alineado |
| CHIRPS mensual | → acumulado semestral | Semestre A/B |

**Criterios de aceptación:**
- 12 semestres completos (2019A a 2024B)
- Sin gaps temporales (imputar con forward-fill si es necesario)
- Reporte de cobertura temporal por estación IDEAM

#### 2.2.3 `03_feature_engineering.py`

**Entrada:** Capas armonizadas en `processed/`
**Salida:** Variables derivadas en `processed/engineered/`

**Features a calcular:**

| Feature | Fórmula | Inputs |
|---------|---------|--------|
| `temp_ajustada_altitud` | `temp_interpolada - 0.006 × (DEM - altitud_estacion)` | Ráster temp + DEM |
| `amplitud_termica` | `temp_max_media - temp_min_media` | Rásters temp |
| `piso_termico` | `if elev<1000: 0; 1000-2000: 1; 2000-3000: 2; >3000: 3` | DEM |
| `indice_fertilidad` | `w₁·N + w₂·P + w₃·K + w₄·pH_opt + w₅·CO` (normalizado) | Rásters suelo |
| `indice_aridez` | `precip_anual / evapotranspiracion` | Rásters clima |
| `anomalia_precip` | `(precip_sem - normal) / σ` | CHIRPS + Normales |
| `ndvi_max_semestre` | `max(NDVI mensuales)` | Composites S2 |
| `ndvi_integral` | `∑(NDVI × 30)` | Composites S2 |

#### 2.2.4 `04_construir_vista_minable.py`

**Entrada:** Stack completo de rásters procesados + datos target
**Salida:** `vista_minable/vista_minable_full.parquet`

**Operaciones:**

1. Crear máscara del departamento de Cundinamarca
2. Muestreo estratificado: ~500K-1M píxeles por (piso_termico × pendiente_clase × presencia_monitoreo)
3. Extraer 74+ valores por píxel del stack de rásters
4. Asignar etiquetas target:
   - Prioridad 1: polígonos de monitoreo UPRA (confianza=1.0)
   - Prioridad 2: EVA municipal con score de aptitud revelada (confianza=0.7)
   - Prioridad 3: SIPRA aptitud (confianza=0.5)
5. Guardar como Parquet con metadatos

**Esquema de la tabla:**

```
pixel_id        INT64       # Identificador único
x               FLOAT64     # Coordenada X (EPSG:3116)
y               FLOAT64     # Coordenada Y (EPSG:3116)
cod_mun         STRING      # Código DANE municipio
semestre        STRING      # '2019A', '2019B', ..., '2024B'
# ── 74+ features ──
temp_media      FLOAT32
temp_max        FLOAT32
...
twi             FLOAT32
piso_termico    INT8
# ── target ──
cultivo         STRING      # Nombre del cultivo
cultivo_id      INT16       # Label encoded
confianza       FLOAT32     # 0.5-1.0
fuente          STRING      # 'monitoreo' | 'eva' | 'sipra'
rendimiento_tha FLOAT32     # Rendimiento histórico (t/ha)
```

**Criterios de aceptación:**
- Sin filas duplicadas (pixel_id + semestre únicos)
- Sin features con >30% de NaN
- Distribución de clases documentada
- Validación cruzada: features de píxeles con monitoreo UPRA deben ser consistentes con la clase asignada

---

### 2.3 Componente 3 — Entrenamiento de Modelos (`entrenamiento/`)

**Estado:** 🔲 Por implementar

#### 2.3.1 `01_eda_exploratorio.py`

- Distribución de cada feature (histogramas, boxplots)
- Matriz de correlación (identificar r > 0.95)
- Distribución de clases target
- Análisis por piso térmico y municipio
- Exportar reporte HTML con visualizaciones

#### 2.3.2 `02_preprocesamiento_ml.py`

**Operaciones:**

| Paso | Detalle | Herramienta |
|------|---------|-------------|
| Imputación | Mediana por estrato (piso_termico × municipio) | `SimpleImputer` o NaN nativo (XGBoost/LightGBM) |
| Outliers | Flag con IQR, no eliminar | numpy |
| Encoding categóricos | LabelEncoder para RF/XGBoost; categórico nativo para LightGBM; Target Encoding para TabNet | scikit-learn, category_encoders |
| Normalización | MinMaxScaler [0,1] para TabNet/LSTM SOLAMENTE | `MinMaxScaler` (fit en train) |
| Split | 80/20 con `StratifiedGroupKFold(groups=cod_mun)` | scikit-learn |
| Balanceo | `class_weight='balanced'` + SMOTE para clases <500 muestras | imblearn |
| Reshape LSTM | `(N, 12, 5)` para features temporales mensuales | numpy reshape |

**Salida:** `X_train.parquet`, `X_test.parquet`, `y_train.parquet`, `y_test.parquet`, `scaler.pkl`, `encoder.pkl`

#### 2.3.3 `03_entrenar_modelos_base.py`

| Modelo | Hiperparámetros | Tuning |
|--------|----------------|--------|
| Random Forest | n_estimators=100-300, max_depth=9-15, max_features='sqrt' | Optuna 100 trials |
| XGBoost | n_estimators=200-500, max_depth=4-8, learning_rate=0.05-0.1, reg_lambda=1.0 | Optuna 100 trials |
| LightGBM | num_leaves=31-127, learning_rate=0.01-0.1, feature_fraction=0.7-0.9 | Optuna 100 trials |

**Salida:** `models/rf_model.pkl`, `models/xgb_model.pkl`, `models/lgbm_model.pkl`

#### 2.3.4 `04_entrenar_especialistas.py`

| Modelo | Configuración | Tuning |
|--------|--------------|--------|
| TabNet | n_d=n_a=32-64, n_steps=3-7, gamma=1.0-2.0, lambda_sparse=1e-4 | Optuna 50 trials |
| LSTM | 2 capas, 64-128 unidades, dropout=0.2-0.3, lr=0.001, epochs=50-100 | Optuna 50 trials |

**Salida:** `models/tabnet_model.pt`, `models/lstm_model.pt`

#### 2.3.5 `05_entrenar_stacking.py`

1. Generar out-of-fold predictions de cada modelo base (5-fold CV)
2. Concatenar las 5 predicciones como features del meta-learner
3. Entrenar LogisticRegression y SVC como meta-learners
4. Seleccionar el mejor por cross-validation accuracy

**Salida:** `models/meta_learner.pkl`

#### 2.3.6 `06_evaluar_modelos.py`

- Accuracy, Precision, Recall, F1-score (macro y por clase)
- Confusion matrix
- AUC-ROC por clase
- SHAP summary plot (feature importance global)
- LIME explanations para 10 muestras de test
- Comparativa con estado del arte (tabla)
- Exportar reporte HTML

---

### 2.4 Componente 4 — API de Inferencia (`api/`)

**Estado:** 🔲 Por implementar

**Framework:** FastAPI

#### 2.4.1 Endpoints

```yaml
POST /api/v1/recomendar:
  description: Recibe un polígono GeoJSON y devuelve ranking de cultivos
  request_body:
    content:
      application/json:
        schema:
          type: object
          required: [poligono]
          properties:
            poligono:
              type: object
              description: GeoJSON Polygon o MultiPolygon (WGS84)
            semestre:
              type: string
              description: "'A' o 'B'. Default: semestre actual"
              default: auto
            top_n:
              type: integer
              description: "Número de cultivos a devolver"
              default: 10
  responses:
    200:
      content:
        application/json:
          schema:
            type: object
            properties:
              ranking:
                type: array
                items:
                  type: object
                  properties:
                    posicion: integer
                    cultivo: string
                    probabilidad: number
                    rendimiento_esperado_tha: number
                    explicacion:
                      type: object
                      properties:
                        factores_positivos: array
                        factores_negativos: array
                        factores_principales: array
              metadata:
                type: object
                properties:
                  municipio: string
                  piso_termico: string
                  elevacion_media: number
                  tiempo_inferencia_ms: number

GET /api/v1/cultivos:
  description: Lista de cultivos del catálogo con metadata

GET /api/v1/health:
  description: Health check del servicio
```

#### 2.4.2 `geospatial.py` — Extracción de Features

```python
def extraer_features(poligono_geojson: dict, semestre: str) -> np.ndarray:
    """
    Recibe un GeoJSON Polygon, ejecuta zonal stats sobre las capas
    precalculadas, y devuelve un vector (1, 74) listo para los modelos.
    """
    # 1. Validar y reproyectar polígono a EPSG:3116
    # 2. Para cada capa raster en processed/:
    #    - Calcular media ponderada por área de los píxeles en el polígono
    # 3. Para capas vectoriales (IGAC):
    #    - Intersectar y obtener valor del polígono contenedor
    # 4. Ensamblar vector en el orden exacto de las columnas de entrenamiento
    # 5. Aplicar feature engineering on-the-fly (piso_termico, indices)
    pass
```

#### 2.4.3 `inference.py` — Pipeline de Predicción

```python
def predecir(features: np.ndarray) -> dict:
    """
    Recibe vector (1, 74), ejecuta los 5 modelos + meta-learner,
    genera explicaciones SHAP, devuelve ranking.
    """
    # 1. Preparar input para cada modelo (normalizar para TabNet/LSTM, reshape para LSTM)
    # 2. Ejecutar modelos en paralelo (ThreadPoolExecutor)
    # 3. Concatenar probabilidades → input del meta-learner
    # 4. Obtener predicción final
    # 5. Generar explicación SHAP para el top-3
    # 6. Construir response dict
    pass
```

#### 2.4.4 Requerimientos No Funcionales

| Requisito | Valor | Medición |
|-----------|-------|----------|
| Latencia P50 | < 1.5 s | Timer en middleware |
| Latencia P99 | < 3 s | Timer en middleware |
| Disponibilidad | 99.5% | Uptime monitoring |
| Concurrencia | 10 requests/s | Load test con locust |
| Tamaño modelos en memoria | < 2 GB | sum(model.size) |
| Cold start | < 10 s | Tiempo de carga inicial |

---

### 2.5 Componente 5 — Frontend (`frontend/`)

**Estado:** 🔲 Por implementar

**Framework sugerido:** React + Leaflet/Mapbox GL

**Funcionalidades:**

1. **Mapa interactivo** con capas base de Cundinamarca
2. **Herramienta de dibujo** de polígonos (Leaflet.draw)
3. **Panel de resultados** con ranking de cultivos, porcentajes y explicaciones SHAP visuales
4. **Vista de detalle** por cultivo: rendimiento histórico, calendario de siembra, factores determinantes
5. **Responsive** para uso en móvil (agricultores en campo)

---

## 3. Convenciones de Desarrollo

### 3.1 Código

- **Lenguaje:** Python 3.10+ (backend), JavaScript/TypeScript (frontend)
- **Formato:** black (Python), prettier (JS)
- **Linting:** flake8 + mypy (Python), eslint (JS)
- **Docstrings:** Google style
- **Nombres:** snake_case (Python), camelCase (JS)
- **Git:** Conventional Commits (`feat:`, `fix:`, `docs:`, `data:`)

### 3.2 Datos

- `raw/` — Inmutable. Nunca modificar archivos descargados.
- `processed/` — Reproducible. Se regenera ejecutando `procesamiento/`.
- `vista_minable/` — Reproducible. Se regenera desde `processed/`.
- `models/` — Versionados con DVC o MLflow.
- **Formato tabular:** Apache Parquet (columnar, comprimido)
- **Formato raster:** GeoTIFF con compresión Deflate
- **CRS del proyecto:** EPSG:3116 (procesamiento), EPSG:4326 (API entrada/salida)

### 3.3 Testing

| Tipo | Scope | Herramienta |
|------|-------|-------------|
| Unit | Funciones individuales de procesamiento | pytest |
| Integration | Pipeline completo extracción → vista minable | pytest + fixtures |
| Model | Accuracy en test set > 95%, F1 macro > 0.90 | Custom assertions |
| API | Endpoints responden correctamente | pytest + httpx |
| Load | 10 req/s sin degradación | locust |
| Geospatial | Valores extraídos en rangos válidos | pytest + rasterio |

### 3.4 CI/CD

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=.
```

---

## 4. Glosario

| Término | Definición |
|---------|-----------|
| **Vista minable** | Tabla rectangular donde cada fila es un (píxel, semestre) y cada columna un feature o target |
| **Feature** | Variable predictora (ej: pH del suelo, NDVI, elevación) |
| **Target** | Variable objetivo (cultivo recomendado) |
| **Zonal stats** | Operación que calcula estadísticos (media, max, etc.) de un raster dentro de un polígono |
| **Stacking** | Técnica de ensemble donde un meta-learner combina las predicciones de modelos base |
| **SHAP** | SHapley Additive exPlanations — método de explicabilidad basado en teoría de juegos |
| **LIME** | Local Interpretable Model-agnostic Explanations — explicabilidad local por aproximación lineal |
| **EVA** | Evaluaciones Agropecuarias Municipales — estadísticas de producción agrícola por municipio |
| **SIPRA** | Sistema de Información para la Planificación Rural Agropecuaria |
| **CDSE** | Copernicus Data Space Ecosystem — plataforma de acceso a datos Sentinel |
| **Piso térmico** | Clasificación altitudinal colombiana: cálido (<1000m), templado (1000-2000m), frío (2000-3000m), páramo (>3000m) |

---

## 5. Riesgos Técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| Vacíos de cobertura de estaciones IDEAM | Alta | Medio | CHIRPS como complemento satelital; Kriging con incertidumbre |
| Nubosidad persistente en Sentinel-2 | Alta | Medio | Composites semestrales con mediana; Sentinel-1 (SAR) como respaldo |
| WAF del IGAC bloquea descargas | Media | Alto | Paginación de 2000, headers de navegador, reintentos con delay |
| Desbalance extremo de clases (papa domina) | Alta | Alto | SMOTE, class_weight='balanced', métricas macro-promediadas |
| Cambio de APIs de datos.gov.co | Baja | Alto | Guardar datos descargados en raw/ (inmutables), versionado |
| Cuota CDSE excedida | Media | Medio | Descarga incremental, caché de composites |

---

*Última actualización: Marzo 2026*
