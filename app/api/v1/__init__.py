from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    auth,
    evidence,
    ground_reports,
    health,
    identity,
    impact,
    landslides,
    live_risk,
    osint,
    priority,
    regional_watch,
    risk,
    road_risk,
    roads,
    shelters,
    sos,
    subscriptions,
    weather,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(identity.router)
api_router.include_router(evidence.router)
api_router.include_router(ground_reports.router)
api_router.include_router(risk.router)
api_router.include_router(impact.router)
api_router.include_router(priority.router)
api_router.include_router(alerts.router)
api_router.include_router(weather.router)
api_router.include_router(live_risk.router)
api_router.include_router(road_risk.router)
api_router.include_router(roads.router)
api_router.include_router(landslides.router)
api_router.include_router(sos.router)
api_router.include_router(shelters.router)
api_router.include_router(osint.router)
api_router.include_router(regional_watch.router)
api_router.include_router(subscriptions.router)




