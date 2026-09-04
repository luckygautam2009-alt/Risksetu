"""
Deterministic fingerprinting and deduplication logic for alerts.
"""
import hashlib
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.alerts.constants import CALCULATION_VERSION, SPATIAL_BUCKET_PRECISION

if TYPE_CHECKING:
    from app.models.alert import Alert


def compute_alert_fingerprint(
    alert_type: str,
    severity: str,
    latitude: float,
    longitude: float,
    source_id: str | None = None,
    calculation_version: str = CALCULATION_VERSION,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for alert deduplication.
    Coordinates are quantized into spatial buckets (~111m precision at 3 decimal places).
    """
    bucket_lat = round(latitude, SPATIAL_BUCKET_PRECISION)
    bucket_lon = round(longitude, SPATIAL_BUCKET_PRECISION)
    raw_key = (
        f"{alert_type.strip().upper()}:"
        f"{severity.strip().upper()}:"
        f"{bucket_lat:.3f}:"
        f"{bucket_lon:.3f}:"
        f"{(source_id or '').strip()}:"
        f"{calculation_version.strip()}"
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def find_active_duplicate(db: Session, fingerprint: str) -> "Alert | None":
    """
    Checks if an ACTIVE alert with the exact fingerprint already exists in the database.
    """
    from app.models.alert import Alert

    stmt = select(Alert).where(
        Alert.fingerprint == fingerprint,
        Alert.status == "ACTIVE",
    ).limit(1)
    return db.execute(stmt).scalar_one_or_none()
