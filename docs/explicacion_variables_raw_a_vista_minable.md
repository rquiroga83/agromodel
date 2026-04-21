# De los Datos Crudos a la Vista Minable --- Trazabilidad de Variables

## Proyecto ¿Qué Sembrar? \| Cundinamarca, Colombia

> Este documento explica **qué variables se extrajeron originalmente**,
> **cuáles se excluyeron y por qué**, y **cómo cada variable de la vista
> minable final (54 columnas) fue construida** a partir de los datos
> procesados.

------------------------------------------------------------------------

## 1. Resumen del Flujo

    Extractores (01-08)         → raw/               ~80+ variables originales
        ↓
    01_armonizar_espacial.py    → processed/          Todas al grid 50m EPSG:3116
        ↓
    02_armonizar_temporal.py    → processed/temporal/  Mensual → semestral (media, max, std)
        ↓
    03_feature_engineering.py   → processed/engineered/ 7 features derivadas
        ↓
    04_construir_vista_minable.py → vista_minable/    54 columnas finales

El script `04_construir_vista_minable.py` es donde ocurre la **selección
y exclusión** final de variables. Contiene listas explícitas de
exclusión (`EXCLUIR_CAPAS`, `S2_INDICES_EXCLUIR`, `TOPO_EXCLUIR`,
`SOILGRIDS_PROPS_EXCLUIR`) y además excluye Sentinel-1 completamente.

------------------------------------------------------------------------

## 2. Variables Extraídas vs. Incluidas --- Resumen Cuantitativo

  ---------------------------------------------------------------------------------
  Fuente              Variables extraídas    Variables en vista minable   Excluidas
  ----------------- --------------------- ----------------------------- -----------
  DEM / Topografía                      6                             3           3

  SoilGrids                             9                             8           1

  IGAC                                 13                             5           8

  IDEAM Clima                           5                             4           1

  CHIRPS                                1                             1           0

  Sentinel-2            7 índices × 3 agg             5 índices × 3 agg   2 índices

  Sentinel-1                     3 bandas                             0           3

  Feature                               7                             7           0
  Engineering                                                           

  Metadata/Target                       5                             5           0

  **TOTAL**                      **\~86**                        **54**    **\~32**
  ---------------------------------------------------------------------------------

------------------------------------------------------------------------

## 3. Detalle de Variables Excluidas y Razón

### 3.1 Topografía --- 3 excluidas

  ---------------------------------------------------------------------------
  Variable             Razón de exclusión                  Detalle
  -------------------- ----------------------------------- ------------------
  `dem_cundinamarca`   **Alias duplicado**                 Es el mismo raster
                                                           que
                                                           `dem_elevacion`.
                                                           Se incluye solo
                                                           `elevacion`.

  `aspecto` (original, **Transformada**                    El aspecto
  0°-360°)                                                 circular tiene una
                                                           discontinuidad en
                                                           0°/360° que
                                                           confunde a los
                                                           modelos (0° y 359°
                                                           son casi iguales
                                                           pero numéricamente
                                                           distantes). Se
                                                           reemplazó por
                                                           `aspecto_sin` y
                                                           `aspecto_cos`
                                                           (feature
                                                           engineering).

  `curvatura`          **Sin poder discriminante**         La curvatura del
                                                           terreno tiene una
                                                           distribución casi
                                                           uniforme centrada
                                                           en ≈0 en
                                                           Cundinamarca. Su
                                                           varianza es mínima
                                                           y no aporta
                                                           información para
                                                           distinguir aptitud
                                                           de cultivos.
  ---------------------------------------------------------------------------

### 3.2 SoilGrids --- 1 excluida

  ---------------------------------------------------------------------------
  Variable           Razón de exclusión                  Detalle
  ------------------ ----------------------------------- --------------------
  `ocd` (Densidad de **Alta correlación con SOC**        r \> 0.90 con
  Carbono Orgánico)                                      `sg_soc`. La
                                                         información que
                                                         aporta ya está
                                                         contenida en SOC.
                                                         Excluir evita
                                                         multicolinealidad.

  ---------------------------------------------------------------------------

### 3.3 IGAC --- 8 excluidas de 13

El IGAC produce mapas de suelos con 13+ campos por unidad cartográfica.
La mayoría son variables categóricas de texto libre con cardinalidad muy
alta o información redundante con otras fuentes:

  -----------------------------------------------------------------------------
  Variable              Razón de exclusión                  Detalle
  --------------------- ----------------------------------- -------------------
  `igac_subgrupo`       **Cardinalidad extrema**            1.109 clases de
                                                            taxonomía USDA. Un
                                                            modelo no puede
                                                            aprender de tantas
                                                            categorías con tan
                                                            pocas muestras por
                                                            clase. Redundante
                                                            con las propiedades
                                                            de suelo (pH,
                                                            textura,
                                                            fertilidad) que ya
                                                            capturan las
                                                            diferencias
                                                            taxonómicas
                                                            relevantes.

  `igac_ucsuelo`        **Cardinalidad extrema**            \~500+ unidades
                                                            cartográficas de
                                                            suelo. Similar a
                                                            subgrupo --- es una
                                                            clasificación
                                                            detallada que no
                                                            aporta más alla de
                                                            las propiedades
                                                            físico-químicas ya
                                                            incluidas.

  `igac_clima`          **Redundante con IDEAM/CHIRPS**     \~34 clases
                                                            climáticas del
                                                            IGAC. El clima ya
                                                            está representado
                                                            por 5 variables
                                                            continuas de
                                                            IDEAM + CHIRPS +
                                                            índice de aridez,
                                                            que son más
                                                            precisas y
                                                            granulares que una
                                                            clase categórica.

  `igac_paisaje`        **Redundante con topografía**       \~20 tipos de
                                                            paisaje. Ya
                                                            capturado por
                                                            elevación,
                                                            pendiente, TWI y
                                                            aspecto.

  `igac_material`       **Impacto indirecto**               \~15 tipos de
                                                            material parental.
                                                            No afecta
                                                            directamente al
                                                            cultivo --- su
                                                            impacto se
                                                            manifiesta a través
                                                            de las propiedades
                                                            del suelo (pH,
                                                            fertilidad,
                                                            textura) que ya
                                                            están incluidas.

  `igac_relieve`        **Redundante con topografía**       \~10 tipos de
                                                            relieve. Ya
                                                            representado por
                                                            pendiente, TWI y
                                                            elevación.

  `igac_calificacion`   **Redundante con fertilidad**       \~10 clases de
                                                            calificación del
                                                            suelo. Es una
                                                            evaluación
                                                            integrada que ya
                                                            está representada
                                                            por
                                                            `igac_fertilidad`
                                                            (más granular).

  `igac_suma_bases`     **Redundante con CEC**              Suma de bases
                                                            intercambiables.
                                                            Altamente
                                                            correlacionado con
                                                            `sg_cec` (Capacidad
                                                            de Intercambio
                                                            Catiónico) que ya
                                                            está incluida.
  -----------------------------------------------------------------------------

**Las 5 variables IGAC que SÍ se incluyen** (`fertilidad`, `fosforo`,
`ph`, `potasio`, `vocacion`) son las que tienen cardinalidad baja (5-8
categorías), significado agronómico directo y complementan la
información de SoilGrids con evaluaciones locales expertas.

### 3.4 Clima IDEAM --- 1 excluida

  ---------------------------------------------------------------------------
  Variable               Razón de exclusión                  Detalle
  ---------------------- ----------------------------------- ----------------
  `precipitacion_acum`   **100% ceros**                      La interpolación
  (IDEAM)                                                    kriging de
                                                             precipitación
                                                             desde estaciones
                                                             IDEAM falló ---
                                                             produjo
                                                             exclusivamente
                                                             valores de 0 en
                                                             todo el
                                                             departamento. Se
                                                             usa
                                                             `chirps_acum`
                                                             como fuente
                                                             alternativa de
                                                             precipitación
                                                             (cobertura
                                                             satelital
                                                             uniforme, sin
                                                             gaps
                                                             espaciales).

  ---------------------------------------------------------------------------

### 3.5 Sentinel-2 --- 2 índices excluidos de 7

  --------------------------------------------------------------------------
  Variable           Razón de exclusión                  Detalle
  ------------------ ----------------------------------- -------------------
  `s2_evi` (Enhanced **Alta correlación con NDVI**       r \> 0.95 con
  Vegetation Index)                                      `s2_ndvi`. NDVI es
                                                         más estable y
                                                         ampliamente
                                                         adoptado. Excluir
                                                         EVI reduce
                                                         multicolinealidad
                                                         sin pérdida de
                                                         información.

  `s2_ndwi`          **Redundante con humedad**          Mide contenido de
  (Normalized                                            agua en vegetación.
  Difference Water                                       Ya cubierto por
  Index)                                                 `humedad_media`
                                                         (IDEAM) y el
                                                         `indice_aridez`
                                                         (CHIRPS +
                                                         temperatura).
  --------------------------------------------------------------------------

**Los 5 índices S2 que SÍ se incluyen** (NDVI, GNDVI, MSAVI, BSI, SAVI)
cubren: - **NDVI**: Vigor vegetativo general - **GNDVI**: Sensible a
clorofila (nitrógeno) - **MSAVI**: Vegetación con suelo expuesto (no
necesita parámetro L) - **BSI**: Suelo desnudo (complemento inverso de
vegetación) - **SAVI**: Vegetación ajustada por suelo (similar a MSAVI
pero con parámetro fijo)

### 3.6 Sentinel-1 --- 3 bandas excluidas (COMPLETAMENTE)

  -----------------------------------------------------------------------------
  Variable                 Razón de exclusión                  Detalle
  ------------------------ ----------------------------------- ----------------
  `s1_vv_media`            **53% datos faltantes**             El satélite
                                                               Sentinel-1B
                                                               falló en
                                                               diciembre 2021.
                                                               Los datos
                                                               2022-2025 tienen
                                                               cobertura
                                                               incompleta.

  `s1_vh_media`            **53% datos faltantes**             Mismo problema.

  `s1_vh_vv_ratio_media`   **53% datos faltantes**             Mismo problema.
                                                               Además, las 3
                                                               bandas SAR son
                                                               parcialmente
                                                               redundantes con:
                                                               (1) Sentinel-2
                                                               (5 índices
                                                               ópticos de
                                                               vegetación) y
                                                               (2) Humedad
                                                               IDEAM + CHIRPS +
                                                               índice de aridez
                                                               para humedad del
                                                               suelo.
  -----------------------------------------------------------------------------

**Nota**: Sentinel-1 se puede reincorporar si se obtienen datos
posteriores a la misión Sentinel-1B. El código tiene las líneas
preparadas (comentadas en `_definir_capas_semestrales`).

------------------------------------------------------------------------

## 4. Variables de Feature Engineering --- Creación de nuevas variables

Estas 7 variables no existen en los datos crudos; fueron creadas en
`03_feature_engineering.py` con base en conocimiento agronómico:

  ------------------------------------------------------------------------------------------------------------------
  Variable              Creada desde          Fórmula / Lógica                           Justificación agronómica
  --------------------- --------------------- ------------------------------------------ ---------------------------
  `aspecto_sin`         `aspecto` (DEM)       `sin(aspecto × π/180)`                     Codifica orientación N-S
                                                                                         sin discontinuidad 0°/360°.
                                                                                         Valores: -1=Oeste, +1=Este.

  `aspecto_cos`         `aspecto` (DEM)       `cos(aspecto × π/180)`                     Codifica orientación E-O.
                                                                                         Valores: -1=Sur, +1=Norte.
                                                                                         Ambas juntas representan la
                                                                                         dirección completa.

  `piso_termico`        `elevacion`           0=Cálido(\<1000m), 1=Templado(1000-2000m), La variable más
                                              2=Frío(2000-3000m), 3=Páramo(\>3000m)      determinante de aptitud
                                                                                         agrícola. Conocimiento
                                                                                         experto IGAC/MADR.

  `indice_fertilidad`   `sg_nitrogen`,        Promedio normalizado (0-1) de 4            Resume fertilidad en un
                        `sg_phh2o`, `sg_cec`, componentes; pH con tratamiento de         score interpretable, reduce
                        `sg_soc`              distancia al óptimo 6.5                    multicolinealidad.

  `amplitud_termica`    `temperatura_max` -   Diferencia en °C                           Mide calidad de cultivo:
                        `temperatura_min`                                                amplitudes altas → más
                                                                                         azúcares (mejor calidad en
                                                                                         café, papa, fresa).

  `anomalia_precip`     `chirps_acum` por     `(precip_sem - media_hist) / std_hist`     Indica sequía o exceso.
                        semestre              separado por A/B                           Valores \< -1 = seco, \> 1
                        vs. histórico                                                    = húmedo.

  `ndvi_max`            Rasters mensuales     `max(NDVI_ene, NDVI_feb, ..., NDVI_jun)`   Pico de verdor del
                        NDVI                  con NaN para nubes                         semestre. Duplicado de
                                                                                         `s2_ndvi_max` por diseño
                                                                                         (ver nota).

  `ndvi_integral`       Rasters mensuales     `Σ(NDVI_mensual) × 30 días`                Producción total de biomasa
                        NDVI                                                             (proxy de productividad
                                                                                         primaria neta).

  `indice_aridez`       `chirps_acum` / ETP   Precipitación / Evapotranspiración         Balance hídrico real: \< 1
                        Hargreaves            Potencial                                  = déficit, \> 5 = exceso.
  ------------------------------------------------------------------------------------------------------------------

### Nota sobre `ndvi_max` vs `s2_ndvi_max`

`ndvi_max` (feature engineering) y `s2_ndvi_max` (agregación temporal)
son **numéricamente idénticas** (r = 1.000). Ambas se calcularon como el
máximo de los NDVI mensuales del semestre. La duplicidad surgió porque
`ndvi_max` se generó en el paso 03 (feature engineering) como raster
derivado, mientras que `s2_ndvi_max` se generó en el paso 02 (agregación
temporal) como estadístico semestral. Para entrenamiento de modelos,
**se recomienda excluir `ndvi_max`** y conservar `s2_ndvi_max`.

------------------------------------------------------------------------

## 5. Variables Target --- Cómo se asignaron las etiquetas

La vista minable incluye 5 columnas de target:

  -----------------------------------------------------------------------
  Variable                       Descripción
  ------------------------------ ----------------------------------------
  `cultivo`                      Nombre del cultivo asignado (7 clases)

  `cultivo_id`                   Encoding numérico (0-6) según
                                 `catalogo_cultivos.json`

  `confianza`                    Calidad de la etiqueta (0.0-1.0)

  `fuente`                       Origen: `monitoreo`, `eva`, o `sipra`

  `rendimiento_tha`              Rendimiento en ton/ha (solo para algunos
                                 cultivos)
  -----------------------------------------------------------------------

### Sistema de prioridad de etiquetas

    Prioridad 1: Monitoreo UPRA (confianza = 1.0)
        └→ Polígonos georreferenciados de cultivos reales (2021-2024)
        └→ Solo 4 cultivos: Papa, Maíz, Arroz, Cacao

    Prioridad 2: EVA municipal (confianza = 0.16 - 0.43)
        └→ Cultivo dominante del departamento compatible con piso térmico
        └→ Score ponderado por area_cosechada relativa
        
    Prioridad 3: SIPRA aptitud (confianza = 0.2 - 0.5)
        └→ Zonas donde es técnicamente posible cultivar (no observación real)
        └→ Solo como respaldo cuando no hay monitoreo ni EVA

### Los 7 cultivos en la vista minable

    cultivo_id Cultivo           \% aproximado Fuente principal
  ------------ --------------- --------------- ------------------
             0 Arroz                    \~1.5% EVA
             1 Cacao                    \~0.1% SIPRA
             2 Caña Panelera            \~0.1% SIPRA
             3 Frijol                  \~10.8% EVA
             4 Palma                    \~0.3% SIPRA
             5 Papa                    \~84.8% EVA + Monitoreo
             6 Papa Capiro              \~2.4% EVA

**NOTA**: Papa domina con \~85% del dataset. Esto refleja la realidad
agrícola de Cundinamarca (departamento productor de papa), pero implica
un **desbalance extremo** que debe tratarse durante el entrenamiento
(stratified sampling, class weights, SMOTE, etc.).

------------------------------------------------------------------------

## 6. Variables que NO existen en la vista minable pero sí en processed/

  ---------------------------------------------------------------------------------------------------
  Variable / Raster         Ubicación                                  Razón de no inclusión
  ------------------------- ------------------------------------------ ------------------------------
  Rasters mensuales de      `processed/temporal/`                      Se usan para calcular
  NDVI, temperatura, etc.                                              estadísticos semestrales. Los
                                                                       datos mensuales se conservan
                                                                       para uso futuro con LSTM.

  `precipitacion_acum`      `processed/temporal/clima/ideam/`          100% ceros (kriging fallido).
  IDEAM                                                                Reemplazado por CHIRPS.

  Rasters de aspecto        `processed/topo/`                          Reemplazado por `aspecto_sin`
  original                                                             y `aspecto_cos`.

  Rasters de curvatura      `processed/topo/`                          Sin poder discriminante (≈0
                                                                       uniforme).

  Rasters S1 (VV, VH,       `processed/temporal/satelite/sentinel1/`   53% datos faltantes por fallo
  ratio)                                                               Sentinel-1B.

  Rasters S2 EVI            `processed/temporal/satelite/sentinel2/`   Redundante con NDVI (r\>0.95).

  Rasters S2 NDWI           `processed/temporal/satelite/sentinel2/`   Redundante con humedad e
                                                                       índice de aridez.

  IGAC subgrupo, ucsuelo,   `processed/suelo/igac/`                    Cardinalidad extrema o
  clima, etc.                                                          redundancia (ver sección 3.3).

  SoilGrids OCD             `processed/suelo/soilgrids/`               Altamente correlacionado con
                                                                       SOC (r\>0.9).
  ---------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 7. Mapa Completo: Variable Raw → Variable Vista Minable

### 7.1 Metadata (4 variables)

  -----------------------------------------------------------------------
  Vista minable           Origen                  Nota
  ----------------------- ----------------------- -----------------------
  `pixel_id`              Generado en Paso 8      Secuencial, sin
                                                  significado espacial

  `x`                     DEM transform           Coordenada X del centro
                                                  del píxel (EPSG:3116)

  `y`                     DEM transform           Coordenada Y del centro
                                                  del píxel (EPSG:3116)

  `semestre`              Generado en Paso 6-7    Label del semestre
                                                  (2020A-2025B)
  -----------------------------------------------------------------------

### 7.2 Features estáticos --- Topografía (6 variables)

  ------------------------------------------------------------------------
  Vista minable           Origen raw               Procesamiento
  ----------------------- ------------------------ -----------------------
  `elevacion`             Extractor 07 DEM         Armonizado a 50m
                                                   EPSG:3116

  `pendiente`             Extractor 07 DEM →       Armonizado a 50m
                          `gdaldem slope`          

  `twi`                   Extractor 07 DEM →       Armonizado a 50m
                          cálculo TWI              

  `aspecto_sin`           FE (03):                 Ingeniería de features
                          `sin(aspecto × π/180)`   

  `aspecto_cos`           FE (03):                 Ingeniería de features
                          `cos(aspecto × π/180)`   

  `piso_termico`          FE (03): clasificación   Ingeniería de features
                          por elevación            
  ------------------------------------------------------------------------

### 7.3 Features estáticos --- Suelo SoilGrids (8 variables)

  Vista minable   Origen raw     Procesamiento
  --------------- -------------- -----------------------------------------
  `sg_phh2o`      Extractor 04   Bilinear a 50m. Unidad: pH × 10
  `sg_soc`        Extractor 04   Bilinear a 50m. Unidad: g/kg × 10
  `sg_nitrogen`   Extractor 04   Bilinear a 50m. Unidad: g/kg × 10
  `sg_cec`        Extractor 04   Bilinear a 50m. Unidad: cmol/kg × 10
  `sg_bdod`       Extractor 04   Bilinear a 50m. Unidad: g/cm³ × 10
  `sg_clay`       Extractor 04   Nearest-neighbor + normalización a 100%
  `sg_sand`       Extractor 04   Nearest-neighbor + normalización a 100%
  `sg_silt`       Extractor 04   Nearest-neighbor + normalización a 100%

### 7.4 Features estáticos --- Suelo IGAC (5 variables)

  -----------------------------------------------------------------------
  Vista minable           Origen raw              Procesamiento
  ----------------------- ----------------------- -----------------------
  `igac_fertilidad`       Extractor 03            Rasterización de
                                                  polígonos. Ordinal 1-7

  `igac_fosforo`          Extractor 03            Rasterización. Ordinal
                                                  1-5

  `igac_ph`               Extractor 03            Rasterización. Ordinal
                                                  1-6

  `igac_potasio`          Extractor 03            Rasterización. Ordinal
                                                  1-5

  `igac_vocacion`         Extractor 03            Rasterización.
                                                  Categórica 0-8
  -----------------------------------------------------------------------

### 7.5 Features estáticos --- Derivado (1 variable)

  -----------------------------------------------------------------------
  Vista minable           Origen                  Procesamiento
  ----------------------- ----------------------- -----------------------
  `indice_fertilidad`     FE (03): sg + igac      Promedio normalizado
                                                  0-1 de 4 componentes

  -----------------------------------------------------------------------

### 7.6 Features dinámicos --- Clima (5 variables)

  -----------------------------------------------------------------------
  Vista minable           Origen raw              Procesamiento
  ----------------------- ----------------------- -----------------------
  `temperatura_media`     Extractor 01 IDEAM      Kriging + adiabática →
                                                  1km → 50m. Media
                                                  semestral

  `temperatura_max`       Extractor 01 IDEAM      Kriging + adiabática →
                                                  1km → 50m. Media de
                                                  máximos

  `temperatura_min`       Extractor 01 IDEAM      Kriging + adiabática →
                                                  1km → 50m. Media de
                                                  mínimos

  `humedad_media`         Extractor 01 IDEAM      Kriging → 1km → 50m.
                                                  Media semestral

  `chirps_acum`           Extractor 02 CHIRPS     Bilinear 5.3km → 50m.
                                                  Acumulado semestral
  -----------------------------------------------------------------------

### 7.7 Features dinámicos --- Derivados (5 variables)

  -----------------------------------------------------------------------
  Vista minable           Origen                  Procesamiento
  ----------------------- ----------------------- -----------------------
  `amplitud_termica`      FE (03): temp_max -     °C por semestre
                          temp_min                

  `anomalia_precip`       FE (03): chirps_acum    z-score vs histórico
                          estandarizado           por tipo semestre

  `ndvi_max`              FE (03): max NDVI       **Duplicado de
                          mensual                 s2_ndvi_max** (r=1.0)

  `ndvi_integral`         FE (03): Σ(NDVI × 30    Proxy de biomasa total
                          días)                   

  `indice_aridez`         FE (03): precip / ETP   Balance hídrico
                          Hargreaves              
  -----------------------------------------------------------------------

### 7.8 Features dinámicos --- Sentinel-2 (15 variables)

  -----------------------------------------------------------------------
  Vista minable           Origen raw              Procesamiento
  ----------------------- ----------------------- -----------------------
  `s2_ndvi_media`         Extractor 05            Media semestral de
                                                  observaciones válidas

  `s2_ndvi_max`           Extractor 05            Máximo semestral

  `s2_ndvi_std`           Extractor 05            Desviación estándar
                                                  semestral

  `s2_gndvi_media`        Extractor 05            Media semestral

  `s2_gndvi_max`          Extractor 05            Máximo semestral

  `s2_gndvi_std`          Extractor 05            Desviación estándar

  `s2_msavi_media`        Extractor 05            Media semestral

  `s2_msavi_max`          Extractor 05            Máximo semestral

  `s2_msavi_std`          Extractor 05            Desviación estándar

  `s2_bsi_media`          Extractor 05            Media semestral

  `s2_bsi_max`            Extractor 05            Máximo semestral

  `s2_bsi_std`            Extractor 05            Desviación estándar

  `s2_savi_media`         Extractor 05            Media semestral

  `s2_savi_max`           Extractor 05            Máximo semestral

  `s2_savi_std`           Extractor 05            Desviación estándar
  -----------------------------------------------------------------------

### 7.9 Variables Target (5 variables)

  -----------------------------------------------------------------------
  Vista minable           Origen                  Procesamiento
  ----------------------- ----------------------- -----------------------
  `cultivo`               Monitoreo + EVA + SIPRA Asignación prioritaria
                                                  (Paso 7)

  `cultivo_id`            Generado                Label encoding desde
                                                  catálogo JSON

  `confianza`             Calculado en Paso 7     Monitoreo=1.0,
                                                  EVA=0.16-0.43,
                                                  SIPRA=0.2-0.5

  `fuente`                Calculado en Paso 7     `monitoreo`, `eva`, o
                                                  `sipra`

  `rendimiento_tha`       EVA (Extractor 08)      Mediana por
                                                  cultivo-semestre
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 8. Recomendaciones de Exclusión Adicional para Modelos ML

El análisis estadístico (ver `informe_analisis_estadistico.md`)
identifica las siguientes variables candidatas a excluir ANTES del
entrenamiento:

  -------------------------------------------------------------------------
  Variable             Problema              Recomendación
  -------------------- --------------------- ------------------------------
  `ndvi_max`           Duplicado exacto de   **Excluir** --- conservar
                       `s2_ndvi_max`         `s2_ndvi_max`
                       (r=1.000)             

  `temperatura_max`    Correlación casi      **Excluir** --- ya capturada
                       perfecta con          por media y amplitud
                       `temperatura_media`   
                       (r=0.99)              

  `temperatura_min`    Correlación casi      **Excluir** --- ya capturada
                       perfecta con          por media y amplitud
                       `temperatura_media`   
                       (r=0.98)              

  `s2_savi_*` (3 vars) Redundancia con       **Excluir** --- MSAVI es la
                       `s2_msavi_*` (r≈1.0)  versión mejorada de SAVI

  `sg_nitrogen`        Alta correlación con  **Evaluar** --- puede
                       `sg_soc` (r\>0.85) y  excluirse si se conserva
                       `indice_fertilidad`   `indice_fertilidad`
                       (r=0.90)              

  `igac_vocacion`      52.5% ceros (sin      **Transformar** --- crear
                       información)          binaria `tiene_vocacion` o
                                             excluir
  -------------------------------------------------------------------------

Si se aplican todas las exclusiones recomendadas, la vista minable
quedaría en **\~46 features** (excluyendo metadata y target).

