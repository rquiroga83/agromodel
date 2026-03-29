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
├── 05_extraer_sentinel2.py        # Satélite: Sentinel-2 índices espectrales semestrales
├── 06_extraer_sentinel1.py        # Satélite: Sentinel-1 backscatter SAR semestral
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
python run_all.py

# Ejecutar un extractor específico
python run_all.py 1         # Solo clima IDEAM
python run_all.py 5 6       # Solo Sentinel-2 y Sentinel-1
python run_all.py 8         # Solo targets (EVA, Monitoreo, SIPRA)

# O ejecutar directamente
python 01_extraer_clima_ideam.py
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
│   ├── ideam_precipitacion/   → CSV por año (~5-10M registros/año)
│   ├── ideam_humedad/         → CSV (~2-5M registros)
│   ├── ideam_normales/        → CSV (~50K registros, línea base 1961-2020)
│   └── chirps/                → 72 GeoTIFF mensuales (12 meses × 6 años)
├── suelo/
│   ├── igac_quimica/          → GeoJSON (propiedades químicas, escala 1:100.000)
│   ├── igac_vocacion/         → GeoJSON (vocación de uso, 18 clases)
│   └── soilgrids/             → 27 GeoTIFF (9 propiedades × 3 profundidades)
├── satelite/
│   ├── sentinel2/             → 12 GeoTIFF semestrales (7 bandas cada uno)
│   └── sentinel1/             → 12 GeoTIFF semestrales (3 bandas cada uno)
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
| 05 | Sentinel-2 (CDSE) | 1-2 horas | ~500 MB TIF |
| 06 | Sentinel-1 (CDSE) | 30-60 min | ~200 MB TIF |
| 07 | DEM Copernicus (CDSE) | 5-10 min | ~50 MB TIF |
| 08 | EVA + UPRA + SIPRA | 1-2 horas | ~200 MB |

### Notas Importantes

- **Idempotencia:** Cada script verifica si los archivos ya existen antes de descargar.
  Se puede interrumpir y reanudar sin problemas.
- **IGAC WAF:** El firewall del IGAC bloquea `where=1=1`. Se usa `OBJECTID>0`.
- **CDSE cuota:** La cuenta gratuita tiene límites de requests. Si se exceden,
  esperar y reintentar.
- **CHIRPS:** Se intenta GEE primero. Si no está configurado, usa descarga directa.
- **Datos estáticos vs temporales:** SoilGrids, IGAC y DEM se descargan una sola vez.
  IDEAM, CHIRPS, Sentinel-2 y Sentinel-1 tienen datos por cada semestre 2019-2024.
