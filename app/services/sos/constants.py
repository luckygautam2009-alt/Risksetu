"""
SOS + Shelter module constants.
"""
from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# SOS lifecycle states
# ---------------------------------------------------------------------------
class SOSStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


# Permitted transitions per current status
SOS_VALID_TRANSITIONS: dict[SOSStatus, set[SOSStatus]] = {
    SOSStatus.ACTIVE: {SOSStatus.ACKNOWLEDGED, SOSStatus.RESOLVED, SOSStatus.CANCELLED},
    SOSStatus.ACKNOWLEDGED: {SOSStatus.RESOLVED, SOSStatus.CANCELLED},
    SOSStatus.RESOLVED: set(),
    SOSStatus.CANCELLED: set(),
}

# ---------------------------------------------------------------------------
# SOS severity levels
# ---------------------------------------------------------------------------
class SOSSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# SOS audit actions
# ---------------------------------------------------------------------------
class SOSAuditAction(str, Enum):
    CREATED = "CREATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
    RISK_ASSESSED = "RISK_ASSESSED"
    ALERT_LINKED = "ALERT_LINKED"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    DISPATCH_TRIGGERED = "DISPATCH_TRIGGERED"


# ---------------------------------------------------------------------------
# SOS → alert severity mapping
# Maps SOS severity to the alert severity used when generating a linked alert
# ---------------------------------------------------------------------------
SOS_TO_ALERT_SEVERITY: dict[str, str] = {
    "LOW": "INFO",
    "MEDIUM": "WARNING",
    "HIGH": "HIGH",
    "CRITICAL": "CRITICAL",
}

# Risk thresholds for auto-alerting from SOS
SOS_ALERT_RISK_THRESHOLD = 50.0   # live_risk_score ≥ this → generate alert

# ---------------------------------------------------------------------------
# Shelter service constants
# ---------------------------------------------------------------------------
SHELTER_DEFAULT_RADIUS_M: float = 20_000.0   # 20 km default search radius
SHELTER_MAX_RADIUS_M: float = 100_000.0      # 100 km hard cap
SHELTER_MIN_RADIUS_M: float = 500.0

# Suitability scoring weights — only components with data are used
SUITABILITY_W_DISTANCE: float = 0.50   # distance from requester (lower = better)
SUITABILITY_W_CAPACITY: float = 0.30   # capacity adequacy (only if capacity known)
SUITABILITY_W_ACCESSIBILITY: float = 0.20   # accessibility (only if verified)
# Weights are renormalized if capacity/accessibility unavailable

# Distance decay: full score at 0m, 0 score at SUITABILITY_MAX_DISTANCE_M
SUITABILITY_MAX_DISTANCE_M: float = 50_000.0

MODULE_VERSION = "SOS_SHELTER_V1"
