"""
Alert trigger rules engine evaluating pre-computed multi-phase intelligence outputs.
"""
from typing import Any

from app.services.alerts.constants import (
    AlertType,
    PRIORITY_SCORE_CRITICAL,
    PRIORITY_SCORE_HIGH,
    RISK_SCORE_CRITICAL,
    RISK_SCORE_HIGH,
)


def evaluate_alert_triggers(
    risk_score: float | None = None,
    risk_level: str | None = None,
    priority_score: float | None = None,
    priority_level: str | None = None,
    isolation_severity: str | None = None,
    ground_intelligence_summary: dict[str, Any] | None = None,
) -> tuple[AlertType, str, str, list[str]]:
    """
    Evaluates inputs against trigger thresholds and returns:
    (primary_alert_type, title, message, trigger_reasons)
    """
    reasons: list[str] = []
    norm_risk = (risk_level or "").upper()
    norm_prio = (priority_level or "").upper()
    norm_iso = (isolation_severity or "").upper()

    norm_r_score = (risk_score / 100.0) if (risk_score is not None and risk_score > 1.0) else risk_score
    norm_p_score = (priority_score / 100.0) if (priority_score is not None and priority_score > 1.0) else priority_score

    is_crit_risk = norm_risk == "CRITICAL" or (norm_r_score is not None and norm_r_score >= RISK_SCORE_CRITICAL)
    is_high_risk = norm_risk == "HIGH" or (norm_r_score is not None and norm_r_score >= RISK_SCORE_HIGH)
    is_crit_prio = norm_prio == "CRITICAL" or (norm_p_score is not None and norm_p_score >= PRIORITY_SCORE_CRITICAL)
    is_high_prio = norm_prio == "HIGH" or (norm_p_score is not None and norm_p_score >= PRIORITY_SCORE_HIGH)
    is_iso_severe = norm_iso in ("CRITICAL", "HIGH", "MODERATE")

    has_ground_intel = False
    if ground_intelligence_summary:
        trust_class = (ground_intelligence_summary.get("trust_class") or "").upper()
        trust_score = float(ground_intelligence_summary.get("trust_score") or 0.0)
        has_ground_intel = trust_class in ("HIGH", "MEDIUM") or trust_score >= 50.0

    if is_crit_risk:
        reasons.append(f"Physical landslide risk score {risk_score or 0.0:.2f} is at CRITICAL threshold")
    elif is_high_risk:
        reasons.append(f"Physical landslide risk score {risk_score or 0.0:.2f} is at HIGH threshold")

    if is_crit_prio:
        reasons.append(f"Operational intervention priority {priority_score or 0.0:.2f} is at CRITICAL threshold")
    elif is_high_prio:
        reasons.append(f"Operational intervention priority {priority_score or 0.0:.2f} is at HIGH threshold")

    if is_iso_severe:
        reasons.append(f"Topological road network analysis indicates {norm_iso} connectivity disruption")

    if has_ground_intel and ground_intelligence_summary:
        tc = ground_intelligence_summary.get("trust_class", "UNKNOWN")
        ts = float(ground_intelligence_summary.get("trust_score", 0.0))
        reasons.append(f"Corroborated ground intelligence report with trust score {ts:.1f} ({tc})")

    # Select primary alert type and draft message
    if is_crit_prio:
        alert_type = AlertType.CRITICAL_PRIORITY
        title = "Critical Operational Intervention Priority"
        message = (
            f"Impact-aware assessment indicates critical intervention urgency (priority score: {priority_score or 0.0:.2f}, "
            f"level: {norm_prio or 'CRITICAL'}) driven by compound population exposure and network criticality."
        )
    elif is_crit_risk:
        alert_type = AlertType.CRITICAL_RISK
        title = "Critical Physical Landslide Hazard"
        message = (
            f"Spatial terrain and rainfall susceptibility assessment indicates critical landslide risk "
            f"(risk score: {risk_score or 0.0:.2f}, level: {norm_risk or 'CRITICAL'})."
        )
    elif is_high_prio:
        alert_type = AlertType.HIGH_PRIORITY
        title = "High Operational Intervention Priority"
        message = (
            f"Impact-aware assessment indicates high intervention priority (priority score: {priority_score or 0.0:.2f}, "
            f"level: {norm_prio or 'HIGH'}) requiring operational review."
        )
    elif is_high_risk:
        alert_type = AlertType.HIGH_RISK
        title = "High Physical Landslide Hazard"
        message = (
            f"Spatial terrain susceptibility assessment indicates elevated landslide hazard "
            f"(risk score: {risk_score or 0.0:.2f}, level: {norm_risk or 'HIGH'})."
        )
    elif is_iso_severe and not has_ground_intel:
        alert_type = AlertType.CONNECTIVITY_DISRUPTION
        title = "Simulated Road Connectivity Disruption"
        message = (
            f"Topological network isolation simulation indicates {norm_iso} connectivity disruption "
            f"and settlement access vulnerability."
        )
    elif has_ground_intel and ground_intelligence_summary:
        alert_type = AlertType.GROUND_INTELLIGENCE
        title = "Corroborated Ground Observation Alert"
        tc = ground_intelligence_summary.get("trust_class", "UNKNOWN")
        ts = float(ground_intelligence_summary.get("trust_score", 0.0))
        message = (
            f"Field ground intelligence submitted by verified observers indicates slope instability or visible hazard "
            f"(trust score: {ts:.1f}, class: {tc})."
        )
    else:
        alert_type = AlertType.HIGH_RISK
        title = "Landslide Operational Advisory"
        message = "Spatial intelligence advisory generated based on current hazard and connectivity parameters."
        reasons.append("General operational advisory threshold met")

    return alert_type, title, message, reasons
