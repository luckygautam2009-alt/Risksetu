# RiskSetu provider change

This build removes the paid Google Routes dependency and the required IMD/GSI setup.

- Weather: IndianAPI (`INDIANAPI_KEY`, server-side only). The key is sent as `x-api-key`.
- Map rendering: Leaflet + OpenStreetMap tiles (no key).
- Navigation: OSRM + OpenStreetMap road graph (no Google key). `OSRM_BASE_URL` can be changed later.
- Historical landslides: GSI is optional. Demo mode uses labelled synthetic history; live mode can return no history until an approved dataset is imported.
- Missing rainfall/history is represented as unknown/unavailable, not as zero risk.

For the current student/demo deployment use `DATA_MODE=mock` plus `INDIANAPI_KEY`. This keeps local/demo persistence while allowing the weather card to use IndianAPI when the provider is reachable.
