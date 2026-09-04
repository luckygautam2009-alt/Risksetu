"""
Deterministic decision support recommendation generator and explainability engine.
"""
from typing import Any

from app.services.alerts.constants import AlertSeverity, AlertType, STANDARD_SYSTEM_LIMITATION


def generate_recommended_actions(
    alert_type: AlertType,
    severity: AlertSeverity,
    risk_score: float | None = None,
    priority_score: float | None = None,
    isolation_severity: str | None = None,
    ground_intelligence_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Deterministically generates prioritized, structured action recommendations
    tailored to the operational context of the alert.
    """
    actions: list[dict[str, Any]] = []
    norm_iso = (isolation_severity or "").upper()

    # 1. Immediate Field Verification
    if severity == AlertSeverity.CRITICAL or alert_type in (AlertType.CRITICAL_RISK, AlertType.CRITICAL_PRIORITY):
        actions.append({
            "action_id": "REC_FIELD_VERIFY_URGENT",
            "title": "Immediate On-Site Slope & Road Verification",
            "description": "Deploy engineering and disaster management field teams to inspect identified critical slope sections and road junctions.",
            "urgency": "IMMEDIATE",
            "target_stakeholders": ["District Administration", "Public Works Department (PWD)", "SDRF"],
            "priority_rank": 1,
        })
        actions.append({
            "action_id": "REC_RESOURCE_PREPOSITION",
            "title": "Preposition Heavy Earthmoving & Clearance Equipment",
            "description": "Stage excavators and road clearing machinery at strategic transit junctions near simulated blockage zones.",
            "urgency": "IMMEDIATE",
            "target_stakeholders": ["PWD", "Border Roads Organisation (BRO)"],
            "priority_rank": 2,
        })
    elif severity == AlertSeverity.HIGH or alert_type in (AlertType.HIGH_RISK, AlertType.HIGH_PRIORITY):
        actions.append({
            "action_id": "REC_FIELD_INSPECT_HIGH",
            "title": "Targeted Engineering Slope Inspection",
            "description": "Conduct structural inspection along elevated hazard corridors and vulnerable road embankments.",
            "urgency": "ELEVATED",
            "target_stakeholders": ["PWD", "District Disaster Management Authority (DDMA)"],
            "priority_rank": 1,
        })

    # 2. Connectivity & Road Network Actions
    if norm_iso in ("CRITICAL", "HIGH") or alert_type == AlertType.CONNECTIVITY_DISRUPTION:
        actions.append({
            "action_id": "REC_NETWORK_DETOUR_PLAN",
            "title": "Activate Alternate Route & Detour Logistics",
            "description": "Notify transport authorities to verify viability of backup feeder routes for vulnerable settlements.",
            "urgency": "IMMEDIATE" if norm_iso == "CRITICAL" else "ELEVATED",
            "target_stakeholders": ["Traffic Police", "DDMA", "Transport Department"],
            "priority_rank": len(actions) + 1,
        })

    # 3. Ground Intelligence Verification Actions
    if ground_intelligence_summary or alert_type == AlertType.GROUND_INTELLIGENCE:
        actions.append({
            "action_id": "REC_GROUND_INTEL_VALIDATE",
            "title": "Validate Community Ground Observations",
            "description": "Cross-check submitted citizen observations against satellite imagery and historical landslide inventories.",
            "urgency": "ELEVATED",
            "target_stakeholders": ["Geological Survey Teams", "Local Revenue Officers"],
            "priority_rank": len(actions) + 1,
        })

    # 4. Standard Operational Advisory if no high-urgency actions generated
    if not actions:
        actions.append({
            "action_id": "REC_ROUTINE_MONITORING",
            "title": "Routine Sensor & Precipitation Monitoring",
            "description": "Maintain regular monitoring schedule and update baseline GIS inventories as new observations arrive.",
            "urgency": "ROUTINE",
            "target_stakeholders": ["DDMA", "Municipal Authorities"],
            "priority_rank": 1,
        })

    return actions


def generate_explanation_payload(
    alert_type: AlertType,
    severity: AlertSeverity,
    reasons: list[str],
    risk_score: float | None = None,
    risk_level: str | None = None,
    priority_score: float | None = None,
    priority_level: str | None = None,
    isolation_severity: str | None = None,
    ground_intelligence_summary: dict[str, Any] | None = None,
    data_freshness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Builds an explainable, auditable payload explaining the deterministic rationale,
    contributing factors, confidence indicators, and known limitations.
    """
    contributing_factors = []
    if risk_score is not None:
        contributing_factors.append(f"Physical Hazard Susceptibility: {risk_score:.2f} ({risk_level or 'N/A'})")
    if priority_score is not None:
        contributing_factors.append(f"Operational Intervention Priority: {priority_score:.2f} ({priority_level or 'N/A'})")
    if isolation_severity:
        contributing_factors.append(f"Road Network Isolation Impact: {isolation_severity}")
    if ground_intelligence_summary:
        trust_class = ground_intelligence_summary.get("trust_class", "UNKNOWN")
        trust_score = float(ground_intelligence_summary.get("trust_score", 0.0))
        contributing_factors.append(f"Corroborated Ground Intelligence: Score {trust_score:.1f} ({trust_class})")

    confidence = "HIGH" if (risk_score is not None and priority_score is not None) else "MODERATE"

    return {
        "summary": f"Alert generated as {severity.value} due to {len(reasons)} matching operational criteria.",
        "trigger_reasons": reasons,
        "contributing_factors": contributing_factors,
        "confidence_level": confidence,
        "data_freshness_status": data_freshness.get("status", "VALID") if data_freshness else "VALID",
        "system_limitations": [
            STANDARD_SYSTEM_LIMITATION,
            "Connectivity disruption assessments reflect topological network simulations under hypothetical blockages.",
        ],
    }
