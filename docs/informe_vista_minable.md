# Informe de Análisis Estadístico - Vista Minable
## Proyecto: ¿Qué Sembrar? - AgroPlus
### Fecha: 17/04/2026

---

## RESUMEN EJECUTIVO

Vista minable: **5,284,340 filas × 54 columnas**
- Features numéricos: **45**
- Features categóricos: **0**
- Columnas target: **5**
- Columnas metadata: **4**
- Cultivos únicos: **7**
- Semestres: **12** (2020A a 2025B)

---

## 1. VALIDACIÓN ESTRUCTURAL

### 1.1 Filas duplicadas (x, y, semestre)
- Duplicados exactos: **0** (0.00%)
- ✅ Sin duplicados

### 1.2 Columnas duplicadas
- Columnas con nombre repetido: **Ninguna**

### 1.3 Rango de coordenadas (EPSG:3116)
| Eje | Min | Max | Rango |
|-----|-----|-----|-------|
| X | 918,116 | 1,113,773 | 195,657 |
| Y | 904,282 | 1,137,623 | 233,340 |

### 1.4 Semestres cubiertos
| Semestre | Filas | % del total |
|----------|-------|-------------|
| 2020A | 499,994 | 9.5% |
| 2020B | 499,994 | 9.5% |
| 2021A | 499,994 | 9.5% |
| 2021B | 499,994 | 9.5% |
| 2022A | 499,994 | 9.5% |
| 2022B | 499,994 | 9.5% |
| 2023A | 499,994 | 9.5% |
| 2023B | 499,994 | 9.5% |
| 2024A | 499,994 | 9.5% |
| 2024B | 499,994 | 9.5% |
| 2025A | 142,200 | 2.7% |
| 2025B | 142,200 | 2.7% |

---

## 2. ANÁLISIS DEL TARGET (Variable Objetivo)

### 2.1 Distribución de cultivos
| Cultivo | Filas | % del Total | Acumulado |
|---------|-------|-------------|-----------|
| Papa | 4,479,531 | 84.8% | 84.8% |
| Frijol | 568,210 | 10.8% | 95.5% |
| Papa Capiro | 129,396 | 2.4% | 98.0% |
| Arroz | 79,971 | 1.5% | 99.5% |
| Palma | 13,212 | 0.3% | 99.7% |
| Cacao | 7,126 | 0.1% | 99.9% |
| Cana Panelera | 6,894 | 0.1% | 100.0% |

**Ratio de desbalance**: 649.8:1 (max='Papa' vs min='Cana Panelera')
🚨 **DESBALANCE EXTREMO** — Se requiere balanceo obligatorio (SMOTE, class_weight, undersampling)

### 2.2 Distribución por fuente de etiqueta
| Fuente | Filas | % | Confianza media |
|--------|-------|---|-----------------|
| eva | 4,433,911 | 83.9% | 0.35 |
| monitoreo | 566,029 | 10.7% | 1.00 |
| sipra | 284,400 | 5.4% | 0.50 |

### 2.3 Cultivos por fuente

| cultivo       |     eva |   monitoreo |   sipra |     All |
|:--------------|--------:|------------:|--------:|--------:|
| Arroz         |       0 |       79971 |       0 |   79971 |
| Cacao         |       0 |           0 |    7126 |    7126 |
| Cana Panelera |       0 |           0 |    6894 |    6894 |
| Frijol        |  568210 |           0 |       0 |  568210 |
| Palma         |       0 |           0 |   13212 |   13212 |
| Papa          | 3865701 |      486058 |  127772 | 4479531 |
| Papa Capiro   |       0 |           0 |  129396 |  129396 |
| All           | 4433911 |      566029 |  284400 | 5284340 |

### 2.4 Distribución de confianza
| Stat | Valor |
|------|-------|
| count | 5284340.0000 |
| mean | 0.4314 |
| std | 0.2040 |
| min | 0.1634 |
| 25% | 0.3281 |
| 50% | 0.3606 |
| 75% | 0.4262 |
| max | 1.0000 |

### 2.5 Rendimiento (ton/ha)
| Stat | Valor |
|------|-------|
| count | 4999940.00 |
| mean | 16.47 |
| std | 6.48 |
| min | 1.30 |
| 25% | 16.00 |
| 50% | 17.00 |
| 75% | 18.50 |
| max | 29.00 |
- % NaN: 5.4%

#### Rendimiento por cultivo

| cultivo       |      count |   mean |    std |    min |   median |    max |
|:--------------|-----------:|-------:|-------:|-------:|---------:|-------:|
| Papa          | 4351759.00 |  18.54 |   3.82 |  16.00 |    17.00 |  29.00 |
| Frijol        |  568210.00 |   1.88 |   0.31 |   1.30 |     2.00 |   2.20 |
| Arroz         |   79971.00 |   7.31 |   0.78 |   6.07 |     7.66 |   8.24 |
| Cana Panelera |       0.00 | nan    | nan    | nan    |   nan    | nan    |
| Cacao         |       0.00 | nan    | nan    | nan    |   nan    | nan    |
| Palma         |       0.00 | nan    | nan    | nan    |   nan    | nan    |
| Papa Capiro   |       0.00 | nan    | nan    | nan    |   nan    | nan    |

---

## 3. ANÁLISIS DE VALORES FALTANTES (NaN, Nulos, Ceros)

### 3.1 Valores NaN por variable

| Variable | % NaN | % Válido | Tipo |
|----------|-------|----------|------|
| piso_termico | 4.61% | 95.39% | ✅ Bajo |
| sg_sand | 1.08% | 98.92% | ✅ Bajo |
| sg_silt | 1.08% | 98.92% | ✅ Bajo |
| sg_clay | 1.08% | 98.92% | ✅ Bajo |
| s2_bsi_max | 0.70% | 99.30% | ✅ Bajo |
| s2_bsi_media | 0.70% | 99.30% | ✅ Bajo |
| s2_savi_max | 0.70% | 99.30% | ✅ Bajo |
| s2_msavi_max | 0.70% | 99.30% | ✅ Bajo |
| s2_msavi_media | 0.70% | 99.30% | ✅ Bajo |
| s2_ndvi_max | 0.70% | 99.30% | ✅ Bajo |
| s2_ndvi_media | 0.70% | 99.30% | ✅ Bajo |
| s2_savi_media | 0.70% | 99.30% | ✅ Bajo |
| ndvi_max | 0.70% | 99.30% | ✅ Bajo |
| s2_gndvi_max | 0.70% | 99.30% | ✅ Bajo |
| s2_gndvi_media | 0.70% | 99.30% | ✅ Bajo |
| indice_aridez | 0.00% | 100.00% | ✅ Bajo |
| amplitud_termica | 0.00% | 100.00% | ✅ Bajo |
| temperatura_max | 0.00% | 100.00% | ✅ Bajo |
| temperatura_media | 0.00% | 100.00% | ✅ Bajo |
| humedad_media | 0.00% | 100.00% | ✅ Bajo |
| temperatura_min | 0.00% | 100.00% | ✅ Bajo |

**24 variables** sin ningún NaN

### 3.2 Valores cero por variable

| Variable | % Ceros | N Ceros | Diagnóstico |
|----------|---------|---------|-------------|
| igac_vocacion | 52.50% | 2,774,534 | Revisar |
| s2_bsi_std | 0.70% | 36,847 | Revisar |
| s2_ndvi_std | 0.70% | 36,842 | Revisar |
| s2_msavi_std | 0.70% | 36,842 | Revisar |
| s2_savi_std | 0.70% | 36,842 | Revisar |
| s2_gndvi_std | 0.70% | 36,841 | Revisar |

### 3.3 Valores atípicos extremos

| Variable | % Extremos | N | Min | Max | Mean | Std |
|----------|------------|---|-----|-----|------|-----|
| igac_fosforo | 1.06% | 55,778 | 1.00 | 5.00 | 1.07 | 0.41 |
| igac_ph | 1.06% | 55,778 | 1.00 | 6.00 | 1.32 | 0.64 |
| sg_phh2o | 0.61% | 32,054 | 0.10 | 6.60 | 5.50 | 0.40 |
| igac_potasio | 0.56% | 29,778 | 1.00 | 5.00 | 1.28 | 0.55 |
| sg_bdod | 0.40% | 20,946 | 0.10 | 13.90 | 10.27 | 1.22 |
| s2_gndvi_max | 0.32% | 16,645 | -1.00 | 1.00 | 0.63 | 0.12 |
| sg_cec | 0.17% | 9,118 | 0.10 | 67.70 | 27.85 | 4.58 |
| amplitud_termica | 0.15% | 8,106 | 0.19 | 17.07 | 2.97 | 2.28 |
| pendiente | 0.15% | 8,040 | 0.00 | 176.51 | 15.84 | 14.25 |
| indice_aridez | 0.13% | 6,608 | 0.00 | 45.94 | 5.34 | 3.02 |
| s2_ndvi_max | 0.12% | 6,456 | -1.00 | 1.00 | 0.70 | 0.15 |
| ndvi_max | 0.12% | 6,456 | -1.00 | 1.00 | 0.70 | 0.15 |

---

## 4. ESTADÍSTICAS DESCRIPTIVAS POR GRUPO

### Topografía

| Variable | % NaN | Mean | Std | Min | Q1 | Mediana | Q3 | Max | % Ceros |
|----------|-------|------|-----|-----|----|---------|----|-----|---------|
| elevacion | 0.0% | 2566.11 | 744.33 | 194.70 | 2532.69 | 2689.82 | 3026.80 | 4124.14 | 0.0% |
| pendiente | 0.0% | 15.84 | 14.25 | 0.00 | 5.51 | 13.23 | 21.49 | 176.51 | 0.0% |
| twi | 0.0% | 5.60 | 5.95 | 2.32 | 2.58 | 3.12 | 4.39 | 30.08 | 0.0% |
| piso_termico | 4.6% | 2.17 | 0.61 | 1.00 | 2.00 | 2.00 | 3.00 | 3.00 | 0.0% |
| aspecto_sin | 0.0% | -0.04 | 0.72 | -1.00 | -0.76 | -0.11 | 0.68 | 1.00 | 0.0% |
| aspecto_cos | 0.0% | -0.13 | 0.68 | -1.00 | -0.80 | -0.24 | 0.52 | 1.00 | 0.0% |

### SoilGrids (Suelo)

| Variable | % NaN | Mean | Std | Min | Q1 | Mediana | Q3 | Max | % Ceros |
|----------|-------|------|-----|-----|----|---------|----|-----|---------|
| sg_phh2o | 0.0% | 5.50 | 0.40 | 0.10 | 5.30 | 5.50 | 5.70 | 6.60 | 0.0% |
| sg_soc | 0.0% | 78.66 | 20.16 | 0.10 | 65.90 | 76.40 | 90.70 | 185.60 | 0.0% |
| sg_nitrogen | 0.0% | 50.02 | 9.19 | 0.10 | 45.10 | 50.00 | 55.20 | 91.00 | 0.0% |
| sg_cec | 0.0% | 27.85 | 4.58 | 0.10 | 25.90 | 28.10 | 30.60 | 67.70 | 0.0% |
| sg_bdod | 0.0% | 10.27 | 1.22 | 0.10 | 9.50 | 10.30 | 11.10 | 13.90 | 0.0% |
| sg_clay | 1.1% | 31.18 | 4.08 | 16.00 | 29.00 | 31.00 | 34.00 | 49.00 | 0.0% |
| sg_sand | 1.1% | 34.58 | 5.56 | 6.00 | 31.00 | 35.00 | 39.00 | 50.00 | 0.0% |
| sg_silt | 1.1% | 32.85 | 3.56 | 21.00 | 30.00 | 32.00 | 35.00 | 51.00 | 0.0% |

### IGAC (Suelo)

| Variable | % NaN | Mean | Std | Min | Q1 | Mediana | Q3 | Max | % Ceros |
|----------|-------|------|-----|-----|----|---------|----|-----|---------|
| igac_fertilidad | 0.0% | 2.66 | 1.06 | 1.00 | 2.00 | 3.00 | 3.00 | 7.00 | 0.0% |
| igac_fosforo | 0.0% | 1.07 | 0.41 | 1.00 | 1.00 | 1.00 | 1.00 | 5.00 | 0.0% |
| igac_ph | 0.0% | 1.32 | 0.64 | 1.00 | 1.00 | 1.00 | 2.00 | 6.00 | 0.0% |
| igac_potasio | 0.0% | 1.28 | 0.55 | 1.00 | 1.00 | 1.00 | 2.00 | 5.00 | 0.0% |
| igac_vocacion | 0.0% | 2.53 | 2.89 | 0.00 | 0.00 | 0.00 | 6.00 | 8.00 | 52.5% |

### Clima (IDEAM + CHIRPS)

| Variable | % NaN | Mean | Std | Min | Q1 | Mediana | Q3 | Max | % Ceros |
|----------|-------|------|-----|-----|----|---------|----|-----|---------|
| temperatura_media | 0.0% | -1.37 | 6.51 | -16.21 | -5.40 | -3.12 | 0.04 | 25.17 | 0.0% |
| temperatura_max | 0.0% | 0.14 | 6.84 | -14.38 | -4.19 | -1.74 | 2.09 | 29.48 | 0.0% |
| temperatura_min | 0.0% | -2.83 | 6.15 | -19.84 | -6.63 | -4.31 | -1.43 | 23.99 | 0.0% |
| humedad_media | 0.0% | 78.33 | 7.19 | 61.84 | 71.68 | 80.17 | 84.57 | 95.88 | 0.0% |
| chirps_acum | 0.0% | 719.40 | 320.51 | 0.00 | 518.36 | 629.26 | 805.79 | 2704.43 | 0.1% |
| amplitud_termica | 0.0% | 2.97 | 2.28 | 0.19 | 1.28 | 2.20 | 4.05 | 17.07 | 0.0% |
| anomalia_precip | 0.0% | -0.05 | 0.99 | -2.12 | -0.84 | -0.14 | 0.63 | 2.23 | 0.1% |
| indice_aridez | 0.0% | 5.34 | 3.02 | 0.00 | 3.12 | 4.79 | 6.75 | 45.94 | 0.1% |

### Sentinel-2 (Satélite)

| Variable | % NaN | Mean | Std | Min | Q1 | Mediana | Q3 | Max | % Ceros |
|----------|-------|------|-----|-----|----|---------|----|-----|---------|
| s2_ndvi_media | 0.7% | -2730.17 | 2128.43 | -8332.67 | -3332.78 | -1666.33 | -1665.92 | 0.94 | 0.0% |
| s2_ndvi_max | 0.7% | 0.70 | 0.15 | -1.00 | 0.63 | 0.73 | 0.80 | 1.00 | 0.0% |
| s2_ndvi_std | 0.0% | 3444.45 | 1829.79 | 0.00 | 3726.57 | 3726.68 | 4713.88 | 4999.97 | 0.7% |
| s2_gndvi_media | 0.7% | -2730.16 | 2128.40 | -8332.67 | -3332.77 | -1666.32 | -1665.99 | 0.83 | 0.0% |
| s2_gndvi_max | 0.7% | 0.63 | 0.12 | -1.00 | 0.58 | 0.65 | 0.70 | 1.00 | 0.0% |
| s2_gndvi_std | 0.0% | 3444.40 | 1829.79 | 0.00 | 3726.56 | 3726.65 | 4713.85 | 4999.94 | 0.7% |
| s2_msavi_media | 0.7% | -2730.33 | 2128.39 | -8332.54 | -3332.89 | -1666.41 | -1666.11 | 0.81 | 0.0% |
| s2_msavi_max | 0.7% | 0.45 | 0.15 | -0.24 | 0.35 | 0.46 | 0.56 | 0.99 | 0.0% |
| s2_msavi_std | 0.0% | 3444.36 | 1829.75 | 0.00 | 3726.49 | 3726.59 | 4713.76 | 4999.93 | 0.7% |
| s2_bsi_media | 0.7% | -2731.33 | 2128.32 | -8332.59 | -3333.19 | -1666.76 | -1666.51 | 0.40 | 0.0% |
| s2_bsi_max | 0.7% | -0.04 | 0.14 | -0.56 | -0.14 | -0.06 | 0.05 | 1.00 | 0.0% |
| s2_bsi_std | 0.0% | 3444.75 | 1829.37 | 0.00 | 3726.31 | 3726.42 | 4713.53 | 4999.75 | 0.7% |
| s2_savi_media | 0.7% | -2730.32 | 2128.39 | -8332.53 | -3332.88 | -1666.40 | -1666.11 | 0.75 | 0.0% |
| s2_savi_max | 0.7% | 0.45 | 0.13 | -0.20 | 0.37 | 0.46 | 0.54 | 0.94 | 0.0% |
| s2_savi_std | 0.0% | 3444.37 | 1829.76 | 0.00 | 3726.50 | 3726.59 | 4713.77 | 4999.90 | 0.7% |

### Features Derivadas

| Variable | % NaN | Mean | Std | Min | Q1 | Mediana | Q3 | Max | % Ceros |
|----------|-------|------|-----|-----|----|---------|----|-----|---------|
| indice_fertilidad | 0.0% | 0.61 | 0.13 | 0.00 | 0.56 | 0.62 | 0.68 | 0.92 | 0.4% |
| s2_ndvi_max | 0.7% | 0.70 | 0.15 | -1.00 | 0.63 | 0.73 | 0.80 | 1.00 | 0.0% |
| s2_gndvi_max | 0.7% | 0.63 | 0.12 | -1.00 | 0.58 | 0.65 | 0.70 | 1.00 | 0.0% |
| ndvi_max | 0.7% | 0.70 | 0.15 | -1.00 | 0.63 | 0.73 | 0.80 | 1.00 | 0.0% |
| ndvi_integral | 0.0% | -498596.97 | 396154.22 | -1799820.00 | -599899.06 | -299925.50 | -299866.31 | 168.96 | 0.0% |

---

## 5. ANÁLISIS DE CORRELACIONES

### 5.1 Pares con |r| > 0.80 (43 pares encontrados)

| Variable 1 | Variable 2 | Correlación (r) | Diagnóstico |
|------------|------------|-----------------|-------------|
| s2_ndvi_max | ndvi_max | 1.0000 | 🚨 Redundante — excluir una |
| s2_msavi_std | s2_savi_std | 1.0000 | 🚨 Redundante — excluir una |
| s2_msavi_media | s2_savi_media | 1.0000 | 🚨 Redundante — excluir una |
| s2_ndvi_std | s2_savi_std | 1.0000 | 🚨 Redundante — excluir una |
| s2_ndvi_std | s2_msavi_std | 1.0000 | 🚨 Redundante — excluir una |
| s2_ndvi_media | s2_savi_media | 1.0000 | 🚨 Redundante — excluir una |
| s2_ndvi_media | s2_msavi_media | 1.0000 | 🚨 Redundante — excluir una |
| s2_ndvi_media | s2_gndvi_media | 1.0000 | 🚨 Redundante — excluir una |
| s2_gndvi_media | s2_savi_media | 1.0000 | 🚨 Redundante — excluir una |
| s2_gndvi_media | s2_msavi_media | 1.0000 | 🚨 Redundante — excluir una |
| s2_ndvi_std | s2_gndvi_std | 0.9999 | 🚨 Redundante — excluir una |
| s2_gndvi_std | s2_savi_std | 0.9999 | 🚨 Redundante — excluir una |
| s2_gndvi_std | s2_msavi_std | 0.9999 | 🚨 Redundante — excluir una |
| s2_gndvi_media | s2_bsi_media | 0.9998 | 🚨 Redundante — excluir una |
| s2_msavi_media | s2_bsi_media | 0.9998 | 🚨 Redundante — excluir una |
| s2_bsi_media | s2_savi_media | 0.9998 | 🚨 Redundante — excluir una |
| s2_ndvi_media | s2_bsi_media | 0.9998 | 🚨 Redundante — excluir una |
| s2_gndvi_std | s2_bsi_std | 0.9997 | 🚨 Redundante — excluir una |
| s2_ndvi_std | s2_bsi_std | 0.9997 | 🚨 Redundante — excluir una |
| s2_bsi_std | s2_savi_std | 0.9997 | 🚨 Redundante — excluir una |
| s2_msavi_std | s2_bsi_std | 0.9997 | 🚨 Redundante — excluir una |
| s2_msavi_media | ndvi_integral | 0.9992 | 🚨 Redundante — excluir una |
| s2_savi_media | ndvi_integral | 0.9992 | 🚨 Redundante — excluir una |
| s2_ndvi_media | ndvi_integral | 0.9992 | 🚨 Redundante — excluir una |
| s2_gndvi_media | ndvi_integral | 0.9992 | 🚨 Redundante — excluir una |
| s2_bsi_media | ndvi_integral | 0.9990 | 🚨 Redundante — excluir una |
| s2_msavi_max | s2_savi_max | 0.9959 | 🚨 Redundante — excluir una |
| temperatura_media | temperatura_max | 0.9864 | 🚨 Redundante — excluir una |
| temperatura_media | temperatura_min | 0.9823 | 🚨 Redundante — excluir una |
| s2_gndvi_max | ndvi_max | 0.9667 | 🚨 Redundante — excluir una |
| s2_ndvi_max | s2_gndvi_max | 0.9667 | 🚨 Redundante — excluir una |
| elevacion | temperatura_media | -0.9473 | 📋 Moderada-Alta — evaluar |
| temperatura_max | temperatura_min | 0.9441 | ⚠️ Alta — considerar excluir |
| elevacion | temperatura_min | -0.9429 | 📋 Moderada-Alta — evaluar |
| elevacion | temperatura_max | -0.9262 | 📋 Moderada-Alta — evaluar |
| sg_nitrogen | indice_fertilidad | 0.9024 | ⚠️ Alta — considerar excluir |
| elevacion | piso_termico | 0.8855 | 📋 Moderada-Alta — evaluar |
| sg_cec | indice_fertilidad | 0.8452 | 📋 Moderada-Alta — evaluar |
| s2_savi_max | ndvi_max | 0.8434 | 📋 Moderada-Alta — evaluar |
| s2_ndvi_max | s2_savi_max | 0.8434 | 📋 Moderada-Alta — evaluar |
| sg_soc | indice_fertilidad | 0.8204 | 📋 Moderada-Alta — evaluar |
| s2_msavi_max | ndvi_max | 0.8139 | 📋 Moderada-Alta — evaluar |
| s2_ndvi_max | s2_msavi_max | 0.8139 | 📋 Moderada-Alta — evaluar |

### 5.2 Variables menos correlacionadas (posiblemente irrelevantes)

| Variable | CV (Coef. Variación) | Std | Mean |
|----------|---------------------|-----|------|
| sg_phh2o | 0.0735 | 0.4038 | 5.4977 |
| humedad_media | 0.0918 | 7.1914 | 78.3310 |
| sg_silt | 0.1082 | 3.5556 | 32.8511 |
| sg_bdod | 0.1185 | 1.2170 | 10.2688 |
| sg_clay | 0.1308 | 4.0770 | 31.1798 |
| sg_sand | 0.1608 | 5.5594 | 34.5810 |
| sg_cec | 0.1645 | 4.5798 | 27.8467 |
| sg_nitrogen | 0.1837 | 9.1865 | 50.0175 |
| s2_gndvi_max | 0.1839 | 0.1160 | 0.6304 |
| s2_ndvi_max | 0.2097 | 0.1462 | 0.6973 |

---

## 6. BALANCE DE CLASES POR SEMESTRE

| semestre   |   Arroz |   Cacao |   Cana Panelera |   Frijol |   Palma |   Papa |   Papa Capiro |
|:-----------|--------:|--------:|----------------:|---------:|--------:|-------:|--------------:|
| 2020A      |       0 |       0 |               0 |    56824 |       0 | 443170 |             0 |
| 2020B      |       0 |       0 |               0 |    56824 |       0 | 443170 |             0 |
| 2021A      |   14154 |       0 |               0 |    56824 |       0 | 429016 |             0 |
| 2021B      |    6376 |       0 |               0 |    56823 |       0 | 436795 |             0 |
| 2022A      |   13018 |       0 |               0 |    56824 |       0 | 430152 |             0 |
| 2022B      |   10149 |       0 |               0 |    56824 |       0 | 433021 |             0 |
| 2023A      |    7391 |       0 |               0 |    56824 |       0 | 435779 |             0 |
| 2023B      |   12191 |       0 |               0 |    56818 |       0 | 430985 |             0 |
| 2024A      |   16692 |       0 |               0 |    56801 |       0 | 426501 |             0 |
| 2024B      |       0 |       0 |               0 |    56824 |       0 | 443170 |             0 |
| 2025A      |       0 |    3563 |            3447 |        0 |    6606 |  63886 |         64698 |
| 2025B      |       0 |    3563 |            3447 |        0 |    6606 |  63886 |         64698 |

---

## 7. ALERTAS Y RECOMENDACIONES

### Resumen de Alertas

| Severidad | Cantidad |
|-----------|----------|
| 🚨 CRÍTICA | 2 |
| ⚠️ ALTA | 6 |
| 📋 MEDIA | 0 |

### Detalle de Alertas

- **🚨 CRÍTICA**: Desbalance extremo de target: ratio 650:1. 'Papa' domina con 84.8%. Usar SMOTE, class_weight='balanced', o undersampling.
- **🚨 CRÍTICA**: Sentinel-2 `*_media` y `*_std` tienen valores basura (-8332 a 0.94). La causa es que `02_armonizar_temporal.py` no filtra NoData (-9999) correctamente en archivos multibanda S2 antes de aplicar `nanmean`. Solo `*_max` son correctos (nanmax excluye valores negativos). **Requiere corregir y re-ejecutar armonización temporal.**
- **⚠️ ALTA**: `s2_ndvi_max` y `ndvi_max` están casi perfectamente correlacionadas (r=1.000). Excluir una para evitar multicolinealidad.
- **⚠️ ALTA**: `s2_msavi_std` y `s2_savi_std` están casi perfectamente correlacionadas (r=1.000). Excluir una para evitar multicolinealidad.
- **⚠️ ALTA**: `s2_msavi_media` y `s2_savi_media` están casi perfectamente correlacionadas (r=1.000). Excluir una para evitar multicolinealidad.
- **⚠️ ALTA**: `s2_ndvi_std` y `s2_savi_std` están casi perfectamente correlacionadas (r=1.000). Excluir una para evitar multicolinealidad.
- **⚠️ ALTA**: `s2_ndvi_std` y `s2_msavi_std` están casi perfectamente correlacionadas (r=1.000). Excluir una para evitar multicolinealidad.
- **⚠️ ALTA**: Fuente 'eva' domina con 83.9%. Esto significa que la mayoría de etiquetas vienen de EVA (confianza=0.7), no de monitoreo directo.

---

## 8. RECOMENDACIÓN DE VARIABLES A EXCLUIR/CONSERVAR

### Variables a EXCLUIR

| Variable | Razón |
|----------|-------|
| `ndvi_integral` | Redundante con s2_bsi_media (r=0.999) |
| `ndvi_max` | Redundante con s2_gndvi_max (r=0.967) |
| `s2_bsi_media` | Redundante con s2_ndvi_media (r=1.000) |
| `s2_bsi_std` | Redundante con s2_msavi_std (r=1.000) |
| `s2_gndvi_max` | Redundante con s2_ndvi_max (r=0.967) |
| `s2_gndvi_media` | Redundante con s2_ndvi_media (r=1.000) |
| `s2_gndvi_std` | Redundante con s2_ndvi_std (r=1.000) |
| `s2_msavi_media` | Redundante con s2_gndvi_media (r=1.000) |
| `s2_msavi_std` | Redundante con s2_gndvi_std (r=1.000) |
| `s2_savi_max` | Redundante con s2_msavi_max (r=0.996) |
| `s2_savi_media` | Redundante con s2_bsi_media (r=1.000) |
| `s2_savi_std` | Redundante con s2_bsi_std (r=1.000) |
| `temperatura_max` | Redundante con temperatura_media (r=0.986) |
| `temperatura_min` | Redundante con temperatura_media (r=0.982) |

### Variables a CONSERVAR (vista minable final)

**31 features numéricos:**

- `elevacion`
- `pendiente`
- `twi`
- `sg_phh2o`
- `sg_soc`
- `sg_nitrogen`
- `sg_cec`
- `sg_bdod`
- `sg_clay`
- `sg_sand`
- `sg_silt`
- `igac_fertilidad`
- `igac_fosforo`
- `igac_ph`
- `igac_potasio`
- `igac_vocacion`
- `piso_termico`
- `indice_fertilidad`
- `aspecto_sin`
- `aspecto_cos`
- `temperatura_media`
- `humedad_media`
- `chirps_acum`
- `s2_ndvi_media`
- `s2_ndvi_max`
- `s2_ndvi_std`
- `s2_msavi_max`
- `s2_bsi_max`
- `amplitud_termica`
- `anomalia_precip`
- `indice_aridez`

---

## 9. TRATAMIENTO RECOMENDADO ANTES DE MODELAR

### 9.1 Imputación de NaN

- `sg_clay` (1.1% NaN): Imputar ceros → NaN → mediana espacial
- `sg_sand` (1.1% NaN): Imputar ceros → NaN → mediana espacial
- `sg_silt` (1.1% NaN): Imputar ceros → NaN → mediana espacial
- `piso_termico` (4.6% NaN): Imputar con mediana global
- `temperatura_media` (0.0% NaN): Imputar con regresión vs elevación
- `temperatura_max` (0.0% NaN): Imputar con regresión vs elevación
- `temperatura_min` (0.0% NaN): Imputar con regresión vs elevación
- `humedad_media` (0.0% NaN): Imputar con mediana global
- `s2_ndvi_media` (0.7% NaN): Imputar con mediana por semestre
- `s2_ndvi_max` (0.7% NaN): Imputar con mediana por semestre
- `s2_gndvi_media` (0.7% NaN): Imputar con mediana por semestre
- `s2_gndvi_max` (0.7% NaN): Imputar con mediana por semestre
- `s2_msavi_media` (0.7% NaN): Imputar con mediana por semestre
- `s2_msavi_max` (0.7% NaN): Imputar con mediana por semestre
- `s2_bsi_media` (0.7% NaN): Imputar con mediana por semestre
- `s2_bsi_max` (0.7% NaN): Imputar con mediana por semestre
- `s2_savi_media` (0.7% NaN): Imputar con mediana por semestre
- `s2_savi_max` (0.7% NaN): Imputar con mediana por semestre
- `amplitud_termica` (0.0% NaN): Imputar con mediana global
- `ndvi_max` (0.7% NaN): Imputar con mediana global
- `indice_aridez` (0.0% NaN): Imputar con mediana global

### 9.2 Transformaciones

- **Normalización**: StandardScaler para variables continuas
- **Encoding**: One-hot para `fuente` (3 categorías)
- **Target encoding**: Label encoding ya aplicado en `cultivo_id`
- **Balanceo**: SMOTE o class_weight='balanced' (ratio desbalance: 650:1)

### 9.3 Variables SoilGrids (valores ×10)

| Variable | Valor actual | Valor real | Transformación |
|----------|-------------|------------|----------------|
| sg_phh2o | ~52 | pH 5.2 | ÷10 |
| sg_soc | ~706 | 70.6 g/kg | ÷10 |
| sg_nitrogen | ~435 | 4.35 g/kg | ÷10 |
| sg_cec | ~236 | 23.6 cmol/kg | ÷10 |
| sg_bdod | ~102 | 1.02 g/cm³ | ÷10 |
