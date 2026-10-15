# Azure setup for the API (Stage 5)

What to create, in the Azure portal, before the first deploy. Nothing here is created by code; `deploy-backend.yml` only rolls an existing Container App to a new image.
Items marked **TODO(verify)** are prices or portal behaviour I could not confirm from this machine: check them on the page named before relying on them.

## What you are creating

| # | Resource | Name (suggested) | Settings |
| :--- | :--- | :--- | :--- |
| 1 | Resource group | `rg-delhi-air` | Region **Central India** (`centralindia`) |
| 2 | Container Apps environment | `cae-delhi-air` | Consumption only (no dedicated workload profile), same region; zone redundancy **off**; logs: see step 3 |
| 3 | Container App | `ca-delhi-air-api` | Consumption, **0.25 vCPU / 0.5 GiB**, **min replicas 0**, max replicas 2, HTTP ingress **external**, image from GHCR |
| 4 | Microsoft Entra app registration | `gh-delhi-air-deploy` | One federated credential for GitHub Actions (OIDC); role Contributor on `rg-delhi-air` only |

Scale to zero means no compute charge while nobody calls the API; the first call after idle takes a cold start (the image is small: no pandas, no models).
Cost, **TODO(verify)** on the Container Apps pricing page: the Consumption plan has a monthly free grant of vCPU-seconds, GiB-seconds and requests per subscription, and I expect this app to stay inside it.
Set a budget alert anyway (step 0).

## Step 0. Before anything else (once per subscription)

1. Portal > **Subscriptions** > your student subscription > **Resource providers**: register `Microsoft.App` and `Microsoft.OperationalInsights`.
2. Portal > **Cost Management** > **Budgets** > Add: scope = the subscription, amount a few dollars, alerts at 50%, 80% and 100% to your email.
3. **Azure for Students region policy (TODO(verify))**: student subscriptions often restrict allowed regions. If Central India is not offered in the region drop-down, pick the nearest region the portal does offer and tell me; nothing in the code depends on the region.
4. **Entra permissions (TODO(verify))**: creating an app registration (step 4) needs a tenant that lets you register applications. If the portal refuses (a university tenant can block it), tell me: the alternative is a personal tenant, not a stored password.

## Step 1. Resource group

Portal > **Resource groups** > Create: name `rg-delhi-air`, region Central India > Review + create.

## Step 2-3. Container Apps environment and the Container App (one wizard)

Portal > **Container Apps** > Create:

1. **Basics:** subscription, resource group `rg-delhi-air`, name `ca-delhi-air-api`, region Central India, **Container Apps Environment** > Create new:
   - name `cae-delhi-air`; **Environment type: Consumption only**; zone redundancy disabled.
   - **Monitoring** tab: Logs destination. If **Don't save** is offered, choose it. Otherwise keep Azure Log Analytics (it creates a workspace; **TODO(verify)** its free ingestion allowance on the Log Analytics pricing page) and later set a daily cap on the workspace (Log Analytics workspace > Usage and estimated costs > Daily cap, e.g. 0.1 GB).
   - Networking: leave defaults (public network access on, no custom VNet).
2. **Container** tab:
   - Keep **Use quickstart image** ticked (`mcr.microsoft.com/k8se/quickstart:latest`); the first deploy replaces it with ours.
   - **CPU and memory: 0.25 CPU cores, 0.5 Gi memory.**
   - Environment variables are added after creation (step 5), because the secret has to exist first.
3. **Ingress** tab: **Enabled**; Ingress traffic **Accepting traffic from anywhere**; Ingress type **HTTP**; Transport auto; target port **80** (the quickstart image; the deploy workflow switches it to 8000); insecure connections **off**.
4. Create. Then open the app > **Application > Revision management / Scale** (the label varies by portal version) and set **Min replicas = 0, Max replicas = 2**.

## Step 4. OIDC for GitHub Actions (no password stored anywhere)

1. Portal > **Microsoft Entra ID** > **App registrations** > New registration: name `gh-delhi-air-deploy`, single tenant, no redirect URI. Copy **Application (client) ID** and **Directory (tenant) ID**.
2. The app > **Certificates & secrets** > **Federated credentials** > Add credential:
   - Scenario: **GitHub Actions deploying Azure resources**
   - Organization `siddhu-exe`, Repository `Air-Quality-Risk-Forecasting`
   - Entity type **Environment**, environment name `production`
   - Name `github-production`. (Resulting subject: `repo:siddhu-exe/Air-Quality-Risk-Forecasting:environment:production`; issuer `https://token.actions.githubusercontent.com`; audience `api://AzureADTokenExchange`.)
   - Do **not** create a client secret.
3. Portal > **Resource groups** > `rg-delhi-air` > **Access control (IAM)** > Add role assignment: role **Contributor**, assign to the `gh-delhi-air-deploy` application (Select members, search the app name). Scope stays the resource group, so the credential can touch nothing else.
4. Copy your **Subscription ID** (Subscriptions > your subscription > Overview).

## Step 5. The database secret and the API settings (Container App)

Open `ca-delhi-air-api`:

1. **Settings > Secrets** > Add: key `database-url-readonly`, type Container Apps Secret, value = your **`DATABASE_URL_READONLY`** pooler connection string (the `api_readonly.<project-ref>` user). Paste it only here.
2. **Application > Containers > Edit and deploy** > the container > **Environment variables** > Add:
   | Name | Source | Value |
   | :--- | :--- | :--- |
   | `DATABASE_URL_READONLY` | Reference a secret | `database-url-readonly` |
   | `FRONTEND_ORIGIN` | Manual entry | the Vercel URL, e.g. `https://<project>.vercel.app` (several origins: comma-separated). Until Vercel exists use `http://localhost:5173`. |
   Optional: `STALE_AFTER_HOURS` (default 3), `CACHE_SECONDS` (default 60).
3. Save and create the revision.

## Step 6. GitHub: secrets, variables, environment

Repository > **Settings**:

1. **Environments** > New environment `production` (optionally add yourself as a required reviewer so every deploy waits for your approval).
2. **Secrets and variables > Actions > Secrets** (repository secrets):
   | Name | Value |
   | :--- | :--- |
   | `AZURE_CLIENT_ID` | Application (client) ID from step 4 |
   | `AZURE_TENANT_ID` | Directory (tenant) ID |
   | `AZURE_SUBSCRIPTION_ID` | Subscription ID |
   These are identifiers, not credentials; they are stored as secrets because `azure/login` expects them there.
3. **Variables** (repository variables):
   | Name | Value |
   | :--- | :--- |
   | `AZURE_RESOURCE_GROUP` | `rg-delhi-air` |
   | `AZURE_CONTAINER_APP` | `ca-delhi-air-api` |
4. Not needed in GitHub for the API: the database string lives only in the Container App secret. (`forecast.yml` and the ingest/score workflows use the repository secrets `DATABASE_URL`; the forecast dry run also reads `DATABASE_URL_READONLY`, which is still to be added as a repository secret.)

## Step 7. First image and first deploy (I stop before this)

1. Actions > **deploy-backend** > Run workflow with **deploy = off**: runs the API tests and pushes `ghcr.io/siddhu-exe/delhi-air-api` to GHCR (no Azure involved).
2. GitHub > your profile > **Packages** > `delhi-air-api` > Package settings > **Change visibility > Public**. The image holds code and three report CSVs only, no credentials, so a public image lets the Container App pull without registry credentials. (Keep it private instead and you must add the package as a registry with a read-only token in the Container App.)
3. Run the workflow again with **deploy = on**. It logs in with OIDC, rolls the app to the new image, sets the ingress target port to 8000 and calls `/api/v1/health` (retrying through a cold start).
4. Check by hand: open `https://<app fqdn>/api/v1/health` (the FQDN is on the Container App overview page) and `https://<app fqdn>/api/docs`.

## Rollback and teardown

- Roll back: Container App > Revision management > activate the previous revision, or re-run the workflow from an older commit.
- Remove everything: delete the resource group `rg-delhi-air` (the Entra app and its federated credential are separate; delete the app registration too).
