# Infografía — Pipeline AgroPlus "¿Qué Sembrar?"

Guía de contenido para diseño de infografía del sistema de recomendación de cultivos
para Cundinamarca, Colombia.

---

## METADATOS DEL PROYECTO

- **Área**: Cundinamarca (22.623 km²)
- **Resolución**: 50 × 50 m por píxel (~9 millones de píxeles)
- **Ventana temporal**: 2020-2025 (12 semestres: A/B)
- **CRS trabajo**: EPSG:3116 (MAGNA-SIRGAS Bogotá)
- **14 clases objetivo**: Papa, Caña Panelera, Café, Maíz, Plátano, Mango,
  Frijol, Cacao, Arveja, Palma, Banano, Naranja, Otros cultivos, No apto

---

## PANEL 0 — Diagrama general (vista 360°)

Diagrama en 4 bloques secuenciales con flechas entre ellos.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. EXTRAER  │───▶│ 2. ARMONIZAR │───▶│  3. MINABLE  │───▶│ 4. ETIQUETAR │
│  9 fuentes   │    │  grilla 50m  │    │ tabla píxel  │    │  3 niveles   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
   heterogéneo       EPSG:3116            parquet             14 clases
   (CSV, GeoTIFF,    float32              ~500k filas          con confianza
   GeoJSON, HDF5)    NoData=-9999         53 features          L1/L2/L3
```

**Colores sugeridos por bloque:**
- Bloque 1 (Extraer): azul (#2E86AB)
- Bloque 2 (Armonizar): verde (#06A77D)
- Bloque 3 (Vista minable): naranja (#F18F01)
- Bloque 4 (Etiquetar): rojo (#D62828)

---

## PANEL 1 — Extracción de 9 fuentes

Diagrama central con el mapa de Cundinamarca rodeado por 9 iconos-fuente
con flechas convergentes.

### Bloque CLIMA (☁️)
- **IDEAM**: temperatura, precipitación, humedad (estaciones puntuales)
- **CHIRPS**: precipitación satelital 5.5 km (rellenar huecos IDEAM)

### Bloque SUELO (🌱)
- **SoilGrids 2.0 (ISRIC)**: pH, carbono orgánico, textura, CIC, nitrógeno (250 m global)
- **IGAC**: vocación de uso, taxonomía, química local (variable)

### Bloque TOPOGRAFÍA (⛰️)
- **Copernicus GLO-30**: DEM 30 m → elevación, pendiente, TWI, aspecto

### Bloque SATELITAL (🛰️)
- **Sentinel-2 L2A**: NDVI, GNDVI, SAVI, MSAVI, BSI (mensual, 50 m)
- **Sentinel-1 GRD**: VV, VH, ratio VH/VV en dB (radar, no excluido)

### Bloque ETIQUETADO (🏷️)
- **UPRA Monitoreo**: polígonos de campo (Papa, Arroz — 7 capas)
- **EVA Municipal**: CSV áreas por cultivo/municipio/año
- **SIPRA Aptitud**: 14+ capas de aptitud por cultivo
- **MGN DANE**: límites municipales

**Dato visual**: "9 fuentes heterogéneas → 1 proyecto unificado"

---

## PANEL 2 — Armonización espacial y temporal

### Visual principal
Mostrar capas apiladas que convergen a una grilla común:

```
     Fuentes crudas                    Grilla armonizada
┌──────────────────────┐            ┌──────────────────────┐
│ 🌡️ IDEAM puntos      │            │                      │
│ 🗺️ SoilGrids 250m   │   ───▶    │    EPSG:3116         │
│ ⛰️ DEM 30m           │  armonizar │    50 × 50 m         │
│ 🛰️ Sentinel 10m      │            │    float32           │
│ 🏷️ GeoJSON WGS84     │            │    NoData=-9999      │
└──────────────────────┘            └──────────────────────┘
```

### Técnicas aplicadas

| Problema | Solución |
|----------|----------|
| Estaciones IDEAM dispersas | Interpolación **Kriging ordinario** |
| Rasters con resoluciones distintas | **Remuestreo bilineal/nearest** a 50 m |
| Proyecciones variadas | Reproyección a **EPSG:3116** |
| Texturas no suman 100% | **Normalización** clay+sand+silt = 100% |
| NoData heterogéneo | Unificado a **-9999 → NaN** |

### Armonización temporal

```
Diario ──▶ Mensual ──▶ Semestral (A/B)
         agregación    agg: media, sum,
         climatológica  max, std, min
```

- **Mensual**: preservado para futuros modelos LSTM
- **Semestral**: consumido por modelos tabulares (XGBoost, RF)
- Calendario Colombia: Semestre A = Ene–Jun, Semestre B = Jul–Dic

---

## PANEL 3 — Construcción de la vista minable

### Visual principal
Mostrar cómo de muchos rasters se saca una tabla rectangular.

```
     RASTERS (50 capas)                     TABLA MINABLE
┌──────────────────────┐               ┌────────────────────────┐
│  ┌─ elevacion        │               │pixel│semes│elev│…│cult│
│  ┌─ ph_suelo         │               ├─────┼─────┼────┼─┼────┤
│  ┌─ ndvi_max         │ muestreo      │  1  │2022A│1500│…│Papa│
│  ┌─ temperatura      │────────▶      │  2  │2022A│ 800│…│Cafe│
│  ┌─ pendiente        │ estratificado │  3  │2022B│2500│…│NA  │
│  ┌─ ...              │               │ ... │ ... │... │…│... │
│  └─ 50 capas         │               └────────────────────────┘
└──────────────────────┘                500.000 filas × 53 cols
```

### Paso a paso

**① Máscara válida** 
Solo píxeles dentro de Cundinamarca con DEM definido (~9 M píxeles)

**② Rasterización de vectores**
Polígonos UPRA, municipios DANE, aptitud SIPRA → rasters 50 m alineados

**③ Muestreo estratificado**
32 estratos: piso térmico (4) × pendiente (4) × monitoreo (2)
- Todos los píxeles UPRA (L1) se **incluyen 100%**
- Resto muestreado proporcionalmente por estrato → max 500.000

**④ Extracción de features**
Para cada (píxel, semestre): leer valor en cada raster = 53 columnas

**⑤ Codificación temporal cíclica**
Transformar "2022A" en features numéricos:
- `semestre_cos = cos(π · k)` donde k ∈ {0,1}
- `year_norm = (year - 2020) / 5`

**⑥ Export parquet**
`vista_minable_full.parquet` + `catalogo_cultivos.json`

### Composición del feature set

```
TOTAL: 53 features
├── Topográficas (5):   elevación, pendiente, TWI, aspecto_sin/cos
├── Suelo (8):          pH, SOC, N, CIC, densidad, clay, sand, silt
├── Clima (5):          T media/max/min, humedad, CHIRPS
├── Satelital S2 (15):  5 índices × 3 estadísticos (media, max, std)
├── Derivadas (10):     piso térmico, fertilidad, aridez, NDVI máx, …
└── Identificación (5): pixel_id, x, y, semestre, cod_mun
```

---

## PANEL 4 — Etiquetado jerárquico de 3 niveles

### Visual principal: pirámide invertida de calidad decreciente

```
                    ▲ CONFIANZA
                    │
         ┌──────────┴──────────┐
         │  L1: UPRA MONITOREO │  confianza = 1.00
         │  Papa, Arroz        │  fuente: observación satelital
         │  ~10.000 píxeles    │  ✓ polígonos verificados
         └──────────┬──────────┘
                    │
     ┌──────────────┴──────────────┐
     │  L2: EVA MUNICIPAL          │  confianza = 0.30 - 0.70
     │  Los 14 cultivos            │  fuente: estadística municipal
     │  ~350.000 píxeles           │  ⚠ auto-reporte campesino
     └──────────────┬──────────────┘
                    │
  ┌─────────────────┴─────────────────┐
  │  L3: NO APTO (PROXY)              │  confianza = 0.40
  │  Solo clase "No_apto"             │  fuente: SIPRA + NDVI bajo
  │  ~140.000 píxeles                 │  ⚠ inferencia indirecta
  └───────────────────────────────────┘
```

### Nivel L1 — UPRA Monitoreo Satelital

**Fuente**: Polígonos de campo delimitados por UPRA con Sentinel-1/2
**Cobertura Cundinamarca**: Papa y Arroz (los demás cultivos no tienen)
**Lógica**:
```
si pixel ∈ polígono_UPRA_del_semestre:
    etiqueta = cultivo        # Papa, Arroz
    confianza = 1.0
    fuente = 'monitoreo'
```
**Por qué conf=1.0**: verificación visual humana de polígonos reales.

### Nivel L2 — EVA Municipal

**Fuente**: Estadísticas MADR/UPRA de área cosechada por municipio y año
**Lógica**:
```
para cada municipio m y semestre s:
    cultivo_dominante = el de mayor área
    score = área_dominante / área_agrícola_total_m
    
    si pixel ∈ municipio m y sin etiqueta L1:
        si score ≥ 0.30:
            etiqueta = cultivo_dominante     # Café, Caña, Maíz, etc.
            confianza = min(score, 0.7)
        sino:
            etiqueta = 'Otros_cultivos'
            confianza = 0.30
```
**Por qué conf ≤ 0.7**: el cultivo dominante municipal **no** es el cultivo de cada píxel
individual (dentro del municipio hay bosque, pasto, agua, varios cultivos mezclados).

### Nivel L3 — No Apto (proxy)

**Fuente combinada**: SIPRA aptitud + NDVI histórico
**Lógica**:
```
si pixel aún sin etiqueta (fuera de MGN o municipio sin datos EVA):
    SIPRA_vota_noapto = (≥ 3 capas SIPRA dicen "No apta")
    NDVI_ausente     = (NDVI_max_2años < 0.15)
    
    si SIPRA_vota_noapto O NDVI_ausente:
        etiqueta = 'No_apto'
        confianza = 0.40
        fuente = 'noapto_proxy'
```
**Por qué el cruce**:
- SIPRA solo es prescriptivo ("podría no crecer") → débil
- NDVI bajo es observacional ("no creció") → fuerte
- Juntos: filtran parques naturales (NDVI alto) y dejan solo zonas realmente no cultivables

---

## PANEL 5 — Cómo el modelo usa la confianza

### Visual: balanza con pesos distintos por etiqueta

```
           Entrenamiento del modelo
    ┌────────────────────────────────────┐
    │                                    │
    │  Pérdida = Σᵢ wᵢ · error(yᵢ, ŷᵢ)  │
    │                                    │
    │  donde:                            │
    │   wᵢ = class_balanced × confianzaᵢ │
    │                                    │
    └────────────────────────────────────┘

    Píxel L1 (Papa, conf=1.0)    ████████  peso alto
    Píxel L2 (Café, conf=0.5)    ████      peso medio
    Píxel L3 (No_apto, conf=0.4) ███       peso bajo
```

**Efecto en el aprendizaje**: los píxeles L1 "tiran" del modelo con el doble o triple
de fuerza que los L2/L3. Las etiquetas ruidosas aportan información pero no dominan.

**Validación espacial (`GroupKFold` por municipio)**:
- Ningún municipio aparece a la vez en train y test
- Evita fuga espacial entre píxeles vecinos

---

## PANEL 6 — Cifras clave para mostrar

Números para cajas/callouts destacados:

| Métrica | Valor |
|---------|-------|
| Fuentes de datos integradas | 9 |
| Área cubierta | 22.623 km² |
| Resolución espacial | 50 × 50 m |
| Píxeles totales del departamento | ~9.000.000 |
| Semestres analizados | 12 (2020A–2025B) |
| Features por píxel | 53 |
| Filas en vista minable | ~500.000 |
| Clases del modelo | 14 |
| Niveles de etiquetado | 3 (L1/L2/L3) |
| Tamaño parquet final | ~200 MB |

---

## PALETA DE COLORES SUGERIDA

```
Primario      Extraer     Armonizar   V. Minable   Etiquetar
#1B263B      #2E86AB     #06A77D     #F18F01      #D62828
Azul marino  Azul        Verde       Naranja      Rojo

L1 Monitoreo   L2 EVA       L3 No_apto
#2E7D32        #F57C00      #757575
Verde oscuro   Naranja      Gris
```

---

## ICONOGRAFÍA SUGERIDA

- 🛰️ Satélite → Sentinel-2, Sentinel-1
- ☁️ Nube → datos climáticos IDEAM/CHIRPS
- 🌱 Planta → suelo SoilGrids/IGAC
- ⛰️ Montaña → DEM/topografía
- 🏷️ Etiqueta → target (UPRA, EVA, SIPRA)
- 📊 Gráfica → vista minable
- ⚙️ Engranaje → armonización
- 🧠 Cerebro → modelo ML (entrenamiento)
- 🗺️ Mapa → predicción final

---

## FLUJO NARRATIVO PROPUESTO (lectura de arriba hacia abajo)

1. **Título**: "AgroPlus — De 9 fuentes heterogéneas a una recomendación de cultivo"
2. **Mapa**: Cundinamarca con subtítulo "22.623 km² · 9 M píxeles de 50 m"
3. **Bloque 1**: Extraer (9 fuentes → crudos)
4. **Bloque 2**: Armonizar (crudos → grilla común)
5. **Bloque 3**: Vista minable (rasters → tabla)
6. **Bloque 4**: Etiquetar jerárquicamente (pirámide de confianza)
7. **Bloque 5**: Entrenamiento ponderado por confianza
8. **Cierre**: "Un modelo que aprende de datos heterogéneos sin dejar que el ruido domine"
