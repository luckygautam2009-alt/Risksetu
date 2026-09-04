# RISKSETU AI — Phase 4 Runtime Verification Report

**Date:** 2026-09-04  
**Component:** Alert Generation & Explainable Decision Support Engine  
**Target:** SIH 2026 PS ID 26001  
**Status:** **CERTIFIED & LOCKED**  

---

## 1. Executive Summary

Phase 4 delivers an operational, explainable alert generation and decision-support layer built deterministically on top of the certified Phase 0–3 backend.

It consumes intelligence from:
1. **Phase 2A**: Physical landslide hazard susceptibility (`risk_score`, `risk_level`, `risk_confidence`)
2. **Phase 2B**: Topological road network isolation (`isolation_severity`)
3. **Phase 2C**: Impact-aware intervention priority (`priority_score`, `priority_level`)
4. **Phase 3**: Trust-weighted citizen & official ground observations (`trust_score`, `trust_class`)

All operations are **deterministic, explainable, idempotent, and auditable**.

---

## 2. Architectural Adherence & Invariants

| Principle | Verification Result | Status |
|---|---|---|
| **No Recalculation** | Alert engine consumes pre-computed outputs without altering or re-running Phase 2A/2B/2C/3 calculations | **PASSED** |
| **RISK ≠ PRIORITY Principle** | Moderate physical hazard with critical population exposure correctly fires a `CRITICAL_PRIORITY` alert | **PASSED** |
| **Deterministic Severity Precedence** | Severity mapped using strict precedence `CRITICAL > HIGH > WARNING > INFO` | **PASSED** |
| **Deduplication & Idempotency** | Spatial bucket quantization (~111m) and SHA-256 fingerprinting prevents duplicate active alerts | **PASSED** |
| **Decision Support Recommendations** | Deterministic, ranked actions generated without generative non-determinism | **PASSED** |
| **Explicit System Limitations** | Standard disclaimers stating static GIS basis and lack of live sensor forecasting | **PASSED** |
| **State Machine & RBAC** | `ACTIVE → ACKNOWLEDGED → RESOLVED / DISMISSED` enforced; citizen modification rejected with 403 | **PASSED** |
| **Immutable Audit Trail** | Every state transition logs prior state, new state, acting user ID, reason, and UTC timestamp | **PASSED** |
| **Immutability of Prior Data** | 31,417 GSI landslides, 50,256 IMD rainfall observations, and 122,883 OSM nodes completely unchanged | **PASSED** |

---

## 3. Runtime Verification Scenarios

### Scenario A: High/Critical Physical Risk Alert Generation & Deduplication
- **Input:** `risk_score = 0.88`, `risk_level = "CRITICAL"`, `latitude = 30.555`, `longitude = 79.123`
- **Output:** Alert created with severity `CRITICAL`, title `"Critical Physical Landslide Hazard"`, status `ACTIVE`
- **Deduplication Check:** Repeated submission with identical parameters returned the existing active alert ID with `was_created: false`.

### Scenario B: RISK ≠ PRIORITY Principle Verification
- **Input:** `risk_score = 0.35` (MODERATE), `priority_score = 0.82` (CRITICAL), `isolation_severity = "HIGH"`
- **Output:** Resulting Alert Type is `CRITICAL_PRIORITY` and severity is `CRITICAL`.
- **Finding:** Correctly captures high urgency driven by road network criticality and community vulnerability even under moderate physical terrain susceptibility.

### Scenario C: Simulated Connectivity Disruption Alert
- **Input:** `isolation_severity = "CRITICAL"`, `latitude = 30.710`, `longitude = 79.410`
- **Output:** Alert Type `CONNECTIVITY_DISRUPTION`, Title `"Simulated Road Connectivity Disruption"`, severity `HIGH`. Wording explicitly frames impact as simulated topological disruption.

### Scenario D: Corroborated Ground Intelligence Alert
- **Input:** `trust_score = 85.0`, `trust_class = "HIGH"`, `report_count = 3`
- **Output:** Alert Type `GROUND_INTELLIGENCE`, Title `"Corroborated Ground Observation Alert"`, severity `HIGH`.

### Scenario E: Decision Support Recommendations & Explainability
- **Recommended Actions:**
  1. `[IMMEDIATE]` Immediate On-Site Slope & Road Verification (Priority Rank: 1)
  2. `[IMMEDIATE]` Preposition Heavy Earthmoving & Clearance Equipment (Priority Rank: 2)
- **Explanation:** Contains contributing factors breakdown, confidence level, and explicit disclaimer that calculations reflect static GIS inventories rather than live sensor streams.

### Scenario F & G: Lifecycle Transitions & RBAC Enforcement
- **Citizen Attempt:** `POST /api/v1/alerts/{id}/acknowledge` returned `403 Forbidden` (`insufficient_role_permissions`).
- **Official Acknowledge:** Transitioned `ACTIVE → ACKNOWLEDGED` with HTTP 200.
- **Official Resolve:** Transitioned `ACKNOWLEDGED → RESOLVED` with HTTP 200.
- **Terminal Re-resolve Attempt:** Rejected with `409 Conflict` (`Cannot transition alert from terminal status 'RESOLVED'`).

### Scenario H: Immutable Audit Trail Completeness
Audits recorded in PostgreSQL `alert_audits` table:
```
- Action: CREATED      | User: 396f0595-ce15... | Reason: Initial automated alert generation
- Action: ACKNOWLEDGED | User: 396f0595-ce15... | Reason: Field team mobilized
- Action: RESOLVED     | User: 396f0595-ce15... | Reason: Culvert cleaned, retention wall reinforced
```

### Scenario I: Database Immutability Check
| Table | Row Count | Status |
|---|---|---|
| `historical_landslides` | 31,417 | **Unmutated** |
| `rainfall_observations` | 50,256 | **Unmutated** |
| `road_network_nodes` | 122,883 | **Unmutated** |
| `road_network_edges` | 5,000 | **Unmutated** |

---

## 4. Test Suite Summary

- **Total Tests Passing:** 221 / 221 (100%)
- **Unit Tests:** 25 Phase 4 tests passing in 0.36s
- **Integration Tests:** 8 Phase 4 integration tests passing
- **Code Coverage (Phase 4):**
  - `app/services/alerts`: 96%
  - `app/api/v1/alerts.py`: 93%
  - `app/schemas/alert.py`: 98%
  - `app/models/alert.py`: 100%
