# Documentación Técnica — Modelo LLP-Co AgroPlus L2
## Clasificación de Cultivos por Proporciones Municipales (Cundinamarca)

> **Base teórica:** La Rosa, Oliveira & Ghamisi (2022). *Learning crop type mapping from regional label proportions in large-scale SAR and optical imagery*. arXiv:2208.11607v1.

---

## 1. ¿Qué hace el modelo funcionalmente?

El modelo LLP-Co (Learning from Label Proportions with Contrastive Clustering) resuelve un problema de **clasificación débilmente supervisada**: en lugar de requerir etiquetas por píxel (costosas y escasas), aprende a clasificar cada píxel a nivel de cultivo usando únicamente las **proporciones de área cultivada reportadas por municipio** en la Evaluación Agropecuaria Municipal (EVA) del MADR.

**Flujo funcional:**

```
Píxel (40 variables geoespaciales)
        │
        ▼
   MLPEncoder  ─────────────►  embedding z ∈ ℝ^512  (L2-normalizado)
        │
        ▼
Similitud coseno con K=17 prototipos entrenables V ∈ ℝ^{17×512}
        │
        ▼
Sinkhorn-Knopp  ◄──── prior w_mun (proporciones EVA del municipio)
   (asignación OT restringida a proporciones del bag)
        │
        ▼
Pérdida Swap entre 2 vistas aumentadas del mismo píxel
        │
        ▼
P(cultivo | píxel) = softmax(z · V^T / τ)   ─►  ranking Top-K cultivos
```

El modelo **no necesita etiquetas individuales por píxel**. La supervisión proviene exclusivamente de las proporciones de área cultivada por municipio-semestre (ej. "en el municipio 25xxx, el 40% es maíz, 30% arveja, 15% fríjol…"). El optimizador fuerza que las probabilidades predichas *promediadas sobre todos los píxeles del municipio* coincidan con esas proporciones censales.

---

## 2. Datos de entrada del modelo

### 2.1 Fuente de datos

La vista minable `vista_minable_full.parquet` es la entrada principal. Se filtra a filas con `fuente == 'eva_municipal'` (capa L2), que corresponde a píxeles con cobertura agrícola georreferenciada según la EVA de Cundinamarca.

### 2.2 Máscara agrícola

Antes del entrenamiento se aplica un filtro de vegetación activa para excluir píxeles no agrícolas:

| Filtro | Criterio | Píxeles removidos |
|--------|----------|------------------|
| Sin vegetación | NDVI medio < 0.15 | 9,534 (0.3%) |
| Bosque primario denso | NDVI alto + baja varianza temporal | 312,102 (10.4%) |
| Bosque secundario / pastura estable | NDVI moderado estable | 343,141 (11.5%) |

**Total píxeles L2 EVA:** 2,990,171 → **2,325,394 píxeles activos** (77.8%)

### 2.3 Variables de entrada (40 features)

Las features se agrupan en cuatro dominios funcionales:

#### Topografía y morfología (5 variables)
| Variable | Descripción |
|----------|-------------|
| `elevacion` | Elevación sobre el nivel del mar (m) — DEM 50m |
| `pendiente` | Inclinación del terreno (°) |
| `twi` | Topographic Wetness Index — capacidad de acumulación hídrica |
| `aspecto_sin` / `aspecto_cos` | Orientación de ladera (descompuesta en seno y coseno) |
| `piso_termico` | Zona altitudinal (frío/templado/cálido/muy frío) — derivado de elevación |

#### Suelo (12 variables)
| Variable | Descripción |
|----------|-------------|
| `sg_phh2o` | pH en agua (SoilGrids 250m) |
| `sg_soc` | Carbono orgánico del suelo (g/kg) |
| `sg_nitrogen` | Nitrógeno total (g/kg) |
| `sg_cec` | Capacidad de intercambio catiónico |
| `sg_bdod` | Densidad aparente (kg/dm³) |
| `sg_clay` / `sg_sand` / `sg_silt` | Textura: arcilla, arena, limo (%) |
| `igac_fertilidad` | Clase de fertilidad IGAC |
| `igac_ph` | pH según mapa de suelos IGAC |
| `igac_potasio` | Contenido de potasio disponible |
| `igac_vocacion` | Vocación de uso del suelo |
| `indice_fertilidad` | Índice compuesto derivado (feature engineering) |

#### Clima — semestre actual (6 variables)
| Variable | Descripción |
|----------|-------------|
| `temperatura_media` | Temperatura media semestral (°C) — Kriging sobre estaciones IDEAM |
| `humedad_media` | Humedad relativa media (%) |
| `chirps_acum` | Precipitación acumulada semestral CHIRPS (mm) |
| `amplitud_termica` | Rango diurno de temperatura (°C) |
| `anomalia_precip` | Desviación de precipitación respecto a la media histórica |
| `indice_aridez` | Índice de aridez compuesto (balance hídrico) |

#### Satélite Sentinel-2 — estadísticas semestrales (17 variables)
| Variable | Descripción |
|----------|-------------|
| `s2_ndvi_media/max/std` | Índice de Vegetación de Diferencia Normalizada |
| `s2_gndvi_media/max/std` | NDVI verde (sensible a clorofila) |
| `s2_msavi_media/max/std` | MSAVI — robusto a suelo desnudo |
| `s2_bsi_media/max/std` | Bare Soil Index |
| `ndvi_integral` | Integral temporal de NDVI (fenología acumulada) |
| `ndvi_sigma_temporal` | Varianza temporal de NDVI (actividad estacional) |
| `ndvi_mean_temporal` | Media temporal de NDVI |

> **Variables excluidas:** `igac_fosforo` (96.8% en clase modal — casi constante) y variables con correlación |r| > 0.85 (alta redundancia).

### 2.4 Proporciones EVA (supervisión débil)

Para cada bag (municipio, semestre), el vector de proporciones `w ∈ Δ_K` (simplex de K clases) se construye a partir de las áreas cosechadas reportadas en la EVA por municipio-semestre, normalizadas a proporción. Estas proporciones son el **único tipo de etiqueta** que el modelo usa durante el entrenamiento.

### 2.5 Partición de datos

| Partición | Municipios | Píxeles |
|-----------|-----------|---------|
| Entrenamiento | 81 | 1,533,342 |
| Validación | 15 | 534,427 |
| Test | 15 | 257,625 |

---

## 3. Arquitectura del encoder MLP

### 3.1 Rol del encoder

El encoder es el componente central del modelo. Transforma las 40 variables geoespaciales de cada píxel en un **vector de embedding de 512 dimensiones**, L2-normalizado, que vive en la superficie de una hiperesfera unitaria. En este espacio esférico, la similitud entre píxeles se mide por el coseno del ángulo entre sus vectores: píxeles del mismo cultivo deben agruparse cerca de un mismo **prototipo**, y píxeles de cultivos distintos deben alejarse.

### 3.2 Diagrama de capas

```
Entrada: x ∈ ℝ^40  (features escaladas)
    │
    ├──► Linear(40 → 256)
    │    LayerNorm(256)
    │    GELU()
    │    Dropout(p=0.20)
    │
    ├──► Linear(256 → 128)
    │    LayerNorm(128)
    │    GELU()
    │    Dropout(p=0.20)
    │
    ├──► Linear(128 → 64)
    │    LayerNorm(64)
    │    GELU()
    │    Dropout(p=0.20)
    │
    └──► Linear(64 → 512)
         L2-Normalize  ──────►  z ∈ ℝ^512, ‖z‖₂ = 1
```

### 3.3 Capas de entrada

La capa de entrada recibe el vector de 40 features normalizadas con `StandardScaler` (media 0, varianza 1). La normalización es crítica porque las variables tienen escalas muy distintas (mm de precipitación vs. porcentajes de textura vs. índices adimensionales). La primera capa proyecta de 40 a 256 dimensiones con una transformación lineal aprendida.

### 3.4 Capas ocultas

El encoder tiene **tres capas ocultas** con arquitectura idéntica:

| Componente | Dimensiones | Propósito |
|------------|-------------|-----------|
| `Linear` | entrada → salida de capa | Transformación afín aprendida |
| `LayerNorm` | — | Normaliza las activaciones por muestra (no por batch) |
| `GELU` | — | Activación no lineal suave |
| `Dropout(0.20)` | — | Regularización estocástica |

**Por qué LayerNorm y no BatchNorm:** LayerNorm normaliza sobre las dimensiones del embedding de un solo ejemplo, independientemente del tamaño del batch. Esto es importante porque los bags tienen tamaños variables (distintos municipios tienen distinto número de píxeles) y el tamaño del batch efectivo cambia entre iteraciones. BatchNorm introduciría ruido en sus estadísticas cuando el batch es pequeño.

**Por qué GELU y no ReLU:** GELU (Gaussian Error Linear Unit) es una activación suave que no produce gradientes exactamente cero en la región negativa, lo que facilita el flujo de gradientes y la convergencia. Ha demostrado mejor desempeño que ReLU en modelos de representación contrastiva (sigue el estándar de Vision Transformers y modelos de lenguaje modernos).

**Por qué Dropout 0.20:** Además de ser regularización clásica, el dropout en el encoder actúa como un mecanismo de **augmentación implícita**: al pasar el mismo píxel dos veces con distintas máscaras de dropout, se obtienen dos embeddings ligeramente distintos que el modelo debe aprender a asignar al mismo prototipo. Esto es análogo al uso de augmentaciones de imagen en el paper original.

### 3.5 Función de activación GELU

GELU se define como:

```
GELU(x) = x · Φ(x)
```

donde Φ(x) es la función de distribución acumulada de la normal estándar. En la práctica se aproxima como:

```
GELU(x) ≈ 0.5 · x · (1 + tanh(√(2/π) · (x + 0.044715 · x³)))
```

A diferencia de ReLU, GELU no trunca abruptamente en 0 sino que hace una transición suave, preservando gradiente para valores negativos pequeños.

### 3.6 Capa de salida y embeddings

La capa de salida es una proyección lineal de 64 → 512 dimensiones **sin activación**, seguida de **normalización L2**:

```
z = Linear(64 → 512)(h)
z = z / ‖z‖₂
```

**¿Qué representa el embedding z ∈ ℝ^512?**

El embedding es un punto en la superficie de una hiperesfera unitaria de 512 dimensiones. Cada coordenada del embedding no tiene interpretación directa, pero la **dirección del vector** codifica la identidad del cultivo dominante del píxel. Dos píxeles con el mismo cultivo deben producir vectores con un ángulo pequeño entre sí (alto coseno de similitud). La normalización L2 es fundamental porque permite comparar embeddings mediante el producto punto, que equivale exactamente al coseno del ángulo entre ellos. Esto convierte la hiperesfera en un espacio métrico bien definido para clustering.

---

## 4. Prototipos: definición y cálculo

### 4.1 ¿Qué es un prototipo?

Un prototipo `v_k ∈ ℝ^512` (k = 1…K, K=17) es un **vector learnable** que representa el centroide semántico de un cultivo en el espacio de embeddings. Conceptualmente, el prototipo de "Maíz" es el punto en la hiperesfera unitaria hacia donde deben converger los embeddings de todos los píxeles de maíz. Los prototipos son **parámetros entrenables** del modelo, actualizados por gradiente descendente junto con los pesos del encoder.

### 4.2 Definición formal

```
V = [v₁, v₂, ..., v_K] ∈ ℝ^{K × 512}
v_k = v_k / ‖v_k‖₂   (normalizados a la esfera unitaria)
```

K = 17 prototipos, uno por clase de cultivo:

| Índice | Cultivo |
|--------|---------|
| 0 | Caña Panelera |
| 1 | Café |
| 2 | Maíz |
| 3 | Plátano |
| 4 | Mango |
| 5 | Fríjol |
| 6 | Cacao |
| 7 | Arveja |
| 8 | Palma |
| 9 | Banano |
| 10 | Cítricos |
| 11 | Mora |
| 12 | Zanahoria |
| 13 | Tomate de Árbol |
| 14 | Yuca |
| 15 | Habichuela |
| 16 | Hortalizas |

> **Nota:** Papa es manejada por el modelo L1 (UPRA); No_apto es manejada por el modelo L3 (SIPRA). Estas clases no aparecen en el L2.

### 4.3 Cálculo de probabilidades desde embeddings

Dado un embedding `z ∈ ℝ^512` (L2-normalizado), la probabilidad de que el píxel pertenezca al cultivo k se calcula así:

**Paso 1 — Scores de similitud coseno:**
```
s_k = z · v_k^T / τ       para k = 1…K
```
donde τ = 0.04965 es la temperatura softmax. Un τ bajo hace la distribución más "picuda" (predicciones más nítidas); un τ alto la suaviza.

**Paso 2 — Probabilidad softmax:**
```
P(cultivo=k | píxel) = exp(s_k) / Σ_{k'} exp(s_{k'})
```

**Paso 3 — Ranking de cultivos:**
La salida natural del modelo es un ranking de los 17 cultivos ordenados por probabilidad descendente. Top-1 es el cultivo más probable, Top-3 los tres más probables, etc.

### 4.4 Inicialización y regularización de prototipos

Los prototipos se inicializan con pesos aleatorios. Durante la primera época (`FREEZE_PROTO_EPOCHS=1`), los prototipos permanecen **congelados** para dar tiempo al encoder a aprender representaciones básicas antes de que los prototipos comiencen a moverse. Posteriormente, ambos (encoder y prototipos) se actualizan simultáneamente.

La **pérdida KoLeo** (con peso 0.1) penaliza que los prototipos colapsen hacia el mismo punto, fomentando su separación en la hiperesfera.

---

## 5. Por qué esta arquitectura

### 5.1 Adaptación de LLP-Co a datos tabulares

El paper original (La Rosa et al. 2022) usa **ResNet18** como encoder porque trabaja con parches de imagen de 21×21 píxeles de Sentinel-1/2 o Landsat. En AgroPlus, los datos de entrada son **tabulares**: un vector de 40 features por píxel, sin estructura espacial local explícita.

El reemplazo de ResNet18 por un MLP es la adaptación fundamental:

| Componente | Paper original | AgroPlus L2 |
|------------|---------------|-------------|
| Encoder | ResNet18 + projection head | MLP 4 capas (256→128→64→512) |
| Input | Parches imagen 21×21 | Vector tabular 40 features |
| Augmentación | Rotaciones, espejo, resize | Feature dropout + ruido gaussiano |
| Embedding dim | 1024 | 512 |

### 5.2 Por qué MLP y no modelo más complejo

- **Los datos son tabulares sin estructura espacial local:** un CNN requiere datos con estructura 2D. Cada píxel en la vista minable ya tiene sus features pre-agregadas por semestre, eliminando la variabilidad espacial intra-parche que justifica el uso de CNNs.
- **Capacidad suficiente:** 4 capas con 256→128→64→512 neuronas tienen ~100K parámetros, adecuados para 40 features de entrada. Más capas introducirían sobreajuste dado el ruido en las etiquetas EVA.
- **Gradiente estable:** La arquitectura pirámide decreciente (256→128→64) comprime progresivamente, forzando representaciones más abstractas en capas profundas antes del proyector de 512 dimensiones.

### 5.3 Por qué el problema es LLP y no supervisión completa

Las etiquetas pixel-a-pixel son inexistentes o no confiables en Cundinamarca a escala regional. La EVA reporta **áreas sembradas por municipio y semestre**, no polígonos por lote. El paradigma LLP permite usar estos datos censales directamente como supervisión, sin necesidad de asignar etiquetas individuales a cada píxel.

---

## 6. Entrenamiento del modelo

### 6.1 Augmentación de features (dos vistas por píxel)

Para cada píxel, se generan **dos vistas aumentadas** `x^t` y `x^s` aplicando perturbaciones distintas:

| Grupo de features | Dropout | Ruido gaussiano σ |
|------------------|---------|-----------------|
| Topografía / suelo (estáticas) | Sin dropout | σ ≈ 0.001 (mínimo) |
| Clima | 10% dropout | σ ≈ 0.05 |
| Sentinel-2 (simula nubosidad) | 20% dropout | σ ≈ 0.05 |

Las features de topografía y suelo son **estáticas** (no cambian entre semestres), por lo que se aplica mínima perturbación. Las features de Sentinel-2 simulan la nubosidad que afecta la disponibilidad de datos ópticos en campo.

Hiperparámetros de augmentación (optimizados por Optuna):
- `P_DROP_AUG = 0.20` (probabilidad de dropout por feature)
- `SIGMA_AUG = 0.08677` (desviación estándar del ruido gaussiano)

### 6.2 Algoritmo de entrenamiento (Algoritmo 1 del paper)

```
Para cada época:
  Para cada bag B_i = (municipio, semestre):
    1. Generar dos vistas aumentadas X^t_i, X^s_i  (shape: n_i × 40)
    2. Codificar:  Z^t_i = f_θ(X^t_i),  Z^s_i = f_θ(X^s_i)  (n_i × 512, L2-norm)
    3. Calcular scores:  S_i = Z_i · V^T  (n_i × K, similitudes coseno)
    4. Sinkhorn-Knopp: Q^t_i, Q^s_i = SK(S^t_i, w_i),  SK(S^s_i, w_i)
       (códigos suaves restringidos a proporciones EVA del municipio w_i)
    5. Pérdida swap:
       L_swap = ℓ(Z^s_i, Q^t_i) + ℓ(Z^t_i, Q^s_i)
    6. Actualizar θ (encoder) y V (prototipos) con AdamW
```

### 6.3 Sinkhorn-Knopp: qué es y para qué sirve

**El problema que resuelve:** Dado un conjunto de embeddings `Z ∈ ℝ^{n_i × 512}` de un bag y K prototipos `V`, queremos asignar cada píxel a un prototipo de forma que la **distribución de asignaciones respete las proporciones EVA `w_i`**. Por ejemplo, si w_i dice que el 40% del municipio es maíz y 30% arveja, entonces el 40% de los píxeles del bag deben ser asignados al prototipo de maíz y el 30% al de arveja.

Este es un **problema de transporte óptimo**: mover "masa" (píxeles) desde sus posiciones en el espacio de embeddings hasta los prototipos, minimizando el costo de transporte (disimilitud coseno), sujeto a que la masa que llega a cada prototipo respete las proporciones `w_i`.

**Formulación matemática:**

```
Q*_i = argmax_{Q ∈ U(w,a)} Tr(Q^T · V · Z^T_i) + ε · h(Q_i)
```

donde:
- `Q ∈ ℝ^{K × n_i}` es la matriz de códigos (asignaciones suaves de píxeles a prototipos)
- `U(w,a)` es el conjunto de matrices no negativas con marginales `w` (proporciones EVA) y `a = 1/n_i · 1` (cada píxel contribuye igualmente)
- `h(Q)` es la entropía de Q (regularización entrópica)
- `ε = 0.06020` controla la suavidad: ε bajo → asignaciones más duras (closer to hard assignment); ε alto → distribuciones más difusas (riesgo de colapso)

**Algoritmo Sinkhorn-Knopp (5 iteraciones):**

El término de regularización entrópica convierte el problema de OT en un problema de escalado de matrices que se resuelve de forma iterativa:

```
Inicializar: M = exp(V · Z^T / ε)   (K × n_i, scores exponenciados)
Para t = 1…5:
  M ← diag(w / (M · 1_{n_i})) · M   (normalizar filas → respetar proporciones w)
  M ← M · diag(a / (M^T · 1_K))      (normalizar columnas → cada píxel contribuye igual)
Q ← M
```

Cada iteración de Sinkhorn es una simple división de cada fila/columna de la matriz. La convergencia en 5 iteraciones es suficiente gracias a la regularización entrópica, que suaviza el problema. El resultado `Q` es una matriz de probabilidades suaves que codifica "¿con qué probabilidad pertenece el píxel j al cultivo k, dado que el municipio tiene proporciones w?".

**¿Por qué no usar equipartición (SwAV estándar)?** SwAV original asume que todos los clústeres deben tener el mismo tamaño. LLP-Co reemplaza esta restricción por las proporciones reales del municipio (`w_i`), convirtiendo la equipartición en una restricción proporcional. Esto es la contribución central del paper respecto a SwAV.

### 6.4 Pérdida Swap (Swap Loss)

La pérdida swap compara las asignaciones (códigos Q) de una vista con las predicciones de probabilidad de la otra vista:

```
L_swap(z^s, z^t) = ℓ(z^s, c^t) + ℓ(z^t, c^s)
```

donde cada término es una cross-entropía:

```
ℓ(z^t_{i,j}, c^s_{i,j}) = -Σ_k  c^{s(k)}_{i,j} · log P^{t(k)}_{i,j}
```

y las probabilidades se calculan como:

```
P^{t(k)}_{i,j} = exp((z^t_{i,j})^T · v_k / τ) / Σ_{k'} exp((z^t_{i,j})^T · v_{k'} / τ)
```

**Intuición del swap:** Si la vista t y la vista s de un mismo píxel contienen la misma información semántica (mismo cultivo), entonces debe ser posible predecir el código de s a partir de los features de t, y viceversa. La pérdida swap penaliza cuando una vista no puede predecir el código de la otra. Esto fuerza al encoder a aprender representaciones **invariantes a las augmentaciones aplicadas**, lo que es equivalente a aprender features robustas del cultivo.

### 6.5 Hiperparámetros de entrenamiento

| Hiperparámetro | Valor | Descripción |
|----------------|-------|-------------|
| Optimizador | AdamW | Con weight decay |
| `LR_INIT` | 0.1 | Tasa de aprendizaje inicial |
| `LR_MIN` | 1e-5 | Tasa mínima (cosine decay) |
| `WEIGHT_DECAY` | 1e-6 | Regularización L2 de pesos |
| `TOTAL_EPOCHS` | 500 | Épocas totales de entrenamiento |
| `WARMUP_EPOCHS` | 5 | Épocas de calentamiento lineal del LR |
| `FREEZE_PROTO_EPOCHS` | 1 | Épocas con prototipos congelados |
| `TAU (τ)` | 0.04965 | Temperatura softmax (Optuna) |
| `EPS_SK (ε)` | 0.06020 | Regularización Sinkhorn (Optuna) |
| `N_SINKHORN` | 5 | Iteraciones Sinkhorn-Knopp |
| `EMB_DIM` | 512 | Dimensión del embedding |
| `K` | 17 | Número de prototipos/clases |
| `KOLEO_WEIGHT` | 0.1 | Peso de pérdida de diversidad de prototipos |

**Schedule de learning rate (cosine warmup):**
```
Si época < 5:  LR = LR_INIT × (época + 1) / 5     (calentamiento lineal)
Si época ≥ 5:  LR = LR_MIN + 0.5 × (LR_INIT - LR_MIN) × (1 + cos(π × progreso))
```

### 6.6 Optimización de hiperparámetros con Optuna

Los hiperparámetros τ, ε y σ_aug fueron optimizados con **Optuna** (búsqueda bayesiana), minimizando la divergencia KL de validación:

| Parámetro | Rango de búsqueda | Valor óptimo encontrado |
|-----------|------------------|------------------------|
| `TAU (τ)` | [0.02, 0.20] | **0.04965** |
| `EPS_SK (ε)` | [0.005, 0.10] | **0.06020** |
| `SIGMA_AUG` | [0.01, 0.15] | **0.08677** |

---

## 7. Predicción

### 7.1 Proceso de inferencia

En inferencia (sin augmentación ni Sinkhorn), el proceso se simplifica:

```python
# 1. Escalar features
x_scaled = scaler.transform(x_raw)          # (N, 40)

# 2. Encoder
with torch.no_grad():
    z = encoder(x_scaled)                    # (N, 512) — L2 normalizado

# 3. Scores de similitud
scores = z @ prototypes.normed().T           # (N, 17)

# 4. Probabilidades
P = softmax(scores / τ, dim=1)              # (N, 17) — distribución sobre cultivos

# 5. Top-K ranking por píxel
top_k = argsort(P, descending=True)[:, :K]  # cultivos más probables
```

### 7.2 Salida del modelo

Para cada píxel, el modelo produce:
- Un vector de probabilidades `P ∈ ℝ^17` con `Σ P_k = 1`
- El **Top-1** es el cultivo más probable (clasificación hard)
- El **Top-3/5** es más apropiado dado que el modelo genera distribuciones suaves

**Ejemplo de salida (píxeles de validación):**

```
píxel_id   Top1          P1      Top2          P2      Top3          P3
12345      Arveja        0.421   Hortalizas    0.218   Fríjol        0.143
67890      Maíz          0.512   Café          0.189   Caña Panelera 0.091
```

### 7.3 Predicción a nivel de bag (municipio)

Para evaluar la calidad de las proporciones predichas:

```
w_pred_mun = mean(P, axis=0)    sobre todos los píxeles del municipio
```

Esta proporción predicha se compara con `w_eva` (proporciones reportadas por la EVA) mediante la divergencia KL.

---

## 8. Métricas de evaluación

Las métricas se dividen en **métricas de bag** (nativas de LLP) y **métricas de píxel** (proxy de calidad de clasificación individual).

### 8.1 Métricas de bag — KL Divergence

**Definición:** La divergencia de Kullback-Leibler mide cuánto se aleja la distribución de proporciones predicha por el modelo de las proporciones EVA:

```
KL(w_eva || w_pred) = Σ_k  w_eva_k · log(w_eva_k / w_pred_k)
```

Esta es la **métrica nativa de LLP**: el modelo aprende directamente a minimizarla. Un KL cercano a 0 significa que las proporciones predichas a nivel municipal reproducen fielmente las del censo.

**Resultados en validación:**

| Estadístico | Valor |
|-------------|-------|
| Media | 0.8185 |
| Mediana | 0.5601 |
| P25 | 0.2913 |
| P75 | 0.6404 |
| Máximo | 5.7126 (municipio 25530) |

**Top-5 municipios con mayor KL (peor desempeño):**

| Municipio | KL |
|-----------|-----|
| 25530 | 5.7126 |
| 25281 | 0.8194 |
| 25797 | 0.6494 |
| 25867 | 0.6447 |
| 25181 | 0.6360 |

### 8.2 Métricas de píxel — Top-K Accuracy

**Definición:** Fracción de píxeles donde el cultivo pseudo-verdadero (`argmax(w_eva)` del municipio) aparece entre los K cultivos más probables predichos:

```
Top-K Acc = |{píxel j : cultivo_verdadero ∈ Top-K(P_j)}| / N_total
```

> **Nota metodológica:** Como se explica en el paper (La Rosa et al. 2022, Sección V), las métricas de píxel son aproximadas porque la pseudo-etiqueta `argmax(w_eva)` asigna el *cultivo mayoritario del municipio* a **todos** los píxeles del municipio — esto no es la etiqueta verdadera del píxel individual, sino el cultivo dominante a nivel agregado. Por eso Top-3/5 son métricas más informativas que Top-1.

**Resultados:**

| Métrica | Validación | Test |
|---------|-----------|------|
| Top-1 | 27.45% | 31.38% |
| Top-3 | 60.25% | 68.87% |
| Top-5 | 77.55% | 82.78% |
| Top-8 | 86.56% | 88.95% |

### 8.3 Per-Class Recall (Validación)

| Cultivo | n_píxeles | R@1 | R@2 | R@3 | R@5 |
|---------|-----------|-----|-----|-----|-----|
| Caña Panelera | 1,976 | 16.9% | 40.5% | 56.0% | 71.4% |
| Café | 9,475 | 31.1% | 47.6% | 54.7% | 67.6% |
| Maíz | 69,148 | 19.3% | 31.8% | 56.6% | 76.6% |
| Mango | 1,641 | 28.2% | 48.0% | 54.1% | 71.7% |
| Fríjol | 18,672 | 22.9% | 31.9% | 37.4% | 51.8% |
| Arveja | 153,790 | **41.2%** | **58.4%** | **77.4%** | **94.5%** |
| Palma | 51,869 | 0.0% | 0.0% | 0.0% | 0.0% |
| Cítricos | 763 | 9.4% | 25.8% | 50.5% | 64.1% |
| Zanahoria | 80,967 | 12.4% | 32.1% | 44.3% | 75.2% |
| Hortalizas | 146,126 | 35.6% | 63.4% | 77.6% | 93.2% |
| **Macro avg** | **534,427** | **12.8%** | **22.3%** | **29.9%** | **39.2%** |

**Observaciones clave:**
- **Arveja y Hortalizas** tienen los mejores recalls — son los cultivos más representados en Cundinamarca y sus signatures espectrales son más distintivas.
- **Palma** tiene recall 0% en validación — probablemente ausente o muy escasa en los municipios del conjunto de validación.
- **Fríjol** tiene el recall más bajo entre clases con tamaño razonable — su firma espectral se confunde con otras leguminosas y cultivos transitorios.

### 8.4 F1 Macro y matriz de confusión

El F1 macro se calcula usando `argmax(w_eva)` como pseudo-GT (etiqueta dura del cultivo mayoritario del municipio). Esta métrica **subestima sistemáticamente** al modelo cuando predice distribuciones correctas para municipios con múltiples cultivos, pero sirve como sanity check de la separabilidad por clase.

### 8.5 Análisis de prototipos — similitud coseno

La matriz de similitud coseno entre los K=17 prototipos permite evaluar la calidad del espacio de representación aprendido:

```
S_proto = V · V^T   ∈ ℝ^{K × K}
```

- **Diagonal = 1.0** (cada prototipo consigo mismo)
- **Off-diagonal cercano a 0** indica prototipos bien separados (ideal)
- **Off-diagonal alto** indica que dos cultivos son difícilmente distinguibles con las features disponibles

Esta matriz es equivalente a un mapa de "confusión" en el espacio latente, más informativo que la matriz de confusión en el espacio de predicción.

### 8.6 ¿Por qué estas métricas son válidas para LLP-Co?

Siguiendo el marco del paper (Sección IV-B, "Evaluation Metrics"):

1. **KL Divergence** es la métrica propia del problema LLP — mide directamente lo que el modelo optimiza. Es la métrica más honesta respecto al objetivo de entrenamiento.

2. **Top-K Accuracy** es válida porque en un modelo que predice distribuciones de probabilidad, la métrica de clasificación correcta es si la clase verdadera aparece en el soporte de alta probabilidad, no si es exactamente la top-1. El paper reporta esta misma métrica para evaluar sus resultados (Sección V).

3. **ARI y NMI** son métricas de clustering que evalúan la concordancia entre asignaciones predichas y etiquetas verdaderas, independientemente del mapeo de índices (el paper los reporta en Tabla III). Son robustas a la permutación de etiquetas de clústeres.

4. **F1 Macro** es útil como referencia comparativa pero debe interpretarse con cautela dado el problema de pseudo-etiquetado a nivel de municipio.

> Las métricas AccP (prototype accuracy) y AccH (Hungarian algorithm accuracy) del paper requieren un conjunto de referencia con etiquetas pixel-a-pixel, no disponible en este proyecto. Se utilizan las métricas equivalentes (Top-K, KL, F1) adaptadas a los datos disponibles de Cundinamarca.

---

## 9. Arquitectura del sistema completo en AgroPlus

El modelo LLP-Co es la **capa L2** del ensamble jerárquico de AgroPlus:

```
Píxel geoespacial
      │
      ▼
L1 — Modelo UPRA (monitoreo)
      │ ¿Hay papa o uso especial?
      │ Si → etiqueta L1
      │ No ↓
      ▼
L2 — Modelo LLP-Co (EVA municipal)  ◄── Este documento
      │ Asigna distribución P(cultivo) sobre 17 clases
      │
      ▼
L3 — Modelo SIPRA + NDVI (No_apto)
      │ ¿El píxel es agrícola o no apto?
      └─► Etiqueta final ensamblada
```

---

## 10. Limitaciones y siguientes pasos

| Limitación | Descripción |
|------------|-------------|
| Palma con recall 0% | La palma aceitera es escasa en Cundinamarca — el prior EVA asigna proporciones muy bajas y el modelo no aprende su firma |
| KL alto en municipio 25530 | Posible discrepancia entre el área agrícola reportada por EVA y la real según NDVI |
| Top-1 bajo (27%) | Esperado: el modelo predice distribuciones, no clases únicas. Top-3 (60%) es la métrica operativa |
| Bag size fijo por municipio | Municipios con pocos píxeles tienen bags inestables para Sinkhorn-Knopp |

**Hiperparámetros con mayor impacto para afinar:**

| Parámetro | Valores sugeridos | Efecto esperado |
|-----------|-----------------|-----------------|
| `BAG_SIZE` | 1024 / 2048 / 4096 | Más grande = OT más estable |
| `TAU` | 0.03 / 0.05 / 0.10 | Más bajo = predicciones más nítidas |
| `EPS_SK` | 0.01 / 0.05 / 0.10 | Más bajo = más fiel al prior EVA |
| `TOTAL_EPOCHS` | 300 / 500 / 800 | KL_valid debe estabilizarse |
| `EMB_DIM` | 256 / 512 / 1024 | Capacidad del encoder |

---

## Referencias

- La Rosa, L.E.C., Oliveira, D.A.B., & Ghamisi, P. (2022). *Learning crop type mapping from regional label proportions in large-scale SAR and optical imagery*. arXiv:2208.11607v1 [cs.CV].
- Caron, M., et al. (2020). *Unsupervised Learning of Visual Features by Contrasting Cluster Assignments* (SwAV). NeurIPS 2020.
- Cuturi, M. (2013). *Sinkhorn Distances: Lightspeed Computation of Optimal Transport Distances*. NeurIPS 2013.
- EVA — Evaluación Agropecuaria Municipal. MADR / UPRA. Cundinamarca 2018-2023.
- SoilGrids 250m — ISRIC World Soil Information.
- CHIRPS v2.0 — Climate Hazards Group InfraRed Precipitation with Station data.
