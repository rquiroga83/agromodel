# LLP-Co — Serie de Slides Infográficos
## "Cómo aprende un modelo sin ver las etiquetas individuales"
## 15 slides | Formato 16:9 (1920×1080) | Estilo: técnico-visual minimalista

---

## SISTEMA DE DISEÑO GLOBAL

```
FONDO BASE:        #0D1117  (negro azulado)
FONDO SECUNDARIO:  #161B22  (gris muy oscuro, para paneles)
FONDO TERCIARIO:   #21262D  (gris oscuro, para cards)

AZUL ENCODER:      #4A9EFF  (elementos del encoder / embeddings)
NARANJA PROTOTIPO: #FF7B35  (prototipos / vectores de clase)
VERDE EVA:         #44CC88  (proporciones EVA / señal correcta)
AMARILLO CÓDIGO Q: #FFD166  (códigos Sinkhorn / asignaciones)
ROJO PÉRDIDA:      #FF4455  (funciones de pérdida / errores)
LILA AUGMENTATION: #B57BFF  (data augmentation / vistas)
BLANCO TEXTO:      #E6EDF3
GRIS TEXTO:        #8B949E

TIPOGRAFÍA TÍTULOS:    Inter Bold, 32–40px
TIPOGRAFÍA SUBTÍTULOS: Inter SemiBold, 20–24px
TIPOGRAFÍA CUERPO:     Inter Regular, 14–16px
TIPOGRAFÍA ECUACIONES: JetBrains Mono o LaTeX renderizado
BORDES / SEPARADORES:  1px #30363D
ESQUINAS:              border-radius 8px en todos los cards
```

---

# SLIDE 01 — EL PROBLEMA CENTRAL

**Título del slide:** `El Problema: Aprender sin Etiquetas Individuales`
**Subtítulo:** `Learning from Label Proportions (LLP)`

---

## LAYOUT (grilla 12 columnas × 8 filas)

```
┌─────────────────────────────────────────────────────────────────┐
│  TÍTULO                                              [Logo]      │  fila 1
├──────────────────────────┬──────────────────────────────────────┤
│                          │                                      │
│   PANEL A                │   PANEL B                            │  filas 2–6
│   Lo que NO tenemos      │   Lo que SÍ tenemos                  │
│   (etiquetas por pixel)  │   (proporciones por municipio)       │
│                          │                                      │
│                          │                                      │
├──────────────────────────┴──────────────────────────────────────┤
│   PANEL C: Analogía visual de urna                               │  filas 7–8
└─────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — Lo que NO tenemos (col 1–5, filas 2–6)

```
VISUAL PRINCIPAL:
  Grilla de 6×6 = 36 cuadros, cada uno 50×50px de territorio.
  TODOS los cuadros son de color GRIS NEUTRO (#8B949E).
  En el centro de cada cuadro: un signo "?" en blanco.

  Debajo de la grilla, una flecha hacia abajo con texto:
    "¿Papa? ¿Maíz? ¿Arveja? ¿Haba?"

BORDE del panel: 2px dashed #FF4455 (rojo, indica ausencia)
ETIQUETA SUPERIOR: "❌ Sin etiquetas por pixel"  (color #FF4455)

SUBTEXTO bajo el panel:
  "No sabemos qué cultivo
   crece en cada pixel"

TAMAÑO DE LA GRILLA: ocupa 80% del panel A
```

---

## PANEL B — Lo que SÍ tenemos (col 7–12, filas 2–6)

```
VISUAL PRINCIPAL:
  Mapa estilizado de un municipio (polígono irregular, color #21262D).
  Dentro del polígono: los mismos 36 cuadros, ahora coloreados
  en proporciones correctas pero en ORDEN ALEATORIO:
    16 cuadros VERDE (#44CC88)    → Papa 43%
    7 cuadros AZUL (#4A9EFF)     → Maíz 18%
    3 cuadros NARANJA (#FF7B35)  → Arveja 9%
    2 cuadros AMARILLO (#FFD166) → Haba 6%
    8 cuadros GRIS CLARO         → Otros 24%

BARRA DE PROPORCIONES a la derecha del mapa:
  Barras horizontales con porcentaje y nombre:
  ████████████ 43%  Papa
  ████          18%  Maíz
  ██             9%  Arveja
  █              6%  Haba
  ██████        24%  Otros
  (fuente: "EVA Municipal")

BORDE del panel: 2px solid #44CC88 (verde, indica disponibilidad)
ETIQUETA SUPERIOR: "✓ Proporciones por municipio"  (color #44CC88)

SUBTEXTO bajo el panel:
  "Sabemos CUÁNTOS pixels
   son de cada cultivo —
   no cuáles."
```

---

## PANEL C — La analogía (col 1–12, filas 7–8)

```
VISUAL: Línea horizontal de izquierda a derecha:

  [Urna de vidrio con bolas de color]
         ↓
  Bolas visibles en proporciones conocidas
  (43 rojas, 18 azules, 9 naranjas de 100)
         ↓
  [Mano que intenta ver el interior]
         ↓
  "¿Cuál bola es cuál?"  →  SIGNO DE INTERROGACIÓN GRANDE

TEXTO CENTRAL (en el panel):
  "LLP resuelve exactamente esto: conociendo solo las proporciones del municipio,
   el modelo aprende a predecir el cultivo de cada pixel individual."

FONDO del panel C: #161B22 (ligeramente más claro que el fondo)
```

---

## PROMPT IMAGEN PRINCIPAL (Slide 01)
```
Infographic slide dark background #0D1117: LEFT HALF shows 6x6 grid of grey 
pixels all labeled with "?" question marks, red dashed border, label "Sin 
etiquetas por pixel"; RIGHT HALF shows same grid inside municipality polygon 
with pixels colored by crop proportion (43% green papa, 18% blue maíz, 9% 
orange arveja), horizontal bar chart on right showing proportions, green solid 
border, label "Proporciones por municipio"; BOTTOM STRIP shows urn analogy 
with colored balls; Inter font, minimal technical style
```

---
---

# SLIDE 02 — LOS DATOS DE ENTRADA

**Título:** `El Pixel como Observación`
**Subtítulo:** `Cada punto del mapa = vector de 72 variables`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │  fila 1
├──────────────┬─────────────────────────────────────────────────┤
│              │                                                  │
│  PANEL A     │  PANEL B                                         │  filas 2–7
│  El pixel    │  Sus features (4 grupos)                         │
│  físico      │                                                  │
│              │                                                  │
├──────────────┴─────────────────────────────────────────────────┤
│  PANEL C: El vector x ∈ ℝ⁷²   →   "Esto entra al modelo"       │  fila 8
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — El pixel físico (col 1–3, filas 2–7)

```
VISUAL:
  Cuadrado grande (el pixel, 50×50m) con textura de terreno agrícola.
  Color de fondo: verde oscuro con variación de textura.
  
  Encima del cuadrado, las dimensiones en anotación técnica:
    ←  50 m  →
    ↕  50 m  ↕

  Debajo del cuadrado:
    Semestre: "2023-A (Ene–Jun)"
    Municipio: "Zipaquirá"
    Coordenadas: "(4.97°N, 74.01°O)"

BORDE: 2px solid #4A9EFF
```

---

## PANEL B — Los 4 grupos de features (col 4–12, filas 2–7)

```
SUBDIVISIÓN en 4 cards horizontales apilados:

┌─── CARD 1: CLIMA (fondo #1C2128, borde izquierdo #4A9EFF 4px) ───────────┐
│  ÍCONO: nube con sol (24px, color #4A9EFF)
│  TÍTULO: "Variables Climáticas  (18 features)"
│  CHIPS de variables (pills redondeados):
│    [T_min] [T_max] [T_media] [Precipitación] [ETP] [Humedad]
│    [Amplitud_térmica] [Anomalía_precip] [Piso_térmico] ...
│  EJEMPLO VALOR: "T_min = 8.2°C  |  Precip = 142 mm/sem"
└───────────────────────────────────────────────────────────────────────────┘

┌─── CARD 2: SATÉLITE SENTINEL-2 (borde izquierdo #B57BFF 4px) ────────────┐
│  ÍCONO: satélite (24px, color #B57BFF)
│  TÍTULO: "Índices de Vegetación  (21 features — 7 índices × 3 stats)"
│  CHIPS:
│    [NDVI_mean] [NDVI_std] [NDVI_max]
│    [EVI_mean]  [GNDVI_mean] [NDWI_mean]
│    [MSAVI_mean] [BSI_mean] [SAVI_mean]
│  EJEMPLO VALOR: "NDVI_mean = 0.72  |  EVI_max = 0.81"
└───────────────────────────────────────────────────────────────────────────┘

┌─── CARD 3: SUELO (borde izquierdo #FF7B35 4px) ──────────────────────────┐
│  ÍCONO: capas de suelo (24px, color #FF7B35)
│  TÍTULO: "Textura y Química del Suelo  (12 features)"
│  CHIPS:
│    [Arcilla%] [Arena%] [Limo%] [pH] [MO%]
│    [Fósforo] [Potasio] [CIC] [Fertilidad]
│  EJEMPLO VALOR: "Arcilla = 42%  |  pH = 6.1  |  Fertilidad = Media"
└───────────────────────────────────────────────────────────────────────────┘

┌─── CARD 4: TOPOGRAFÍA (borde izquierdo #44CC88 4px) ─────────────────────┐
│  ÍCONO: montaña estilizada (24px, color #44CC88)
│  TÍTULO: "Relieve y Posición  (21 features)"
│  CHIPS:
│    [Elevación] [Pendiente] [Aspecto] [TPI] [TWI]
│    [Curvatura] [Sem_sin] [Sem_cos]  ← codificación cíclica
│  EJEMPLO VALOR: "Elevación = 2.847 m  |  Pendiente = 12°"
└───────────────────────────────────────────────────────────────────────────┘
```

---

## PANEL C — El vector resultante (col 1–12, fila 8)

```
VISUAL: Barra horizontal larga que representa el vector x ∈ ℝ⁷²
  Dividida en 4 segmentos coloreados por grupo:
  [══ CLIMA (18) ══][══════ SATÉLITE (21) ══════][══ SUELO (12) ══][══ TOPO (21) ══]
    (#4A9EFF)              (#B57BFF)                 (#FF7B35)         (#44CC88)

  Encima: "x ∈ ℝ⁷²  —  vector de entrada al modelo"
  Debajo: flecha hacia la derecha → "→ Encoder"
```

---

## PROMPT IMAGEN (Slide 02)
```
Technical infographic slide on dark #0D1117: LEFT shows a single green 50x50m 
terrain pixel with technical annotations (dimensions, coordinates, semester); 
RIGHT shows four stacked cards for feature groups: Climate (blue, 18 features, 
temperature/precipitation chips), Satellite Sentinel-2 (purple, 21 features, 
NDVI/EVI chips), Soil (orange, 12 features), Topography (green, 21 features); 
BOTTOM shows a segmented horizontal bar representing feature vector x∈ℝ72 
colored by group, arrow pointing right to Encoder; Inter font, dark cards
```

---
---

# SLIDE 03 — LOS BAGS: GRUPOS POR MUNICIPIO

**Título:** `Bags: la Unidad de Supervisión`
**Subtítulo:** `Un bag = todos los pixels de un municipio en un semestre`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├──────────────────────┬─────────────────────────────────────────┤
│  PANEL A             │  PANEL B                                 │
│  Mapa Cundinamarca   │  Anatomía de un bag                      │
│  con municipios      │                                          │
├──────────────────────┴─────────────────────────────────────────┤
│  PANEL C: Split train / val / test por municipio                │
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — Mapa de Cundinamarca (col 1–4, filas 2–6)

```
VISUAL:
  Silueta de Cundinamarca en #21262D.
  116 municipios separados por líneas finas #30363D.
  3 municipios resaltados con colores distintos:
    Zipaquirá  → borde #4A9EFF  (ejemplo de bag)
    Soacha     → borde #FF7B35  (otro bag)
    Facatativá → borde #44CC88  (otro bag)

  Encima del mapa:
    "116 municipios"
    "~9.2 M pixels totales"
    "10 semestres (2020–2025)"

  Un municipio resaltado (Zipaquirá) tiene una flecha
  saliendo hacia el Panel B.
```

---

## PANEL B — Anatomía de un bag (col 5–12, filas 2–6)

```
VISUAL: Diagrama de un "bag" (bolsa/contenedor rectangular con borde redondeado)

┌─────────────────────────────────────────────────────────────────┐
│  MUNICIPIO: Zipaquirá  |  SEMESTRE: 2023-A                      │ ← cabecera #161B22
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Grilla de ~40 pixels coloreados aleatoriamente por cultivo]   │
│                                                                  │
│  Verde(papa) Verde Verde Azul(maíz) Verde Gris(otros)...        │
│  Naranja(arv) Verde Azul Verde Amarillo(haba) Verde...          │
│  ...                                                             │
│                                                                  │
│  Nota: "2.847 pixels en este bag"                               │
├─────────────────────────────────────────────────────────────────┤
│  PROPORCIONES EVA (w_m):                                         │ ← pie #161B22
│  ████████████ Papa    43%  │ ████ Maíz   18%                    │
│  ██ Arveja    9%       │ █ Haba    6%   │ ████ Otros 24%        │
└─────────────────────────────────────────────────────────────────┘

A la derecha del bag, una lista de propiedades:

  📦  Bag = (municipio, semestre)
  🔢  Tamaño: N_m pixels
  📊  Supervisión: w_m ∈ Δ¹⁸  (vector de proporciones EVA)
  ⚠️  Sin etiquetas por pixel
  ✓   Solo la distribución agregada es conocida
```

---

## PANEL C — Split train/val/test (col 1–12, filas 7–8)

```
VISUAL: Mapa de Cundinamarca dividido en 3 zonas de color:

  [AZUL #4A9EFF]   60% municipios → TRAIN    (70 municipios)
  [AMARILLO #FFD166] 20% municipios → VALID  (23 municipios)
  [ROJO #FF4455]   20% municipios → TEST     (23 municipios)

  NOTA IMPORTANTE debajo del mapa:
  "⚠ El split es por municipio completo, no por pixel.
   El modelo nunca ve pixeles de los municipios de test durante el entrenamiento."

  A la derecha del mapa, tabla resumen:
  ┌──────────┬────────────┬──────────────┬────────────┐
  │  Split   │ Municipios │    Pixels    │   Bags     │
  ├──────────┼────────────┼──────────────┼────────────┤
  │  Train   │    70      │  ~5.5 M      │   700      │
  │  Valid   │    23      │  ~1.8 M      │   230      │
  │  Test    │    23      │  ~2.1 M      │   230      │
  └──────────┴────────────┴──────────────┴────────────┘
```

---

## PROMPT IMAGEN (Slide 03)
```
Infographic on dark background: LEFT shows Cundinamarca Colombia department 
map with 116 municipality polygons, 3 highlighted with different colors 
(blue Zipaquirá, orange Soacha, green Facatativá), population statistics 
overlay; CENTER/RIGHT shows a bag container with header "Zipaquirá 2023-A", 
inside a grid of colored pixels (green=papa 43%, blue=maíz 18%, etc.) randomly 
arranged, footer shows EVA proportion bar chart; BOTTOM strip shows same map 
split into train/val/test zones with municipality count table
```

---
---

# SLIDE 04 — EL ENCODER MLP

**Título:** `El Encoder: Transformando Pixels en Geometría`
**Subtítulo:** `MLPEncoder — 4 capas — ℝ⁷² → ℝ⁵¹²`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PANEL A: Diagrama de arquitectura (flujo horizontal)            │
│                                                                  │
├──────────────────────┬──────────────────────────────────────────┤
│  PANEL B             │  PANEL C                                  │
│  Detalle de 1 capa   │  Detalle de activaciones                  │
└──────────────────────┴──────────────────────────────────────────┘
```

---

## PANEL A — Arquitectura completa (col 1–12, filas 2–5)

```
DIAGRAMA HORIZONTAL de bloques proporcionales en ancho a la dimensión:

[INPUT]  →  [BLOQUE 1]  →  [BLOQUE 2]  →  [BLOQUE 3]  →  [OUTPUT]
  72           256             128              64             512
  (gris)      (azul)          (azul)          (azul)         (azul brillante)

Los bloques se muestran como rectángulos con:
  - Altura fija (igual para todos)
  - ANCHO proporcional: 256 más ancho, 64 más angosto
  - Fondo: #1C2228 para todos excepto el OUTPUT que es #4A9EFF con transparencia

Encima de cada bloque (etiqueta):
  "72"    "256"    "128"    "64"    "512"

Debajo de cada bloque (componentes en miniatura, apilados):
  Bloque 1–3:
    [Linear]
    [LayerNorm]
    [GELU]
    [Dropout 20%]
  Bloque 4 (Output):
    [Linear]
    [L2-Norm]   ← importante, en color distinto #FFD166

Las flechas entre bloques son rectas, color #4A9EFF.

En la esquina superior derecha del panel:
  "~400K parámetros entrenables"

En la parte inferior del panel:
  Barra de color continua del mismo ancho que el diagrama:
  [gris neutro]════════════════════════════════════[#4A9EFF intenso]
  "Información del pixel"                      "Embedding abstracto"
```

---

## PANEL B — Detalle de una capa (col 1–5, filas 6–8)

```
TÍTULO: "Anatomía de cada capa oculta"

DIAGRAMA VERTICAL (zoom al Bloque 1):

  Entrada: vector de dim=N
      │
      ▼
  ┌──────────────────────────────┐
  │  Linear (N → 256)            │  fondo #1A3A5C, borde #4A9EFF
  │  y = xW^T + b                │  (ecuación en gris claro)
  └──────────────────────────────┘
      │
      ▼
  ┌──────────────────────────────┐
  │  LayerNorm                   │  fondo #162B1F, borde #44CC88
  │  ŷ = (y - μ) / σ · γ + β   │
  └──────────────────────────────┘
      │
      ▼
  ┌──────────────────────────────┐
  │  GELU                        │  fondo #2A1F0F, borde #FF7B35
  │  GELU(x) = x·Φ(x)           │
  └──────────────────────────────┘
      │
      ▼
  ┌──────────────────────────────┐
  │  Dropout (p = 0.20)          │  fondo #1F1225, borde #B57BFF
  │  Algunos nodos → 0           │
  └──────────────────────────────┘
      │
      ▼
  Salida: vector de dim=256
```

---

## PANEL C — Por qué GELU (col 6–12, filas 6–8)

```
TÍTULO: "GELU vs ReLU — ¿Por qué importa?"

GRÁFICA (ejes visibles, fondo #161B22):
  Eje X: entrada [-3, 3]  |  Eje Y: salida [-0.2, 3]

  Curva ReLU:
    Color #FF4455 (rojo), línea 2px
    Forma: L invertida (cero para x<0, diagonal para x>0)
    Etiqueta a la derecha: "ReLU: max(0, x)"

  Curva GELU:
    Color #FF7B35 (naranja), línea 2.5px
    Forma: suave, ligeramente negativa en [-0.5, 0], crece fluidamente
    Etiqueta a la derecha: "GELU: x·Φ(x)"

  ZONA SOMBREADA en #FF7B3520 (naranja translúcido) de x=-2 a x=0:
    Texto dentro: "GELU mantiene señal
    para activaciones pequeñas"

TABLA comparativa debajo de la gráfica:
  ┌─────────────────┬─────────┬──────────┐
  │  Propiedad      │  ReLU   │   GELU   │
  ├─────────────────┼─────────┼──────────┤
  │  Diferenciable  │    ✗    │    ✓     │
  │  Negativas      │  → 0   │  atenuadas│
  │  Gradiente      │ 0 o 1  │  suave   │
  │  Usado en       │ CNN     │Transformers│
  └─────────────────┴─────────┴──────────┘
```

---

## PROMPT IMAGEN (Slide 04)
```
Technical architecture infographic: TOP section shows horizontal MLP encoder 
diagram with 5 blocks (72→256→128→64→512 dimensions), block width proportional 
to dimension, each internal block shows stacked sub-layers (Linear/LayerNorm/
GELU/Dropout), final block shows L2-Normalize highlighted in gold, data flow 
arrows left to right; BOTTOM LEFT shows vertical zoom into single layer 
(Linear+LayerNorm+GELU+Dropout stacked with equations); BOTTOM RIGHT shows 
GELU vs ReLU comparison graph (red L-shape vs smooth orange curve), shaded 
region showing advantage of GELU for near-zero values; dark background
```

---
---

# SLIDE 05 — EL ESPACIO LATENTE

**Título:** `La Hiperesfera Unitaria: Geometría del Espacio Latente`
**Subtítulo:** `Todos los embeddings viven en la superficie de una esfera de 512 dimensiones`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├────────────────────────┬───────────────────────────────────────┤
│                        │                                        │
│  PANEL A               │  PANEL B                               │
│  La esfera (3D)        │  Por qué normalizar                    │
│                        │                                        │
├────────────────────────┴───────────────────────────────────────┤
│  PANEL C: La similitud coseno como métrica de distancia         │
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — La esfera (col 1–5, filas 2–6)

```
VISUAL CENTRAL: Esfera 3D en perspectiva (simplificada de 512D a 3D)

  La esfera:
    Color de superficie: #1C2228 con transparencia 50%
    Contorno: líneas de latitud/longitud en #30363D
    Radio = 1 (unitaria)

  Sobre la superficie de la esfera: 5 puntos de colores
    🟢 Papa    → punto verde #44CC88 con flecha desde centro
    🔵 Maíz    → punto azul #4A9EFF con flecha desde centro
    🟠 Arveja  → punto naranja #FF7B35 con flecha desde centro
    🟡 Haba    → punto amarillo #FFD166 con flecha desde centro
    ⚪ Pixel sin etiqueta → punto gris con "?" encima

  Las flechas desde el centro a cada punto son los "embeddings".
  Cada flecha está etiquetada: "z_i" (pixel) o "c_k" (prototipo).

  En el centro de la esfera: punto pequeño negro "O" (origen)

  ECUACIÓN en el borde derecho del panel:
    ‖z‖₂ = 1
    (todos los puntos equidistantes del origen)
```

---

## PANEL B — Por qué normalizar (col 6–12, filas 2–6)

```
TÍTULO: "¿Por qué proyectar en una esfera?"

4 CARDS verticales apilados:

CARD 1 — Sin normalización [fondo #1F1218, borde #FF4455]:
  "Vector crudo: z = [3.2, -0.1, 8.7, ...]"
  "La magnitud ‖z‖ varía de pixel a pixel."
  "La distancia mezcla magnitud + dirección."

CARD 2 — Con normalización [fondo #121F17, borde #44CC88]:
  "Vector normalizado: ẑ = z / ‖z‖"
  "‖ẑ‖ = 1 siempre — solo importa la dirección."
  "La distancia = solo el ángulo entre vectores."

CARD 3 — Ventaja matemática [fondo #0F1A2A, borde #4A9EFF]:
  ECUACIÓN grande:
    z_i · c_k = ‖z_i‖ · ‖c_k‖ · cos(θ)
              = 1 · 1 · cos(θ)
              = cos(θ)
  "El producto punto = coseno del ángulo"
  "Similitud limpia, sin escala."

CARD 4 — Interpretación [fondo #1A1A0F, borde #FFD166]:
  ESCALA VISUAL horizontal:
    -1 ←─────────── 0 ───────────→ +1
  "opuesto"     "perpendicular"   "idéntico"
  "Cultivos distintos → ángulo grande → cos pequeño"
  "Cultivos iguales  → ángulo pequeño → cos grande"
```

---

## PANEL C — Similitud coseno (col 1–12, filas 7–8)

```
VISUAL: 3 pares de vectores en la esfera (simplificada a círculo 2D):

PAR 1 — θ pequeño (~10°):
  Dos flechas casi paralelas (color similar).
  cos(10°) ≈ 0.98 → "Alta similitud"
  Texto: "Pixel de papa ↔ Prototipo papa"

PAR 2 — θ mediano (~60°):
  Dos flechas a 60° (colores distintos).
  cos(60°) = 0.50 → "Similitud media"
  Texto: "Pixel de papa ↔ Prototipo maíz"

PAR 3 — θ grande (~150°):
  Dos flechas casi opuestas.
  cos(150°) ≈ -0.87 → "Baja similitud"
  Texto: "Pixel de papa ↔ Prototipo café"

Los 3 pares se muestran en un círculo 2D con fondo #161B22.
Debajo: "La distancia angular define qué tan parecido es un pixel a cada cultivo."
```

---

## PROMPT IMAGEN (Slide 05)
```
Mathematical visualization slide: TOP LEFT shows 3D unit sphere with 5 colored 
embedding points on surface (green=papa, blue=maíz, orange=arveja, yellow=haba, 
grey=unlabeled pixel) each with direction arrows from origin center, equation 
‖z‖₂=1 shown; TOP RIGHT shows 4 stacked explanation cards comparing unnormalized 
vs normalized vectors, cosine similarity derivation z·c=cos(θ), and 
-1 to +1 similarity scale; BOTTOM shows three vector pair examples on 2D 
circle showing small/medium/large angles with cosine values and crop context; 
dark background technical style
```

---
---

# SLIDE 06 — LOS PROTOTIPOS

**Título:** `Los Prototipos: Representantes de Cada Cultivo`
**Subtítulo:** `18 vectores aprendibles en la misma esfera que los embeddings`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├───────────────────────────────────┬────────────────────────────┤
│  PANEL A                          │  PANEL B                   │
│  Esfera con 18 prototipos         │  Evolución durante          │
│                                   │  entrenamiento             │
├───────────────────────────────────┴────────────────────────────┤
│  PANEL C: De embedding a scores — la operación matricial        │
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — Los 18 prototipos en la esfera (col 1–6, filas 2–6)

```
VISUAL: Esfera 3D (igual estilo que Slide 05)

  18 FLECHAS desde el centro, distribuidas en la superficie.
  Cada flecha tiene:
    - Color único por cultivo
    - Etiqueta al final: nombre del cultivo
    - Grosor: 2px

  Cultivoss etiquetados (simplificado a 12 visibles en esta proyección):
    Papa, Maíz, Arveja, Fresa, Haba, Tomate,
    Cebolla, Café, Caña, Plátano, Uchuva, Mora

  Alrededor de cada flecha (prototipo):
    Una nube de 3–5 puntos pequeños del mismo color = pixels de ese cultivo
    (muestra que el prototipo es el "centro" de ese cluster)

  ECUACIÓN en la esquina:
    C ∈ ℝ^{K×d}
    K = 18 cultivos
    d = 512 dimensiones
    ‖c_k‖₂ = 1  ∀k

  NOTA al pie del panel:
    "Los prototipos NO se inicializan con conocimiento de los cultivos.
     Aprenden su posición durante el entrenamiento."
```

---

## PANEL B — Evolución durante el entrenamiento (col 7–12, filas 2–6)

```
TÍTULO: "Cómo evolucionan los prototipos"

3 MINI-ESFERAS en fila horizontal, mostrando epochs distintas:

ESFERA 1 (Época 0):
  Etiqueta: "Inicio"
  18 flechas en posiciones aleatorias — desorden total.
  Color de las flechas: todas mezcladas sin patrón.
  Puntos de pixels: dispersos por toda la esfera.

ESFERA 2 (Época 100):
  Etiqueta: "Entrenamiento medio"
  Las flechas comienzan a agruparse con sus pixels.
  Se ven 3–4 clusters emergentes, pero aún superpuestos.

ESFERA 3 (Época 500):
  Etiqueta: "Entrenamiento completo"
  Cada flecha-prototipo está claramente separada.
  Los pixels de cada cultivo están agrupados alrededor de su prototipo.
  Los 18 prototipos cubren todo el espacio esférico uniformemente.

FLECHA de progreso debajo de las 3 esferas:
  ───────────────────────────────────────────→
  Época 0                                 Época 500

TEXTO debajo:
  "500 épocas | 14.2 minutos en GPU CUDA"
```

---

## PANEL C — De embedding a scores (col 1–12, filas 7–8)

```
VISUAL: Operación matricial simplificada

IZQUIERDA: "Embedding del pixel"
  Vector z_i: columna de 512 valores (visualizado como barra vertical azul)
  Etiqueta: "z_i ∈ ℝ⁵¹²"

CENTRO: "Matriz de prototipos"
  Rectángulo C^T de 512 × 18:
    Cada columna = un prototipo (coloreada con el color del cultivo)
    Etiqueta: "C^T ∈ ℝ^{512×18}"
    Operación: "×  (producto matricial)"

DERECHA: "Scores de similitud"
  Vector de 18 valores (barra horizontal):
  [0.89] [0.41] [0.12] [0.67] [0.03] ...
  El valor más alto (Papa = 0.89) resaltado en verde.
  Etiqueta: "s ∈ ℝ¹⁸"

ECUACIÓN completa debajo:
  s = z_i · C^T    donde s_k = z_i · c_k = cos(θ_{ik})

FLECHA continua que conecta los tres elementos de izquierda a derecha.
```

---

## PROMPT IMAGEN (Slide 06)
```
Prototype visualization infographic: TOP LEFT shows unit sphere with 18 labeled 
prototype arrows (one per crop: papa, maíz, arveja, fresa etc.) plus small pixel 
point clouds clustered around each prototype, equation C∈R^(18×512) shown; 
TOP RIGHT shows three mini-spheres side by side showing training evolution 
(epoch 0: random prototypes, epoch 100: emerging clusters, epoch 500: clean 
separated clusters with pixels clustered around prototypes); BOTTOM shows 
matrix multiplication diagram: blue embedding vector × prototype matrix → 
18 similarity scores bar, highest score highlighted green; dark technical style
```

---
---

# SLIDE 07 — EL PROBLEMA DE TRANSPORTE ÓPTIMO

**Título:** `Transporte Óptimo: Asignar Pixels Respetando Proporciones`
**Subtítulo:** `El puente entre la señal débil (EVA) y las predicciones individuales`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├──────────────────────┬─────────────────────────────────────────┤
│  PANEL A             │  PANEL B                                 │
│  El problema         │  La formulación matemática               │
│  (grafo bipartito)   │                                          │
├──────────────────────┴─────────────────────────────────────────┤
│  PANEL C: Analogía de la urna — cerrar el ciclo con Slide 01   │
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — Grafo bipartito (col 1–6, filas 2–6)

```
VISUAL: Grafo bipartito vertical

COLUMNA IZQUIERDA — Pixels (fuente):
  8 círculos apilados, todos grises:
    p₁  p₂  p₃  p₄  p₅  p₆  p₇  ... pₙ
  Etiqueta izquierda: "N pixels del bag"

COLUMNA DERECHA — Prototipos (destino):
  5 rectángulos apilados (cultivos simplificados a 5):
    [Papa   ████████████ 43%]
    [Maíz   ████          18%]
    [Arveja ██             9%]
    [Haba   █              6%]
    [Otros  ██████        24%]
  La barra de cada rectángulo indica su "capacidad" (cuota EVA).
  Etiqueta derecha: "18 prototipos con cuota EVA"

ARISTAS entre los dos lados:
  Cada pixel conecta a TODOS los prototipos.
  El GROSOR de cada arista = similitud coseno s_{ik}
  Color: gradiente de gris (delgada) a #4A9EFF (gruesa para alta similitud)

  Ejemplo visible:
    p₃ → Papa: arista gruesa (alta similitud)
    p₃ → Otros: arista muy delgada (baja similitud)

LEYENDA en la esquina inferior:
  ─── delgada: baja similitud
  ═══ gruesa:  alta similitud
  (Grosor = s_{ik} = cos(θ_{ik}))

TEXTO DE RESTRICCIÓN (en rojo #FF4455, borde de la columna derecha):
  "⚠ Restricción: el flujo total a Papa = 43%"
  "⚠ Restricción: el flujo total a Maíz = 18%"
  "⚠ ..."
```

---

## PANEL B — Formulación matemática (col 7–12, filas 2–6)

```
TÍTULO: "La optimización"

BLOQUE ECUACIÓN (fondo #161B22, borde #FFD166):
  Problema de transporte óptimo:

  max_{Q} Σᵢⱼ Qᵢⱼ · sᵢⱼ
  
  sujeto a:
    Σⱼ Qᵢⱼ = 1/N    ∀i  (cada pixel asigna toda su masa)
    Σᵢ Qᵢⱼ = wⱼ     ∀j  (cada prototipo recibe su cuota EVA)
    Qᵢⱼ ≥ 0         ∀i,j

DESGLOSE debajo de la ecuación con 3 cards:

CARD 1 (azul): "Qᵢⱼ"
  "Cantidad de pixel i asignada al prototipo j"
  "Es la 'etiqueta suave' que buscamos"

CARD 2 (naranja): "sᵢⱼ"
  "Similitud coseno entre pixel i y prototipo j"
  "Maximizamos: pixels similares van a prototipos similares"

CARD 3 (verde): "wⱼ"
  "Cuota EVA del cultivo j en este municipio"
  "La restricción que incorpora la señal débil"

RESULTADO al pie:
  "Q* ∈ ℝ^{N×18} — la asignación óptima de N pixels a 18 cultivos"
```

---

## PANEL C — Analogía de cierre (col 1–12, filas 7–8)

```
VISUAL: Referencia directa al Slide 01 (urna)

Izquierda: la urna del Slide 01 (bolas coloreadas, proporción conocida)
Flecha grande →
Centro: "Transporte Óptimo"
  "Asignar cada bola al color correcto
   manteniendo las proporciones exactas"
Flecha grande →
Derecha: la urna ABIERTA — cada bola tiene ahora una etiqueta de color
  "¡Urna resuelta!"

TEXTO bajo la secuencia:
  "El Optimal Transport es el mecanismo que 'abre la urna' del Slide 01."
```

---

## PROMPT IMAGEN (Slide 07)
```
Optimal transport infographic: LEFT shows bipartite graph with pixel nodes 
(grey circles) on left connected by lines of varying thickness (cosine 
similarity) to 5 crop prototype rectangles (papa 43%, maíz 18%, arveja 9% etc.) 
with capacity bars on right, red warning annotations on prototype capacity 
constraints; RIGHT shows mathematical formulation box with max objective and 
constraints (row sums = 1/N, column sums = EVA proportion w_j), three 
explanation cards for Q_ij, s_ij, w_j; BOTTOM shows urn analogy callback 
"transport optimal opens the urn"; dark background
```

---
---

# SLIDE 08 — SINKHORN-KNOPP PASO A PASO

**Título:** `Sinkhorn-Knopp: El Algoritmo que Resuelve el Transporte`
**Subtítulo:** `5 iteraciones de normalización alternada → asignación óptima`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PANEL CENTRAL: Evolución de la matriz Q en 5 iteraciones        │
│                                                                  │
├──────────────────────────────────┬─────────────────────────────┤
│  PANEL B: El algoritmo en código  │  PANEL C: Interpretación    │
└──────────────────────────────────┴─────────────────────────────┘
```

---

## PANEL CENTRAL — Evolución de la matriz (col 1–12, filas 2–6)

```
VISUAL: 6 mini-matrices de calor en fila horizontal

MATRIZ 0 (Inicio):
  Etiqueta: "M — Scores raw"
  Heatmap N×18: colores irregulares, sin patrón.
  Sumas de filas variables (barras a la derecha, desiguales).
  Sumas de columnas variables (barras abajo, no coinciden con EVA).
  Color dominante: mezcla de azul claro y azul oscuro.

FLECHA con "Paso 1: Normalizar filas" →

MATRIZ 1 (Post normalización de filas):
  Etiqueta: "Iter 1a — Filas normalizadas"
  Cada fila suma ahora exactamente 1/N.
  Barras de filas a la derecha: TODAS IGUALES (línea horizontal uniforme).
  Barras de columnas abajo: AÚN desiguales.

FLECHA con "Paso 2: Normalizar columnas" →

MATRIZ 2 (Post normalización de columnas):
  Etiqueta: "Iter 1b — Columnas normalizadas"
  Cada columna suma su cuota EVA wⱼ.
  Barras de columnas abajo: ahora COINCIDEN con la barra EVA.
  Barras de filas: levemente perturbadas.

FLECHA con "Repetir..." →

MATRIZ 3 (Iter 2):
  Etiqueta: "Iter 2..."
  Las perturbaciones son menores.

FLECHA →

MATRIZ 4 (Iter 5 — Final):
  Etiqueta: "Q* — Converged"
  Fondo: bordes más definidos, estructura clara.
  Barras de filas: uniformes. Barras de columnas: exactas a EVA.
  BORDE en #44CC88 (verde) indicando éxito.

INDICADOR de convergencia bajo las matrices:
  Curva decreciente: "Cambio entre iteraciones" → se acerca a 0.
```

---

## PANEL B — El algoritmo (col 1–6, filas 7–8)

```
CÓDIGO (fondo #0D1117, borde #30363D, fuente JetBrains Mono):

  # Inicialización
  M = exp(scores / ε)     # scores pixel×cultivo

  # 5 iteraciones de normalización
  for _ in range(5):
      # Paso 1: normalizar filas
      M = M / M.sum(1, keepdim=True)
      # Paso 2: normalizar columnas → cuotas EVA
      M = M / M.sum(0, keepdim=True) * w_eva

  Q = M   # Código de asignación óptima

  # ε = 0.022 (regularización Sinkhorn)
  # w_eva = proporciones EVA del municipio

Los comentarios están en color #44CC88 (verde).
Las palabras clave (for, in, range) en #FF7B35 (naranja).
```

---

## PANEL C — ¿Qué hace ε? (col 7–12, filas 7–8)

```
TÍTULO: "El papel de ε (epsilon de regularización)"

COMPARACIÓN visual: 3 matrices pequeñas en fila

  ε = 0.001 (muy bajo):
    Matriz Q: muy polarizada, valores 0 o 1 (asignación dura).
    Texto: "Asignación rígida
             Sigue fielmente el prior EVA"

  ε = 0.022 (óptimo):
    Matriz Q: valores suaves [0.0, 1.0].
    Texto: "Balance óptimo
             (valor encontrado por Optuna)"

  ε = 0.5 (muy alto):
    Matriz Q: muy uniforme, casi constante por fila.
    Texto: "Asignación blanda
             Ignora el prior EVA"

GRADIENTE horizontal:
  [Duro ←────────────────────────────→ Blando]
  [ε pequeño]                      [ε grande]

FLECHA que señala el ε=0.022: "← Valor optimizado"
```

---

## PROMPT IMAGEN (Slide 08)
```
Sinkhorn-Knopp algorithm infographic: TOP SECTION shows 5 sequential N×18 
heatmap matrices from left to right: initial scores matrix (irregular), after 
row normalization (equal row sums shown as bars right), after column 
normalization (column sums match EVA proportions shown as bars bottom), 
intermediate iterations, final converged Q matrix (green border, clean 
structure), arrows labeled "Normalizar filas" and "Normalizar columnas" between 
steps; BOTTOM LEFT shows pseudocode in monospace font; BOTTOM RIGHT shows 
epsilon effect comparison (low/optimal/high epsilon → hard/soft assignments); 
dark background
```

---
---

# SLIDE 09 — EL CÓDIGO Q: LA ETIQUETA SUAVE

**Título:** `El Código Q: La Etiqueta Suave por Pixel`
**Subtítulo:** `Q no dice "este pixel es papa" — dice cuánto de cada cultivo debe ser`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├────────────────────────┬───────────────────────────────────────┤
│  PANEL A               │  PANEL B                              │
│  Q visualizado         │  Interpretación de Q[i]               │
├────────────────────────┴───────────────────────────────────────┤
│  PANEL C: Q vs softmax crudo — ¿cuál es la diferencia?         │
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — La matriz Q (col 1–5, filas 2–6)

```
VISUAL: Heatmap N×18 de la matriz Q final (después de Sinkhorn)

  Eje Y: "Pixels del bag" (p₁ a pₙ)
  Eje X: los 18 cultivos (Papa, Maíz, Arveja, ...)

  Colores: paleta viridis inversa (azul oscuro = 0, amarillo = alto)

  ZOOM a 3 filas representativas (líneas de selección en blanco):
    Fila 12: alta concentración en "Papa" (una celda muy amarilla)
    Fila 47: distribución más repartida entre Papa y Arveja
    Fila 89: alta concentración en "Maíz"

  Suma de cada fila visible en barra lateral derecha: todas iguales = 1/N
  Suma de cada columna visible en barra inferior: = wⱼ (cuota EVA)

  LEYENDA de color en la esquina.
  TÍTULO del heatmap: "Q ∈ ℝ^{N×18}"
```

---

## PANEL B — Interpretación de Q[i] (col 6–12, filas 2–6)

```
TÍTULO: "¿Qué significa Q[i] para un pixel específico?"

Para cada uno de los 3 pixels zoom del Panel A:

┌─── PIXEL 12 ─────────────────────────────────────────┐
│  Q[12] = [0.81, 0.06, 0.05, 0.02, ...]               │
│  Barras horizontales:                                  │
│    Papa  ████████████████ 81%                          │
│    Maíz  █               6%                            │
│    Arveja█               5%                            │
│    ...   ...             8%                            │
│  Interpretación: "Asignado principalmente a Papa"     │
└───────────────────────────────────────────────────────┘

┌─── PIXEL 47 ─────────────────────────────────────────┐
│  Q[47] = [0.42, 0.04, 0.38, 0.07, ...]               │
│    Papa  ████████        42%                           │
│    Arveja███████         38%                           │
│    Otros               20%                            │
│  Interpretación: "Ambiguo — condiciones similares"    │
└───────────────────────────────────────────────────────┘

┌─── PIXEL 89 ─────────────────────────────────────────┐
│  Q[89] = [0.03, 0.88, 0.02, ...]                     │
│    Maíz  ████████████████████ 88%                    │
│    Papa  ▌                    3%                     │
│  Interpretación: "Claramente asignado a Maíz"        │
└───────────────────────────────────────────────────────┘

NOTA al pie:
  "Q[i] actúa como la 'etiqueta suave' que el modelo aprenderá a reproducir."
  "No es una predicción — es el objetivo de entrenamiento."
```

---

## PANEL C — Q vs softmax crudo (col 1–12, filas 7–8)

```
TÍTULO: "¿Por qué Sinkhorn y no solo softmax?"

COMPARACIÓN en dos columnas:

COLUMNA IZQUIERDA — Softmax crudo (sin Sinkhorn):
  Mini-barras de 5 pixels del mismo bag:
    p₁: Papa 94%, Maíz 3%...
    p₂: Papa 88%, Maíz 9%...
    p₃: Papa 91%, Maíz 7%...
    p₄: Papa 89%, Maíz 8%...
    p₅: Papa 95%, Maíz 3%...
  Suma de "Papa" en el bag: 91%  (MUY SUPERIOR al 43% del EVA)
  Etiqueta: "❌ Viola la restricción EVA"
  Borde: #FF4455

COLUMNA DERECHA — Código Q (con Sinkhorn):
  Mini-barras del mismo bag:
    p₁: Papa 81%, Arveja 15%...
    p₂: Papa 76%, Maíz 18%...
    p₃: Maíz 62%, Papa 28%...
    p₄: Arveja 58%, Papa 37%...
    p₅: Maíz 71%, Papa 21%...
  Suma de "Papa" en el bag: 43%  (EXACTA al EVA)
  Etiqueta: "✓ Respeta la restricción EVA"
  Borde: #44CC88

TEXTO CENTRAL ENTRE COLUMNAS:
  "Sinkhorn proyecta las predicciones al espacio que satisface
   las proporciones del municipio."
```

---

## PROMPT IMAGEN (Slide 09)
```
Soft label visualization infographic: LEFT shows N×18 heatmap Q matrix with 
viridis coloring (dark=0, yellow=high probability), three pixel rows highlighted 
with selection brackets, row sum bars all equal on right, column sum bars 
matching EVA proportions below; RIGHT shows three interpretation panels for 
selected pixels (pixel 12: 81% papa bar chart, pixel 47: ambiguous 42%papa/38%
arveja, pixel 89: 88% maíz); BOTTOM shows side-by-side comparison: raw softmax 
violates EVA proportions (bag shows 91% papa, red border) vs Sinkhorn-Q 
satisfies EVA exactly (43% papa, green border); dark background
```

---
---

# SLIDE 10 — DATA AUGMENTATION

**Título:** `Dos Vistas del Mismo Pixel`
**Subtítulo:** `El mismo terreno, dos mediciones ligeramente distintas`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PANEL CENTRAL: Bifurcación pixel → X_s + X_t                   │
│                                                                  │
├──────────────────────────────────┬─────────────────────────────┤
│  PANEL B: Reglas de augmentación  │  PANEL C: ¿Por qué funciona?│
└──────────────────────────────────┴─────────────────────────────┘
```

---

## PANEL CENTRAL — Bifurcación (col 1–12, filas 2–5)

```
VISUAL: Diagrama de bifurcación

CENTRO:
  Pixel original con su vector de 72 features
  (barra horizontal dividida en 4 segmentos de colores por grupo)
  Etiqueta: "x — vector original"

BIFURCACIÓN: la barra se divide en dos ramas (V invertida)

RAMA IZQUIERDA — X_s (Vista Source):
  El mismo vector pero con modificaciones:
  - Segmento CLIMA: barras ligeramente distintas (+ruido), algunos valores grises (dropout)
  - Segmento SATÉLITE: barras modificadas con ruido
  - Segmento SUELO: IDÉNTICO al original (mismo color exacto)
  - Segmento TOPO: IDÉNTICO al original

  LEYENDAS sobre cada sección:
    Clima/Satélite: "+ ruido σ=0.033 + dropout p=0.20"
    Suelo/Topo: "sin cambio (variables estables)"

  Etiqueta: "X_s — Vista Source" (color #B57BFF)

RAMA DERECHA — X_t (Vista Target):
  Igual pero con diferentes valores de ruido/dropout (posiciones distintas grises):
  Etiqueta: "X_t — Vista Target" (color #B57BFF, tono diferente)

TEXTO CENTRAL entre las ramas:
  "Misma identidad geográfica
   Perturbaciones diferentes
   → El modelo debe ser CONSISTENTE entre vistas"
```

---

## PANEL B — Reglas de augmentación (col 1–6, filas 6–8)

```
TÍTULO: "Reglas de augmentación diferenciada"

TABLA:

┌──────────────────┬─────────────────────────────────┬──────────────┐
│ Grupo de feature │ Augmentación                    │ ¿Por qué?    │
├──────────────────┼─────────────────────────────────┼──────────────┤
│ Clima            │ Ruido gaussiano σ=0.033          │ Medición     │
│ (18 features)    │ + Dropout p=0.20                 │ variable     │
├──────────────────┼─────────────────────────────────┼──────────────┤
│ Satélite S2      │ Ruido gaussiano σ=0.033          │ Nubes,       │
│ (21 features)    │ + Dropout p=0.20                 │ variación    │
│                  │ (simula días distintos)           │ temporal     │
├──────────────────┼─────────────────────────────────┼──────────────┤
│ Suelo            │ ─── Sin augmentación ───         │ No cambia    │
│ (12 features)    │                                  │ con el tiempo│
├──────────────────┼─────────────────────────────────┼──────────────┤
│ Topografía       │ ─── Sin augmentación ───         │ No cambia    │
│ (21 features)    │                                  │ con el tiempo│
└──────────────────┴─────────────────────────────────┴──────────────┘
```

---

## PANEL C — Por qué funciona (col 7–12, filas 6–8)

```
TÍTULO: "La intuición de la consistencia"

DIAGRAMA:

  [Papa en día lluvioso]  →  Encoder  →  Embedding A
                                               |
                              ← similitud alta →
                                               |
  [Papa en día soleado]   →  Encoder  →  Embedding B

  "Si el terreno es papa tanto en día nublado como en día claro,
   ambos embeddings deben apuntar en la misma dirección."

CONTRASTE en un segundo nivel:

  [Papa]  →  Embedding A  ←── diferente ───  Embedding B ←── [Maíz]

  "Perturbaciones del mismo pixel deben ser similares."
  "Pixels de cultivos distintos deben ser diferentes."

TEXTO FINAL:
  "Augmentation = crear pares de entrenamiento sin necesitar etiquetas."
  (Técnica tomada de SwAV, Caron et al. 2020, adaptada para features tabulares)
```

---

## PROMPT IMAGEN (Slide 10)
```
Data augmentation infographic: CENTER shows original 72-feature pixel vector 
(4-color segmented horizontal bar) splitting into two branches (V-shape): 
LEFT branch X_s shows climate and satellite features with noise (slight color 
variation) and some features greyed out (dropout), soil and topography segments 
identical to original; RIGHT branch X_t shows different dropout positions; 
label "same geographic identity, different perturbations"; BOTTOM LEFT shows 
augmentation rules table (climate/satellite: noise+dropout, soil/topo: no 
augmentation with reason column); BOTTOM RIGHT shows consistency intuition 
diagram (rainy day papa ↔ sunny day papa should embed similarly); dark background
```

---
---

# SLIDE 11 — EL SWAP LOSS

**Título:** `Swap Loss: Predecir el Código de la Vista Contraria`
**Subtítulo:** `Si ambas vistas muestran el mismo terreno, sus predicciones deben coincidir`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PANEL CENTRAL: Diagrama completo del swap loss                  │
│                                                                  │
├──────────────────────┬──────────────────────────────────────────┤
│  PANEL B             │  PANEL C                                  │
│  La ecuación         │  Intuición: ¿por qué cruzar?              │
└──────────────────────┴──────────────────────────────────────────┘
```

---

## PANEL CENTRAL — Diagrama del swap loss (col 1–12, filas 2–5)

```
VISUAL: Diagrama de flujo de dos caminos paralelos

══════════════════════ CAMINO SUPERIOR (Vista Source) ══════════════════════
X_s ──→ [Encoder] ──→ z_s ──→ [Prototipos] ──→ scores_s ──→ [softmax/τ] ──→ P_s
                                                     │
                                                     └──→ [Sinkhorn / w_EVA] ──→ Q_s

══════════════════════ CAMINO INFERIOR (Vista Target) ══════════════════════
X_t ──→ [Encoder] ──→ z_t ──→ [Prototipos] ──→ scores_t ──→ [softmax/τ] ──→ P_t
                                                     │
                                                     └──→ [Sinkhorn / w_EVA] ──→ Q_t

Nota visual: el bloque [Encoder] y [Prototipos] son el MISMO bloque
compartido entre ambos caminos (línea punteada vertical entre ellos,
etiqueta "pesos compartidos").

═══════════════════════ FLECHAS CRUZADAS (EL SWAP) ══════════════════════
          P_s ──────────────────────╲
                                     ╲── CE(P_s, Q_t) ──→ ℒ₁
                                     ╱
          P_t ──────────────────────╱
                          ╲
                           ╲── CE(P_t, Q_s) ──→ ℒ₂

Las flechas cruzadas se muestran en ROJO BRILLANTE #FF4455 con 3px de grosor.
Los bloques P y Q se destacan visualmente:
  P (predicciones softmax): color #4A9EFF (azul)
  Q (códigos Sinkhorn): color #FFD166 (amarillo)

RESULTADO al pie:
  ℒ_swap = (ℒ₁ + ℒ₂) / 2
```

---

## PANEL B — La ecuación (col 1–5, filas 6–8)

```
FONDO: #161B22

ECUACIÓN COMPLETA (renderizada, grande):

  ℒ_swap = -1/2 Σᵢ [ Q_t(i)ᵀ log P_s(i)
                    + Q_s(i)ᵀ log P_t(i) ]

DESGLOSE por línea con anotación:
  Q_t(i)ᵀ log P_s(i):
    → "Código de t como objetivo, predicción de s"
    → "Cross-entropy de P_s respecto a Q_t"
  
  Q_s(i)ᵀ log P_t(i):
    → "Código de s como objetivo, predicción de t"
    → "Cross-entropy de P_t respecto a Q_s"

NOTA al pie:
  "Si P_s ≈ Q_t y P_t ≈ Q_s → pérdida ≈ 0
   El modelo 'sabe' el cultivo con consistencia entre vistas"
```

---

## PANEL C — ¿Por qué cruzar? (col 6–12, filas 6–8)

```
TÍTULO: "¿Por qué no comparar P_s con Q_s directamente?"

COMPARACIÓN:

❌ Sin cruce (P_s vs Q_s):
  "El modelo podría hacer trampa:
   colapsar todo a un solo cultivo
   y obtener pérdida baja sin aprender."
   (Diagrama: todas las flechas al mismo prototipo)

✓ Con cruce (P_s vs Q_t):
  "Para que P_s prediga correctamente Q_t,
   debe entender el cultivo desde features distintas.
   No puede hacer trampa copiando."
   (Diagrama: las dos vistas deben concordar en la predicción)

TEXTO FINAL:
  "El swap es el mecanismo anti-atajo:
   obliga al encoder a capturar información
   robusta e invariante a las perturbaciones."
```

---

## PROMPT IMAGEN (Slide 11)
```
Swap loss diagram infographic: MAIN SECTION shows two parallel pathways: 
TOP PATH X_s→Encoder→z_s→Prototypes→scores_s→softmax→P_s and 
→Sinkhorn→Q_s; BOTTOM PATH X_t→same shared Encoder/Prototypes→P_t and Q_t; 
CROSSED RED ARROWS between P_s→CE(Ps,Qt)→L1 and P_t→CE(Pt,Qs)→L2; 
P blocks colored blue, Q blocks colored yellow, shared weights indicated 
by dashed vertical line; BOTTOM LEFT shows full loss equation; 
BOTTOM RIGHT shows why-cross explanation with collapse prevention diagram; 
dark background
```

---
---

# SLIDE 12 — REGULARIZACIÓN KOLEO

**Título:** `KoLeo: Evitar el Colapso de Prototipos`
**Subtítulo:** `Forzar que los 18 prototipos ocupen todo el espacio esférico`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├────────────────────────┬───────────────────────────────────────┤
│  PANEL A               │  PANEL B                              │
│  Antes/Después KoLeo   │  La ecuación y la intuición           │
├────────────────────────┴───────────────────────────────────────┤
│  PANEL C: KoLeo en el contexto de la pérdida total             │
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — Antes y después (col 1–6, filas 2–6)

```
DOS ESFERAS LADO A LADO:

ESFERA IZQUIERDA — Sin KoLeo (colapso):
  Título: "❌ Sin KoLeo — Colapso"
  Borde: #FF4455

  Todos los prototipos aglomerados en el mismo sector de la esfera.
  Flechas apuntando en direcciones muy similares.
  La mitad inferior de la esfera está completamente vacía.
  
  Efecto: "El modelo siempre predice los mismos 2–3 cultivos"
  "Los otros 15 prototipos son redundantes"

ESFERA DERECHA — Con KoLeo (distribuido):
  Título: "✓ Con KoLeo — Distribución uniforme"
  Borde: #44CC88

  Los 18 prototipos distribuidos uniformemente por toda la superficie.
  Cada uno apuntando en una dirección distinta.
  Flechas de repulsión animadas (→←) entre prototipos adyacentes.
  
  Efecto: "Cada uno de los 18 cultivos tiene su propio 'espacio'"
  "El modelo puede predecir cualquiera de los 18 cultivos"

ETIQUETAS de distancia en la esfera derecha:
  d_min entre prototipos adyacentes marcada con "d_min ↑"
  "KoLeo maximiza la distancia mínima entre prototipos"
```

---

## PANEL B — La ecuación e intuición (col 7–12, filas 2–6)

```
ECUACIÓN (fondo #161B22, borde #FFD166):

  ℒ_KoLeo = -(1/K) Σₖ log min_{k'≠k} ‖cₖ - cₖ'‖₂

ANOTACIONES de la ecuación:
  K = 18   (número de prototipos)
  cₖ       (vector del prototipo k)
  min_{k'≠k} ‖cₖ - cₖ'‖  (distancia al prototipo más cercano)

INTERPRETACIÓN:
  "Si dos prototipos están muy cerca: ‖cₖ - cₖ'‖ ≈ 0"
  "→ log(0) → -∞ → pérdida muy grande"
  "→ El modelo aprende a separarlos"

DIAGRAMA de la función log(x):
  Curva log(x): crece lentamente para x grande, cae a -∞ para x→0
  Región marcada x≈0: "zona de penalización severa"
  Flecha: "‖cₖ - cₖ'‖ pequeño → penalización grande"

PARÁMETRO:
  λ_KoLeo = 0.214   (peso en la pérdida total — optimizado con Optuna)
```

---

## PANEL C — La pérdida total (col 1–12, filas 7–8)

```
VISUAL: Ecuación de pérdida total en formato grande y claro

  ℒ_total = ℒ_swap + λ · ℒ_KoLeo

Con desglose visual:

  ┌─────────────────────────────┐   ┌────────────────────────────┐
  │        ℒ_swap               │   │    λ · ℒ_KoLeo             │
  │  Consistencia entre vistas  │ + │  Diversidad de prototipos   │
  │  (señal principal)          │   │  (regularización)           │
  │  → Aprende qué es cada      │   │  → Evita que el modelo     │
  │    cultivo                  │   │    colapse a pocos cultivos │
  └─────────────────────────────┘   └────────────────────────────┘

  λ = 0.214  (λ demasiado alto → prototipos dispersos sin semántica)
             (λ demasiado bajo → colapso)

BARRA de balance:
  [Solo swap]────────────[Balance óptimo λ=0.214]────────────[Solo KoLeo]
      Colapso potencial              ↑                       Sin semántica
```

---

## PROMPT IMAGEN (Slide 12)
```
KoLeo regularization infographic: TOP LEFT shows two sphere comparisons: 
LEFT sphere shows prototype collapse (all 18 arrows clustered in one hemisphere, 
half sphere empty, red border, label "sin KoLeo"); RIGHT sphere shows evenly 
distributed prototypes across full surface with repulsion arrows between adjacent 
prototypes, green border, label "con KoLeo"; TOP RIGHT shows KoLeo equation with 
log(min distance) annotation and log curve graph showing severe penalty near zero; 
BOTTOM shows total loss equation split box showing L_swap + lambda*L_KoLeo with 
descriptions and balance bar; dark background
```

---
---

# SLIDE 13 — EL BUCLE DE ENTRENAMIENTO COMPLETO

**Título:** `El Ciclo Completo: Una Iteración de Entrenamiento`
**Subtítulo:** `Integrando encoder, prototipos, Sinkhorn, swap loss y KoLeo`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DIAGRAMA CENTRAL: Bucle completo de entrenamiento              │
│                    (ocupa 80% del slide)                         │
│                                                                  │
├──────────────────────────────────┬─────────────────────────────┤
│  PANEL B: Curva de entrenamiento  │  PANEL C: Hiperparámetros   │
└──────────────────────────────────┴─────────────────────────────┘
```

---

## DIAGRAMA CENTRAL — El bucle completo (col 1–12, filas 2–6)

```
VISUAL: Diagrama de flujo completo con todas las piezas de slides anteriores

Organizado en 3 filas horizontales:

FILA 1 (DATOS):
  [Bag municipio] → [Pixel x] → [Augment] → X_s  //  X_t

FILA 2 (MODELO — caminos paralelos):
  X_s → [Encoder] → z_s → [C (prototipos)] → s_s → [softmax/τ] → P_s
                                                  → [Sinkhorn/w] → Q_s
  X_t → [Encoder] → z_t → [C (prototipos)] → s_t → [softmax/τ] → P_t
                                                  → [Sinkhorn/w] → Q_t
  (Encoder y C son bloques compartidos con línea de unión)

FILA 3 (PÉRDIDAS):
  P_s ─╮                         ╭─ Q_t
        ├→ CE(P_s, Q_t) = ℒ₁    │
  P_t ─╯                         ╰─ Q_s
        ╰→ CE(P_t, Q_s) = ℒ₂

  [C (prototipos)] → KoLeo(C) = ℒ₃

  [ℒ_total = ℒ₁ + ℒ₂ + λℒ₃]

FILA 4 (GRADIENTE — flecha de retorno):
  ℒ_total → [∂ℒ/∂θ] → BACKPROP (flecha roja grande que sube de vuelta)
                                    ↑
                             [Encoder + Prototipos]
                             "Parámetros actualizados"

NUMERACIÓN CIRCULAR en cada bloque (1, 2, 3...):
  Permite seguir el flujo en el orden correcto.

COLORES DE BLOQUES (consistentes con slides anteriores):
  Encoder:      #4A9EFF
  Prototipos C: #FF7B35
  Sinkhorn:     #FFD166
  Swap Loss:    #FF4455
  KoLeo:        #B57BFF
  Augmentation: #B57BFF20
  Backprop:     flecha #44CC88
```

---

## PANEL B — Curva de entrenamiento (col 1–6, filas 7–8)

```
GRÁFICA dual (dos ejes Y):

Eje Y izquierdo (azul): "ℒ_swap (train loss)"
  Curva que baja de ~3.5 a ~0.8 en 500 épocas
  Forma suave con pequeñas oscilaciones

Eje Y derecho (naranja): "KL divergencia (valid)"
  Curva que baja de ~0.25 a ~0.09 en 500 épocas

Eje X: "Época (de 1 a 500)"

Línea vertical punteada en época ~50: "Warmup terminado"
Estrella en la época de mejor validación.

TEXTO debajo:
  "14.2 min entrenamiento | GPU CUDA | 500 épocas"
```

---

## PANEL C — Hiperparámetros clave (col 7–12, filas 7–8)

```
TABLA compacta:

┌──────────────────┬──────────┬───────────────────────────────┐
│  Hiperparámetro  │  Óptimo  │  Efecto                       │
├──────────────────┼──────────┼───────────────────────────────┤
│  τ (temperatura) │  0.0497  │  Nitidez de predicciones      │
│  ε (Sinkhorn)    │  0.0224  │  Fidelidad al prior EVA       │
│  λ (KoLeo)       │  0.214   │  Diversidad de prototipos     │
│  σ (ruido aug)   │  0.033   │  Intensidad perturbación      │
│  p_drop (aug)    │  0.204   │  Dropout en augmentación      │
│  LR_init         │  0.00116 │  Tasa de aprendizaje          │
│  emb_dim         │  512     │  Dimensión del embedding      │
└──────────────────┴──────────┴───────────────────────────────┘

NOTA:
  "Optimizados con Optuna — búsqueda bayesiana — 100 trials"
```

---

## PROMPT IMAGEN (Slide 13)
```
Complete training loop infographic: MAIN SECTION (80% of slide) shows full 
data flow diagram in 4 rows: ROW 1 data (bag→pixel→augment→Xs/Xt); ROW 2 
model parallel paths (Xs/Xt→shared encoder→shared prototypes→softmax+Sinkhorn 
→Ps/Qt and Pt/Qs); ROW 3 losses (crossed swap arrows CE(Ps,Qt)+CE(Pt,Qs), 
KoLeo on prototypes, total loss box); ROW 4 green backpropagation arrow 
returning to encoder/prototypes; blocks color-coded (blue encoder, orange 
prototypes, yellow Sinkhorn, red loss); BOTTOM LEFT dual-axis training curve 
(loss and KL validation over 500 epochs); BOTTOM RIGHT hyperparameter table 7 
rows; dark background
```

---
---

# SLIDE 14 — EVALUACIÓN: ¿CÓMO MEDIR SIN ETIQUETAS REALES?

**Título:** `Evaluación del Modelo`
**Subtítulo:** `Tres métricas para validar sin etiquetas por pixel`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├─────────────────┬──────────────────────┬────────────────────────┤
│  MÉTRICA 1      │  MÉTRICA 2           │  MÉTRICA 3             │
│  KL Divergencia │  Top-K Accuracy      │  Matriz de confusión   │
│  (LLP nativa)   │  (ground truth UPRA) │  (Top-K por clase)     │
└─────────────────┴──────────────────────┴────────────────────────┘
```

---

## PANEL MÉTRICA 1 — KL Divergencia (col 1–4, filas 2–8)

```
TÍTULO: "KL Divergencia Municipal"
SUBTÍTULO: "¿Cuán bien reproducimos las proporciones EVA?"

ECUACIÓN:
  KL(w_EVA || ŷ_bag) = Σⱼ wⱼ · log(wⱼ / ŷⱼ)
  donde ŷⱼ = (1/N) Σᵢ∈bag P_ij

GRÁFICA: barras horizontales por municipio (ordenadas de menor a mayor KL)
  La mayoría de barras son cortas (azul #4A9EFF) → bien predichos.
  Algunas barras son largas (naranja) → municipios difíciles.
  Línea de referencia vertical: KL promedio.

ESCALA: 0 a 0.4

INTERPRETACIÓN:
  KL = 0:   "Predicción perfecta — proporciones exactas"
  KL > 0.2: "Municipio difícil — cultivos poco representados"

VALOR RESUMEN:
  ┌────────────────────┐
  │  KL promedio test  │
  │       0.087        │
  │   (menor = mejor)  │
  └────────────────────┘
```

---

## PANEL MÉTRICA 2 — Top-K Accuracy (col 5–8, filas 2–8)

```
TÍTULO: "Top-K Accuracy"
SUBTÍTULO: "¿Aparece el cultivo real entre las K predicciones?"

NOTA: "Usando pixels de monitoreo UPRA (L1) como ground truth"

3 GAUGES circulares apilados:

GAUGE 1 — Top-1:
  Arco de 180° (semicírculo), relleno al 52%.
  Color: gradiente de #FF4455 (0%) a #44CC88 (100%).
  Texto en centro: "52%"
  Subtítulo: "El cultivo más probable es el correcto"

GAUGE 2 — Top-3:
  Arco al 73%.
  Texto: "73%"
  Subtítulo: "El cultivo está entre los 3 más probables"

GAUGE 3 — Top-5:
  Arco al 84%.
  Texto: "84%"
  Subtítulo: "El cultivo está entre los 5 más probables"

LÍNEA BASELINE debajo:
  "Baseline aleatorio (1/18 clases): Top-1 = 5.6%"
  "El modelo supera 9× el azar"
```

---

## PANEL MÉTRICA 3 — Matriz de confusión (col 9–12, filas 2–8)

```
TÍTULO: "Confusión entre Cultivos"
SUBTÍTULO: "Top-3: ¿cuándo falla y hacia dónde?"

MINI HEATMAP 6×6 (6 cultivos más frecuentes):
  Filas: cultivo real (verdad de campo)
  Columnas: cultivo más predicho cuando falla

  Diagonal: verde brillante (aciertos)
  Off-diagonal: gradiente rojo (intensidad = tasa de error)

  Los errores más marcados (celdas más rojas):
    Papa → Arveja: "condiciones similares de altura"
    Maíz → Frijol: "temperatura y precipitación parecidas"
    Cebolla → Papa: "suelo y altitud solapados"

CULTIVOS en los ejes: Papa, Maíz, Arveja, Haba, Cebolla, Frijol

INTERPRETACIÓN al pie:
  "Los errores ocurren entre cultivos con
   condiciones agro-climáticas similares.
   Esto es esperable — no son errores aleatorios."
```

---

## PROMPT IMAGEN (Slide 14)
```
Three-panel evaluation metrics infographic: LEFT panel shows horizontal bar 
chart of KL divergence per municipality (ordered low to high, blue=low good, 
orange=high problematic), KL=0.087 summary box, equation shown; CENTER panel 
shows three semicircular gauges stacked (Top-1: 52%, Top-3: 73%, Top-5: 84%) 
with gradient fill and baseline comparison (random 5.6%); RIGHT panel shows 
6x6 confusion matrix heatmap for top 6 crops (green diagonal=correct, red 
off-diagonal=errors, most confused pairs annotated: papa↔arveja, maíz↔frijol); 
dark background three-column layout
```

---
---

# SLIDE 15 — EL MAPA FINAL Y EL SISTEMA COMPLETO

**Título:** `El Resultado: De Proporción Municipal a Predicción por Pixel`
**Subtítulo:** `Cundinamarca — 9 millones de pixels — 18 cultivos — resolución 50m`

---

## LAYOUT

```
┌────────────────────────────────────────────────────────────────┐
│  TÍTULO                                                         │
├─────────────────────────────┬──────────────────────────────────┤
│  PANEL A                    │  PANEL B                          │
│  Comparación                │  Mapa final "Qué Sembrar"         │
│  EVA municipal vs            │                                   │
│  LLP-Co por pixel            │                                   │
├─────────────────────────────┴──────────────────────────────────┤
│  PANEL C: El ensamble jerárquico L1 + L2 + L3                   │
└────────────────────────────────────────────────────────────────┘
```

---

## PANEL A — Comparación de resoluciones (col 1–5, filas 2–6)

```
DOS MAPAS de la misma zona (municipio de Zipaquirá):

MAPA IZQUIERDO — Resolución EVA (municipal):
  El municipio es un polígono de color UNIFORME.
  Color = cultivo dominante (verde papa).
  Sin variación interna.
  Etiqueta: "EVA: Resolución municipal"
  Texto: "Todo Zipaquirá = Papa 43%"
  Pixel size visible: "~15 km²"

MAPA DERECHO — LLP-Co (pixel):
  El mismo municipio pero cada pixel de 50m tiene su propio color.
  Las laderas (alta pendiente, alta elevación) → más verde (papa)
  Los valles planos → más azul (maíz) o naranja (arveja)
  Las zonas urbanas → gris (no agrícola)
  Etiqueta: "LLP-Co: Resolución pixel (50m)"
  Texto: "Variación intra-municipal visible"

FLECHA entre los dos mapas:
  "De polígono → a pixel"

ESTADÍSTICAS bajo los mapas:
  EVA:   116 polígonos en Cundinamarca
  LLP-Co: 9.2 millones de pixels
```

---

## PANEL B — El mapa completo (col 6–12, filas 2–6)

```
MAPA de Cundinamarca completo con píxeles coloreados por cultivo más probable.

LEYENDA (18 cultivos con color):
  🟢 Papa        🔵 Maíz       🟠 Arveja
  🟡 Haba        🔴 Tomate     🟤 Café
  ... (todos los 18 cultivos)
  ⬛ No agrícola (zona urbana/rocosa)

OVERLAY adicional:
  Puntos de monitoreo UPRA (L1) como estrellas blancas pequeñas.
  Bordes de municipio como líneas finas #30363D.

ZOOM a una zona representativa (inset en la esquina):
  Detalle de 5×5 km mostrando variación pixel a pixel.

ESTADÍSTICAS del mapa:
  "9.2M pixels | 18 clases | resolución 50m"
  "Actualizable semestralmente"
```

---

## PANEL C — El ensamble jerárquico (col 1–12, filas 7–8)

```
DIAGRAMA de capas (de mayor a menor confianza):

CAPA L1 — Monitoreo UPRA:
  Color: #44CC88 brillante | Ícono: lupa/campo
  "Datos de campo directo — Confianza: 1.0"
  "Sobreescribe cualquier predicción del modelo"
  "~3.000 pixels con etiqueta verificada"

CAPA L2 — LLP-Co (este modelo):
  Color: #4A9EFF | Ícono: red neuronal
  "Predicción por pixel desde proporciones EVA — Confianza: 0.2–0.7"
  "Cubre todos los pixels no etiquetados directamente"
  "~8.5M pixels predichos"

CAPA L3 — No-apto SIPRA+NDVI:
  Color: #FF4455 | Ícono: X / máscara
  "Zonas claramente no agrícolas — Confianza: proxy"
  "Enmascara predicciones L2 en zonas urbanas/rocosas"

FLECHA de integración:
  [L1 prevalece] → [L2 cubre el resto] → [L3 enmascara no-agrícolas]
  = "Qué Sembrar — mapa integrado"

TEXTO FINAL (tipografía grande, centrada, al pie del panel C):
  "LLP-Co: aprender de proporciones → predecir en pixels."
```

---

## PROMPT IMAGEN (Slide 15)
```
Final results infographic: TOP LEFT shows two side-by-side maps of Zipaquirá 
municipality: left map shows uniform EVA color (whole municipality = one color), 
right map shows pixel-level variation (50m pixels with different colors for 
hillsides vs valleys vs urban areas), "de polígono a pixel" arrow between them; 
TOP RIGHT shows full Cundinamarca department pixel map colored by most probable 
crop (18-color legend), UPRA monitoring stars overlay, municipality borders; 
BOTTOM shows three-layer hierarchy diagram (L1 field monitoring green, L2 LLP-Co 
blue, L3 non-suitable red) with integration arrow producing "Qué Sembrar" final 
map; dark background
```

---

# ÍNDICE DE SLIDES Y FLUJO NARRATIVO

```
SLIDE 01 — El Problema          → "No tenemos etiquetas por pixel, solo proporciones"
    ↓ "¿De dónde vienen los datos?"
SLIDE 02 — Los Datos            → "72 features por pixel: clima, satélite, suelo, topo"
    ↓ "¿Cómo se agrupan?"
SLIDE 03 — Los Bags             → "Municipio = bag con proporciones EVA"
    ↓ "¿Cómo procesa el modelo esos datos?"
SLIDE 04 — El Encoder MLP       → "4 capas transforman el vector en embedding"
    ↓ "¿Qué forma tiene ese embedding?"
SLIDE 05 — El Espacio Latente   → "Todos los embeddings en una hiperesfera unitaria"
    ↓ "¿Cómo comparamos embeddings con cultivos?"
SLIDE 06 — Los Prototipos       → "18 vectores aprendibles = centros de cada cultivo"
    ↓ "¿Cómo asignamos sin violar las proporciones?"
SLIDE 07 — Transporte Óptimo   → "Asignar maximizando similitud + respetando EVA"
    ↓ "¿Cómo se calcula esa asignación?"
SLIDE 08 — Sinkhorn-Knopp      → "5 iteraciones de normalización alternada"
    ↓ "¿Qué produce Sinkhorn?"
SLIDE 09 — El Código Q          → "Etiqueta suave por pixel que satisface EVA"
    ↓ "¿Cómo generamos pares de entrenamiento?"
SLIDE 10 — Data Augmentation    → "Dos vistas perturbadas del mismo pixel"
    ↓ "¿Cómo usamos esas vistas para entrenar?"
SLIDE 11 — Swap Loss            → "Predecir el código Q de la vista contraria"
    ↓ "¿Qué evita el colapso?"
SLIDE 12 — KoLeo               → "Maximizar distancia mínima entre prototipos"
    ↓ "¿Cómo se integra todo?"
SLIDE 13 — Bucle Completo      → "Una iteración: datos → modelo → pérdidas → backprop"
    ↓ "¿Cómo se evalúa?"
SLIDE 14 — Evaluación           → "KL divergencia + Top-K accuracy + confusión"
    ↓ "¿Cuál es el resultado final?"
SLIDE 15 — El Mapa Final        → "9M pixels predichos — ensamble L1+L2+L3"
```

---

# ESPECIFICACIONES DE PRODUCCIÓN

## Dimensiones y formato
- **Tamaño:** 1920 × 1080 px (16:9), exportar también en 3840 × 2160 (4K)
- **Formato de entrega:** SVG (editable) + PNG (render final)

## Herramientas recomendadas
| Herramienta | Uso |
|-------------|-----|
| Figma | Composición de slides, grillas, colores, tipografía |
| Manim / ManimML | Animación de matrices, esferas, diagramas de flujo |
| Observable Plot | Heatmaps interactivos y barras |
| Inkscape | SVGs de ecuaciones y diagramas complejos |
| LaTeX + dvisvgm | Render de ecuaciones en SVG |

## Tipografía
- Títulos: **Inter Bold** 32px
- Subtítulos: Inter SemiBold 20px
- Texto cuerpo: Inter Regular 14px
- Código / ecuaciones: **JetBrains Mono** 13px

## Iconografía
- Usar exclusivamente iconos de línea (Phosphor Icons o Lucide)
- Tamaño estándar: 24px con stroke 1.5px
- Color: heredado del color del panel al que pertenecen
