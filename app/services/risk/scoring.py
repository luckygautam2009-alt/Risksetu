"""
Scoring engine, proportional weight redistribution, and confidence calculation.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.risk import RiskFactorDetail
from app.services.risk.constants import (
    BASE_WEIGHT_HISTORICAL,
    BASE_WEIGHT_RAINFALL,
    BASE_WEIGHT_SPATIAL_CONTEXT,
    RISK_LEVEL_HIGH_MAX,
    RISK_LEVEL_LOW_MAX,
    RISK_LEVEL_MODERATE_MAX,
)
from app.services.risk.rainfall import RainfallEvidenceResult
from app.services.risk.spatial import SpatialEvidenceResult


@dataclass
class ScoreCompositionResult:
    risk_score: float
    risk_level: str
    confidence_score: float
    factors: list[RiskFactorDetail]
    weight_redistributed: bool
    redistribution_note: str | None


class RiskScoringEngine:
    """Combines individual evidence factors into a composite, explainable risk assessment."""

    @staticmethod
    def determine_risk_level(score: float) -> str:
        """Categorize numerical risk score into discrete operational tiers."""
        if score <= RISK_LEVEL_LOW_MAX:
            return "LOW"
        elif score <= RISK_LEVEL_MODERATE_MAX:
            return "MODERATE"
        elif score <= RISK_LEVEL_HIGH_MAX:
            return "HIGH"
        else:
            return "CRITICAL"

    @classmethod
    def compose_score(
        cls,
        spatial_res: SpatialEvidenceResult,
        rainfall_res: RainfallEvidenceResult,
    ) -> ScoreCompositionResult:
        """Compose final risk score with mathematical proportional weight redistribution."""
        factors: list[RiskFactorDetail] = []

        # 1. Historical Landslide Factor
        factors.append(
            RiskFactorDetail(
                name="historical_landslide_evidence",
                display_name="Historical Landslide Spatial Density & Proximity",
                score=spatial_res.score,
                raw_weight=BASE_WEIGHT_HISTORICAL,
                effective_weight=BASE_WEIGHT_HISTORICAL,  # will be normalized below
                available=True,
                evidence=spatial_res.evidence_dict,
                explanation=spatial_res.explanation,
            )
        )

        # 2. Rainfall Anomaly Factor
        factors.append(
            RiskFactorDetail(
                name="rainfall_climatology_anomaly",
                display_name="Precipitation Anomaly (IMD 117-Year Baseline)",
                score=rainfall_res.score,
                raw_weight=BASE_WEIGHT_RAINFALL,
                effective_weight=BASE_WEIGHT_RAINFALL,  # will be normalized below
                available=rainfall_res.available,
                evidence=rainfall_res.evidence_dict,
                explanation=rainfall_res.explanation,
            )
        )

        # 3. Terrain & Morphometry Factor (Explicitly unavailable in source repository)
        factors.append(
            RiskFactorDetail(
                name="terrain_morphometry",
                display_name="DEM Terrain Morphometry (Slope, Aspect, TWI)",
                score=0.0,
                raw_weight=BASE_WEIGHT_SPATIAL_CONTEXT,
                effective_weight=0.0,
                available=False,
                evidence={"status": "NOT AVAILABLE IN SOURCE DATA"},
                explanation="Terrain morphometry factor unavailable: No Bhoonidhi/CartoDEM raster tile is present.",
            )
        )

        # Calculate sum of raw weights for available factors
        available_factors = [f for f in factors if f.available]
        available_weight_sum = sum(f.raw_weight for f in available_factors)

        weight_redistributed = available_weight_sum < 1.0
        redistribution_note = None

        composite_score = 0.0
        if available_weight_sum > 0.0:
            for f in factors:
                if f.available:
                    f.effective_weight = round(f.raw_weight / available_weight_sum, 4)
                    composite_score += f.score * f.effective_weight
                else:
                    f.effective_weight = 0.0
        else:
            composite_score = 0.0

        composite_score = round(max(0.0, min(100.0, composite_score)), 1)
        risk_level = cls.determine_risk_level(composite_score)

        if weight_redistributed:
            redistribution_note = (
                f"Weights were redistributed among {len(available_factors)} available factor(s) "
                f"(Total active weight: {available_weight_sum * 100:.0f}%)."
            )

        # Compute Confidence Score [0-100]
        # Evaluates evidence coverage independently from the risk score
        confidence = cls.calculate_confidence(spatial_res, rainfall_res)

        return ScoreCompositionResult(
            risk_score=composite_score,
            risk_level=risk_level,
            confidence_score=confidence,
            factors=factors,
            weight_redistributed=weight_redistributed,
            redistribution_note=redistribution_note,
        )

    @staticmethod
    def calculate_confidence(
        spatial_res: SpatialEvidenceResult,
        rainfall_res: RainfallEvidenceResult,
    ) -> float:
        """Calculate quantitative confidence score [0-100] based on evidence completeness."""
        conf = 0.0

        # 1. Historical spatial sample completeness (up to 40 pts)
        if spatial_res.count_within_25km > 0:
            # 20 pts for nearby data points
            conf += min(20.0, spatial_res.count_within_25km * 2.0)
            # Up to 20 pts for ratio of dated events
            if spatial_res.dated_events_count > 0:
                ratio = spatial_res.dated_events_count / spatial_res.count_within_25km
                conf += 20.0 * ratio
            else:
                conf += 5.0  # spatial points exist but undated
        else:
            conf += 10.0  # reliable zero-evidence baseline

        # 2. Rainfall evidence completeness (up to 30 pts)
        if rainfall_res.available:
            conf += 30.0
        else:
            conf += 0.0  # missing rainfall inputs

        # 3. Terrain morphometry completeness (up to 30 pts)
        # Currently DEM is unavailable -> 0 pts
        # (When DEM tiles are ingested in future phases, this adds up to 30 pts)

        return round(max(0.0, min(100.0, conf)), 1)
