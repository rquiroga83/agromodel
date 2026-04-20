# Documento de Variables — Vista Minable AgroPlus

> **Fecha:** 16/04/2026  
> **Script:** `procesamiento/04_construir_vista_minable.py`  
> **Salida:** `vista_minable/vista_minable_full.parquet`

---

## Resumen Ejecutivo

La vista minable contiene **~40-50 features** por cada fila (pixel × semestre), organizados en 5 fuentes de datos. Se excluyeron **21 variables** por problemas críticos detectados en el análisis estadístico: cardinalidad extrema, alta correlación, datos faltantes severos, o redundancia con otras variables.

---

## 1. Estructura de la Vista Minable

| Componente | Columnas | Descripción |
|-----------|----------|-------------|
| **Metadatos** | `pixel_id`, `x`, `y`, `semestre` | Identificación única del registro |
| **Features estáticos** | ~17 | No cambian por semestre (suelo, topografía) |
| **Features semestrales** | ~18-27 | Varían cada semestre (clima, satélite) |
| **Target** | `cultivo`, `cultivo_id`, `confianza`, `fuente`, `rendimiento_tha` | Etiqueta de cultivo y rendimiento |

Cada fila = **un píxel de 50m × 50m en un semestre específico** del departamento de Cundinamarca.

---

## 2. Variables INCLUIDAS en la Vista Minable

### 2.1 Topográficas (DEM — fuente: NASA SRTM / Copernicus DEM)

| Variable | Columna | Unidad | Tipo | Fuente archivo |
|----------|---------|--------|------|----------------|
| Elevación | `elevacion` | m.s.n.m. | Continua | `processed/topo/dem_elevacion_50m.tif` |
| Pendiente | `pendiente` | grados | Continua | `processed/topo/dem_pendiente_50m.tif` |
| Índice Topográfico de Humedad | `twi` | adimensional | Continua | `processed/topo/dem_twi_50m.tif` |
| Aspecto seno | `aspecto_sin` | adimensional (-1 a 1) | Continua | `processed/engineered/aspecto_sin.tif` |
| Aspecto coseno | `aspecto_cos` | adimensional (-1 a 1) | Continua | `processed/engineered/aspecto_cos.tif` |

> **Nota:** El aspecto original (0-360°) se descompone en sin/cos para evitar la discontinuidad en 0°/360°.

### 2.2 Suelo — SoilGrids (fuente: ISRIC)

| Variable | Columna | Unidad | Profundidad | Tipo | Fuente archivo |
|----------|---------|--------|-------------|------|----------------|
| pH agua | `sg_phh2o` | pH×10 | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_phh2o_0_5cm.tif` |
| Carbono orgánico del suelo | `sg_soc` | g/kg | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_soc_0_5cm.tif` |
| Nitrógeno total | `sg_nitrogen` | cg/kg | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_nitrogen_0_5cm.tif` |
| Capacidad de intercambio catiónico | `sg_cec` | cmolc/kg | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_cec_0_5cm.tif` |
| Densidad aparente | `sg_bdod` | kg/dm³ | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_bdod_0_5cm.tif` |
| Arcilla normalizada | `sg_clay` | % (0-1) | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_clay_0_5cm_norm.tif` |
| Arena normalizada | `sg_sand` | % (0-1) | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_sand_0_5cm_norm.tif` |
| Limo normalizado | `sg_silt` | % (0-1) | 0-5 cm | Continua | `processed/suelo/soilgrids/soilgrids_silt_0_5cm_norm.tif` |

> **Nota:** Solo se usa la profundidad 0-5 cm (la más relevante para agricultura). Las texturas se cargan normalizadas (`_norm.tif`).

### 2.3 Suelo — IGAC (fuente: IGAC, Estudio General de Suelos)

| Variable | Columna | Clases | Tipo | Fuente archivo |
|----------|---------|--------|------|----------------|
| pH cualitativo | `igac_ph` | 6 categorías | Ordinal (int) | `processed/suelo/igac/igac_ph.tif` |
| Fósforo disponible | `igac_fosforo` | 5 categorías | Ordinal (int) | `processed/suelo/igac/igac_fosforo.tif` |
| Potasio disponible | `igac_potasio` | 5 categorías | Ordinal (int) | `processed/suelo/igac/igac_potasio.tif` |
| Fertilidad | `igac_fertilidad` | 7 categorías | Ordinal (int) | `processed/suelo/igac/igac_fertilidad.tif` |
| Vocación de uso | `igac_vocacion` | 8+ categorías | Nominal (int) | `processed/suelo/igac/igac_vocacion.tif` |

> **Nota:** Los IGAC se almacenan como enteros (códigos). Cada archivo tiene un `_tabla_codigos.json` asociado con el mapeo código → etiqueta.

### 2.4 Features Derivadas Estáticas (engineered)

| Variable | Columna | Descripción | Fuente |
|----------|---------|-------------|--------|
| Piso térmico | `piso_termico` | 0=Cálido(<1000m), 1=Templado, 2=Frío, 3=Páramo(>3000m) | `processed/engineered/piso_termico.tif` |
| Índice de fertilidad | `indice_fertilidad` | Índice compuesto de fertilidad del suelo | `processed/engineered/indice_fertilidad.tif` |

> **Estado:** Estas variables requieren que `03_feature_engineering.py` se ejecute primero. Si no existen, no se incluyen.

### 2.5 Clima — IDEAM (fuente: Estaciones IDEAM, interpolación IDW/kriging)

| Variable | Columna | Unidad | Frecuencia | Fuente archivo |
|----------|---------|--------|------------|----------------|
| Temperatura media | `temperatura_media` | °C | Semestral | `processed/temporal/clima/ideam/temperatura_media_{SEM}.tif` |
| Temperatura máxima | `temperatura_max` | °C | Semestral | `processed/temporal/clima/ideam/temperatura_max_{SEM}.tif` |
| Temperatura mínima | `temperatura_min` | °C | Semestral | `processed/temporal/clima/ideam/temperatura_min_{SEM}.tif` |
| Humedad relativa media | `humedad_media` | % | Semestral | `processed/temporal/clima/ideam/humedad_media_{SEM}.tif` |

### 2.6 Clima — CHIRPS (fuente: Climate Hazards Group, satélite+pluviómetros)

| Variable | Columna | Unidad | Frecuencia | Fuente archivo |
|----------|---------|--------|------------|----------------|
| Precipitación acumulada | `chirps_acum` | mm | Semestral | `processed/temporal/clima/chirps/chirps_acum_{SEM}.tif` |

### 2.7 Satélite — Sentinel-2 (fuente: ESA, reflectancia multiespectral)

| Variable | Columna | Tipo | Frecuencia | Fuente archivo |
|----------|---------|------|------------|----------------|
| NDVI media | `s2_ndvi_media` | Continua | Semestral | `processed/temporal/satelite/sentinel2/` |
| NDVI máximo | `s2_ndvi_max` | Continua | Semestral | |
| NDVI std | `s2_ndvi_std` | Continua | Semestral | |
| GNDVI media | `s2_gndvi_media` | Continua | Semestral | |
| GNDVI máximo | `s2_gndvi_max` | Continua | Semestral | |
| GNDVI std | `s2_gndvi_std` | Continua | Semestral | |
| MSAVI media | `s2_msavi_media` | Continua | Semestral | |
| MSAVI máximo | `s2_msavi_max` | Continua | Semestral | |
| MSAVI std | `s2_msavi_std` | Continua | Semestral | |
| BSI media | `s2_bsi_media` | Continua | Semestral | |
| BSI máximo | `s2_bsi_max` | Continua | Semestral | |
| BSI std | `s2_bsi_std` | Continua | Semestral | |
| SAVI media | `s2_savi_media` | Continua | Semestral | |
| SAVI máximo | `s2_savi_max` | Continua | Semestral | |
| SAVI std | `s2_savi_std` | Continua | Semestral | |

> **Nota:** 5 índices × 3 estadísticos (media, max, std) = **15 variables Sentinel-2** por semestre.

### 2.8 Features Derivadas Semestrales (engineered)

| Variable | Columna | Descripción | Fuente |
|----------|---------|-------------|--------|
| Amplitud térmica | `amplitud_termica` | tmax - tmin (°C) | `processed/engineered/` |
| Anomalía precipitación | `anomalia_precip` | Desviación de CHIRPS vs media histórica | `processed/engineered/` |
| NDVI máximo | `ndvi_max` | NDVI máximo del semestre | `processed/engineered/` |
| Integral NDVI | `ndvi_integral` | Suma NDVI sobre umbral (proxy productividad) | `processed/engineered/` |
| Índice de aridez | `indice_aridez` | Precipitación / Evapotranspiración potencial | `processed/engineered/` |

> **Estado:** Requieren `03_feature_engineering.py`. Si no existen, no se incluyen.

### 2.9 Variables Target

| Variable | Columna | Descripción |
|----------|---------|-------------|
| Cultivo | `cultivo` | Nombre del cultivo (string) |
| ID cultivo | `cultivo_id` | Entero (label encoding) |
| Confianza | `confianza` | 0.0-1.0 (monitoreo=1.0, EVA=0.7, SIPRA=0.5) |
| Fuente | `fuente` | "monitoreo", "eva", o "sipra" |
| Rendimiento | `rendimiento_tha` | Toneladas por hectárea (de EVA) |

---

## 3. Variables EXCLUIDAS de la Vista Minable

### 3.1 Excluidas por Problemas Críticos

| # | Variable | Fuente | Razón de exclusión | Severidad |
|---|----------|--------|-------------------|-----------|
| 1 | `igac_subgrupo` | IGAC | **Cardinalidad extrema:** 1109 clases de taxonomía USDA Soil Taxonomy. One-hot = 1109 columnas (maldición de dimensionalidad). Redundante con propiedades de suelo ya incluidas (SoilGrids + IGAC químicas). | 🔴 Crítica |
| 2 | `igac_ucsuelo` | IGAC | **Cardinalidad alta:** ~500+ unidades cartográficas de suelo. Misma problemática que subgrupo. | 🔴 Crítica |
| 3 | `igac_clima` | IGAC | **Redundancia:** ~34 clases climáticas (Holdridge/etc). Ya cubierto por variables IDEAM + CHIRPS con datos continuos y más precisos. | 🟡 Moderada |
| 4 | `igac_paisaje` | IGAC | **Redundancia:** ~20 tipos de paisaje. Ya capturado por topografía (elevación, pendiente, TWI). | 🟡 Moderada |
| 5 | `igac_material` | IGAC | **Irrelevante:** ~15 tipos de material parental. No afecta directamente la productividad del cultivo. | 🟡 Moderada |
| 6 | `igac_relieve` | IGAC | **Redundancia:** ~10 tipos de relieve. Ya capturado por pendiente, elevación y TWI. | 🟡 Moderada |
| 7 | `igac_calificacion` | IGAC | **Redundancia:** ~10 clases de calificación general. Redundante con `igac_fertilidad` e `indice_fertilidad`. | 🟡 Moderada |
| 8 | `igac_suma_bases` | IGAC | **Correlación:** Suma de bases intercambiables. Altamente correlacionado con CEC (`sg_cec`) y `igac_fertilidad`. | 🟡 Moderada |
| 9 | `s2_evi` (EVI) | Sentinel-2 | **Alta correlación con NDVI:** r > 0.95. NDVI es más estable y ampliamente validado. No aporta información diferencial. | 🔴 Crítica |
| 10 | `s2_ndwi` (NDWI) | Sentinel-2 | **Redundancia:** Mide contenido de agua en vegetación. Ya cubierto por humedad IDEAM + CHIRPS + índice de aridez. | 🟡 Moderada |
| 11 | `dem_curvatura` | DEM | **Sin poder discriminante:** Distribución casi uniforme centrada en 0. Desviación estándar ≈ 0. No permite diferenciar cultivos. | 🔴 Crítica |
| 12 | `soilgrids_ocd_*` | SoilGrids | **Correlación alta con SOC:** r > 0.9. Densidad de carbono orgánico es redundante con stock de carbono orgánico (`sg_soc`). | 🟡 Moderada |
| 13 | `dem_cundinamarca_50m` | DEM | **Alias:** Duplicado de `dem_elevacion_50m.tif`. Ya incluido como `elevacion`. | 🟢 Menor |

### 3.2 Excluidas por diseño (nunca se incluyeron)

| # | Variable/Grupo | Fuente | Razón |
|---|----------------|--------|-------|
| 14 | `soilgrids_*_5_15cm` | SoilGrids | Solo se usa profundidad 0-5 cm (la más relevante para agricultura). Profundidades mayores no se procesan. |
| 15 | `soilgrids_*_15_30cm` | SoilGrids | Ídem anterior. |
| 16 | `soilgrids_{clay,sand,silt}_0_5cm.tif` (raw) | SoilGrids | Solo se usan las versiones normalizadas (`_norm.tif`). Las raw tienen valores en g/kg (0-1000%) que no suman 100%. |
| 17 | `dem_aspecto_50m` | DEM | El aspecto circular (0-360°) se descompone en `aspecto_sin` y `aspecto_cos` para evitar la discontinuidad. |
| 18 | `ideam_precipitacion_acum` | IDEAM | **100% ceros:** La interpolación kriging de estaciones de precipitación falló. Se usa CHIRPS como reemplazo. |
| 19 | Sentinel-1 (VV, VH, VH/VV ratio) | Sentinel-1A/B | **53% datos faltantes:** Sentinel-1B falló en dic 2021. Para 2022-2025 solo hay datos parciales. Redundante con Sentinel-2 + IDEAM. |

### 3.3 Resumen de exclusión por categoría

| Categoría | Total original | Incluidas | Excluidas |
|-----------|---------------|-----------|-----------|
| IGAC suelo | 13 variables | 5 | 8 |
| SoilGrids | 6 props × 1 depth + 3 textures | 8 | 1 (ocd) + no incluidas (depths 5-15, 15-30, raw textures) |
| Topografía | 5 (elev, pend, curv, twi, aspecto) | 4 + 2 engineered | 1 (curvatura) + 1 (aspecto → sin/cos) |
| Sentinel-2 | 7 índices × 3 stats = 21 | 5 × 3 = 15 | 2 × 3 = 6 (EVI, NDWI) |
| Sentinel-1 | 3 bandas | 0 | 3 |
| IDEAM clima | 5 variables | 4 | 1 (precipitación fallida) |
| CHIRPS | 1 | 1 | 0 |
| Engineered | 7 | 2 existentes + 5 pendientes | 0 |
| **TOTAL** | **~70+** | **~40-50** | **~21+** |

---

## 4. Validación del Script

### 4.1 Función `_definir_capas_estaticas()` — ✅ Correcto

```
Topográficas:      elevacion, pendiente, twi               (3 variables)
SoilGrids props:   sg_phh2o, sg_soc, sg_nitrogen, sg_cec, sg_bdod  (5 variables)
SoilGrids text:    sg_clay, sg_sand, sg_silt                (3 variables)
IGAC:              igac_ph, igac_fosforo, igac_potasio,     (5 variables)
                   igac_fertilidad, igac_vocacion
Engineered:        piso_termico, indice_fertilidad,         (4 variables)
                   aspecto_sin, aspecto_cos
                   ─────────────────────────────────
                   Total estáticas: 20 variables
```

### 4.2 Función `_definir_capas_semestrales()` — ✅ Correcto

```
IDEAM:             temperatura_media, temperatura_max,      (4 variables)
                   temperatura_min, humedad_media
CHIRPS:            chirps_acum                              (1 variable)
Sentinel-2:        5 índices × 3 stats = 15                (15 variables)
Engineered:        amplitud_termica, anomalia_precip,       (5 variables)
                   ndvi_max, ndvi_integral, indice_aridez
                   ─────────────────────────────────
                   Total semestrales: 25 variables
```

### 4.3 Constantes de exclusión aplicadas

| Constante | Variables | Dónde se aplica |
|-----------|-----------|-----------------|
| `EXCLUIR_CAPAS` | dem_cundinamarca + 8 IGAC | Filtro en glob IGAC |
| `S2_INDICES_EXCLUIR` | evi, ndwi | No usada directamente (se removió del loop) |
| `TOPO_EXCLUIR` | curvatura | No usada directamente (se removió del loop) |
| `SOILGRIDS_PROPS_EXCLUIR` | ocd | No usada directamente (se removió del list) |

> **Nota:** Las constantes documentan la razón de exclusión. La exclusión real se implementa removiendo las variables de los loops explícitos en `_definir_capas_estaticas()` y `_definir_capas_semestrales()`.

### 4.4 Verificación de archivos fuente

| Directorio | Archivos esperados | Estado |
|------------|-------------------|--------|
| `processed/topo/` | dem_elevacion_50m, dem_pendiente_50m, dem_twi_50m | ✅ Existen |
| `processed/suelo/soilgrids/` | soilgrids_{phh2o,soc,nitrogen,cec,bdod}_0_5cm + textures norm | ✅ Existen |
| `processed/suelo/igac/` | 13 archivos igac_*.tif (5 incluidos, 8 excluidos) | ✅ Existen |
| `processed/engineered/` | aspecto_sin.tif, aspecto_cos.tif | ✅ Existen |
| `processed/engineered/` | piso_termico, indice_fertilidad | ⚠️ Pendiente (requiere 03_feature_engineering.py) |
| `processed/temporal/clima/ideam/` | temperaturas + humedad por semestre | ✅ Existen |
| `processed/temporal/clima/chirps/` | chirps_acum por semestre | ✅ Existen |
| `processed/temporal/satelite/sentinel2/` | s2_{indice}_{agg}_{sem}.tif | ✅ Existen |
| `processed/engineered/` (temporal) | amplitud_termica_*, anomalia_precip_*, etc. | ⚠️ Pendiente |

---

## 5. Tratamiento Recomendado por Variable

### 5.1 Variables categóricas IGAC (requieren encoding)

| Variable | Método recomendado | Notas |
|----------|-------------------|-------|
| `igac_ph` | Ordinal encoding (1-6) | Ya es ordinal natural (muy ácido → neutro-alkalino) |
| `igac_fosforo` | Ordinal encoding (1-5) | Orden natural (muy bajo → muy alto) |
| `igac_potasio` | Ordinal encoding (1-5) | Orden natural (muy bajo → muy alto) |
| `igac_fertilidad` | Ordinal encoding (1-7) | Índice compuesto ordinal |
| `igac_vocacion` | One-hot o target encoding | Nominal, sin orden natural |
| `piso_termico` | Ordinal encoding (0-3) | Ya es ordinal (cálido → páramo) |

### 5.2 Variables continuas (requieren normalización)

| Variables | Método recomendado | Notas |
|-----------|-------------------|-------|
| `sg_*` (SoilGrids) | StandardScaler | Distribuciones aproximadamente normales |
| `elevacion`, `pendiente` | StandardScaler | Rangos muy diferentes |
| `temperatura_*`, `chirps_acum` | StandardScaler | Estacionales, diferente escala |
| `s2_*` (índices espectrales) | MinMaxScaler o StandardScaler | Rango acotado [-1, 1] o similar |

### 5.3 Variables con NaN esperados

| Variable | % NaN esperado | Tratamiento |
|-----------|---------------|-------------|
| Sentinel-1 (si se reactiva) | ~53% | **No reactivar** hasta tener más datos |
| IDEAM humedad/presión | ~5-15% | Imputar con media por piso térmico |
| s2_*_std | ~2-5% | NaN donde solo hay 1 observación → imputar con 0 |
| `rendimiento_tha` | ~40-60% | Solo disponible para fuente=monitoreo/eva. No imputar. |

---

## 6. Próximos Pasos

1. **Ejecutar `03_feature_engineering.py`** para generar las variables derivadas faltantes:
   - `piso_termico.tif`
   - `indice_fertilidad.tif`
   - `amplitud_termica_{SEM}.tif`
   - `anomalia_precip_{SEM}.tif`
   - `ndvi_max_{SEM}.tif`
   - `ndvi_integral_{SEM}.tif`
   - `indice_aridez_{SEM}.tif`

2. **Ejecutar `04_construir_vista_minable.py`** para generar el parquet final.

3. **Validar resultados:** Verificar NaN %, distribución de target, y correlaciones post-extracción.

---

## Historial de Cambios

| Fecha | Cambio | Archivo |
|-------|--------|---------|
| 16/04/2026 | Exclusión de 8 variables IGAC (subgrupo, ucsuelo, clima, paisaje, material, relieve, calificacion, suma_bases) | `04_construir_vista_minable.py` |
| 16/04/2026 | Exclusión de EVI y NDWI de Sentinel-2 | `04_construir_vista_minable.py` |
| 16/04/2026 | Exclusión de dem_curvatura | `04_construir_vista_minable.py` |
| 16/04/2026 | Exclusión de soilgrids_ocd | `04_construir_vista_minable.py` |
| 16/04/2026 | Exclusión previa de Sentinel-1 (53% NaN) | `04_construir_vista_minable.py` |
| 16/04/2026 | Exclusión previa de IDEAM precipitación (100% ceros) | `02_armonizar_temporal.py` |