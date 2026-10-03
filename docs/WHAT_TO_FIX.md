# What Needs to Change (simple version)

## The one big idea
The AQI number you predict is **already a 24-hour average**, so it barely moves from one hour to the next.
That means "just copy the last value" is almost as good as your models. Any result is only impressive
if it **beats that simple guess**, so always show the comparison.

---

## Must fix (these hurt you in an interview)

1. **Your 1-hour model loses to "copy the last value"** on two of three measures (RMSE and R²).
   → Show this honestly. Don't advertise "R² 0.99" as a win.

2. **README numbers don't match your result files.**
   → Make one script generate every number, and copy the table from its output.

3. **The alert threshold was picked using the test data.** That's like seeing the exam answers.
   → Pick it on the validation data, then check it on test once.

4. **"95.7% of Severe days caught" hides the other side:** about half of the alarms are false.
   → Always show "caught" and "false alarms" together.

5. **The "17 hours warning" and "0% critical misses" numbers are easy to get** with almost any forecast.
   → Compare them against "copy the last value". Tighten the lead-time rule.

6. **The Diwali study can't measure the ban.** The ban was active in every year you looked at,
   so there's nothing to compare against. Your own tests (pre-trends, placebo) show the method fails.
   → Rename it to "why simple before/after comparisons mislead" and drop claims you can't prove
   (stubble burning, inversion as *the cause*).

7. **The model never saw a winter before being tested on one.**
   → Rebuild AQI for 2023–2024 from the raw pollutant data you already have, and train on past winters.

8. **Tone of the docs.** Words like "guarantee", "100% compliance" and "cryptographic integrity" read as
   AI-generated hype. → Plain language, plus a "Limitations" section near the top of the README.

9. **Tests don't test anything** (they just print).
   → Add a few real tests, especially "does the target line up with the right future hour?"

---

## Should add (makes it stand out)

- **Weather and fire data:** wind, boundary-layer height (Open-Meteo), and crop-fire counts (NASA FIRMS).
- **Forecast PM2.5 directly** (it changes hour to hour, so real skill shows).
- **Uncertainty ranges**: "tomorrow 380–450, 70% chance of Severe" instead of a single number.
- **Test on more than one winter** (2024 and 2025), not just one 2-month window.

## For real users (production)

- Live data pulled automatically each hour, plus a forecast produced every day.
- Track whether the live forecasts actually beat "copy the last value".
- Compare against the government's own forecast (IITM AQEWS / SAFAR).
- Clear disclaimer and uncertainty shown to the public.

---

**Order:** Fix 1–6 and 8–9 first (about 1–2 weeks, mostly honesty and reporting). Then 7 and the "should add" list.
Full step-by-step instructions are in `docs/IMPROVEMENT_PLAN.md`.
