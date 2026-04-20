"""
run_all.py
════════════════════════════════════════════════════════════════
Ejecuta todos los extractores en secuencia para descargar
los datos crudos del proyecto AgroPlus (¿Qué Sembrar?).

Uso (con uv desde la raíz del proyecto):
    uv run extractores/run_all.py                        # Ejecutar todos
    uv run extractores/run_all.py 3                      # Ejecutar solo el script 03 (IGAC)
    uv run extractores/run_all.py 5 6                    # Ejecutar scripts 05 y 06 (Sentinel-2 y 1)

    # Script 01: pasos individuales del clima IDEAM
    uv run extractores/run_all.py 01:temp                # Solo temperatura
    uv run extractores/run_all.py 01:precip              # Solo precipitación (todos los años)
    uv run extractores/run_all.py 01:precip:2021         # Precipitación año 2021
    uv run extractores/run_all.py 01:precip:2021:6       # Precipitación junio 2021
    uv run extractores/run_all.py 01:humedad             # Solo humedad
    uv run extractores/run_all.py 01:normales            # Solo normales climatológicas

    # Script 06: re-descargar Sentinel-1 (detecta y reemplaza archivos vacíos)
    uv run extractores/run_all.py 6                      # Todos los meses
    uv run extractores/06_extraer_sentinel1.py --mes 2022_01  # Un mes específico

Cada script es idempotente: si un archivo ya existe y es válido, lo salta.
Los archivos vacíos o corruptos se detectan y re-descargan automáticamente.
Se puede reanudar después de una interrupción.

Dependencias (instaladas automáticamente por uv):
    requests, pandas, geopandas, rasterio, sentinelhub, numpy, scipy, pysheds
"""

import subprocess
import sys
import os

SCRIPTS = [
    ('01', '01_extraer_clima_ideam.py',     'Clima IDEAM (Temperatura, Precipitación, Humedad, Normales)'),
    ('02', '02_extraer_chirps.py',          'Precipitación CHIRPS satelital'),
    ('03', '03_extraer_suelo_igac.py',      'Suelo IGAC (Propiedades Químicas + Vocación de Uso)'),
    ('04', '04_extraer_soilgrids.py',       'Suelo SoilGrids 2.0 (ISRIC — propiedades físicas)'),
    ('05', '05_extraer_sentinel2.py',       'Sentinel-2 índices espectrales (CDSE)'),
    ('06', '06_extraer_sentinel1.py',       'Sentinel-1 backscatter SAR (CDSE)'),
    ('07', '07_extraer_dem_topografia.py',  'Copernicus DEM topografía (Elevación, Pendiente, TWI)'),
    ('08', '08_extraer_target.py',          'Target: EVA + Monitoreo UPRA + SIPRA Aptitud'),
]


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Crear estructura de directorios
    from config import crear_directorios
    crear_directorios()

    # Parsear argumentos: soporta "01", "01:temp", "01:precip:2021", "01:precip:2021:6"
    def parse_arg(arg):
        """Retorna (numero, extra_args[]) dado un argumento como '01:precip:2021:6'."""
        partes = arg.split(':')
        return partes[0], partes[1:]

    if len(sys.argv) > 1:
        args_parsed = [parse_arg(a) for a in sys.argv[1:]]
        numeros = set(n for n, _ in args_parsed)
        scripts_sel = [(n, s, d) for n, s, d in SCRIPTS if n in numeros]
        # Mapa de extras por número
        extras_map = {n: ex for n, ex in args_parsed}
    else:
        scripts_sel = SCRIPTS
        extras_map = {}

    print("="*70)
    print("EXTRACCIÓN DE DATOS — PROYECTO ¿QUÉ SEMBRAR?")
    print("Cundinamarca, Colombia | Ventana: 2019-2024")
    print("="*70)
    print(f"\nScripts a ejecutar: {len(scripts_sel)}")
    for num, script, desc in scripts_sel:
        extra = extras_map.get(num, [])
        sufijo = f" (--step {' '.join(extra)})" if extra else ""
        print(f"  [{num}] {desc}{sufijo}")
    print()

    resultados = []
    for num, script, desc in scripts_sel:
        extra = extras_map.get(num, [])

        print(f"\n{'▓'*70}")
        print(f"  [{num}] {desc}")
        print(f"{'▓'*70}\n")

        script_path = os.path.join(base_dir, script)

        # Construir argumentos extra para el script
        extra_args = []
        if extra:
            step = extra[0]
            extra_args += ['--step', step]
            if len(extra) >= 2:
                extra_args += ['--year', extra[1]]
            if len(extra) >= 3:
                extra_args += ['--mes', extra[2]]

        try:
            result = subprocess.run(
                [sys.executable, script_path] + extra_args,
                cwd=base_dir,
                timeout=7200,  # 2 horas máximo por script
            )
            status = '✓ OK' if result.returncode == 0 else f'✗ Error (código {result.returncode})'
        except subprocess.TimeoutExpired:
            status = '⏱ Timeout (2h)'
        except Exception as e:
            status = f'✗ Error: {e}'

        resultados.append((num, desc, status))

    print(f"\n\n{'='*70}")
    print("RESUMEN DE EXTRACCIÓN")
    print(f"{'='*70}")
    for num, desc, status in resultados:
        print(f"  [{num}] {status:20s} {desc}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
