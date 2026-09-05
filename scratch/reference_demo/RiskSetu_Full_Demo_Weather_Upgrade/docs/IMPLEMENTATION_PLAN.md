# RiskSetu implementation audit

The existing application is a Vite/React JavaScript screen and FastAPI service. There is no authentication, database, real GIS map, or trained model. The existing four API paths and baseline scoring formula are retained. The GSI sample GeoJSON and legacy adapters remain available.

## Changes

- Extend backend main, risk engine, requirements, frontend entry, styling, package metadata and training script.
- Add configuration, validated models, authentication, persistence, geospatial services, provider adapters, notifications, media, tests and inventory import.
- Add TypeScript dashboard, Leaflet provider, citizen/officer workflows, offline queue, service worker and Supabase client.
- Add Supabase migration with profiles, incidents, media, confirmations, zones, inventory, weather, shelters, roads, dispatches, notifications, user locations and audit logs.
- Add environment templates and operating instructions. Secrets stay on the server.

## Execution order

1. Foundation, persistent mock mode, roles and schema.
2. Government adapter boundaries, provenance, historical ingestion and transparent risk engine.
3. Reporting, uploads, community confidence and officer verification.
4. Route sampling, road exclusions and explanation.
5. Gemini structured analysis, briefings and language templates.
6. Population exposure and verified shelter ranking.
7. Realtime, offline queue, security checks, backend tests and frontend build.

## Scientific constraints

Baseline scores are not calibrated event probabilities: landslide_probability remains null until a validated model is installed. Demo history, weather, terrain, route geometry and population are explicitly MOCK. No fabricated government shelters are recommended. A lower-risk route is not a safety guarantee. Production deployment requires approved datasets, auth/storage setup, operational validation and infrastructure hardening.
