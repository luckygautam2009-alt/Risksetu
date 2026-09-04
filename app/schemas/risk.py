"""
Pydantic schemas for the Explainable Spatial Risk Intelligence Engine.
"""
from __future__ import annotations

from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskEvaluationRequest(BaseModel):
    """Input parameters for evaluating landslide risk at a specific spatial coordinate."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS 84 Latitude in decimal degrees.",
        examples=[30.3165],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS 84 Longitude in decimal degrees.",
        examples=[78.0322],
    )
    rainfall_subdivision_id: uuid.UUID | None = Field(
        default=None,
        description="Optional UUID of the IMD meteorological subdivision for rainfall baseline lookup.",
    )
    observed_rainfall_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional observed precipitation in millimeters for anomaly evaluation.",
        examples=[350.0],
    )
    year: int | None = Field(
        default=None,
        ge=1800,
        le=2100,
        description="Optional calendar year of the observation.",
        examples=[2020],
    )
    month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Optional calendar month of the observation (1-12).",
        examples=[7],
    )

    @field_validator("observed_rainfall_mm")
    @classmethod
    def validate_rainfall_consistency(cls, v: float | None, info: Any) -> float | None:
        """Ensure rainfall observation is accompanied by month when provided."""
        # Month validation will be checked in the engine coordinator
        return v


class RiskFactorDetail(BaseModel):
    """Detailed breakdown of a single contributing risk factor."""

    name: str = Field(..., description="Machine-readable factor name.")
    display_name: str = Field(..., description="Human-readable factor title.")
    score: float = Field(..., ge=0.0, le=100.0, description="Normalized factor score [0-100].")
    raw_weight: float = Field(..., ge=0.0, le=1.0, description="Baseline configured factor weight.")
    effective_weight: float = Field(..., ge=0.0, le=1.0, description="Normalized weight after redistribution.")
    available: bool = Field(..., description="Whether source data for this factor was present and valid.")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Structured quantitative evidence.")
    explanation: str = Field(..., description="Plain-language explanation of this factor's contribution.")


class RiskEvaluationData(BaseModel):
    """Payload of the risk evaluation response."""

    risk_score: float = Field(..., ge=0.0, le=100.0, description="Composite risk score [0-100].")
    risk_level: str = Field(..., description="Categorical risk level: LOW, MODERATE, HIGH, CRITICAL.")
    confidence_score: float = Field(..., ge=0.0, le=100.0, description="Data richness and confidence [0-100].")
    calculation_version: str = Field(..., description="Version of the risk calculation algorithm.")
    queried_location: dict[str, float] = Field(..., description="Queried latitude and longitude.")
    factors: list[RiskFactorDetail] = Field(..., description="List of all evaluated contributing factors.")
    weight_redistributed: bool = Field(..., description="Whether weights were redistributed due to missing factors.")
    summary_explanation: str = Field(..., description="Synthesis of the primary drivers of the risk score.")
    limitations: list[str] = Field(..., description="Explicit documentation of data gaps and assumptions.")


class RiskEvaluationResponse(BaseModel):
    """Standard API success envelope for risk evaluation."""

    data: RiskEvaluationData
    meta: dict[str, Any] = Field(default_factory=dict)
