"""
09_extraer_municipios_dane.py
===================================================================
Descarga el Marco Geoestadistico Nacional (MGN-DANE) — poligonos de
municipios de Cundinamarca con codigo DANE.

Se usa para rasterizar el codigo municipal al grid de 50 m y poder
cruzar cada pixel con los registros EVA municipales durante la
construccion de la vista minable (paso 3 de `asignar_target`).

Estrategia de descarga (en orden):
  1. ESRI Colombia - Municipios_2024 FeatureServer (verificado)
  2. ESRI Colombia - Municipios_2024 MapServer (alt)
  3. Fallback: instrucciones para colocar manualmente el shapefile
     oficial (MGN_ANM_MPIO_POLITICO.shp) en raw/target/mgn/.

Salida:
  extractores/raw/target/mgn/municipios_cundinamarca.geojson

Campos conservados (normalizados):
  - cod_dane     : codigo DANE municipio (5 chars, str)
  - nombre_mpio  : nombre del municipio
  - cod_dpto     : codigo DANE departamento (2 chars, str)
  - geometry     : Polygon / MultiPolygon en EPSG:4326

Uso:
    uv run extractores/09_extraer_municipios_dane.py
    uv run extractores/09_extraer_municipios_dane.py --force
"""

import os
import sys
import json
import time
import argparse

import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    DIRS, DEPT_DANE, HEADERS_GOV, DANE_MGN_URLS, crear_directorios
)


OUT_FILE = os.path.join(DIRS['target_mgn'], 'municipios_cundinamarca.geojson')


# Candidatos de nombres de campo DANE municipal/departamental segun fuente.
# El servicio a veces expone 'MPIO_CDPMP' (5 dig), 'cod_dane', 'COD_DANE',
# 'codigo_mpio', 'MpCodigo', etc.
CAMPOS_COD_MUN = [
    # ESRI Colombia Municipios_2024 (verificado)
    'MpCodigo', 'mpcodigo',
    # MGN oficial DANE
    'mpio_cdpmp', 'MPIO_CDPMP', 'MPIO_CCDGO', 'mpio_ccdgo',
    # Otras fuentes
    'cod_dane', 'COD_DANE', 'codigo_mpio', 'COD_MPIO',
    'cod_mpio', 'CODIGO_DIVIPOLA', 'divipola',
]
CAMPOS_COD_DPTO = [
    'dpto_ccdgo', 'DPTO_CCDGO', 'cod_dpto', 'COD_DPTO',
    'codigo_dpto', 'DPCODIGO', 'dpcodigo', 'CODIGO_DEPARTAMENTO',
]
# Nombre del municipio (string)
CAMPOS_NOMBRE = [
    'MpNombre', 'mpnombre',
    'mpio_cnmbr', 'MPIO_CNMBR', 'nombre_mpio', 'NOMBRE_MPIO',
    'nombre_municipio', 'MPIO', 'municipio', 'MUNICIPIO',
    'nom_mpio', 'NOM_MPIO',
]
# Nombre del departamento (string, mayusculas). Se usa para filtrar cuando
# no hay campo de codigo departamental.
CAMPOS_NOMBRE_DPTO = [
    'Depto', 'DEPTO', 'depto', 'DEPARTAMENTO', 'departamento',
    'NOMBRE_DPTO', 'nombre_dpto',
]


def _primer_campo_presente(props, candidatos):
    """Devuelve el primer campo de `candidatos` que exista en `props`."""
    if not props:
        return None
    # Normalizar keys a minusculas para matching case-insensitive
    props_lower = {k.lower(): k for k in props.keys()}
    for cand in candidatos:
        if cand.lower() in props_lower:
            return props_lower[cand.lower()]
    return None


def _normalizar_feature(feat):
    """Convierte un feature ArcGIS/GeoJSON al esquema canonico del proyecto."""
    props = feat.get('properties') or feat.get('attributes') or {}

    campo_mun = _primer_campo_presente(props, CAMPOS_COD_MUN)
    campo_dpto_cod = _primer_campo_presente(props, CAMPOS_COD_DPTO)
    campo_dpto_nom = _primer_campo_presente(props, CAMPOS_NOMBRE_DPTO)
    campo_nom = _primer_campo_presente(props, CAMPOS_NOMBRE)

    cod_mun_raw = str(props.get(campo_mun, '')).strip() if campo_mun else ''
    cod_dpto_raw = str(props.get(campo_dpto_cod, '')).strip() if campo_dpto_cod else ''
    nombre_dpto = str(props.get(campo_dpto_nom, '')).strip() if campo_dpto_nom else ''
    nombre = str(props.get(campo_nom, '')).strip() if campo_nom else ''

    # Normalizar cod_mun a 5 chars (con ceros a la izquierda)
    if cod_mun_raw.isdigit():
        cod_mun = cod_mun_raw.zfill(5)
    else:
        cod_mun = cod_mun_raw

    # cod_dpto = primeros 2 chars de cod_mun si no viene directo
    if not cod_dpto_raw and len(cod_mun) >= 2:
        cod_dpto = cod_mun[:2]
    else:
        cod_dpto = cod_dpto_raw.zfill(2) if cod_dpto_raw.isdigit() else cod_dpto_raw

    geom = feat.get('geometry')
    if geom is None:
        return None

    return {
        'type': 'Feature',
        'properties': {
            'cod_dane': cod_mun,
            'cod_dpto': cod_dpto,
            'nombre_dpto': nombre_dpto.upper(),
            'nombre_mpio': nombre,
        },
        'geometry': geom,
    }


def _filtrar_cundinamarca(features):
    """Filtra features que pertenezcan a Cundinamarca.
    Acepta: cod_dpto == '25' OR cod_dane empieza por '25' OR nombre_dpto contiene 'CUNDINAMARCA'.
    """
    out = []
    for f in features:
        p = f['properties']
        cd = p.get('cod_dpto', '')
        cm = p.get('cod_dane', '')
        nd = p.get('nombre_dpto', '') or ''
        if cd == DEPT_DANE or cm.startswith(DEPT_DANE) or 'CUNDINAMARCA' in nd:
            out.append(f)
    return out


def descargar_arcgis(url):
    """
    Descarga features de un MapServer/FeatureServer ArcGIS REST (paginado).
    Prueba varias cláusulas `where` en orden hasta encontrar una que funcione
    contra el esquema del servicio; luego pagina.
    Retorna lista de features normalizados en formato GeoJSON, o None si falla.
    """
    # Orden de preferencia: filtros específicos primero, genérico al final.
    where_options = [
        "Depto='CUNDINAMARCA'",                     # ESRI Colombia Municipios_2024
        f"MpCodigo LIKE '{DEPT_DANE}%'",            # ESRI Colombia (por codigo)
        f"DPTO_CCDGO='{DEPT_DANE}'",                # MGN DANE oficial
        f"dpto_ccdgo='{DEPT_DANE}'",
        f"cod_dpto='{DEPT_DANE}'",
        f"MPIO_CDPMP LIKE '{DEPT_DANE}%'",
        '1=1',                                        # fallback: todo, filtrar local
    ]

    # Buscamos el primer where que no produzca error ArcGIS en la primera pagina.
    for where in where_options:
        primera_pagina = _consultar_pagina(url, where, offset=0, page=2000)
        if primera_pagina is None:
            # Error de red — probar siguiente url (no tiene sentido iterar where)
            return None
        if primera_pagina.get('error'):
            err = primera_pagina['error'].get('message', '')
            print(f"    where fallo ({where}): {err}")
            continue
        break
    else:
        print("    Ningun where funciono en este endpoint.")
        return None

    feats = primera_pagina.get('features', [])
    print(f"    where='{where}' -> {len(feats)} municipios en pagina 1")

    all_features = list(feats)
    offset = len(feats)

    # Si hay mas paginas, seguir bajando
    while primera_pagina.get('exceededTransferLimit') or len(feats) >= 2000:
        primera_pagina = _consultar_pagina(url, where, offset=offset, page=2000)
        if primera_pagina is None or primera_pagina.get('error'):
            break
        feats = primera_pagina.get('features', [])
        if not feats:
            break
        all_features.extend(feats)
        offset += len(feats)
        print(f"    -> {len(feats)} municipios (total: {len(all_features)})")
        if len(feats) < 2000:
            break
        time.sleep(0.5)

    if not all_features:
        return None

    # Normalizar + filtrar a Cundinamarca
    normalizados = [_normalizar_feature(f) for f in all_features]
    normalizados = [f for f in normalizados if f is not None]
    return _filtrar_cundinamarca(normalizados)


def _consultar_pagina(url, where, offset, page):
    """Hace una consulta paginada al endpoint. Retorna dict o None en error de red."""
    params = {
        'where': where,
        'outFields': '*',
        'f': 'geojson',
        'returnGeometry': 'true',
        'resultOffset': offset,
        'resultRecordCount': page,
        'outSR': '4326',
    }
    try:
        r = requests.get(f"{url}/query", params=params, headers=HEADERS_GOV,
                         timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    Error consultando {url}: {e}")
        return None


def intentar_descarga():
    """Prueba URLs en orden hasta encontrar una que funcione."""
    for i, url in enumerate(DANE_MGN_URLS, 1):
        print(f"\n  [{i}/{len(DANE_MGN_URLS)}] Intentando: {url}")
        features = descargar_arcgis(url)
        if features:
            print(f"  OK: {len(features)} municipios de Cundinamarca extraidos.")
            return features
        print(f"     Fallo; probando siguiente fuente...")
    return None


def imprimir_fallback_manual():
    """Instrucciones para colocar manualmente el shapefile MGN."""
    out_dir = DIRS['target_mgn']
    print("\n" + "=" * 70)
    print("FALLBACK MANUAL")
    print("=" * 70)
    print("No se pudo descargar programaticamente. Opciones:")
    print()
    print("1) Descargar desde DANE Geoportal:")
    print("   https://geoportal.dane.gov.co/servicios/descarga-y-metadatos/")
    print("   descarga-mgn-marco-geoestadistico-nacional/")
    print("   - Seleccionar MGN 2018 o mas reciente")
    print("   - Descargar MGN_ANM_MPIO_POLITICO.shp (capa municipios)")
    print()
    print("2) Alternativa (IGAC):")
    print("   https://geoportal.igac.gov.co/contenido/datos-abiertos-cartografia")
    print()
    print(f"3) Colocar el .shp (con .dbf, .shx, .prj) en:")
    print(f"   {out_dir}")
    print()
    print("4) O convertir manualmente a GeoJSON:")
    print(f"   ogr2ogr -f GeoJSON -t_srs EPSG:4326 \\")
    print(f"     -where \"DPTO_CCDGO='25'\" \\")
    print(f"     {OUT_FILE} \\")
    print(f"     MGN_ANM_MPIO_POLITICO.shp")
    print()
    print("Una vez presente el archivo, re-ejecutar este extractor.")
    print("=" * 70)


def convertir_shapefile_local():
    """
    Si existe un .shp en raw/target/mgn/, lo convierte a GeoJSON con el
    esquema canonico. Retorna True si se convirtio exitosamente.
    """
    out_dir = DIRS['target_mgn']
    try:
        import geopandas as gpd
    except ImportError:
        print("  geopandas no esta disponible; no se puede convertir SHP local.")
        return False

    # Buscar cualquier .shp en la carpeta
    import glob
    shps = glob.glob(os.path.join(out_dir, '*.shp'))
    if not shps:
        return False

    shp = shps[0]
    print(f"\n  Shapefile local encontrado: {shp}")
    print(f"  Convirtiendo a GeoJSON...")

    try:
        gdf = gpd.read_file(shp)
    except Exception as e:
        print(f"  Error leyendo shapefile: {e}")
        return False

    # Reproyectar a 4326 si hace falta
    if gdf.crs and str(gdf.crs).upper() != 'EPSG:4326':
        gdf = gdf.to_crs('EPSG:4326')

    # Identificar campos
    cols_lower = {c.lower(): c for c in gdf.columns}

    def _col(cands):
        for c in cands:
            if c.lower() in cols_lower:
                return cols_lower[c.lower()]
        return None

    col_mun = _col(CAMPOS_COD_MUN)
    col_dpto = _col(CAMPOS_COD_DPTO)
    col_nom = _col(CAMPOS_NOMBRE)

    if not col_mun:
        print(f"  No se encontro campo de codigo DANE municipal en: {list(gdf.columns)}")
        return False

    gdf_out = gdf.copy()
    gdf_out['cod_dane'] = gdf[col_mun].astype(str).str.zfill(5)
    gdf_out['cod_dpto'] = (
        gdf[col_dpto].astype(str).str.zfill(2) if col_dpto
        else gdf_out['cod_dane'].str[:2]
    )
    gdf_out['nombre_mpio'] = gdf[col_nom] if col_nom else ''

    # Filtrar Cundinamarca
    gdf_out = gdf_out[gdf_out['cod_dpto'] == DEPT_DANE].copy()
    gdf_out = gdf_out[['cod_dane', 'cod_dpto', 'nombre_mpio', 'geometry']]

    if len(gdf_out) == 0:
        print(f"  No hay municipios de Cundinamarca (cod_dpto={DEPT_DANE}) en el shapefile.")
        return False

    gdf_out.to_file(OUT_FILE, driver='GeoJSON')
    print(f"  Guardado: {OUT_FILE} ({len(gdf_out)} municipios)")
    return True


def guardar_geojson(features, path):
    geojson = {'type': 'FeatureCollection', 'features': features}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"  Guardado: {path} ({len(features)} municipios)")


def main():
    parser = argparse.ArgumentParser(
        description='Descarga MGN-DANE (municipios de Cundinamarca).'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Sobreescribir archivo existente.'
    )
    args = parser.parse_args()

    crear_directorios()

    if os.path.exists(OUT_FILE) and not args.force:
        print(f"Ya existe: {OUT_FILE}")
        print("Usar --force para regenerar.")
        return

    print("=" * 70)
    print("DESCARGA MGN-DANE (Municipios Cundinamarca)")
    print("=" * 70)

    # Primero probar si hay shapefile local
    if convertir_shapefile_local():
        return

    # Intentar descarga remota
    features = intentar_descarga()
    if features:
        guardar_geojson(features, OUT_FILE)
        return

    imprimir_fallback_manual()
    sys.exit(1)


if __name__ == '__main__':
    main()
