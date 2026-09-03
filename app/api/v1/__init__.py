from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)

# Phase 1+: auth, regions, risk, reports, roads, impact, priority, alerts,
# audit-logs routers get included here, in that build order, per §25.
