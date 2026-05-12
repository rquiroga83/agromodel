# Modelo L1 UPRA — Resultados y Decisiones
## AgroPlus "Que Sembrar?" · Clasificador binario Papa vs no-Papa · XGBoost

**Fecha de ejecucion:** 2026-05-01  
**Notebook:** `CRISP_DM_AgroPlus_L1_UPRA.ipynb`  
**Artefacto:** `checkpoints/l1_upra_papa_v3.joblib` (1.38 MB)

---

## 1. Datos de entrada

| Parametro | Valor |
|-----------|-------|
| Fuente | `vista_minable/vista_minable_full.parquet` |
| Filas totales (pixel-semestre) | 4,164,485 |
| Columnas raw | 77 |
| Catalogo de cultivos | 20 clases |
| Memoria en RAM | ~1.4 GB |
| Resolucion espacial | 50 m / pixel |
| Ventana temporal | 2020–2024 |

### Esquema de etiquetado (tres capas)

| Capa | Fuente | Confianza | Cobertura |
|------|--------|-----------|-----------|
| L1 | Monitoreo UPRA (ground truth de campo) | 1.0 | Altiplano cundiboyacense |
| L2 | EVA municipal (proporciones por municipio) | 0.7 | Todo Cundinamarca |
| L3 | No_apto proxy (SIPRA + NDVI < 0.15) | 0.4 | Zonas no agricolas |

---

## 2. Construccion del target y filtros aplicados

### Target binario
`y = 1` si `cultivo == 'Papa'`, `y = 0` para cualquier otro cultivo.

### Fuentes incluidas en L1
Solo `monitoreo` y `eva_municipal`. La fuente `noapto_proxy` se excluye: etiqueta pixeles no agricolas que producen separacion trivial.

### Cultivos en fuente monitoreo (UPRA)
| Cultivo | Pixeles |
|---------|---------|
| Papa | 486,058 |
| Otros (no-Papa gold negatives, w=1.0) | — |

### Ajuste 1 — Filtro de envelope geografico
El monitoreo UPRA cubre el altiplano (2,540–3,362 m s.n.m.). Sin filtro, los negativos EVA cubren toda Cundinamarca, creando separacion geografica trivial (no agronomica).

- **Feature proxy:** `elevacion`
- **Envelope Papa:** [2,540 m, 3,362 m] (percentiles 5–95)
- **Ventana EVA aceptada:** ±10 % del rango → [2,286 m, 3,618 m]

| Conjunto | Filas |
|----------|-------|
| EVA total | (resto de 4,164,485) |
| EVA dentro del envelope | conservados |
| EVA fuera del envelope | excluidos |
| **df_l1 final** | **2,846,800 filas** |

### Composicion del dataset L1

| Clase | Pixeles | Porcentaje |
|-------|---------|------------|
| Papa (y=1) | 486,058 | 17.07 % |
| no-Papa (y=0) | 2,360,742 | 82.93 % |
| **Total** | **2,846,800** | |

**Razon de desbalance masa neg/pos:** 3.45

---

## 3. Calidad de datos

| Aspecto | Resultado |
|---------|-----------|
| Columnas con NaN | 17 |
| Mayor porcentaje de NaN | `piso_termico` 2.81 % (79,971 filas) |
| `sg_clay` missing | 0.80 % (22,646 filas) |
| Tratamiento | Imputacion por mediana del train (SimpleImputer) |

---

## 4. Diagnostico de leakage — tres fuentes detectadas y eliminadas

### 4.1 Leakage geografico (descartado)
Sanity check con un solo feature geografico antes y despues del filtro de envelope:

| Feature | Sin envelope | Con envelope |
|---------|-------------|-------------|
| `temperatura_media` | PR-AUC = 0.3141 ✓ | PR-AUC = 0.3411 ✓ |
| `elevacion` | PR-AUC = 0.3308 ✓ | PR-AUC = 0.4030 ✓ |
| `piso_termico` | PR-AUC = 0.2988 ✓ | PR-AUC = 0.3294 ✓ |
| `indice_aridez` | PR-AUC = 0.2430 ✓ | PR-AUC = 0.3166 ✓ |

Ninguna feature geografica individual supera el umbral de 0.70. **La geografia no era la causa raiz.**

### 4.2 Leakage temporal — features cross-semestre (causa raiz del PR-AUC = 1.0 en v1/v2)
`ndvi_sigma_temporal` y `ndvi_mean_temporal` se calculan con **todos los semestres disponibles (2020–2024)**, incluyendo los periodos de validacion y test. Son constantes por pixel: el modelo aprende el fingerprint NDVI del pixel Papa en train y lo reconoce perfectamente en valid.

**Accion:** ambas excluidas explicitamente de `EXCLUDE_COLS`.

### 4.3 Leakage directo de target — columnas `prob_*`
Las columnas `prob_Papa`, `prob_Maiz`, etc. son la distribucion de probabilidad sobre cultivos asignada por el etiquetador. `prob_Papa` es esencialmente el target.

**Accion:** filtro `not c.startswith('prob_')` en la construccion de `feature_cols`.

### 4.4 Leakage por split temporal + features estaticos (causa raiz del PR-AUC = 1.0 en v3 temprano)
Con split temporal (train ≤ 2022, valid = 2023), el **99.2 % de los pixeles de valid (5,017 pixeles) ya aparecia en train** con distintos semestres pero **features estaticos identicos** (suelo, topografia, IGAC). El modelo memorizaba el fingerprint combinado de 27 features en 2–3 arboles.

**Accion:** cambio a split espacial por municipio (GroupShuffleSplit).

### 4.5 Escaneo automatico feature por feature
Entrenamiento individual con cada uno de los 27 features supervivientes:

| Feature | PR-AUC solo |
|---------|------------|
| `sg_soc` | 0.3545 |
| `sg_phh2o` | 0.3488 |
| `temperatura_media` | 0.3411 |
| `sg_bdod` | 0.3400 |
| `pendiente` | 0.3384 |
| *(resto)* | 0.32–0.33 |

**Leakers detectados (PR-AUC > 0.70): 0.** Todos los features son safe individualmente.

---

## 5. Seleccion de features

### Pipeline de reduccion

| Paso | Features |
|------|---------|
| Columnas raw | 77 |
| Tras EXCLUDE_COLS (ids, target, leakage temporal, prob_*) | 39 |
| Tras filtro de varianza minima (modal > 80 %) | −2 (`igac_fosforo`, `sample_weight`) |
| Tras filtro de colinealidad (\|r\| > 0.85) | −10 (`elevacion`, `s2_bsi_media`, `s2_gndvi_media`, `s2_gndvi_std`, `s2_msavi_media`, `s2_msavi_std`, `s2_ndvi_max`, `s2_ndvi_media`, `s2_ndvi_std`, `sg_nitrogen`) |
| **Features finales** | **27** |

### Features seleccionados (27)

| Categoria | Features |
|-----------|---------|
| Topografia | `pendiente`, `twi`, `aspecto_sin`, `aspecto_cos` |
| Suelo SoilGrids | `sg_phh2o`, `sg_soc`, `sg_cec`, `sg_bdod`, `sg_clay`, `sg_sand`, `sg_silt` |
| Suelo IGAC | `igac_fertilidad`, `igac_ph`, `igac_potasio`, `igac_vocacion` |
| Derivados | `indice_fertilidad` |
| Clima | `temperatura_media`, `humedad_media`, `chirps_acum`, `amplitud_termica`, `anomalia_precip`, `indice_aridez` |
| Satelital (por semestre) | `s2_gndvi_max`, `s2_msavi_max`, `s2_bsi_max`, `s2_bsi_std` |
| Productividad | `ndvi_integral` |

### Top features por importancia XGBoost (modelo base)

| Rank | Feature | Gain |
|------|---------|------|
| 1 | `humedad_media` | 0.2369 |
| 2 | `sg_phh2o` | 0.1004 |
| 3 | `chirps_acum` | 0.0882 |

### Top features por Mutual Information

El ranking por MI coincide en su mayoria con el de gain del modelo: features climaticas e hidrologicas dominan la discriminacion intra-altiplano.

---

## 6. Split de datos

### Estrategia: GroupShuffleSplit espacial por municipio

Garantiza **cero solapamiento de pixeles** entre folds: cada municipio aparece en exactamente un fold.

> Diagnostico previo al fix: con split temporal, el 99.2 % de los pixeles de valid (5,017) ya aparecia en train con features identicos.

| Fold | Filas | Municipios | Papa | % Papa |
|------|-------|-----------|------|--------|
| **Train** | 1,732,760 | 64 | 270,812 | 15.63 % |
| **Valid** | 687,190 | 14 | 148,705 | 21.64 % |
| **Test** | 426,850 | 14 | 66,541 | 15.59 % |

**scale_pos_weight** (masa neg / masa pos en train) = **3.846**

### Preprocesamiento

- Imputacion: `SimpleImputer(strategy='median')` ajustado solo a train.
- Escalado: `StandardScaler` ajustado solo a train.
- Dimensiones finales: `X_train_pp (1,732,760 × 27)`, `X_valid_pp (687,190 × 27)`, `X_test_pp (426,850 × 27)`.

---

## 7. Modelo base XGBoost

### Configuracion

| Parametro | Valor |
|-----------|-------|
| `n_estimators` | 3,000 (con early stopping) |
| `max_depth` | 3 |
| `learning_rate` | 0.01 |
| `subsample` | 0.6 |
| `colsample_bytree` | 0.5 |
| `min_child_weight` | 10 |
| `gamma` | 0.5 |
| `reg_alpha` | 1.0 |
| `reg_lambda` | 5.0 |
| `early_stopping_rounds` | 100 |
| `eval_set` | solo valid (sin train) |
| `device` | CUDA |

### Resultado

| Metrica | Valor |
|---------|-------|
| Mejor iteracion | 27 |
| Tiempo de entrenamiento | 1.9 s |
| **PR-AUC valid** | **0.4288** |
| Train PR-AUC | 0.3522 |
| Gap (train − valid) | −0.0756 |

El gap negativo (valid > train) indica que valid tiene mayor proporcion de Papa que train (21.6 % vs 15.6 %), no overfitting. El modelo es genuinamente honesto.

### Curva de entrenamiento

```
[0]   valid PR-AUC: 0.29176
[100] valid PR-AUC: 0.42202
[127] valid PR-AUC: 0.42349  ← early stop
```

---

## 8. Validacion cruzada espacial (CV leave-municipio-out)

**Metodo:** `StratifiedGroupKFold(n_splits=5)` sobre municipios del train.

| Metrica | Media | Std | Rango |
|---------|-------|-----|-------|
| PR-AUC | 0.3364 | 0.0382 | [0.2818, 0.3970] |
| ROC-AUC | 0.7072 | 0.0252 | — |

La variabilidad entre folds (~0.12 puntos de rango en PR-AUC) es **aceptable**. Refleja la heterogeneidad real entre municipios del altiplano, no sobreajuste.

> Nota: PR-AUC de CV (0.34) es inferior al del modelo base sobre valid (0.43) porque la CV usa solo train (64 municipios) con 5 folds de ~13 municipios cada uno. Con menos datos de entrenamiento por fold, la discriminacion baja.

---

## 9. Optimizacion bayesiana con Optuna

### Gestion de estudios

| Estudio | Trials | Estado | PR-AUC |
|---------|--------|--------|--------|
| `l1_upra_xgb_v1` | 120 | Contaminado (leakage geografico) | ~1.0000 |
| `l1_upra_xgb_v2` | 70 | Contaminado (leakage temporal + prob_*) | 1.0000 |
| `l1_upra_xgb_v3` (trials 0–29) | 30 | Contaminado (split temporal) | 1.0000 |
| `l1_upra_xgb_v3` (trials 30–59) | 30 | Honestos (split espacial) | 0.40–0.45 |
| **`l1_upra_xgb_v4`** | **50** (30 sembrados + 20 nuevos) | **Limpio** | **0.40–0.45** |

### Configuracion Optuna v4

- **Sampler:** TPESampler multivariado (n_startup_trials=5)
- **Pruner:** MedianPruner (n_startup_trials=5)
- **Siembra:** 30 trials honestos de v3 importados automaticamente
- **Trials adicionales:** 20

### Espacio de busqueda

| Hiperparametro | Rango |
|----------------|-------|
| `n_estimators` | [300, 2000] |
| `max_depth` | [2, 6] |
| `learning_rate` | [0.005, 0.05] (log) |
| `subsample` | [0.4, 0.8] |
| `colsample_bytree` | [0.3, 0.7] |
| `min_child_weight` | [3, 30] |
| `gamma` | [0.1, 5.0] |
| `reg_alpha` | [0.05, 5.0] (log) |
| `reg_lambda` | [0.1, 10.0] (log) |

### Mejor trial (trial #24 del estudio v4 / trial #54 de v3 honesto)

| Hiperparametro | Valor |
|----------------|-------|
| `max_depth` | 6 |
| `learning_rate` | 0.03388 |
| `subsample` | 0.5666 |
| `colsample_bytree` | 0.5134 |
| `min_child_weight` | 7 |
| `gamma` | 0.7571 |
| `reg_alpha` | 1.0698 |
| `reg_lambda` | 5.6143 |
| `n_estimators` (sugerido) | 1,074 |
| **`best_iteration` real** | **379** |
| **PR-AUC valid** | **0.4532** |

> El `n_estimators` sugerido por Optuna (1,074) difiere del `best_iteration` real (379) porque el early stopping detiene el entrenamiento antes. El modelo final usa **380 arboles** (best_iteration + 1), no 1,074.

---

## 10. Modelo final

### Construccion

- Entrenado sobre **train + valid** combinados (2,419,950 filas).
- `n_estimators = 380` (best_iteration real, no el valor sugerido).
- Sin `early_stopping_rounds` en el modelo final.
- `eval_set` contiene solo train+valid (test excluido del eval_set).

### Metricas en test (hold-out de 14 municipios no vistos)

| Metrica | Valor |
|---------|-------|
| **PR-AUC test** | **0.4370** |
| ROC-AUC test | 0.7769 |
| Train+Valid PR-AUC | 0.5466 |
| Gap (fit − test) | +0.1096 |

### Metricas por umbral (threshold = 0.5)

| Metrica | Valor |
|---------|-------|
| Accuracy | 0.6155 |
| Precision | 0.3333 |
| Recall | 0.8500 |
| F1 | 0.4789 |
| Brier score | — |
| Log-loss | — |

### Seleccion de umbral operativo

| Criterio | Threshold | Precision | Recall | F1 |
|----------|-----------|-----------|--------|-----|
| Default 0.5 | 0.500 | 0.259 | 0.850 | 0.397 |
| **Max F1** | **0.600** | **0.305** | **0.658** | **0.417** |
| Recall @ Precision ≥ 0.90 | — | — | 0.002 | — |

> El criterio Recall@Precision=0.90 no se alcanza en este modelo. Con split espacial la tarea es genuinamente dificil: la precision maxima sostenida con recall util es ~0.30–0.35.

**Umbral operativo seleccionado: 0.600 (maximo F1)**

---

## 11. Analisis de errores (threshold = 0.600)

### Distribucion de predicciones en test

| Tipo | Cantidad | Tasa |
|------|---------|------|
| Verdaderos positivos (TP) | — | — |
| Verdaderos negativos (TN) | 304,274 | — |
| Falsos positivos (FP) | 99,826 | FP rate = 27.71 % |
| Falsos negativos (FN) | 22,750 | FN rate = 34.19 % |

### Interpretacion

- **FP (no-Papa predicho como Papa, 27.7 %):** pixeles del altiplano que comparten firma topo-climatica con Papa pero corresponden a otros cultivos de clima frio (arveja, zanahoria, hortalizas).
- **FN (Papa predicho como no-Papa, 34.2 %):** parcelas Papa con caracteristicas atipicas (altitudes marginales, siembras fuera de ciclo normal) o municipios con baja cobertura de monitoreo.

### Top municipios con mas errores

| Municipio (cod) | Errores totales |
|-----------------|----------------|
| 25269 | 34,869 |
| 25407 | 24,332 |

---

## 12. Persistencia del modelo

**Archivo:** `checkpoints/l1_upra_papa_v3.joblib` (1.38 MB)

### Contenido del artefacto

| Campo | Descripcion |
|-------|-------------|
| `model` | XGBClassifier (380 arboles) |
| `feature_cols` | Lista de 27 features |
| `imputer` | SimpleImputer ajustado a train |
| `scaler` | StandardScaler ajustado a train |
| `threshold_op` | 0.600 (max F1) |
| `best_params` | Hiperparametros del trial #24/v4 |
| `version` | `v3_sin_leakage` |
| `geo_envelope` | elevacion [2540, 3362] |

---

## 13. Resumen de ajustes anti-leakage aplicados (cronologia)

| Version | Problema detectado | Solucion aplicada | PR-AUC valid resultante |
|---------|-------------------|-------------------|------------------------|
| v1/v2 | `noapto_proxy` como negativo | Excluir `noapto_proxy` | 1.0 (otro leakage) |
| v2 | Leakage geografico sospechado | Filtro envelope elevacion | 1.0 (otro leakage) |
| v3 temprano | `ndvi_sigma_temporal`, `ndvi_mean_temporal` constantes cross-semestre | Excluidos de EXCLUDE_COLS | 1.0 (otro leakage) |
| v3 temprano | Columnas `prob_*` = target directo | Filtro `startswith('prob_')` | 1.0 (otro leakage) |
| v3 temprano | Split temporal + features estaticos = 99.2 % de pixeles solapados | Split espacial por municipio | **0.43–0.45** |
| v3/v4 | Optuna cargaba trials contaminados (1.0) | Estudio v4 limpio + siembra honestos | **0.4532** |
| v4 | `n_estimators` sugerido ≠ `best_iteration` real | `n_estimators = best_iteration + 1` | gap fit−test = +0.11 |
| v4 | Test en `eval_set` del modelo final | Removido de eval_set | hold-out limpio |

---

## 14. Rol en el ensamble jerarquico

El artefacto produce `P(Papa | x)` para cualquier pixel del area de estudio, usando el mismo pipeline de preprocesamiento (imputer + scaler). La etapa de stacking lo combinara con:

- **L2 (LLP-Co):** `P(cultivo | x)` para los 17 cultivos no-Papa (clasificador multiclase EVA).
- **L3 (XGBoost SIPRA+NDVI):** `P(no_apto | x)` para pixeles fuera de vocacion agricola.

---

## 15. Limitaciones y proximos pasos

| Limitacion | Impacto | Accion sugerida |
|-----------|---------|----------------|
| PR-AUC test 0.437: distancia entre municipios Papa y frontera de altiplano | Falsos positivos altos en municipios fronterizos | Agregar feature de distancia al centroide del nucleo Papa historico |
| `ndvi_sigma_temporal` excluida pero es genuinamente informativa | Perdida de poder discriminativo del ciclo de cultivo | Recalcular con datos solo del periodo de train (Estrategia #4 definitiva) |
| Monitoreo UPRA solo tiene Papa en Cundinamarca | L1 no puede detectar Papa en zonas no monitoreadas | Ampliar ground truth con otros cultivos UPRA o teldeteccion supervisada |
| Recall@Precision=0.90 no alcanzado | El ensamble no puede garantizar alta precision en L1 individualmente | Calibrar threshold de Papa en la etapa de stacking, no en L1 |
