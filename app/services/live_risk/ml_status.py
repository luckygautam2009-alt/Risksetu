"""
LIVE_RISK_V1 — ML status probe.

Reads the artifact metadata.json and determines whether the ML model is
scientifically validated and production-ready.

Policy:
  Only a model whose metadata.json contains BOTH:
    artifact_label  == "PRODUCTION READY"
    scientific_validity_verdict == "MODEL VALID — BASELINE SUSCEPTIBILITY MODEL"
  is considered available for production inference.

  The current artifact is labelled "EXPERIMENTAL — NOT PRODUCTION READY" and
  carries verdict "MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES".
  Therefore ml_status = "unavailable" and no inference is performed.
"""
from __future__ import annotations

import json
from pathlib import Path

import structlog

logger = structlog.get_logger("risksetu.live_risk.ml_status")

_ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "services" / "prediction" / "artifacts"
# Resolve relative to project root
_METADATA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "app" / "services" / "prediction" / "artifacts" / "metadata.json"
)

_VALID_ARTIFACT_LABEL = "PRODUCTION READY"
_VALID_VERDICT = "MODEL VALID — BASELINE SUSCEPTIBILITY MODEL"


def get_ml_status() -> dict[str, str | None]:
    """Return the current ML layer status dict.

    Returns:
        {
            "status": "available" | "unavailable",
            "model_version": str | None,
            "reason": str | None,
        }
    """
    try:
        if not _METADATA_PATH.exists():
            return {
                "status": "unavailable",
                "model_version": None,
                "reason": "No ML model artifact found in prediction/artifacts/.",
            }

        metadata: dict = json.loads(_METADATA_PATH.read_text())
        artifact_label: str = metadata.get("artifact_label", "")
        verdict: str = metadata.get("scientific_validity_verdict", "")
        model_version: str | None = metadata.get("model_version")

        if _VALID_ARTIFACT_LABEL in artifact_label and verdict == _VALID_VERDICT:
            logger.info("ml_status_available", model_version=model_version)
            return {
                "status": "available",
                "model_version": model_version,
                "reason": None,
            }

        reason = (
            f"Artifact label: '{artifact_label}'. "
            f"Validity verdict: '{verdict}'. "
            "Model requires DEM/terrain features before production deployment."
        )
        logger.debug("ml_status_unavailable", model_version=model_version, reason=reason)
        return {
            "status": "unavailable",
            "model_version": model_version,
            "reason": reason,
        }

    except (OSError, json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
        logger.warning("ml_status_probe_error", error_type=type(exc).__name__)
        return {
            "status": "unavailable",
            "model_version": None,
            "reason": f"Could not read ML artifact metadata: {type(exc).__name__}",
        }
