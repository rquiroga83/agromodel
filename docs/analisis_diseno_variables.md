# Análisis de Diseño y Variables del Modelo — «¿Qué Sembrar?»
## Módulo de Recomendación de Cultivos | Cundinamarca, Colombia

> Documento técnico que explicita los supuestos, decisiones de diseño y justificación de cada grupo de variables del modelo de IA, con respaldo en el estado del arte en sistemas de recomendación agrícola.

---

## 1. Contexto y Objetivo del Sistema

El módulo «¿Qué Sembrar?» recibe un polígono geográfico —la parcela del agricultor— y devuelve un ranking de cultivos ordenados por probabilidad de éxito, fundamentado en la aptitud agroecológica real de esa ubicación en Cundinamarca.

El sistema opera bajo un supuesto central: **la aptitud de un cultivo en un lugar es predecible a partir de las condiciones biofísicas del terreno (suelo, clima, topografía) y del historial de lo que otros agricultores han sembrado exitosamente en condiciones similares**. Este supuesto es válido cuando:

- Las condiciones no varían abruptamente dentro del píxel de análisis (50 m × 50 m).
- El historial de siembra refleja decisiones racionales de los agricultores.
- El comportamiento pasado de los cultivos en ese ambiente es predictivo del futuro.

La validez de estos supuestos está respaldada por la literatura: Emmanuel N. et al. (2024), Hamza et al. (2025), Hasan et al. (2023) y Jeong et al. (2016) demuestran que modelos entrenados con variables biofísicas históricas predicen aptitud de cultivos con exactitud del 85–99% en sus contextos respectivos.

---

## 2. Decisiones de Diseño Fundamentales

### 2.1 Unidad de Análisis: (Píxel, Semestre)

**Decisión:** Cada fila de la tabla de entrenamiento corresponde a un píxel de 50 m × 50 m en un semestre específico (2020A–2025B). Un mismo píxel aparece hasta 12 veces —una por semestre.

**Supuesto:** Las condiciones dentro de un píxel de 50 m son suficientemente homogéneas para caracterizarlas con un solo valor por variable.

**Justificación:**
- El píxel es más granular que el municipio (que pierde variabilidad espacial interna) y más representativo que la parcela individual (de la que hay muy pocos datos georreferenciados).
- El semestre es la unidad de planificación agrícola en Colombia: las Evaluaciones Agropecuarias Municipales (EVA) reportan datos semestrales, el IDEAM publica balances hídricos semestrales, y los ciclos bimodales de lluvia de Cundinamarca estructuran naturalmente los calendarios de siembra en dos períodos (enero–junio y julio–diciembre).
- Iqbal et al. (2023) demuestran que usar series temporales dentro de ciclos de cultivo mejora la clasificación respecto a usar imágenes únicas.

**Alternativas descartadas:**
- **Municipio:** Datos EVA completos (1.104 municipios × 15 años), pero pierde toda la heterogeneidad espacial interna. Un municipio de Cundinamarca puede tener zonas de páramo y zonas cálidas simultáneamente.
- **Fila mensual en la vista minable:** Los rasters mensuales **sí se conservan** los mantiene explícitamente para uso futuro en modelos LSTM. Lo que se descarta es usar el mes como unidad de fila en la vista minable tabular: los modelos tabulares (RF, XGBoost, LightGBM) no explotan la secuencia temporal, y usar 6 filas por píxel (una por mes) en lugar de 1 (el semestre agregado) generaría ruido por meses con nubosidad alta y triplicaría el tamaño de la tabla sin beneficio para esos modelos.

### 2.2 Resolución Espacial: 50 Metros

**Decisión:** Todo el pipeline trabaja a 50 m × 50 m en proyección EPSG:3116 (MAGNA-SIRGAS Colombia Bogotá).

**Supuesto:** La resolución de 50 m es suficiente para capturar la variabilidad agroecológica relevante para la recomendación de cultivos en Cundinamarca.

**Justificación:**
- Es la resolución de descarga de Sentinel-1 y Sentinel-2 (configurada en `extractores/config.py: RESOLUCION_M = 50`), que permite cubrir Cundinamarca con 4 tiles por mes en lugar de 90, reduciendo tiempo de descarga de ~450 min a ~90 min con 8 workers.
- A 50 m, Cundinamarca (24.000 km²) genera ~9.6 millones de píxeles. Con 12 semestres y muestreo estratificado de 500.000 píxeles, la vista minable tiene ~6 millones de filas —manejable en RAM con pandas.
- La variabilidad de suelos IGAC (escala 1:100.000) y SoilGrids (250 m) limita la precisión efectiva de las capas edafológicas, haciendo que el beneficio marginal de usar píxeles de mayor resolucion sobre sobre pixeles de 50 m sea pequeño para ese grupo de variables.

**Alternativa descartada (10 m):** Máxima información espectral pero genera ~240M píxeles × 12 semestres = 2.880M filas. Computacionalmente inviable para entrenamiento con hardware estándar. La ganancia en precisión para recomendación agronómica no justifica el costo computacional.

### 2.3 Proyección Cartográfica: EPSG:3116

**Decisión:** Todos los rasters procesados se reproyectan a EPSG:3116 (MAGNA-SIRGAS Colombia Bogotá), la proyección oficial del IGAC para Cundinamarca.

**Supuesto:** Las operaciones métricas (pendiente, curvatura, TWI, distancias de Kriging) requieren unidades métricas exactas.

**Justificación:**
- En proyecciones geográficas (WGS84, lat/lon), un grado de longitud mide ~111 km en el ecuador pero menos en latitudes medias. Los gradientes topográficos calculados con diferencias de grados darían pendientes incorrectas. EPSG:3116 garantiza que 1 unidad = 1 metro en cualquier punto de Cundinamarca.
- El Kriging Ordinario (usado para interpolar estaciones IDEAM) requiere distancias isotrópicas para ajustar el variograma. Con proyecciones métricas, la distancia entre estaciones en metros es directamente comparable.
- Los mapas IGAC y SIPRA están en EPSG:4686 o EPSG:4326 pero sus unidades de análisis (los polígonos) son comparables con el grid métrico.

### 2.4 Ventana Temporal: 2020–2025

**Decisión:** Se descargan 6 años de datos (72 meses, 12 semestres: 2020A a 2025B).

**Supuesto:** El período 2020–2025 es representativo de las condiciones actuales y futuras del clima en Cundinamarca, y tiene suficiente cobertura de datos de alta calidad (Sentinel-2 L2A disponible desde 2018 con buena cobertura).

**Justificación:**
- El monitoreo satelital UPRA comienza en 2021. La EVA tiene datos desde 2007, pero su calidad espacial para asignación a píxeles mejora cuando se combina con el monitoreo. Comenzar en 2020 permite un año de "rodaje" antes del monitoreo y maximiza la calidad de etiquetas.
- 6 años × 2 semestres = 12 registros por píxel. Con muestreo de 500.000 píxeles, se tienen 6M ejemplos de entrenamiento —suficiente para modelos complejos (Random Forest, XGBoost, LightGBM).
- El período incluye variabilidad climática (años con La Niña y El Niño), lo que hace el modelo más robusto a condiciones anómalas.

### 2.5 Sistema de Etiquetas con Tres Fuentes y Confianza Diferenciada

**Decisión:** Las etiquetas de entrenamiento combinan tres fuentes con niveles de confianza distintos: monitoreo UPRA (1.0), EVA municipal (0.7), zonificación SIPRA (0.2–0.5).

**Supuesto:** No existe un censo completo de qué se siembra en cada píxel de Cundinamarca. Las tres fuentes son complementarias en cobertura espacial y temporal pero difieren en precisión.

**Justificación epistemológica:**

| Fuente | Tipo | Precisión espacial | Cobertura | Confianza |
|---|---|---|---|---|
| Monitoreo UPRA | Polígonos georreferenciados | Parcela exacta | 4 cultivos, 2021–2024 | 1.0 |
| EVA municipal | Estadística oficial | Municipal (±km) | 60+ cultivos, 2007–2025 | 0.7 |
| SIPRA aptitud | Modelo agronómico | Zona (~km²) | 65+ cultivos, estático | 0.2–0.5 |

Esta escala de confianza permite usar la columna como peso de muestra durante el entrenamiento, dando más influencia a las observaciones directas (monitoreo) y menos a las inferidas (SIPRA). Hasan et al. (2023) y Emmanuel N. et al. (2024) señalan que la calidad de las etiquetas es el factor más crítico para el rendimiento del modelo.

### 2.6 Muestreo Estratificado

**Decisión:** Se muestrea el 5% de los píxeles mediante estratificación por piso térmico × clase de pendiente, incluyendo el 100% de los píxeles con monitoreo UPRA.

**Supuesto:** La distribución de cultivos en Cundinamarca no es uniforme en el espacio. El piso térmico y la pendiente son las variables más determinantes de esa distribución.

**Justificación:**
- El muestreo aleatorio simple favorece las zonas más extensas (piso frío y templado, pendiente moderada), subrepresentando cultivos de tierra caliente (arroz, cacao, palma) que son minoría en área pero importantes para el modelo.
- Los 32 estratos (4 pisos × 4 clases pendiente × 2 disponibilidades de monitoreo) garantizan que cada combinación ecológica tenga al menos 15.000 píxeles de muestra.
- Emmanuel N. et al. (2024) identifican el sesgo de muestreo como una causa principal de modelos que predicen bien en las clases dominantes pero fallan en las raras.

---

## 3. Fuentes de Datos: Descripción y Acceso

### 3.1 IDEAM — Datos Meteorológicos

**Descripción:** Red nacional de estaciones meteorológicas automáticas y convencionales del IDEAM. Para Cundinamarca, ~50–70 estaciones activas.

**Variables disponibles:**
- Temperatura ambiente del aire (dataset `sbwg-7ju4` en datos.gov.co)
- Precipitación (dataset `s54a-sgyg`)
- Humedad relativa del aire (dataset `uext-mhny`)
- Normales climatológicas 1961–2020 (dataset `nsz2-kzcq`): medias de precipitación, temperaturas máxima/mínima/media, brillo solar, evaporación

**Cómo obtener:**
```
API REST: https://www.datos.gov.co/resource/{dataset_id}.json
Ejemplo: https://www.datos.gov.co/resource/sbwg-7ju4.json?$limit=50000
```

**Formato:** JSON/CSV con campos de estación, fecha, valor, unidad.
**Limitación:** Cobertura espacial irregular; zonas remotas con pocas estaciones.

### 3.2 CHIRPS v3 — Precipitación Satelital

**Descripción:** Climate Hazards Group InfraRed Precipitation with Station data. Combina imágenes infrarrojas de satélite con datos de estaciones. Cobertura global 50°S–50°N desde 1981.

**Variables:** Precipitación mensual (mm), resolución ~5.3 km (0.05°).

**Cómo obtener:**
```
# Por FTP masivo:
ftp://ftp.chc.ucsb.edu/pub/org/chc/products/CHIRPS-2.0/global_monthly/tifs/

# Por GEE (Google Earth Engine):
ee.ImageCollection("UCSB-CHG/CHIRPS/MONTHLY")

# Por Python con xarray:
# URL patrón: https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/
# chirps-v3.0.{YYYY}.{MM}.tif.gz
```

**Uso en el proyecto:** Descargado por `extractores/01_extraer_clima.py`. Complementa al IDEAM con cobertura uniforme. Se usa para anomalías de precipitación e índice de aridez porque no depende de la densidad de estaciones.

### 3.3 Copernicus Data Space — Sentinel-2 L2A

**Descripción:** Imágenes ópticas multiespectrales con corrección atmosférica (Bottom of Atmosphere), resolución 10–60 m, revisita 5 días.

**Bandas utilizadas:** B02 (azul), B03 (verde), B04 (rojo), B08 (NIR), B11 (SWIR), SCL (máscara nubes), dataMask.

**Cómo obtener:**
```
# API SentinelHub via CDSE (credenciales OAuth2):
Base URL: https://sh.dataspace.copernicus.eu
Token URL: https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token

# Registro gratuito: https://dataspace.copernicus.eu
# Suscripción necesaria para uso intensivo (plan básico gratuito: 30.000 procunidades/mes)
```

**En el proyecto:** Descargado por `extractores/05_extraer_sentinel2.py`. Compositing mensual por mediana libre de nubes (filtro SCL). 7 índices calculados en evalscript JavaScript. Se descargan 4 tiles por mes a 50 m (configurable en `RESOLUCION_M`).

**Supuesto crítico corregido:** La función `preProcessScenes` del evalscript NO funciona en CDSE (usa `orbit.tiles` que no existe en ese endpoint). El evalscript debe omitirla; de lo contrario, todos los píxeles devuelven 0. Este bug fue identificado y corregido: todos los archivos descargados con el evalscript incorrecto deben re-descargarse.

### 3.4 Copernicus Data Space — Sentinel-1 GRD

**Descripción:** Radar SAR banda C, modo IW (Interferometric Wide), polarización VV+VH, resolución 10 m, revisita 6–12 días. Penetra nubes.

**Variables:** Backscatter VV (dB), VH (dB), ratio VH/VV (dB).

**Cómo obtener:** Misma API y credenciales que Sentinel-2 (CDSE). Colección `SENTINEL1_IW_ASC`.

**En el proyecto:** `extractores/06_extraer_sentinel1.py`. Compositing mensual por media (SAR no tiene problema de nubes). Misma arquitectura de tiles que S2.

### 3.5 SoilGrids 2.0 (ISRIC)

**Descripción:** Mapas globales de propiedades del suelo generados por machine learning a partir de ~240.000 perfiles mundiales. Resolución 250 m. 6 profundidades estándar (0–5, 5–15, 15–30, 30–60, 60–100, 100–200 cm).

**Propiedades disponibles:** `phh2o` (pH), `soc` (carbono orgánico), `nitrogen` (nitrógeno total), `cec` (capacidad de intercambio catiónico), `bdod` (densidad aparente), `ocd` (densidad de carbono orgánico), `clay`, `sand`, `silt` (texturas).

**Cómo obtener:**
```
# WCS (Web Coverage Service):
https://maps.isric.org/mapserv?map=/map/{propiedad}.map&SERVICE=WCS&REQUEST=GetCoverage
&COVERAGEID={propiedad}_mean_{profundidad}

# REST API con descarga de tiles:
https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&property={prop}

# Descarga masiva (recomendada para áreas grandes):
rsync -avz --partial rsync://hydra.isric.org/soilgrids/latest/data/{propiedad}/ .
```

**En el proyecto:** `extractores/03_extraer_suelos.py`. Se descargan las profundidades 0–5 cm como representativas del horizonte agrícola.

### 3.6 IGAC — Información de Suelos y Vocación de Uso

**Descripción:** Instituto Geográfico Agustín Codazzi. Mapas vectoriales nacionales a escala 1:100.000.

**Datasets:**
- Propiedades químicas de suelos: pH (`F_SAL`), fósforo (`P`), potasio (`K`), fertilidad (`Calificacion_1`)
- Vocación de Uso: código de aptitud (18 clases)
- Unidades de suelo: `UCSuelo`, `SUBGRUPO` (taxonomía), `PAISAJE`

**Cómo obtener:**
```
# Geoservicios WFS del IGAC:
https://sigweb.igac.gov.co/arcgis/services/

# Portal de datos abiertos:
https://www.datos.gov.co/browse?q=IGAC+suelos

# Descarga directa (requiere registro):
https://www.igac.gov.co/es/servicios-cartograficos/download
```

**Supuesto:** Los campos del IGAC son rangos cualitativos ("≤ 5.5", "5.5–6.0") no valores continuos. Se tratan como variables categóricas ordinales durante la rasterización.

### 3.7 Copernicus DEM GLO-30

**Descripción:** Modelo Digital de Elevación global a 30 m derivado de datos TanDEM-X. Cobertura mundial.

**Variables base:** Elevación en metros. Derivadas calculadas: pendiente (operador de Horn), aspecto (arctan2 de gradientes), curvatura (segunda derivada), TWI (índice topográfico de humedad).

**Cómo obtener:**
```
# AWS Open Data (sin costo):
https://registry.opendata.aws/copernicus-dem/

# Descarga directa por tiles:
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat}_00_W{lon}_00_DEM.tif

# Python con boto3:
import boto3
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
s3.download_file('copernicus-dem-30m', 'key', 'local_file.tif')
```

**En el proyecto:** `extractores/02_extraer_topo.py`. Las derivadas se calculan a 30 m PRIMERO (resolución original) y luego se resamplán a 50 m. Calcularlas post-resampling introduciría suavizado artificial que distorsionaría pendientes.

### 3.8 UPRA — Etiquetas de Entrenamiento

**Fuentes de etiquetas:**

| Dataset | Descripción | Acceso |
|---|---|---|
| EVA UPRA | Evaluaciones Agropecuarias Municipales: área sembrada, cosechada y rendimiento por cultivo-municipio-semestre | `datos.gov.co: 2pnw-mmge` |
| Monitoreo Satelital UPRA | Polígonos georreferenciados de parcelas productivas (papa, maíz, arroz, cacao, plátano, pastos, caña) | Geoservicios UPRA: `geoservicios.upra.gov.co` |
| SIPRA Zonificaciones | 65+ capas de aptitud por cultivo a 1:100.000 (Alta, Media, Baja, No Apta) | Portal SIPRA: `sipra.upra.gov.co` |

```
# EVA via datos.gov.co:
GET https://www.datos.gov.co/resource/2pnw-mmge.json?departamento=CUNDINAMARCA&$limit=100000

# Monitoreo UPRA WFS:
https://geoservicios.upra.gov.co/arcgis/rest/services/MonitoreoCultivos/MapServer
```

---

## 4. Variables de Entrada: Grupos, Objetivo y Justificación del Estado del Arte

### Grupo 1 — Variables Climáticas

**Objetivo dentro del proyecto:** Caracterizar el régimen térmico e hídrico del semestre en cada píxel, incorporando tanto las condiciones medias como los extremos y anomalías que determinan el éxito o fracaso de cada cultivo.

El clima es el factor limitante principal de la aptitud agrícola porque no puede ser modificado por el agricultor (a diferencia del suelo, que puede enmendarse). Toda selección de cultivo es, en esencia, una adaptación al régimen climático del lugar.

#### 4.1.1 Temperatura Media, Máxima y Mínima del Semestre

| Variable | Tipo | Fuente | Resolución bruta |
|---|---|---|---|
| `temp_media` | Float (°C) | IDEAM + Kriging | Puntual → 1 km → 50 m |
| `temp_max` | Float (°C) | IDEAM + Kriging | Puntual → 50 m |
| `temp_min` | Float (°C) | IDEAM + Kriging | Puntual → 50 m |

**Por qué son importantes:**

La temperatura media determina el rango en el que los procesos metabólicos del cultivo operan eficientemente. Cada especie tiene un rango óptimo fuera del cual el rendimiento disminuye: papa (10–20°C), maíz (20–30°C), cacao (22–30°C), tomate (18–26°C).

La temperatura máxima captura episodios de estrés por calor que pueden quemar flores (aborto floral) y reducir el cuajado de frutos, incluso cuando la media semestral es tolerable. Un semestre con temperatura media de 22°C pero máximas de 38°C en dos semanas puede destruir la cosecha de tomate.

La temperatura mínima captura riesgo de heladas, crítico en el altiplano cundiboyacense. En zonas a más de 2.800 m, temperaturas mínimas por debajo de 0°C —incluso ocasionales— destruyen cultivos sensibles como fresa, arveja y flores de exportación.

**Evidencia del estado del arte:**
- Emmanuel N. et al. (2024) identifican temperatura como uno de los top-5 features por importancia en Random Forest para recomendación de cultivos. Los análisis SHAP muestran valores positivos para cultivos de zona cálida y negativos para cultivos de zona fría.
- Jeong et al. (2016) usan temperatura máxima (`maxt`) y mínima (`mint`) como predictores explícitos en modelos RF globales de rendimiento de trigo, maíz y papa.
- Hamza et al. (2025) reportan que temperatura, precipitación y humedad son los tres features más influyentes en su modelo híbrido RFXG para clasificación de cultivos con 99.71% de exactitud.

**Corrección adiabática (supuesto de diseño clave):**
Las estaciones IDEAM están en puntos fijos de altitud. Un píxel a 2.600 m sin estación cercana recibe la temperatura interpolada de la estación más próxima, que puede estar a 1.200 m. Sin corrección, el error sería de aproximadamente (2.600−1.200) × 0.006 = 8.4°C —la diferencia entre clasificar ese píxel como templado o frío. La corrección adiabática estándar (−6°C por cada 1.000 m de ascenso) es un fenómeno físico bien establecido por la termodinámica de la atmósfera.

#### 4.1.2 Precipitación Acumulada y CHIRPS

| Variable | Tipo | Fuente | Resolución bruta |
|---|---|---|---|
| `precip_ideam` | Float (mm) | IDEAM + Kriging | Puntual → 50 m |
| `chirps_acum` | Float (mm) | CHIRPS v3 | 5.3 km → 50 m |

**Por qué son importantes:**

La precipitación acumulada en el semestre es el indicador primario de disponibilidad hídrica para el cultivo. Los requerimientos varían enormemente: arroz de inundación necesita >800 mm por ciclo, maíz ~400–600 mm, trigo ~200–400 mm. Un semestre con precipitación insuficiente produce déficit hídrico que reduce rendimiento o mata el cultivo.

Se incluyen ambas fuentes porque son complementarias: IDEAM tiene mejor calibración en puntos con estación pero deja zonas sin datos; CHIRPS cubre uniformemente todo el territorio con estimación satelital continua desde 1981.

**Evidencia del estado del arte:**
- Kara et al. (2024) en AgroXAI identifican `rainfall` como el feature más importante (mayor valor SHAP) en modelos Random Forest y LightGBM para clasificación de 22 cultivos.
- Shams et al. (2024) en XAI-CROP confirman precipitación como feature #1 en el dataset estándar de 2.200 registros con 7 variables.
- Agrawal et al. (2023) asignan a la precipitación un peso de 5.59–10.37% en el análisis AHP de aptitud de tierras para trigo y mostaza.

#### 4.1.3 Humedad Relativa del Aire

| Variable | Tipo | Fuente |
|---|---|---|
| `humedad_media` | Float (%) | IDEAM + Kriging → 50 m |

**Por qué es importante:**

La humedad relativa afecta la transpiración del cultivo (baja humedad → mayor demanda hídrica → estrés), el desarrollo de enfermedades fungosas (alta humedad → botritis, mildiu), y la eficiencia fotosintética. En Cundinamarca, la alta nubosidad del semestre B (humedad >85%) es un factor limitante para cultivos que requieren buen drenaje y aireación.

**Evidencia del estado del arte:**
- Kara et al. (2024) identifican humedad como el feature más importante en análisis SHAP para clasificación de cultivos con RF y LGBM.
- Hamza et al. (2025) incluyen humedad en su conjunto de 7 features principales con correlación significativa con la clase de cultivo.

---

### Grupo 2 — Variables Edafológicas (Suelo)

**Objetivo dentro del proyecto:** Capturar las propiedades permanentes del suelo que determinan la fertilidad potencial, la disponibilidad de nutrientes y las condiciones físicas para el desarrollo radicular. A diferencia del clima, el suelo puede mejorarse parcialmente con enmiendas, pero su naturaleza base es un condicionante estructural.

Las propiedades edafológicas son estáticas en escala de años. Se calculan una vez y se reutilizan para todos los semestres.

#### 4.2.1 pH del Suelo

| Variable | Tipo | Fuente |
|---|---|---|
| `phh2o` (SoilGrids) | Float (pH 0–14) | SoilGrids 2.0 + IGAC |
| `igac_ph` (IGAC) | Categórico ordinal | IGAC 1:100.000 |

**Por qué es importante:**

El pH controla la disponibilidad de todos los nutrientes del suelo. A pH < 5.5 (ácido), el aluminio y el manganeso alcanzan concentraciones tóxicas para la mayoría de cultivos. A pH > 7.5 (alcalino), el hierro, zinc y manganeso se vuelven insolubles. El pH óptimo para la mayoría de cultivos es 6.0–7.0.

En Colombia, el IGAC reporta que el 84.1% de los suelos tienen pH ≤ 5.5. Esto significa que la toxicidad alumínica es la limitante química más frecuente en los suelos de Cundinamarca, y el pH es la variable que la resume.

**Evidencia del estado del arte:**
- Agrawal et al. (2023) le asignan la mayor ponderación AHP de todos los parámetros evaluados: 20.5% para trigo y 19.7% para mostaza.
- Hamza et al. (2025) incluyen pH en su conjunto de 7 features determinantes.
- Cartolano et al. (2024) demuestran mediante análisis SHAP que pH contribuye positiva o negativamente según el cultivo (valores altos favorecen cultivos de suelo neutro como espinaca; valores bajos favorecen arándanos).

#### 4.2.2 Nitrógeno Total

| Variable | Tipo | Fuente |
|---|---|---|
| `nitrogen` | Float (g/kg) | SoilGrids 2.0, 0–5 cm |

**Por qué es importante:**

El nitrógeno es el macronutriente primario: componente de clorofila, proteínas y ácidos nucleicos. Su deficiencia limita directamente la producción de biomasa. En suelos con bajo nitrógeno, incluso condiciones climáticas ideales no producen rendimientos aceptables sin fertilización.

**Evidencia del estado del arte:**
- Agrawal et al. (2023) asignan al nitrógeno la 2da mayor ponderación AHP después del pH: 12.42–17.27%.
- Mohan et al. (2024) demuestran relevancia de N en predicción de rendimiento de arroz bajo escenarios de cambio climático.
- Emmanuel N. et al. (2024) incluyen N junto con P y K en su "Soil Fertility Index" de feature engineering.

#### 4.2.3 Fósforo Disponible

| Variable | Tipo | Fuente |
|---|---|---|
| `igac_fosforo` | Categórico ordinal | IGAC (campo `P`) |

**Por qué es importante:**

El fósforo es esencial para el desarrollo radicular (energía ATP), la floración y la maduración de semillas. Su deficiencia retrasa la madurez y reduce el rendimiento, especialmente en cultivos de raíz (papa, yuca) y granos (maíz, fríjol). El IGAC reporta fósforo disponible por Bray o Mehlich-3 como rangos cualitativos.

**Evidencia del estado del arte:**
- Kara et al. (2024) identifican fósforo como el 2do feature más importante después de humedad en análisis SHAP para RF y LGBM.
- Agrawal et al. (2023) le asignan 10.66–12.42% de peso AHP.
- Cartolano et al. (2024) confirman que P y humedad son los más determinantes para clasificar manzana y otros cultivos específicos.

#### 4.2.4 Potasio Intercambiable

| Variable | Tipo | Fuente |
|---|---|---|
| `igac_potasio` | Categórico ordinal | IGAC (campo `K`) |

**Por qué es importante:**

El potasio regula la apertura de estomas, la resistencia a enfermedades, la calidad del fruto (firmeza, sabor, color) y la tolerancia al estrés hídrico y térmico. Su deficiencia es común en suelos arenosos o ácidos de Cundinamarca, especialmente en zonas de cultivos intensivos donde no se restituye con fertilización adecuada.

**Evidencia del estado del arte:**
- Agrawal et al. (2023) asignan 10.66–14.00% a K en AHP.
- Hamza et al. (2025) reportan correlación P-K de 0.74 en su análisis exploratorio, lo que sugiere que ambos son indicadores del mismo estado de fertilidad.
- Kara et al. (2024) identifican K como feature decisivo en explicaciones LIME para varios cultivos.

#### 4.2.5 Carbono Orgánico del Suelo (SOC)

| Variable | Tipo | Fuente |
|---|---|---|
| `soc` | Float (g/kg) | SoilGrids 2.0, 0–5 cm |

**Por qué es importante:**

El carbono orgánico del suelo es el indicador más integrado de salud del suelo: refleja actividad biológica, retención hídrica, porosidad y fertilidad potencial. Suelos con alto SOC tienen mayor capacidad buffer ante acidez y mayor disponibilidad de nutrientes mediante mineralización. En los páramos de Cundinamarca, el SOC puede superar 100 g/kg; en los valles áridos del Magdalena puede ser < 5 g/kg.

**Evidencia del estado del arte:**
- Agrawal et al. (2023) asignan 6.26–7.63% a materia orgánica/carbono.
- El Mapa Nacional de Stock de COS del IGAC (2017) reporta rangos de 10–264 t/ha en Colombia, confirmando alta variabilidad espacialmente relevante para la recomendación.

#### 4.2.6 Texturas: Arcilla, Arena, Limo

| Variable | Tipo | Fuente |
|---|---|---|
| `clay`, `sand`, `silt` | Float (%) | SoilGrids 2.0, 0–5 cm |

**Por qué son importantes:**

Las texturas determinan la capacidad de retención de agua (arcilla > limo > arena), el drenaje (arena > limo > arcilla), la aireación y la susceptibilidad a compactación. Cultivos como el arroz requieren suelos arcillosos que retienen agua; el maní y la mandioca prefieren suelos arenosos que drenan bien; la papa requiere suelos francos (equilibrio de los tres) para formación de tubérculos sin deformaciones.

Las tres variables se normalizan para que sumen 100% (corrección de errores de redondeo del producto SoilGrids).

**Evidencia del estado del arte:**
- Agrawal et al. (2023) incluyen textura del suelo con 3.40–4.26% de peso AHP.
- Jeong et al. (2016) usan arcilla como predictor en modelos globales de papa y maíz.
- La evaluación de aptitud de tierras FAO (1976) incluye clase textural como criterio primario de aptitud agrícola.

#### 4.2.7 Vocación de Uso (IGAC)

| Variable | Tipo | Fuente |
|---|---|---|
| `igac_vocacion` | Categórico (18 clases) | IGAC 1:100.000 |

**Por qué es importante:**

La vocación de uso es la síntesis oficial del potencial agrícola de cada unidad de suelo, integrando pendiente, textura, profundidad efectiva, pedregosidad, erosión, fertilidad, drenaje y régimen climático en una sola clasificación. Funciona como variable de alto nivel que encapsula el conocimiento experto del IGAC en formato directamente usable por el modelo, y también sirve como benchmark de validación: si el modelo recomienda un cultivo en zona de vocación forestal, esa discrepancia requiere revisión.

---

### Grupo 3 — Variables Satelitales (Percepción Remota)

**Objetivo dentro del proyecto:** Capturar el estado actual y la dinámica temporal de la vegetación y la superficie terrestre con observación directa desde el satélite, independientemente de las mediciones puntuales de estaciones. Los datos satelitales son los únicos que proveen información de alta resolución espacial con cobertura continua del territorio.

Las variables satelitales son dinámicas: se calculan por semestre y varían año a año reflejando tanto las condiciones climáticas del período como las prácticas agrícolas reales en cada píxel.

#### 4.3.1 Índices Espectrales de Sentinel-2

Para cada índice se calculan tres estadísticos por semestre: **media**, **máximo** y **desviación estándar** — dando 21 variables (7 índices × 3 estadísticos).

| Índice | Fórmula | Resolución nativa |
|---|---|---|
| NDVI | (B8−B4)/(B8+B4) | 10 m |
| GNDVI | (B8−B3)/(B8+B3) | 10 m |
| EVI | 2.5×(B8−B4)/(B8+6B4−7.5B2+1) | 10 m |
| NDWI | (B3−B8)/(B3+B8) | 10 m |
| MSAVI | (2B8+1−√((2B8+1)²−8(B8−B4)))/2 | 10 m |
| BSI | (B11+B4−B8−B2)/(B11+B4+B8+B2) | 20 m |
| SAVI | (B8−B4)/(B8+B4+0.5)×1.5 | 10 m |

**NDVI (Normalized Difference Vegetation Index):**
El índice de vegetación más establecido. Mide el verdor fotosintéticamente activo. Rango de −1 (agua, nieve) a +1 (vegetación densa). Es la "firma" de cobertura vegetal del píxel.

**GNDVI (Green NDVI):**
Reemplaza la banda roja por la verde. Más sensible a concentración de clorofila y contenido de nitrógeno foliar que NDVI. Útil para predecir rendimiento (un cultivo con más clorofila suele rendir más).

**EVI (Enhanced Vegetation Index):**
Corrige efectos atmosféricos y de suelo presentes en NDVI. Funciona mejor que NDVI en zonas de alta biomasa tropical donde NDVI satura (valor constante ~0.9 aunque la biomasa siga aumentando).

**NDWI (Normalized Difference Water Index):**
Detecta contenido de agua en la vegetación y cuerpos de agua superficiales. Crucial para identificar zonas de riego vs. secano, y para detectar parcelas de arroz inundado.

**MSAVI (Modified Soil Adjusted Vegetation Index):**
Minimiza la influencia del suelo desnudo en etapas tempranas del cultivo (siembra, emergencia). Más informativo que NDVI cuando la cobertura vegetal es < 30%.

**BSI (Bare Soil Index):**
Detecta suelo desnudo y composición mineral de la superficie. Útil para identificar parcelas en barbecho o recién preparadas para siembra.

**SAVI (Soil Adjusted Vegetation Index):**
Versión más simple de MSAVI con factor de corrección de suelo L=0.5. Estándar FAO para zonas áridas y semiáridas.

**Evidencia del estado del arte:**
- Iqbal et al. (2023) demuestran que combinando 10 bandas espectrales + 5 índices de Sentinel-2 en series temporales, modelos LSTM alcanzan 93%+ de precisión en clasificación de cultivos.
- Bolívar-Santamaría & Reu (2021) validan el uso de Sentinel-2 específicamente en los Andes colombianos para detectar sistemas agroforestales con 94% de precisión.
- Blickensdörfer et al. (2022) usan series temporales de S1+S2+Landsat para mapeo de tipos de cultivo en Alemania, confirmando la ventaja de datos multitemporales sobre imágenes únicas.

**Por qué tres estadísticos (media, máximo, desviación estándar):**
- La **media** representa el estado vegetativo típico del semestre.
- El **máximo** captura el pico de vigor (menos afectado por nubes que la media, ya que se toma el mejor mes).
- La **desviación estándar** mide la variabilidad temporal: alta variabilidad indica ciclos cortos (cultivos transitorios que se siembran y cosechan); baja variabilidad indica cultivos permanentes o pastizales.

#### 4.3.2 Backscatter SAR de Sentinel-1

| Variable | Tipo | Cálculo |
|---|---|---|
| `VV_dB` | Float (dB) | 10×log10(VV), media semestral |
| `VH_dB` | Float (dB) | 10×log10(VH), media semestral |
| `VH_VV_ratio_dB` | Float (dB) | VH_dB − VV_dB |

**Por qué son importantes:**

Sentinel-1 SAR penetra nubes, que es crítico en Cundinamarca donde la nubosidad puede superar el 70% del semestre B. Cuando Sentinel-2 produce NaN por nubes, Sentinel-1 provee información alternativa de la superficie.

- **VV (polarización vertical-vertical):** Sensible a la humedad superficial del suelo y a la rugosidad de la superficie. Suelos húmedos tienen mayor retrodispersión.
- **VH (polarización cruzada vertical-horizontal):** Más sensible a la estructura volumétrica de la vegetación (dosel, tallos). Permite diferenciar cultivos por arquitectura de planta.
- **Ratio VH/VV:** Normaliza efectos de humedad del suelo, resaltando la contribución de la vegetación al retorno radar. Discrimina tipos de cobertura vegetal de forma más robusta que VV o VH solos.

**Evidencia del estado del arte:**
- Van Tricht et al. (2018) demuestran que la combinación sinérgica S1+S2 mejora la clasificación de cultivos sobre cualquiera de las dos fuentes por separado.
- Khabbazan et al. (2019) usan Sentinel-1 para monitoreo de cultivos con cobertura nubosa, mostrando que SAR es el único recurso válido en regiones tropicales con alta nubosidad.
- Blickensdörfer et al. (2022) confirman que la fusión S1+S2+Landsat temporal proporciona los mejores resultados de clasificación en todos los tipos de cultivo evaluados.

---

### Grupo 4 — Variables Topográficas

**Objetivo dentro del proyecto:** Capturar las condiciones permanentes del relieve que determinan drenaje, exposición solar, riesgo de heladas y viabilidad de mecanización. La topografía es el "esqueleto" sobre el cual se organiza toda la variabilidad agroecológica de Cundinamarca.

Las variables topográficas son completamente estáticas (la elevación no cambia) y se calculan una sola vez para todo el proyecto.

#### 4.4.1 Elevación

| Variable | Tipo | Fuente |
|---|---|---|
| `elevacion` | Float (m.s.n.m.) | Copernicus DEM GLO-30 → 50 m |

**Por qué es importante:**

En Cundinamarca, la elevación va de ~200 m (Valle del Magdalena) a >3.900 m (páramos de Sumapaz). Esta variación de 3.700 m implica una diferencia de temperatura de ~22°C, que es más que la diferencia entre el ecuador y el polo ártico a nivel del mar. Ningún otro departamento colombiano tiene tanta variabilidad altitudinal en tan poco espacio.

La elevación es el proxy más directo del piso térmico y del régimen de temperaturas. También determina qué cultivos son biológicamente posibles: el cacao no puede sobrevivir por encima de 1.200 m; la papa de páramo no prospera por debajo de 2.000 m.

**Evidencia del estado del arte:**
- Agrawal et al. (2023) incluyen elevación con 2.02% de peso AHP.
- Emmanuel N. et al. (2024) proponen "Altitude-Adjusted Climate Metrics" como feature engineering crítico en zonas con alta variabilidad altitudinal.

#### 4.4.2 Pendiente

| Variable | Tipo | Cálculo |
|---|---|---|
| `pendiente` | Float (%) | Operador de Horn 3×3 sobre DEM |

**Por qué es importante:**

La pendiente determina: (1) susceptibilidad a erosión hídrica —pendientes >25% son consideradas de alto riesgo por el IDEAM; (2) viabilidad de mecanización —tractores estándar operan hasta ~15%, maquinaria especializada hasta ~30%; (3) drenaje superficial —pendientes muy suaves (<1%) se encharcan.

El IGAC usa pendiente como criterio primario en su sistema de clasificación de Vocación de Uso. La normativa colombiana de zonificación agrícola establece umbrales específicos por pendiente.

**Evidencia del estado del arte:**
- Agrawal et al. (2023) asignan 2.85–2.90% a pendiente en AHP.
- La evaluación de aptitud FAO (1976) incluye clase de pendiente como factor limitante de clase 1 o 2 según su severidad.

#### 4.4.3 Aspecto

| Variable | Tipo | Cálculo |
|---|---|---|
| `aspecto` | Float (°, 0=Norte, sentido horario) | arctan2(dz/dy, dz/dx) |

**Por qué es importante:**

El aspecto determina la exposición solar de la ladera. En el hemisferio norte (Cundinamarca está entre 3.7° y 5.8°N), las diferencias de radiación solar entre laderas norte y sur son pequeñas pero significativas en zonas de montaña. Las laderas orientadas al este reciben sol de mañana y tienden a ser más secas (evapotranspiración matutina alta); las del oeste reciben la tarde. En zonas de páramo, las laderas norte tienen más riesgo de heladas nocturnas por mayor pérdida de calor radiativo.

#### 4.4.4 TWI (Topographic Wetness Index)

| Variable | Tipo | Cálculo |
|---|---|---|
| `twi` | Float (adimensional) | ln(área_drenaje / tan(pendiente)) |

**Por qué es importante:**

El TWI es el indicador topográfico más informativo sobre acumulación de humedad en el suelo. Integra la posición en la cuenca (cuánta agua drena hacia ese punto desde aguas arriba) con la pendiente local (cuánto tiempo retiene esa agua). Valores altos de TWI (>10) indican zonas húmedas potencialmente inundables —aptas para arroz de secano o inadecuadas para cultivos que requieren drenaje. Valores bajos (<4) indican crestas bien drenadas.

---

### Grupo 5 — Variables Derivadas (Feature Engineering)

**Objetivo dentro del proyecto:** Codificar conocimiento agronómico experto en variables que los algoritmos pueden usar directamente, sin necesidad de inferir relaciones complejas entre múltiples features primitivos. Cada variable derivada es una transformación que explicita una relación que existe en los datos pero que sería difícil de aprender automáticamente.

#### 4.5.1 Piso Térmico

| Variable | Tipo | Cálculo |
|---|---|---|
| `piso_termico` | Categórico (0–3) | umbralización de elevación |

- 0 = Cálido: < 1.000 m
- 1 = Templado: 1.000–2.000 m
- 2 = Frío: 2.000–3.000 m
- 3 = Páramo: > 3.000 m

**Por qué es importante:**

El piso térmico es la variable más determinante de la aptitud agrícola en Cundinamarca. Es una convención del IGAC y el MADR que organiza estructuralmente qué cultivos son posibles en cada zona. El arroz y el cacao solo existen en piso cálido; el café en templado; la papa en frío; el páramo tiene vocación de conservación.

Al precomputar esta clasificación se incorpora el conocimiento experto de la agronomía colombiana como feature categórico que el modelo puede usar directamente como divisor del espacio de decisión, en lugar de tener que aprender la discontinuidad implícita en la elevación continua.

**Evidencia del estado del arte:**
- Emmanuel N. et al. (2024) proponen clasificaciones agroecológicas derivadas como feature engineering que mejora la generalización del modelo en zonas diversas.

#### 4.5.2 Amplitud Térmica Semestral

| Variable | Tipo | Cálculo |
|---|---|---|
| `amplitud_termica` | Float (°C) | temp_max_media − temp_min_media del semestre |

**Por qué es importante:**

La amplitud térmica indica el diferencial diurno-nocturno de temperatura, que afecta directamente la calidad del cultivo. Las plantas acumulan carbohidratos (azúcares) de día por fotosíntesis, pero los consumen por respiración de noche. Una noche fría reduce la respiración, acumulando más azúcares netos —esto explica la calidad excepcional de las papas y fresas del páramo de Cundinamarca (amplitud de 12–18°C) frente a las de tierra caliente (amplitud de 4–8°C).

**Evidencia del estado del arte:**
- Emmanuel N. et al. (2024) incluyen métricas climáticas ajustadas por altitud que capturan el régimen térmico diurno-nocturno como feature engineering clave.

#### 4.5.3 Índice de Fertilidad Compuesto

| Variable | Tipo | Cálculo |
|---|---|---|
| `indice_fertilidad` | Float (0–1) | 0.25×N_norm + 0.25×pH_opt + 0.25×CEC_norm + 0.25×SOC_norm |

Donde `pH_opt = 1 − |pH − 6.5| / 3.5` (distancia al pH óptimo de 6.5).

**Por qué es importante:**

Resume la fertilidad del suelo en una dimensión interpretable. Las cuatro variables de suelo son complementarias pero correlacionadas (suelos con alto N tienden a tener alto SOC). El índice compuesto: (1) reduce la dimensionalidad de 4 variables a 1; (2) minimiza multicolinealidad; (3) facilita la explicabilidad SHAP —un agro-extensionista puede entender "fertilidad = 0.7" más fácilmente que cuatro valores de N, pH, CEC y SOC.

Los pesos iguales (0.25 cada uno) reflejan la equiponderación en ausencia de datos que permitan estimar pesos óptimos específicos para Cundinamarca.

**Evidencia del estado del arte:**
- Emmanuel N. et al. (2024) proponen explícitamente un "Soil Fertility Index" compuesto de N, P y K como feature engineering.
- Agrawal et al. (2023) demuestran que los pesos óptimos por AHP son 20.5% para pH, 17.27% para N, 12.42% para P y K —justificando la inclusión de estas cuatro variables en el índice.

#### 4.5.4 Anomalía de Precipitación

| Variable | Tipo | Cálculo |
|---|---|---|
| `anomalia_precip` | Float (σ) | (precip_sem − media_historica_sem) / σ_historica_sem |

**Por qué es importante:**

La precipitación absoluta no distingue si un semestre fue "normal" o "excepcional". La anomalía captura la variabilidad interanual: cuántas desviaciones estándar se apartó el semestre de su normal histórica. Un semestre con −2σ indica sequía severa; +2σ indica lluvias excepcionales.

Esta variable permite que el modelo generalice entre años: si en 2021 hubo sequía (anomalía = −1.8) y los cultivos de maíz fracasaron, y en 2022 fue normal (anomalía = 0.1) y el maíz prosperó, el modelo aprende que la anomalía es el predictor, no el año.

**Evidencia del estado del arte:**
- Hasan et al. (2023) y Mohan et al. (2024) integran variabilidad climática interanual para mejorar robustez del modelo frente a años anómalos.
- Kern et al. (2018) usan anomalías climáticas en modelos estadísticos de rendimiento en Europa Central.

#### 4.5.5 NDVI Máximo Semestral

| Variable | Tipo | Cálculo |
|---|---|---|
| `ndvi_max` | Float (−1 a 1) | max(NDVI mensual), excluyendo NaN |

**Por qué es importante:**

El NDVI máximo captura el pico de vigor vegetativo del semestre —el mejor momento observable de la vegetación en ese período. Es más informativo que la media porque:
- La media se degrada con meses nublados (NaN o valores bajos por nubosidad parcial).
- El máximo toma solo el mes con mejor observación, representando el potencial real del píxel.

Para cultivos de ciclo corto, el NDVI máximo corresponde al estado de mayor cobertura antes de la cosecha. Para cultivos permanentes, es el pico de la temporada de crecimiento.

**Evidencia del estado del arte:**
- Iqbal et al. (2023) procesan series temporales de índices y demuestran que los estadísticos máximos tienen mayor poder discriminatorio que las medias en clasificación de cultivos.

#### 4.5.6 Integral de NDVI Semestral

| Variable | Tipo | Cálculo |
|---|---|---|
| `ndvi_integral` | Float (días de verdor equivalentes) | Σ(NDVI_mensual × 30 días) |

**Por qué es importante:**

La integral de NDVI es el proxy estándar de producción primaria neta (PPN) en teledetección. Acumula el verdor durante todo el semestre, distinguiendo patrones fenológicos:
- Cultivo transitorio: integral baja (solo verde durante el ciclo de 3–4 meses).
- Cultivo permanente (café, cacao, plátano): integral alta (verde todo el semestre).
- Pastizal: integral media-alta con baja variabilidad.

**Evidencia del estado del arte:**
- Kern et al. (2018) usan la integral de índices de vegetación como predictor de rendimiento en modelos estadísticos para Europa Central.

#### 4.5.7 Índice de Aridez

| Variable | Tipo | Cálculo |
|---|---|---|
| `indice_aridez` | Float | precipitación_acumulada / ETP_Hargreaves |

Donde ETP se estima por el método de Hargreaves: `ETP = 0.0023 × Ra × (Tmed + 17.8) × (Tmax − Tmin)^0.5`

**Por qué es importante:**

La precipitación absoluta no captura el balance hídrico real: 600 mm pueden ser excesivos en una zona fría con baja evapotranspiración, o insuficientes en una zona cálida con alta demanda. El índice de aridez integra oferta (precipitación) y demanda (ETP) en un solo número que clasifica el balance hídrico:
- < 0.5: árido (déficit severo)
- 0.5–1.0: semiárido (déficit moderado)
- > 1.0: húmedo (balance positivo)

**Por qué Hargreaves y no Penman-Monteith:**
Penman-Monteith es más preciso pero requiere velocidad del viento y radiación solar a alta resolución —datos no disponibles de forma uniforme en Cundinamarca. Hargreaves solo necesita temperaturas máxima, mínima y media, que sí están disponibles con cobertura completa. Para los fines de este sistema, la precisión relativa de Hargreaves (correlación ~0.89 con Penman en zonas tropicales) es suficiente.

**Evidencia del estado del arte:**
- Jeong et al. (2016) incluyen evapotranspiración como predictor en modelos RF de rendimiento a escala global.

---

## 5. Estructura Consolidada de la Vista Minable

La tabla final contiene las siguientes columnas:

### Columnas de Identificación

| Columna | Tipo | Descripción |
|---|---|---|
| `pixel_id` | Int64 | Identificador único del píxel (índice lineal en el grid) |
| `row`, `col` | Int32 | Coordenadas en el grid raster |
| `lon`, `lat` | Float64 | Coordenadas WGS84 del centroide del píxel |
| `semestre` | String | Etiqueta del semestre (e.g., "2021B") |

### Columnas de Features Estáticos (~30)

| Grupo | Variables |
|---|---|
| Topografía | `elevacion`, `pendiente`, `aspecto`, `curvatura`, `twi` |
| SoilGrids | `phh2o`, `soc`, `nitrogen`, `cec`, `bdod`, `ocd` + 3 texturas normalizadas |
| IGAC | `igac_ph`, `igac_fosforo`, `igac_potasio`, `igac_vocacion`, `igac_fertilidad`, `igac_ucsuelo`, `igac_subgrupo`, `igac_paisaje` + otros según disponibilidad |
| Derivados estáticos | `piso_termico`, `indice_fertilidad` |

### Columnas de Features Dinámicos por Semestre (~40)

| Grupo | Variables |
|---|---|
| Clima IDEAM | `temp_media`, `temp_max`, `temp_min`, `humedad_media`, `precip_ideam` |
| Clima CHIRPS | `chirps_acum` |
| Sentinel-2 | 7 índices × 3 estadísticos = `NDVI_mean`, `NDVI_max`, `NDVI_std`, `GNDVI_mean`, ... |
| Sentinel-1 | `VV_dB`, `VH_dB`, `VH_VV_ratio_dB` |
| Derivados dinámicos | `amplitud_termica`, `anomalia_precip`, `ndvi_max`, `ndvi_integral`, `indice_aridez` |

### Columnas de Target

| Columna | Tipo | Descripción |
|---|---|---|
| `cultivo_id` | Int16 | Código entero del cultivo (referencia en catálogo JSON) |
| `cultivo_nombre` | String | Nombre del cultivo |
| `confianza_label` | Float32 | Calidad de la etiqueta (1.0=monitoreo, 0.7=EVA, 0.2–0.5=SIPRA) |
| `fuente_label` | String | Fuente de la etiqueta (`monitoreo`, `eva`, `sipra`) |

**Total estimado:** ~74 features base, expandible a ~120 con todos los estadísticos mensuales.

---

## 6. Limitaciones y Mitigaciones

| Limitación | Impacto | Mitigación |
|---|---|---|
| Resolución 50 m de Sentinel | Parcelas menores a ~0.25 ha no son representadas correctamente | Solo relevante para horticultura de alto valor; no afecta los cultivos extensivos principales |
| EVA no espacializada (nivel municipal) | Ruido en etiquetas: se asume que el cultivo más reportado en el municipio corresponde a los píxeles compatibles | Confianza reducida (0.7); volumen de datos permite que el modelo aprenda la señal sobre el ruido |
| SIPRA es modelización, no observación | Puede estar desactualizado o ser impreciso en zonas específicas | Confianza mínima (0.2–0.5); solo como respaldo de último recurso |
| Alta nubosidad Cundinamarca en S2 | NaN en features satelitales ópticos en meses con nubosidad >90% | Se requieren ≥2 meses válidos por semestre; Sentinel-1 SAR complementa donde S2 falla |
| Pocas estaciones IDEAM en zonas remotas | Mayor incertidumbre en la interpolación Kriging en páramos y Valle del Magdalena | CHIRPS cubre esas zonas; corrección adiabática reduce error sistemático en montaña |
| `preProcessScenes` bug en CDSE | Todos los archivos S2 descargados con el evalscript incorrecto tienen 100% de valores cero | Re-descarga con evalscript corregido (sin `preProcessScenes`); validación con MD5 y estadísticos básicos |

---

## 7. Referencias Bibliográficas

Agrawal, N., Govil, H., & Kumar, T. (2023). Agricultural land suitability classification and crop suggestion using GIS and AHP. *Environment, Development and Sustainability*, 25, 13695–13726.

Blickensdörfer, L., et al. (2022). Mapping of crop types and crop sequences with combined time series of Sentinel-1, Sentinel-2 and Landsat 8 data for Germany. *Remote Sensing of Environment*, 269, 112831.

Bolívar-Santamaría, S. & Reu, B. (2021). Detection and characterization of agroforestry systems in the Colombian Andes using Sentinel-2 imagery. *Agroforestry Systems*, 95, 499–514.

Cartolano, A., Cuzzocrea, A., & Pilato, G. (2024). Analyzing and assessing explainable AI models for smart agriculture environments. *Multimedia Tools and Applications*, 83, 37225–37246.

Emmanuel N., et al. (2024). Crop Recommendation Model Using Machine Learning. *Int. J. of Latest Scientific Research and Publications*, 709–714.

FAO. (1976). *A Framework for Land Evaluation*. Soils Bulletin 32. Food and Agriculture Organization, Rome.

Hamza, A., et al. (2025). Soil type crop recommendation using hybrid ML model. *Scientific Reports*, 15, 8560.

Hasan, M., et al. (2023). Ensemble machine learning-based recommendation system for effective prediction of suitable agricultural crop cultivation. *Frontiers in Plant Science*, 14, 1234555.

IGAC. (2017). *Mapa Nacional de Stock de Carbono Orgánico del Suelo de Colombia*. Instituto Geográfico Agustín Codazzi.

Iqbal, N., et al. (2023). Crop identification using multi-temporal Sentinel-2 data and machine learning. *Sensors*, 23, 1779.

Jeong, J. H., et al. (2016). Random Forests for Global and Regional Crop Yield Predictions. *PLOS ONE*, 11(6), e0156571.

Kara, M., et al. (2024). AgroXAI: An Edge Computing-Based Explainable Crop Recommendation System. *Preprint arXiv*, 2412.16196.

Kern, A., et al. (2018). Statistical modelling of crop yield in Central Europe using climate data and remote sensing vegetation indices. *Agricultural and Forest Meteorology*, 260–261, 300–320.

Khabbazan, S., et al. (2019). Crop monitoring using Sentinel-1 data: a case study from The Netherlands. *Remote Sensing*, 11, 1887.

Mohan, P., et al. (2024). AI-driven climate change impact prediction on agricultural yields using XAI. *Frontiers in Plant Science*, 15, 1451607.

Shams, M. Y., Gamel, S. A. & Talaat, F. M. (2024). Enhancing crop recommendation systems with explainable AI. *Neural Computing and Applications*, 36, 5695–5714.

Van Tricht, K., et al. (2018). Synergistic use of radar Sentinel-1 and optical Sentinel-2 imagery for crop mapping. *Remote Sensing*, 10, 1642.

Venancio, L. P., et al. (2019). Forecasting corn yield at the farm level based on FAO-66 and SAVI. *Agricultural Water Management*, 225, 105779.

---

*Documento técnico del proyecto «¿Qué Sembrar?» — Plataforma de Planificación Agrícola para Cundinamarca, Colombia, 2026.*
