# Diccionario de Variables - Vista Minable

---

## RESUMEN

| Concepto | Valor |
|----------|-------|
| **Total columnas** | 54 |
| **Metadata** | 4 |
| **Features estáticos** | 20 (no cambian por semestre) |
| **Features dinámicos** | 25 (cambian por semestre) |
| **Target** | 5 |
| **Filas** | 5,284,340 |
| **Granularidad** | 1 fila = 1 píxel (50m) × 1 semestre |
| **Período** | 2020A – 2025B (12 semestres) |
| **Sistema coordenadas** | EPSG:3116 (Magna-Sirgas Origen-Nacional) |

---

## 1. VARIABLES DE METADATA (4)

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 1 | `pixel_id` | int64 | — | Único por fila | Generado | Identificador único secuencial de cada fila en la vista minable. No tiene significado espacial. |
| 2 | `x` | float64 | metros | Estática | DEM | Coordenada X (este) del centro del píxel en EPSG:3116. Identifica la posición horizontal del píxel de 50m. |
| 3 | `y` | float64 | metros | Estática | DEM | Coordenada Y (norte) del centro del píxel en EPSG:3116. Identifica la posición vertical del píxel de 50m. |
| 4 | `semestre` | string | — | Dinámica | Generado | Semestre agrícola en formato `YYYYA` (primer semestre, jan-jun) o `YYYYB` (segundo semestre, jul-dic). Rango: 2020A a 2025B. |

---

## 2. FEATURES ESTÁTICOS — TOPOGRAFÍA (6)

Variables derivadas del Modelo Digital de Elevación (DEM) a 50m de resolución. No cambian entre semestres.

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 5 | `elevacion` | float32 | m.s.n.m. | Estática | DEM (Extractor 07) | Altitud sobre el nivel del mar del centro del píxel. Rango en Cundinamarca: ~150–4200 m. Determina pisos térmicos y condiciones climáticas. Es la variable topográfica más importante. |
| 6 | `pendiente` | float32 | % | Estática | DEM (Extractor 07) | Inclinación del terreno en porcentaje (0%=plano, >100%=escarpado). Calculada con `gdaldem slope`. Afecta erosión, drenaje, maquinabilidad yaptitud agrícola. Rango: 0–177%. |
| 7 | `twi` | float32 | adimensional | Estática | DEM (Extractor 07) | **Topographic Wetness Index** (Índice de Humedad Topográfica). Mide la tendencia del terreno a acumular agua: TWI = ln(área_captación / pendiente). Valores altos (>10) indican zonas húmedas o de drenaje; bajos (< 3) indican lomas secas. |
| 8 | `aspecto_sin` | float32 | adimensional [-1, 1] | Estática | Feature Engineering | Componente senoidal de la orientación del terreno: `sin(aspecto × π/180)`. Codifica la orientación Norte-Sur del terreno. Valores cercanos a 1 = orientación Este; -1 = Oeste. En zonas planas = 0. |
| 9 | `aspecto_cos` | float32 | adimensional [-1, 1] | Estática | Feature Engineering | Componente cosenoidal de la orientación del terreno: `cos(aspecto × π/180)`. Codifica la orientación Este-Oeste. Valores cercanos a 1 = orientación Norte; -1 = Sur. En zonas planas = 0. La descomposición circular evita la discontinuidad 0°/360°. |
| 10 | `piso_termico` | float32 | categoría (0-3) | Estática | Feature Engineering (03) | Clasificación térmica por altitud: 0=Cálido (<1000msnm), 1=Templado (1000-2000m), 2=Frío (2000-3000m), 3=Páramo (>3000m). Determina qué cultivos son viables. ~4.6% NaN (píxeles sin DEM). Usada como estrato de muestreo y para asignar cultivos EVA por piso. |

---

## 3. FEATURES ESTÁTICOS — SUELO SOILGRIDS (8)

Propiedades del suelo a 0-5 cm de profundidad, modelo global a 250m re-muestreado a 50m. Los valores vienen en unidades SoilGrids (×10 del valor real).

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 11 | `sg_phh2o` | float32 | pH × 10 | Estática | SoilGrids (Extractor 04) | **pH del suelo** medido en agua. Valor almacenado = pH_real × 10 (ej: 52 → pH 5.2). Rango típico Cundinamarca: 4.5–6.7. Determina disponibilidad de nutrientes. pH < 5.5 = ácido (común en zonas altas). ~0% NaN. |
| 12 | `sg_soc` | float32 | g/kg × 10 | Estática | SoilGrids (Extractor 04) | **Carbono Orgánico del Suelo** (Soil Organic Carbon). Valor almacenado = SOC_real × 10 (ej: 706 → 70.6 g/kg). Indica fertilidad y retención de agua. Valores altos > 60 g/kg en zonas de páramo. |
| 13 | `sg_nitrogen` | float32 | g/kg × 10 | Estática | SoilGrids (Extractor 04) | **Nitrógeno total** del suelo. Valor almacenado = N_real × 10 (ej: 435 → 4.35 g/kg). Nutriente esencial para el crecimiento vegetal. Alta correlación con SOC (r>0.85). |
| 14 | `sg_cec` | float32 | cmol/kg × 10 | Estática | SoilGrids (Extractor 04) | **Capacidad de Intercambio Catiónico**. Valor almacenado = CEC_real × 10 (ej: 236 → 23.6 cmol/kg). Mide la capacidad del suelo para retener nutrientes. CEC > 20 = suelos fértiles. |
| 15 | `sg_bdod` | float32 | g/cm³ × 10 | Estática | SoilGrids (Extractor 04) | **Densidad aparente del suelo** (Bulk Density). Valor almacenado = bdod_real × 10 (ej: 102 → 1.02 g/cm³). Indica compactación. Valores < 1.0 = suelos orgánicos/porosos; > 1.4 = compactados. |
| 16 | `sg_clay` | float32 | % (normalizado) | Estática | SoilGrids (Extractor 04) | **Porcentaje de arcilla** (0-100%). Afecta retención de agua y nutrientes, dificultad de laboreo. Rango: 16–49%. Normalizado durante armonización espacial. |
| 17 | `sg_sand` | float32 | % (normalizado) | Estática | SoilGrids (Extractor 04) | **Porcentaje de arena** (0-100%). Suelos arenosos = buen drenaje pero baja retención. Rango: 6–50%. Normalizado. Arcilla + Arena + Limo ≈ 100%. |
| 18 | `sg_silt` | float32 | % (normalizado) | Estática | SoilGrids (Extractor 04) | **Porcentaje de limo** (0-100%). Partículas intermedias. Suelos limosos = fértiles pero susceptibles a erosión. Rango: 21–51%. Normalizado. |

---

## 4. FEATURES ESTÁTICOS — SUELO IGAC (5)

Variables del estudio detallado de suelos del IGAC (Instituto Geográfico Agustín Codazzi). Son variables categóricas codificadas como numéricas ordinales.

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 19 | `igac_fertilidad` | float32 | categoría (1-7) | Estática | IGAC (Extractor 03) | **Clase de fertilidad** del suelo según IGAC. Escala 1 (muy baja) a 7 (muy alta). Es la evaluación integrada de nutrientes, pH, textura y materia orgánica. Mediana = 3 (media). |
| 20 | `igac_fosforo` | float32 | categoría (1-5) | Estática | IGAC (Extractor 03) | **Nivel de fósforo disponible** en el suelo. Escala 1 (muy bajo) a 5 (muy alto). El fósforo es esencial para raíces y floración. El 93% está en categoría 1 (bajo) — limitante común en suelos colombianos. |
| 21 | `igac_ph` | float32 | categoría (1-6) | Estática | IGAC (Extractor 03) | **Clase de pH** del suelo según IGAC. Escala 1 (muy ácido) a 6 (alcalino). Mediana = 1 (muy ácido). Más interpretable que SoilGrids pH a nivel de finca. |
| 22 | `igac_potasio` | float32 | categoría (1-5) | Estática | IGAC (Extractor 03) | **Nivel de potasio intercambiable**. Escala 1 (muy bajo) a 5 (muy alto). Esencial para resistencia a plagas y calidad de frutos. La mayoría está en categoría 1-2. |
| 23 | `igac_vocacion` | float32 | categoría (0-8) | Estática | IGAC (Extractor 03) | **Vocación de uso del suelo** según IGAC. Categorías: 0=Sin información, 1-8=distintos tipos de uso agrícola. **52.5% son cero** (sin información) — zonas urbanas, páramos o sin estudio. Para modelar: tratar 0 como categoría adicional o crear variable binaria `tiene_vocacion`. |

---

## 5. FEATURES ESTÁTICOS — DERIVADOS (1)

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 24 | `indice_fertilidad` | float32 | adimensional (0-1) | Estática | Feature Engineering (03) | **Índice compuesto de fertilidad** del suelo. Combina SG pH, SOC, CEC, IGAC fertilidad, fósforo y potasio en un score normalizado 0-1. Valores > 0.6 = suelos fértiles. Alta correlación con `sg_nitrogen` (r=0.90) y `sg_cec` (r=0.85). |

---

## 6. FEATURES DINÁMICOS — CLIMA (8)

Variables climáticas agregadas por semestre. Cambian cada semestre para un mismo píxel.

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 25 | `temperatura_media` | float32 | °C | Semestral | IDEAM (Extractor 01) | **Temperatura media semestral** interpolada vía kriging desde estaciones IDEAM. Alta correlación negativa con elevación (r=-0.95). Rango: -16 a 25°C. **NOTA**: Valores negativos en zonas altas sugieren posible error en la interpolación — verificar. |
| 26 | `temperatura_max` | float32 | °C | Semestral | IDEAM (Extractor 01) | **Temperatura máxima media** semestral. Correlación casi perfecta con `temperatura_media` (r=0.99). **Recomendación: EXCLUIR** — no aporta información adicional más allá de temperatura_media. |
| 27 | `temperatura_min` | float32 | °C | Semestral | IDEAM (Extractor 01) | **Temperatura mínima media** semestral. Correlación casi perfecta con `temperatura_media` (r=0.98). **Recomendación: EXCLUIR** — reemplazada por `amplitud_termica`. |
| 28 | `humedad_media` | float32 | % | Semestral | IDEAM (Extractor 01) | **Humedad relativa media** semestral interpolada desde estaciones. Rango: 62-96%. Indica disponibilidad atmosférica de agua. Valores > 80% = zonas de ladera húmedas. |
| 29 | `chirps_acum` | float32 | mm | Semestral | CHIRPS (Extractor 02) | **Precipitación acumulada semestral** desde CHIRPS (satélite + estaciones). Rango: 0-2704 mm/semestre. Es la fuente principal de precipitación (IDEAM precipitación falló = 100% ceros). |
| 30 | `amplitud_termica` | float32 | °C | Semestral | Feature Engineering (03) | **Diferencia entre temp_max y temp_min** semestral. Mide la variabilidad térmica. Valores altos (>5°C) = zonas de ladera con microclimas; bajos (<2°C) = valles planos. |
| 31 | `anomalia_precip` | float32 | adimensional | Semestral | Feature Engineering (03) | **Anomalía de precipitación** estandarizada respecto al promedio histórico. Valores > 1 = semestre inusualmente húmedo; < -1 = inusualmente seco. Indica sequía o exceso de lluvia. |
| 32 | `indice_aridez` | float32 | adimensional | Semestral | Feature Engineering (03) | **Índice de aridez** = precipitación / evapotranspiración_potencial. Valores < 1 = condiciones áridas; > 5 = muy húmedo. Determina qué cultivos pueden sobrevivir sin riego. Rango: 0-46. |

---

## 7. FEATURES DINÁMICOS — SENTINEL-2 (15)

Índices de vegetación derivados de imágenes Sentinel-2 (10m) agregados a 50m. Estadísticos calculados sobre las observaciones del semestre.

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 33 | `s2_ndvi_media` | float32 | adimensional [-1,1] | Semestral | Sentinel-2 (Extractor 05) | **NDVI medio semestral** (Normalized Difference Vegetation Index). Media de todas las observaciones del semestre.|
| 34 | `s2_ndvi_max` | float32 | adimensional [-1,1] | Semestral | Sentinel-2 (Extractor 05) | **NDVI máximo semestral**. Valor máximo alcanzado por la vegetación. ✅ Correcto (rango -1 a 1). Representa el pico de verdor del semestre. Valores > 0.7 = vegetación densa/cultivos. |
| 35 | `s2_ndvi_std` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **NDVI desviación estándar** semestral. Mide heterogeneidad temporal. |
| 36 | `s2_gndvi_media` | float32 | adimensional [-1,1] | Semestral | Sentinel-2 (Extractor 05) | **GNDVI medio** (Green NDVI). Sensible a clorofila.|
| 37 | `s2_gndvi_max` | float32 | adimensional [-1,1] | Semestral | Sentinel-2 (Extractor 05) | **GNDVI máximo semestral**. Correcto. Alta correlación con s2_ndvi_max (r=0.97).  |
| 38 | `s2_gndvi_std` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **GNDVI desviación estándar**.  |
| 39 | `s2_msavi_media` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **MSAVI medio** (Modified Soil-Adjusted Vegetation Index).  |
| 40 | `s2_msavi_max` | float32 | adimensional [-1,1] | Semestral | Sentinel-2 (Extractor 05) | **MSAVI máximo semestral**. Correcto. Útil en zonas con vegetación dispersa. Similar a SAVI pero no requiere parámetro L. |
| 41 | `s2_msavi_std` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **MSAVI desviación estándar**.. |
| 42 | `s2_bsi_media` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **BSI medio** (Bare Soil Index). Detecta suelo descubierto.  |
| 43 | `s2_bsi_max` | float32 | adimensional [-1,1] | Semestral | Sentinel-2 (Extractor 05) | **BSI máximo semestral**. Correcto. Valores positivos = suelo expuesto; negativos = vegetación. Complementa NDVI. |
| 44 | `s2_bsi_std` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **BSI desviación estándar**.  |
| 45 | `s2_savi_media` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **SAVI medio** (Soil-Adjusted Vegetation Index). Redundante con MSAVI (r=1.0). |
| 46 | `s2_savi_max` | float32 | adimensional [-1,1] | Semestral | Sentinel-2 (Extractor 05) | **SAVI máximo semestral**. Correcto. Alta correlación con MSAVI max (r=0.996). **Recomendación: EXCLUIR** — redundante con msavi_max. |
| 47 | `s2_savi_std` | float32 | adimensional | Semestral | Sentinel-2 (Extractor 05) | **SAVI desviación estándar**.  |

---

## 8. FEATURES DINÁMICOS — DERIVADOS DE VEGATACIÓN (2)

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 48 | `ndvi_max` | float32 | adimensional [-1,1] | Semestral | Feature Engineering (03) | **NDVI máximo derivado** desde el raster engineered. **Duplicado exacto de `s2_ndvi_max`** (r=1.000).  |
| 49 | `ndvi_integral` | float32 | adimensional | Semestral | Feature Engineering (03) | **Integral del NDVI** sobre el semestre (área bajo la curva). Representa la producción total de biomasa. |

---

## 9. VARIABLES TARGET (5)

| # | Variable | Tipo | Unidad | Frecuencia | Fuente | Descripción |
|---|----------|------|--------|------------|--------|-------------|
| 50 | `cultivo` | string | — | Semestral | EVA + Monitoreo + SIPRA | **Variable target principal** — nombre del cultivo asignado al píxel-semestre. 7 clases con encoding en `catalogo_cultivos.json`: Papa (84.8%), Frijol (10.8%), Papa Capiro (2.4%), Arroz (1.5%), Palma (0.3%), Cacao (0.1%), Caña Panelera (0.1%). **Desbalance extremo 650:1**. |
| 51 | `cultivo_id` | int16 | — | Semestral | Generado | **Encoding numérico** del cultivo. Mapeo en `vista_minable/catalogo_cultivos.json`. Para modelos ML que requieran target numérico. |
| 52 | `confianza` | float32 | [0-1] | Semestral | Generado | **Confianza de la etiqueta**. Monitoreo=1.0, SIPRA=0.2-0.5 (según aptitud), EVA=0.35×score_aptitud (máx 0.35). Media≈0.43. Útil como `sample_weight` en entrenamiento. |
| 53 | `fuente` | string | — | Semestral | Generado | **Fuente de la etiqueta**. Valores: `eva` (~84%), `monitoreo` (~11%), `sipra` (~5%). Indica la calidad de la etiqueta. Monitoreo = georreferenciado directo (polígonos UPRA). EVA = asignado por piso térmico desde registros municipales. SIPRA = aptitud modelada. |
| 54 | `rendimiento_tha` | float32 | ton/ha | Semestral | EVA (Extractor 08) | **Rendimiento del cultivo** en toneladas por hectárea. Mediana del rendimiento EVA por cultivo-semestre. Solo disponible para Papa (~18.5 t/ha), Frijol (~1.9 t/ha) y Arroz (~7.3 t/ha). **~5% NaN**. Los 4 cultivos menores (Cacao, Caña Panelera, Palma, Papa Capiro) no tienen datos de rendimiento. Potencial target secundario para modelo de regresión. |

---

> **Documento relacionado**: Ver [`explicacion_variables_raw_a_vista_minable.md`](explicacion_variables_raw_a_vista_minable.md) para la trazabilidad completa de cada variable desde los datos crudos hasta la vista minable, incluyendo las 32 variables excluidas y sus razones.
