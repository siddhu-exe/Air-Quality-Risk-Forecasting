# Delhi air quality forecast API. Build from the repository root:
#   docker build -f backend/Dockerfile -t delhi-air-api .
# The image holds the API code, its pinned dependencies and three report CSVs (the /backtest evidence). It contains no model
# files and no credentials: DATABASE_URL_READONLY and FRONTEND_ORIGIN are injected as Container App environment variables.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/app backend/app
COPY reports/modeling/live_retrain/window_update_baseline.csv reports/modeling/live_retrain/
COPY reports/modeling/live_pm25/pm25_forecast_metrics.csv reports/modeling/live_pm25/
COPY reports/live/ reports/live/

RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
