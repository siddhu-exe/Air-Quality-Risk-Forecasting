# Repository Guidelines

Air Quality Risk Forecasting is a Python 3.9+ project: an idempotent PostgreSQL ETL pipeline, causal feature engineering, multi-horizon AQI forecasting (1h/6h/24h), and CPCB/GRAP risk classification.

## Project Structure & Module Organization
- `etl/` — pipeline logic (`discover.py`, `transform_*.py`, `load_postgres.py`, `pipeline.py`); spec in `etl/ETL_SPECIFICATION.md`.
- `src/eda/`, `src/features/`, `src/models/` — analysis, the 124-feature matrix builder, and model/classification code.
- `sql/` — numbered migrations and validation scripts (`001_create_tables.sql` … `006_fix_fk_delete_policy.sql`).
- `notebooks/` — Colab training notebooks; `scripts/` — notebook generators.
- `phase_5/`, `phase_7/`, `docs/` — phase specifications, audits, and findings.
- `reports/`, `models/`, `data/processed/` — generated outputs; `Og Data/` — raw Delhi/Mumbai sources.

## Build, Test, and Development Commands
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt          # install pinned dependencies
python3 etl/run_full_load.py             # full ETL load into PostgreSQL
python3 verify_full_load.py              # post-load row-count validation
bash test_db.sh                          # apply migrations + schema/constraint checks
python3 src/features/build_features.py   # rebuild the feature matrix
python3 test_aqi_ts.py                   # spot-check XLSX timestamp parsing
```
Database settings come from `.env` (`POSTGRES_HOST`, `POSTGRES_PORT=5433`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`). Never hard-code credentials; follow `etl/load_postgres.py`.

## Coding Style & Naming Conventions
- 4-space indentation, `snake_case` for modules, functions, and variables; `UPPER_SNAKE_CASE` for constants.
- Match the existing layout: standard-library imports, then third-party, then local; module-level docstring or header comment explaining purpose.
- Prefer explicit dataframe/column names and typed dicts (e.g. `CAAQMS_COL_MAP`) over positional indexing.
- No linter or formatter is configured; keep diffs minimal and consistent with nearby files.

## Testing Guidelines
There is no pytest suite or coverage gate; checks are ad-hoc scripts run against the live database or sample files. Name new checks `test_*.py` and assert on concrete values (row counts, timestamps, constraint violations) rather than printing alone. Always run `bash test_db.sh` after changing `sql/`.

## Commit & Pull Request Guidelines
History follows Conventional Commits, often phase-scoped: `feat(phase7): implement risk classification`, `docs(audit): complete Phase 7 audit`. Use `feat`, `docs`, `fix`, or `refactor` with an optional scope, and a short imperative subject. PRs should state the phase/scope, summarize behavior changes, list new artifacts or migrations, and confirm the validation commands run. Link related issues and include report paths or screenshots for generated figures.

## Agent-Specific Instructions
Treat raw data as immutable: write outputs to `reports/`, `data/processed/`, or `models/`. Beware the `Jahangirpuri` directory's trailing tab character when globbing. `local_pg_data/`, `venv/`, and `.env` are gitignored — do not commit them or embed secrets in code.
