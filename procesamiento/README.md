# procesamiento/

Scripts de transformación de datos crudos a capas armonizadas listas para modelado.

## 01_armonizar_espacial.py

Convierte todas las fuentes de datos crudas (`extractores/raw/`) a un único grid de referencia:

| Parámetro | Valor |
|---|---|
| CRS | EPSG:3116 — MAGNA-SIRGAS Colombia Bogotá |
| Resolución | 10 m × 10 m |
| Salida | `processed/` |

### Dependencias

```bash
pip install rasterio geopandas pykrige scipy numpy pyproj pandas
```

---

### Ejecución por paso

#### Todo en secuencia (orden automático correcto)

```bash
uv run procesamiento/01_armonizar_espacial.py
```

> El script ejecuta los pasos en el orden correcto: DEM → IDEAM → CHIRPS → SoilGrids → IGAC → Sentinel-2 → Sentinel-1 → Validación.

---

#### Paso 1 — Estaciones IDEAM (Kriging)

Interpola las estaciones puntuales del IDEAM a superficie continua 10 m usando Kriging Ordinario. La temperatura incluye corrección por gradiente adiabático (−6 °C / 1000 m).

> **Requiere el DEM procesado primero** (usa la elevación para la corrección de temperatura).

```bash
# Las tres variables
uv run procesamiento/01_armonizar_espacial.py --step ideam

# Solo temperatura
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable temperatura

# Solo precipitación
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable precipitacion

# Solo humedad relativa
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable humedad
```

Salida: `processed/clima/ideam/{variable}_{YYYY_MM}_kriging.tif`

---

#### Paso 2 — CHIRPS (precipitación satelital)

Reproyecta los GeoTIFF mensuales de CHIRPS (~5.3 km) a 10 m con resampling bilineal.

```bash
uv run procesamiento/01_armonizar_espacial.py --step chirps
```

Salida: `processed/clima/chirps/*.tif`

---

#### Paso 3 — SoilGrids

Reproyecta propiedades de suelo globales (250 m) a 10 m. Usa bilineal para variables continuas y nearest-neighbor para texturas (clay, sand, silt). Normaliza automáticamente clay + sand + silt = 100%.

```bash
uv run procesamiento/01_armonizar_espacial.py --step soilgrids
```

Salida: `processed/suelo/soilgrids/*.tif`

---

#### Paso 4 — IGAC (suelo colombiano vectorial)

Rasteriza los polígonos del IGAC (propiedades químicas y vocación de uso) al grid de 10 m. Los campos categóricos (fertilidad, vocación) se codifican a enteros con tabla de códigos JSON.

```bash
uv run procesamiento/01_armonizar_espacial.py --step igac
```

Salida: `processed/suelo/igac/*.tif` y `*_tabla_codigos.json`

---

#### Paso 5 — Sentinel-2

Reproyecta compuestos semestrales de reflectancia Sentinel-2 a EPSG:3116 / 10 m. Funciona tanto para bandas nativas a 10 m como a 20 m.

```bash
uv run procesamiento/01_armonizar_espacial.py --step sentinel2
```

Salida: `processed/satelite/sentinel2/s2_indices_{YYYY_MM}.tif`

---

#### Paso 6 — Sentinel-1

Reproyecta imágenes SAR Sentinel-1 GRD a EPSG:3116 (resolución nativa ya es 10 m).

```bash
uv run procesamiento/01_armonizar_espacial.py --step sentinel1
```

Salida: `processed/satelite/sentinel1/s1_backscatter_{YYYY_MM}.tif`

---

#### Paso 7 — DEM + derivadas topográficas

Reproyecta el DEM Copernicus GLO-30 y sus derivadas (pendiente, aspecto, curvatura, TWI) de 30 m a 10 m. **Ejecutar este paso primero** cuando se procesa todo desde cero.

```bash
uv run procesamiento/01_armonizar_espacial.py --step dem
```

Salida: `processed/topo/dem_{banda}_10m.tif`

| Archivo | Contenido |
|---|---|
| `dem_elevacion_10m.tif` | Elevación en metros |
| `dem_pendiente_10m.tif` | Pendiente en grados (0°–90°) |
| `dem_aspecto_10m.tif` | Orientación de ladera (0°=Norte) |
| `dem_curvatura_10m.tif` | Curvatura del perfil |
| `dem_twi_10m.tif` | Topographic Wetness Index |
| `dem_cundinamarca_10m.tif` | Alias de elevación (usado por IDEAM) |

---

#### Validación

Verifica que todos los rásteres en `processed/` compartan CRS, dimensiones y rangos físicos válidos.

```bash
uv run procesamiento/01_armonizar_espacial.py --step validar
```

---

### Orden recomendado al procesar desde cero

```bash
uv run procesamiento/01_armonizar_espacial.py --step dem
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable temperatura
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable precipitacion
uv run procesamiento/01_armonizar_espacial.py --step ideam --variable humedad
uv run procesamiento/01_armonizar_espacial.py --step chirps
uv run procesamiento/01_armonizar_espacial.py --step soilgrids
uv run procesamiento/01_armonizar_espacial.py --step igac
uv run procesamiento/01_armonizar_espacial.py --step sentinel2
uv run procesamiento/01_armonizar_espacial.py --step sentinel1
uv run procesamiento/01_armonizar_espacial.py --step validar
```

### Reanudación automática

Cada paso verifica si el archivo de salida ya existe antes de procesarlo. Si una ejecución se interrumpe, basta con volver a correr el mismo comando — los archivos ya generados se saltan automáticamente.
