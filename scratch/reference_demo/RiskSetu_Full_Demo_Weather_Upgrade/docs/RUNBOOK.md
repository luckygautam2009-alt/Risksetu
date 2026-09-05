# Run RiskSetu locally

The actual project is the inner `NER_Landslide_AI_Starter` folder containing backend, frontend and this docs directory.

## First setup (Windows PowerShell)

From the project root:

```powershell
Copy-Item .env.example .env
py -3.12 -m venv backend/.venv-risksetu
backend/.venv-risksetu/Scripts/python.exe -m pip install -r backend/requirements.txt
cd frontend
npm install
```

The task already created `backend/.venv-risksetu` because the supplied `.venv` referenced an interpreter that is no longer installed. You can use the new environment directly on this machine. Python 3.12 is required by the pinned scientific dependencies.

## Start two terminals

Backend terminal, from project root:

```powershell
cd backend
.venv-risksetu/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend terminal, from project root:

```powershell
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. The Vite proxy forwards `/api` to port 8000. Backend docs: http://127.0.0.1:8000/api/docs. If an older backend occupies port 8000, stop that process in its original terminal before starting the updated backend. No existing user process is automatically stopped.

## Demo accounts

Default password for all demo accounts: `RiskSetuDemo!2026`.

| Account | Access |
|---|---|
| citizen@risksetu.demo | Reporting, routes, confirmations, notifications |
| officer@risksetu.demo | Verification, dispatch, road and shelter management |
| admin@risksetu.demo | Officer approval, plus officer functions |

Login has buttons for these local demo accounts. Changing `DEMO_PASSWORD` affects new demo database seeding only. Existing hashes are not overwritten on restart. Do not publish demo mode online.

## SIH demo flow

1. Open the Shillong dashboard and point out the explicit MOCK banner, risk factors and provenance.
2. Switch map layers to show risk zones, reports, rainfall and history. Change region to one of the eight NER states.
3. Sign in as citizen. Create a report at a distinct coordinate, add a photo, and inspect pending status. Under airplane/offline mode submit another report; it remains in the device queue, including media, until network restoration.
4. For community confirmation use a different account near the report. GPS is required and must be within 1 km; do not claim test coordinates are real GPS. Backend tests exercise this gate with test coordinates.
5. Sign in as officer, open Operations and review the report. Add notes, verify/reject, inspect evidence, generate a template briefing, record dispatch and complete it from Field response.
6. Record a blocked road, compare route alternatives and explain the excluded corridor. Synthetic routes are a visualization of the algorithm, not usable navigation directions.
7. Review population exposure. Add a verified demo shelter near Guwahati's low-risk zone, set capacity and check eligibility. High-risk, full or unassessed shelters are not offered to citizens.
8. Sign in as admin and approve an officer access request from a citizen account.

## Verification

```powershell
cd backend
.venv-risksetu/Scripts/python.exe -m pytest -q
cd ../frontend
npm run typecheck
npm run build
```

Tests use a temporary SQLite database and uploads folder and never modify the local demo database. To test the PWA offline shell, build the frontend, then restart the backend and open http://127.0.0.1:8000. FastAPI serves the compiled app on the same origin; the service worker precaches its HTML and compiled assets. `npm run dev` intentionally does not install the service worker. Offline basemap tiles are not cached; saved hazard metadata and reports remain accessible.

## Inventory and training

From project root:

```powershell
backend/.venv-risksetu/Scripts/python.exe scripts/import_gsi_inventory.py scripts/sample_inventory.csv --mock --dry-run
backend/.venv-risksetu/Scripts/python.exe scripts/import_gsi_inventory.py YOUR_LICENSED_INVENTORY.csv --source GSI
backend/.venv-risksetu/Scripts/python.exe scripts/import_risk_zones.py YOUR_ASSESSED_CELLS.json --dry-run
backend/.venv-risksetu/Scripts/python.exe ml/train_model.py YOUR_TRAINING_DATA.csv --split temporal
```

Training CSV columns: rainfall_24h_mm, rainfall_72h_mm, soil_moisture_pct, slope_deg, historical_landslides, susceptibility, label, event_date. Spatial holdout additionally needs spatial_group. Both classes must exist in training and test samples. No dataset or reported accuracy is fabricated. Generated artifacts are experimental and not automatically installed into the operational risk endpoint.

## Live environment

1. Create your Supabase project and apply `supabase/migrations/001_risksetu.sql` in the SQL editor or via your migration workflow. Test in a disposable project first.
2. Configure Supabase email authentication; populate server URL, anon key and service-role key in `.env`.
3. Create the first admin through Supabase Auth, then an authorized database operator runs:

```sql
update public.profiles set role='admin', officer_verified=true
where id='YOUR_AUTH_USER_UUID';
```

4. Set `DATA_MODE=live`. Set approved weather endpoint, Gemini key/model and OSRM endpoint as needed. Missing integrations return explicit unavailable states.
5. Import licensed history and fresh measured risk cells; register actual verified shelters through an approved officer. There is no sample seeding in live mode.
6. Use one API worker; production scaling and transactions require the work described in SECURITY.md. Configure frontend origin/API proxy for deployment. Never put backend secrets in VITE variables.

All environment keys are listed in `.env.example`. Operational deployment also needs ingestion scheduling, verified data, model validation, provider terms, security review and authority collaboration. The app is an SIH prototype, not an authorized public early-warning system.

## Vercel startup error: invalid DATA_MODE

`RuntimeError: DATA_MODE must be mock or live` means the function imported the app but rejected an environment setting before database initialization. It does not confirm a SQLite error.

In the Vercel project's environment-variable settings, the **name** is `DATA_MODE`; its **value** must be just `mock` or `live`. Do not enter `DATA_MODE=mock`, quotes, an empty string, `production`, or `development` in the value field. Surrounding whitespace and letter case are normalized by the parser. Unknown values still fail explicitly, and the value is never printed to logs.

Apply the setting to the relevant deployment environment (Production for the public domain), then redeploy. Use `mock` only for the local demonstration; a public operational backend needs `live` plus configured Supabase credentials and the migration. Changing the mode alone does not provide database access, durable serverless storage or a compiled frontend. Do not switch to `live` merely to silence the error if Supabase is not ready.

This repository's local SQLite database, process-local demo sessions and uploaded files are not durable shared storage for Vercel Functions. Moving SQLite to `/tmp` does not solve that architecture issue. Use the Services deployment below for the frontend and configured live backend. The development-only Vite proxy does not run in a static production deployment.

## Vercel Services deployment

The tracked `vercel.json` must sit beside `frontend/` and `backend/` at the Git repository root. A configuration placed in the enclosing Downloads folder is outside the repository and is not sent to GitHub or Vercel.

1. In Vercel Build and Deployment settings, set **Root Directory** to the repository root (leave it empty), not `frontend` or `backend`. Set **Framework Preset** to **Services**.
2. Remove old project-wide build/install/output overrides. Each service owns its build: the frontend runs `npm ci` and `npm run build`, producing `dist`; the backend uses FastAPI with `app.main:app` relative to `backend/`, its existing requirements, and Python 3.12.
3. Keep credentials in Vercel's environment settings. No environment values belong in `vercel.json`. For this same-origin deployment, leave `VITE_API_URL` unset so the existing frontend calls `/api/...` on its own origin. Never put server secrets in `VITE_` variables. Existing live-mode prerequisites above still apply.
4. Deploy the commit containing the root configuration. API rewrites run before the frontend catch-all and preserve the original path. `/openapi.json` goes to FastAPI so `/api/docs` can load its schema; the existing `/health`, `/risk/predict`, `/weather/{lat}/{lon}`, and `/reports` aliases also go to the backend.
5. Check `/`, `/api/health`, `/api/docs`, and `/openapi.json` on the resulting deployment. A missing API route should return the backend's 404, not frontend HTML.

The root `.vercelignore` excludes local environment files, virtual environments, generated builds, and local data from CLI uploads. Both services are built from source; application behavior is unchanged.

Configuration reference: [Vercel Services guide](https://vercel.com/kb/guide/vercel-services), [Vercel JSON schema](https://openapi.vercel.sh/vercel.json), and [Python runtime](https://vercel.com/docs/functions/runtimes/python). Use the current `services` format with top-level service rewrites, rather than the older `experimentalServices`/`routePrefix` format.

### Supabase API key settings

For live deployments, set `DATA_MODE=live`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` and `SUPABASE_SECRET_KEY`. Copy only the raw value into each hosted value field. The secret key belongs only in backend environment settings. Revoke exposed secrets and replace them before redeploying.

Legacy `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` names remain supported; nonblank modern names take precedence. Modern secret keys are sent in `apikey`, not as JWT bearer tokens. User access tokens retain bearer authentication. `SUPABASE_JWKS_URL` is not required: this backend checks user tokens through Supabase Auth. Apply the Supabase migration before using live data endpoints.
