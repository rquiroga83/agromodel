"""
config.py — Configuración compartida para todos los extractores del proyecto ¿Qué Sembrar?
═══════════════════════════════════════════════════════════════════════════════════════════

Área de interés: Cundinamarca, Colombia
Ventana temporal: 2019-2024 (6 años, 12 semestres)
  - Clima IDEAM: 2019-01-01 a 2024-12-31
  - EVA Target: 2019 a 2024
  - Sentinel-2/1: 2019-01-01 a 2024-12-31
  - Suelo / DEM: estáticos (una sola descarga)

Variables sensibles (credenciales) en extractores/.env — no en git.
Copiar extractores/.env.example → extractores/.env y completar los valores.

pip install requests pandas geopandas rasterio sentinelhub numpy scipy pysheds python-dotenv
"""

import os
from pathlib import Path

# Cargar .env si existe (python-dotenv opcional; fallback a os.environ puro)
_env_path = Path(__file__).parent / '.env'
try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    # Sin python-dotenv: parsear manualmente el .env
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ──────────────────────────────────────────────────────────────
# ÁREA DE INTERÉS — Cundinamarca (WGS84)
# ──────────────────────────────────────────────────────────────
BBOX_WGS84    = [-74.89, 3.73, -73.05, 5.84]   # [west, south, east, north]
RESOLUCION_M  = 50                              # Resolución del proyecto en metros
DEPT_DANE     = '25'                             # Código DANE de Cundinamarca
DEPT_NAME     = 'CUNDINAMARCA'

# ──────────────────────────────────────────────────────────────
# VENTANA TEMPORAL
# ──────────────────────────────────────────────────────────────
YEAR_START = 2020
YEAR_END   = 2024  # ultimo anio con cobertura UPRA (papa_2024_s1 es la mas reciente)
# UPRA aun no publica papa_2024_s2 ni papa_2025_*. La vista minable se corta en 2024A
# para que el modelo se entrene sobre semestres con etiquetas L1 disponibles.
INCLUDE_LAST_YEAR_S2 = False  # cambia a True cuando UPRA publique papa_2024_s2
DATE_START = f'{YEAR_START}-01-01'
DATE_END   = f'{YEAR_END}-12-31' if INCLUDE_LAST_YEAR_S2 else f'{YEAR_END}-06-30'

# Semestres agrícolas de Colombia (filtrados por INCLUDE_LAST_YEAR_S2)
SEMESTRES = []
for year in range(YEAR_START, YEAR_END + 1):
    SEMESTRES.append({'label': f'{year}A', 'start': f'{year}-01-01', 'end': f'{year}-06-30'})
    if year < YEAR_END or INCLUDE_LAST_YEAR_S2:
        SEMESTRES.append({'label': f'{year}B', 'start': f'{year}-07-01', 'end': f'{year}-12-31'})

# Meses del período de análisis (truncado al ultimo semestre incluido)
import calendar
MESES = []
for year in range(YEAR_START, YEAR_END + 1):
    ultimo_mes_anio = 12 if (year < YEAR_END or INCLUDE_LAST_YEAR_S2) else 6
    for mes in range(1, ultimo_mes_anio + 1):
        ultimo_dia = calendar.monthrange(year, mes)[1]
        MESES.append({
            'label': f'{year}_{mes:02d}',
            'start': f'{year}-{mes:02d}-01',
            'end':   f'{year}-{mes:02d}-{ultimo_dia:02d}',
        })

# ──────────────────────────────────────────────────────────────
# TILES SENTINEL
# SentinelHub limita a ~2500 px por lado.
# A 10 m → ~25 km por tile (~80 tiles para Cundinamarca).
# A 50 m → ~125 km por tile (~4 tiles para Cundinamarca).
# ──────────────────────────────────────────────────────────────
SENTINEL_GSD_M = RESOLUCION_M  # usa la resolución del proyecto
SENTINEL_MAX_PX = 2500        # límite de SentinelHub por lado

def generar_tiles_sentinel(bbox=None, gsd_m=None):
    """
    Divide un bbox [west, south, east, north] en sub-bboxes cuadrados.
    El tamaño del tile se calcula para no superar SENTINEL_MAX_PX px por lado
    a la resolución gsd_m indicada.
    Retorna lista de dicts: {'bbox': [w,s,e,n], 'label': 'r{row}_c{col}', 'size': (w_px, h_px)}
    """
    import math
    bbox  = bbox  or BBOX_WGS84
    gsd_m = gsd_m or SENTINEL_GSD_M

    west, south, east, north = bbox
    lat_mid = (south + north) / 2

    # metros por grado en cada eje
    m_per_deg_lat = 111_320
    m_per_deg_lon = 111_320 * math.cos(math.radians(lat_mid))

    # tamaño máximo de tile en grados para no superar SENTINEL_MAX_PX
    max_tile_deg_lat = (SENTINEL_MAX_PX * gsd_m) / m_per_deg_lat
    max_tile_deg_lon = (SENTINEL_MAX_PX * gsd_m) / m_per_deg_lon

    n_rows = math.ceil((north - south) / max_tile_deg_lat)
    n_cols = math.ceil((east  - west)  / max_tile_deg_lon)

    tiles = []
    for row in range(n_rows):
        for col in range(n_cols):
            t_west  = west  + col * max_tile_deg_lon
            t_south = south + row * max_tile_deg_lat
            t_east  = min(t_west  + max_tile_deg_lon, east)
            t_north = min(t_south + max_tile_deg_lat, north)

            w_m = (t_east - t_west) * m_per_deg_lon
            h_m = (t_north - t_south) * m_per_deg_lat
            w_px = max(1, round(w_m / gsd_m))
            h_px = max(1, round(h_m / gsd_m))

            tiles.append({
                'bbox': [t_west, t_south, t_east, t_north],
                'label': f'r{row:02d}_c{col:02d}',
                'size': (w_px, h_px),
            })

    return tiles

SENTINEL_TILES = generar_tiles_sentinel()

# ──────────────────────────────────────────────────────────────
# CREDENCIALES COPERNICUS DATA SPACE (CDSE)
# Leídas desde extractores/.env — nunca hardcodear aquí.
# ──────────────────────────────────────────────────────────────
CDSE_CLIENT_ID     = os.environ.get('CDSE_CLIENT_ID', '')
CDSE_CLIENT_SECRET = os.environ.get('CDSE_CLIENT_SECRET', '')
CDSE_BASE_URL      = 'https://sh.dataspace.copernicus.eu'
CDSE_TOKEN_URL     = (
    'https://identity.dataspace.copernicus.eu'
    '/auth/realms/CDSE/protocol/openid-connect/token'
)

if not CDSE_CLIENT_ID or not CDSE_CLIENT_SECRET:
    import warnings
    warnings.warn(
        "CDSE_CLIENT_ID / CDSE_CLIENT_SECRET no configurados. "
        "Copiar extractores/.env.example → extractores/.env y completar las credenciales.",
        stacklevel=2,
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
    'target_mgn':    os.path.join(RAW_DIR, 'target', 'mgn'),
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
# App Token de datos.gov.co (Socrata) — leído desde extractores/.env
# Sin token: throttling por IP compartido.
# Con token: hasta 1.000 requests/hora sin throttling por request.
SODA_APP_TOKEN = os.environ.get('SODA_APP_TOKEN', '')

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
    # Cobertura UPRA en Cundinamarca (verificado 2026-04 contra REST):
    #   - Papa: SI, 2021-2024 semestrales (miles de poligonos por semestre)
    #   - Maiz: NO. UPRA monitorea maiz solo en Meta, Tolima, Cordoba, Cesar,
    #     Huila (zonas industriales). Las 17k ha de maiz cundinamarques vienen
    #     de EVA estadistica, no de monitoreo satelital.
    #   - Cacao: removido. Las capas departamentales Cacao_2020-2023 estan
    #     vacias para depto=25; la capa nacional `cacao_nal_2023` cubre solo
    #     un anio y mezcla geometrias agregadas. Cacao se etiqueta solo via L2 EVA.
    #   - Arroz: removido (cultivo de tierra caliente, no relevante).
    #
    # Papa (2021-2024) — semestres nombrados _s1/_s2
    'papa_2021_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2021_s1/MapServer/0',
    'papa_2021_s2':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2021_s2/MapServer/0',
    'papa_2022_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2022_s1/MapServer/0',
    'papa_2022_s2':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2022_s2/MapServer/0',
    'papa_2023_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2023_s1/MapServer/0',
    'papa_2023_s2':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2023_s2/MapServer/0',
    'papa_2024_s1':  f'{UPRA_BASE}/MonitoreoCultivos/papa_2024_s1/MapServer/0',
}

UPRA_APTITUD = {
    # Capas de aptitud SIPRA alineadas con los TOP-12 cultivos EVA de Cundinamarca.
    # (Papa, Caña, Café, Maíz, Plátano, Mango, Frijol, Cacao, Arveja, Palma, Banano, Naranja)
    # NOTA: UPRA NO publica capas de aptitud para Arveja ni Naranja — estos cultivos
    # solo reciben etiqueta via EVA municipal; el proxy No_apto ignora ausencia.
    # ── Papa ──
    'papa_capiro_s1':   f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_diacol_capiro_sem_1/MapServer/0',
    'papa_capiro_s2':   f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_diacol_capiro_sem_2/MapServer/0',
    'papa_s1':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_sem_1_Dic2019/MapServer/0',
    'papa_s2':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_papa_sem_2_Dic2019/MapServer/0',
    # ── Café ──
    'cafe':             f'{UPRA_BASE}/aptitud_uso_suelo/Aptitud_Cafe_Jul2022/MapServer/0',
    # ── Maíz ──
    'maiz_s1':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_maiz_sem_1_diciembre_2019/MapServer/0',
    'maiz_s2':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_maiz_sem_2_diciembre_2019/MapServer/0',
    # ── Caña panelera ──
    'cana_panelera':    f'{UPRA_BASE}/aptitud_uso_suelo/Aptitud_Cultivo_Comercial_Cana_Panelera_Oct2020/MapServer/0',
    # ── Cacao ──
    'cacao':            f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_cacao_diciembre_2019/MapServer/0',
    # ── Frijol ──
    'frijol':           f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_frijol_comercial/MapServer/0',
    # ── Palma ──
    'palma':            f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_palma_2018/MapServer/0',
    # ── Plátano (agregado 2026-04) ──
    'platano':          f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_platano/MapServer/0',
    # ── Mango (agregado 2026-04) ──
    'mango':            f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_mango_diciembre_2019/MapServer/0',
    # ── Banano (agregado 2026-04) ──
    'banano':           f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_banano/MapServer/0',
    # ── Auxiliares (No_apto proxy): cultivos adicionales para ampliar cobertura de
    # la intersección "No apta" de todos los cultivos ──
    'fresa':            f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_fresa_Dic2019/MapServer/0',
    'aguacate_hass':    f'{UPRA_BASE}/aptitud_uso_suelo/aptitud_aguacate_hass_Dic2019/MapServer/0',
}

# Cultivos EVA canonicos por area cosechada en Cundinamarca.
# Orden: area cosechada descendente (sin Papa).
# Top-12 originales (~77% area no-Papa) + 5 adicionales (~8% mas) = ~85% cobertura.
# Nuevos: Mora, Zanahoria, Tomate_Arbol, Yuca, Habichuela (todos >47K ha acumuladas).
EVA_TOP_CULTIVOS = [
    'Papa', 'Cana_Panelera', 'Cafe', 'Maiz', 'Platano', 'Mango',
    'Frijol', 'Cacao', 'Arveja', 'Palma', 'Banano', 'Naranja',
    'Mora', 'Zanahoria', 'Tomate_Arbol', 'Yuca', 'Habichuela',
]
# Conjunto completo de clases del modelo (19 clases)
MODEL_CLASSES = EVA_TOP_CULTIVOS + ['Otros_cultivos', 'No_apto']

# ──────────────────────────────────────────────────────────────
# DANE MGN — Marco Geoestadístico Nacional (Municipios)
# Se usan endpoints IGAC/ArcGIS públicos como fuente primaria; si fallan,
# se permite colocar manualmente un shapefile en RAW_DIR/mgn/.
# ──────────────────────────────────────────────────────────────
DANE_MGN_URLS = [
    # ESRI Colombia - Municipios 2024 (verificado 2026-04: campos
    # MpCodigo [5-6 dig DANE], MpNombre, Depto [nombre depto])
    'https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services/Municipios_2024/FeatureServer/0',
    # Alternativa: versión MapServer del mismo recurso
    'https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services/Municipios_2024/MapServer/0',
]

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
