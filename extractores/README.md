# Extractores de Datos — Proyecto ¿Qué Sembrar?
## Cundinamarca, Colombia | Ventana Temporal: 2019–2024

### Estructura de Scripts

```
extractores/
├── config.py                      # Configuración compartida (bbox, credenciales, rutas)
├── run_all.py                     # Ejecutor maestro (todos los scripts en secuencia)
├── 01_extraer_clima_ideam.py      # Clima: Temperatura, Precipitación, Humedad, Normales
├── 02_extraer_chirps.py           # Clima: Precipitación satelital CHIRPS
├── 03_extraer_suelo_igac.py       # Suelo: Propiedades Químicas + Vocación de Uso (IGAC)
├── 04_extraer_soilgrids.py        # Suelo: SoilGrids 2.0 (pH, SOC, textura, densidad, CEC, N)
├── 05_extraer_sentinel2.py        # Satélite: Sentinel-2 índices espectrales mensuales (10 m real, tiles)
├── 06_extraer_sentinel1.py        # Satélite: Sentinel-1 backscatter SAR mensual (10 m real, tiles)
├── 07_extraer_dem_topografia.py   # Topografía: DEM + Pendiente + Aspecto + Curvatura + TWI
└── 08_extraer_target.py           # Target: EVA + Monitoreo UPRA + SIPRA Aptitud
```

### Instalación de Dependencias

```bash
pip install requests pandas geopandas rasterio sentinelhub numpy scipy pysheds
# Opcional para CHIRPS via GEE:
pip install earthengine-api
```

### Uso

```bash
# Ejecutar TODOS los extractores (puede tardar varias horas)
uv run run_all.py

# Ejecutar un extractor específico por número
uv run run_all.py 01        # Solo clima IDEAM (los 4 pasos)
uv run run_all.py 05 06     # Solo Sentinel-2 y Sentinel-1 (tiles + merge)

# Script 05 — Sentinel-2: descargar un mes específico (tiles + merge)
uv run extractores/05_extraer_sentinel2.py --mes 2020_01
uv run extractores/05_extraer_sentinel2.py               # Todos los meses

# Script 06 — Sentinel-1: descargar un mes específico (tiles + merge)
uv run extractores/06_extraer_sentinel1.py --mes 2020_01
uv run extractores/06_extraer_sentinel1.py               # Todos los meses
uv run run_all.py 08        # Solo targets (EVA, Monitoreo, SIPRA)

# Script 01 — Clima IDEAM: ejecutar cada variable de forma independiente
uv run run_all.py 01:temp       # Solo Temperatura
uv run run_all.py 01:precip     # Solo Precipitación (todos los años, por mes)
uv run run_all.py 01:humedad    # Solo Humedad del Aire
uv run run_all.py 01:normales   # Solo Normales Climatológicas 1961-2020

# Script 01 — Precipitación: reanudar desde un año o mes específico
uv run run_all.py 01:precip:2021        # Solo precipitación 2021
uv run run_all.py 01:precip:2021:6      # Solo precipitación junio 2021

# Script 03 — Suelo IGAC: ejecutar cada capa de forma independiente
uv run run_all.py 03:quimica    # Solo Propiedades Químicas
uv run run_all.py 03:vocacion   # Solo Vocación de Uso

# Script 08 — Target: ejecutar cada dataset de forma independiente
uv run run_all.py 08:eva        # Solo EVA (Evaluaciones Agropecuarias)
uv run run_all.py 08:monitoreo  # Solo Monitoreo Satelital UPRA
uv run run_all.py 08:sipra      # Solo Zonificación de Aptitud SIPRA

# O ejecutar directamente con argumentos
uv run 01_extraer_clima_ideam.py --step precip
uv run 01_extraer_clima_ideam.py --step precip --year 2021
uv run 01_extraer_clima_ideam.py --step precip --year 2021 --mes 6
uv run 03_extraer_suelo_igac.py --step quimica
uv run 03_extraer_suelo_igac.py --step vocacion
```

### Parámetros Clave (config.py)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| BBOX_WGS84 | [-74.89, 3.73, -73.05, 5.84] | Bounding box de Cundinamarca |
| YEAR_START | 2019 | Inicio de ventana temporal |
| YEAR_END | 2024 | Fin de ventana temporal |
| DEPT_DANE | '25' | Código DANE de Cundinamarca |
| CDSE_CLIENT_ID | sh-d7474d2c-... | OAuth client Copernicus Data Space |

### Datos de Salida Esperados

```
raw/
├── clima/
│   ├── ideam_temperatura/     → CSV (~2-5M registros)
│   ├── ideam_precipitacion/   → CSV por mes (72 archivos, ~500K-1M registros/mes)
│   ├── ideam_humedad/         → CSV (~2-5M registros)
│   ├── ideam_normales/        → CSV (~50K registros, línea base 1961-2020)
│   └── chirps/                → 72 GeoTIFF mensuales (12 meses × 6 años)
├── suelo/
│   ├── igac_quimica/          → GeoJSON (propiedades químicas, escala 1:100.000)
│   ├── igac_vocacion/         → GeoJSON (vocación de uso, 18 clases)
│   └── soilgrids/             → 27 GeoTIFF (9 propiedades × 3 profundidades)
├── satelite/
│   ├── sentinel2/             → 72 GeoTIFF mensuales a 10 m (7 bandas cada uno, ~1.3 GB/mes)
│   └── sentinel1/             → 72 GeoTIFF mensuales a 10 m (3 bandas cada uno, ~550 MB/mes)
├── topo/
│   └── dem_glo30/             → 1 GeoTIFF multibanda (5 bandas topográficas)
└── target/
    ├── eva/                   → CSV (EVA histórica + UPRA + calendarios)
    ├── monitoreo/             → GeoJSON por cultivo×año×semestre
    └── sipra/                 → GeoJSON de aptitud por cultivo
```

### Tiempos Estimados de Descarga

| Script | Fuente | Tiempo Estimado | Volumen |
|--------|--------|-----------------|---------|
| 01 | IDEAM (datos.gov.co API) | 1-3 horas | ~500 MB CSV |
| 02 | CHIRPS (CHC UCSB o GEE) | 30-60 min | ~200 MB TIF |
| 03 | IGAC (ArcGIS REST) | 2-4 horas | ~300 MB GeoJSON |
| 04 | SoilGrids (ISRIC WCS) | 30-60 min | ~100 MB TIF |
| 05 | Sentinel-2 (CDSE) | ~3 horas (~80 tiles × 72 meses) | ~94 GB TIF |
| 06 | Sentinel-1 (CDSE) | ~3 horas (~80 tiles × 72 meses) | ~40 GB TIF |
| 07 | DEM Copernicus (CDSE) | 5-10 min | ~50 MB TIF |
| 08 | EVA + UPRA + SIPRA | 1-2 horas | ~200 MB |

### Notas Importantes

- **Idempotencia:** Cada script verifica si los archivos ya existen antes de descargar.
  Se puede interrumpir y reanudar sin problemas. La precipitación se descarga por mes
  (`precipitacion_cund_YYYY_MM.csv`) para granularidad fina de reanudación.
- **IGAC WAF:** El firewall del IGAC bloquea `where=1=1`. Se usa `OBJECTID>0`.
- **CDSE cuota:** La cuenta gratuita tiene límites de requests. Si se exceden,
  esperar y reintentar.
- **CHIRPS:** Se intenta GEE primero. Si no está configurado, usa descarga directa.
- **Datos estáticos vs temporales:** SoilGrids, IGAC y DEM se descargan una sola vez.
  IDEAM, CHIRPS, Sentinel-2 y Sentinel-1 tienen datos por cada semestre 2019-2024.
