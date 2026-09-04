from fastapi import APIRouter

from app.api.v1 import alerts, auth, ground_reports, health, impact, priority, risk

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ground_reports.router)
api_router.include_router(risk.router)
api_router.include_router(impact.router)
api_router.include_router(priority.router)
api_router.include_router(alerts.router)



