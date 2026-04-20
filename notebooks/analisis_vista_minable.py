"""
Analisis estadistico completo de la vista minable.
Genera informe en docs/informe_vista_minable.md
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from collections import Counter

warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET = os.path.join(BASE, 'vista_minable', 'vista_minable_full.parquet')
OUT_MD = os.path.join(BASE, 'docs', 'informe_vista_minable.md')

# ── Cargar datos ──────────────────────────────────────────────
print("Cargando vista minable...")
df = pd.read_parquet(PARQUET)
print(f"  Dimensiones: {df.shape[0]:,} filas × {df.shape[1]} columnas")

# ── Separar columnas ──────────────────────────────────────────
meta_cols = ['pixel_id', 'x', 'y', 'semestre']
target_cols = ['cultivo', 'cultivo_id', 'confianza', 'fuente', 'rendimiento_tha']
feature_cols = [c for c in df.columns if c not in meta_cols + target_cols]

# Separar features numéricas y categóricas
feat_num = df[feature_cols].select_dtypes(include=[np.number]).columns.tolist()
feat_cat = [c for c in feature_cols if c not in feat_num]

report = []
report.append("# Informe de Análisis Estadístico - Vista Minable")
report.append("## Proyecto: ¿Qué Sembrar? - AgroPlus")
report.append(f"### Fecha: {pd.Timestamp.now().strftime('%d/%m/%Y')}")
report.append("")
report.append("---")
report.append("")

# ── RESUMEN EJECUTIVO ─────────────────────────────────────────
report.append("## RESUMEN EJECUTIVO")
report.append("")
report.append(f"Vista minable: **{df.shape[0]:,} filas × {df.shape[1]} columnas**")
report.append(f"- Features numéricos: **{len(feat_num)}**")
report.append(f"- Features categóricos: **{len(feat_cat)}**")
report.append(f"- Columnas target: **{len(target_cols)}**")
report.append(f"- Columnas metadata: **{len(meta_cols)}**")
report.append(f"- Cultivos únicos: **{df['cultivo'].nunique()}**")
report.append(f"- Semestres: **{df['semestre'].nunique()}** ({sorted(df['semestre'].unique())[0]} a {sorted(df['semestre'].unique())[-1]})")
report.append("")

# ── 1. VALIDACIÓN ESTRUCTURAL ─────────────────────────────────
report.append("---")
report.append("")
report.append("## 1. VALIDACIÓN ESTRUCTURAL")
report.append("")

# 1.1 Duplicados
dup = df.duplicated(subset=['x', 'y', 'semestre']).sum()
report.append(f"### 1.1 Filas duplicadas (x, y, semestre)")
report.append(f"- Duplicados exactos: **{dup:,}** ({100*dup/len(df):.2f}%)")
if dup > 0:
    report.append("- ⚠️ **ALERTA**: Hay filas duplicadas. Un mismo píxel-semestre no debería aparecer más de una vez.")
else:
    report.append("- ✅ Sin duplicados")
report.append("")

# 1.2 Columnas duplicadas
dup_cols = [c for c in df.columns if list(df.columns).count(c) > 1]
report.append(f"### 1.2 Columnas duplicadas")
report.append(f"- Columnas con nombre repetido: **{dup_cols if dup_cols else 'Ninguna'}**")
report.append("")

# 1.3 Rango de coordenadas
report.append(f"### 1.3 Rango de coordenadas (EPSG:3116)")
report.append(f"| Eje | Min | Max | Rango |")
report.append(f"|-----|-----|-----|-------|")
report.append(f"| X | {df['x'].min():,.0f} | {df['x'].max():,.0f} | {df['x'].max()-df['x'].min():,.0f} |")
report.append(f"| Y | {df['y'].min():,.0f} | {df['y'].max():,.0f} | {df['y'].max()-df['y'].min():,.0f} |")
report.append("")

# 1.4 Semestres
sems = sorted(df['semestre'].unique())
report.append(f"### 1.4 Semestres cubiertos")
report.append(f"| Semestre | Filas | % del total |")
report.append(f"|----------|-------|-------------|")
for s in sems:
    n = (df['semestre'] == s).sum()
    report.append(f"| {s} | {n:,} | {100*n/len(df):.1f}% |")
report.append("")

# ── 2. ANÁLISIS DEL TARGET ────────────────────────────────────
report.append("---")
report.append("")
report.append("## 2. ANÁLISIS DEL TARGET (Variable Objetivo)")
report.append("")

# 2.1 Distribución de cultivos
report.append("### 2.1 Distribución de cultivos")
vc = df['cultivo'].value_counts()
report.append(f"| Cultivo | Filas | % del Total | Acumulado |")
report.append(f"|---------|-------|-------------|-----------|")
acum = 0
for cult, n in vc.items():
    acum += n
    report.append(f"| {cult} | {n:,} | {100*n/len(df):.1f}% | {100*acum/len(df):.1f}% |")
report.append("")

# Desbalance
max_c = vc.iloc[0]
min_c = vc.iloc[-1]
ratio = max_c / min_c
report.append(f"**Ratio de desbalance**: {ratio:.1f}:1 (max='{vc.index[0]}' vs min='{vc.index[-1]}')")
if ratio > 10:
    report.append("🚨 **DESBALANCE EXTREMO** — Se requiere balanceo obligatorio (SMOTE, class_weight, undersampling)")
elif ratio > 3:
    report.append("⚠️ **DESBALANCE MODERADO** — Recomendado usar class_weight o SMOTE")
report.append("")

# 2.2 Distribución por fuente
report.append("### 2.2 Distribución por fuente de etiqueta")
fuente_vc = df['fuente'].value_counts()
report.append(f"| Fuente | Filas | % | Confianza media |")
report.append(f"|--------|-------|---|-----------------|")
for f in fuente_vc.index:
    n = fuente_vc[f]
    conf = df.loc[df['fuente']==f, 'confianza'].mean()
    report.append(f"| {f} | {n:,} | {100*n/len(df):.1f}% | {conf:.2f} |")
report.append("")

# 2.3 Distribución por fuente y cultivo
report.append("### 2.3 Cultivos por fuente")
report.append("")
ct = pd.crosstab(df['cultivo'], df['fuente'], margins=True)
report.append(ct.to_markdown())
report.append("")

# 2.4 Confianza
report.append("### 2.4 Distribución de confianza")
conf_stats = df['confianza'].describe()
report.append(f"| Stat | Valor |")
report.append(f"|------|-------|")
for stat_name in ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']:
    report.append(f"| {stat_name} | {conf_stats[stat_name]:.4f} |")
report.append("")

# 2.5 Rendimiento
report.append("### 2.5 Rendimiento (ton/ha)")
rend = df['rendimiento_tha'].dropna()
if len(rend) > 0:
    report.append(f"| Stat | Valor |")
    report.append(f"|------|-------|")
    for stat_name in ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']:
        report.append(f"| {stat_name} | {rend.describe()[stat_name]:.2f} |")
    report.append(f"- % NaN: {100*df['rendimiento_tha'].isna().mean():.1f}%")
    report.append("")
    # Rendimiento por cultivo
    report.append("#### Rendimiento por cultivo")
    report.append("")
    rend_cult = df.groupby('cultivo')['rendimiento_tha'].agg(['count', 'mean', 'std', 'min', 'median', 'max'])
    rend_cult = rend_cult.sort_values('count', ascending=False)
    report.append(rend_cult.to_markdown(floatfmt='.2f'))
report.append("")

# ── 3. ANÁLISIS DE VALORES FALTANTES ──────────────────────────
report.append("---")
report.append("")
report.append("## 3. ANÁLISIS DE VALORES FALTANTES (NaN, Nulos, Ceros)")
report.append("")

report.append("### 3.1 Valores NaN por variable")
report.append("")
nan_pct = df[feat_num].isna().mean() * 100
nan_sorted = nan_pct.sort_values(ascending=False)

report.append(f"| Variable | % NaN | % Válido | Tipo |")
report.append(f"|----------|-------|----------|------|")
for col in nan_sorted.index:
    pct = nan_sorted[col]
    if pct == 0:
        continue
    val_pct = 100 - pct
    # Clasificar
    if pct > 50:
        tipo = "🚨 CRÍTICO"
    elif pct > 20:
        tipo = "⚠️ Alto"
    elif pct > 5:
        tipo = "📋 Medio"
    else:
        tipo = "✅ Bajo"
    report.append(f"| {col} | {pct:.2f}% | {val_pct:.2f}% | {tipo} |")

# Variables sin NaN
sin_nan = (nan_sorted == 0).sum()
report.append(f"\n**{sin_nan} variables** sin ningún NaN")
report.append("")

# 3.2 Ceros
report.append("### 3.2 Valores cero por variable")
report.append("")
zero_report = []
for col in feat_num:
    n_zero = (df[col] == 0).sum()
    pct_zero = 100 * n_zero / len(df)
    if pct_zero > 0.5:  # Solo reportar si > 0.5%
        zero_report.append((col, pct_zero, n_zero))

if zero_report:
    report.append(f"| Variable | % Ceros | N Ceros | Diagnóstico |")
    report.append(f"|----------|---------|---------|-------------|")
    for col, pct, n in sorted(zero_report, key=lambda x: -x[1]):
        # Determinar si los ceros son válidos
        if 'sg_' in col:
            diag = "⚠️ Sospechoso (pH=0, SOC=0 son inválidos)"
        elif 'pendiente' in col:
            diag = "✅ Válido (terreno plano)"
        elif 'twi' in col:
            diag = "⚠️ Revisar (TWI=0 es inusual)"
        else:
            diag = "Revisar"
        report.append(f"| {col} | {pct:.2f}% | {n:,} | {diag} |")
else:
    report.append("No se encontraron variables con >0.5% de ceros")
report.append("")

# 3.3 Valores atípicos extremos
report.append("### 3.3 Valores atípicos extremos")
report.append("")
outlier_report = []
for col in feat_num:
    serie = df[col].dropna()
    if len(serie) == 0:
        continue
    q1 = serie.quantile(0.01)
    q99 = serie.quantile(0.99)
    mean = serie.mean()
    std = serie.std()
    if std > 0:
        # Valores más allá de 5 std
        n_extreme = ((serie > mean + 5*std) | (serie < mean - 5*std)).sum()
        pct_extreme = 100 * n_extreme / len(serie)
        if pct_extreme > 0.1:
            outlier_report.append((col, pct_extreme, n_extreme, serie.min(), serie.max(), mean, std))

if outlier_report:
    report.append(f"| Variable | % Extremos | N | Min | Max | Mean | Std |")
    report.append(f"|----------|------------|---|-----|-----|------|-----|")
    for col, pct, n, mn, mx, mean, std in sorted(outlier_report, key=lambda x: -x[1]):
        report.append(f"| {col} | {pct:.2f}% | {n:,} | {mn:.2f} | {mx:.2f} | {mean:.2f} | {std:.2f} |")
report.append("")

# ── 4. ESTADÍSTICAS DESCRIPTIVAS ──────────────────────────────
report.append("---")
report.append("")
report.append("## 4. ESTADÍSTICAS DESCRIPTIVAS POR GRUPO")
report.append("")

# Identificar grupos
topo_vars = [c for c in feat_num if any(x in c for x in ['elevacion', 'pendiente', 'twi', 'aspecto', 'piso'])]
sg_vars = [c for c in feat_num if c.startswith('sg_')]
igac_vars = [c for c in feat_num if c.startswith('igac_')]
clima_vars = [c for c in feat_num if any(x in c for x in ['temperatura', 'humedad', 'chirps', 'amplitud', 'anomalia', 'aridez'])]
s2_vars = [c for c in feat_num if c.startswith('s2_')]
eng_vars = [c for c in feat_num if any(x in c for x in ['ndvi_max', 'ndvi_integral', 'indice_fertilidad'])]

groups = [
    ("Topografía", topo_vars),
    ("SoilGrids (Suelo)", sg_vars),
    ("IGAC (Suelo)", igac_vars),
    ("Clima (IDEAM + CHIRPS)", clima_vars),
    ("Sentinel-2 (Satélite)", s2_vars),
    ("Features Derivadas", eng_vars),
]

for group_name, group_vars in groups:
    if not group_vars:
        continue
    report.append(f"### {group_name}")
    report.append("")
    report.append(f"| Variable | % NaN | Mean | Std | Min | Q1 | Mediana | Q3 | Max | % Ceros |")
    report.append(f"|----------|-------|------|-----|-----|----|---------|----|-----|---------|")
    for col in group_vars:
        serie = df[col]
        n_nan = serie.isna().mean() * 100
        desc = serie.describe()
        n_zero = (serie == 0).mean() * 100
        report.append(f"| {col} | {n_nan:.1f}% | {desc['mean']:.2f} | {desc['std']:.2f} | {desc['min']:.2f} | {desc['25%']:.2f} | {desc['50%']:.2f} | {desc['75%']:.2f} | {desc['max']:.2f} | {n_zero:.1f}% |")
    report.append("")

# ── 5. CORRELACIONES ──────────────────────────────────────────
report.append("---")
report.append("")
report.append("## 5. ANÁLISIS DE CORRELACIONES")
report.append("")

# Tomar muestra para correlación (500k filas max)
sample_size = min(200_000, len(df))
df_sample = df[feat_num].sample(n=sample_size, random_state=42)

print("Calculando correlaciones...")
corr_matrix = df_sample.corr()

# Encontrar pares altamente correlacionados
high_corr = []
for i in range(len(corr_matrix.columns)):
    for j in range(i+1, len(corr_matrix.columns)):
        r = corr_matrix.iloc[i, j]
        if abs(r) > 0.80:
            high_corr.append((corr_matrix.columns[i], corr_matrix.columns[j], r))

high_corr.sort(key=lambda x: -abs(x[2]))

report.append(f"### 5.1 Pares con |r| > 0.80 ({len(high_corr)} pares encontrados)")
report.append("")
if high_corr:
    report.append(f"| Variable 1 | Variable 2 | Correlación (r) | Diagnóstico |")
    report.append(f"|------------|------------|-----------------|-------------|")
    for v1, v2, r in high_corr:
        if r > 0.95:
            diag = "🚨 Redundante — excluir una"
        elif r > 0.90:
            diag = "⚠️ Alta — considerar excluir"
        else:
            diag = "📋 Moderada-Alta — evaluar"
        report.append(f"| {v1} | {v2} | {r:.4f} | {diag} |")
report.append("")

# Correlación con target (si es numérico)
report.append("### 5.2 Variables menos correlacionadas (posiblemente irrelevantes)")
report.append("")
# Variables con baja varianza
low_var = []
for col in feat_num:
    serie = df[col].dropna()
    if len(serie) > 0:
        cv = serie.std() / (abs(serie.mean()) + 1e-10)  # Coeficiente de variación
        low_var.append((col, cv, serie.std(), serie.mean()))

low_var.sort(key=lambda x: abs(x[1]))
report.append(f"| Variable | CV (Coef. Variación) | Std | Mean |")
report.append(f"|----------|---------------------|-----|------|")
for col, cv, std, mean in low_var[:10]:
    report.append(f"| {col} | {cv:.4f} | {std:.4f} | {mean:.4f} |")
report.append("")

# ── 6. BALANCE DE CLASES POR SEMESTRE ─────────────────────────
report.append("---")
report.append("")
report.append("## 6. BALANCE DE CLASES POR SEMESTRE")
report.append("")

ct_sem = pd.crosstab(df['semestre'], df['cultivo'])
ct_sem = ct_sem.reindex(sorted(ct_sem.index))

report.append(ct_sem.to_markdown())
report.append("")

# ── 7. ALERTAS Y RECOMENDACIONES ──────────────────────────────
report.append("---")
report.append("")
report.append("## 7. ALERTAS Y RECOMENDACIONES")
report.append("")

alertas = []

# Alerta: desbalance
if ratio > 10:
    alertas.append(("🚨 CRÍTICA", f"Desbalance extremo de target: ratio {ratio:.0f}:1. "
                     f"'{vc.index[0]}' domina con {100*vc.iloc[0]/len(df):.1f}%. "
                     f"Usar SMOTE, class_weight='balanced', o undersampling."))

# Alerta: NaN altos
for col in nan_sorted.index:
    pct = nan_sorted[col]
    if pct > 30:
        alertas.append(("🚨 CRÍTICA", f"`{col}` tiene {pct:.1f}% NaN. Considerar excluir o imputar."))

# Alerta: ceros sospechosos
for col, pct, n in zero_report:
    if 'sg_' in col and pct > 1:
        alertas.append(("⚠️ ALTA", f"`{col}` tiene {pct:.1f}% ceros. SoilGrids codifica NoData como 0. "
                         f"Reemplazar 0 → NaN antes de modelar."))

# Alerta: correlaciones altas
redundantes = [(v1, v2, r) for v1, v2, r in high_corr if abs(r) > 0.95]
if redundantes:
    for v1, v2, r in redundantes[:5]:
        alertas.append(("⚠️ ALTA", f"`{v1}` y `{v2}` están casi perfectamente correlacionadas (r={r:.3f}). "
                         f"Excluir una para evitar multicolinealidad."))

# Alerta: poca varianza
for col, cv, std, mean in low_var[:3]:
    if abs(cv) < 0.01:
        alertas.append(("📋 MEDIA", f"`{col}` tiene varianza casi cero (CV={cv:.4f}). Sin poder discriminante."))

# Alerta: fuente concentrada
if fuente_vc.iloc[0] / len(df) > 0.80:
    alertas.append(("⚠️ ALTA", f"Fuente '{fuente_vc.index[0]}' domina con "
                     f"{100*fuente_vc.iloc[0]/len(df):.1f}%. "
                     f"Esto significa que la mayoría de etiquetas vienen de EVA (confianza=0.7), "
                     f"no de monitoreo directo."))

# Alerta: rendimiento NaN
rend_nan_pct = df['rendimiento_tha'].isna().mean() * 100
if rend_nan_pct > 30:
    alertas.append(("⚠️ ALTA", f"`rendimiento_tha` tiene {rend_nan_pct:.1f}% NaN. "
                     f"Si es variable target secundaria, imputar por mediana de cultivo-semestre."))

report.append("### Resumen de Alertas")
report.append("")
report.append(f"| Severidad | Cantidad |")
report.append(f"|-----------|----------|")
severities = [a[0] for a in alertas]
for sev in ["🚨 CRÍTICA", "⚠️ ALTA", "📋 MEDIA"]:
    n = severities.count(sev)
    report.append(f"| {sev} | {n} |")
report.append("")

report.append("### Detalle de Alertas")
report.append("")
for sev, msg in alertas:
    report.append(f"- **{sev}**: {msg}")
report.append("")

# ── 8. VARIABLES A EXCLUIR ────────────────────────────────────
report.append("---")
report.append("")
report.append("## 8. RECOMENDACIÓN DE VARIABLES A EXCLUIR/CONSERVAR")
report.append("")

excluir = set()
razon_excluir = {}

# 1. Redundantes (r > 0.95)
for v1, v2, r in redundantes:
    # Mantener la más interpretable
    if 'std' in v2 and 'media' in v1:
        excluir.add(v2)
        razon_excluir[v2] = f"Redundante con {v1} (r={r:.3f})"
    elif 'max' in v2 and 'media' in v1:
        excluir.add(v2)
        razon_excluir[v2] = f"Redundante con {v1} (r={r:.3f})"
    else:
        excluir.add(v2)
        razon_excluir[v2] = f"Redundante con {v1} (r={r:.3f})"

# 2. Alta NaN
for col in nan_sorted.index:
    if nan_sorted[col] > 50:
        excluir.add(col)
        razon_excluir[col] = f">{nan_sorted[col]:.0f}% NaN"

# 3. Baja varianza
for col, cv, std, mean in low_var[:3]:
    if abs(cv) < 0.001:
        excluir.add(col)
        razon_excluir[col] = f"Varianza casi cero (CV={cv:.6f})"

conservar = [c for c in feat_num if c not in excluir]

report.append("### Variables a EXCLUIR")
report.append("")
if excluir:
    report.append(f"| Variable | Razón |")
    report.append(f"|----------|-------|")
    for col in sorted(excluir):
        report.append(f"| `{col}` | {razon_excluir.get(col, 'Ver detalle arriba')} |")
else:
    report.append("No se recomienda excluir ninguna variable adicional.")
report.append("")

report.append("### Variables a CONSERVAR (vista minable final)")
report.append("")
report.append(f"**{len(conservar)} features numéricos:**")
report.append("")
for col in conservar:
    report.append(f"- `{col}`")
report.append("")

# ── 9. TRATAMIENTO RECOMENDADO ────────────────────────────────
report.append("---")
report.append("")
report.append("## 9. TRATAMIENTO RECOMENDADO ANTES DE MODELAR")
report.append("")

report.append("### 9.1 Imputación de NaN")
report.append("")
for col in feat_num:
    pct = nan_sorted.get(col, 0)
    if pct > 0:
        if 'sg_' in col:
            report.append(f"- `{col}` ({pct:.1f}% NaN): Imputar ceros → NaN → mediana espacial")
        elif 's2_' in col:
            report.append(f"- `{col}` ({pct:.1f}% NaN): Imputar con mediana por semestre")
        elif col in ['temperatura_media', 'temperatura_max', 'temperatura_min']:
            report.append(f"- `{col}` ({pct:.1f}% NaN): Imputar con regresión vs elevación")
        else:
            report.append(f"- `{col}` ({pct:.1f}% NaN): Imputar con mediana global")
report.append("")

report.append("### 9.2 Transformaciones")
report.append("")
report.append("- **Normalización**: StandardScaler para variables continuas")
report.append("- **Encoding**: One-hot para `fuente` (3 categorías)")
report.append("- **Target encoding**: Label encoding ya aplicado en `cultivo_id`")
report.append(f"- **Balanceo**: SMOTE o class_weight='balanced' (ratio desbalance: {ratio:.0f}:1)")
report.append("")

report.append("### 9.3 Variables SoilGrids (valores ×10)")
report.append("")
report.append("| Variable | Valor actual | Valor real | Transformación |")
report.append("|----------|-------------|------------|----------------|")
report.append("| sg_phh2o | ~52 | pH 5.2 | ÷10 |")
report.append("| sg_soc | ~706 | 70.6 g/kg | ÷10 |")
report.append("| sg_nitrogen | ~435 | 4.35 g/kg | ÷10 |")
report.append("| sg_cec | ~236 | 23.6 cmol/kg | ÷10 |")
report.append("| sg_bdod | ~102 | 1.02 g/cm³ | ÷10 |")
report.append("")

# ── Guardar ───────────────────────────────────────────────────
print("\nGenerando informe...")
text = "\n".join(report)
with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write(text)

print(f"\nInforme guardado: {OUT_MD}")
print(f"Longitud: {len(report)} líneas")