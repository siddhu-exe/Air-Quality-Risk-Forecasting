"""Generate notebooks/d1_feature_audit_colab.ipynb and the small upload bundle for it.

The audit scores the FROZEN 1h/6h LightGBM models and the 24h hybrid on the validation window with some live
inputs missing or substituted (docs/TIER_3/PLAN.md, decision D1). LightGBM is not installed on the dev laptop,
so the 1h/6h part runs on Colab. Nothing is trained.

    python scripts/generate_d1_audit_notebook.py
Writes notebooks/d1_feature_audit_colab.ipynb and tier3_d1_audit_bundle.zip (repo root).
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "d1_feature_audit_colab.ipynb"
BUNDLE = ROOT / "tier3_d1_audit_bundle.zip"

FROZEN = [
    "models/lgb_model_1h_v1.joblib", "models/lgb_model_6h_v1.joblib",
    "models/24h/final/24h_final_model.joblib", "models/24h/final/scaler_final_24h.joblib",
    "models/24h/final/imputer_final_24h.joblib", "models/24h/final/feature_names_final.joblib",
]
DATA = ["data/processed/features_extended.parquet", "data/processed/exogenous_weather.parquet"]
SOURCE_DIRS = ["src", "etl"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_files() -> list[Path]:
    files = [ROOT / f for f in FROZEN + DATA]
    files += [p for d in SOURCE_DIRS for p in (ROOT / d).rglob("*.py")]
    files += sorted((ROOT / "Og Data" / "Delhi data").glob("*/Raw Data/2025_*_1H.csv"))
    return [p for p in files if "__pycache__" not in p.parts]


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}


def build_notebook() -> dict:
    expected = {f: sha256(ROOT / f) for f in FROZEN}
    cells = [
        md("""
# D1 feature-availability audit (validation window only)

Scores the **frozen** models (1h/6h LightGBM, 24h hybrid) on Sep 1 - Oct 31 2025 with live-source gaps applied:
no solar radiation and no ITO weather (OpenAQ primary), or no NOx and no station weather (data.gov.in primary),
each with the gaps filled from Open-Meteo/ERA5 or left empty. Nothing is trained. The test window is never read.

**Before running:** upload `tier3_d1_audit_bundle.zip` to your Drive folder (or to `/content`), then run all cells.
The notebook stops if any frozen model's hash differs from the one recorded when this notebook was generated.
"""),
        code("""
import os, sys, hashlib, subprocess, zipfile, pathlib, platform
try:
    from google.colab import drive
    drive.mount('/content/drive')
    PROJECT_DIR = pathlib.Path('/content/drive/MyDrive/aq_tier3_audit')
except ImportError:                      # running locally
    PROJECT_DIR = pathlib.Path('.').resolve()
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
BUNDLE = next((p for p in [PROJECT_DIR / 'tier3_d1_audit_bundle.zip', pathlib.Path('/content/tier3_d1_audit_bundle.zip')] if p.exists()), None)
if BUNDLE is not None:
    zipfile.ZipFile(BUNDLE).extractall(PROJECT_DIR)
    print('extracted', BUNDLE)
os.chdir(PROJECT_DIR); sys.path.insert(0, str(PROJECT_DIR))
print('project dir:', PROJECT_DIR)
"""),
        code(f"""
EXPECTED_SHA256 = {json.dumps(expected, indent=4)}
def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
bad = [f for f, h in EXPECTED_SHA256.items() if not pathlib.Path(f).exists() or sha(f) != h]
assert not bad, f'frozen model files missing or different from the recorded hashes: {{bad}}'
missing = [f for f in {json.dumps(DATA)} if not pathlib.Path(f).exists()]
assert not missing, f'missing data files: {{missing}}'
assert list(pathlib.Path('Og Data/Delhi data').glob('*/Raw Data/2025_*_1H.csv')), 'raw 2025 CSVs missing'
print('frozen models verified against recorded hashes; inputs present')
"""),
        code("""
# lightgbm is needed for the 1h/6h models; psycopg2 is imported (not used) by the shared feature module
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'lightgbm', 'psycopg2-binary', 'pyarrow', 'python-dotenv', 'requests'], capture_output=True, text=True)
print(r.stdout[-500:], r.stderr[-500:])
import sklearn, lightgbm, pandas, numpy
print('python', platform.python_version(), '| sklearn', sklearn.__version__, '| lightgbm', lightgbm.__version__, '| pandas', pandas.__version__, '| numpy', numpy.__version__)
print('NOTE: the frozen models were pickled with other library versions; load warnings below are expected, a crash is not.')
"""),
        code("""
r = subprocess.run([sys.executable, '-W', 'ignore', '-m', 'src.evaluation.feature_availability_audit', '--horizons', '24', '1', '6'], capture_output=True, text=True)
print(r.stdout[-6000:]); print(r.stderr[-3000:])
assert r.returncode == 0, 'the audit failed; do not use partial output'
"""),
        code("""
import pandas as pd
from IPython.display import Markdown, display
out = pathlib.Path('reports/modeling/live_audit')
display(Markdown((out / 'feature_availability_audit.md').read_text()))
table = pd.read_csv(out / 'feature_availability_audit.csv')
assert set(table.horizon) == {'1h', '6h', '24h'}, f'horizons present: {sorted(set(table.horizon))}'
table[['horizon', 'scenario', 'n', 'mae', 'mae_persistence', 'skill_mae', 'delta_mae_vs_baseline', 'delta_mae_ci_lo', 'delta_mae_ci_hi']].round(3)
"""),
        code("""
import shutil
shutil.make_archive('/content/d1_audit_results' if os.path.exists('/content') else 'd1_audit_results', 'zip', 'reports/modeling/live_audit')
try:
    from google.colab import files; files.download('/content/d1_audit_results.zip')
except ImportError:
    print('results zip written locally')
"""),
    ]
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main() -> None:
    NOTEBOOK.parent.mkdir(exist_ok=True)
    NOTEBOOK.write_text(json.dumps(build_notebook(), indent=1, ensure_ascii=False))
    files = bundle_files()
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())
    print(f"wrote {NOTEBOOK.relative_to(ROOT)} and {BUNDLE.name} ({BUNDLE.stat().st_size / 1e6:.1f} MB, {len(files)} files)")


if __name__ == "__main__":
    main()
