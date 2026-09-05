"""
Constants, thresholds, enumerations, and limitation templates for Phase 4 Alert Generation & Decision Support.
"""
from enum import Enum


class AlertType(str, Enum):
    HIGH_RISK = "HIGH_RISK"
    CRITICAL_RISK = "CRITICAL_RISK"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    CRITICAL_PRIORITY = "CRITICAL_PRIORITY"
    CONNECTIVITY_DISRUPTION = "CONNECTIVITY_DISRUPTION"
    GROUND_INTELLIGENCE = "GROUND_INTELLIGENCE"
    SOS_EMERGENCY = "SOS_EMERGENCY"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class AlertAuditAction(str, Enum):
    CREATED = "CREATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    DEDUPLICATED = "DEDUPLICATED"


# Numeric precedence for deterministic severity comparison (higher = more severe)
SEVERITY_PRECEDENCE = {
    AlertSeverity.INFO: 1,
    AlertSeverity.WARNING: 2,
    AlertSeverity.HIGH: 3,
    AlertSeverity.CRITICAL: 4,
}

# Risk score trigger thresholds
RISK_SCORE_CRITICAL = 0.70
RISK_SCORE_HIGH = 0.50
RISK_SCORE_MODERATE = 0.30

# Priority score trigger thresholds (from Phase 2C)
PRIORITY_SCORE_CRITICAL = 0.75
PRIORITY_SCORE_HIGH = 0.50

# Ground intelligence trigger thresholds
GROUND_INTEL_MIN_TRUST_CLASS = {"HIGH", "MEDIUM"}
GROUND_INTEL_MIN_TRUST_SCORE = 50.0

# Deduplication configuration
DEDUP_TIME_WINDOW_SECONDS = 21600  # 6 hours
SPATIAL_BUCKET_PRECISION = 3  # ~111m resolution

# Stale data indicators
RAINFALL_MAX_STALENESS_DAYS = 7
GROUND_INTEL_MAX_STALENESS_HOURS = 72

# Version & Disclaimers
CALCULATION_VERSION = "v1.0.0"
STANDARD_SYSTEM_LIMITATION = (
    "Deterministic decision support based on static spatial GIS, topological network analysis, "
    "and recorded observations. Does not constitute a live sensor-based early warning."
)
