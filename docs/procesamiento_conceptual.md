# Procesamiento de Datos — Explicación Conceptual
## Módulo «¿Qué Sembrar?» | Cundinamarca, Colombia

> Este documento explica **qué hace** cada etapa del pipeline de procesamiento, **por qué** se toma cada decisión de diseño, y **cómo se justifica** cada feature en términos agronómicos y estadísticos. No contiene código.

---

## Visión General del Pipeline

El problema central es el siguiente: tenemos datos geoespaciales de fuentes heterogéneas —estaciones meteorológicas puntuales, imágenes satelitales, mapas de suelo, registros agrícolas históricos— y necesitamos convertirlos en una tabla rectangular donde cada fila describe completamente las condiciones de un lugar específico en un semestre específico, y la columna final diga qué cultivo fue exitoso ahí. Esa tabla es lo que alimentará los modelos de machine learning.

El pipeline tiene cuatro pasos en secuencia:

```
Datos crudos (múltiples formatos, resoluciones, CRS)
        ↓
[01] Armonización Espacial     → todos al mismo grid 10m EPSG:3116
        ↓
[02] Agregación Temporal       → mensuales → estadísticos semestrales
        ↓
[03] Feature Engineering       → variables derivadas con significado agronómico
        ↓
[04] Construcción Vista Minable → tabla Parquet: (píxel, semestre) → cultivo
```

---

## Paso 1 — Armonización Espacial

### El Problema que Resuelve

Imagine intentar comparar un termómetro con una imagen satelital: el termómetro te da un número para toda la ciudad, la imagen te da un número por cada cuadro de 10 metros. Si quieres saber la temperatura en ese cuadro de 10 metros, tienes que interpolar. Ahora multiplique ese problema por ocho fuentes de datos completamente distintas, en proyecciones cartográficas distintas, con resoluciones que van de 250 metros (SoilGrids) a 10 metros (Sentinel) pasando por puntos sin extensión (estaciones IDEAM). Sin armonización, ninguna comparación entre fuentes es matemáticamente válida.

La armonización espacial resuelve esto llevando **todos los datos al mismo sistema de coordenadas, la misma resolución y el mismo encuadre geográfico**.

### Por Qué EPSG:3116 y 10 Metros

**EPSG:3116 (MAGNA-SIRGAS Colombia Bogotá)** es la proyección oficial del IGAC para Cundinamarca. Al ser una proyección plana métrica, un píxel siempre mide exactamente 10m × 10m sin importar en qué parte del departamento esté. Las proyecciones geográficas (latitud/longitud) no tienen esta propiedad: un grado de longitud mide menos metros cerca de los polos que en el ecuador. Para calcular pendientes, distancias entre estaciones, o hacer convoluciones sobre el ráster, las unidades métricas exactas son indispensables.

**10 metros** es la resolución nativa de Sentinel-2, la fuente de datos de mayor resolución del proyecto. Fijar 10m como estándar significa que nunca se inventa información —si una fuente tiene 250m de resolución original, sus píxeles se remuestrean a 10m pero el contenido de información real sigue siendo el de 250m. Lo opuesto habría sido degradar Sentinel-2 a, digamos, 250m para que todo fuera igual: eso sí destruiría información real.

### Cómo se Trata Cada Fuente

**Estaciones IDEAM → Kriging Ordinario con corrección adiabática:**
Las estaciones son puntos sin extensión. Hay entre 30 y 60 estaciones activas en Cundinamarca para un territorio de 24.000 km². Kriging Ordinario es el mejor interpolador espacial lineal insesgado cuando la variable tiene autocorrelación espacial —y temperatura y precipitación la tienen por definición: dos estaciones cercanas se parecen más que dos estaciones lejanas. El Kriging ajusta automáticamente un variograma que captura esa estructura de correlación.

La corrección adiabática es crítica para temperatura: Cundinamarca va de 200m de altitud (Valle del Magdalena) a 3.900m (páramos de Sumapaz), una diferencia de más de 22°C que ninguna red de estaciones puede capturar completamente. El gradiente adiabático seco (−6°C por cada 1.000m de ascenso) es un fenómeno físico bien establecido. Sin esta corrección, el mapa de temperatura tendría errores sistemáticos en zonas de montaña donde las estaciones son escasas.

La interpolación se hace en dos etapas: primero a 1 km (manejable en RAM) y luego se remuestrea bilinealmente a 10m. Aplicar Kriging directamente a 10m requeriría matrices de millones de elementos, computacionalmente inviable.

**CHIRPS → Resampling bilineal desde 5.3 km:**
CHIRPS combina imágenes infrarrojas de satélite con datos de estaciones terrestres para estimar precipitación. Su resolución original de ~5.3 km es mucho más gruesa que 10m, pero la interpolación bilineal es correcta aquí porque la precipitación varía de forma continua y suave a esa escala. CHIRPS complementa el IDEAM porque cubre uniformemente todo el territorio, incluyendo zonas sin estaciones.

**SoilGrids → Bilineal para continuos, Nearest-Neighbor para texturas:**
SoilGrids provee propiedades de suelo a 250m. Para variables continuas como pH, carbono orgánico o capacidad de intercambio catiónico, la interpolación bilineal es apropiada porque los valores intermedios tienen sentido físico. Para texturas (arcilla, arena, limo), se usa Nearest-Neighbor: no existe un suelo con exactamente "30% arcilla" entre un suelo de "40% arcilla" y uno de "20% arcilla" —cada valor de textura corresponde a un horizonte real de suelo con su propia historia geológica.

Además, las texturas se normalizan para que arcilla + arena + limo = 100% en cada píxel. Los errores de redondeo en el producto original pueden violar esta restricción, lo que introduciría inconsistencias en los modelos.

**IGAC → Rasterización de polígonos:**
El IGAC produce mapas vectoriales de unidades de suelo. Cada polígono tiene atributos como pH, fósforo, potasio, vocación de uso. Para integrarlos al grid de 10m, se "pinta" cada polígono sobre el ráster: todos los píxeles dentro de ese polígono reciben el valor del atributo correspondiente. Los campos categóricos (fertilidad, vocación) se codifican como enteros con una tabla de correspondencia que se guarda en JSON. Los campos del IGAC son rangos textuales ("≤ 5.5", "5.5–6.0") porque el mapa original es cualitativo —se tratan como categóricos, no como numéricos continuos.

**Sentinel-2 y Sentinel-1 → Descarga por tiles a 10m real:**
El extractor no descarga una imagen de baja resolución y la escala artificialmente. Descarga Cundinamarca en ~80 tiles de ~24km cada uno, a resolución real de 10m por tile, y los fusiona. Esto garantiza que cada píxel contiene información real del sensor. La reproyección posterior (de WGS84 a EPSG:3116) preserva esa resolución nativa.

---

## Paso 2 — Agregación Temporal

### El Problema que Resuelve

Después del paso 1, tenemos rásteres mensuales: 72 imágenes de temperatura, 72 de precipitación, 72 de NDVI, etc. (12 meses × 6 años). Los modelos ML trabajan con una fila por observación —un (píxel, semestre). Necesitamos resumir esos 6 meses en estadísticos que capturen lo que importa agronómicamente en ese período.

### Por Qué Semestral y No Mensual

Los modelos tabulares (Random Forest, XGBoost, LightGBM, TabNet) no entienden secuencias —para ellos, cada columna es independiente. Si se pusieran los 72 meses como 72 columnas separadas, el modelo no sabría que "temperatura enero 2020" y "temperatura febrero 2020" son consecutivas y están relacionadas. El LSTM sí entiende secuencias, por eso recibe datos mensuales directamente (se explica en el paso de entrenamiento).

El semestre agrícola (enero–junio, julio–diciembre) es la unidad natural de planificación en Colombia: las evaluaciones agropecuarias (EVA) registran producción por semestre, el IDEAM reporta balances por semestre, y los agricultores toman decisiones de siembra semestralmente siguiendo el calendario bimodal de lluvias de Cundinamarca.

Los rásteres mensuales **no se eliminan** —son necesarios para el LSTM y para los features de NDVI del paso 3.

### Qué Estadístico se Calcula y Por Qué

**Temperatura — media, máximo, mínimo:**
- La **media** caracteriza el régimen térmico general del semestre, determinante para la aptitud de la mayoría de cultivos (maíz prospera entre 20–30°C, papa entre 10–20°C).
- El **máximo** captura episodios de calor extremo que pueden quemar flores y reducir rendimiento, aunque la temperatura media sea tolerable.
- El **mínimo** captura riesgo de heladas, crítico para cultivos sensibles como fresa o tomate en zonas de páramo.
Los tres juntos describen el régimen térmico de forma más completa que cualquiera por separado.

**Precipitación — acumulado:**
Para precipitación, lo que importa agronómicamente es el **total disponible** en el período. Un mes con 200mm seguido de uno con 50mm no es igual a dos meses con 125mm (estrés hídrico), pero para la decisión de qué sembrar en un semestre, la suma es el indicador primario de disponibilidad de agua.

**Humedad relativa — media:**
La humedad media afecta la transpiración de los cultivos, el desarrollo de enfermedades fungosas y la eficiencia hídrica. Un valor promedio semestral es suficiente para capturar si el ambiente es húmedo o seco como característica del lugar.

**Sentinel-2 — media, máximo, desviación estándar por índice:**
- La **media** representa el estado vegetativo típico del semestre.
- El **máximo** captura el pico de vigor, importante para cultivos que tienen una fase de crecimiento intenso.
- La **desviación estándar** mide la variabilidad: un NDVI muy variable indica cultivos de ciclo corto que se siembran y cosechan dentro del semestre; un NDVI estable indica cultivos permanentes o pastizales.

**Sentinel-1 — media:**
El backscatter SAR (radar) penetra nubes, lo que es fundamental en Cundinamarca donde la nubosidad puede superar el 70% en el semestre B. La media semestral de la señal VV (polarización vertical) y VH (cruzada) caracterizan la estructura del dosel y la humedad del suelo de forma complementaria a las imágenes ópticas.

---

## Paso 3 — Feature Engineering

### Por Qué Crear Features Derivadas

Los modelos pueden aprender relaciones complejas, pero aprenden mejor y más rápido cuando las relaciones ya están explicitadas en los datos. Un modelo podría en teoría aprender que "temperatura media 15°C + elevación 2500m → zona fría apta para papa", pero si le damos directamente la variable "piso térmico = frío", la relación es inmediata y el modelo necesita menos datos para capturarla. Las features derivadas codifican conocimiento agronómico experto en el formato que el modelo puede usar más eficientemente.

### Feature 1 — Piso Térmico

**Qué es:** Clasificación de cada píxel en cuatro categorías según su altitud:
- Cálido: por debajo de 1.000m sobre el nivel del mar
- Templado: entre 1.000 y 2.000m
- Frío: entre 2.000 y 3.000m
- Páramo: por encima de 3.000m

**Por qué importa:** El piso térmico es la variable más determinante de la aptitud agrícola en Cundinamarca. Es el concepto que estructuralmente organiza qué cultivos son posibles en cada zona del departamento. El arroz y el cacao solo existen en pisos cálidos. El café habita principalmente el templado. La papa y la arveja son cultivos de piso frío. El páramo tiene vocación de conservación, no agrícola.

**Por qué no usar solo la elevación:** La elevación es continua y el modelo tiene que aprender sola la discontinuidad entre pisos. Al precomputar la clasificación, estamos incorporando el conocimiento experto de la agronomía colombiana (los pisos térmicos son convenciones establecidas por el IGAC y el MADR) en una variable que el modelo puede usar directamente como feature categórica.

**Decisión de diseño:** Se calcula una sola vez (es estático, la elevación no cambia) y se almacena. Todos los modelos lo usarán para segmentar su espacio de decisión.

### Feature 2 — Amplitud Térmica

**Qué es:** La diferencia entre la temperatura máxima media y la temperatura mínima media del semestre, en grados Celsius.

**Por qué importa:** La amplitud térmica es un indicador de la calidad del cultivo, no solo de su aptitud. Los cultivos producen azúcares y sabores más intensos cuando las noches son frescas y los días son cálidos: la planta acumula carbohidratos de día (fotosíntesis activa) y los consume menos de noche (respiración reducida). Esto explica por qué las papas de páramo en Cundinamarca tienen mejor calidad que las de tierra caliente: alta amplitud térmica. La fresa de Cundinamarca compite internacionalmente por la misma razón.

**Por qué no está ya en los datos:** Tenemos temperatura máxima y mínima por separado, pero la diferencia tiene un significado agronómico propio que el modelo no inferiría tan fácilmente calculándola implícitamente de dos columnas.

**Decisión de diseño:** Se calcula por semestre porque la amplitud varía entre el semestre seco (B: julio–diciembre, más variable) y el lluvioso (A: enero–junio, más estable con la cobertura nubosa).

### Feature 3 — Índice de Fertilidad

**Qué es:** Un número entre 0 y 1 que resume la fertilidad del suelo combinando cuatro propiedades de SoilGrids a 0–5 cm de profundidad:
- Nitrógeno total (N): nutriente primario, limitante principal del crecimiento
- pH optimizado: qué tan cercano está el pH a 6.5, el óptimo para la mayoría de cultivos
- Capacidad de intercambio catiónico (CEC): capacidad del suelo de retener nutrientes
- Carbono orgánico del suelo (SOC): materia orgánica, proxy de actividad biológica

Cada componente se normaliza entre 0 y 1 usando los percentiles 2 y 98 del departamento (para ser robusto ante outliers). El pH tiene un tratamiento especial: no se normaliza linealmente sino que se calcula la distancia al óptimo de 6.5 —tanto la acidez extrema como la alcalinidad extrema son malas.

**Por qué importa:** La fertilidad del suelo determina directamente el rendimiento potencial independientemente del clima. Un suelo pobre puede limitar el rendimiento incluso en condiciones climáticas perfectas. En Cundinamarca, los suelos ácidos con alta saturación de aluminio son una limitante crítica para muchos cultivos.

**Por qué un índice compuesto y no las variables por separado:** Las cuatro variables de suelo son complementarias pero también correlacionadas (suelos con alto N tienden a tener alto SOC). Un índice compuesto con pesos iguales (0.25 cada uno) resume la fertilidad en una dimensión interpretable, reduce la multicolinealidad y facilita la explicabilidad SHAP. Los pesos iguales reflejan que, en ausencia de datos que permitan estimar pesos óptimos específicos para Cundinamarca, la equiponderación es la elección más conservadora e interpretable.

**Decisión de diseño:** Es estático (el suelo no cambia semestre a semestre en escala de años). Solo se calcula una vez.

### Feature 4 — Anomalía de Precipitación

**Qué es:** Cuántas desviaciones estándar se aleja la precipitación de un semestre de la normal histórica para ese tipo de semestre. Un valor de +2 significa que fue un semestre excepcionalmente lluvioso. Un valor de −1.5 significa que fue seco.

**Por qué importa:** Un cultivo que funciona bien en un semestre "normal" puede fracasar en un semestre con déficit hídrico severo, o al contrario, sufrir pudrición de raíz en uno excepcionalmente lluvioso. Los modelos que no capturan la variabilidad interanual aprenden correlaciones espurias. Si en 2020 hubo sequía y los cultivos de maíz fracasaron, y en 2021 hubo lluvia normal y el maíz prosperó, el modelo necesita saber que la diferencia fue la anomalía de precipitación, no el maíz en sí.

**Por qué separar semestres A y B:** En Cundinamarca, el semestre A (enero–junio) corresponde al primer ciclo de lluvias (pico en abril–mayo) y el semestre B (julio–diciembre) al segundo (pico en octubre–noviembre). La "normalidad" es distinta para cada uno: comparar un semestre B con la normal de semestres A sería estadísticamente incorrecto. La anomalía se calcula dentro de cada tipo.

**Decisión de diseño:** Se usa CHIRPS y no IDEAM para la precipitación de este cálculo porque CHIRPS tiene cobertura espacial uniforme (no depende de que haya estaciones), lo que hace la comparación más consistente entre zonas con distinta densidad de estaciones.

### Feature 5 — NDVI Máximo del Semestre

**Qué es:** El valor más alto que alcanzó el índice de vegetación normalizado (NDVI) en cualquiera de los 6 meses del semestre.

**Por qué importa:** El NDVI máximo es un proxy del vigor vegetativo pico: cuánto verde "puro" alcanzó la vegetación en su mejor momento del semestre. Un píxel con NDVI máximo de 0.8 tiene una cobertura vegetal densa y activa. Uno con máximo de 0.3 tiene vegetación escasa o estresada. Para cultivos como la papa, el pico de NDVI coincide con el cierre del dosel, momento crítico de acumulación de tubérculos.

**Por qué el máximo y no la media:** La media puede ser baja por nubes (valores NaN o cero en meses nublados). El máximo captura el mejor momento observable del semestre, que es más informativo sobre el potencial del píxel que el promedio de observaciones parciales.

**Tratamiento de nubes:** Los píxeles con valor cero en Sentinel-2 corresponden a zonas cubiertas por nubes sin datos reales. Se reemplazan por NaN antes de calcular el máximo, para que las nubes no contaminen la estadística.

### Feature 6 — Integral de NDVI

**Qué es:** La suma de los valores mensuales de NDVI multiplicada por 30 días. Representa el área bajo la curva de verdor durante el semestre.

**Por qué importa:** La integral de NDVI es el proxy estándar de la producción primaria neta (PPN) en teledetección. Un cultivo de ciclo corto que crece rápido, se cosecha y deja el suelo desnudo tiene una integral baja aunque su NDVI máximo haya sido alto. Un cultivo permanente como el café mantiene follaje todo el año y acumula una integral alta. Esta variable permite distinguir cultivos por su patrón fenológico, no solo por su estado en un momento dado.

**Por qué en unidades de días:** Multiplicar por 30 transforma la suma de índices sin unidades en una métrica de "días equivalentes de verdor máximo", que es más interpretable para agrónomos que un número adimensional.

### Feature 7 — Índice de Aridez

**Qué es:** La razón entre la precipitación acumulada del semestre y la evapotranspiración potencial (ETP) estimada por el método de Hargreaves. Valores mayores a 1 indican exceso de agua; valores menores a 1 indican déficit hídrico.

**Por qué importa:** La precipitación absoluta no dice todo sobre el balance hídrico. 500mm pueden ser suficientes en zona fría (donde la evapotranspiración es baja) pero insuficientes en zona cálida (donde la planta pierde más agua). El índice de aridez combina precipitación y demanda evapotranspirativa en un solo número que captura el verdadero balance hídrico del lugar.

**Por qué Hargreaves y no Penman-Monteith:** Penman-Monteith es más preciso pero requiere humedad relativa, velocidad del viento y radiación solar a alta resolución. Hargreaves solo necesita temperatura máxima, mínima y media, que sí tenemos. Para los fines de este sistema de recomendación, Hargreaves es un compromiso adecuado entre precisión y disponibilidad de datos.

**Decisión de diseño:** Se usa CHIRPS para la precipitación (cobertura uniforme) y los agregados de temperatura IDEAM (que ya tienen corrección adiabática incorporada, lo que es crucial para zonas de montaña donde la ETP varía fuertemente con la altitud).

---

## Paso 4 — Construcción de la Vista Minable

### Qué es la Vista Minable

La vista minable es la tabla final que los algoritmos de machine learning consumen directamente. Su nombre viene de "data mining" —es la vista de los datos que se puede "minar" para encontrar patrones. Cada fila describe completamente un lugar en un momento dado, y la última columna dice qué cultivo fue exitoso ahí.

La decisión de construirla como tabla rectangular (en lugar de, por ejemplo, alimentar los modelos directamente desde los rasters) es fundamental: permite usar todos los algoritmos de ML tabulares estándar, facilita la depuración y auditoría, y permite exportar e inspeccionar los datos con herramientas convencionales como pandas.

### La Estructura: Por Qué (Píxel, Semestre)

Una fila de la vista minable corresponde a un **píxel geográfico específico en un semestre específico**. Esto tiene varias implicaciones:

**Un mismo píxel aparece hasta 12 veces** (una por cada semestre 2020A–2025B). Esto permite que el modelo aprenda no solo las condiciones del lugar (que son estáticas o cambian lentamente) sino también cómo las condiciones climáticas variables de cada semestre afectan el éxito del cultivo. Un píxel a 2.400m de altitud puede plantar papa exitosamente en semestres normales, pero fallar en semestres con heladas tardías.

**Por qué no usar la parcela o el municipio como unidad:** La parcela georreferenciada tiene máxima precisión pero muy pocos datos de campo. El municipio tiene mucha cobertura de datos (EVA) pero pierde toda la variabilidad espacial interna. El píxel de 10m es el compromiso óptimo: máxima resolución espacial con cobertura total del departamento gracias a las imágenes satelitales.

### Muestreo Estratificado — Por Qué No Usar Todos los Píxeles

Cundinamarca a 10m tiene aproximadamente 480 millones de píxeles. Con 12 semestres, la tabla tendría 5.760 millones de filas, lo que es computacionalmente inviable para entrenamiento. El muestreo reduce este número a ~500.000 píxeles (6 millones de filas con 12 semestres).

**Por qué estratificado y no aleatorio simple:** El muestreo aleatorio puro favorecería los pisos térmicos más frecuentes (templado y frío dominan en Cundinamarca). Los cultivos raros de tierra caliente —arroz, cacao, palma— estarían subrepresentados. La estratificación por piso térmico × pendiente garantiza que cada combinación de condiciones ecológicas tenga representación proporcional en el dataset.

**Por qué incluir todos los píxeles con monitoreo:** Los polígonos de monitoreo UPRA son la fuente de etiquetas más confiable (confianza=1.0, porque son polígonos georreferenciados de cultivos reales). Su inclusión completa maximiza el número de ejemplos de alta calidad para el entrenamiento.

**Los cuatro estratos de pendiente** tienen justificación agronómica directa: pendiente plana (<5°) es tierra potencialmente cultivable con cualquier mecanización; suave (5–15°) admite mecanización parcial; moderada (15–30°) solo permite cultivos manuales; escarpada (>30°) es prácticamente incultivable y su presencia en el dataset sirve como "zona de exclusión" para que el modelo aprenda a no recomendar cultivos ahí.

### Las Tres Fuentes de Etiquetas y Sus Confianzas

El problema fundamental es que no existe un censo completo de qué se siembra en cada hectárea de Cundinamarca. Las etiquetas se construyen combinando tres fuentes de información con calidades distintas:

**Prioridad 1 — Monitoreo UPRA (confianza=1.0):**
Polígonos georreferenciados por satélite de parcelas con cultivos identificados. Son la fuente de mayor precisión porque la geometría del polígono delimita exactamente la parcela y el cultivo fue verificado visualmente. La limitación es que solo cubren cuatro cultivos (papa, maíz, arroz, cacao) y los años 2021–2024. Cualquier píxel que caiga dentro de estos polígonos recibe su etiqueta con plena confianza.

**Prioridad 2 — EVA municipal (confianza≤0.7):**
Las Evaluaciones Agropecuarias Municipales registran área sembrada, área cosechada y rendimiento por cultivo para cada municipio y semestre. No dicen dónde exactamente en el municipio se sembró, pero sí qué se sembró exitosamente. La estrategia es asignar el cultivo dominante del municipio (ponderado por área cosechada) a los píxeles del municipio que no tienen monitoreo, priorizando cultivos compatibles con el piso térmico del píxel. La confianza es menor (0.7) porque hay incertidumbre sobre la ubicación exacta dentro del municipio.

La compatibilidad con piso térmico es clave: si el municipio registra tanto papa como arroz, y el píxel está a 2.500m, se asigna papa, no arroz. Esto incorpora conocimiento agronómico en el proceso de etiquetado.

**Prioridad 3 — SIPRA aptitud (confianza=0.2–0.5):**
La zonificación de aptitud SIPRA indica dónde es técnicamente posible cultivar cada especie. No dice que se esté cultivando actualmente, sino que el suelo y el clima son apropiados. Se usa como fuente de respaldo para píxeles sin monitoreo ni EVA, con confianza reducida (0.5 para aptitud alta, 0.4 para media, 0.2 para baja). Solo se incluyen zonas de Cundinamarca (se filtra el dataset nacional al departamento).

**Por qué este sistema de prioridades:** Refleja la calidad epistemológica de cada fuente. Los polígonos de monitoreo son observación directa. La EVA es estadística oficial verificada pero sin precisión espacial. SIPRA es modelización técnica, más incierta pero con cobertura completa. Los modelos ML pueden usar la columna de confianza como peso de muestra durante el entrenamiento, dando más importancia a las observaciones de mayor calidad.

### Las 74+ Columnas de Features

La tabla incluye features de cuatro familias:

**Topográficas (5 features, estáticas):** Elevación, pendiente, aspecto, curvatura y TWI. Son los condicionantes permanentes del terreno. La elevación determina el piso térmico, la pendiente el riesgo de erosión y la mecanizabilidad, el aspecto la exposición solar (laderas orientadas al este reciben sol de mañana y son más secas, las del oeste reciben la tarde), la curvatura el drenaje superficial, y el TWI la acumulación de humedad en el suelo.

**Edafológicas (12 SoilGrids + 13 IGAC, estáticas):** Las propiedades del suelo son el sustrato que los cultivos no pueden cambiar. pH, carbono orgánico, nitrógeno, capacidad de intercambio catiónico, densidad aparente, arcilla, arena y limo determinan la fertilidad potencial, la retención de agua, la aireación y la aptitud para distintos sistemas radiculares. Las capas IGAC complementan con información de vocación de uso, clasificación taxonómica del suelo y propiedades químicas a escala local que SoilGrids global no capta.

**Climáticas semestrales (7 features por semestre):** Temperatura media, máxima y mínima; precipitación acumulada IDEAM y CHIRPS; humedad media. Son las condiciones del ambiente durante el período de crecimiento. Se incluyen tanto IDEAM como CHIRPS porque se complementan: IDEAM tiene mejor calibración puntual pero gaps espaciales; CHIRPS tiene cobertura uniforme pero menor precisión local.

**Satelitales semestrales (24 Sentinel-2 + 3 Sentinel-1 por semestre):** Los 7 índices espectrales de Sentinel-2 (NDVI, GNDVI, EVI, NDWI, MSAVI, BSI, SAVI) en media, máximo y desviación estándar capturan el estado de la vegetación, el contenido de agua de la hoja, la estructura del dosel y la presencia de suelo desnudo. Sentinel-1 añade información de estructura del dosel y humedad del suelo que no depende de condiciones de iluminación ni nubes.

**Derivadas (7 features por semestre):** Las ya descritas en el Paso 3, que codifican conocimiento agronómico explícito.

### El Formato Parquet — Por Qué No CSV

Apache Parquet es un formato columnar comprimido diseñado para análisis de datos. Frente a CSV tiene ventajas determinantes para este proyecto:

- **Tipado:** Cada columna tiene tipo explícito (float32, int8, string). Los CSV son texto plano y requieren inferencia de tipos.
- **Compresión:** Parquet con compresión Snappy ocupa entre 3 y 10 veces menos que el CSV equivalente para datos numéricos densos.
- **Velocidad de lectura:** Las librerías ML (pandas, scikit-learn, PyTorch) leen Parquet directamente sin parsear texto.
- **Lectura columnar:** Si solo se necesitan las columnas de features (sin el target), Parquet lee solo esas columnas del disco. Un CSV requiere leer el archivo completo.

Para una tabla potencial de 6 millones de filas × 80 columnas, estas diferencias son la distinción entre un proceso que tarda 2 minutos y uno que tarda 20.

### El Catálogo de Cultivos

Junto al Parquet se genera un archivo JSON que mapea cada nombre de cultivo a un número entero (cultivo_id). Este archivo es crítico para la fase de inferencia: cuando el modelo predice "clase 7", necesitamos saber que "clase 7" es "Papa". Sin este catálogo, el modelo es una caja negra que predice números sin significado.

Se guarda como archivo separado (no dentro del Parquet) para que la API de inferencia pueda cargarlo de forma independiente sin cargar la tabla completa.

---

## Coherencia del Sistema

Las decisiones de diseño de los cuatro pasos están interconectadas y se refuerzan mutuamente:

| Decisión | Justificación | Impacto en el Sistema |
|---|---|---|
| 10m de resolución | Nativo de Sentinel-2, mayor resolución disponible | Define granularidad de toda la tabla |
| EPSG:3116 | CRS oficial colombiano, métricas exactas | Habilita Kriging y derivadas topográficas correctas |
| Granularidad mensual en raw | LSTM necesita secuencias, NDVI integral necesita meses | Permite tanto features tabulares como temporales |
| Semestral para modelos tabulares | Unidad de planificación agrícola colombiana | Alinea con EVA, SIPRA y decisiones de siembra |
| Corrección adiabática en temperatura | Gradiente físico de −6°C/1000m | Evita errores sistemáticos en zonas de montaña |
| Tres fuentes de etiquetas con confianza | No existe censo completo de cultivos | Permite entrenamiento ponderado, maximiza cobertura |
| Muestreo estratificado | Clases raras subrepresentadas en muestreo aleatorio | Evita sesgo hacia pisos dominantes |
| Parquet + catálogo JSON | Eficiencia computacional + interpretabilidad | Habilita inferencia en <2s en producción |

---

## Limitaciones Conocidas y Mitigaciones

**Asignación EVA no espacializada:** La EVA registra cultivos a nivel municipal, no de parcela. La asignación a píxeles usa el piso térmico como proxy espacial, lo que introduce ruido en los labels. Mitigación: confianza=0.7 (menor que monitoreo), y el volumen de datos con ruido controlado no impide que el modelo aprenda la señal correcta.

**SIPRA es modelización, no observación:** Los mapas de aptitud SIPRA son el resultado de modelos agronómicos, no de observaciones de campo. Pueden estar desactualizados o ser imprecisos. Mitigación: confianza=0.2–0.5, solo se usan como respaldo cuando no hay otra fuente.

**Cobertura de nubosidad en Sentinel-2:** Cundinamarca tiene alta nubosidad, especialmente en semestre B. Meses sin imágenes limpias generan NaN en las features satelitales. Mitigación: se requieren al menos 2 meses válidos para generar estadísticos; el NDVI máximo usa solo los meses sin nubes; Sentinel-1 (SAR) complementa donde Sentinel-2 falla.

**Escasez de estaciones IDEAM en zonas remotas:** Los páramos y valles del Magdalena tienen pocas estaciones. El Kriging produce mayor incertidumbre ahí. Mitigación: CHIRPS cubre esas zonas con datos satelitales, y la corrección adiabática reduce el error sistemático en zonas de montaña.

---

*Documento generado en el contexto del proyecto ¿Qué Sembrar? | Marzo 2026*
