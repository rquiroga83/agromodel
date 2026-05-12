import json

NB = 'd:/trabajo/agroplus/modelado/CRISP_DM_AgroPlus_L1_UPRA.ipynb'
with open(NB, 'r', encoding='utf-8') as f:
    nb = json.load(f)

def find_cell(nb, cid):
    for i, c in enumerate(nb['cells']):
        if c.get('id') == cid:
            return i
    return None

# ==============================================================
# FIX 1: Split espacial por municipio
# ==============================================================
SPLIT_SRC = (
    "# =====================================================================\n"
    "# SPLIT ESPACIAL POR MUNICIPIO (reemplaza split temporal)\n"
    "#\n"
    "# CAUSA RAIZ DEL OVERFITTING RESIDUAL:\n"
    "#   Split temporal (train<=2022, valid=2023) permite que el MISMO PIXEL\n"
    "#   aparezca en train y en valid con features estaticos IDENTICOS.\n"
    "#   Los 27 features restantes (suelo + topografia + IGAC + clima) forman\n"
    "#   un fingerprint unico por pixel. El modelo memoriza los Papa pixels\n"
    "#   en 2-3 arboles y los reconoce perfectamente en valid.\n"
    "#\n"
    "# SOLUCION: GroupShuffleSplit por cod_mun -> cero solapamiento de pixeles.\n"
    "# =====================================================================\n"
    "\n"
    "X = df_l1[feature_cols].copy()\n"
    "y = df_l1[TARGET_COL].astype(np.int8).values\n"
    "sample_w = df_l1['sample_weight'].values\n"
    "groups   = df_l1['cod_mun'].values\n"
    "\n"
    "# --- Diagnostico de solapamiento con split temporal (ANTES del fix) ---\n"
    "if '_year' in df_l1.columns and 'x' in df_l1.columns and 'y' in df_l1.columns:\n"
    "    year_arr = df_l1['_year'].values\n"
    "    m_tr_t = year_arr <= 2022\n"
    "    m_va_t = year_arr == 2023\n"
    "    coords_tr = set(zip(df_l1.loc[m_tr_t, 'x'].values, df_l1.loc[m_tr_t, 'y'].values))\n"
    "    coords_va = set(zip(df_l1.loc[m_va_t, 'x'].values, df_l1.loc[m_va_t, 'y'].values))\n"
    "    overlap = len(coords_tr & coords_va)\n"
    "    pct = overlap / max(len(coords_va), 1) * 100\n"
    "    print(f'[Diagnostico] Split temporal: {overlap:,} pixeles solapados '\n"
    "          f'entre train y valid ({pct:.1f}% de valid)')\n"
    "    print(f'  -> El modelo memoriza estos pixeles. PR-AUC=1.0 trivial.')\n"
    "\n"
    "# --- Split espacial ---\n"
    "from sklearn.model_selection import GroupShuffleSplit\n"
    "\n"
    "# Paso 1: separar test (15% de municipios)\n"
    "gss_test = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)\n"
    "idx_trv, idx_te = next(gss_test.split(X, y, groups=groups))\n"
    "\n"
    "# Paso 2: separar valid (~15% del total = 17.6% de train+valid)\n"
    "gss_valid = GroupShuffleSplit(n_splits=1, test_size=0.176, random_state=42)\n"
    "idx_tr, idx_va = next(gss_valid.split(\n"
    "    X.iloc[idx_trv], y[idx_trv], groups=groups[idx_trv]))\n"
    "idx_tr_abs = idx_trv[idx_tr]\n"
    "idx_va_abs = idx_trv[idx_va]\n"
    "\n"
    "m_tr = np.zeros(len(y), dtype=bool); m_tr[idx_tr_abs] = True\n"
    "m_va = np.zeros(len(y), dtype=bool); m_va[idx_va_abs] = True\n"
    "m_te = np.zeros(len(y), dtype=bool); m_te[idx_te]      = True\n"
    "\n"
    "# Verificar ambas clases en todos los folds\n"
    "_ok = True\n"
    "for fold_mask, fold_name in [(m_tr,'train'), (m_va,'valid'), (m_te,'test')]:\n"
    "    if len(np.unique(y[fold_mask])) < 2:\n"
    "        print(f'  ADVERTENCIA: {fold_name} tiene solo una clase')\n"
    "        _ok = False\n"
    "if _ok:\n"
    "    print('Ambas clases presentes en todos los folds: OK')\n"
    "\n"
    "X_train, y_train, sw_train, g_train = (\n"
    "    X.loc[m_tr].reset_index(drop=True), y[m_tr], sample_w[m_tr], groups[m_tr])\n"
    "X_valid, y_valid, sw_valid, g_valid = (\n"
    "    X.loc[m_va].reset_index(drop=True), y[m_va], sample_w[m_va], groups[m_va])\n"
    "X_test, y_test, sw_test, g_test = (\n"
    "    X.loc[m_te].reset_index(drop=True), y[m_te], sample_w[m_te], groups[m_te])\n"
    "\n"
    "muns_tr, muns_va, muns_te = set(g_train), set(g_valid), set(g_test)\n"
    "fuga_tv = muns_tr & muns_va; fuga_tt = muns_tr & muns_te; fuga_vt = muns_va & muns_te\n"
    "print(f'Split: espacial por municipio')\n"
    "print(f'Train: {len(X_train):>8,} filas | {len(muns_tr):>3} muns | '\n"
    "      f'Papa={y_train.sum():,} ({y_train.mean()*100:.2f}%)')\n"
    "print(f'Valid: {len(X_valid):>8,} filas | {len(muns_va):>3} muns | '\n"
    "      f'Papa={y_valid.sum():,} ({y_valid.mean()*100:.2f}%)')\n"
    "print(f'Test : {len(X_test):>8,} filas | {len(muns_te):>3} muns | '\n"
    "      f'Papa={y_test.sum():,} ({y_test.mean()*100:.2f}%)')\n"
    "if fuga_tv or fuga_tt or fuga_vt:\n"
    "    print(f'  ERROR: municipios compartidos: {fuga_tv|fuga_tt|fuga_vt}')\n"
    "else:\n"
    "    print('  Sin solapamiento de municipios: OK')\n"
    "\n"
    "masa_pos_tr = sw_train[y_train == 1].sum()\n"
    "masa_neg_tr = sw_train[y_train == 0].sum()\n"
    "SCALE_POS_WEIGHT = float(masa_neg_tr / max(masa_pos_tr, 1))\n"
    "print(f'scale_pos_weight = {SCALE_POS_WEIGHT:.3f}')\n"
)

idx = find_cell(nb, 'e18f0fab')
nb['cells'][idx]['source'] = SPLIT_SRC
nb['cells'][idx]['outputs'] = []
nb['cells'][idx]['execution_count'] = None
print(f'Split cell reemplazado en index {idx}')

# ==============================================================
# FIX 2: Base model — solo valid en eval_set + diagnostico gap
# ==============================================================
BASE_SRC = (
    "# FIX: eval_set contiene SOLO valid (quitar train de eval_set).\n"
    "# Con train en eval_set, XGBoost monitorea valid (ultimo set) correctamente,\n"
    "# pero el diagnostico se confunde. Sin train, el output es mas limpio.\n"
    "\n"
    "xgb_base = XGBClassifier(\n"
    "    n_estimators=3000,\n"
    "    max_depth=3,\n"
    "    learning_rate=0.01,\n"
    "    subsample=0.6,\n"
    "    colsample_bytree=0.5,\n"
    "    min_child_weight=10,\n"
    "    gamma=0.5,\n"
    "    reg_alpha=1.0,\n"
    "    reg_lambda=5.0,\n"
    "    objective='binary:logistic',\n"
    "    eval_metric='aucpr',\n"
    "    scale_pos_weight=SCALE_POS_WEIGHT,\n"
    "    early_stopping_rounds=100,\n"
    "    random_state=42,\n"
    "    n_jobs=XGB_N_JOBS,\n"
    "    tree_method=XGB_TREE_METHOD,\n"
    "    device=XGB_DEVICE,\n"
    ")\n"
    "\n"
    "t0 = time.time()\n"
    "xgb_base.fit(\n"
    "    X_train_pp, y_train,\n"
    "    sample_weight=sw_train,\n"
    "    eval_set=[(X_valid_pp, y_valid)],     # Solo valid\n"
    "    sample_weight_eval_set=[sw_valid],\n"
    "    verbose=100,\n"
    ")\n"
    "print(f'Entrenamiento base: {time.time()-t0:.1f}s')\n"
    "print(f'Mejor iteracion: {xgb_base.best_iteration}  |  '\n"
    "      f'PR-AUC valid: {xgb_base.best_score:.4f}')\n"
    "\n"
    "# Diagnostico gap train vs valid\n"
    "proba_tr_base = xgb_base.predict_proba(X_train_pp)[:, 1]\n"
    "proba_va_base = xgb_base.predict_proba(X_valid_pp)[:, 1]\n"
    "pr_tr = average_precision_score(y_train, proba_tr_base, sample_weight=sw_train)\n"
    "pr_va = average_precision_score(y_valid, proba_va_base, sample_weight=sw_valid)\n"
    "print(f'Train PR-AUC: {pr_tr:.4f}  |  Valid PR-AUC: {pr_va:.4f}  '\n"
    "      f'|  Gap: {pr_tr - pr_va:+.4f}')\n"
    "if pr_va > 0.98:\n"
    "    print('ADVERTENCIA: PR-AUC=1.0. Revisar solapamiento de pixeles en split.')\n"
)

idx = find_cell(nb, '8c29646f')
nb['cells'][idx]['source'] = BASE_SRC
nb['cells'][idx]['outputs'] = []
nb['cells'][idx]['execution_count'] = None
print(f'Base model cell reemplazado en index {idx}')

# ==============================================================
# FIX 3: Optuna — guardar best_iteration como user_attr
# ==============================================================
OPTUNA_SRC = (
    "optuna.logging.set_verbosity(optuna.logging.WARNING)\n"
    "\n"
    "OPTUNA_TRIALS = 30\n"
    "OPTUNA_DB     = 'sqlite:///d:/trabajo/agroplus/modelado/optuna_l1_upra.db'\n"
    "OPTUNA_STUDY  = 'l1_upra_xgb_v3'\n"
    "\n"
    "def objective(trial):\n"
    "    params = {\n"
    "        'n_estimators':     trial.suggest_int('n_estimators', 300, 2000),\n"
    "        'max_depth':        trial.suggest_int('max_depth', 2, 6),\n"
    "        'learning_rate':    trial.suggest_float('learning_rate', 0.005, 0.05, log=True),\n"
    "        'subsample':        trial.suggest_float('subsample', 0.4, 0.8),\n"
    "        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.3, 0.7),\n"
    "        'min_child_weight': trial.suggest_int('min_child_weight', 3, 30),\n"
    "        'gamma':            trial.suggest_float('gamma', 0.1, 5.0),\n"
    "        'reg_alpha':        trial.suggest_float('reg_alpha', 0.05, 5.0, log=True),\n"
    "        'reg_lambda':       trial.suggest_float('reg_lambda', 0.1, 10.0, log=True),\n"
    "    }\n"
    "    model = XGBClassifier(\n"
    "        **params,\n"
    "        objective='binary:logistic',\n"
    "        eval_metric='aucpr',\n"
    "        scale_pos_weight=SCALE_POS_WEIGHT,\n"
    "        early_stopping_rounds=40,\n"
    "        random_state=42,\n"
    "        n_jobs=XGB_N_JOBS,\n"
    "        tree_method=XGB_TREE_METHOD,\n"
    "        device=XGB_DEVICE,\n"
    "        verbosity=0,\n"
    "    )\n"
    "    model.fit(X_train_pp, y_train,\n"
    "              sample_weight=sw_train,\n"
    "              eval_set=[(X_valid_pp, y_valid)],\n"
    "              sample_weight_eval_set=[sw_valid],\n"
    "              verbose=False)\n"
    "\n"
    "    # FIX: guardar best_iteration real para el modelo final.\n"
    "    # study.best_params['n_estimators'] es el valor SUGERIDO, no el real.\n"
    "    trial.set_user_attr('best_iteration', int(model.best_iteration))\n"
    "\n"
    "    proba_va = model.predict_proba(X_valid_pp)[:, 1]\n"
    "    return average_precision_score(y_valid, proba_va, sample_weight=sw_valid)\n"
    "\n"
    "\n"
    "sampler = optuna.samplers.TPESampler(seed=42, multivariate=True, n_startup_trials=10)\n"
    "pruner  = optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=0)\n"
    "\n"
    "study = optuna.create_study(\n"
    "    study_name=OPTUNA_STUDY,\n"
    "    storage=OPTUNA_DB,\n"
    "    direction='maximize',\n"
    "    sampler=sampler,\n"
    "    pruner=pruner,\n"
    "    load_if_exists=True,\n"
    ")\n"
    "\n"
    "n_prev = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])\n"
    "print(f'Estudio \"{OPTUNA_STUDY}\" - trials previos: {n_prev}')\n"
    "print(f'Lanzando {OPTUNA_TRIALS} trials | objetivo: maximizar PR-AUC valid')\n"
    "\n"
    "t0 = time.time()\n"
    "study.optimize(objective, n_trials=OPTUNA_TRIALS, show_progress_bar=True)\n"
    "print(f'Optuna: {(time.time()-t0)/60:.1f} min')\n"
    "\n"
    "best = study.best_trial\n"
    "best_iter_real = best.user_attrs.get('best_iteration', best.params.get('n_estimators'))\n"
    "print(f'Mejor PR-AUC valid : {best.value:.4f}  (trial #{best.number})')\n"
    "print(f'n_estimators final : {best_iter_real + 1}  '\n"
    "      f'(n_estimators sugerido={best.params[\"n_estimators\"]})')\n"
    "if best.value > 0.98:\n"
    "    print('ADVERTENCIA: PR-AUC alto. Revisar solapamiento de pixeles.')\n"
    "print('Mejores hiperparametros:')\n"
    "for k, v in best.params.items():\n"
    "    print(f'  {k:<18} = {v}')\n"
)

idx = find_cell(nb, 'f4122161')
nb['cells'][idx]['source'] = OPTUNA_SRC
nb['cells'][idx]['outputs'] = []
nb['cells'][idx]['execution_count'] = None
print(f'Optuna cell reemplazado en index {idx}')

# ==============================================================
# FIX 4: Modelo final — best_iteration real, sin test en eval_set
# ==============================================================
FINAL_SRC = (
    "# FIX A: n_estimators = best_iteration + 1 (no el valor sugerido por Optuna).\n"
    "#   study.best_params['n_estimators'] es el valor sugerido por TPE (ej. 1500).\n"
    "#   El modelo real uso early stopping y se detuvo en best_iteration (ej. 180).\n"
    "#   Sin FIX A, el modelo final entrena 1500 arboles en vez de 181 -> sobreajuste.\n"
    "# FIX B: eval_set no incluye test -> no hay contaminacion del hold-out.\n"
    "# FIX C: sin early_stopping_rounds -> n_estimators ya es el valor calibrado.\n"
    "\n"
    "best_iter_real = study.best_trial.user_attrs.get(\n"
    "    'best_iteration', study.best_params.get('n_estimators'))\n"
    "\n"
    "final_params = study.best_params.copy()\n"
    "final_params['n_estimators'] = best_iter_real + 1   # FIX A\n"
    "final_params.update({\n"
    "    'objective':        'binary:logistic',\n"
    "    'eval_metric':      'aucpr',\n"
    "    'scale_pos_weight': SCALE_POS_WEIGHT,\n"
    "    'random_state':     42,\n"
    "    'n_jobs':           XGB_N_JOBS,\n"
    "    'tree_method':      XGB_TREE_METHOD,\n"
    "    'device':           XGB_DEVICE,\n"
    "})\n"
    "assert 'early_stopping_rounds' not in final_params, 'Remover early_stopping de final_params'\n"
    "\n"
    "X_fit  = np.vstack([X_train_pp, X_valid_pp])\n"
    "y_fit  = np.concatenate([y_train, y_valid])\n"
    "sw_fit = np.concatenate([sw_train, sw_valid])\n"
    "\n"
    "final_model = XGBClassifier(**final_params)\n"
    "final_model.fit(\n"
    "    X_fit, y_fit,\n"
    "    sample_weight=sw_fit,\n"
    "    eval_set=[(X_fit, y_fit)],             # FIX B: solo train+valid, sin test\n"
    "    sample_weight_eval_set=[sw_fit],\n"
    "    verbose=False,\n"
    ")\n"
    "\n"
    "proba_test       = final_model.predict_proba(X_test_pp)[:, 1]\n"
    "proba_train_full = final_model.predict_proba(X_fit)[:, 1]\n"
    "\n"
    "pr_fit  = average_precision_score(y_fit,  proba_train_full, sample_weight=sw_fit)\n"
    "pr_test = average_precision_score(y_test, proba_test,       sample_weight=sw_test)\n"
    "print(f'Modelo final: {best_iter_real + 1} arboles  '\n"
    "      f'(n_estimators sugerido era: {study.best_params[\"n_estimators\"]})')\n"
    "print(f'Train+Valid PR-AUC : {pr_fit:.4f}')\n"
    "print(f'Test PR-AUC        : {pr_test:.4f}  gap={pr_fit - pr_test:+.4f}')\n"
    "print(f'Test ROC-AUC       : {roc_auc_score(y_test, proba_test, sample_weight=sw_test):.4f}')\n"
)

idx = find_cell(nb, '68a212d3')
nb['cells'][idx]['source'] = FINAL_SRC
nb['cells'][idx]['outputs'] = []
nb['cells'][idx]['execution_count'] = None
print(f'Final model cell reemplazado en index {idx}')

with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print('\nSaved OK')
