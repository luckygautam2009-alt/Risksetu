# RISKSETU AI — Backend

NER landslide early-warning decision-support system.
SIH 2026 | PS ID 26001 | Team: Beacon Devs

This repository is being built **backend-first, one phase at a time**,
following `RISKSETU_AI_ULTIMATE_MASTER_BUILD.md` (the full specification —
keep it alongside this repo; every phase's Definition of Done is defined
there in §26).

## Status: Phase 0 — Foundation ✅

What exists right now:
- FastAPI app skeleton (`app/main.py`) with CORS, request-correlation
  middleware, and a standard `{data, meta}` / `{error}` response contract.
- Centralized settings (`app/core/config.py`) — nothing hardcoded.
- Structured JSON logging with automatic secret redaction.
- `/api/v1/health` and `/api/v1/readiness` endpoints.
- Postgres/PostGIS + Redis via Docker Compose.
- Alembic wired up (no migrations yet — that's Phase 1).
- Password hashing / JWT helper functions, unit-tested (routes come in
  Phase 1).
- CI (GitHub Actions): lint + test on every push.

**Not yet built:** any database tables, auth routes, RBAC, risk engine,
trust engine, graph/impact engine, priority engine, alerts, or frontend.
Do not add these until their phase (see roadmap below).

## Quickstart (local, zero external API calls)

```bash
cp .env.example .env
# edit .env if needed — defaults work with docker-compose as-is

docker compose up -d db redis
poetry install
poetry run alembic upgrade head   # no-op until Phase 1 adds migrations
poetry run uvicorn app.main:app --reload
```

Visit:
- http://localhost:8000/docs — OpenAPI docs
- http://localhost:8000/api/v1/health
- http://localhost:8000/api/v1/readiness

Or run everything (API included) in Docker:

```bash
docker compose up --build
```

## Tests

```bash
poetry run pytest --cov=app
```

## Roadmap (see spec §25 for full detail)

| Phase | Name | Status |
|---|---|---|
| 0 | Foundation | ✅ done |
| 1 | Database + Auth | ⏳ next |
| 2 | Data Backbone (terrain, rainfall, roads, ingestion) | not started |
| 3 | Intelligence (risk engine, trust engine) | not started |
| 4 | Differentiator (graph, isolation, priority) | not started |
| 5 | Operational Loop (alerts) | not started |
| 6 | Hardening | not started |
| 7 | Frontend | not started |

## Engineering rules (non-negotiable, see spec §0)

1. Server is the source of truth — never trust client-supplied scores,
   roles, or computed IDs.
2. Every state change is auditable.
3. Every module has 4 contracts: input, output, failure modes, tests.
4. External data is disposable — fixtures/cache make the demo work offline.
5. Derived data is versioned.
6. Idempotency everywhere it matters.
7. Fail closed for auth; fail soft for non-critical external deps.
8. No raw exception/stack trace reaches the client.
9. No destructive operation without explicit auth + audit log.
10. If it can't be demoed end-to-end, it isn't MVP-complete.
