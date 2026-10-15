"""Generate notebooks/live_retrain_colab.ipynb and its upload bundle (tier3_live_retrain_bundle.zip, repo root).

The notebook re-fits the AQI models on the live-consistent matrix (recomputed AQI as input and target), runs the PM2.5 1h/6h
audit/export on live-masked inputs and the 24h quantile / P(severe) export (decision D2), verifies everything it wrote, and zips the
results. Heavy training stays on Colab. The frozen models in ``models/`` are inputs only; the notebook refuses to start if their
hashes differ, and every file in the bundle is re-hashed after extraction.

    python scripts/generate_live_retrain_notebook.py
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "live_retrain_colab.ipynb"
BUNDLE = ROOT / "tier3_live_retrain_bundle.zip"

FROZEN = [
    "models/lgb_model_1h_v1.joblib", "models/lgb_model_6h_v1.joblib",
    "models/24h/final/24h_final_model.joblib", "models/24h/final/scaler_final_24h.joblib",
    "models/24h/final/imputer_final_24h.joblib", "models/24h/final/feature_names_final.joblib",
]
EXTRA = ["config/model_hashes.json", "requirements-forecast.txt", "requirements-live.txt",
         "reports/modeling/pm25/pm25_forecast_metrics.csv", "reports/modeling/probabilistic/probabilistic_metrics.json"]
SOURCE_DIRS = ["src", "etl"]
RAW_GLOBS = ["Og Data/Delhi data/*/Raw Data/2024_*_1H.csv", "Og Data/Delhi data/*/Raw Data/2025_*_1H.csv"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_files() -> list[Path]:
    files = [ROOT / f for f in FROZEN + EXTRA if (ROOT / f).exists()]
    files += [p for d in SOURCE_DIRS for p in (ROOT / d).rglob("*.py")]
    for pattern in RAW_GLOBS:
        files += sorted(ROOT.glob(pattern))
    return sorted({p for p in files if "__pycache__" not in p.parts})


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}


def build_notebook(manifest: dict[str, str]) -> dict:
    cells = [
        md("""
# Live-consistent retrain (Tier 3)

Re-fits the AQI models so training and serving use the **same AQI definition** (the one the live ingest computes), then runs the
PM2.5 1h/6h audit/export and the 24h quantile / P(severe) export (decision D2).

| Section | What it does | Scored |
| :--- | :--- | :--- |
| A | 1h/6h LightGBM + 24h hybrid, recomputed AQI as features and target, frozen hyper-parameters and features | validation selects the iteration count only; **test is scored once** |
| B | PM2.5 1h/6h (and 24h) on live-masked inputs (no NOx/NO/solar, no ITO weather), Tier 2 variant selection on validation | test scored once, next to persistence |
| C | 24h quantile models + conformal pad + P(AQI >= 401) classifier, export only | as in Tier 2 |

**Before running:** upload `tier3_live_retrain_bundle.zip` to your Drive folder `aq_tier3_live` (or to `/content`), keep `SMOKE = False`,
then *Run all*. The notebook stops on any hash mismatch, any failed step, and on a second test scoring. It never edits the frozen files.
"""),
        code("""
SMOKE = False          # True = code-path check only (30 boosting rounds, 2 months of training, smoke profile); results must not be used
RUN_AQI, RUN_PM25, RUN_QUANTILE = True, True, True
"""),
        code("""
import os, sys, hashlib, subprocess, zipfile, pathlib, platform, json
try:
    from google.colab import drive
    drive.mount('/content/drive')
    PROJECT_DIR = pathlib.Path('/content/drive/MyDrive/aq_tier3_live')
except ImportError:                      # running locally
    PROJECT_DIR = pathlib.Path('.').resolve()
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
BUNDLE = next((p for p in [PROJECT_DIR / 'tier3_live_retrain_bundle.zip', pathlib.Path('/content/tier3_live_retrain_bundle.zip')] if p.exists()), None)
assert BUNDLE is not None, 'tier3_live_retrain_bundle.zip not found in the Drive folder or /content'
zipfile.ZipFile(BUNDLE).extractall(PROJECT_DIR)
os.chdir(PROJECT_DIR); sys.path.insert(0, str(PROJECT_DIR))
print('project dir:', PROJECT_DIR, '| bundle:', BUNDLE)
"""),
        code(f"""
BUNDLE_SHA256 = {json.dumps(manifest, indent=1)}
def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
bad = [f for f, h in BUNDLE_SHA256.items() if not pathlib.Path(f).exists() or sha(f) != h]
assert not bad, f'{{len(bad)}} bundle file(s) missing or changed since the notebook was generated, e.g. {{bad[:5]}}'
recorded = json.loads(pathlib.Path('config/model_hashes.json').read_text())
frozen_bad = [f for f, h in recorded.items() if sha(f) != h]
assert not frozen_bad, f'frozen model files differ from config/model_hashes.json: {{frozen_bad}}'
print(f'{{len(BUNDLE_SHA256)}} bundle files and {{len(recorded)}} frozen model files verified against recorded hashes')
"""),
        code("""
# pinned to the versions the forecast job installs (requirements-forecast.txt): exported pickles must load there
PINS = ['scikit-learn==1.9.0', 'lightgbm==4.7.0', 'joblib==1.6.0', 'pyarrow', 'psycopg2-binary', 'python-dotenv', 'requests', 'matplotlib']
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *PINS], capture_output=True, text=True)
print(r.stdout[-400:], r.stderr[-800:])
import sklearn, lightgbm, pandas, numpy, joblib
print('python', platform.python_version(), '| sklearn', sklearn.__version__, '| lightgbm', lightgbm.__version__, '| pandas', pandas.__version__, '| numpy', numpy.__version__)
assert sklearn.__version__ == '1.9.0' and lightgbm.__version__ == '4.7.0', 'library versions differ from requirements-forecast.txt; do not export models'
print('NOTE: the frozen models were pickled with other versions; unpickle warnings are expected, a crash is not.')
"""),
        code("""
def run(args, extra_env=None):
    env = {**os.environ, 'PYTHONPATH': str(PROJECT_DIR), 'PYTHONWARNINGS': 'ignore'}
    env.update(extra_env or {})
    r = subprocess.run([sys.executable, '-W', 'ignore', *args], capture_output=True, text=True, env=env)
    print(r.stdout[-7000:]); print(r.stderr[-3000:])
    assert r.returncode == 0, f'step failed ({" ".join(args)}); do not use partial output'

START = ['--start', '2025-07-01'] if SMOKE else []
run(['-m', 'src.features.build_live_matrix', *START])
import pandas as pd
for name in ('features_live', 'features_live_masked'):
    frame = pd.read_parquet(f'data/processed/{name}.parquet')
    assert set(frame.aqi_source.dropna().unique()) == {'recomputed'}, 'matrix must carry recomputed AQI only'
    print(name, frame.shape, frame.timestamp.min(), '..', frame.timestamp.max())
"""),
        code("""
# SECTION A: AQI models (test window scored once; a second run is refused unless LIVE_RETRAIN_ALLOW_RESCORE=1)
if RUN_AQI:
    run(['-m', 'src.models.live_retrain'], {'LIVE_RETRAIN_SMOKE': '1' if SMOKE else '0'})
"""),
        code("""
# SECTION B: PM2.5 on live-masked inputs (Tier 2 variant selection on validation, standard profile, exported)
profile = 'smoke' if SMOKE else 'standard'
if RUN_PM25:
    run(['-m', 'src.models.train_pm25_forecast'], {'T2_PROFILE': profile, 'LIVE_MATRIX_PATH': 'data/processed/features_live_masked.parquet',
                                                   'LIVE_OUT_DIR': 'reports/modeling/live_pm25', **({} if SMOKE else {'LIVE_EXPORT_DIR': 'models/live/pm25'})})
# SECTION C: 24h quantile + P(severe)
if RUN_QUANTILE:
    run(['-m', 'src.models.train_quantile_forecast'], {'T2_PROFILE': profile, 'LIVE_MATRIX_PATH': 'data/processed/features_live_masked.parquet',
                                                      'LIVE_OUT_DIR': 'reports/modeling/live_quantile',
                                                      'LIVE_EXPORT_DIR': 'models/live_smoke/quantile' if SMOKE else 'models/live/quantile'})
"""),
        code("""
if not SMOKE and RUN_AQI and RUN_PM25 and RUN_QUANTILE:
    run(['-m', 'src.models.live_verify_export'])          # re-hashes, reloads and predicts with every exported model; non-zero on any problem
else:
    print('verification skipped (SMOKE or a section was switched off)')
"""),
        code("""
from IPython.display import Markdown, display
for path in ['reports/modeling/live_retrain/live_retrain_metrics.md', 'reports/modeling/live_pm25/pm25_forecast_metrics.md', 'reports/modeling/live_quantile/quantile_metrics.md']:
    if pathlib.Path(path).exists():
        display(Markdown(pathlib.Path(path).read_text()))
ref = pathlib.Path('reports/modeling/pm25/pm25_forecast_metrics.csv')
if ref.exists():
    print('Tier 2 reference (official-AQI matrix, all inputs) for the PM2.5 table above:')
    display(pd.read_csv(ref)[['horizon', 'split', 'model_mae', 'persistence_mae', 'skill_mae', 'skill_mae_ci_lo', 'skill_mae_ci_hi']])
"""),
        code("""
assert not SMOKE, 'SMOKE results are never zipped'
import shutil
stage = pathlib.Path('/content/tier3_live_retrain_results') if os.path.exists('/content') else pathlib.Path('tier3_live_retrain_results')
shutil.rmtree(stage, ignore_errors=True); stage.mkdir(parents=True)
for src in ['models/live', 'reports/modeling/live_retrain', 'reports/modeling/live_pm25', 'reports/modeling/live_quantile']:
    if pathlib.Path(src).exists():
        shutil.copytree(src, stage / src)
shutil.make_archive(str(stage), 'zip', stage)
try:
    from google.colab import files; files.download(str(stage) + '.zip')
except ImportError:
    print('results zip written locally:', str(stage) + '.zip')
"""),
    ]
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main() -> None:
    files = bundle_files()
    manifest = {p.relative_to(ROOT).as_posix(): sha256(p) for p in files}
    NOTEBOOK.parent.mkdir(exist_ok=True)
    NOTEBOOK.write_text(json.dumps(build_notebook(manifest), indent=1, ensure_ascii=False))
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())
    print(f"wrote {NOTEBOOK.relative_to(ROOT)} and {BUNDLE.name} ({BUNDLE.stat().st_size / 1e6:.1f} MB, {len(files)} files)")


if __name__ == "__main__":
    main()
