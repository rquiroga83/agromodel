# LLP-Co — Guión y Storyboard de Video
## "Cómo aprender sin saber la respuesta exacta"
## Estilo: Branch Education | Duración: ~13 minutos | Narración en español

---

## HILO NARRATIVO

El video cuenta una historia única y continua:
un pixel de terreno no tiene etiqueta → solo tenemos proporciones por municipio →
construimos un espacio matemático donde los cultivos similares se agrupan →
usamos transporte óptimo para que los grupos respeten las proporciones reales →
entrenamos con consistencia entre vistas → el resultado es un mapa de probabilidades por pixel.

Cada escena termina planteando la pregunta que responde la siguiente.

---

## PALETA Y ESTILO VISUAL

- **Fondo:** negro (#0A0A0A)
- **Texto principal:** blanco (#FFFFFF)
- **Azul encoder:** #4A9EFF
- **Naranja prototipo:** #FF7B35
- **Verde positivo / papa:** #44CC88
- **Rojo negativo / pérdida:** #FF4455
- **Amarillo EVA / proporción:** #FFD166
- **Transiciones:** fade a negro entre partes, corte seco entre escenas internas
- **Tipografía:** Inter Light para narración, Inter Bold para términos clave

---

# PARTE 1 — EL PUNTO DE PARTIDA (1:30)
*Establece el problema central: tenemos datos, no tenemos etiquetas por pixel.*

---

## ESCENA 1.1 — Un pixel sin nombre (0:00–0:28)

**Narración:**
> "Imagina un campo de cincuenta metros por cincuenta metros en Cundinamarca, Colombia.
> Es solo un rectángulo de tierra. Pero en ese rectángulo alguien está sembrando algo —
> papa, maíz, arveja, fresa. Lo que sea.
> Si tienes un satélite, puedes ver su color, su textura, su humedad.
> Lo que no puedes ver es su nombre."

**Visual — segundo a segundo:**
```
0:00–0:06
  Pantalla negra.
  Aparece lentamente un cuadrado de 50×50px en el centro, color verde musgo.
  Debajo: "50 m × 50 m — Cundinamarca, Colombia"

0:06–0:14
  Alrededor del cuadrado aparecen íconos flotando en órbita:
    ↑ termómetro (temperatura)
    ↗ nube con lluvia (precipitación)
    → onda satelital (NDVI, EVI)
    ↘ perfil de suelo (arcilla, limo)
    ↓ montaña (elevación, pendiente)
  Cada ícono pulsa brevemente al aparecer.

0:14–0:22
  Todos los íconos se convierten en números y se alinean a la derecha
  formando un vector vertical: [0.72, 18.3, 0.41, 0.63, 2847, ...]
  Etiqueta encima: "x  ∈ ℝ⁷²"

0:22–0:28
  Un gran signo de interrogación "?" aparece a la izquierda del cuadrado.
  Texto bajo el signo: "¿Cultivo?"
  El cuadrado y el "?" quedan en pantalla — frozen — mientras la narración continúa.
```

**Prompt imagen estática:**
`Single 50x50 green pixel square centered on black background, surrounded by orbiting data icons (thermometer, rain cloud, satellite wave, soil layers, mountain), icons transforming into a numerical feature vector on the right side, large question mark on the left, minimalist technical illustration, dark background`

---

## ESCENA 1.2 — El dato que sí tenemos (0:28–1:05)

**Narración:**
> "No tenemos la etiqueta de ese pixel. Pero sí tenemos algo:
> cada año, el estado publica cuánto se siembra de cada cultivo
> en cada municipio. En Zipaquirá: cuarenta y tres por ciento papa,
> dieciocho por ciento maíz, nueve por ciento arveja.
> Son proporciones. No dicen en qué pixel está cada cultivo —
> solo cuántos pixeles del municipio *en total* pertenecen a cada uno.
> En el campo del aprendizaje automático, a esto se llama
> aprender desde proporciones de etiqueta — LLP por sus siglas en inglés."

**Visual — segundo a segundo:**
```
0:28–0:36
  El pixel de la escena anterior se multiplica: aparece una grilla
  de ~200 pixels (14×14) que representa el municipio de Zipaquirá.
  Todos son del mismo gris neutro — sin etiqueta.
  Texto arriba: "Municipio: Zipaquirá — ~2.800 pixels"

0:36–0:46
  A la derecha de la grilla aparece un panel con barras horizontales:
    ██████████ Papa   43%
    ████       Maíz   18%
    ██         Arveja  9%
    █          Haba    6%
    ▒▒▒▒▒▒    Otros  24%
  Etiqueta: "EVA — Evaluación Agropecuaria Municipal"

0:46–0:58
  Las barras se convierten en flechas que apuntan a la grilla.
  Los pixels de la grilla se colorean gradualmente en las proporciones correctas:
    43% se vuelven verde (papa)
    18% se vuelven azul (maíz)
    9%  se vuelven naranja (arveja)
  PERO el orden interno es aleatorio — shuffled — no hay patrón espacial.
  Texto aparece debajo: "Sabemos cuántos. No sabemos cuáles."

0:58–1:05
  Zoom-out: aparece el mapa completo de Cundinamarca con 116 municipios.
  Cada municipio tiene su barra de proporciones flotando encima.
  Texto central: "116 municipios. ~9 millones de pixels. Cero etiquetas individuales."
  → CORTE a Escena 1.3
```

**Prompt imagen estática:**
`Grid of 200 small squares representing municipality pixels, all grey/unlabeled, next to horizontal bar chart showing crop proportions (papa 43% green, maíz 18% blue, arveja 9% orange), arrows connecting bars to grid, pixels gradually colored in proportion but randomly ordered, caption "sabemos cuántos, no cuáles", clean dark educational diagram`

---

## ESCENA 1.3 — La pregunta que guía el video (1:05–1:30)

**Narración:**
> "La pregunta es: ¿puedes entrenar un modelo que — conociendo solo estas proporciones —
> aprenda a predecir el cultivo en cada pixel individual?
> La respuesta es sí. Y el mecanismo que lo hace posible
> combina tres ideas: un encoder que mapea pixels a un espacio geométrico,
> prototipos que representan cada cultivo en ese espacio,
> y un algoritmo de transporte óptimo que fuerza al modelo a respetar
> las proporciones que sí conocemos.
> Vamos parte por parte."

**Visual — segundo a segundo:**
```
1:05–1:12
  Pantalla se divide verticalmente en tres columnas, cada una con un ícono:
    Columna 1: cubo 3D con flechas (encoder)    → texto "Encoder"
    Columna 2: 18 estrellas/vectores (prototipos) → texto "Prototipos"
    Columna 3: red de flujos (transporte óptimo)  → texto "Sinkhorn-Knopp"

1:12–1:22
  Las tres columnas se conectan con flechas de izquierda a derecha.
  Debajo de las flechas: "Pixel → Embedding → Asignación → Predicción"

1:22–1:30
  Las tres columnas hacen fade-out excepto la columna 1 (Encoder),
  que se expande para ocupar toda la pantalla.
  → FADE TO BLACK → Título: "PARTE 2 — EL ENCODER"
```

**Prompt imagen estática:**
`Three column overview diagram on dark background: column 1 shows 3D cube with arrows labeled Encoder, column 2 shows 18 star vectors labeled Prototipos, column 3 shows flow network labeled Sinkhorn-Knopp, connected by horizontal arrows below showing "Pixel → Embedding → Asignación → Predicción", clean minimalist technical layout`

---

# PARTE 2 — EL ENCODER (2:15)
*¿Cómo convierte el encoder 72 números en una dirección en el espacio?*

---

## ESCENA 2.1 — La red neuronal, capa por capa (1:30–2:20)

**Narración:**
> "El encoder es una red neuronal de tipo MLP — perceptrón multicapa.
> Toma el vector de 72 features del pixel y lo transforma en cuatro pasos.
> Primero, una capa lineal lo proyecta a 256 dimensiones.
> Luego a 128. Luego a 64. Y finalmente lo expande a 512.
> Cada una de las tres primeras capas tiene tres ingredientes:
> normalización de capa, activación GELU, y dropout.
> La última capa es solo lineal."

**Visual — segundo a segundo:**
```
1:30–1:40
  Aparece un diagrama horizontal de bloques.
  De izquierda a derecha:
    [72] →  [BLOQUE 1: 256]  →  [BLOQUE 2: 128]  →  [BLOQUE 3: 64]  →  [512]

  El ancho de cada bloque es PROPORCIONAL a sus dimensiones.
  Colores: bloques internos en azul (#4A9EFF), input en gris, output en azul brillante.

1:40–1:55
  Zoom IN al Bloque 1 (256).
  El bloque se descompone en tres sub-capas apiladas verticalmente:
    ┌─────────────────────┐
    │  Linear(72 → 256)   │  ← color azul
    ├─────────────────────┤
    │    LayerNorm(256)   │  ← color verde claro
    ├─────────────────────┤
    │      GELU()         │  ← color naranja
    ├─────────────────────┤
    │   Dropout(p=0.2)    │  ← color rojo translúcido
    └─────────────────────┘
  Cada sub-capa aparece con un delay de 0.2s (izquierda a derecha pop-in).

1:55–2:05
  Zoom OUT — volvemos a ver los 4 bloques completos.
  Los bloques 2 y 3 muestran el mismo stack interno (mini-versión).
  El bloque 4 (512) muestra solo: Linear(64 → 512) — sin LayerNorm/GELU/Dropout.
  Texto bajo el diagrama: "MLPEncoder: 4 capas | ~400K parámetros"

2:05–2:20
  Un dato de ejemplo (un pixel real) entra como vector [0.72, 18.3, ...].
  Animación: el vector fluye de izquierda a derecha a través de los bloques.
  En cada bloque, el vector cambia de color (transformación).
  Llega al final como un vector de 512 dimensiones.
  → Continúa en Escena 2.2
```

**Prompt imagen estática:**
`MLP neural network architecture diagram: horizontal blocks left to right showing dimensions 72→256→128→64→512, each internal block decomposes to show Linear+LayerNorm+GELU+Dropout sub-layers stacked vertically, block width proportional to dimensions, blue color scheme on dark background, data flow arrow left to right`

---

## ESCENA 2.2 — Por qué GELU en lugar de ReLU (2:20–2:55)

**Narración:**
> "Las activaciones GELU merecen un momento de atención.
> ReLU — la activación clásica — es simple: cualquier valor negativo se convierte en cero.
> GELU es distinto: en lugar de un corte abrupto, aplica una curva suave
> inspirada en la distribución gaussiana. Los valores negativos no se eliminan por completo —
> se atenúan gradualmente. Esto permite que el gradiente fluya de forma más rica
> durante el entrenamiento, especialmente para activaciones pequeñas."

**Visual — segundo a segundo:**
```
2:20–2:30
  Gráfica XY aparece en pantalla.
  Eje X: "entrada a la neurona" (de -3 a 3)
  Eje Y: "salida" (de -0.2 a 3)
  Primero aparece la curva ReLU: línea en L — cero para x<0, diagonal para x>0.
  Color: rojo (#FF4455). Etiqueta: "ReLU"

2:30–2:45
  Sobre la misma gráfica aparece la curva GELU: línea suave, ligeramente
  bajo cero para x ≈ -0.5, luego sube fluidamente.
  Color: naranja (#FF7B35). Etiqueta: "GELU"
  Una zona sombreada en [-1.5, 0] muestra la diferencia:
  "GELU deja pasar información negativa atenuada"

2:45–2:55
  La gráfica se minimiza a la esquina inferior derecha (thumbnail).
  El diagrama de la red neuronal de Escena 2.1 vuelve al centro.
  La activación GELU en cada bloque pulsa brevemente en naranja.
  → Continúa en Escena 2.3
```

**Prompt imagen estática:**
`Mathematical graph comparing ReLU (red L-shape, zero for negatives) vs GELU (smooth orange curve, slight negative values near x=-0.5), x-axis labeled "entrada neurona" from -3 to 3, y-axis "salida", shaded region highlighting where GELU allows attenuated negative information through, dark background clean plot`

---

## ESCENA 2.3 — La esfera latente: normalización L2 (2:55–3:45)

**Narración:**
> "La última capa del encoder produce un vector de 512 dimensiones.
> Pero antes de usarlo, hacemos algo crucial: lo normalizamos a longitud 1.
> Dividimos cada vector por su propia magnitud.
> El resultado es que todos los embeddings — de todos los pixels —
> quedan proyectados sobre la superficie de una hiperesfera unitaria.
> ¿Por qué importa esto? Porque en una esfera, la distancia entre dos puntos
> equivale exactamente al coseno del ángulo entre ellos.
> Y el coseno del ángulo mide similitud de forma limpia, sin importar la escala."

**Visual — segundo a segundo:**
```
2:55–3:05
  El vector de 512 dimensiones del encoder aparece a la izquierda.
  Una flecha con texto "÷ ‖z‖₂" lleva a un nuevo vector a la derecha.
  Texto bajo la flecha: "normalización L2"
  Los dos vectores se muestran como barras verticales:
  - Izquierda: barras de altura variable, magnitudes diferentes
  - Derecha: barras normalizadas, ‖z‖ = 1.0 exactamente

3:05–3:20
  La pantalla se transforma en una ESFERA 3D (simplificada a 3D para visualizar).
  Aparecen 5 puntos de colores distintos en la superficie:
    rojo (papa), azul (maíz), verde (arveja), amarillo (fresa), naranja (haba)
  Cada punto tiene una flecha desde el centro mostrando su "dirección".
  El centro de la esfera está marcado con "0" (origen).

3:20–3:35
  Un sexto punto aparece: un pixel sin etiqueta (color gris).
  Se calcula el ángulo θ entre el punto gris y el punto rojo (papa).
  Aparece la fórmula: cos(θ) = z_i · c_k  (producto punto de vectores unitarios)
  El ángulo θ se muestra en la esfera con un arco.
  Texto: "Ángulo pequeño = gran similitud"

3:35–3:45
  Zoom-out: la esfera queda en el lado izquierdo de la pantalla.
  A la derecha aparece un espacio vacío con un signo "+".
  Texto aparece gradualmente: "+ Prototipos = ?"
  La narración hace una pausa dramática de 1 segundo.
  → FADE → Título: "PARTE 3 — LOS PROTOTIPOS"
```

**Prompt imagen estática:**
`3D unit sphere on dark background, 5 colored points on surface (red=papa, blue=maíz, green=arveja, yellow=fresa, orange=haba) each with direction arrows from center, one grey unlabeled point showing angle θ to nearest prototype, formula cos(θ)=z·c shown, caption "ángulo pequeño = gran similitud"`

---

# PARTE 3 — LOS PROTOTIPOS (1:45)
*Los prototipos son los "representantes" de cada cultivo en el espacio latente.*

---

## ESCENA 3.1 — Qué es un prototipo (3:45–4:20)

**Narración:**
> "Un prototipo es simplemente un vector aprendible —
> un punto en la misma esfera de 512 dimensiones donde viven los embeddings.
> El modelo tiene dieciocho prototipos, uno por cada clase de cultivo.
> Al inicio del entrenamiento, están en posiciones aleatorias.
> Durante el entrenamiento, se ajustan para que cada uno quede
> en la dirección promedio de todos los pixels de su cultivo.
> Al final, el prototipo de 'papa' apunta en la dirección donde
> se concentran los pixels de papa."

**Visual — segundo a segundo:**
```
3:45–3:55
  La esfera de la escena anterior. Ahora aparecen 18 FLECHAS GRANDES
  desde el centro hacia la superficie — los prototipos.
  Cada flecha tiene un color distinto y una etiqueta:
    Papa, Maíz, Arveja, Fresa, Haba, Tomate, Cebolla,
    Café, Caña, Plátano, Uchuva, Mora, Habichuela,
    Pepino, Zanahoria, Remolacha, Frijol, Pimentón

3:55–4:08
  Los prototipos comienzan en posiciones aleatorias (flechas en desorden).
  Gradualmente, a medida que "el entrenamiento avanza" (counter de épocas aparece):
  Los puntos de pixels se acercan a las flechas de su cultivo.
  Las flechas se mueven suavemente para alinearse con sus clusters.
  Animación fluida, 5 pasos clave del entrenamiento.

4:08–4:20
  Estado final: 18 prototipos bien distribuidos, cada uno rodeado
  de puntos del color de su cultivo.
  Texto aparece: "c_k ∈ ℝ⁵¹² | ‖c_k‖ = 1 | k = 1..18"
  → Continúa en Escena 3.2
```

**Prompt imagen estática:**
`Unit sphere with 18 labeled prototype arrows from center to surface (each crop: papa, maíz, arveja, fresa, etc.), colored pixel points clustering around their corresponding prototype arrows, training epoch counter visible, 3D minimalist visualization dark background`

---

## ESCENA 3.2 — Del embedding al score (4:20–5:30)

**Narración:**
> "Para clasificar un pixel, calculamos su similitud con cada prototipo.
> Hacemos el producto punto entre el embedding del pixel y cada uno de los 18 prototipos.
> Como ambos vectores tienen longitud 1, el resultado es exactamente el coseno del ángulo —
> un número entre -1 y 1 para cada cultivo.
> Luego dividimos cada score por un parámetro llamado temperatura — tau.
> Cuanto más pequeño sea tau, más concentrada queda la distribución final.
> Con tau igual a 0.05 — el valor optimizado — las predicciones son bastante nítidas."

**Visual — segundo a segundo:**
```
4:20–4:35
  Diagrama lineal en pantalla:
    [Pixel embedding z_i (512D)] 
        ↓  producto punto con cada c_k
    [18 scores: s₁, s₂, ..., s₁₈]
  
  La operación se muestra como una multiplicación matricial:
    z_i (1×512) × C^T (512×18) = scores (1×18)
  Los scores aparecen como una fila de 18 barras verticales.
  Algunos positivos (altos), algunos negativos (bajos).

4:35–4:50
  Los scores se dividen por τ = 0.05 (valor aparece en pantalla).
  Las barras se "amplían" — la diferencia entre el mayor y el menor se hace más grande.
  Una flecha etiquetada "÷ τ" separa el "antes" y el "después".
  Texto: "τ pequeño → predicciones más polarizadas"

4:50–5:10
  Se aplica softmax a los scores escalados.
  Las barras se convierten en probabilidades que suman 1.
  Resultado: P(cultivo | pixel) = [0.67, 0.12, 0.08, ...]
  La barra más alta (Papa = 0.67) se ilumina en verde brillante.

5:10–5:30
  COMPARACIÓN VISUAL: dos columnas
    τ = 0.50: barras casi uniformes (distribución plana, incertidumbre)
    τ = 0.05: una barra dominante (predicción confiada)
  Texto central: "τ controla la confianza del modelo"
  Texto debajo: "τ = 0.0497 (optimizado con Optuna)"
  → Una pregunta aparece en pantalla: "¿Pero cómo sabemos que estas asignaciones
    son correctas si no tenemos etiquetas individuales?"
  → FADE → Título: "PARTE 4 — TRANSPORTE ÓPTIMO"
```

**Prompt imagen estática:**
`Two-panel comparison showing temperature tau effect on softmax distribution: LEFT panel tau=0.5 shows near-uniform probability bars across 18 crops, RIGHT panel tau=0.05 shows one dominant bar (papa 67%) with others much lower, arrow between panels labeled "÷ τ", clean bar chart visualization dark background`

---

# PARTE 4 — TRANSPORTE ÓPTIMO Y SINKHORN-KNOPP (3:30)
*El corazón del modelo: cómo las proporciones EVA guían las asignaciones.*

---

## ESCENA 4.1 — El problema de asignación (5:30–6:15)

**Narración:**
> "Aquí está el problema central.
> Tenemos N pixels en un municipio. Para cada uno, el modelo produce scores
> de similitud con los 18 prototipos. Queremos asignar cada pixel al prototipo
> más parecido — pero con una restricción crucial:
> el número de pixels asignados a 'papa' no puede ser cualquiera.
> Debe ser exactamente el 43% que dice el EVA.
> Lo mismo para maíz, arveja, y cada uno de los 18 cultivos.
> Este es un problema de transporte óptimo:
> mover 'masa' de pixels hacia prototipos maximizando similitud total,
> respetando cuánta masa puede recibir cada prototipo."

**Visual — segundo a segundo:**
```
5:30–5:45
  DIAGRAMA BIPARTITO en pantalla:
    Izquierda: columna de 8 círculos = pixels (p₁, p₂, ..., pₙ)
    Derecha: columna de 5 rectángulos = prototipos (Papa, Maíz, Arveja, Haba, Otros)
    (simplificado a 5 para visualización)

  Los círculos de pixels son grises (sin asignar).
  Los rectángulos de prototipos muestran su cuota EVA:
    Papa  [████████ 43%]
    Maíz  [████ 18%]
    Arveja[██   9%]
    Haba  [█    6%]
    Otros [████ 24%]

5:45–6:00
  Flechas tenues aparecen conectando cada pixel a TODOS los prototipos.
  El grosor de cada flecha es proporcional a la similitud coseno.
  Texto: "Costo de asignación = -similitud"

6:00–6:15
  Aparece un semáforo rojo sobre el diagrama:
  "Restricción: la masa total que llega a Papa debe ser 43%"
  La restricción se muestra como una barra de capacidad al lado de cada prototipo.
  Texto matemático aparece en el fondo (translúcido):
    minimizar Σᵢⱼ Qᵢⱼ · (-sᵢⱼ)
    sujeto a: Σⱼ Qᵢⱼ = 1/N  (cada pixel suma 1/N)
              Σᵢ Qᵢⱼ = wⱼ   (cada prototipo recibe su cuota EVA)
  → Continúa en Escena 4.2
```

**Prompt imagen estática:**
`Bipartite graph for optimal transport: left column shows N pixel nodes (grey circles), right column shows 5 crop prototypes (colored rectangles) with EVA capacity bars (papa 43%, maíz 18%, arveja 9%, haba 6%, otros 24%), flow arrows of varying thickness from pixels to prototypes proportional to similarity, constraint equations shown transparently in background`

---

## ESCENA 4.2 — Sinkhorn-Knopp paso a paso (6:15–7:30)

**Narración:**
> "La solución a este problema de transporte óptimo se calcula con el algoritmo Sinkhorn-Knopp.
> El punto de partida es la matriz de scores:
> N filas — una por pixel — y 18 columnas — una por cultivo.
> El algoritmo alterna dos pasos muy simples, repetidos cinco veces.
> Paso uno: normaliza cada fila para que sume uno.
> Esto convierte cada fila en una distribución de probabilidad sobre cultivos.
> Paso dos: normaliza cada columna para que sume la cuota del EVA.
> Esto fuerza que las proporciones del municipio sean respetadas.
> Alternando estos dos pasos, la matriz converge a la asignación óptima."

**Visual — segundo a segundo:**
```
6:15–6:30
  Pantalla muestra una MATRIZ de calor (heatmap): N filas × 18 columnas.
  Cada celda tiene un color de intensidad proporcional al score.
  Eje Y: "Pixels del municipio" | Eje X: "Cultivos (Papa, Maíz, ...)"
  Título: "M — Matriz de similitudes (antes de Sinkhorn)"
  Las filas tienen sumas irregulares — no normalizadas.

6:30–6:45
  PASO 1 aparece en el borde superior izquierdo.
  Animación: cada fila se normaliza simultáneamente.
  Las celdas de cada fila se redistribuyen para que la suma sea 1/N.
  Una barra de "suma de fila" a la derecha se iguala para todas.
  Texto: "Paso 1: normalizar filas → Σⱼ Qᵢⱼ = 1/N"

6:45–7:00
  PASO 2 aparece.
  Animación: cada columna se normaliza para que sume su cuota EVA wⱼ.
  La columna "Papa" se ajusta para sumar 0.43.
  La columna "Maíz" para 0.18. Etc.
  Una barra de "suma de columna" en el fondo se ajusta a wⱼ.
  Texto: "Paso 2: normalizar columnas → Σᵢ Qᵢⱼ = wⱼ (EVA)"

7:00–7:15
  Los pasos 1 y 2 se repiten 3 veces más en TIMELAPSE rápido.
  Counter de iteraciones: "1 / 5... 2 / 5... 3 / 5... 4 / 5... 5 / 5"
  La matriz gradualmente "se asienta" — los cambios en cada iteración son menores.
  Los colores se estabilizan en patrones claros.

7:15–7:30
  La matriz final Q aparece: ahora tiene estructura limpia.
  Cada fila es una distribución de probabilidad (etiqueta suave) para un pixel.
  La suma de cada columna coincide exactamente con las proporciones EVA.
  Texto destacado: "Q — Código óptimo de asignación"
  Sub-texto: "Cada fila Q[i] es la 'etiqueta suave' del pixel i"
  → Una flecha apunta desde Q hacia el siguiente paso: "¿Cómo usamos Q para entrenar?"
  → FADE → Título: "PARTE 5 — EL ENTRENAMIENTO"
```

**Prompt imagen estática (Paso 1):**
`NxK heatmap matrix showing Sinkhorn-Knopp step 1 (row normalization): before shows irregular row sums, after shows each row summing to uniform 1/N, row sum bars on right side equalizing, color intensity shows probability values, mathematical annotation Σⱼ Qᵢⱼ = 1/N, dark background educational diagram`

**Prompt imagen estática (Paso 2):**
`NxK heatmap matrix showing Sinkhorn-Knopp step 2 (column normalization): column sum bars at bottom adjusting to match EVA proportions (papa col sums to 0.43, maíz to 0.18 etc), EVA proportion labels visible, mathematical annotation Σᵢ Qᵢⱼ = wⱼ, clean iteration visualization`

**Prompt imagen estática (Resultado Q):**
`Final Sinkhorn-Knopp output Q matrix after 5 iterations: clean heatmap with clear structure, each row is a soft label probability distribution for one pixel, column sums precisely matching EVA proportions shown in bar chart below, labeled "Código óptimo Q — etiqueta suave por pixel"`

---

# PARTE 5 — EL ENTRENAMIENTO (2:30)
*Swap-loss: dos vistas del mismo pixel deben predecir el mismo código Q.*

---

## ESCENA 5.1 — Aumentación de features (7:30–8:10)

**Narración:**
> "Para entrenar el modelo, necesitamos una señal de error.
> Usamos un truco brillante tomado de SwAV, el método de Facebook AI de 2020,
> adaptado aquí para features geoespaciales en lugar de imágenes.
> De cada pixel generamos dos versiones ligeramente perturbadas —
> como si midieramos el mismo campo en dos días distintos con
> ligero ruido en los sensores.
> A la primera la llamamos vista-S. A la segunda, vista-T.
> Las perturbaciones son ruido gaussiano en variables de clima y satélite,
> más dropout aleatorio de algunas features.
> Las variables topográficas y de suelo no se perturban — son estables."

**Visual — segundo a segundo:**
```
7:30–7:42
  El pixel original (vector de 72 valores) aparece en el centro.
  Se bifurca en dos ramas: izquierda (vista-S) y derecha (vista-T).

7:42–7:55
  En la rama izquierda (vista-S):
    Las features de clima/satélite parpadean ligeramente (ruido σ=0.033).
    Algunas features se vuelven grises (dropout p=0.2).
    Las features de suelo/topografía permanecen sin cambio (color verde estable).
    Etiqueta: "X_s — Vista Source"
  
  En la rama derecha (vista-T), mismo proceso pero perturbaciones diferentes:
    Etiqueta: "X_t — Vista Target"

7:55–8:10
  Las dos vistas se muestran como dos vectores paralelos.
  Las posiciones donde hay ruido se resaltan con llaves curvas.
  Las posiciones donde coinciden exactamente se resaltan en verde.
  Texto central: "Misma esencia — perturbaciones distintas"
  → Continúa en Escena 5.2
```

**Prompt imagen estática:**
`Single pixel feature vector branching into two augmented views X_s (left) and X_t (right): climate and satellite features show slight color variation (gaussian noise σ=0.033), some features greyed out (dropout p=0.2), soil and topography features remain identical and stable (green highlight), caption "misma esencia - perturbaciones distintas", fork diagram`

---

## ESCENA 5.2 — El swap loss (8:10–9:15)

**Narración:**
> "Aquí está la idea del swap loss.
> La vista-S pasa por el encoder y los prototipos para producir probabilidades P-S.
> La vista-T hace lo mismo para producir probabilidades P-T.
> Pero además, calculamos los códigos Sinkhorn de cada vista:
> Q-S para la vista-S y Q-T para la vista-T.
> La pérdida de entrenamiento es:
> qué tan bien predice P-S el código Q-T,
> más qué tan bien predice P-T el código Q-S.
> Es decir: lo que predigo desde una vista debe coincidir
> con el código óptimo calculado desde la otra vista.
> Este 'intercambio' de vistas es el truco que da el nombre al método —
> Swapping Assignments between Views."

**Visual — segundo a segundo:**
```
8:10–8:25
  Diagrama de flujo completo aparece en pantalla, dos caminos paralelos:

  CAMINO SUPERIOR (Vista-S):
  X_s → [Encoder] → z_s → [Prototipos] → scores_s → [softmax/τ] → P_s

  CAMINO INFERIOR (Vista-T):
  X_t → [Encoder] → z_t → [Prototipos] → scores_t → [softmax/τ] → P_t

  El Encoder y los Prototipos son COMPARTIDOS (mismo bloque, con línea que baja).
  Texto: "Pesos compartidos — mismo modelo para ambas vistas"

8:25–8:45
  Ahora aparecen los códigos Sinkhorn:
  Q_s ← Sinkhorn(scores_s, W_EVA) [rama superior]
  Q_t ← Sinkhorn(scores_t, W_EVA) [rama inferior]
  Las Q tienen un color distinto (amarillo) que las P (azul).

8:45–9:05
  Las flechas de pérdida aparecen CRUZADAS (el "swap"):
    P_s ──────────────→ CrossEntropy(P_s, Q_t)  [predecir código de t desde s]
    P_t ←────────────── CrossEntropy(P_t, Q_s)  [predecir código de s desde t]
  
  Las flechas cruzadas se resaltan en rojo.
  Texto: "Loss = ½ [CE(P_s, Q_t) + CE(P_t, Q_s)]"
  
9:05–9:15
  Una ecuación completa aparece en el centro:
    ℒ_swap = -½ Σᵢ [Q_t(i)ᵀ log P_s(i) + Q_s(i)ᵀ log P_t(i)]
  
  Texto explicativo: "Si ambas vistas predicen lo mismo → pérdida baja"
  → Continúa en Escena 5.3
```

**Prompt imagen estática:**
`SwAV-style swap loss diagram: two parallel paths from X_s and X_t through shared encoder and prototypes to P_s and P_t respectively, Sinkhorn blocks computing Q_s and Q_t from EVA proportions, CROSSED arrows showing CrossEntropy(P_s, Q_t) and CrossEntropy(P_t, Q_s), loss equation at bottom, shared encoder block highlighted, dark background`

---

## ESCENA 5.3 — KoLeo: anti-colapso de prototipos (9:15–10:00)

**Narración:**
> "Hay un problema potencial: todos los prototipos podrían colapsar
> en la misma posición. Si el encoder siempre asigna todo a 'papa',
> la pérdida podría ser baja sin que el modelo haya aprendido nada real.
> La regularización KoLeo previene esto.
> Penaliza los prototipos que están demasiado cerca entre sí,
> forzando que los 18 vectores se repartan el espacio esférico.
> Es como poner imanes de repulsión en los prototipos —
> cada uno quiere alejarse de los demás."

**Visual — segundo a segundo:**
```
9:15–9:28
  ANTES (sin KoLeo): La esfera aparece con los 18 prototipos
  amontonados en un solo sector. La mitad del espacio esférico vacío.
  Texto: "Colapso de prototipos — modelo degenerado"

9:28–9:42
  DESPUÉS (con KoLeo): Los prototipos se dispersan uniformemente por la esfera.
  Animación: flechas de repulsión entre prototipos adyacentes.
  Cada prototipo "rebota" hacia espacio libre.
  Texto: "KoLeo: maximizar distancia mínima entre prototipos"

9:42–10:00
  Ecuación aparece:
    ℒ_KoLeo = - (1/K) Σₖ log min_{k'≠k} ‖cₖ - cₖ'‖
  
  Pérdida total completa aparece debajo:
    ℒ_total = ℒ_swap + λ · ℒ_KoLeo
  
  Texto: "λ = 0.214 (optimizado con Optuna)"
  → FADE → Título: "PARTE 6 — EL BUCLE COMPLETO"
```

**Prompt imagen estática:**
`Side-by-side sphere comparison: LEFT sphere shows prototype collapse (18 arrows clustered in one sector, half sphere empty, labeled "colapso"), RIGHT sphere shows KoLeo-regularized prototypes spread evenly across full sphere surface with repulsion arrows between nearby prototypes, KoLeo equation below, dark background`

---

# PARTE 6 — EL BUCLE COMPLETO (1:30)
*Todo junto: una iteración de entrenamiento de principio a fin.*

---

## ESCENA 6.1 — Un epoch completo (10:00–11:00)

**Narración:**
> "Integremos todo en un solo ciclo de entrenamiento.
> Tomamos un batch de pixels de un municipio — un 'bag'.
> Generamos dos vistas aumentadas de cada pixel.
> Ambas vistas pasan por el encoder compartido para obtener embeddings.
> Los embeddings se pasan por los prototipos para obtener scores.
> Los scores se convierten en distribuciones P con softmax y temperatura tau.
> Los mismos scores pasan por Sinkhorn-Knopp usando las proporciones EVA del municipio,
> produciendo los códigos Q.
> Calculamos el swap loss cruzado y la regularización KoLeo.
> El gradiente fluye hacia atrás, actualizando el encoder y los prototipos.
> Repetimos esto 500 épocas."

**Visual — segundo a segundo:**
```
10:00–10:10
  Pantalla en negro. Aparece el diagrama completo del modelo de una vez:
  es el mismo diagrama de la Escena 5.2 pero expandido para mostrar todos los pasos.
  Todos los bloques están presentes pero desaturados (gris).

10:10–10:45
  Animación de un "token" (bola azul) que recorre el diagrama completo:
  
    Bag (municipio) → X_orig
    X_orig → X_s (aumentación, bola se bifurca en dos: azul y naranja)
    X_s, X_t → Encoder → z_s, z_t (bolas entran al cubo del encoder)
    z_s, z_t → Prototipos → scores (bolas golpean la matriz de prototipos)
    scores → softmax(τ) → P_s, P_t (bolas se convierten en vectores de prob)
    scores → Sinkhorn(W_EVA) → Q_s, Q_t (flecha paralela hacia abajo)
    P_s ↔ Q_t, P_t ↔ Q_s → ℒ_swap (flechas cruzadas se encienden en rojo)
    Prototipos → ℒ_KoLeo (pequeña bola verde llega al bloque KoLeo)
    ℒ_total → Backprop → Encoder actualizado (flecha de retorno verde)
  
  Cada bloque se ilumina al recibir la bola.

10:45–11:00
  Counter de épocas aparece en la esquina superior derecha: 1 / 500.
  Cada epoch el diagrama "pulsa" una vez.
  Time-lapse: el counter avanza rápidamente hasta 500.
  La curva de pérdida aparece en miniatura en la esquina inferior:
  baja de ~3.5 a ~0.8 suavemente.
  Texto: "14.2 minutos de entrenamiento en GPU CUDA"
  → Continúa en Escena 6.2
```

**Prompt imagen estática:**
`Complete LLP-Co training loop diagram: bag of pixels → augmentation (X_s/X_t) → shared encoder → prototypes → softmax+tau (P_s/P_t) and Sinkhorn+EVA (Q_s/Q_t) → crossed swap loss arrows → KoLeo regularization → backpropagation arrow returning to encoder, all blocks color-coded, epoch counter 500 in corner, training loss curve in bottom corner`

---

## ESCENA 6.2 — Optimización de hiperparámetros con Optuna (11:00–11:30)

**Narración:**
> "El modelo tiene 7 hiperparámetros clave.
> En lugar de ajustarlos a mano, se usa Optuna —
> una librería de optimización bayesiana que ejecuta 100 pruebas,
> cada una con una configuración diferente, guiándose por los resultados anteriores.
> El objetivo: minimizar la divergencia KL entre las proporciones predichas
> y las del EVA en el conjunto de validación.
> Los valores óptimos encontrados:
> tau igual a 0.0497, epsilon Sinkhorn 0.0224, peso KoLeo 0.214."

**Visual — segundo a segundo:**
```
11:00–11:12
  Tabla de 7 hiperparámetros con rango y valor óptimo:
  
  | Hiperparámetro  | Rango       | Óptimo   | Efecto                        |
  |-----------------|-------------|----------|-------------------------------|
  | τ (tau)         | 0.05–0.20   | 0.0497   | Nitidez de predicciones       |
  | ε (Sinkhorn)    | 0.005–0.10  | 0.0224   | Fidelidad al prior EVA        |
  | λ (KoLeo)       | 0.01–0.50   | 0.214    | Diversidad de prototipos      |
  | σ (ruido aug.)  | 0.01–0.15   | 0.033    | Intensidad de perturbación    |
  | p_drop (aug.)   | 0.05–0.40   | 0.204    | Dropout en aumentación        |
  | LR_init         | 3e-4–3e-3   | 0.00116  | Tasa de aprendizaje inicial   |
  | emb_dim         | 128–512     | 512      | Dimensión del embedding       |

11:12–11:30
  Gráfica de dispersión de los 100 trials de Optuna:
  Eje X: τ | Eje Y: ε_Sinkhorn | Color: KL divergencia (azul=bajo=mejor)
  Una estrella marca el punto óptimo en τ=0.05, ε=0.022.
  Texto: "100 trials × ~8 min/trial = búsqueda de 13 horas"
  → FADE → Título: "PARTE 7 — LOS RESULTADOS"
```

**Prompt imagen estática:**
`Optuna optimization scatter plot: x-axis tau (0.05-0.20), y-axis epsilon Sinkhorn (0.005-0.10), 100 trial points colored by validation KL divergence (blue=low=better, red=high=worse), optimal point starred at tau=0.05 epsilon=0.022, hyperparameter table inset showing all 7 parameters with ranges and optimal values`

---

# PARTE 7 — LOS RESULTADOS (1:30)
*¿Qué produce el modelo y cómo se evalúa?*

---

## ESCENA 7.1 — La predicción por pixel (11:30–12:00)

**Narración:**
> "Una vez entrenado, el encoder convierte cada pixel en un embedding.
> Los embeddings se pasan por los prototipos con temperatura tau.
> El resultado es un vector de 18 probabilidades por pixel.
> Tenemos aproximadamente 9 millones de pixels en Cundinamarca.
> Cada uno recibe su distribución sobre 18 cultivos.
> El mapa resultante no es 'en este pixel hay papa' —
> es 'en este pixel hay 67% de probabilidad de papa,
> 12% maíz, 8% arveja'."

**Visual — segundo a segundo:**
```
11:30–11:42
  Mapa de Cundinamarca pixelado.
  Cada pixel tiene un mini pie-chart encima (demasiado pequeño para ver individualmente).
  Un pixel específico se amplía (zoom in): muestra sus 18 barras de probabilidad.
    Papa     ████████████ 67%
    Maíz     ██           12%
    Arveja   █            8%
    Haba                  4%
    ...otros              9%

11:42–12:00
  El zoom-out muestra el mapa coloreado por la clase más probable (top-1).
  Cada pixel toma el color del cultivo con mayor probabilidad.
  Se compara lado a lado con el mapa EVA municipal (colores planos por municipio).
  Leyenda con 18 colores.
  Texto: "P(cultivo | pixel) — 18 probabilidades por cada uno de los ~9M pixels"
  → Continúa en Escena 7.2
```

**Prompt imagen estática:**
`Side-by-side comparison: LEFT shows pixelated Cundinamarca map with each 50m pixel colored by most probable crop (18-color legend: green papa, blue maíz, orange arveja etc), one pixel zoomed showing probability bars; RIGHT shows flat EVA municipal map with whole municipalities colored uniformly, clear contrast between pixel-level and municipal-level resolution`

---

## ESCENA 7.2 — Métricas de evaluación (12:00–12:45)

**Narración:**
> "Para evaluar el modelo usamos dos métricas principales.
> La primera es la divergencia KL — la métrica nativa de LLP —
> que mide qué tan lejos están las proporciones predichas por municipio
> de las proporciones reales del EVA. Cuanto menor, mejor.
> La segunda es Top-K accuracy usando los pixeles de monitoreo UPRA
> como ground truth: ¿con qué frecuencia el cultivo real de un pixel
> aparece entre las tres predicciones más probables del modelo?
> Este Top-3 está por encima del 70% en el conjunto de prueba."

**Visual — segundo a segundo:**
```
12:00–12:15
  Panel izquierdo: barras de KL divergencia por municipio (ordenadas de menor a mayor).
  Mayoría de barras bajas (azul). Algunos municipios con KL alto (rojo).
  Texto: "KL(w_EVA || ŷ_municipio) — métrica nativa LLP"

12:15–12:30
  Panel central: gauges circulares mostrando:
    Top-1: 52% (el cultivo real es el más probable)
    Top-3: 73% (el cultivo real está entre los 3 más probables)
    Top-5: 84% (entre los 5 más probables)
  Los gauges se llenan con una animación de arco.

12:30–12:45
  Panel derecho: matriz de confusión 6×6 (cultivos más frecuentes).
  Diagonal verde (aciertos). Off-diagonal rojo (errores).
  Los errores más frecuentes son entre cultivos similares:
  Papa↔Arveja, Maíz↔Frijol (mismas condiciones climáticas).
  Texto: "Los errores ocurren entre cultivos con condiciones similares — esperable"
  → Continúa en Escena 7.3
```

**Prompt imagen estática:**
`Three-panel evaluation dashboard: LEFT shows bar chart of KL divergence per municipality (sorted low to high, blue bars good, red bars problematic); CENTER shows three circular gauges Top-1 52%, Top-3 73%, Top-5 84%; RIGHT shows 6x6 confusion matrix with green diagonal and red off-diagonal errors, crop names labeled, caption showing similar crops confused`

---

## ESCENA 7.3 — El ensamble y cierre (12:45–13:30)

**Narración:**
> "Las predicciones de LLP-Co son la capa 2 de un sistema jerárquico.
> En los pixels donde hay monitoreo de campo directo — la capa 1 —
> esos datos prevalecen con confianza total.
> En los pixels donde hay evidencia clara de no-aptitud — la capa 3 —
> la predicción se enmascara.
> El resultado integrado es 'Qué Sembrar' —
> un mapa de recomendación de cultivos para Cundinamarca,
> a resolución de 50 metros, actualizado semestralmente.
> LLP-Co resuelve el problema que planteamos al inicio:
> aprende de proporciones, predice en pixels."

**Visual — segundo a segundo:**
```
12:45–13:00
  ANIMACIÓN CAPAS (vista cenital del mapa):
  Capa base: predicciones LLP-Co en todos los pixels (colores de cultivo).
  Se superpone la Capa 1: puntos brillantes (estrellas) donde hay monitoreo UPRA.
  Se aplica la Capa 3: zonas urbanas y rocosas se oscurecen (No-apto).
  El mapa resultante queda limpio y completo.

13:00–13:15
  Zoom IN a una zona agrícola representativa.
  El mapa muestra variación dentro del mismo municipio:
  un municipio que el EVA decía "43% papa" ahora muestra
  exactamente qué zonas (laderas, valles) tienen más probabilidad de papa.
  Texto: "Resolución 50m vs. resolución municipal: de polígono a pixel"

13:15–13:30
  La pantalla vuelve al diagrama de tres columnas de la Escena 1.3.
  Encoder + Prototipos + Sinkhorn-Knopp.
  Cada bloque se ilumina brevemente.
  Texto final aparece gradualmente:
    "Aprender de proporciones → predecir en pixels"
    "LLP-Co — La Rosa et al., AAAI 2022"
    "AgroPlus — Cundinamarca 2025"
  Fade a negro.
```

**Prompt imagen estática:**
`Layer-by-layer map construction: base layer shows LLP-Co pixel predictions (colorful crop map), L1 monitoring points overlay as bright stars, L3 non-suitable mask darkens urban zones, final integrated "Qué Sembrar" map shows sub-municipal variation within Zipaquirá (hilly areas vs. flat areas with different crop probabilities), 50m pixel resolution visible`

---

# RESUMEN EJECUTIVO DE ESCENAS Y CONCATENACIÓN

```
PARTE 1 — EL PUNTO DE PARTIDA (1:30)
  1.1 Un pixel sin nombre       → establece el sujeto: el pixel y sus features
  1.2 El dato que sí tenemos    → introduce EVA y el concepto de bag
  1.3 La pregunta guía          → presenta los 3 bloques: Encoder, Prototipos, Sinkhorn
        ↓ "Vamos parte por parte"

PARTE 2 — EL ENCODER (2:15)
  2.1 La red neuronal           → arquitectura MLP capa por capa
  2.2 Por qué GELU              → detalle de activación (1 escena corta, no interrumpe)
  2.3 La esfera latente         → normalización L2, espacio geométrico
        ↓ "+ Prototipos = ?"

PARTE 3 — LOS PROTOTIPOS (1:45)
  3.1 Qué es un prototipo       → vectores aprendibles en la esfera
  3.2 Del embedding al score    → similitud coseno, temperatura tau
        ↓ "¿Cómo sabemos que son correctas sin etiquetas?"

PARTE 4 — TRANSPORTE ÓPTIMO Y SINKHORN-KNOPP (3:30)
  4.1 El problema de asignación → restricción EVA, formulación OT
  4.2 Sinkhorn-Knopp paso a paso → iteraciones de normalización
        ↓ "¿Cómo usamos Q para entrenar?"

PARTE 5 — EL ENTRENAMIENTO (2:30)
  5.1 Aumentación de features   → X_s y X_t como dos vistas
  5.2 El swap loss              → flechas cruzadas P_s↔Q_t y P_t↔Q_s
  5.3 KoLeo: anti-colapso       → regularización de prototipos

PARTE 6 — EL BUCLE COMPLETO (1:30)
  6.1 Un epoch completo         → integración visual de todo el flujo
  6.2 Optuna                    → tabla de hiperparámetros, scatter plot

PARTE 7 — LOS RESULTADOS (1:30)
  7.1 La predicción por pixel   → distribución de 18 probabilidades
  7.2 Métricas de evaluación    → KL divergencia, Top-K accuracy
  7.3 El ensamble y cierre      → capas L1/L2/L3, mapa final, recapitulación
```

---

# ECUACIONES PARA RENDERIZAR (LaTeX)

```latex
% Similitud coseno con temperatura
s_{ik} = \frac{z_i \cdot c_k}{\tau}

% Distribución softmax del modelo
P_s(i) = \text{softmax}\!\left(\frac{z_s^{(i)} \cdot C}{\tau}\right)

% Problema de Optimal Transport
Q^* = \underset{Q \in \mathcal{Q}(w)}{\arg\max} \sum_{ij} Q_{ij} s_{ij}

% Algoritmo Sinkhorn-Knopp (iteraciones)
Q^{(t+1)} = \text{diag}(\mathbf{1}/Q^{(t)}\mathbf{1}) \cdot Q^{(t)}
Q^{(t+2)} = Q^{(t+1)} \cdot \text{diag}(w/Q^{(t+1)\top}\mathbf{1})

% Swap loss
\mathcal{L}_{\text{swap}} = -\frac{1}{2} \sum_i \left[ Q_t^{(i)\top} \log P_s^{(i)} + Q_s^{(i)\top} \log P_t^{(i)} \right]

% KoLeo regularización
\mathcal{L}_{\text{KoLeo}} = -\frac{1}{K} \sum_{k=1}^{K} \log \min_{k' \neq k} \|c_k - c_{k'}\|_2

% Pérdida total
\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{swap}} + \lambda \cdot \mathcal{L}_{\text{KoLeo}}

% Restricción de bag (objetivo final)
\frac{1}{|B_m|} \sum_{i \in B_m} P(y \mid x_i) \approx w_m^{\text{EVA}}
```

---

# ESPECIFICACIONES TÉCNICAS DE PRODUCCIÓN

| Elemento | Especificación |
|----------|---------------|
| Resolución | 3840×2160 (4K), 60fps |
| Fondo | #0A0A0A (negro casi puro) |
| Tipografía | Inter (Google Fonts, libre) |
| Duración total | ~13:30 |
| Narración | ~150 palabras/minuto, español neutro |
| Herramienta animación | Manim Community (ManimML para redes neuronales) |
| Herramienta imágenes | Midjourney v6 o DALL-E 3 con los prompts de esta guía |
| Voz | ElevenLabs — voz masculina, velocidad 0.95, tono académico |
| Música | Ambient instrumental sin letra, 60–80 BPM |

---

# FUENTES Y REFERENCIAS

- [La Rosa & Oliveira, AAAI 2022 — LLP con Clustering Contrastivo](https://ojs.aaai.org/index.php/AAAI/article/view/20112)
- [Caron et al., NeurIPS 2020 — SwAV: Unsupervised Learning by Contrasting Cluster Assignments](https://arxiv.org/pdf/2006.09882)
- [AI Summer — Explicación visual de SwAV](https://theaisummer.com/swav/)
- [Medium — Explicando SwAV paso a paso](https://medium.com/@liviameinhardt/explaining-swav-unsupervised-learning-of-visual-features-by-contrasting-cluster-assignments-be2a3b520634)
- UPRA — Evaluación Agropecuaria Municipal (EVA), Colombia
