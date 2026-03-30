# Armonización Espacial — `procesamiento/01_armonizar_espacial.py`

## Objetivo General

Antes de entrenar cualquier modelo de recomendación agrícola, todas las fuentes de datos del proyecto deben hablar el mismo idioma espacial: misma proyección, mismo tamaño de píxel, mismo encuadre geográfico. Sin esta homogeneización, no es posible alinear un píxel de temperatura con el píxel de suelo y el píxel de imagen satelital que cubren exactamente el mismo punto del territorio.

`01_armonizar_espacial.py` toma los datos crudos descargados por los extractores y los convierte a un único grid de referencia:

| Parámetro | Valor |
|---|---|
| Sistema de referencia de coordenadas | EPSG:3116 — MAGNA-SIRGAS Colombia Bogotá |
| Resolución espacial | 10 m × 10 m |
| Área de cobertura | Cundinamarca, Colombia |
| Valor de celda vacía (NoData) | −9999.0 |
| Formato de salida | GeoTIFF comprimido (Deflate) |

El script se ejecuta fuente por fuente (pasos 1 al 7) y al final opcionalmente valida la consistencia de todos los rásteres de salida.

---

## Por Qué EPSG:3116 y 10 m

**EPSG:3116 (MAGNA-SIRGAS Colombia Bogotá)** es la proyección oficial cartográfica de Colombia para Cundinamarca. Al ser una proyección plana métrica, las distancias en metros son exactas sobre el área de interés, lo que es indispensable para operaciones de vecindad (pendiente, kriging, convoluciones).

**10 m × 10 m** es la resolución nativa de las bandas principales de Sentinel-2 (B02, B03, B04, B08). Fijar 10 m como estándar evita degradar la fuente de mayor resolución y permite comparaciones directas entre píxeles satelitales y sus valores de suelo, clima y topografía.

---

## Utilidades Comunes

### `get_grid_cundinamarca()`

Calcula el transform affine, el ancho y el alto del grid objetivo transformando el bounding box de Cundinamarca (definido en WGS84 en `config.py`) a EPSG:3116. Todos los demás pasos usan esta función para obtener las dimensiones exactas del grid y así asegurarse de que todos los archivos de salida tengan exactamente el mismo número de filas y columnas.

### `reproyectar_raster(src, dst, resampling_method)`

Utilidad genérica que toma cualquier GeoTIFF de entrada (en cualquier CRS y resolución), calcula la reproyección al grid objetivo y escribe el GeoTIFF de salida con compresión Deflate. Admite tres métodos de remuestreo:

- **bilineal**: interpolación ponderada por distancia de los cuatro vecinos más cercanos. Adecuado para variables continuas (temperatura, precipitación, reflectancias).
- **nearest-neighbor**: asigna el valor del píxel más cercano. Obligatorio para variables categóricas (tipos de suelo, vocación de uso) para no mezclar categorías.
- **cubic**: interpolación bicúbica de 16 vecinos. No se usa actualmente pero está disponible para superficies que requieren mayor suavidad.

---

## Paso 1 — Estaciones IDEAM → Kriging + Corrección Adiabática

**Función:** `armonizar_ideam()`
**Entrada:** CSV por mes/año en `extractores/raw/clima/ideam_{temperatura|precipitacion|humedad}/`
**Salida:** `processed/clima/ideam/{variable}_{semestre}_kriging.tif`

### El Problema

Las estaciones meteorológicas del IDEAM son puntos discretos, no cubren el territorio de forma uniforme y Cundinamarca tiene aproximadamente 30–60 estaciones activas. Un modelo de machine learning necesita valores en cada uno de los ~476 millones de píxeles del grid de 10 m. Es necesario interpolar los puntos a superficies continuas.

### Por Qué Kriging Ordinario

El **Kriging Ordinario** es el mejor estimador lineal insesgado (BLUE) para interpolación geoespacial cuando se conoce la estructura de autocorrelación espacial de la variable. A diferencia de IDW (interpolación por distancia inversa), Kriging ajusta automáticamente un variograma experimental que captura la variabilidad espacial real de la variable (¿a qué distancia dejan de estar correlacionadas dos estaciones?). Esto produce superficies más realistas y proporciona además una estimación de la incertidumbre de la predicción.

### El Problema de Memoria y la Solución a Dos Etapas

Aplicar Kriging directamente al grid de 10 m crearía una matriz de covarianza de 476.000.000 × N_estaciones, lo que requiere cientos de GiB de RAM y es computacionalmente inviable. La solución es una estrategia en **dos etapas**:

1. **Kriging a 1 km** (~480 × 550 = 264.000 píxeles): se construye un grid intermedio a resolución kilométrica, que es perfectamente manejable en RAM (unos pocos MB). El radio de influencia de las estaciones en una región de 24.000 km² es del orden de decenas de kilómetros, por lo que la resolución de 1 km captura toda la variabilidad climática relevante sin perder información.

2. **Resampling bilineal de 1 km a 10 m**: el ráster de Kriging a 1 km se remuestrea con interpolación bilineal al grid final de 10 m. Esta operación es eficiente (solo cambio de escala) y produce transiciones suaves entre píxeles.

### Corrección por Gradiente Adiabático Seco (Solo Temperatura)

La temperatura disminuye aproximadamente **6 °C por cada 1.000 m de altitud** (gradiente adiabático seco). Cundinamarca varía entre ~200 m (Tequendama) y ~3.900 m (páramos de Sumapaz), una diferencia de más de 22 °C que no puede capturarse solo con las estaciones (pocas cubren páramos).

El proceso de corrección adiabática tiene dos momentos:

- **Antes del Kriging:** los valores observados de temperatura en cada estación se "normalizan" a una altitud de referencia (la mediana de altitudes de las estaciones del semestre), restando `0.006 × (altitud_estación − altitud_referencia)`. Así, el Kriging interpola temperaturas comparables entre sí.

- **Después del Kriging:** el ráster de Kriging a 1 km se "desnormaliza" usando el DEM (Modelo Digital de Elevación) remuestrado a 1 km: se suma `0.006 × (altitud_DEM − altitud_referencia)` píxel a píxel. El resultado es una superficie de temperatura que respeta tanto la variabilidad espacial interpolada por el Kriging como el gradiente altitudinal del territorio.

> **Nota:** el DEM debe armonizarse primero (`--step dem`). Si no existe, la corrección adiabática se omite y se emite un aviso.

### Agregación Temporal por Semestre

Los datos IDEAM tienen una observación por cada 10 minutos (precipitación) o cada hora (temperatura, humedad). Se agrupan por semestre agrícola (Semestre A: enero–junio, Semestre B: julio–diciembre) y se calcula la **mediana** por estación. La mediana es robusta ante outliers instrumentales comunes en redes de telemetría.

---

## Paso 2 — CHIRPS → Reproyección Bilineal desde ~5.3 km

**Función:** `armonizar_chirps()`
**Entrada:** `extractores/raw/clima/chirps/*.tif`
**Salida:** `processed/clima/chirps/*.tif`

### Qué es CHIRPS

CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data) es un producto de precipitación global que combina estimaciones de satélite con datos de estaciones en tierra. Tiene una resolución original de 0.05° (~5.3 km) y una ventana temporal mensual o diaria. Complementa las estaciones IDEAM porque cubre todo el territorio de forma uniforme, incluyendo zonas sin estaciones.

### Por Qué Bilineal

CHIRPS es una variable continua (mm de precipitación). El resampling bilineal desde 5.3 km a 10 m produce una interpolación suave que preserva los gradientes de precipitación. No se usa cubic porque la diferencia de escala (530×) ya es una extrapolación y la complejidad adicional del cubic no aporta información real.

---

## Paso 3 — SoilGrids → Bilineal (Continuos) / Nearest-Neighbor (Texturas) + Normalización

**Función:** `armonizar_soilgrids()` + `_normalizar_texturas_soilgrids()`
**Entrada:** `extractores/raw/suelo/soilgrids/*.tif`
**Salida:** `processed/suelo/soilgrids/*.tif` y `*_norm.tif` (texturas)

### Qué es SoilGrids

SoilGrids 2.0 (ISRIC) es el producto global de propiedades de suelo derivado de machine learning sobre datos de perfiles de suelo. Tiene resolución de 250 m y cubre múltiples profundidades (0–5 cm, 5–15 cm, 15–30 cm) y propiedades:

| Propiedad | Tipo | Descripción |
|---|---|---|
| `phh2o` | Continua | pH en agua |
| `soc` | Continua | Carbono orgánico del suelo |
| `bdod` | Continua | Densidad aparente |
| `cec` | Continua | Capacidad de intercambio catiónico |
| `nitrogen` | Continua | Nitrógeno total |
| `ocd` | Continua | Densidad de carbono orgánico |
| `clay` | Textura | Fracción de arcilla (%) |
| `sand` | Textura | Fracción de arena (%) |
| `silt` | Textura | Fracción de limo (%) |

### Dos Métodos de Resampling Según el Tipo de Variable

- **Propiedades continuas** (pH, SOC, BDOD, CEC, N, OCD): resampling **bilineal**. Los valores intermedios entre dos píxeles tienen significado físico real.

- **Texturas** (clay, sand, silt): resampling **nearest-neighbor**. Las texturas son propiedades intrínsecas del horizonte de suelo mapeado; interpolar entre "40% arcilla" y "20% arcilla" daría un valor de "30% arcilla" que no corresponde a ningún horizonte real. Se asigna el valor del píxel de suelo más cercano a cada píxel de destino.

### Normalización de Texturas

Por definición, `clay + sand + silt = 100%` en cualquier punto del suelo. Sin embargo, el resampling nearest-neighbor y los errores de redondeo en el producto original pueden producir sumas distintas de 100. La función `_normalizar_texturas_soilgrids()` lee los tres rásteres de textura por profundidad, calcula `total = clay + sand + silt` y divide cada fracción por el total:

```
clay_norm[i,j] = clay[i,j] / (clay[i,j] + sand[i,j] + silt[i,j]) × 100
```

Esto garantiza que los tres canales de textura sean siempre coherentes entre sí, lo que evita errores en modelos que los usen como entrada.

---

## Paso 4 — IGAC Vectorial → Rasterización a 10 m

**Función:** `armonizar_igac()`
**Entrada:** GeoJSON en `extractores/raw/suelo/igac_quimica/` y `extractores/raw/suelo/igac_vocacion/`
**Salida:** `processed/suelo/igac/*.tif` y `*_tabla_codigos.json`

### Por Qué Rasterización y No Vectorial

Los datos IGAC son polígonos de unidades de suelo con atributos como fertilidad, pH, vocación de uso. El modelo de machine learning trabaja con píxeles, no con polígonos. La rasterización convierte cada polígono en un conjunto de píxeles con el valor del atributo del polígono. `rasterio.features.rasterize` es eficiente para esto: recorre los pares (geometría, valor) y "pinta" cada polígono en el ráster de destino.

### Capas Producidas

**De propiedades químicas (`propiedades_quimicas_suelo.geojson`):**

| Campo IGAC | Archivo de salida | Tipo | Resampling |
|---|---|---|---|
| `FERTIL` | `fertilidad_igac.tif` | Categórico (int16) | nearest |
| `PH_AGUA` | `ph_agua_igac.tif` | Continuo (float32) | bilineal |
| `SAT_AL` | `sat_aluminio_igac.tif` | Continuo (float32) | bilineal |
| `FOSFORO` | `fosforo_igac.tif` | Continuo (float32) | bilineal |
| `POTASIO` | `potasio_igac.tif` | Continuo (float32) | bilineal |

**De vocación de uso (`vocacion_uso_suelo.geojson`):**

| Campo IGAC | Archivo de salida | Tipo | Resampling |
|---|---|---|---|
| `VOCACION` | `vocacion_uso_igac.tif` | Categórico (int16) | nearest |

### Codificación de Categóricos y Tabla de Códigos

Las variables categóricas (fertilidad, vocación) contienen strings como "Alta", "Media", "Ganadera", etc. Los modelos de ML requieren valores numéricos. El script asigna un entero secuencial (1, 2, 3, …) a cada clase única y guarda un archivo JSON con el mapeo inverso:

```json
// fertilidad_igac_tabla_codigos.json
{"1": "Alta", "2": "Media", "3": "Baja", "4": "Muy baja"}
```

Esto permite interpretar las predicciones del modelo después de entrenamiento.

---

## Paso 5 — Sentinel-2 → Reproyección a EPSG:3116 / 10 m

**Función:** `armonizar_sentinel2()`
**Entrada:** `extractores/raw/satelite/sentinel2/*.tif`
**Salida:** `processed/satelite/sentinel2/*.tif`

### Qué Contienen los GeoTIFF de Sentinel-2

El extractor descarga compuestos semestrales de reflectancia de superficie por banda espectral:

- **Bandas a 10 m nativos:** B02 (azul), B03 (verde), B04 (rojo), B08 (NIR cercano)
- **Bandas a 20 m nativos:** B05, B06, B07, B8A (NIR red-edge), B11, B12 (SWIR)
- **Índices derivados:** NDVI, EVI, NDWI (calculados en el extractor a partir de las bandas)

### Por Qué Solo Bilineal Para Ambas Resoluciones

Sentinel-2 ya descarga en UTM (generalmente EPSG:32618 para Colombia), que es un sistema de coordenadas plano métrico. La reproyección a EPSG:3116 implica una leve rotación y corrección de escala. El resampling bilineal es adecuado para reflectancias (variables continuas físicamente significativas). Las bandas a 20 m se upsamplean a 10 m, lo que es aceptable porque la resolución espectral de esas bandas sigue siendo válida a 10 m para índices vegetativos.

---

## Paso 6 — Sentinel-1 → Solo Reproyección a EPSG:3116

**Función:** `armonizar_sentinel1()`
**Entrada:** `extractores/raw/satelite/sentinel1/*.tif`
**Salida:** `processed/satelite/sentinel1/*.tif`

### Diferencia con Sentinel-2

Sentinel-1 es radar de apertura sintética (SAR). Sus GRD (Ground Range Detected) procesados ya tienen resolución de 10 m nativa. Por lo tanto, este paso solo realiza la reproyección de CRS (de UTM a EPSG:3116) sin ningún cambio de resolución. El método bilineal se aplica igualmente para el remuestreo a causa del shift geográfico en la reproyección.

### Valor del SAR para el Proyecto

El radar SAR penetra nubes, lo que es fundamental en Cundinamarca donde la nubosidad puede superar el 70% durante el semestre B. Provee información sobre estructura del dosel y humedad del suelo que complementa las bandas ópticas de Sentinel-2.

---

## Paso 7 — DEM Copernicus GLO-30 → Derivadas a 30 m + Resampling a 10 m

**Función:** `armonizar_dem()`
**Entrada:** `extractores/raw/topo/dem_glo30/cundinamarca_topografia.tif` (multibanda)
**Salida:** `processed/topo/dem_{banda}_10m.tif` por cada banda; alias `dem_cundinamarca_10m.tif`

### Por Qué las Derivadas se Calculan Antes del Resampling

El DEM Copernicus GLO-30 tiene resolución nativa de 30 m. El extractor calcula derivadas topográficas (pendiente, aspecto, curvatura, TWI) a esa resolución original y las guarda como un GeoTIFF multibanda. Este orden es crítico:

- **Calcular derivadas después del resampling a 10 m** introduciría artefactos: bilinear de 30→10 m produce una superficie suavizada artificialmente, y las derivadas de segundo orden (curvatura) de esa superficie suavizada serían incorrectas.
- **Calcular derivadas en la resolución original de 30 m** respeta la información real del DEM y luego se remuestrea solo el resultado, lo que es mucho más estable numéricamente.

### Bandas del Archivo Multibanda

| Banda | Variable | Descripción |
|---|---|---|
| 1 | `elevacion` | Elevación en metros sobre el nivel del mar |
| 2 | `pendiente` | Grados de inclinación (0°–90°) |
| 3 | `aspecto` | Orientación de la ladera en grados (0°=Norte) |
| 4 | `curvatura` | Curvatura del perfil (convexa/cóncava) |
| 5 | `twi` | Topographic Wetness Index — proxy de acumulación de humedad |

### Relevancia para el Modelo

La topografía determina el microclima (temperatura por altitud, precipitación por efecto orográfico), el drenaje (TWI), la erosión (pendiente × aspecto) y la aptitud agrícola. Es una de las covariables más predictivas en modelos de recomendación de cultivos para regiones montañosas como Cundinamarca.

### Alias del DEM de Elevación

El paso crea un alias `dem_cundinamarca_10m.tif` que apunta a la banda de elevación. Este archivo es el que consume el Paso 1 (IDEAM) para la corrección adiabática de temperatura, por eso el **DEM debe procesarse siempre primero** cuando se ejecutan todos los pasos en secuencia.

---

## Validación de Capas (`--step validar`)

**Función:** `validar_capas()`

Recorre todos los GeoTIFF en `processed/` y verifica:

1. **CRS = EPSG:3116** — todos los archivos deben estar en el mismo sistema de referencia.
2. **Dimensiones idénticas** — todos los archivos deben tener exactamente el mismo número de filas y columnas, que es el grid de referencia de Cundinamarca a 10 m.
3. **Rangos físicos plausibles** — detecta outliers o errores de conversión verificando que los valores estén dentro de rangos esperados:

| Keyword en nombre del archivo | Rango válido |
|---|---|
| `temperatura` | −5 °C a 40 °C |
| `precipitacion` | 0 mm a 800 mm |
| `humedad` | 0% a 100% |
| `elevacion` | 100 m a 4000 m |
| `pendiente` | 0° a 90° |
| `ph` | 3 a 9 |

Si algún archivo falla alguna de estas verificaciones, se reporta en consola con `✗` (error de geometría) o `⚠` (rango fuera de lo esperado).

---

## Orden de Ejecución Recomendado

```bash
# 1. DEM primero (lo necesita la corrección adiabática de temperatura)
uv run procesamiento/01_armonizar_espacial.py --step dem

# 2. IDEAM (interpola estaciones con corrección altitudinal)
uv run procesamiento/01_armonizar_espacial.py --step ideam

# 3. CHIRPS (precipitación satelital, independiente)
uv run procesamiento/01_armonizar_espacial.py --step chirps

# 4. SoilGrids (suelo global, independiente)
uv run procesamiento/01_armonizar_espacial.py --step soilgrids

# 5. IGAC (suelo colombiano vectorial, independiente)
uv run procesamiento/01_armonizar_espacial.py --step igac

# 6 y 7. Satelital (independientes entre sí)
uv run procesamiento/01_armonizar_espacial.py --step sentinel2
uv run procesamiento/01_armonizar_espacial.py --step sentinel1

# Validación final
uv run procesamiento/01_armonizar_espacial.py --step validar

# O todo en secuencia (el script respeta el orden correcto automáticamente)
uv run procesamiento/01_armonizar_espacial.py
```

---

## Estructura de Salida

```
processed/
├── clima/
│   ├── ideam/
│   │   ├── temperatura_2020A_kriging.tif
│   │   ├── temperatura_2020B_kriging.tif
│   │   ├── precipitacion_2020A_kriging.tif
│   │   └── humedad_2020A_kriging.tif
│   └── chirps/
│       └── chirps_v2.0.2020.01.tif
├── suelo/
│   ├── soilgrids/
│   │   ├── soilgrids_phh2o_0_5cm.tif
│   │   ├── soilgrids_clay_0_5cm.tif
│   │   └── soilgrids_clay_0_5cm_norm.tif
│   └── igac/
│       ├── fertilidad_igac.tif
│       ├── fertilidad_igac_tabla_codigos.json
│       └── vocacion_uso_igac.tif
├── satelite/
│   ├── sentinel2/
│   │   └── s2_2020A_B04.tif
│   └── sentinel1/
│       └── s1_2020A_VV.tif
└── topo/
    ├── dem_elevacion_10m.tif
    ├── dem_pendiente_10m.tif
    ├── dem_aspecto_10m.tif
    ├── dem_curvatura_10m.tif
    ├── dem_twi_10m.tif
    └── dem_cundinamarca_10m.tif  ← alias de elevación, usado por IDEAM
```

---

## Dependencias

```
pip install rasterio geopandas pykrige scipy numpy pyproj pandas
```

| Librería | Uso en el script |
|---|---|
| `rasterio` | Lectura/escritura de GeoTIFF, reproyección, rasterización |
| `geopandas` | Lectura de GeoJSON y reproyección de vectoriales |
| `pykrige` | Kriging ordinario para interpolación de estaciones |
| `scipy.ndimage` | Convoluciones para derivadas topográficas |
| `numpy` | Operaciones matriciales en todos los pasos |
| `pyproj` | Transformación de coordenadas entre CRS |
| `pandas` | Carga y agregación de CSVs de IDEAM |
