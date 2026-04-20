# Informe de Análisis Estadístico - Datos Procesados para Vista Minable
## Proyecto: ¿Qué Sembrar? - AgroPlus
### Fecha: 16/04/2026

---

## RESUMEN EJECUTIVO

Se analizaron **~74 variables** en los datos procesados (`processed/`) incluyendo topografía, suelo (SoilGrids + IGAC), clima (IDEAM + CHIRPS) y satélite (Sentinel-1/2). Se identificaron **12 alertas críticas**, **8 alertas altas** y **6 alertas medias** que requieren atención antes de construir la vista minable.

---

## 1. ALERTAS CRÍTICAS 🚨

### 1.1 IDEAM Precipitación: 100% CEROS (VARIABLE ROTA)
| Mes | mean | std | % ceros |
|-----|------|-----|---------|
| 2020_01 | 0.000 | 0.000 | **100%** |
| 2020_07 | 0.000 | 0.000 | **100%** |
| 2021_01 | 0.004 | 0.009 | 0.0% |
| 2021_07 | 0.000 | 0.000 | **100%** |
| 2022_01 | 0.000 | 0.000 | **100%** |
| 2022_07 | 0.000 | 0.000 | **100%** |
| 2023_01 | 0.000 | 0.000 | **100%** |
| 2023_07 | 0.000 | 0.000 | **100%** |
| 2024_01 | 0.000 | 0.000 | **100%** |

**Diagnóstico**: La interpolación kriging de precipitación FALLÓ para casi todos los meses. Solo 2021_01 tiene datos no-ceros (y son valores minúsculos ~0.004 mm). Esto indica que el extractor IDEAM o el proceso de kriging tiene un bug grave para precipitación.

**Acción**: 
- **EXCLUIR** `ideam_precipitacion` de la vista minable
- **USAR CHIRPS** como fuente de precipitación (está completa y con valores realistas)
- Revisar el extractor `01_extraer_clima_ideam.py` y el script `01_armonizar_espacial.py`

### 1.2 EVI (Sentinel-2): Valores Extremos / Overflow
| Mes | mean | std | min | max |
|-----|------|-----|-----|-----|
| 2020_01/EVI | 0.4541 | 0.4005 | -1,065 | 428 |
| 2021_07/EVI | **-155.2** | **262,861** | **-714,365,568** | 4,246 |
| 2022_01/EVI | **54.03** | **457,702** | **-345,602,080** | **1,851,621,888** |
| 2022_07/EVI | **-146.4** | **461,575** | **-1,450,000,000** | 1,343 |
| 2023_01/EVI | **-44.77** | **96,732** | **-360,498,208** | 2,812 |

**Diagnóstico**: EVI tiene overflow/división por cero masivo. El rango esperado es [-1, 1]. Valores de cientos de millones indican un **bug en el evalscript de Sentinel-2** (división por NIR+canopy cuando ambos son ~0).

**Acción**:
- **EXCLUIR EVI** hasta corregir el evalscript
- Agregar protección `if (NIR + canopy) < 0.01: EVI = NoData` 
- Los índices NDVI, GNDVI, MSAVI, SAVI, BSI sí parecen correctos

### 1.3 NDWI = -GNDVI (REDUNDANCIA EXACTA)
```
GNDVI mean=0.6232, std=0.1444, range=[-1, 1]
NDWI mean=-0.6232, std=0.1444, range=[-1, 1]
```
**Diagnóstico**: NDWI es exactamente el negativo de GNDVI en todos los meses analizados. Esto significa que la fórmula del NDWI está calculando `-(GNDVI)` o `(Green-NIR)/(Green+NIR)` en vez de `(Green-SWIR)/(Green+SWIR)`.

**Acción**: 
- **EXCLUIR NDWI** de la vista minable (es redundante con GNDVI)
- Corregir el evalscript para usar la banda SWIR (B11) en vez de NIR

### 1.4 `dem_cundinamarca_50m.tif` = `dem_elevacion_50m.tif` (DUPLICADO)
```
dem_cundinamarca: mean=1665.605, std=1118.764, range=[149.132, 4216.166]
dem_elevacion:    mean=1665.605, std=1118.764, range=[149.132, 4216.166]
```
**Diagnóstico**: Ambas capas son idénticas. `dem_cundinamarca` es el DEM original y `dem_elevacion` es una copia sin renombrar.

**Acción**: **EXCLUIR** `dem_cundinamarca_50m.tif`, mantener solo `dem_elevacion_50m.tif`

### 1.5 Sentinel-1: 3 Años Sin Datos Válidos (2022-2025)

| Período | VV_dB | VH_dB | VH_VV_ratio |
|---------|-------|-------|-------------|
| 2020_01-2021_07 | ✅ Normal (mean VV≈-9dB) | ✅ Normal | ✅ Normal |
| 2022_01 - 2025_01 | **0% datos válidos** | **0% datos válidos** | **0% datos válidos** |
| 2025_07 | ✅ Normal | ✅ Normal | ✅ Normal |

**Diagnóstico**: Sentinel-1 no tiene datos válidos para 24 de 36 meses muestreados (2022-01 a 2025-01). Solo hay datos para 2020, 2021 y 2025_07. Esto puede ser un problema en el extractor o en la armonización espacial.

**Acción**: 
- Verificar si `raw/sentinel1/` tiene datos para 2022-2025
- Si hay datos raw, el problema está en `01_armonizar_espacial.py`
- Si no hay datos raw, hay que re-ejecutar el extractor Sentinel-1
- Para la vista minable, solo usar Sentinel-1 de 2020-2021 y 2025_07

### 1.6 `processed/temporal/` VACÍO
**Diagnóstico**: El directorio `processed/temporal/` no tiene archivos. Esto significa que `02_armonizar_temporal.py` no generó salida.

**Acción**: Ejecutar/depurar `02_armonizar_temporal.py` antes de construir la vista minable.

### 1.6 SoilGrids: Valores en Unidades x10
Los SoilGrids reportan valores multiplicados por 10:
- **pH**: mean=52.193 → pH real = **5.2** (correcto para Cundinamarca)
- **CEC**: mean=235.674 → CEC real = **23.6 cmol/kg**
- **Nitrogen**: mean=435.350 → N real = **4.35 g/kg** → 0.435 dag/kg
- **SOC**: mean=705.950 → SOC real = **70.6 g/kg** → 7.06 dag/kg
- **BDOD**: mean=102.238 → bdod real = **1.02 g/cm³** (100 = kg/dm³)

**Acción**: En `03_feature_engineering.py`, dividir por 10 las variables de SoilGrids para obtener valores reales. Documentar las unidades.

---

## 2. ALERTAS ALTAS ⚠️

### 2.1 IDEAM Humedad: Meses con Varianza Casi Cero
| Mes | mean | std | Diagnóstico |
|-----|------|-----|-------------|
| 2020_01 | 71.022 | 0.139 | Normal |
| 2020_07 | 67.125 | **0.001** | Kriging colapsó a constante |
| 2022_01 | 76.438 | **0.005** | Kriging colapsó |
| 2022_07 | 80.421 | **0.003** | Kriging colapsó |
| 2023_01 | 78.838 | **0.001** | Kriging colapsó |

**Diagnóstico**: Varios meses de humedad tienen variación espacial casi nula (std < 0.01), indicando que el kriging colapsó a un valor constante. Esto ocurre cuando hay muy pocas estaciones con datos para ese mes.

**Acción**: Imputar estos meses con la media anual o interpolar temporalmente desde meses adyacentes.

### 2.2 Pendiente: Valores > 100%
```
dem_pendiente: max=244.619 (rango esperado: 0-100%)
```
**Diagnóstico**: Pendientes > 100% son geométricamente posibles (cliffs > 45°) pero el valor 244% sugiere un artefacto del cálculo en pendientes muy escarpadas.

**Acción**: Revisar la fórmula. Si está en grados, convertir a porcentaje con `tan(slope_deg) * 100`. Si está en radianes, el valor es incorrecto.

### 2.3 Sentinel-2: Alta Nubosidad en Julio
| Mes | % Válido | % NoData |
|-----|----------|----------|
| 2020_01 | 97.0% | 3.0% |
| 2020_07 | 54.1% | **45.9%** |
| 2021_01 | 92.7% | 7.3% |
| 2021_07 | 60.1% | **39.9%** |
| 2022_01 | 90.9% | 9.1% |
| 2022_07 | 51.3% | **48.7%** |
| 2023_01 | 88.3% | 11.7% |
| 2023_07 | 43.4% | **56.6%** |

**Diagnóstico**: Los meses de julio (temporada de lluvias/seca según zona) tienen consistentemente 40-57% de NoData, probablemente por nubosidad. Los meses de enero tienen 3-12% NoData.

**Acción**: En `02_armonizar_temporal.py`, al agregar semestralmente, los píxeles con NoData se deben excluir del cálculo de estadísticos (no imputar con 0).

### 2.4 IGAC Vocación: 50.3% NoData
```
igac_vocacion: n=9,474,809 (49.7% válido), 50.3% NoData
```
**Diagnóstico**: La mitad de los píxeles no tienen dato de vocación de uso del suelo IGAC. Esto es esperado porque el IGAC no cubre todas las áreas del departamento (zonas urbanas, páramos, bosques protectores no tienen vocación agrícola asignada).

**Tratamiento**: 
- **No excluir** la variable — la vocación es relevante donde existe
- Tratar NoData como categoría "Sin información" (código 0)
- En `03_feature_engineering.py`, reemplazar NoData (-1 o nodata) con 0 antes de normalizar
- Los modelos basados en árboles (RF, XGBoost, LightGBM) manejan bien esta categoría adicional
- Si se usa one-hot encoding, la categoría 0 ("Sin información") será una columna binaria más

### 2.5 Aspecto: Valor -1 (Áreas Planas)
```
dem_aspecto: min=-1.000 (debería ser 0-360)
```
**Diagnóstico**: El valor -1 es el estándar GDAL para indicar "aspecto indefinido" en áreas planas (pendiente = 0°). No es un error — es el comportamiento correcto de `gdaldem aspect`. En Cundinamarca, las zonas planas (valles del Magdalena, sabana de Bogotá) tienen pendiente ≈ 0 y por tanto aspecto = -1.

**Tratamiento**: 
- **No excluir** la variable — el aspecto es importante para insolación y vientos
- En `03_feature_engineering.py`, aplicar **descomposición circular**:
  - `aspecto_sin = sin(aspecto × π/180)` → para píxeles planos (-1), asignar 0
  - `aspecto_cos = cos(aspecto × π/180)` → para píxeles planos (-1), asignar 0
- Esto convierte una variable circular (0-360°) en dos variables lineales continuas
- Los píxeles planos quedan codificados como (sin=0, cos=0), lo cual es correcto (sin dirección preferida)
- **Descartar** la columna `aspecto` original de la vista minable, usar solo `aspecto_sin` y `aspecto_cos`

---

## 3. ALERTAS MEDIAS 📋

### 3.1 SoilGrids: ~1.1% Ceros en Todas las Variables (NoData sin marcar)

| Variable | % Ceros | Valor Mínimo Válido (después de excluir ceros) |
|----------|---------|------------------------------------------------|
| phh2o | 1.1% | pH=0 → **inválido** (rango real: 3.5–6.7) |
| soc | 1.1% | SOC=0 → **inválido** (siempre hay carbono orgánico) |
| nitrogen | 1.1% | N=0 → **inválido** (siempre hay nitrógeno) |
| cec | 1.1% | CEC=0 → **inválido** (siempre hay capacidad de intercambio) |
| bdod | 1.2% | bdod=0 → **inválido** (densidad siempre > 0) |
| ocd | 1.1% | OCD=0 → **inválido** |

**Diagnóstico**: Todas las variables SoilGrids tienen exactamente ~1.1% de ceros, lo que indica una **zona espacial consistente** donde SoilGrids no tiene datos y codificó como 0 en vez de NoData. SoilGrids 250 m tiene gaps en zonas con escasas calicatas de referencia (probablemente zonas de páramo o áreas urbanas).

**Impacto**: pH=0, SOC=0, N=0 son **físicamente imposibles**. Si se pasan al modelo, los árboles de decisión podrían crear reglas como "si pH < 5 → cultivo X", y los píxeles con pH=0 serían mal clasificados.

**Tratamiento**:
- En `03_feature_engineering.py` o `04_construir_vista_minable.py`:
  1. **Reemplazar 0 → NaN** para todas las variables SoilGrids (excepto clay_norm/sand_norm/silt_norm que ya están limpias)
  2. **Imputar con mediana espacial**: usar un kernel de 3×3 píxeles para rellenar los NaN con la mediana de vecinos válidos
  3. Si quedan NaN residuales (píxeles aislados), imputar con la mediana global de Cundinamarca
- **No excluir** las variables — 98.9% de los datos son válidos
- Las versiones `_norm` (clay, sand, silt) **no tienen ceros** — ya fueron limpiadas en `01_armonizar_espacial.py`

### 3.3 IGAC Subgrupo: Alta Cardinalidad
```
igac_subgrupo: 100.0% válido, mean=600.876, range=[27, 1106]
```
Posiblemente cientos de clases únicas. Para la vista minable, considerar agrupar o usar one-hot encoding selectivo.

---

## 4. VARIABLES CORRELACIONADAS ESPERADAS

Basado en la naturaleza de los datos, se esperan estas correlaciones:

| Par | Correlación Esperada | Acción |
|-----|---------------------|--------|
| NDVI ↔ GNDVI | r > 0.95 | Mantener solo **NDVI** |
| MSAVI ↔ SAVI | r > 0.90 | Mantener solo **MSAVI** |
| NDVI ↔ MSAVI | r > 0.85 | Mantener ambos (captan aspectos diferentes) |
| elevación ↔ temperatura | r < -0.90 | Mantener ambas (no lineal) |
| IGAC_pH ↔ SoilGrids_pH | r > 0.70 | Mantener IGAC_pH (más local) |
| SOC ↔ Nitrogen | r > 0.85 | Mantener ambos por ahora |
| clay ↔ sand | r < -0.85 | Mantener solo **clay_norm** (más relevante agronómicamente) |
| IGAC_subgrupo ↔ IGAC_ucsuelo | r > 0.80 | Mantener **subgrupo** (más agregado) |
| OCD ↔ SOC | r > 0.90 | **EXCLUIR OCD** (derivado de SOC × bdod) |

---

## 5. VARIABLES A EXCLUIR DE LA VISTA MINABLE

### EXCLUIR (Problemas Críticos):
| Variable | Razón |
|----------|-------|
| `ideam_precipitacion` | 100% ceros - interpolación fallida |
| `sentinel2/EVI` | Overflow/valores extremos - bug en evalscript |
| `sentinel2/NDWI` | Redundante con GNDVI (NDWI = -GNDVI) |
| `dem_cundinamarca_50m` | Duplicado exacto de dem_elevacion_50m |
| `soilgrids_*_5_15cm` | No usar para vista minable (solo 0_5cm) |
| `soilgrids_*_15_30cm` | No usar para vista minable (solo 0_5cm) |
| `soilgrids_{clay,sand,silt}_*_0_5cm.tif` | Usar versiones `_norm` |
| `soilgrids_ocd_*` | Redundante con SOC (OCD = SOC × bdod) |
| `dem_curvatura` | Varianza casi cero (std=0.002) |
| `sentinel1/*` | **EXCLUIDO** — 53% datos faltantes (2022-2025), redundante con S2/CHIRPS |

### EXCLUIR por Redundancia:
| Variable | Mantener en su lugar |
|----------|---------------------|
| `sentinel2/GNDVI` | NDVI (más establecido) |
| `sentinel2/SAVI` | MSAVI (más robusto) |
| `igac_ucsuelo` | igac_subgrupo (más agregado) |

---

## 6. ESTRUCTURA FINAL SUGERIDA DE LA VISTA MINABLE

### Columnas de Identificación (6):
```
pixel_id, row, col, lon, lat, semestre
```

### Features Estáticos (~18 variables):
| Grupo | Variables | Cantidad |
|-------|-----------|----------|
| **Topografía** | elevacion, pendiente, twi, aspecto_sin, aspecto_cos | 5 |
| **SoilGrids 0-5cm** | phh2o, soc, nitrogen, cec, bdod, clay_norm | 6 |
| **IGAC** | ph, fosforo, potasio, fertilidad, vocacion | 5 |
| **Derivados** | piso_termico | 1 |

### Features Dinámicos por Semestre (~14 variables):
| Grupo | Variables | Cantidad |
|-------|-----------|----------|
| **IDEAM Clima** | temp_media, temp_max, temp_min, humedad_media | 4 |
| **CHIRPS** | precip_acum | 1 |
| **Sentinel-2** | NDVI_mean, NDVI_max, NDVI_std, MSAVI_mean, BSI_mean | 5 |
| **Derivados** | amplitud_termica, anomalia_precip, ndvi_max, ndvi_integral, indice_aridez | 5 |

### Target (4):
```
cultivo_id, cultivo_nombre, confianza_label, fuente_label
```

### **TOTAL: ~43-49 features** (reducido de ~74 originales)

---

## 7. RECOMENDACIONES DE TRATAMIENTO

### 7.1 Transformaciones Necesarias:
1. **Aspecto circular**: `aspecto_sin = sin(aspecto × π/180)`, `aspecto_cos = cos(aspecto × π/180)`
2. **SoilGrids ÷ 10**: phh2o, soc, nitrogen, cec, bdod dividir por 10 para obtener valores reales
3. **IGAC categóricas**: One-hot encoding para fertilidad (7 clases), vocacion (8 clases), ph (6 clases)
4. **Normalización**: StandardScaler para variables continuas antes del modelo

### 7.2 Imputación:
- **SoilGrids ceros**: Reemplazar 0 → NaN → imputar con mediana espacial
- **IGAC vocación NoData**: Crear categoría "Sin dato" (código 0)
- **Sentinel-2 NoData por nubes**: Excluir del cálculo semestral (no rellenar con 0)
- **IDEAM humedad constante**: Interpolar temporalmente desde meses adyacentes

### 7.3 Orden de Ejecución:
1. ✅ `01_armonizar_espacial.py` (ya ejecutado)
2. ❌ `02_armonizar_temporal.py` (FALTA - temporal/ está vacío)
3. 🔧 Corregir evalscript de Sentinel-2 (EVI overflow, NDWI formula)
4. 🔧 Revisar kriging de precipitación IDEAM
5. ⏳ `03_feature_engineering.py`
6. ⏳ `04_construir_vista_minable.py`

---

## 8. ESTADÍSTICAS DETALLADAS POR VARIABLE

### Topografía:
| Variable | n | % Válido | Mean | Std | Min | Max | % Ceros |
|----------|---|----------|------|-----|-----|-----|---------|
| elevacion | 19,028,195 | 99.9% | 1665.6 | 1118.8 | 149.1 | 4216.2 | 0.0% |
| pendiente | 19,028,195 | 99.9% | 20.2 | 17.0 | 0.0 | 244.6 | 0.1% |
| aspecto | 19,028,195 | 99.9% | 174.1 | 91.1 | -1.0 | 359.9 | 0.0% |
| curvatura | 19,028,195 | 99.9% | -0.000 | 0.002 | -0.022 | 0.021 | 0.1% |
| twi | 19,028,195 | 99.9% | 4.7 | 4.6 | 2.3 | 31.5 | 0.0% |

### SoilGrids 0-5cm (valores en unidades SoilGrids, ÷10 para reales):
| Variable | n | % Válido | Mean | Std | Min | Max | % Ceros |
|----------|---|----------|------|-----|-----|-----|---------|
| phh2o | 19,029,172 | 99.9% | 52.2 | 7.0 | 0 | 67 | 1.1% |
| soc | 19,029,172 | 99.9% | 706.0 | 266.2 | 0 | 1891 | 1.1% |
| nitrogen | 19,029,172 | 99.9% | 435.4 | 129.1 | 0 | 927 | 1.1% |
| cec | 19,029,172 | 99.9% | 235.7 | 64.0 | 0 | 738 | 1.1% |
| bdod | 19,029,172 | 99.9% | 102.2 | 18.7 | 0 | 149 | 1.2% |
| ocd | 19,029,172 | 99.9% | 508.8 | 108.6 | 0 | 782 | 1.1% |
| clay_norm | 18,695,586 | 98.2% | 32.1 | 4.4 | 16 | 49 | 0.0% |
| sand_norm | 18,695,586 | 98.2% | 34.7 | 5.4 | 3 | 51 | 0.0% |
| silt_norm | 18,695,586 | 98.2% | 31.8 | 3.3 | 20 | 57 | 0.0% |

### IGAC:
| Variable | n | % Válido | Mean | N Clases | Clase Dominante | % Dominante |
|----------|---|----------|------|----------|-----------------|-------------|
| ph | 19,046,027 | 100% | 1.34 | ~6 | - | - |
| fosforo | 19,046,027 | 100% | 1.17 | ~5 | - | - |
| potasio | 19,046,027 | 100% | 1.30 | ~5 | - | - |
| fertilidad | 19,046,027 | 100% | 2.79 | 7 | - | - |
| vocacion | 9,474,809 | **49.7%** | 5.58 | 8 | - | - |
| clima | 19,046,027 | 100% | 9.70 | ~34 | - | - |
| subgrupo | 19,046,027 | 100% | 600.9 | ~muchas | - | - |

### Clima Mensual (Muestra):
| Variable | Mes | Mean | Std | Observación |
|----------|-----|------|-----|-------------|
| temp | 2020_01 | 8.5°C | 11.3 | Normal |
| temp | 2020_07 | 6.6°C | 9.3 | Normal |
| precip IDEAM | Todos | **0.000** | 0.000 | **ROTO** |
| precip CHIRPS | 2020_01 | 41.2mm | 13.3 | ✅ Normal |
| precip CHIRPS | 2020_07 | 231.4mm | 165.7 | ✅ Normal |
| humedad | 2020_01 | 71.0% | 0.14 | Normal |
| humedad | 2020_07 | 67.1% | **0.001** | ⚠️ Constante |

### Sentinel-2 (Muestra):
| Variable | 2020_01 Mean | 2020_07 Mean | Rango Válido | Observación |
|----------|-------------|-------------|--------------|-------------|
| NDVI | 0.673 | 0.636 | [-1, 1] | ✅ Normal |
| GNDVI | 0.623 | 0.561 | [-1, 1] | ✅ Normal |
| EVI | 0.454 | 0.515 | [-1065, 7135] | ❌ **OVERFLOW** |
| NDWI | -0.623 | -0.561 | [-1, 1] | ⚠️ = -GNDVI |
| MSAVI | 0.401 | 0.421 | [-0.31, 0.97] | ✅ Normal |
| BSI | -0.137 | -0.167 | [-0.81, 0.98] | ✅ Normal |
| SAVI | 0.410 | 0.423 | [-0.35, 0.97] | ✅ Normal |

---

*Informe generado automáticamente por `notebooks/analisis_estadistico_vista_minable.py`*