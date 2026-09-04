"""
Rainfall climatology baseline and anomaly evaluator.

Calculates standardized precipitation anomalies (z-scores) relative to
117-year historical IMD monthly subdivision normals (1901-2017).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rainfall import RainfallClimatology, RainfallSubdivision


@dataclass
class RainfallEvidenceResult:
    available: bool
    score: float  # [0-100]
    subdivision_name: str | None
    observed_mm: float | None
    climatology_mean_mm: float | None
    climatology_std_mm: float | None
    z_score: float | None
    anomaly_mm: float | None
    evidence_dict: dict[str, Any]
    explanation: str


class RainfallRiskEvaluator:
    """Evaluates rainfall risk using IMD historical climatological baselines."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(
        self,
        subdivision_id: uuid.UUID | None,
        observed_rainfall_mm: float | None,
        month: int | None,
        year: int | None = None,
    ) -> RainfallEvidenceResult:
        """Calculate standardized precipitation anomaly against 117-year climatology baseline."""
        if subdivision_id is None or observed_rainfall_mm is None or month is None:
            return RainfallEvidenceResult(
                available=False,
                score=0.0,
                subdivision_name=None,
                observed_mm=observed_rainfall_mm,
                climatology_mean_mm=None,
                climatology_std_mm=None,
                z_score=None,
                anomaly_mm=None,
                evidence_dict={
                    "reason": "Missing required rainfall parameters (subdivision_id, observed_rainfall_mm, and month).",
                },
                explanation="Rainfall factor unavailable: Observation parameters were not provided.",
            )

        # Lookup subdivision
        subdiv = self.db.get(RainfallSubdivision, subdivision_id)
        if not subdiv:
            return RainfallEvidenceResult(
                available=False,
                score=0.0,
                subdivision_name=None,
                observed_mm=observed_rainfall_mm,
                climatology_mean_mm=None,
                climatology_std_mm=None,
                z_score=None,
                anomaly_mm=None,
                evidence_dict={
                    "reason": f"Subdivision ID {subdivision_id} not found in database.",
                },
                explanation="Rainfall factor unavailable: Specified subdivision ID does not exist.",
            )

        # Lookup Climatology baseline for month
        c_stmt = select(RainfallClimatology).where(
            RainfallClimatology.subdivision_id == subdivision_id,
            RainfallClimatology.month == month,
        )
        clim = self.db.scalars(c_stmt).first()

        if not clim:
            return RainfallEvidenceResult(
                available=False,
                score=0.0,
                subdivision_name=subdiv.subdivision_name,
                observed_mm=observed_rainfall_mm,
                climatology_mean_mm=None,
                climatology_std_mm=None,
                z_score=None,
                anomaly_mm=None,
                evidence_dict={
                    "subdivision_name": subdiv.subdivision_name,
                    "month": month,
                    "reason": "No climatological normal record found for this subdivision and month.",
                },
                explanation=f"Rainfall factor unavailable: No 117-year baseline computed for month {month}.",
            )

        mean_mm = clim.mean_mm
        std_mm = clim.stddev_mm
        anomaly_mm = round(observed_rainfall_mm - mean_mm, 2)

        # Safe z-score calculation avoiding division by zero
        if std_mm > 0.0:
            z = round((observed_rainfall_mm - mean_mm) / std_mm, 2)
        else:
            z = 0.0

        # Continuous scoring formula:
        # z <= 0.0 (at or below normal) -> 0 score
        # 0.0 < z <= 3.0 -> maps linearly from 0 to 100 points
        # z > 3.0 -> capped at 100 points
        if z <= 0.0:
            score = 0.0
            anomaly_desc = "below or at historical normal"
        elif z <= 1.0:
            score = round(z * 33.33, 1)
            anomaly_desc = "mildly above normal"
        elif z <= 2.0:
            score = round(z * 33.33, 1)
            anomaly_desc = "significantly above normal (elevated threshold)"
        elif z <= 3.0:
            score = round(z * 33.33, 1)
            anomaly_desc = "severe precipitation anomaly (>2 sigma)"
        else:
            score = 100.0
            anomaly_desc = "extreme precipitation event (>3 sigma above 117-year normal)"

        score = max(0.0, min(100.0, score))

        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        m_name = month_names[month - 1] if 1 <= month <= 12 else str(month)

        explanation = (
            f"Precipitation of {observed_rainfall_mm:.1f} mm in {m_name} ({subdiv.subdivision_name}) "
            f"is {anomaly_desc} (Mean: {mean_mm:.1f} mm, StdDev: {std_mm:.1f} mm, Z-Score: {z:+.2f})."
        )

        evidence_dict = {
            "subdivision_name": subdiv.subdivision_name,
            "month": month,
            "year": year,
            "observed_rainfall_mm": observed_rainfall_mm,
            "climatology_mean_mm": mean_mm,
            "climatology_std_mm": std_mm,
            "anomaly_mm": anomaly_mm,
            "z_score": z,
            "years_in_baseline": clim.years_used,
            "baseline_period": f"{clim.source_period_start}-{clim.source_period_end}",
        }

        return RainfallEvidenceResult(
            available=True,
            score=score,
            subdivision_name=subdiv.subdivision_name,
            observed_mm=observed_rainfall_mm,
            climatology_mean_mm=mean_mm,
            climatology_std_mm=std_mm,
            z_score=z,
            anomaly_mm=anomaly_mm,
            evidence_dict=evidence_dict,
            explanation=explanation,
        )
