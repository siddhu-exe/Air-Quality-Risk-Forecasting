# 0004. Tier 3 scope decisions (D1 to D6)

**Status:** accepted.

| ID | Decision |
| :--- | :--- |
| D1 | Originally "serve the frozen models unchanged". Superseded by [0001](0001-frozen-vs-live-consistent-models.md) after the audit showed the AQI basis mismatch. |
| D2 | Re-fit PM2.5, quantile and P(severe) models in the same Colab notebook, export only. |
| D3 | Backfill the history the feature window needs before the first forecast. Done. |
| D4 | The repository is public; nothing sensitive is committed. |
| D5 | The Diwali and threshold-sweep screens are dropped from the live app; the analyses stay in `reports/`. |
| D6 | Rewrite `frontend/CLAUDE.md` once the API contract is final (Stage 6). |

Weather for model inputs is never filled from Open-Meteo (`weather_fill = "none"`); Open-Meteo is stored only for display.
