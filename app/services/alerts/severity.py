"""
Deterministic severity mapping engine for operational alerts.
"""
from typing import Any

from app.services.alerts.constants import (
    AlertSeverity,
    PRIORITY_SCORE_CRITICAL,
    PRIORITY_SCORE_HIGH,
    RISK_SCORE_CRITICAL,
    RISK_SCORE_HIGH,
    SEVERITY_PRECEDENCE,
)


def determine_alert_severity(
    risk_score: float | None = None,
    risk_level: str | None = None,
    priority_score: float | None = None,
    priority_level: str | None = None,
    isolation_severity: str | None = None,
    ground_intelligence_summary: dict[str, Any] | None = None,
) -> AlertSeverity:
    """
    Deterministically computes the highest-precedence severity rating across
    all multi-phase operational dimensions.

    Precedence: CRITICAL (4) > HIGH (3) > WARNING (2) > INFO (1).
    """
    candidates: list[AlertSeverity] = []

    # Normalize scores if on [0-100] scale
    norm_r_score = (risk_score / 100.0) if (risk_score is not None and risk_score > 1.0) else risk_score
    norm_p_score = (priority_score / 100.0) if (priority_score is not None and priority_score > 1.0) else priority_score

    # 1. Risk Dimension
    norm_risk_level = (risk_level or "").upper()
    if norm_risk_level == "CRITICAL" or (norm_r_score is not None and norm_r_score >= RISK_SCORE_CRITICAL):
        candidates.append(AlertSeverity.CRITICAL)
    elif norm_risk_level == "HIGH" or (norm_r_score is not None and norm_r_score >= RISK_SCORE_HIGH):
        candidates.append(AlertSeverity.HIGH)
    elif norm_risk_level == "MODERATE":
        candidates.append(AlertSeverity.WARNING)

    # 2. Priority Dimension (Impact-Aware)
    norm_prio_level = (priority_level or "").upper()
    if norm_prio_level == "CRITICAL" or (norm_p_score is not None and norm_p_score >= PRIORITY_SCORE_CRITICAL):
        candidates.append(AlertSeverity.CRITICAL)
    elif norm_prio_level == "HIGH" or (norm_p_score is not None and norm_p_score >= PRIORITY_SCORE_HIGH):
        candidates.append(AlertSeverity.HIGH)
    elif norm_prio_level == "MODERATE":
        candidates.append(AlertSeverity.WARNING)

    # 3. Isolation / Network Dimension
    norm_iso_severity = (isolation_severity or "").upper()
    if norm_iso_severity == "CRITICAL":
        candidates.append(AlertSeverity.HIGH)
    elif norm_iso_severity in ("HIGH", "MODERATE"):
        candidates.append(AlertSeverity.WARNING)

    # 4. Ground Intelligence Dimension
    if ground_intelligence_summary:
        trust_class = (ground_intelligence_summary.get("trust_class") or "").upper()
        trust_score = float(ground_intelligence_summary.get("trust_score") or 0.0)
        report_count = int(ground_intelligence_summary.get("report_count") or 1)

        if trust_class == "HIGH" and report_count >= 2 and trust_score >= 80.0:
            candidates.append(AlertSeverity.HIGH)
        elif trust_class in ("HIGH", "MEDIUM") or trust_score >= 50.0:
            candidates.append(AlertSeverity.WARNING)

    if not candidates:
        return AlertSeverity.INFO

    # Select highest precedence
    return max(candidates, key=lambda sev: SEVERITY_PRECEDENCE[sev])
