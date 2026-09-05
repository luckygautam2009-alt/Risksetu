# Provider contracts

All government ingestion requires approved access and compatible licensing. No government API URL is fabricated. `DATA_MODE=live` fails startup if Supabase server settings are absent, and never seeds demo rows.

## IndianAPI Weather

Set `INDIANAPI_KEY` on the backend. Requests go to `https://weather.indianapi.in/india/weather` with the key in the `x-api-key` header. RiskSetu maps North-East coordinates to the nearest supported regional city so no paid geocoding API is required. The provider may return `rainfall: null`; RiskSetu preserves missing rainfall as unknown instead of converting it to zero. Results are cached for 15 minutes by default to reduce quota usage.

## Historical landslide inventory (GSI optional)

RiskSetu no longer requires a GSI feed to start or deploy. In demo mode the included history is explicitly synthetic. In live mode the history endpoint may correctly return an empty list until you import an approved CSV/GeoJSON or collect verified records. The existing importer is kept as an optional future path and still validates/deduplicates source, coordinates and event date. Missing history is never interpreted as zero historical risk.

## Terrain and assessed risk cells

`bhuvan.py` reads features from imported risk cells. No restricted satellite service is scraped. Import a JSON array using `scripts/import_risk_zones.py`. Each object supplies name, latitude, longitude, district, state, radius_m, features, source, data_mode, and updated_at. Optional estimated_population is an estimate for that cell; overlapping cells must be deduplicated by the data provider. Features use the validated `/api/risk/predict` schema. The importer computes the retained baseline score; it does not infer unavailable elevation or vegetation values. Cells older than one hour cannot qualify a route or shelter as assessed. Refresh observations and reimport using each cell's existing id.

## OpenStreetMap map + OSRM routing

Leaflet with OpenStreetMap tiles remains the map renderer. Route alternatives now use the OSRM Route service, requested as GeoJSON with alternatives enabled. No Google Maps API key is used. `OSRM_BASE_URL` defaults to `https://router.project-osrm.org`; for production traffic, point it at a hosted/self-managed OSRM service. Route risk scoring remains provider-independent.

## Gemini

Set `GEMINI_API_KEY` and a supported `GEMINI_MODEL`. The adapter uses the documented [generateContent interface](https://ai.google.dev/api/generate-content) with structured JSON response, validates triage fields and keeps predictions separate. Reports are untrusted context. Failed AI calls do not discard uploaded evidence or change incident verification. Mock mode returns explicit templates with zero image-analysis confidence. MP4 files are stored for officer review; visual AI analysis currently supports still images. Language templates cover English/Hindi/Assamese navigation and geofenced alerts, not every UI paragraph.

## Realtime and notifications

Supabase Realtime invalidates subscribed data where RLS permits; the authenticated SSE stream supplies content-free change events for writes on the current API instance. Reconnection refreshes the current state and is backed off by 15 seconds. Use a single API worker for the prototype. Events do not expose reports, profile IDs or locations.

The service worker includes a browser-push receiver. A production VAPID subscription registry, push sender, approved SMS provider and delivery monitoring remain deployment integrations. `sms.py` explicitly returns NOT_CONFIGURED. In-app alerts and confirmations are persisted now. User location is opt-in and only positions recorded within one hour participate in incident geofencing. Notification copy is advisory and does not impersonate an official warning.

## Supabase

Apply the migration and configure email authentication. Profile creation follows the official [Supabase user-data pattern](https://supabase.com/docs/guides/auth/managing-user-data); role approval is stored separately from editable Auth metadata. Tables use [row-level security](https://supabase.com/docs/guides/database/postgres/row-level-security). Authenticated browser clients have read-only RLS access; authorized writes use the API's service role. Private media uses the [Supabase Storage access model](https://supabase.com/docs/guides/storage/security/access-control) and short-lived signed URLs. Database/storage integration must be tested in your Supabase project before deployment; the local environment has no configured Supabase project.
