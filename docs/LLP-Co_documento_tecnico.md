# Mapeo de Tipos de Cultivo con Proporciones de Etiquetas Regionales en Imágenes SAR y Ópticas a Gran Escala

**Referencia:** La Rosa, L.E.C., Oliveira, D.A.B., & Ghamisi, P. (2022). *Learning crop type mapping from regional label proportions in large-scale SAR and optical imagery*. arXiv:2208.11607v1.

---

## 1. Contexto y Problemática

### 1.1 El Cuello de Botella del Aprendizaje Supervisado en Observación de la Tierra

La observación de la Tierra (EO, *Earth Observation*) genera volúmenes masivos de imágenes satelitales de manera continua y gratuita. Para extraer información útil de esas imágenes —como identificar qué tipo de cultivo crece en cada píxel— se requieren mapas de clasificación derivados de las imágenes. Los algoritmos de *deep learning* (DL) han demostrado ser altamente efectivos para esta tarea, pero su rendimiento depende críticamente de contar con grandes conjuntos de datos anotados a nivel de píxel.

**El problema central:** La anotación experta píxel a píxel de imágenes satelitales es:

- **Costosa** en términos económicos y de tiempo especializado.
- **No escalable** para regiones agrícolas extensas (miles de km²).
- **Limitante** en la práctica real, ya que convierte la disponibilidad de datos (no el dato en sí) en el cuello de botella del modelado.

### 1.2 La Oportunidad: Datos de Proporciones de Cultivos

Distintos organismos gubernamentales publican regularmente estadísticas agrícolas a nivel municipal o regional que incluyen la proporción del área cultivada por tipo de cultivo. Ejemplos:

| Organismo | País | Información disponible |
|---|---|---|
| NASS/USDA | Estados Unidos | Área sembrada, cosechada, rendimiento por cultivo |
| IBGE | Brasil | Estadísticas agrícolas municipales por especie |
| Eurostat | Europa | Estadísticas de uso de suelo agrícola |
| Forest Research | Reino Unido | Estadísticas forestales y de cobertura vegetal |

Estas proporciones **no requieren imágenes satelitales** para ser generadas (se obtienen mediante entrevistas y visitas de campo), y están disponibles públicamente. La pregunta que motiva este trabajo es: **¿es posible entrenar un clasificador de tipos de cultivos usando únicamente estas proporciones como supervisión débil, sin etiquetas a nivel de píxel?**

### 1.3 Preguntas de Investigación

El artículo aborda cuatro preguntas específicas:

1. ¿Es suficiente la información a priori sobre proporciones exactas de clases para entrenar un clasificador de identificación de cultivos?
2. ¿Puede un modelo converger a la proporción de clase real usando proporciones aproximadas (de censo)?
3. ¿Cómo afecta el tamaño del "bag" al rendimiento final de clasificación?
4. ¿Generaliza el modelo entrenado satisfactoriamente para diferentes regiones agrícolas y modalidades de imagen?

---

## 2. Marco Teórico: Aprendizaje desde Proporciones de Etiquetas (LLP)

### 2.1 Definición Formal del Problema LLP

El *Learning from Label Proportions* (LLP) es un enfoque de clasificación débilmente supervisado. En lugar de etiquetas individuales por muestra, se conocen únicamente las **proporciones de clases dentro de grupos de muestras** llamados *bags*.

**Definición formal:**

- Dataset de entrenamiento: $\mathcal{D} = \{(B_i, \mathbf{w}_i)\}_{i=1}^{N}$, con $N$ bags disjuntos.
- Bag $B_i = \{(x_{i,j})\}_{j=1}^{n_i}$: conjunto de $n_i$ muestras seleccionadas aleatoriamente.
- $\mathbf{w}_i \in \Delta^K$: vector de proporciones de etiquetas para el bag $i$, donde $\sum_{k=1}^{K} w_i^k = 1$.
- Objetivo: entrenar un clasificador a nivel de **muestra individual** usando solo $\mathbf{w}_i$.

### 2.2 Formulación del Objetivo de Optimización

El clasificador DL estima las probabilidades $\tilde{p}_{i,j} = p_\theta(y | x_{i,j})$ usando softmax. La proporción estimada por bag es:

$$\hat{w}_i = \frac{1}{n_i} \sum_{j=1}^{n_i} \tilde{p}_{i,j}$$

La función de pérdida estándar es la entropía cruzada entre proporción estimada y proporción real:

$$\mathcal{L}(\hat{w}, w) = -\frac{1}{N} \sum_{i=1}^{N} w_i \log \hat{w}_i \quad (1)$$

Reformulando con distribución posterior $q(y^k | x_{i,j})$:

$$\mathcal{L}(p, q) = -\frac{1}{N} \sum_{i=1}^{N} \sum_{j=1}^{n_i} \sum_{k=1}^{K} \frac{q(y^k | x_{i,j})}{n_i} \log p_\theta(y^k | x_{i,j}) \quad (2)$$

El problema de optimización resultante es:

$$\min_{(p,q)} \mathcal{L}(q, p) \quad \text{s.t.} \quad \forall y: q(y^k | \cdot) \in [0,1], \quad \sum_{j=1}^{n_i} q(y^k | x_{i,j}) = w_i^k \cdot n_i \quad (3, 4)$$

La restricción (4) garantiza que la proporción de la etiqueta $k$ en el bag sea exactamente $w_i^k \cdot n_i$ muestras.

### 2.3 Transporte Óptimo Regularizado (ROT) como Solver

Esta formulación es una instancia del **Problema de Transporte Óptimo** (OT). Se define:

- $P^y_{i,j} = p_\theta(y | x_{i,j}) \cdot \frac{1}{n_i}$: matriz $K \times n_i$ de probabilidades conjuntas estimadas por el modelo.
- $Q^y_{i,j} = q(y | x_{i,j}) \cdot \frac{1}{n_i}$: matriz $K \times n_i$ de probabilidades asignadas.

El espacio de soluciones factibles con restricción de proporciones:

$$\mathcal{U}(\mathbf{w}, \mathbf{a})_i := \{Q_i \in \mathbb{R}^{K \times n_i}_+ \mid Q_i \mathbf{1}_{n_i} = \mathbf{w}_i,\; Q_i^T \mathbf{1}_K = \mathbf{a}\} \quad (6)$$

donde $\mathbf{a} = \frac{1}{n_i}\mathbf{1}_{n_i}$ es la restricción normalizadora (cada muestra asignada a un solo cluster).

El objetivo con regularización entrópica:

$$\min_{Q_i \in \mathcal{U}(\mathbf{w}, \mathbf{a})_i} \langle Q_i, -\log P_i \rangle + \varepsilon \cdot h(Q_i) \quad (5)$$

Este problema se resuelve eficientemente con el **algoritmo de Sinkhorn-Knopp**, que itera multiplicaciones matriciales hasta convergencia.

---

## 3. Solución Propuesta: LLP-Co

### 3.1 Fundamento: SwAV con Restricción de Proporciones

El método base es **SwAV** (*Swapping Assignments between Multiple Views*), que combina aprendizaje contrastivo y clustering online. SwAV emplea una restricción de *equipartición*: todos los clusters tienen el mismo tamaño. **LLP-Co** reemplaza esa restricción por las proporciones reales de cultivos.

### 3.2 Arquitectura del Método LLP-Co

```
Imagen satelital de la región
         │
         ▼
┌─────────────────────┐
│   Parches aleatorios │  ──► Bag Bᵢ de nᵢ parches
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Pool de Augmen-   │  ──► Vista Xˢᵢ y Vista Xᵗᵢ
│   taciones         │       (rotaciones, espejos,
└─────────────────────┘        redimensionado aleatorio)
         │
         ▼
┌─────────────────────┐
│  ResNet18 Encoder   │  ──► Vectores de características
│  fθ (backbone)      │       zˢᵢ,ⱼ , zᵗᵢ,ⱼ ∈ ℝᵐ
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Projection Head    │  ──► Características proyectadas
│  (→ 1024 dims)      │       a la esfera unitaria
└─────────────────────┘
         │
         ▼
┌─────────────────────┐     Proporciones
│  Prototipos V =     │ ◄── de censo/dataset
│  [v₁, ..., vₖ]     │     wᵢ ∈ ΔK
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  OT Solver          │  ──► Códigos Qˢᵢ, Qᵗᵢ
│  (Sinkhorn-Knopp)   │       (asignaciones de cluster
│  con restricción wᵢ │        restringidas a wᵢ)
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Swap Loss          │  ──► Gradiente para actualizar
│  Lswap(zˢ, zᵗ)     │       θ y prototipos V
└─────────────────────┘
```

### 3.3 Función de Pérdida: Swap Contrastivo

Para cada par de vistas del mismo parche, LLP-Co aplica una pérdida "intercambiada":

$$\mathcal{L}_{\text{swap}}(z^s_{i,j}, z^t_{i,j}) = \ell(z^s_{i,j}, c^t_{i,j}) + \ell(z^t_{i,j}, c^s_{i,j}) \quad (7)$$

donde cada término es entropía cruzada entre el código de una vista y la probabilidad de la otra:

$$\ell(z^t_{i,j}, c^s_{i,j}) = -\sum_k c^{s(k)}_{i,j} \log p^{t(k)}_{i,j} \quad (8)$$

con la probabilidad calculada como softmax del producto punto entre características y prototipos:

$$p^{t(k)}_{i,j} = \frac{\exp\left((z^t_{i,j})^T v_k / \tau\right)}{\sum_{k'} \exp\left((z^t_{i,j})^T v_{k'} / \tau\right)} \quad (9)$$

**Intuición:** si $z^t_{i,j}$ y $z^s_{i,j}$ contienen información similar, debe ser posible predecir el código $c^s$ desde la característica $z^t$, y viceversa. Features con semántica similar producirán códigos target similares.

### 3.4 Asignación de Códigos con Restricción de Proporciones

Para el bag $i$, el objetivo del solver OT es maximizar la similitud entre las características $Z_i$ y los prototipos $V$:

$$Q^*_i = \max_{Q_i \in \mathcal{U}} \text{Tr}(Q_i^T V^T Z_i) + \varepsilon \cdot h(Q_i) \quad (10)$$

- $V^T Z_i$: matriz $K \times n_i$ de similitudes coseno entre muestras y prototipos.
- $Q_i$: pesos de transporte restringidos a la proporción $\mathbf{w}_i$.
- $\varepsilon$: parámetro de suavizado de la regularización entrópica (valor bajo para evitar colapso del modelo).

La regularización entrópica permite reformular el problema como una matriz exponencial normalizada, soluble iterativamente con Sinkhorn-Knopp.

### 3.5 Algoritmo de Entrenamiento Completo

```
ALGORITMO: LLP-Co Training Loop (dos vistas)

Entrada: D = {(Bᵢ, wᵢ)}ᴺᵢ₌₁  (bags con proporciones)
Entrada: Épocas > 0
Inicializar: Encoder fθ y prototipos V con pesos aleatorios

Para i = 1 hasta épocas:
  Para cada Bᵢ en D:
    1. Generar dos vistas aleatorias Xᵗ'ˢᵢ
    2. Obtener vectores de características Zᵗ'ˢᵢ = fθ(Xᵗ'ˢᵢ)
    3. Calcular scores de prototipo: VᵀZᵗ'ˢᵢ
    4. Calcular códigos Qᵗ'ˢᵢ restringidos a wᵢ  ← OT Sinkhorn-Knopp
    5. Convertir scores a probabilidades Pᵗ'ˢᵢ  ← softmax con τ
    6. Calcular pérdida: Lswap(zˢ, zᵗ)
    7. Actualizar θ y V con paso de gradiente (SGD)
  Fin Para
Fin Para
```

### 3.6 Extensión: Proporciones Globales en lugar de Proporciones por Bag

La contribución principal del artículo es usar LLP-Co en un escenario más realista donde **no se tienen las proporciones exactas de cada bag**, sino solo las **proporciones globales de la región** (obtenidas del censo):

$$\mathcal{D} = \{(B_i, \mathbf{w})\}_{i=1}^{N}$$

donde $\mathbf{w}$ es el mismo vector de proporciones globales para todos los bags $B_i$. Esto implica que la restricción del solver OT es la misma para cada bag, independientemente de su composición real.

---

## 4. Diseño Experimental

### 4.1 Datasets Utilizados

| Atributo | Campo Verde (CV) | Luis Eduardo Magalhães (LEM) |
|---|---|---|
| Estado (Brasil) | Mato Grosso | Bahia |
| Área | 4,782 km² | 3,940 km² |
| Satélites | Sentinel-1A + Landsat-8 | Sentinel-1, Sentinel-2, Landsat-8 |
| Período | Oct 2015 – Jul 2016 | Jun 2017 – Jun 2018 |
| Polígonos de referencia | 513 | 807 |
| Píxeles de referencia | ~6 millones | N/A |
| Cultivos principales | Soya, algodón, maíz | Soya, maíz, algodón, mijo |

**División train/test:** CV → 50%/50%; LEM → 75%/25% de polígonos.

### 4.2 Proporciones del Censo vs. Dataset Anotado

| Dataset | Fuente | Algodón | Maíz | Soya |
|---|---|---|---|---|
| CV | IBGE (censo) | 20.05% | 22.32% | 54.36% |
| CV | Dataset anotado | 45.30% | 35.80% | 73.20% |
| LEM | IBGE (censo) | 4.95% | 7.06% | 78.63% |
| LEM | Dataset anotado | 2.70% | 7.80% | 61.41% |

Nótese la discrepancia significativa en CV (el censo reporta más maíz que algodón, pero el dataset anotado muestra lo contrario). Este desajuste representa el caso de uso más realista y desafiante.

### 4.3 Escenarios Experimentales

| Escenario | Proporciones usadas | Región de entrenamiento | Clases modeladas |
|---|---|---|---|
| **SI** | Proporciones globales del dataset anotado | Región anotada | Cultivos principales + "otros" |
| **SII** | Proporciones del censo IBGE | Región agrícola enmascarada | Cultivos principales + "otros" |
| **SIII** | Proporción exacta por bag | Dataset anotado | Todas las clases |
| **SIV** | Proporciones globales del dataset anotado | Región anotada | Todas las clases |
| **SwAV1/2/3** | Restricción equipartición (baseline) | Varía | Varía |

Para SII, las regiones no agrícolas se eliminaron usando la desviación estándar del NDVI (se descartan píxeles con std < 25%).

### 4.4 Detalles de Implementación

**Arquitectura:**
- Backbone: ResNet18 modificado (stride=1 en primera convolución)
- Projection head: proyección a espacio de 1024 dimensiones
- Parches de entrada: 21×21 píxeles

**Hiperparámetros de entrenamiento:**
- Optimizador: SGD con weight decay = $10^{-6}$
- Learning rate inicial: 0.1, con warmup de 5 épocas + cosine decay hasta 0.0001
- Temperatura softmax: $\tau = 0.1$
- Prototipos congelados durante la primera época
- Muestras por época: 200,000 parches aleatorios

**Hiperparámetros del solver OT:**
- Peso de regularización entrópica: $\varepsilon = 0.05$
- Iteraciones de Sinkhorn: 5
- Asignación dura para bag size=32 en SIII; asignación suave para el resto
- Número de clusters: igual al número de clases (2–3 para SI/SII; todas para SIII/SIV); 30 para SwAV baseline

**Augmentaciones:** rotaciones aleatorias, espejado horizontal/vertical, redimensionado aleatorio.

### 4.5 Métricas de Evaluación

| Métrica | Descripción |
|---|---|
| **AccP** | Exactitud de clasificación directa (cluster = etiqueta predicha) |
| **AccH** | Exactitud con matching óptimo por algoritmo húngaro |
| **kNN** | Clasificación por k vecinos más cercanos (k=25) en el espacio de features |
| **ARI** | *Adjusted Rand Index* — similaridad entre asignaciones de cluster y etiquetas reales |
| **NMI** | *Normalized Mutual Information* — calidad del clustering |

---

## 5. Resultados

### 5.1 Resultados para SI y SII (Cultivos Principales)

| Métrica | CV-SI | CV-SII | CV-SwAV1 | CV-SwAV2 | LEM-SI | LEM-SII | LEM-SwAV1 | LEM-SwAV2 |
|---|---|---|---|---|---|---|---|---|
| AccP | 94.1 | 35.0 | – | – | 90.5 | 85.5 | – | – |
| AccH | 94.1 | 80.5 | 74.4 | 74.7 | 90.5 | 85.5 | 84.1 | 53.5 |
| kNN | 92.0 | 91.0 | 89.2 | 89.7 | 98.8 | 95.3 | 96.0 | 98.3 |
| ARI | 0.83 | 0.48 | 0.50 | 0.41 | 0.66 | 0.49 | 0.46 | −0.03 |
| NMI | 0.76 | 0.51 | 0.50 | 0.44 | 0.53 | 0.47 | 0.36 | 0.12 |

**Observaciones clave:**

- **SI supera al baseline SwAV** en 20 pp (CV) y 6 pp (LEM) en AccH.
- **SII con LEM** supera al baseline SwAV2 en 32 pp, a pesar de usar solo datos de censo.
- **Cluster swapping en CV-SII:** el censo IBGE reporta más maíz que algodón, pero el dataset real tiene la distribución inversa → AccP < AccH, requiriendo matching húngaro para la evaluación.
- Las predicciones son espacialmente suaves (sin el efecto "sal y pimienta" de métodos supervisados).

### 5.2 Resultados para SIII y SIV (Todas las Clases)

**SIII** (proporciones exactas por bag) logra los mejores resultados generales:

- CV: AccH entre 82–86%, cercano al 89.1% de la referencia supervisada.
- LEM: AccH de 86.9–95% para bags pequeños (32–256), **superando** al modelo supervisado (93.1%) en bags 32 y 64.

**SIV** (proporciones globales, todas las clases):

- Rendimiento mejora con el tamaño del bag.
- Mejor AccH en CV: 80.2% (bag 1024); en LEM: 68.8% (bag 2048).
- Clases minoritarias con proporciones similares o muy pequeñas son sistemáticamente confundidas (eucalipto/cerrado, sorgo/suelo).

**Limitación identificada:** el modelo no puede garantizar que el muestreo de cada bag siga las proporciones globales en datasets altamente desbalanceados, lo que afecta el aprendizaje de clases minoritarias.

---

## 6. Análisis de Sensibilidad al Tamaño del Bag

Un hallazgo central del artículo es la diferente sensibilidad al tamaño del bag según el tipo de proporciones:

| Configuración | Comportamiento con el tamaño del bag |
|---|---|
| **Proporciones exactas por bag (SIII)** | Mejor rendimiento con bags **pequeños** (32–128). Bags grandes aumentan varianza |
| **Proporciones globales (SI, SIV)** | Rendimiento mejora con bags **grandes** (2048). Las proporciones del bag convergen a las globales |

**Justificación matemática:** con proporciones globales, a mayor tamaño del bag, la proporción observada dentro del bag converge (por la Ley de los Grandes Números) a la proporción global real del dataset, haciendo la restricción del solver OT más precisa.

---

## 7. Relevancia para Aplicaciones Reales

### 7.1 Ventajas del Enfoque

- **Sin etiquetas píxel a píxel:** solo se necesitan estadísticas de censo públicas y gratuitas.
- **Escalable a grandes regiones:** el entrenamiento online con bags permite procesar millones de píxeles.
- **Agnóstico a la modalidad:** funciona con imágenes ópticas (Landsat-8, Sentinel-2) y SAR (Sentinel-1).
- **Transferible:** las proporciones de censo están disponibles para múltiples países y cultivos.

### 7.2 Limitaciones

- Rendimiento reducido para clases minoritarias con proporciones muy pequeñas o similares entre sí.
- Las discrepancias entre proporciones de censo y proporciones reales del área de interés impactan negativamente la precisión (especialmente AccP).
- La máscara agrícola basada en NDVI puede introducir ruido al incluir regiones no cultivadas.
- El modelo SAR es menos robusto que el modelo óptico ante variaciones de bag size.

### 7.3 Trabajo Futuro Propuesto

- Incorporar pérdidas ponderadas (weighted cross-entropy, focal loss) para clases minoritarias.
- Explorar la sensibilidad a hiperparámetros adicionales (batch size, estrategias de augmentación).
- Extender a otras aplicaciones donde haya datos censales: monitoreo forestal, estimación de cobertura vegetal, análisis climático.

---

## 8. Conclusiones

LLP-Co demuestra que es posible entrenar clasificadores de cultivos con alta precisión sin requerir anotaciones a nivel de píxel, utilizando únicamente proporciones de cultivos disponibles públicamente en datos de censo gubernamentales.

| Escenario | Accuracy obtenida |
|---|---|
| Proporciones exactas del dataset, cultivos principales | >90% |
| Proporciones del censo gubernamental, cultivos principales | 80–85% |
| Proporciones exactas por bag, todas las clases | ~86–95% (comparable o superior a supervisado) |
| Proporciones globales, todas las clases | 62–80% (clases principales bien identificadas) |

El éxito del método abre una línea de investigación relevante para países con buena infraestructura de estadísticas agrícolas (como Colombia a través del DANE/MADR) donde el costo de la anotación de imágenes satelitales ha sido históricamente una barrera para la aplicación de DL en agricultura de precisión y políticas de seguridad alimentaria.

---

*Documento técnico generado a partir de: La Rosa et al. (2022). arXiv:2208.11607v1.*
