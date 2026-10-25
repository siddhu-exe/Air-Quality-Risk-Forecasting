# 0010. Google Air Quality in shadow mode, judged by a pre-registered gate

**Status:** accepted 2026-10-25. The rules below were committed before any Google value was compared with OpenAQ.

**Context.** OpenAQ, the only primary source, has been behind real time for the whole of October 2026 and stopped at 2026-10-23 21:00 IST (`docs/postmortems/2026-10-ingest-stall.md`). WAQI is the other candidate and is PM-only at best (ADR 0009). Google Air Quality returns pollutant concentrations and the local Indian index for any coordinate, on a schedule that does not depend on CPCB's feed reaching OpenAQ. ADR 0009 rejected it on 2026-10-17 because its values are modelled on a grid, not measured by a monitor; the owner reopened it on 2026-10-25. The modelling concern stays a risk; the gate measures it against the monitors.

**Decision.**
- Google is ingested only into `aq.shadow_readings`, never `live_readings`, the models or the API (the isolation of ADR 0009). Hourly current conditions go under source `google`; the 30-day history endpoint goes under `google_history`, because the two can differ and are judged separately.
- Request the **local Indian index** (`ind_cpcb`, NAQI) and the pollutant concentrations. The Universal AQI is requested only to be stored under its own key; it is never shown as, or compared with, a CPCB AQI.
- The gate is `src.live.shadow_compare.gate()` with `GOOGLE_SPEC` / `GOOGLE_HISTORY_SPEC`, the same machinery and thresholds as WAQI (ADR 0009, "the fallback gate"):
  - **Reference:** OpenAQ station data in `aq.live_readings` (source `openaq`), hourly, in the units of the training data.
  - **Pollutants judged:** PM2.5, PM10, NO2, SO2, CO, O3. NH3 is reported by Google but OpenAQ has no live NH3, so it cannot be judged and is stored raw only.
  - **Stations:** all seven, ITO included. The reason WAQI excluded ITO (no monitor to map to) does not apply to a value modelled at the station's coordinates. ITO's OpenAQ reference ends earlier than the others, which only shortens its overlap.
  - **Units:** Google PM is used as is (ug/m3, whole numbers). Gases arrive in ppb and are converted at 25 C and 1 atm (24.45 L/mol) with molar masses NO2 46.0055, SO2 64.066, O3 47.9982, CO 28.010, to ug/m3 (CO to mg/m3). A changed unit label stops the run.
  - **Hours:** Google reports on the UTC hour (11:00Z is 16:30 IST). The shadow label is that instant in IST floored to the hour. The offset (-1, 0 or +1 hour against OpenAQ) is then chosen per pollutant on the first half of the overlap and the gate is scored on the second half, as for WAQI.
  - **Thresholds (second half):** overlap of at least 7 days; per pollutant, at least 5 of the 7 stations pass individually (at least 24 paired hours, corr >= 0.9, |bias| < 10% of the OpenAQ mean, MAE < 20% of the mean) and the passing stations pooled have at least 150 paired hours with the same three tests.
  - **Verdicts:** *PASS* needs every one of the six pollutants to pass; the usable stations are those passing all six. *PM-only* (PM2.5 and PM10 pass, a gas fails) is reported as its own subset verdict. *FAIL* otherwise.
- Report per pollutant and per station, including stations that fail, plus the pooled figure over all stations as information.
- **Information, not a verdict:** Google's `ind_cpcb` against the CPCB AQI recomputed in `aq.live_aqi` (same metrics, plus agreement of the CPCB category).
- **Two stages.** Stage 1 is the gate on `google_history` over the overlap of the 30 days Google can return and the OpenAQ data (about 2026-09-25 to 10-23). Stage 2 is the same gate on the hourly `google` rows collected live after the shadow job starts, at least 7 days of them, because live data collected after the rules were fixed is the cleaner test. A source is only proposed for the models if stage 2 also passes.
- **Outcomes.** PASS (both stages): propose a re-fit on Google-shaped inputs (Colab, same protocol as the live-consistent retrain); the owner decides. PM-only: propose it only as a PM source with a PM-only re-fit, as for WAQI. FAIL: Google stays display-only "current conditions", labelled as a modelled value, never as a CPCB reading.

**Known limits, stated before the result.**
- The reference is OpenAQ, which relays CPCB monitors; Google is a model of the air at a point. Agreement with the monitor is the test, so a source that is smoother than a monitor can fail on MAE while being useful context.
- The models also use NOx and weather. Google provides neither NOx nor station weather, so a Google-fed model would need its own re-fit without them; the gate does not judge that.
- The station coordinates in `aq.stations` are used as given. A few hundred metres of error is inside Google's grid but not inside a roadside monitor's footprint.
- A 30-day window is one season (post-monsoon into winter onset). A pass here is not evidence for other seasons.

**Cost control.** See `docs/TIER_3/GOOGLE_AIR_QUALITY.md`: one SKU, 10,000 free requests a month (70,000 on the India price list), about 5,200 requests a month for hourly polling of seven stations. The job refuses a run that plans more than `--max-requests` or would exceed 300 requests in an IST day, and the hourly workflow stays manual-only until a console quota cap and budget alert are confirmed.

**Consequences.** Google's key becomes a repository secret (`GOOGLE_AIR_QUALITY_API_KEY`). Nothing user-visible changes until a gate passes and the owner decides.
