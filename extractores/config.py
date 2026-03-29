"""
config.py — Configuración compartida para todos los extractores del proyecto ¿Qué Sembrar?
═══════════════════════════════════════════════════════════════════════════════════════════

Área de interés: Cundinamarca, Colombia
Ventana temporal: 2019-2024 (6 años, 12 semestres)
  - Clima IDEAM: 2019-01-01 a 2024-12-31
  - EVA Target: 2019 a 2024
  - Sentinel-2/1: 2019-01-01 a 2024-12-31
  - Suelo / DEM: estáticos (una sola descarga)

pip install requests pandas geopandas rasterio sentinelhub numpy scipy pysheds
"""

import os

# ──────────────────────────────────────────────────────────────
# ÁREA DE INTERÉS — Cundinamarca (WGS84)
# ──────────────────────────────────────────────────────────────
BBOX_WGS84 = [-74.89, 3.73, -73.05, 5.84]   # [west, south, east, north]
DEPT_DANE  = '25'                             # Código DANE de Cundinamarca
DEPT_NAME  = 'CUNDINAMARCA'

# ──────────────────────────────────────────────────────────────
# VENTANA TEMPORAL
# ──────────────────────────────────────────────────────────────
YEAR_START = 2020
YEAR_END   = 2025
DATE_START = f'{YEAR_START}-01-01'
DATE_END   = f'{YEAR_END}-12-31'

# Semestres agrícolas de Colombia
SEMESTRES = []
for year in range(YEAR_START, YEAR_END + 1):
    SEMESTRES.append({'label': f'{year}A', 'start': f'{year}-01-01', 'end': f'{year}-06-30'})
    SEMESTRES.append({'label': f'{year}B', 'start': f'{year}-07-01', 'end': f'{year}-12-31'})

# ──────────────────────────────────────────────────────────────
# CREDENCIALES COPERNICUS DATA SPACE (CDSE)
# ──────────────────────────────────────────────────────────────
CDSE_CLIENT_ID     = 'sh-d7474d2c-e4e8-44a2-80a1-cec3da1afc30'
CDSE_CLIENT_SECRET = 'pahkhcQCFoWrXsIje6fpB3G0U7UUBsMr'
CDSE_BASE_URL      = 'https://sh.dataspace.copernicus.eu'
CDSE_TOKEN_URL     = (
    'https://identity.dataspace.copernicus.eu'
    '/auth/realms/CDSE/protocol/openid-connect/token'
)

# ──────────────────────────────────────────────────────────────
# ESTRUCTURA DE DIRECTORIOS
# ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR  = os.path.join(BASE_DIR, 'raw')

DIRS = {
    'clima_temp':    os.path.join(RAW_DIR, 'clima', 'ideam_temperatura'),
    'clima_precip':  os.path.join(RAW_DIR, 'clima', 'ideam_precipitacion'),
    'clima_humedad': os.path.join(RAW_DIR, 'clima', 'ideam_humedad'),
    'clima_normales': os.path.join(RAW_DIR, 'clima', 'ideam_normales'),
    'clima_chirps':  os.path.join(RAW_DIR, 'clima', 'chirps'),
    'suelo_igac':    os.path.join(RAW_DIR, 'suelo', 'igac_quimica'),
    'suelo_vocacion': os.path.join(RAW_DIR, 'suelo', 'igac_vocacion'),
    'suelo_soilgrids': os.path.join(RAW_DIR, 'suelo', 'soilgrids'),
    'sat_sentinel2': os.path.join(RAW_DIR, 'satelite', 'sentinel2'),
    'sat_sentinel1': os.path.join(RAW_DIR, 'satelite', 'sentinel1'),
    'topo_dem':      os.path.join(RAW_DIR, 'topo', 'dem_glo30'),
    'target_eva':    os.path.join(RAW_DIR, 'target', 'eva'),
    'target_monitoreo': os.path.join(RAW_DIR, 'target', 'monitoreo'),
    'target_sipra':  os.path.join(RAW_DIR, 'target', 'sipra'),
}

def crear_directorios():
    """Crear toda la estructura de directorios si no existe."""
    for path in DIRS.values():
        os.makedirs(path, exist_ok=True)
    print(f"Estructura de directorios creada bajo: {RAW_DIR}")

# ──────────────────────────────────────────────────────────────
# HEADERS HTTP para APIs colombianas
# ──────────────────────────────────────────────────────────────
# App Token de datos.gov.co (Socrata) — sin token: throttling por IP compartido.
# Con token: hasta 1.000 requests/hora sin throttling por request.
# Crear en: https://www.datos.gov.co → perfil → Developer Settings → Create New App Token
SODA_APP_TOKEN = os.environ.get('SODA_APP_TOKEN', 'v1VwafGrvw2k2T30YlxxOdRsM')  # poner el token aquí o en variable de entorno

HEADERS_GOV = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, */*',
    **({'X-App-Token': SODA_APP_TOKEN} if SODA_APP_TOKEN else {}),
}

HEADERS_IGAC = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://mapas.igac.gov.co/',
    'Accept': 'application/json, */*',
}

# ──────────────────────────────────────────────────────────────
# APIs de datos.gov.co (SODA)
# ──────────────────────────────────────────────────────────────
SODA_BASE = 'https://www.datos.gov.co/resource'
SODA_DATASETS = {
    'temperatura':    'sbwg-7ju4',   # Temperatura Ambiente del Aire
    'precipitacion':  's54a-sgyg',   # Precipitación (cada 10 min)
    'humedad':        'uext-mhny',   # Humedad del Aire
    'normales':       'nsz2-kzcq',   # Normales Climatológicas 1961-2020
    'eva_historica':  '2pnw-mmge',   # EVA MADR 2007-2018
    'eva_upra':       'uejq-wxrr',   # EVA UPRA 2019-2024
    'calendario_nacional': '526r-sixz',  # Calendario Nacional Siembras/Cosechas 2023-2024
    'calendario_depto':    '6nv9-uruw',  # Calendario Departamental Siembras/Cosechas 2023-2024
}

# ──────────────────────────────────────────────────────────────
# GEOSERVICIOS UPRA (ArcGIS REST)
# ──────────────────────────────────────────────────────────────
UPRA_BASE = 'https://geoservicios.upra.gov.co/arcgis/rest/services'

UPRA_MONITOREO = {
    # Papa (2021-2024)
    'papa_2021_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2021_s1/MapServer/0',
    'papa_2021_s2':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2021_s2/MapServer/0',
    'papa_2022_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2022_s1/MapServer/0',
    'papa_2022_s2':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2022_s2/MapServer/0',
    'papa_2023_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2023_s1/MapServer/0',
    'papa_2023_s2':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2023_s2/MapServer/0',
    'papa_2024_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2024_s1/MapServer/0',
    # Maíz (2021-2023, semestres nombrados _1/_2)
    'maiz_2021_1':   f'{UPRA_BASE}/MonitoreoCultivos/maiz_2021_1/MapServer/0',
    'maiz_2021_2':   f'{UPRA_BASE}/MonitoreoCultivos/maiz_2021_2/MapServer/0',
    'maiz_2022_1':   f'{UPRA_BASE}/MonitoreoCultivos/maiz_2022_1/MapServer/0',
    'maiz_2022_2':   f'{UPRA_BASE}/MonitoreoCultivos/maiz_2022_2/MapServer/0',
    'maiz_2023_1':   f'{UPRA_BASE}/MonitoreoCultivos/maiz_2023_1/MapServer/0',
    'maiz_2023_2':   f'{UPRA_BASE}/MonitoreoCultivos/maiz_2023_2/MapServer/0',
    # Arroz (2021-2024)
    'arroz_2021_s1': f'{UPRA_BASE}/MonitoreoCultivos/arroz_2021_s1/MapServer/0',
    'arroz_2021_s2': f'{UPRA_BASE}/MonitoreoCultivos/arroz_2021_s2/MapServer/0',
    'arroz_2022_s1': f'{UPRA_BASE}/MonitoreoCultivos/arroz_2022_s1/MapServer/0',
    'arroz_2022_s2': f'{UPRA_BASE}/MonitoreoCultivos/arroz_2022_s2/MapServer/0',
    'arroz_2023_s1': f'{UPRA_BASE}/MonitoreoCultivos/arroz_2023_s1/MapServer/0',
    'arroz_2023_s2': f'{UPRA_BASE}/MonitoreoCultivos/arroz_2023_s2/MapServer/0',
    'arroz_2024_s1': f'{UPRA_BASE}/MonitoreoCultivos/arroz_2024_s1/MapServer/0',
    # Cacao (2020-2023)
    'cacao_2020':    f'{UPRA_BASE}/MonitoreoCultivos/Cacao_2020/MapServer/0',
    'cacao_2021':    f'{UPRA_BASE}/MonitoreoCultivos/Cacao_2021/MapServer/0',
    'cacao_2022':    f'{UPRA_BASE}/MonitoreoCultivos/Cacao_2022/MapServer/0',
    'cacao_2023':    f'{UPRA_BASE}/MonitoreoCultivos/Cacao_2023/MapServer/0',
}

UPRA_APTITUD = {
    # Cultivos relevantes para Cundinamarca con nombres confirmados en el servidor
    'papa_capiro_s1':   f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_diacol_capiro_sem_1/MapServer/0',
    'papa_capiro_s2':   f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_diacol_capiro_sem_2/MapServer/0',
    'papa_s1':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_sem_1_Dic2019/MapServer/0',
    'papa_s2':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_sem_2_Dic2019/MapServer/0',
    'cafe':             f'{UPRA_BASE}/aptitud_uso_suelo/Aptitud_Cafe_Jul2022/MapServer/0',
    'maiz_s1':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_maiz_sem_1_diciembre_2019/MapServer/0',
    'maiz_s2':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_maiz_sem_2_diciembre_2019/MapServer/0',
    'palma':            f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_palma_2018/MapServer/0',
    'fresa':            f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_fresa_Dic2019/MapServer/0',
    'aguacate_hass':    f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_aguacate_hass_Dic2019/MapServer/0',
    'cana_panelera':    f'{UPRA_BASE}/aptitud_uso_suelo/Aptitud_Cultivo_Comercial_Cana_Panelera_Oct2020/MapServer/0',
    'cacao':            f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_cacao_diciembre_2019/MapServer/0',
    'frijol':           f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_frijol_comercial/MapServer/0',
}

# ──────────────────────────────────────────────────────────────
# SoilGrids 2.0 (ISRIC)
# ──────────────────────────────────────────────────────────────
SOILGRIDS_BASE = 'https://rest.isric.org/soilgrids/v2.0/properties/query'
SOILGRIDS_PROPS = ['phh2o', 'soc', 'clay', 'sand', 'silt', 'bdod', 'cec', 'nitrogen', 'ocd']
SOILGRIDS_DEPTHS = ['0-5cm', '5-15cm', '15-30cm']

if __name__ == '__main__':
    crear_directorios()
    print("\nDatasets SODA configurados:")
    for k, v in SODA_DATASETS.items():
        print(f"  {k:20s} → {SODA_BASE}/{v}.json")
    print(f"\nVentana temporal: {DATE_START} a {DATE_END}")
    print(f"Semestres: {len(SEMESTRES)} ({SEMESTRES[0]['label']} a {SEMESTRES[-1]['label']})")
