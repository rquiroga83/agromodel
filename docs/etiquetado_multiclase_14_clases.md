# Etiquetado multiclase (14 clases) — Análisis y cambios

Fecha: 2026-04-22
Alcance: re-diseño del etiquetado (target) de `vista_minable_full.parquet`
para entrenar un clasificador multiclase de cultivos por píxel-semestre.

---

## 1. Contexto y motivación

### Estado previo (descartado)
La versión anterior del pipeline asignaba 7 clases (Papa, Arroz, Papa
Capiro, Frijol, Palma, Cacao, Caña Panelera) combinando tres fuentes:

1. **Monitoreo UPRA** — polígonos georreferenciados reales (Papa, Arroz,
   Cacao, Maíz) con fechas.
2. **EVA (Evaluaciones Agropecuarias Municipales)** — datos tabulares
   sin geometría, agregados por municipio + año.
3. **SIPRA (Sistema de Información Para la Planificación Rural
   Agropecuaria)** — polígonos de **aptitud potencial** (Alta/Media/
   Baja/No apta) por cultivo.

Dos problemas graves en ese esquema:

- **Fuga por `piso_termico`**: EVA se "geolocalizaba" asignando el
  cultivo dominante del departamento según el piso térmico del píxel.
  El modelo recibía `piso_termico` como feature y como regla de
  etiquetado al mismo tiempo → aprendía trivialmente la regla.
- **Fuga por SIPRA como etiqueta positiva**: SIPRA se usaba para marcar
  "este píxel = Papa Capiro" donde SIPRA decía "Papa Capiro Alta". SIPRA
  es en sí mismo un modelo que combina clima, suelo y topografía — las
  mismas variables que el clasificador usa como features. Resultado:
  métricas infladas artificialmente, el modelo "aprende SIPRA", no las
  condiciones reales del cultivo.

Consecuencia: la distribución era 84.8% Papa con métricas >0.95 en
validación, dominadas por leakage.

### Diseño nuevo (este documento)

Etiquetado **jerárquico de 3 niveles** con **hard labels + sample_weight**:

| Nivel | Fuente | Confianza | Evidencia |
|-------|--------|-----------|-----------|
| L1 | Monitoreo UPRA | 1.0 | Polígonos georreferenciados de cultivo real |
| L2 | EVA municipal | 0.30 – 0.70 | Cultivo dominante del municipio-semestre (area cosechada relativa) |
| L3 | Proxy No_apto | 0.40 | SIPRA "No apta" en ≥3 capas ∪ NDVI_max < 0.15 |

Las 14 clases canónicas del modelo son los **12 cultivos EVA que cubren
~80% del área cosechada de Cundinamarca 2019-2024**, más `Otros_cultivos`
(catch-all) y `No_apto`:

```
Papa, Cana_Panelera, Cafe, Maiz, Platano, Mango,
Frijol, Cacao, Arveja, Palma, Banano, Naranja,
Otros_cultivos, No_apto
```

Ninguna feature del modelo (`piso_termico`, clima, suelo, índices
satelitales) participa en la lógica de etiquetado. La única dependencia
geográfica es el código DANE del municipio (via MGN), que **no** es
feature y solo se usa como lookup para EVA.

---

## 2. Análisis de las fuentes de etiquetas

### 2.1 Monitoreo UPRA (`raw/target/monitoreo/`)

- 14 GeoJSON, cobertura real en Cundinamarca:
  - **Papa**: 2021A–2024A, ~127k polígonos
  - **Maíz**: 2021A–2023B, decenas a cientos
  - **Arroz**: 2021A–2024A, ~490 polígonos (zonas cálidas)
  - **Cacao**: 2020A–2023A
- `tipo_cultivo` en el GeoJSON solo distingue "Raíces y Tubérculos" /
  "Cereales"; no hay separación Papa Común vs. Papa Capiro.
- Decisión: el cultivo se toma del **nombre del archivo**, se normaliza
  a una de las 14 clases. Arroz → `Otros_cultivos` (no es top-12 EVA).

**Valor para el modelo**: ground truth espacial y temporalmente
preciso. Base de confianza 1.0 del dataset.

### 2.2 EVA (`raw/target/eva/eva_upra_2019_2024_cundinamarca.csv`)

- 13,218 registros, 109 cultivos únicos, 116 municipios.
- **Sin geometría** — solo (cod_mun, año, cultivo, area_sembrada,
  area_cosechada, rendimiento).
- Top-12 cultivos por área cosechada acumulada 2019-2024 (~80%
  cobertura): Papa (27%), Caña (15%), Café (10%), Maíz (7%), Plátano,
  Mango, Frijol, Cacao, Arveja, Palma, Banano, Naranja.

**Problema**: EVA es agregada a municipio — si un municipio tiene 40%
Papa, 30% Caña, 20% Café, 10% otros, **cada píxel** del municipio en
ese semestre recibirá la misma etiqueta (Papa, la dominante). Eso
introduce correlación espacial masiva dentro del municipio.

**Mitigación**:
1. `confianza = score_aptitud = area_cultivo / area_agrícola_total`
   se usa como `sample_weight`. Si la Papa dominante tiene
   score=0.45, su peso es 0.45, mucho menor que el 1.0 del monitoreo.
2. Cuando ningún cultivo supera score=0.30 (municipio muy diversificado),
   se etiqueta como `Otros_cultivos` con confianza=0.30.
3. La validación cruzada debe ser **por bloques espaciales**
   (KFold sobre municipios), no aleatoria — ver Sección 4.

**Valor para el modelo**: cubre el 95%+ de los píxeles de Cundinamarca
con señal probabilística. Permite que el modelo vea cultivos que no
tienen monitoreo UPRA (Caña, Café, Frijol, etc.) y aprenda sus
condiciones típicas de clima/suelo/topografía.

### 2.3 SIPRA (`raw/target/sipra/aptitud_*.geojson`)

**Cambio**: se amplía el catálogo para cubrir los top-12 cultivos EVA.

Capas ya existentes: Papa (común + Capiro s1/s2), Café, Maíz (s1/s2),
Palma, Cacao, Frijol, Caña panelera, Fresa (auxiliar), Aguacate Hass
(auxiliar).

Capas **agregadas en config.py** (2026-04):
- `platano` → `aptitud_platano/MapServer/0`
- `mango` → `aptitud_mango_diciembre_2019/MapServer/0`
- `banano` → `aptitud_banano/MapServer/0`

Capas **no disponibles en UPRA** para el top-12: Arveja, Naranja. Estas
clases reciben etiqueta solo vía L1 (monitoreo, inexistente) o L2 (EVA).
No afecta al proxy No_apto porque basta con que **algún** cultivo
SIPRA diga "No apta" en un píxel para sumar al conteo.

**Uso revisado**: SIPRA **no se usa para etiquetas positivas**. Solo
aporta al proxy `No_apto` (L3). Esto es defendible porque estamos
usando SIPRA como evidencia de **ausencia de aptitud**, no como
predicción de cultivo. No hay fuga circular: No_apto no correlaciona
con ningún cultivo específico.

### 2.4 MGN-DANE (nuevo: `extractores/09_extraer_municipios_dane.py`)

Polígonos oficiales de municipios de Cundinamarca con código DANE
5-dígitos. Se rasteriza al grid 50 m → cada píxel recibe su
`cod_mun` int. Es el **puente** entre la tabla EVA (indexada por
`cod_mun`) y los píxeles del raster.

El extractor intenta varias fuentes ArcGIS REST en orden (IGAC,
UPRA, DANE Geoportal); si fallan, imprime instrucciones para
colocar manualmente el shapefile MGN en `raw/target/mgn/`.

---

## 3. Cambios técnicos aplicados

### 3.1 `extractores/config.py`

- **Nuevas constantes**:
  - `EVA_TOP_CULTIVOS`: lista de 12 strings en orden de área descendente.
  - `MODEL_CLASSES`: `EVA_TOP_CULTIVOS + ['Otros_cultivos', 'No_apto']`,
    garantiza IDs estables del label encoder entre runs.
  - `DANE_MGN_URLS`: lista de endpoints candidatos para el MGN.
- **`UPRA_APTITUD` extendido**: añadidos `platano`, `mango`, `banano`;
  resto reorganizado por cultivo EVA.
- **`DIRS['target_mgn']`**: nueva carpeta para el GeoJSON del MGN.

### 3.2 `extractores/09_extraer_municipios_dane.py` (nuevo)

Descarga programática del MGN-DANE con:
- 3 endpoints candidatos ArcGIS REST (IGAC, UPRA, DANE).
- Normalización a esquema canónico: `cod_dane` (5 dig), `cod_dpto`,
  `nombre_mpio`, geometría en EPSG:4326.
- Filtrado a Cundinamarca (`cod_dpto == '25'`).
- Fallback: conversión automática de shapefile colocado manualmente
  en `raw/target/mgn/*.shp`.

### 3.3 `procesamiento/04_construir_vista_minable.py`

**Nuevas funciones**:

- `_normalizar_cultivo(nombre_raw)`: mapea cualquier nombre EVA /
  monitoreo a una de las 14 clases canónicas. Maneja acentos y variantes.
- `rasterizar_municipios(profile) -> int32 raster`: MGN-DANE al grid.
- `rasterizar_sipra_noapta(profile) -> int16 raster`: suma de votos
  "No apta" across all SIPRA layers disponibles.
- `cargar_ndvi_max_ultimo_anio() -> float32 raster`: NDVI_max global
  de los últimos ~2 años, usado para el proxy No_apto.

**Funciones modificadas**:

- `cargar_eva()`: ahora retorna **dos** objetos — un DataFrame agregado
  por (cod_mun, semestre, cultivo_norm) con score_aptitud calculado, y
  un dict `{(cod_mun, semestre): {cultivo_norm, score, rendimiento}}`
  con el cultivo dominante por municipio-semestre, para lookup O(1)
  durante la asignación de targets. **Crucial**: la agregación por clase
  canónica se hace **antes** de tomar el "top", así `Papa Común` +
  `Papa Criolla` + `Papa Parda` suman y compiten como una sola clase
  `Papa` contra las demás.
- `asignar_target()`: reemplazada la lógica "solo monitoreo" por la
  jerarquía L1→L2→L3 descrita.
- `construir_vista_minable()`: añadidas las llamadas a rasterización de
  MGN, SIPRA y NDVI. La codificación `cultivo_id` usa ahora
  `MODEL_CLASSES` como catálogo estable (antes usaba
  `sorted(vista['cultivo'].unique())`, que cambiaba con la muestra).

---

## 4. Qué debe aprender el modelo (y qué NO)

### Debe aprender
- Asociaciones **clima × suelo × topografía → cultivo real** en los
  píxeles L1 (monitoreo): cuál es la firma biofísica de Papa, Maíz,
  Cacao, Arroz.
- Distribución probabilística de cultivos por condiciones agroclimáticas
  usando las etiquetas L2 (EVA municipal), entendiendo que la
  confianza es parcial (0.3–0.7).
- A discriminar píxeles no agrícolas (`No_apto`) del resto por firma
  NDVI baja y/o SIPRA rechazo consensuado.

### No debe aprender (controles anti-leakage)
- Regla SIPRA → cultivo: SIPRA **no** participa en asignación positiva.
- Regla piso_termico → cultivo: eliminada del etiquetado; piso_termico
  sigue disponible como feature legítima.
- Identidad del municipio: `cod_mun` **no es feature**, solo se usa
  como puente EVA→píxel. El modelo no tiene forma de memorizar "si
  estoy en municipio X entonces la etiqueta es Y".

### Requisitos de la validación
- **Validación cruzada por bloques espaciales** (spatial KFold por
  municipio o celda geográfica ≥ 10 km). La validación aleatoria
  producirá métricas infladas en ~20-40 pp porque los píxeles de un
  mismo municipio L2 comparten etiqueta.
- Usar `sample_weight = vista['confianza']` al entrenar (XGBoost:
  `sample_weight=` en `.fit()`). Opcionalmente `eval_sample_weight`
  para que la métrica de validación también pondere.
- Reportar métricas **desagregadas por fuente** (monitoreo vs eva
  vs noapto_proxy), no solo agregadas. Una métrica agregada mezcla
  señal clara con ruido probabilístico.
- Rendimientos muy asimétricos por clase esperados; usar `macro-F1` y
  matriz de confusión, no accuracy.

---

## 5. Cómo regenerar la vista minable

```bash
# 1) Descargar MGN (solo la primera vez)
uv run extractores/09_extraer_municipios_dane.py
#    Si falla, seguir instrucciones de fallback manual que imprime.

# 2) Re-descargar SIPRA con capas nuevas (platano, mango, banano)
uv run extractores/08_extraer_target.py --step sipra

# 3) Regenerar la vista minable
del vista_minable\vista_minable_full.parquet   # o rm en bash
uv run procesamiento/04_construir_vista_minable.py

# 4) Diagnóstico rápido de la nueva distribución
uv run python -c "
import pandas as pd
df = pd.read_parquet('vista_minable/vista_minable_full.parquet')
print('filas:', len(df))
print('por fuente:')
print(df['fuente'].value_counts(normalize=True).round(3))
print('top-10 clases:')
print(df['cultivo'].value_counts().head(10))
print('confianza por fuente:')
print(df.groupby('fuente')['confianza'].describe()[['count','mean','min','max']])
"
```

---

## 6. Expectativas de la distribución resultante

Estimación (sujeta a cambios según cobertura real de cada fuente):

| Fuente | % filas | Clases dominantes |
|--------|---------|---------------------|
| monitoreo (L1) | 5–15% | Papa, Otros (Arroz, Maíz, Cacao) |
| eva_municipal (L2) | 70–85% | Papa, Cana_Panelera, Cafe, Maiz, Otros_cultivos |
| noapto_proxy (L3) | 5–15% | No_apto |

A diferencia del esquema previo (84.8% Papa artificial), se espera:
- **Papa** baje a ~30-40% (alineado con EVA real)
- **Cana_Panelera / Cafe / Maiz** suban visiblemente
- **No_apto** aparezca como clase real (~5-15%)
- Clases cola (Arveja, Mango, Banano, Naranja) queden <2% — normal, se
  manejan con `class_weight='balanced'` en XGBoost o con oversampling
  en el pipeline del notebook.

---

## 7. Riesgos conocidos y mitigaciones

| Riesgo | Mitigación |
|--------|-------------|
| `cod_mun` se filtra accidentalmente como feature | Está documentado que **no** es feature. Excluirlo explícitamente en el split features/target del notebook: `X = vista.drop(columns=['cultivo','cultivo_id','confianza','fuente','rendimiento_tha','pixel_id','cod_mun'])`. |
| Validación aleatoria oculta leakage espacial | Usar `GroupKFold` por municipio o bloques geográficos ≥ 10 km. |
| Clases muy raras (Naranja, Arveja) | Posibles soluciones: `class_weight`, stratified batch sampling, o consolidarlas en `Otros_cultivos` si aportan <0.5%. |
| MGN-DANE no descarga | Extractor 09 imprime instrucciones de fallback manual; sin MGN, L2 se omite pero L1 + L3 siguen funcionando. |
| `sample_weight` interacciona mal con `early_stopping` en XGBoost | Usar eval_set con sample_weight propio del holdout; no mezclar train+val weights. |
| SIPRA "No apta" puede sobre-representar tierras baldías | Umbral ≥3 capas votando No_apta + NDVI<0.15 es conservador. Revisar distribución post-generación. |

---

## 8. Próximos pasos en el notebook

1. Cargar `vista_minable_full.parquet` y `catalogo_cultivos.json`.
2. Usar `GroupKFold(n_splits=5, groups=vista['cod_mun'])` o bloques
   espaciales por celda de 10 km.
3. Entrenar XGBoost multiclase (`objective='multi:softprob'`,
   `num_class=14`) con `sample_weight=vista['confianza']`.
4. Reportar métricas por fuente (solo L1, solo L2, solo L3, y
   conjunto). Macro-F1, matriz de confusión, ROC-OvR.
5. Para predicción final sobre Cundinamarca completa: el modelo
   predice probabilidades sobre las 14 clases en cada píxel-semestre.
