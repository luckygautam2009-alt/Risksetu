# Architecture
Sources -> ingestion/normalization -> feature store -> ML inference -> risk service -> PostGIS/GeoJSON -> GIS dashboard / alert service / field app.

Suggested production modules: auth+RBAC; Postgres/PostGIS; object storage; scheduled ingestion workers; model registry; audit log; notification gateway; offline-first mobile/PWA sync; multilingual templates; incident/road status; observability.

Prediction unit should be a geospatial cell/road segment + forecast horizon. Store model_version, feature_timestamp, source provenance and confidence with every prediction.
