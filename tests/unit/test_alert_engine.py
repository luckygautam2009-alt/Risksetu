"""
Unit tests for Phase 4 Alert Generation & Decision Support Engine.
"""
import uuid
import pytest

from app.core.errors import ConflictError, ValidationAppError
from app.services.alerts.constants import (
    AlertSeverity,
    AlertStatus,
    AlertType,
)
from app.services.alerts.decision_support import (
    generate_explanation_payload,
    generate_recommended_actions,
)
from app.services.alerts.deduplication import compute_alert_fingerprint
from app.services.alerts.engine import (
    generate_operational_alert,
    get_alert_by_id,
    list_alerts,
)
from app.services.alerts.lifecycle import transition_alert_status
from app.services.alerts.severity import determine_alert_severity
from app.services.alerts.triggers import evaluate_alert_triggers


from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password


@pytest.fixture
def db_session():
    """Provides a transactional database session with cleanup."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM alert_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM alerts WHERE 1=1;"))
        db.commit()
        yield db
    finally:
        db.rollback()
        try:
            db.execute(text("DELETE FROM alert_audits WHERE 1=1;"))
            db.execute(text("DELETE FROM alerts WHERE 1=1;"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


@pytest.fixture
def test_user_official(db_session):
    """Creates a temporary official user."""
    user = User(
        id=uuid.uuid4(),
        email=f"official_{uuid.uuid4().hex[:8]}@testrisksetu.com",
        hashed_password=hash_password("OfficialPass123!"),
        full_name="Official User",
        role="official",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ============================================================================
# 1. Severity Determination Tests
# ============================================================================


def test_determine_alert_severity_critical_risk():
    sev = determine_alert_severity(risk_score=0.85, risk_level="CRITICAL")
    assert sev == AlertSeverity.CRITICAL


def test_determine_alert_severity_critical_priority():
    # RISK != PRIORITY: moderate risk with critical priority yields CRITICAL severity
    sev = determine_alert_severity(risk_score=0.35, risk_level="MODERATE", priority_score=0.82, priority_level="CRITICAL")
    assert sev == AlertSeverity.CRITICAL


def test_determine_alert_severity_high_risk():
    sev = determine_alert_severity(risk_score=0.60, risk_level="HIGH")
    assert sev == AlertSeverity.HIGH


def test_determine_alert_severity_high_priority():
    sev = determine_alert_severity(risk_score=0.25, risk_level="LOW", priority_score=0.65, priority_level="HIGH")
    assert sev == AlertSeverity.HIGH


def test_determine_alert_severity_isolation_critical():
    sev = determine_alert_severity(risk_score=0.20, isolation_severity="CRITICAL")
    assert sev == AlertSeverity.HIGH


def test_determine_alert_severity_isolation_high():
    sev = determine_alert_severity(risk_score=0.20, isolation_severity="HIGH")
    assert sev == AlertSeverity.WARNING


def test_determine_alert_severity_ground_intel_high_trust():
    gi = {"trust_class": "HIGH", "trust_score": 85.0, "report_count": 3}
    sev = determine_alert_severity(ground_intelligence_summary=gi)
    assert sev == AlertSeverity.HIGH


def test_determine_alert_severity_ground_intel_moderate_trust():
    gi = {"trust_class": "MEDIUM", "trust_score": 55.0, "report_count": 1}
    sev = determine_alert_severity(ground_intelligence_summary=gi)
    assert sev == AlertSeverity.WARNING


def test_determine_alert_severity_fallback_info():
    sev = determine_alert_severity(risk_score=0.10, risk_level="LOW", priority_score=0.15, priority_level="LOW")
    assert sev == AlertSeverity.INFO


# ============================================================================
# 2. Trigger Evaluation Tests
# ============================================================================

def test_evaluate_alert_triggers_critical_priority():
    alert_type, title, message, reasons = evaluate_alert_triggers(
        risk_score=0.40,
        risk_level="MODERATE",
        priority_score=0.85,
        priority_level="CRITICAL",
        isolation_severity="HIGH",
    )
    assert alert_type == AlertType.CRITICAL_PRIORITY
    assert "Critical Operational Intervention Priority" in title
    assert len(reasons) >= 2


def test_evaluate_alert_triggers_critical_risk():
    alert_type, title, message, reasons = evaluate_alert_triggers(
        risk_score=0.75,
        risk_level="CRITICAL",
    )
    assert alert_type == AlertType.CRITICAL_RISK
    assert "Critical Physical Landslide Hazard" in title


def test_evaluate_alert_triggers_high_priority():
    alert_type, title, message, reasons = evaluate_alert_triggers(
        priority_score=0.60,
        priority_level="HIGH",
    )
    assert alert_type == AlertType.HIGH_PRIORITY


def test_evaluate_alert_triggers_connectivity_disruption():
    alert_type, title, message, reasons = evaluate_alert_triggers(
        isolation_severity="CRITICAL",
    )
    assert alert_type == AlertType.CONNECTIVITY_DISRUPTION
    assert "Simulated Road Connectivity Disruption" in title


def test_evaluate_alert_triggers_ground_intel():
    gi = {"trust_class": "HIGH", "trust_score": 75.0, "report_count": 2}
    alert_type, title, message, reasons = evaluate_alert_triggers(
        ground_intelligence_summary=gi,
    )
    assert alert_type == AlertType.GROUND_INTELLIGENCE
    assert "Corroborated Ground Observation" in title


# ============================================================================
# 3. Fingerprint & Deduplication Tests
# ============================================================================

def test_fingerprint_determinism():
    fp1 = compute_alert_fingerprint("HIGH_RISK", "HIGH", 30.55512, 79.12345, "src-1")
    fp2 = compute_alert_fingerprint("HIGH_RISK", "HIGH", 30.55512, 79.12345, "src-1")
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_spatial_quantization():
    # 30.5551 vs 30.5554 round to 30.555 at 3 decimal places -> same fingerprint
    fp1 = compute_alert_fingerprint("HIGH_RISK", "HIGH", 30.5551, 79.1231, "src-1")
    fp2 = compute_alert_fingerprint("HIGH_RISK", "HIGH", 30.5554, 79.1234, "src-1")
    assert fp1 == fp2


def test_fingerprint_different_alert_types():
    fp1 = compute_alert_fingerprint("HIGH_RISK", "HIGH", 30.555, 79.123)
    fp2 = compute_alert_fingerprint("CRITICAL_RISK", "CRITICAL", 30.555, 79.123)
    assert fp1 != fp2


# ============================================================================
# 4. Decision Support & Explainability Tests
# ============================================================================

def test_generate_recommended_actions_critical():
    actions = generate_recommended_actions(
        alert_type=AlertType.CRITICAL_RISK,
        severity=AlertSeverity.CRITICAL,
        risk_score=0.85,
        isolation_severity="CRITICAL",
    )
    action_ids = [a["action_id"] for a in actions]
    assert "REC_FIELD_VERIFY_URGENT" in action_ids
    assert "REC_RESOURCE_PREPOSITION" in action_ids
    assert "REC_NETWORK_DETOUR_PLAN" in action_ids


def test_generate_recommended_actions_ground_intel():
    gi = {"trust_class": "HIGH", "trust_score": 75.0}
    actions = generate_recommended_actions(
        alert_type=AlertType.GROUND_INTELLIGENCE,
        severity=AlertSeverity.WARNING,
        ground_intelligence_summary=gi,
    )
    action_ids = [a["action_id"] for a in actions]
    assert "REC_GROUND_INTEL_VALIDATE" in action_ids


def test_generate_recommended_actions_routine_fallback():
    actions = generate_recommended_actions(
        alert_type=None,  # type: ignore[arg-type]
        severity=AlertSeverity.INFO,
    )
    assert len(actions) == 1
    assert actions[0]["action_id"] == "REC_ROUTINE_MONITORING"



def test_generate_explanation_payload_with_ground_intel():
    gi = {"trust_class": "HIGH", "trust_score": 88.0}
    expl = generate_explanation_payload(
        alert_type=AlertType.GROUND_INTELLIGENCE,
        severity=AlertSeverity.HIGH,
        reasons=["Corroborated ground intelligence report"],
        ground_intelligence_summary=gi,
        data_freshness={"status": "STALE"},
    )
    assert any("Corroborated Ground Intelligence" in cf for cf in expl["contributing_factors"])
    assert expl["data_freshness_status"] == "STALE"


# ============================================================================
# 5. Lifecycle State Transitions Tests (DB Integrated via pytest-postgresql)
# ============================================================================


def test_alert_lifecycle_transitions(db_session, test_user_official):
    # 1. Create alert directly
    alert, created = generate_operational_alert(
        db=db_session,
        latitude=30.450,
        longitude=79.250,
        risk_score=0.82,
        risk_level="CRITICAL",
        created_by_user_id=test_user_official.id,
    )
    assert created is True
    assert alert.status == AlertStatus.ACTIVE.value

    # 2. Transition ACTIVE -> ACKNOWLEDGED
    ack_alert = transition_alert_status(
        db=db_session,
        alert_id=alert.id,
        target_status=AlertStatus.ACKNOWLEDGED,
        user_id=test_user_official.id,
        reason="Field unit dispatched",
    )
    assert ack_alert.status == AlertStatus.ACKNOWLEDGED.value
    assert ack_alert.acknowledged_at is not None
    assert ack_alert.acknowledged_by == test_user_official.id

    # 3. Transition ACKNOWLEDGED -> RESOLVED
    res_alert = transition_alert_status(
        db=db_session,
        alert_id=alert.id,
        target_status=AlertStatus.RESOLVED,
        user_id=test_user_official.id,
        reason="Culvert cleared and slope secured",
    )
    assert res_alert.status == AlertStatus.RESOLVED.value
    assert res_alert.resolved_at is not None
    assert res_alert.resolved_by == test_user_official.id

    # 4. Terminal state test: RESOLVED -> ACKNOWLEDGED must fail
    with pytest.raises(ConflictError):
        transition_alert_status(
            db=db_session,
            alert_id=alert.id,
            target_status=AlertStatus.ACKNOWLEDGED,
            user_id=test_user_official.id,
        )


def test_alert_lifecycle_invalid_revert(db_session, test_user_official):
    alert, _ = generate_operational_alert(
        db=db_session,
        latitude=30.455,
        longitude=79.255,
        risk_score=0.75,
        created_by_user_id=test_user_official.id,
    )
    transition_alert_status(db_session, alert.id, AlertStatus.ACKNOWLEDGED, test_user_official.id)

    # Reverting ACKNOWLEDGED -> ACTIVE must raise ValidationAppError
    with pytest.raises(ValidationAppError):
        transition_alert_status(db_session, alert.id, AlertStatus.ACTIVE, test_user_official.id)


def test_alert_deduplication_in_engine(db_session, test_user_official):
    # First generation creates alert
    alert1, created1 = generate_operational_alert(
        db=db_session,
        latitude=30.600,
        longitude=79.300,
        risk_score=0.72,
        risk_level="CRITICAL",
        created_by_user_id=test_user_official.id,
    )
    assert created1 is True

    # Immediate second generation at same location returns existing active alert
    alert2, created2 = generate_operational_alert(
        db=db_session,
        latitude=30.600,
        longitude=79.300,
        risk_score=0.72,
        risk_level="CRITICAL",
        created_by_user_id=test_user_official.id,
    )
    assert created2 is False
    assert alert1.id == alert2.id


def test_list_and_get_alerts(db_session, test_user_official):
    alert, _ = generate_operational_alert(
        db=db_session,
        latitude=30.700,
        longitude=79.400,
        priority_score=0.88,
        priority_level="CRITICAL",
        created_by_user_id=test_user_official.id,
    )

    fetched = get_alert_by_id(db_session, alert.id)
    assert fetched is not None
    assert fetched.id == alert.id

    alerts_list, count = list_alerts(db_session, status="ACTIVE", severity="CRITICAL")
    assert count >= 1
    assert any(a.id == alert.id for a in alerts_list)
