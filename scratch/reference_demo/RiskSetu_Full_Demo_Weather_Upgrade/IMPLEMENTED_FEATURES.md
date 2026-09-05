# RiskSetu enhanced build

This build keeps the existing UI/architecture and adds the requested disaster-intelligence upgrades without pretending that unavailable data or emergency integrations exist.

## Implemented

- OpenStreetMap + Leaflet remain the basemap; OSRM remains routing. No Google Maps key is required.
- Open-Meteo is the primary current/forecast weather source with no client-side key.
- IndianAPI is retained as a backend fallback provider.
- Optional NASA GPM IMERG Early Run GIS point sampling is implemented when PPS credentials are configured. IMERG data is labelled as satellite near-real-time accumulation, not live radar or a flood forecast.
- Current Area Risk now calls `/api/risk/current` and can calculate from available rainfall, soil moisture, history, nearby incidents, and stored terrain/susceptibility when available. Missing slope/terrain is not fabricated.
- High/critical current risk produces actionable safety guidance on the overview page.
- Open-Meteo forecast windows are shown as time-based rainfall windows when the provider supplies forecast data.
- Regional/upstream rainfall screening monitors configurable points across the eastern Himalayan / North-East corridor and exposes `/api/regional-hazards` and `/api/regional-hazards/impact`.
- Regional events are explicitly screening watches, not deterministic downstream flood predictions.
- First-use geolocation request is implemented. If denied, manual location selection remains available and the prompt is not repeatedly forced on every reload.
- SOS flow is implemented with online send, offline queue, retry on reconnection, `112` and `108` call shortcuts, and an officer SOS queue.
- SOS states are only marked sent after backend acknowledgement. No fake police/hospital dispatch is claimed.
- PWA/offline shell and cached public data continue to work; queued incident reports and SOS requests persist in IndexedDB.
- Browser notification permission is opt-in from Settings rather than being requested immediately with geolocation.
- Local CORS allows Vite ports 5173-5176 plus production origins from `CORS_ORIGINS`.
- GSI remains optional. Mock history/resources stay labelled MOCK.

## External data/integration still needed for operational deployment

- Real verified hospital/police facility dataset or authorized places/emergency integration.
- Official flood/river-stage/discharge feeds and basin connectivity for validated downstream flood forecasting.
- Official GSI landslide inventory if desired.
- Validated/calibrated hazard model before treating a score as an operational warning.
- NASA PPS credentials if IMERG satellite accumulation is enabled.

## New backend endpoints

- `GET /api/risk/current?latitude=...&longitude=...`
- `GET /api/regional-hazards`
- `GET /api/regional-hazards/impact?latitude=...&longitude=...`
- `POST /api/sos`
- `GET /api/sos/{id}`
- `GET /api/officer/sos`
- `PATCH /api/officer/sos/{id}`
- `GET /api/emergency/resources?latitude=...&longitude=...`

## Local run

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `127.0.0.1:8000`, so `frontend/.env` can normally stay empty locally.


## Zero-cost multi-hazard upgrade

- Open-Meteo modelled soil moisture (0–27 cm aggregated proxy) added; clearly labelled as model data, not a physical sensor.
- Copernicus GLO-90 elevation via Open-Meteo Elevation API; slope is derived from a local elevation stencil.
- GloFAS river-discharge context via Open-Meteo Flood API.
- Separate Landslide Risk and Flood/Flash-Flood Risk scores plus overall area risk.
- Data-quality percentage and missing-feature transparency.
- Optional locally trained RandomForest runtime; no fake pre-trained model is bundled.
- Free NASA Global Landslide Catalog import helper for historical prototype data.
- NASA IMERG remains optional because PPS registration is required.

## September prototype workflow upgrade
- Officer geofenced mass alert with optional in-app/browser siren request and target count from consented locations.
- Incident confirmation geofence tightened to 500 m.
- Officer incident inspection includes nearby demo/verified hospitals and up to three hazard-scored route alternatives.
- Route labels distinguish no-known-elevated-risk, moderate caution, and high-risk/reschedule guidance.
- Shillong demo now uses multiple small synthetic micro-risk zones instead of one city-wide risk value; live current-area risk remains coordinate-specific.
- Login includes Citizen / Officer / Admin demo roles plus an Automated Judge Demo tour.
- Overview includes compact visual weather predictor.

Important: a normal website/PWA cannot override a phone's silent mode or reproduce government cell-broadcast emergency sirens. The siren feature works only where browser/PWA audio/notification permissions permit it. Demo emergency resources and micro-risk zones are clearly synthetic in MOCK mode.

## Public-source AI hazard intelligence
- Officer-only intelligence scan of free public disaster/news RSS sources.
- Cross-source corroboration score; public/social-style reports are treated as leads, never proof.
- Corroborates leads with current weather/rainfall before escalating confidence.
- Estimates candidate affected areas and a cautious impact window; never invents precise arrival times.
- High corroborated scenarios produce `PREPARE_EVACUATION_REVIEW`, not an automatic evacuation order.
- Officer can open the existing geofenced siren/area-alert workflow after review.
- Judge demo contains a synthetic, clearly labelled high-risk Shillong OSINT scenario.
- No paid social-media API is required. Direct X/Instagram/Facebook firehose access is not claimed.


## Full Demo + Weather UI update
- Login CTA renamed from Automated Judge Demo to Demo.
- Demo expanded from 4 timed pages to a 25-step guided end-to-end walkthrough with Previous, Pause/Auto Play, Next and Exit controls.
- Guided flow covers weather, micro-area risk, multi-hazard analysis, public-source intelligence, officer review, siren alerting, citizen incident/community verification, route decisions, safer-time logic, emergency access, SOS, offline sync, multilingual support and source transparency.
- Added a prominent Weather Intelligence panel to Citizen Overview with weather visual, temperature, humidity, 1h/24h/72h rain, soil moisture, satellite rainfall when available, forecast windows, precipitation chance and explicit Risk Engine linkage.
- Demo/synthetic information remains labelled; unsupported safer-time or disaster certainty is not invented.
