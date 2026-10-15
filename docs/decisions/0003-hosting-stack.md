# 0003. Hosting stack

**Status:** accepted.

**Context.** Hourly jobs, a small read-only API and a dashboard, on free or near-free tiers, with no always-on model server.

**Decision.**
- **Supabase Postgres** (pooler, schema `aq`) is the single store. Two roles: a writer for jobs (`DATABASE_URL`) and a read-only role for the API (`DATABASE_URL_READONLY`).
- **GitHub Actions** cron jobs run ingestion and forecasting; model inference (joblib) happens inside the job.
- **FastAPI on Azure Container Apps**, scale to zero, image from GHCR, deployed with OIDC (no stored cloud credentials).
- **React frontend on Vercel**.
- Heavy training happens only in Colab.

**Consequences.** The API never loads a model and never writes. Cold starts are accepted. Secrets live only in GitHub secrets, Azure and `.env` (git-ignored).
