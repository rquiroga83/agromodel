# procesamiento/

Scripts de transformación de datos crudos a capas armonizadas listas para modelado.

## 01_armonizar_espacial.py

Convierte todas las fuentes de datos crudas (`extractores/raw/`) a un único grid de referencia:

| Parámetro | Valor |
|---|---|
| CRS | EPSG:3116 — MAGNA-SIRGAS Colombia Bogotá |
| Resolución | 10 m × 10 m |
| Salida | `processed/` |

### Dependencias

```bash
pip install rasterio geopandas pykrige scipy numpy pyproj pandas
```

---

### Ejecución por paso

#### Todo en secuencia (orden automático correcto)

```bash
uv run procesamiento/01_armonizar_espacial.py
```

> El script ejecuta los pasos en el orden correcto: DEM → IDEAM → CHIRPS → SoilGrids → IGAC → Sentinel-2 → Sentinel-1 → Validación.

---

#### Paso 1 — Estaciones IDEAM (Kriging)

Interpola las estaciones puntuales del IDEAM a superficie continua 10 m usando Kriging Ordinario. La temperatura incluye corrección por gradiente adiabático (−6 °C / 1000 m).

> **Requiere el DEM procesado primero** (usa la elevación para la corrección de temperatura).

```bash
# Las tres variables
uv run procesamiento/01_armonizar_espacial.py --step ideam

# Solo temperatura
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable temperatura

# Solo precipitación
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable precipitacion

# Solo humedad relativa
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable humedad
```

Salida: `processed/clima/ideam/{variable}_{YYYY_MM}_kriging.tif`

---

#### Paso 2 — CHIRPS (precipitación satelital)

Reproyecta los GeoTIFF mensuales de CHIRPS (~5.3 km) a 10 m con resampling bilineal.

```bash
uv run procesamiento/01_armonizar_espacial.py --step chirps
```

Salida: `processed/clima/chirps/*.tif`

---

#### Paso 3 — SoilGrids

Reproyecta propiedades de suelo globales (250 m) a 10 m. Usa bilineal para variables continuas y nearest-neighbor para texturas (clay, sand, silt). Normaliza automáticamente clay + sand + silt = 100%.

```bash
uv run procesamiento/01_armonizar_espacial.py --step soilgrids
```

Salida: `processed/suelo/soilgrids/*.tif`

---

#### Paso 4 — IGAC (suelo colombiano vectorial)

Rasteriza los polígonos del IGAC (propiedades químicas y vocación de uso) al grid de 10 m. Los campos categóricos (fertilidad, vocación) se codifican a enteros con tabla de códigos JSON.

```bash
uv run procesamiento/01_armonizar_espacial.py --step igac
```

Salida: `processed/suelo/igac/*.tif` y `*_tabla_codigos.json`

---

#### Paso 5 — Sentinel-2

Reproyecta los GeoTIFF mensuales de Sentinel-2 de WGS84 a EPSG:3116. Conserva la resolución nativa (~10 m) — no hace upsample artificial.

```bash
uv run procesamiento/01_armonizar_espacial.py --step sentinel2
```

Salida: `processed/satelite/sentinel2/s2_indices_{YYYY_MM}.tif` (resolución nativa ~10 m en EPSG:3116)

---

#### Paso 6 — Sentinel-1

Reproyecta los GeoTIFF mensuales de Sentinel-1 SAR de WGS84 a EPSG:3116. Conserva resolución nativa (~10 m).

```bash
uv run procesamiento/01_armonizar_espacial.py --step sentinel1
```

Salida: `processed/satelite/sentinel1/s1_backscatter_{YYYY_MM}.tif` (resolución nativa ~10 m en EPSG:3116)

---

#### Paso 7 — DEM + derivadas topográficas

Reproyecta el DEM Copernicus GLO-30 y sus derivadas (pendiente, aspecto, curvatura, TWI) de 30 m a 10 m. **Ejecutar este paso primero** cuando se procesa todo desde cero.

```bash
uv run procesamiento/01_armonizar_espacial.py --step dem
```

Salida: `processed/topo/dem_{banda}_10m.tif`

| Archivo | Contenido |
|---|---|
| `dem_elevacion_10m.tif` | Elevación en metros |
| `dem_pendiente_10m.tif` | Pendiente en grados (0°–90°) |
| `dem_aspecto_10m.tif` | Orientación de ladera (0°=Norte) |
| `dem_curvatura_10m.tif` | Curvatura del perfil |
| `dem_twi_10m.tif` | Topographic Wetness Index |
| `dem_cundinamarca_10m.tif` | Alias de elevación (usado por IDEAM) |

---

#### Validación

Verifica que todos los rásteres en `processed/` compartan CRS, dimensiones y rangos físicos válidos.

```bash
uv run procesamiento/01_armonizar_espacial.py --step validar
```

---

### Orden recomendado al procesar desde cero

```bash
uv run procesamiento/01_armonizar_espacial.py --step dem
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable temperatura
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable precipitacion
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable humedad
uv run procesamiento/01_armonizar_espacial.py --step chirps
uv run procesamiento/01_armonizar_espacial.py --step soilgrids
uv run procesamiento/01_armonizar_espacial.py --step igac
uv run procesamiento/01_armonizar_espacial.py --step sentinel2
uv run procesamiento/01_armonizar_espacial.py --step sentinel1
uv run procesamiento/01_armonizar_espacial.py --step validar
```

### Reanudación automática

Cada paso verifica si el archivo de salida ya existe antes de procesarlo. Si una ejecución se interrumpe, basta con volver a correr el mismo comando — los archivos ya generados se saltan automáticamente.

---

## 02_armonizar_temporal.py

Agrega los rásteres **mensuales** generados por `01_armonizar_espacial.py` en **estadísticos semestrales** alineados con los semestres agrícolas EVA (Semestre A: enero–junio, Semestre B: julio–diciembre).

### ¿Por qué este paso?

Los modelos necesitan features a nivel semestral (cada observación = un píxel × semestre), pero los datos mensuales se conservan para el LSTM y features temporales. Este script genera los agregados semestrales que alimentan la vista minable y el feature engineering.

### Agregaciones por fuente

| Fuente | Variable | Agregación | Archivo de salida |
|---|---|---|---|
| IDEAM | Temperatura | media, max, min | `temperatura_{agg}_{YYYY[AB]}.tif` |
| IDEAM | Precipitación | acumulado (suma) | `precipitacion_acum_{YYYY[AB]}.tif` |
| IDEAM | Humedad | media | `humedad_media_{YYYY[AB]}.tif` |
| CHIRPS | Precipitación | acumulado (suma) | `chirps_acum_{YYYY[AB]}.tif` |
| Sentinel-2 | 7 índices (NDVI, GNDVI, EVI, NDWI, MSAVI, BSI, SAVI) | media, max, std | `s2_{indice}_{agg}_{YYYY[AB]}.tif` |
| Sentinel-1 | 3 bandas (VV, VH, VH/VV ratio) | media | `s1_{banda}_media_{YYYY[AB]}.tif` |

### Requisitos mínimos

- IDEAM/CHIRPS: mínimo 3 de 6 meses disponibles por semestre
- Sentinel-1/2: mínimo 2 de 6 meses disponibles por semestre

### Dependencias

```bash
pip install rasterio numpy
```

### Ejecución

```bash
# Agregar todo
uv run procesamiento/02_armonizar_temporal.py

# Pasos individuales
uv run procesamiento/02_armonizar_temporal.py --step ideam
uv run procesamiento/02_armonizar_temporal.py --step chirps
uv run procesamiento/02_armonizar_temporal.py --step sentinel2
uv run procesamiento/02_armonizar_temporal.py --step sentinel1
```

### Salida

```
processed/temporal/
├── clima/
│   ├── ideam/
│   │   ├── temperatura_media_2019A.tif
│   │   ├── temperatura_max_2019A.tif
│   │   ├── temperatura_min_2019A.tif
│   │   ├── precipitacion_acum_2019A.tif
│   │   └── humedad_media_2019A.tif
│   └── chirps/
│       └── chirps_acum_2019A.tif
└── satelite/
    ├── sentinel2/
    │   ├── s2_ndvi_media_2019A.tif
    │   ├── s2_ndvi_max_2019A.tif
    │   ├── s2_ndvi_std_2019A.tif
    │   └── ...  (7 índices × 3 agregaciones × 12 semestres)
    └── sentinel1/
        ├── s1_vv_media_2019A.tif
        ├── s1_vh_media_2019A.tif
        └── s1_vh_vv_ratio_media_2019A.tif
```

---

## 03_feature_engineering.py

Genera **features derivadas** a partir de las capas armonizadas y los agregados temporales. Estas features capturan relaciones agroecológicas que no están explícitas en los datos crudos.

### Features generadas

| Feature | Fuentes de entrada | Descripción |
|---|---|---|
| **Piso térmico** | DEM elevación | Clasificación altitudinal: 0=cálido (<1000m), 1=templado (1000–2000m), 2=frío (2000–3000m), 3=páramo (>3000m) |
| **Amplitud térmica** | Temp. max − Temp. min semestral | Diferencia entre temperatura máxima y mínima media del semestre (°C) |
| **Índice de fertilidad** | SoilGrids (N, pH, CEC, SOC) 0–5 cm | Promedio ponderado normalizado: 0.25×N + 0.25×pH_opt + 0.25×CEC + 0.25×SOC. pH óptimo = 1 − |pH−6.5|/3.5 |
| **Anomalía de precipitación** | CHIRPS acumulado semestral | (precip − normal) / std, agrupado por tipo de semestre (A/B). Detecta semestres atípicamente secos o lluviosos |
| **NDVI máximo** | S2 NDVI mensual | Máximo valor de NDVI en el semestre — proxy de vigor vegetativo pico |
| **NDVI integral** | S2 NDVI mensual | Suma de NDVI mensual × 30 días — proxy de producción de biomasa total |
| **Índice de aridez** | Temp. media/max/min + CHIRPS acum | Precipitación / ETP (Hargreaves). ETP = 0.0023 × (Tmedia+17.8) × √(Tmax−Tmin) × Ra × días. Valores <1 = déficit hídrico |

### Dependencias

```bash
pip install rasterio numpy
```

### Ejecución

```bash
# Generar todas las features
uv run procesamiento/03_feature_engineering.py

# Pasos individuales
uv run procesamiento/03_feature_engineering.py --step piso_termico
uv run procesamiento/03_feature_engineering.py --step amplitud_termica
uv run procesamiento/03_feature_engineering.py --step indice_fertilidad
uv run procesamiento/03_feature_engineering.py --step anomalia_precip
uv run procesamiento/03_feature_engineering.py --step ndvi_features
uv run procesamiento/03_feature_engineering.py --step indice_aridez
```

### Salida

```
processed/engineered/
├── piso_termico.tif                   # Estático (int8)
├── indice_fertilidad.tif              # Estático (float32)
├── amplitud_termica_2019A.tif         # Por semestre
├── anomalia_precip_2019A.tif          # Por semestre
├── ndvi_max_2019A.tif                 # Por semestre
├── ndvi_integral_2019A.tif            # Por semestre
└── indice_aridez_2019A.tif            # Por semestre
```

---

## Orden completo de procesamiento

```bash
# 1. Armonización espacial (mensual, 10 m, EPSG:3116)
uv run procesamiento/01_armonizar_espacial.py

# 2. Agregación temporal (mensual → estadísticos semestrales)
uv run procesamiento/02_armonizar_temporal.py

# 3. Feature engineering (features derivadas)
uv run procesamiento/03_feature_engineering.py

# 4. Vista minable (pendiente)
# uv run procesamiento/04_construir_vista_minable.py
```
