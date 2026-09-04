"""
Validation utilities for ground report submissions.
"""
from __future__ import annotations

import datetime
import math

from app.core.errors import ValidationAppError


class GroundReportValidator:
    """Deterministic validator for field observation payloads."""

    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> tuple[float, float]:
        """Verify latitude and longitude are valid finite terrestrial coordinates."""
        if math.isnan(latitude) or math.isinf(latitude):
            raise ValidationAppError("Latitude must be a finite real number.")
        if math.isnan(longitude) or math.isinf(longitude):
            raise ValidationAppError("Longitude must be a finite real number.")

        if not (-90.0 <= latitude <= 90.0):
            raise ValidationAppError(f"Latitude {latitude} out of valid range [-90.0, 90.0].")
        if not (-180.0 <= longitude <= 180.0):
            raise ValidationAppError(f"Longitude {longitude} out of valid range [-180.0, 180.0].")

        return float(latitude), float(longitude)

    @staticmethod
    def validate_observation_time(
        observed_at: datetime.datetime,
        clock_drift_minutes: float = 5.0,
        max_past_days: float = 365.0,
    ) -> datetime.datetime:
        """Validate observation timestamp against future drift and stale past horizons."""
        now = datetime.datetime.now(datetime.timezone.utc)
        target = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=datetime.timezone.utc)

        if target > now + datetime.timedelta(minutes=clock_drift_minutes):
            raise ValidationAppError("Observation timestamp cannot be in the future.")

        if target < now - datetime.timedelta(days=max_past_days):
            raise ValidationAppError(f"Observation timestamp is too stale (> {max_past_days} days).")

        return target

    @staticmethod
    def validate_description(description: str, min_len: int = 10, max_len: int = 2000) -> str:
        """Sanitize and validate description text."""
        cleaned = description.strip()
        if len(cleaned) < min_len:
            raise ValidationAppError(f"Description must contain at least {min_len} non-whitespace characters.")
        if len(cleaned) > max_len:
            raise ValidationAppError(f"Description exceeds maximum length of {max_len} characters.")
        return cleaned
