# Vercel setup for the dashboard (Stage 6)

The dashboard is the static Vite build in `frontend/`. Vercel builds it from `main` and serves it; it calls the API on Azure from the browser, so the API must allow the Vercel origin (step 5).

## 1. Import the project
1. Vercel dashboard > **Add New** > **Project** > import `siddhu-exe/Air-Quality-Risk-Forecasting` (grant the Vercel GitHub app access to that one repository).
2. **Framework Preset:** Vite (detected). **Root Directory:** `frontend` (click Edit and select it).
3. Build settings stay as read from `frontend/vercel.json`: build command `npm run build`, output directory `dist`, SPA rewrite and immutable caching for `/assets/`. Leave **Install Command** at the default.
4. Do not click Deploy yet.

## 2. Environment variables (before the first build)
Project > Settings > **Environment Variables**, for **Production** and **Preview**:

| Name | Value |
| :--- | :--- |
| `VITE_USE_MOCK` | `false` |
| `VITE_API_BASE_URL` | `https://<your Container App FQDN>/api/v1` (the FQDN is on the Container App overview page; no trailing slash) |

These are baked into the build, so changing them needs a redeploy. If `VITE_USE_MOCK` is left unset the site serves the built-in sample data and says "Sample readings · live feed pending" in the header: a visible sign that the variable is missing.

## 3. Deploy
Click **Deploy**. The first build takes a couple of minutes. Open the production URL (`https://<project>.vercel.app`).

## 4. Check it
- Overview loads; with the data source behind real time you should see the stale banner ("Readings are delayed ...") and every forecast cell showing a reason such as "Forecast job not running". That is the correct state until the forecast job runs on fresh data.
- Browser dev tools > Network: calls go to `https://<FQDN>/api/v1/overview` and answer 200. A red CORS error means step 5 is not done yet.

## 5. Allow the dashboard to call the API (CORS)
In Azure, Container App `ca-delhi-air-api` > **Application > Containers > Edit and deploy** > the container > **Environment variables**: set `FRONTEND_ORIGIN` to the production URL, exactly as the browser shows it (scheme and host, no path, no trailing slash), e.g. `https://air-quality-risk-forecasting.vercel.app`. Several origins are comma-separated (add a custom domain here later). Save and create the new revision.

Preview deployments get their own URLs and are not allowed by this setting; test previews with `VITE_USE_MOCK=true` or add the preview URL temporarily.

## 6. Afterwards
- Tell me the Vercel URL; I will record it in the README.
- `frontend/vercel.json` and `.env.example` document the same variables.
