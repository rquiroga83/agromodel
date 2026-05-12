# Estrategia de Modelado AgroPlus — Documento Técnico Detallado

**Proyecto:** AgroPlus — Clasificación multiclase de cultivos agrícolas por píxel-semestre  
**Alcance:** Modelado con múltiples fuentes de datos heterogéneas (CRISP-DM)  
**Resolución espacial:** 50 m/píxel | **Temporal:** semestral (2020A–2024A)  
**Región:** Cundinamarca, Colombia  

---

## Tabla de Contenido

1. [Visión General](#1-visión-general)
2. [Fuentes de Datos y Etiquetado Jerárquico](#2-fuentes-de-datos-y-etiquetado-jerárquico)
3. [Arquitectura del Ensamble Jerárquico](#3-arquitectura-del-ensamble-jerárquico)
4. [Modelo L2 — LLP-Co (Learning from Label Proportions)](#4-modelo-l2--llp-co)
5. [Modelo L1 — UPRA Papa (Ground Truth Binario)](#5-modelo-l1--upra-papa)
6. [Modelo L3 — No Apto (Proxy SIPRA + NDVI)](#6-modelo-l3--no-apto)
7. [Ensamble — Stacking (Meta-modelo)](#7-ensamble--stacking)
8. [Features del Modelo](#8-features-del-modelo)
9. [Estrategia de Validación Espacial](#9-estrategia-de-validación-espacial)
10. [Optimización de Hiperparámetros](#10-optimización-de-hiperparámetros)
11. [Métricas de Evaluación](#11-métricas-de-evaluación)
12. [Controles Anti-Leakage](#12-controles-anti-leakage)
13. [Artefactos y Reproducibilidad](#13-artefactos-y-reproducibilidad)
14. [Riesgos y Mitigaciones](#14-riesgos-y-mitigaciones)

---

## 1. Visión General

### 1.1 Problema

Predecir, para cada píxel de 50 m del territorio de Cundinamarca en cada semestre agrícola, la **distribución de probabilidad** sobre un catálogo de cultivos agrícolas. El resultado no es una clase única sino un ranking probabilístico que permite a tomadores de decisiones agrícolas evaluar alternativas.

### 1.2 Desafío central

Las etiquetas de entrenamiento provienen de tres fuentes con niveles de granularidad y confianza radicalmente distintos:

| Fuente | Granularidad | Confianza | Cobertura |
|--------|-------------|-----------|-----------|
| Monitoreo UPRA | Píxel (polígono) | 1.0 (ground truth) | ~5–15% de pixeles |
| EVA Municipal | Municipio-semestre | 0.30–0.70 (etiqueta débil) | ~70–85% de pixeles |
| Proxy SIPRA+NDVI | Píxel (regla) | 0.40 (proxy negativo) | ~5–15% de pixeles |

Ninguna fuente por sí sola cubre todos los cultivos con calidad suficiente. La estrategia de modelado debe **explotar la complementariedad** de estas fuentes sin introducir fuga de información (leakage).

### 1.3 Solución: Ensamble Jerárquico por Nivel de Etiquetado

En lugar de un único modelo multiclase que mezcla etiquetas duras y blandas, se entrenan **modelos especializados por nivel de etiquetado** y se combinan en un meta-modelo (stacking):

```
                    ┌─────────────────────┐
                    │   META-MODELO        │
                    │   (LogReg / XGBoost) │
                    │   18+2 clases final  │
                    └──────┬──────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
   │  L2 (EVA)   │  │  L1 (UPRA)  │  │  L3 (Proxy) │
   │  LLP-Co     │  │  XGBoost    │  │  XGBoost    │
   │  16-17 clas │  │  Binario    │  │  Binario    │
   │  Soft labels│  │  P(Papa|x)  │  │  P(NoApto|x)│
   └─────────────┘  └─────────────┘  └─────────────┘
```

Cada nivel opera sobre su subconjunto de datos óptimo y produce probabilidades complementarias. El meta-modelo aprende a calibrar y combinar estas señales.

---

## 2. Fuentes de Datos y Etiquetado Jerárquico

### 2.1 Monitoreo UPRA (L1)

**Archivos:** `raw/target/monitoreo/*.geojson` (14 GeoJSON)  
**Contenido:** Polígonos georreferenciados de cultivos reales con verificación de campo (confianza = 1.0). UPRA monitorea activamente en el altiplano cundiboyacense.

**Cultivos con observaciones:**
- **Papa** (~127k polígonos, 2021A–2024A) — especie dominante, concentrada en la franja 2200–3200 msnm
- **Maíz** (2021A–2023B) — decenas a cientos de polígonos
- **Arroz** (~490 polígonos, zonas cálidas)
- **Cacao** (2020A–2023A)

**Valor para el modelo:** Ground truth espacial y temporalmente preciso. Base de confianza máxima del dataset. Sin embargo, la cobertura es limitada geográficamente (principalmente altiplano) y temáticamente (Papa domina >>95% de los registros).

**Decisión de diseño:** Dado que UPRA prácticamente solo monitoriza Papa con cobertura significativa, L1 se plantea como un **clasificador binario Papa vs no-Papa**, no multiclase. Esto evita sesgar el modelo hacia el espacio geográfico de la Papa.

### 2.2 EVA Municipal (L2)

**Archivo:** `raw/target/eva/eva_upra_2019_2024_cundinamarca.csv`  
**Contenido:** Evaluaciones Agropecuarias Municipales — datos tabulares con `area_sembrada`, `area_cosechada` y `rendimiento` por (municipio, año, cultivo). **Sin geometría.**

- 13,218 registros, 109 cultivos únicos, 116 municipios
- Top-12 cultivos cubren ~80% del área cosechada
- Papa domina ~27%, seguida de Caña Panelera (~15%) y Café (~10%)

**Problema fundamental:** EVA reporta a nivel de municipio, no de píxel. Si un municipio tiene 40% Papa, 30% Caña, 20% Café, la etiqueta por defecto sería "Papa" para todos sus píxeles. Esto introduce **correlación espacial masiva** dentro del municipio.

**Mitigación — Soft labels probabilísticas:**
En lugar de asignar una clase hard, se construye un vector de proporciones `W ∈ ℝ^K` por píxel-semestre, donde `W[k] = area_cosechada_cultivo_k / area_agrícola_total` del municipio. Esto transforma una etiqueta hard ruidosa en una **distribución de probabilidad** que preserva la información de todos los cultivos presentes.

**Valor para el modelo:** Cubre el 95%+ de los píxeles con señal probabilística. Permite que el modelo aprenda cultivos sin monitoreo UPRA (Caña, Café, Frijol, etc.) a partir de sus condiciones agroclimáticas municipales.

### 2.3 Proxy No Apto (L3)

**Fuentes:** Polígonos SIPRA de aptitud potencial + NDVI máximo global  
**Criterio:** Un píxel se marca como `No_apto` si:
- SIPRA lo clasifica como "No apta" en ≥3 capas de cultivo, **Y/O**
- `NDVI_max < 0.15` (suelo desnudo/agua/urbano sin vegetación)

**Confianza:** 0.40 — es un proxy negativo, no una observación directa.

**Uso:** Solo aporta evidencia de **ausencia de aptitud agrícola**. SIPRA **no se usa para etiquetas positivas** (elimina la fuga circular detectada en la versión anterior del pipeline, donde el modelo "aprendía SIPRA" en vez de condiciones reales).

### 2.4 MGN-DANE (puente EVA↔píxel)

**Extractor:** `extractores/09_extraer_municipios_dane.py`  
**Contenido:** Polígonos oficiales de los 116 municipios de Cundinamarca con código DANE de 5 dígitos, rasterizados al grid de 50 m.

**Rol:** Es el **puente** entre la tabla EVA (indexada por `cod_mun`) y los píxeles del raster. Cada píxel recibe su `cod_mun` para poder asignarle las proporciones EVA correspondientes.

**Crucial:** `cod_mun` **no es feature** del modelo. Solo se usa como clave de lookup para etiquetado y para la validación por bloques espaciales.

---

## 3. Arquitectura del Ensamble Jerárquico

### 3.1 Principio de diseño

La arquitectura sigue el principio de **especialización por calidad de etiqueta**: cada sub-modelo se entrena sobre el subconjunto de datos donde su fuente de etiquetas es más fuerte, y produce probabilidades que el meta-modelo combina.

### 3.2 Catálogo de clases por nivel

El catálogo final del ensamble consta de **18–19 clases** distribuidas entre los tres niveles:

| Nivel | Clases modeladas | Tipo de etiqueta | Algoritmo |
|-------|-----------------|------------------|-----------|
| **L2 EVA** | 16–17 cultivos no-Papa, no-NoApto: Caña_Panelera, Café, Maíz, Plátano, Mango, Frijol, Cacao, Arveja, Palma, Banano, Cítricos (o Naranja), Mora, Zanahoria, Tomate_Arbol, Yuca, Habichuela, (Hortalizas) | Soft label (proporciones EVA) | LLP-Co (PyTorch) + fallback XGBoost soft-label |
| **L1 UPRA** | Papa (binario: Papa vs no-Papa) | Hard label (ground truth) | XGBoost binario |
| **L3 Proxy** | No_apto (binario: NoApto vs agrícola) | Hard label (proxy SIPRA+NDVI) | XGBoost binario |

**Nota sobre evolución del catálogo L2:**
- **Versión Ensemble (16 clases):** Top-11 originales + 5 nuevos (Mora, Zanahoria, Tomate_Arbol, Yuca, Habichuela). `Otros_cultivos` descartado por baja calidad de etiqueta.
- **Versión LLP-Co standalone (17 clases):** Se agrega `Hortalizas` (cultivos intensivos de ciclo corto de la Sabana) y se agrupa `Naranja→Cítricos` (Naranja + Mandarina + Limón + Tangelo, indistinguibles a 50m, ~62K ha).

### 3.3 Flujo de predicción

Para un píxel nuevo `x`:

```
P(cultivo | x) = META-MODELO(
    P_L2(Caña | x), P_L2(Café | x), ..., P_L2(Habichuela | x),   # 16-17 probs
    P_L1(Papa | x),                                                 # 1 prob
    P_L3(NoApto | x)                                                # 1 prob
)
```

El meta-modelo recibe 18–19 probabilidades de entrada y produce la distribución final sobre el catálogo completo.

---

## 4. Modelo L2 — LLP-Co

**Notebook:** `modelado/CRISP_DM_AgroPlus_LLP_Co.ipynb`  
**Referencia:** La Rosa, Oliveira & Ghamisi (2022). *Learning crop type mapping from regional label proportions in large-scale SAR and optical imagery*. arXiv:2208.11607v1.

### 4.1 Motivación

El modelo L2 enfrenta un problema de **Learning from Label Proportions (LLP)**: las etiquetas de entrenamiento son distribuciones de proporciones a nivel de municipio (bags), no clases individuales por píxel. Un clasificador multiclase estándar (XGBoost con `argmax` como target) desperdicia la información distribucional y trata cada píxel como si fuera un ejemplo hard.

LLP-Co (Learning from Label Proportions with Contrastive clustering) resuelve este problema mediante:

1. **Representación latente** — Un encoder proyecta píxeles a un espacio donde cultivos similares se agrupan.
2. **Prototipos de clase** — K vectores entrenables, uno por cultivo, en el espacio latente.
3. **Transporte óptimo restringido** — El algoritmo de Sinkhorn-Knopp asigna píxeles a prototipos respetando las proporciones EVA del municipio.
4. **Aprendizaje contrastivo swap** — Dos vistas aumentadas del mismo píxel se entrenan para predecir mutuamente sus asignaciones, estabilizando el aprendizaje.

### 4.2 Adaptación de imagen a tabular

El paper original usa ResNet18 sobre patches de imágenes satelitales. La adaptación a datos tabulares de AgroPlus reemplaza el CNN por un **MLP encoder**:

```
Input (F features)
  → Linear(F, 256) → LayerNorm → GELU → Dropout(0.2)
  → Linear(256, 128) → LayerNorm → GELU → Dropout(0.2)
  → Linear(128, 64) → LayerNorm → GELU → Dropout(0.2)
  → Linear(64, emb_dim)
  → L2 Normalize → Embedding z ∈ S^{emb_dim-1}
```

Dimensiones: `emb_dim` = 512 (LLP-Co standalone) o 1024 (Ensemble).

### 4.3 Componentes del modelo

#### 4.3.1 MLPEncoder

Arquitectura de 4 capas progresivas (256→128→64→emb_dim) con normalización LayerNorm, activación GELU y Dropout(0.2). La salida se normaliza L2 para proyectar los embeddings sobre la hiperesfera unitaria, habilitando similitud coseno con los prototipos.

#### 4.3.2 Prototipos (Prototypes)

`V ∈ ℝ^{K × emb_dim}` — K vectores entrenables, uno por clase de cultivo.

- **Inicialización ortogonal** (QR decomposition): máxima separación inicial entre prototipos, previniendo colapso prematuro.
- Se normalizan L2 antes de computar similitud coseno: `score(z, V_k) = z · V_k / (||z|| · ||V_k||)`.
- Congelados durante la primera época para estabilizar el encoder.

#### 4.3.3 Augmentación de features

Se generan **dos vistas aumentadas** por píxel mediante una estrategia **diferenciada por grupo semántico**:

| Grupo | Variables | Dropout | Ruido σ | Justificación |
|-------|-----------|---------|---------|---------------|
| Topográfico | elevación, pendiente, TWI, aspecto, piso_térmico | 0% | 0.01 | Datos estáticos, sin incertidumbre |
| Suelo | sg_*, igac_*, indice_fertilidad | 0% | 0.01 | Datos cuasi-estáticos |
| Clima | temperatura_media, humedad, chirps, amplitud_termica, etc. | 10% | 0.05 | Variabilidad interanual moderada |
| Sentinel-2 | s2_ndvi_*, s2_gndvi_*, s2_bsi_*, s2_msavi_*, ndvi_integral | 20% | 0.05 | Alta variabilidad + nubosidad |
| Otro | Variables residuales | 10% | 0.025 | Conservador |

La augmentación de S2 con dropout alto simula la **cobertura de nubes**, un fenómeno frecuente en imágenes tropicales.

#### 4.3.4 Sinkhorn-Knopp con restricción de proporciones

Solver de **Transporte Óptimo** que asigna píxeles a prototipos respetando las proporciones EVA del municipio:

```
Entrada:  scores ∈ ℝ^{n × K} (similitudes), w ∈ ℝ^K (proporciones EVA, suma=1)
Salida:   Q ∈ ℝ^{n × K} (asignaciones, filas suman 1, columnas con masa ∝ w·n)

Q = exp(scores / ε)           # Kernel RBF
for iter in range(5):
    Q *= (w·n) / Q.sum(col)   # Normalizar columnas → masa proporcional a w
    Q *= 1 / Q.sum(row)        # Normalizar filas → asignación por píxel
```

Parámetros clave:
- **ε (EPS_SK):** Regularización entrópica. Valores bajos (0.01) = más fiel al prior EVA; altos (0.10) = más uniforme.
- **Truco de estabilidad:** Restar el máximo por fila antes de exponenciar previene overflow numérico.

#### 4.3.5 Swap Loss ponderada

Pérdida contrastiva intercambiada entre las dos vistas (ecuaciones 7-9 del paper):

```
L_swap = (1/n) Σ_i [ ℓ(z_t^i, q_s^i) + ℓ(z_s^i, q_t^i) ]

donde ℓ(z, q) = -Σ_k q_k · log(p_k(z))
```

**Ponderación por frecuencia inversa de clase** para combatir colapso de prototipos:

```
class_weight_k = 1 / (w_k + ε)       # Clases raras → mayor peso
pixel_weight_i = Σ_k q_ik · class_weight_k
```

Esto evita que clases dominantes (Café, Caña) absorban la mayoría de los píxeles.

#### 4.3.6 Regularización KoLeo

Penaliza prototipos similares entre sí para mantenerlos separados en la hiperesfera:

```
L_koleo = (1/(K(K-1))) Σ_{j≠k} (V_j · V_k)²
```

Previene el colapso de prototipos (dos o más prototipos convergiendo al mismo vector).

### 4.4 Bags dinámicos por municipio

Cada municipio forma un **bag** cuya proporción objetivo `w_mun` es el promedio EVA de todos sus píxeles. En cada época:

1. Se barajean los municipios en orden aleatorio.
2. Por cada municipio, se muestrean hasta `BAG_SIZE=2048` píxeles sin reemplazo (o todos si el pool es menor).
3. Se computa el paso de gradiente sobre el bag.

Esta estrategia de muestreo dinámico (vs. bags fijos) introduce **estocasticidad por época**, mejorando la generalización.

### 4.5 Máscara agrícola

Antes de formar los bags, se aplican tres filtros secuenciales para excluir píxeles no agrícolas:

| Filtro | Criterio | Excluye |
|--------|----------|---------|
| F1 | `ndvi_mean_temporal < 0.15` | Suelo desnudo, agua, urbano |
| F2 | `ndvi_mean > 0.80 AND ndvi_sigma < 0.06` | Bosque primario denso (alta y estable) |
| F3 | `ndvi_mean > 0.55 AND ndvi_sigma < 0.04` | Bosque secundario / pastura permanente |

`ndvi_sigma_temporal` y `ndvi_mean_temporal` se calculan sobre **todos los semestres** del raster (no solo el muestreado), proporcionando una firma temporal robusta.

### 4.6 Fallback — XGBoost con Soft Labels

Como plan B (si LLP-Co no converge), se entrena un XGBoost multiclase con **expansión de soft labels**:

```
Para cada píxel con W = (w₁, ..., w_K):
  Para cada clase k donde w_k > 0.05:
    Crear fila (x_píxel, y=k) con peso = w_k × class_balanced_k
```

Esto equivale matemáticamente a minimizar la entropía cruzada con soft targets. Más sencillo pero menos elegante que LLP-Co.

### 4.7 Hiperparámetros (espacio de búsqueda Optuna)

| Parámetro | Rango | Rol |
|-----------|-------|-----|
| `TAU` | 0.05 – 0.20 (log) | Temperatura softmax; bajo = predicciones nítidas |
| `EPS_SK` | 0.005 – 0.10 (log) | Regularización Sinkhorn; bajo = fiel al prior EVA |
| `SIGMA_AUG` | 0.01 – 0.15 (log) | Intensidad de ruido en augmentación |
| `LR_INIT` | 0.05 – 0.30 (log) | Tasa de aprendizaje inicial |
| `KOLEO_WEIGHT` | 0.01 – 0.50 (log) | Peso de regularización KoLeo |
| `P_DROP_AUG` | 0.05 – 0.40 | Probabilidad de dropout en augmentación S2 |
| `WEIGHT_DECAY` | 1e-7 – 1e-3 (log) | Regularización L2 del optimizador |

### 4.8 Métricas de evaluación L2

| Métrica | Qué mide | Interpretación |
|---------|----------|----------------|
| **KL(w_eva ‖ w_pred)** por bag | Divergencia entre proporciones EVA reales y predichas | Métrica nativa de LLP; 0 = perfecto |
| **Top-K Accuracy** (K=1,3,5,8) | Si el cultivo argmax(W) está en el top-K predicho | Apropiado para distribuciones suaves |
| **Acc_H (Hungarian)** | Accuracy post-alineamiento de prototipos | Corrige el swap de clusters del aprendizaje contrastivo |
| **Recall@K por clase** | Recall desagregado por cultivo | Detecta clases con baja separabilidad |
| **Similitud coseno entre prototipos** | Separabilidad de clases en espacio latente | Off-diagonal cercana a 0 = clases bien separadas |

**Evaluación Hungarian:** Siguiendo el paper (Sec. V), se usa el algoritmo de asignación Húngaro para mapear prototipos a clases antes de calcular accuracy. Sin esto, el swap de clusters produce `Acc_H >> Acc_P`.

---

## 5. Modelo L1 — UPRA Papa

**Notebook:** `modelado/CRISP_DM_AgroPlus_L1_UPRA.ipynb`

### 5.1 Justificación del modelo dedicado

- **Cobertura concentrada:** Papa se cultiva casi exclusivamente en la franja 2200–3200 msnm del altiplano cundiboyacense. Un modelo binario explota mejor esta firma topo-climática.
- **Calidad de etiqueta superior:** UPRA hace monitoreo predial con verificación de campo (`confianza = 1.0`).
- **Ciclo distintivo:** Papa tiene dos cosechas anuales (semestres A y B) con dinámicas NDVI reconocibles.
- **Evitar sesgo:** Modelar todos los cultivos simultáneamente con datos UPRA sesgaría el modelo hacia el espacio geográfico de la Papa.

### 5.2 Formulación

- **Task:** Clasificación binaria `y = 1` si Papa, `y = 0` si no-Papa
- **Datos:** `fuente == 'monitoreo'` (exclusivamente)
- **Modelo:** XGBoost binario con `scale_pos_weight` para manejar el desbalance
- **Métrica primaria:** PR-AUC (más robusto que ROC-AUC en clases desbalanceadas)

### 5.3 Preprocesamiento

1. **Filtro de varianza:** Se eliminan variables cuasi-constantes (clase modal > 80% de los píxeles). Ejemplo: `igac_fosforo` (93% categoría 1), `igac_ph` (73%), `igac_potasio` (73%).
2. **Filtro de correlación:** Para cada par con `|r| > 0.85`, se elimina la variable más conectada globalmente (mayor correlación media con el resto). Se eliminan redundancias conocidas: `temperatura_max`, `temperatura_min` (redundantes con `temperatura_media` + `amplitud_termica`), `s2_savi_*` (redundantes con `s2_msavi_*`), `ndvi_max` (duplica `s2_ndvi_max`).
3. **Imputación:** Mediana del conjunto de entrenamiento (ajustada solo sobre train).
4. **Escalado:** StandardScaler (opcional para XGBoost, mantiene pipeline reusable).

### 5.4 Diagnóstico univariado

Antes del modelado, se mide la relación de cada feature con el target binario:

- **Point-biserial r:** Correlación lineal entre feature y target binario. Rojo = asociado a Papa; azul = asociado a no-Papa.
- **Mutual Information:** Relación no lineal. Más informativa cuando la asociación no es monotónica.

Las variables topo-climáticas (elevación, temperatura, pendiente) muestran fuerte señal diferenciadora, consistente con el nicho ecológico de la Papa.

### 5.5 Optimización bayesiana (Optuna)

| Hiperparámetro | Rango | Rol |
|----------------|-------|-----|
| `n_estimators` | 200 – 1500 | Número de árboles (con early stopping) |
| `max_depth` | 3 – 12 | Profundidad máxima |
| `learning_rate` | 0.01 – 0.30 (log) | Tasa de aprendizaje |
| `subsample` | 0.5 – 1.0 | Fracción de filas por árbol |
| `colsample_bytree` | 0.4 – 1.0 | Fracción de features por árbol |
| `min_child_weight` | 1 – 20 | Peso mínimo en hoja |
| `gamma` | 0.0 – 5.0 | Poda mínima |
| `reg_alpha` | 1e-4 – 5.0 (log) | Regularización L1 |
| `reg_lambda` | 1e-4 – 5.0 (log) | Regularización L2 |

**Estrategia:** Maximizar PR-AUC en validación. Estudio persistente en SQLite para reanudación. Modelo final re-entrenado sobre train+valid con los mejores hiperparámetros.

### 5.6 Selección de umbral operativo

El threshold por defecto (0.5) no es óptimo en problemas desbalanceados. Se comparan:

| Criterio | Objetivo |
|----------|----------|
| **Máximo F1** | Balance precision-recall |
| **Youden J** | Máximo (TPR - FPR) sobre la curva ROC |
| **Recall@Precision≥0.90** | Umbral más alto que garantiza ≥90% de precisión |

**Criterio de éxito del proyecto:** Recall@Precision=0.90 ≥ 0.70 (capturar al menos 70% de los pixeles Papa con 90% de precisión).

### 5.7 Métricas de evaluación L1

| Métrica | Qué mide |
|---------|----------|
| **ROC-AUC** | Capacidad de ranking general |
| **PR-AUC** | Ranking sobre la clase positiva (Papa) |
| **Brier score** | Calibración de probabilidades |
| **Log-loss** | Penaliza confianza excesiva en errores |
| **Curva de calibración** | Si P(Papa)=0.7, ¿el 70% son Papa realmente? |

---

## 6. Modelo L3 — No Apto

### 6.1 Formulación

- **Task:** Clasificación binaria `y = 1` si No_apto, `y = 0` si agrícola
- **Datos:** `fuente == 'noapto_proxy'` (SIPRA ≥3 capas "No apta" ∪ NDVI_max < 0.15)
- **Modelo:** XGBoost binario (misma arquitectura que L1)

### 6.2 Justificación

El proxy L3 identifica píxeles claramente no agrícolas. Separa esta señal del modelo L2 para que LLP-Co no tenga que aprender simultáneamente 16 cultivos + la clase "no es cultivo", que tiene una firma biofísica muy distinta (NDVI bajo, SIPRA rechazo).

---

## 7. Ensamble — Stacking

**Notebook:** `modelado/CRISP_DM_AgroPlus_Ensemble.ipynb`

### 7.1 Arquitectura

```
Input: features tabulares del píxel (F dimensiones)

Paso 1: L2 (LLP-Co o XGBoost soft)
  → P_L2 = (p_Caña, p_Café, ..., p_Habichuela) ∈ ℝ^16-17

Paso 2: L1 (XGBoost UPRA)
  → P_L1 = P(Papa | x) ∈ [0,1]

Paso 3: L3 (XGBoost Proxy)
  → P_L3 = P(NoApto | x) ∈ [0,1]

Paso 4: Meta-modelo (LogReg o XGBoost)
  Input: concatenación [P_L2, P_L1, P_L3]
  Output: P_final ∈ ℝ^18-19 (distribución sobre catálogo completo)
```

### 7.2 Normalización del vector de probabilidades

Las tres salidas se reescalan para formar un vector de probabilidad válido:

```
P_total = P_L2 × (1 - P_L1) × (1 - P_L3)    # cultivos L2, reescalados
        + P_L1 × one_hot(Papa)                 # contribución de Papa
        + P_L3 × one_hot(No_apto)              # contribución de NoApto
```

Opcionalmente, el meta-modelo aprende esta combinación de forma no lineal.

### 7.3 Decisión de modelo L2

El notebook Ensemble implementa ambos modelos (LLP-Co y XGBoost soft-label) y los compara automáticamente:

```python
if F1_llp > F1_xgb and KL_llp <= KL_xgb * 1.1:
    CHOICE = 'llp_co'
else:
    CHOICE = 'xgb_soft'
```

La decisión se persiste en `checkpoints/l2_choice.json` para que los pasos 2 y 3 la lean.

---

## 8. Features del Modelo

### 8.1 Catálogo de features por categoría

| Categoría | N features | Variables | Dinámico/Estatico |
|-----------|-----------|-----------|-------------------|
| Topografía | ~6 | elevación, pendiente, TWI, aspecto_sin, aspecto_cos, piso_térmico | Estático |
| Suelo SoilGrids | ~8 | sg_phh2o, sg_soc, sg_nitrogen, sg_cec, sg_bdod, sg_clay, sg_sand, sg_silt | Estático |
| Suelo IGAC | ~5 | igac_fertilidad, igac_fosforo, igac_ph, igac_potasio, igac_vocacion | Estático |
| Suelo derivado | ~1 | indice_fertilidad | Estático |
| Clima IDEAM | ~4 | temperatura_media, humedad_media, chirps_acum, amplitud_termica | Dinámico |
| Clima derivado | ~2 | anomalia_precip, indice_aridez | Dinámico |
| Sentinel-2 NDVI | ~3 | s2_ndvi_media, s2_ndvi_max, s2_ndvi_std | Dinámico |
| Sentinel-2 GNDVI | ~3 | s2_gndvi_media, s2_gndvi_max, s2_gndvi_std | Dinámico |
| Sentinel-2 MSAVI | ~3 | s2_msavi_media, s2_msavi_max, s2_msavi_std | Dinámico |
| Sentinel-2 BSI | ~3 | s2_bsi_media, s2_bsi_max, s2_bsi_std | Dinámico |
| Vegetación derivada | ~1 | ndvi_integral | Dinámico |

### 8.2 Variables excluidas (y por qué)

| Variable | Razón de exclusión |
|----------|-------------------|
| `pixel_id`, `x`, `y` | Identificadores, no features |
| `cod_mun`, `semestre` | Puente EVA, no features (evitar memorización municipal) |
| `cultivo`, `cultivo_id`, `confianza`, `fuente` | Target y metadatos de etiquetado |
| `prob_*` | Soft labels (son el target de L2, no features) |
| `temperatura_max`, `temperatura_min` | Redundantes con `temperatura_media` + `amplitud_termica` (r > 0.98) |
| `s2_savi_*` | Redundantes con `s2_msavi_*` (r > 0.99) |
| `ndvi_max` | Duplica exactamente `s2_ndvi_max` (r = 1.0) |
| Variables cuasi-constantes | Clase modal > 80% (ej: igac_fosforo 93%, igac_ph 73%) |

### 8.3 Selección de features finalizada

El proceso de selección ocurre en **tres etapas**:

1. **Exclusión a priori:** Variables de metadata, target, soft labels y redundancias conocidas.
2. **Filtro de varianza:** Variables donde la clase modal supera el 80% de los píxeles (varianza cuasi-nula, correlación artefactuada).
3. **Filtro de correlación:** Para cada par con `|r| > 0.85`, se elimina la variable con mayor correlación media con el resto (más redundante globalmente).

El resultado se visualiza con un heatmap de correlación con clustering jerárquico Ward para verificar la estructura de dependencia residual.

---

## 9. Estrategia de Validación Espacial

### 9.1 Principio

La validación aleatoria (por píxel) produce métricas infladas en ~20–40 puntos porcentuales porque los píxeles de un mismo municipio L2 comparten etiqueta. Además, los píxeles vecinos están altamente correlacionados espacialmente (autocorrelación).

### 9.2 Implementación

**GroupShuffleSplit / StratifiedGroupKFold con `groups = cod_mun`:**

```
Split 1: 85% (train+valid) / 15% test   → por municipio
Split 2: 70% train / 15% valid          → por municipio (del 85%)
```

**Garantías:**
- Ningún municipio aparece en más de un fold.
- Todas las clases están representadas en cada split (estratificación por cultivo dominante del municipio).
- Los municipios se agrupan por su cultivo dominante (argmax del promedio W_norm) para estratificar; grupos con <4 municipios se fusionan en un grupo "Minoritario".

### 9.3 Tamaños típicos

| Split | Fracción | Municipios | Pixeles (estimado) |
|-------|----------|------------|-------------------|
| Train | 70% | ~80 | ~3.5M |
| Valid | 15% | ~18 | ~750K |
| Test | 15% | ~18 | ~750K |

---

## 10. Optimización de Hiperparámetros

### 10.1 Framework

**Optuna** con sampler **TPE multivariado** (Tree-structured Parzen Estimator) y **MedianPruner** para podar trials no prometedores.

### 10.2 Estudios persistentes

Cada estudio se almacena en **SQLite** para permitir reanudación sin perder trials previos:

| Modelo | Base de datos | Variable objetivo |
|--------|---------------|-------------------|
| L2 LLP-Co | `optuna_llp_co.db` (estudio `llp_co_v2`) | Minimizar KL_valid |
| L1 UPRA | `optuna_l1_upra.db` (estudio `l1_upra_xgb_v1`) | Maximizar PR-AUC valid |

### 10.3 Detección de colapso (LLP-Co)

En cada epoch del trial Optuna, se verifica que ningún prototipo absorba >60% de los píxeles. Si ocurre, el trial se poda inmediatamente (colapso de prototipos).

### 10.4 Diagnóstico post-Optuna

- **Historia de optimización:** KL_valid o PR-AUC por trial.
- **Importancia de hiperparámetros** (fANOVA): identifica qué parámetros más impactan el rendimiento.
- **Contorno de parámetros:** Superficie KL_valid en el espacio (TAU, EPS_SK).

---

## 11. Métricas de Evaluación

### 11.1 Métricas por nivel

| Nivel | Métrica primaria | Métricas secundarias |
|-------|-----------------|---------------------|
| **L2 LLP-Co** | KL divergence por bag | Top-K Accuracy, Acc_H (Hungarian), Recall@K por clase, similitud entre prototipos |
| **L2 XGBoost fallback** | F1 macro vs argmax(W_eva) | KL por bag, classification_report |
| **L1 UPRA** | PR-AUC | ROC-AUC, Brier score, Log-loss, F1 @ threshold óptimo |
| **L3 Proxy** | PR-AUC | ROC-AUC, F1 |
| **Ensamble** | F1 macro (18-19 clases) | Accuracy, Top-K, métricas desagregadas por fuente |

### 11.2 Métricas desagregadas

Siguiendo las mejores prácticas, se reportan métricas **desagregadas por fuente de etiqueta** (monitoreo vs EVA vs proxy), no solo agregadas. Una métrica agregada mezcla señal clara (L1) con ruido probabilístico (L2).

### 11.3 Matriz de Confusión Semántica Top-K

Estándar de oro en clasificación de tierras agrícolas (La Rosa 2022, ISPRS):

- **Diagonal:** Fracción de píxeles donde la clase verdadera está en el Top-K del modelo (recall@K).
- **Off-diagonal:** Cuando el modelo falla (clase verdadera fuera de Top-K), muestra a qué clase fue asignado el Top-1.

Un Top-3 Accuracy > 80% significa que el modelo redujo 16 opciones a 3 altamente probables, suficiente para asistir decisión agronómica.

---

## 12. Controles Anti-Leakage

### 12.1 Controles implementados

| Control | Descripción | Dónde se aplica |
|---------|-------------|-----------------|
| **SIPRA no es etiqueta positiva** | SIPRA solo aporta al proxy No_apto (L3). Nunca indica "este píxel es cultivo X". | `04_construir_vista_minable.py` |
| **Piso térmico no es regla de etiquetado** | La versión anterior asignaba cultivos EVA por piso térmico → fuga. Ahora EVA se asigna por municipio completo. | Eliminado en rediseño |
| **`cod_mun` no es feature** | El municipio es clave de lookup EVA, no variable predictiva. El modelo no puede memorizar "municipio X = cultivo Y". | Excluido en todos los notebooks |
| **Validación por municipio** | GroupShuffleSplit garantiza que ningún municipio aparece en train y test simultáneamente. | Todos los modelos |
| **Imputación sobre train** | Medianas del imputer se calculan solo sobre train; valid y test se transforman con esos parámetros. | L1 UPRA |
| **Scaler sobre train** | StandardScaler se ajusta solo sobre train. | Todos los modelos |

### 12.2 Verificación empírica

En todos los notebooks se incluyen asserts explícitos:

```python
assert len(mun_tr & mun_va) == 0
assert len(mun_tr & mun_te) == 0
assert len(mun_va & mun_te) == 0
print("OK: sin intersección de municipios entre train/valid/test")
```

---

## 13. Artefactos y Reproducibilidad

### 13.1 Artefactos persistidos

| Archivo | Contenido | Formato |
|---------|-----------|---------|
| `checkpoints/l2_llp_co.pt` | Encoder + Prototipos + config + history | PyTorch state_dict |
| `checkpoints/l2_xgb_soft.json` | XGBoost fallback L2 | XGBoost native |
| `checkpoints/l2_choice.json` | Decisión LLP-Co vs XGBoost | JSON |
| `checkpoints/l1_upra_papa.joblib` | Modelo L1 + imputer + scaler + feature_cols + threshold + métricas | Joblib |

### 13.2 Semillas de aleatoriedad

```python
np.random.seed(42)
torch.manual_seed(42)
torch.cuda.manual_seed_all(42)  # Si CUDA disponible
random_state=42                  # sklearn, XGBoost, Optuna
```

### 13.3 Reproducibilidad del entrenamiento LLP-Co

Cada epoch genera un `np.random.RandomState(SEED + epoch)` para el muestreo de bags, haciendo determinista el orden de municipios y la selección de píxeles por bag en cada epoch.

---

## 14. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| **Colapso de prototipos LLP-Co** | Un prototipo absorbe la mayoría de píxeles | Regularización KoLeo + weighted swap loss + detección de colapso en Optuna (prune si max_uso > 60%) |
| **LLP-Co no converge** | KL_valid no desciende | Fallback a XGBoost soft-label (automático en Ensemble) |
| **Clases raras con baja Recall@K** | Mora, Zanahoria, Habichuela con pocos pixeles | Weighted swap loss pondera clases raras; Hortalizas agrupa múltiples especies |
| **Fuga espacial accidental** | Métricas infladas | GroupShuffleSplit por municipio + asserts de no-overlap |
| **`cod_mun` filtrado como feature** | Modelo memoriza municipio→cultivo | Documentado como no-feature; excluido explícitamente |
| **Desbalance extremo L1** | Papa >> no-Papa en monitoreo | `scale_pos_weight` + PR-AUC como métrica primaria + threshold operativo ajustado |
| **SIPRA "No apta" sobre-representa tierras baldías** | L3 agresivo | Umbral conservador: ≥3 capas SIPRA + NDVI < 0.15 |
| **EVA desactualizada o incompleta** | Soft labels ruidosos | `confianza` como peso; renormalización sobre clases finales |
| **Correlación artefactuada en variables cuasi-constantes** | Filtro de correlación elimina variables informativas | Filtro de varianza previo (elimina cuasi-constantes antes del cálculo de Pearson) |

---

## Apéndice A: Referencia de Notebooks

| Notebook | Responsabilidad | Fase CRISP-DM |
|----------|----------------|---------------|
| `CRISP_DM_AgroPlus_LLP_Co.ipynb` | Modelo L2 standalone con LLP-Co, Optuna, evaluación completa | Data Preparation → Modeling → Evaluation |
| `CRISP_DM_AgroPlus_L1_UPRA.ipynb` | Modelo L1 binario Papa, Optuna, calibración | Data Understanding → Modeling → Evaluation |
| `CRISP_DM_AgroPlus_Ensemble.ipynb` | Pipeline completo: L2 (LLP-Co + XGBoost fallback) + decisión automática | Modeling → Evaluation |

## Apéndice B: Referencia Bibliográfica

- **La Rosa, B. E., Oliveira, D. A. B., & Ghamisi, P. (2022).** Learning crop type mapping from regional label proportions in large-scale SAR and optical imagery. *arXiv:2208.11607v1*.
- **Sablayrolles, A. et al. (2023).** KoLeo regularization para distribuciones en hiperesfera. Referencia en DINO family.
- **Sinkhorn, R. & Knopp, P.** Convergence rates for an iterative method of matrix balancing. *Pacific J. Math.*
- **Kuhn, H. W. (1955).** The Hungarian method for the assignment problem. *Naval Research Logistics.*