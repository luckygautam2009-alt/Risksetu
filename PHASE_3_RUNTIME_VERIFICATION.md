# PHASE 3 RUNTIME VERIFICATION REPORT
**RISKSETU AI — Ground Intelligence & Trust-Weighted Reporting Engine**
**SIH 2026 PS ID 26001**
**Verification Date:** 2026-09-04

---

## Executive Summary

Phase 3 implementation is **VERIFIED AND CERTIFIED**. All 188 automated tests pass across unit and integration suites. The Ground Intelligence & Trust-Weighted Reporting Engine is fully operational, correctly isolated from certified Phase 0–2C logic, and ready for integration.

---

## Test Suite Results

```
pytest tests/ -v
======================= 188 passed, 3 warnings in 4.13s ========================
```

| Scope | Suite | Tests | Status |
|---|---|---|---|
| Unit | `test_ground_intelligence.py` | 34 | ✅ PASS |
| Integration | `test_ground_reports_api.py` | 8 | ✅ PASS |
| Regression | All Phase 0–2C suites | 146 | ✅ PASS |

---

## Phase 3 Components Verified

### 3.1 Domain Models

| Component | File | Status |
|---|---|---|
| `User` ORM model | `app/models/user.py` | ✅ |
| `GroundReport` ORM model | `app/models/ground_report.py` | ✅ |
| `GroundReportAudit` ORM model | `app/models/ground_report.py` | ✅ |
| `idempotency_key` column + partial unique index | `app/models/ground_report.py` | ✅ |

### 3.2 Database Schema

| Migration | Description | Status |
|---|---|---|
| `0002_phase3_ground_reports` | `users`, `ground_reports`, `ground_report_audits` tables | ✅ Applied |
| `0003_gr_idempotency` | `idempotency_key` column + `uix_ground_reports_user_idempotency` partial index | ✅ Applied |

### 3.3 Ground Intelligence Services

| Service | File | Behaviour Verified |
|---|---|---|
| `GroundReportValidator` | `validation.py` | Coordinate bounds, time range, description length |
| `GeoPlausibilityEvaluator` | `geo_plausibility.py` | Proximity to GSI landslides & OSM road network |
| `TimeDecayEvaluator` | `time_decay.py` | Exponential decay with 7-day half-life |
| `UserReliabilityEvaluator` | `user_reliability.py` | Role-based baseline + historical accuracy |
| `ReportDeduplicator` | `deduplication.py` | Spatial-temporal-textual deduplication |
| `CorroborationEvaluator` | `corroboration.py` | Multi-observer independent spatial convergence |
| `TrustScoringEngine` | `trust.py` | Weighted composite formula |
| `TrustClassifier` | `classification.py` | Deterministic tier classification |
| `RiskEligibilityEvaluator` | `eligibility.py` | Feature-flag gated automated risk eligibility |
| `GroundIntelligenceExplanationGenerator` | `explanation.py` | Audit-defensible plain-text explanation |
| `GroundIntelligenceEngine` | `engine.py` | End-to-end coordinator pipeline |
| `GroundIntelligenceRiskAdapter` | `adapter.py` | Strictly gated read-only adapter for Phase 2A |

### 3.4 Trust Score Formula

```
trust_score = (0.25 × geo_plausibility)
            + (0.20 × temporal_freshness)
            + (0.25 × user_reliability)
            + (0.30 × corroboration)
```

All components clamped [0.0, 100.0]. Final score clamped [0.0, 100.0].

| Trust Class | Threshold |
|---|---|
| `LOW` | score < 40 |
| `MODERATE` | 40 ≤ score < 60 |
| `HIGH` | 60 ≤ score < 80 |
| `VERY_HIGH` | score ≥ 80 |

### 3.5 API Endpoints

| Endpoint | Method | Auth | Verified Behaviour |
|---|---|---|---|
| `/api/v1/auth/register` | POST | None | Creates user, returns JWT |
| `/api/v1/auth/login` | POST | None | Returns JWT, rejects bad credentials |
| `/api/v1/ground-reports` | POST | Bearer (any role) | Submit report, full trust evaluation |
| `/api/v1/ground-reports` | GET | Bearer (any role) | Paginated list with filters |
| `/api/v1/ground-reports/{id}` | GET | Bearer (any role) | Single report retrieval |
| `/api/v1/ground-reports/{id}/status` | PATCH | Bearer (official/admin) | RBAC-gated status moderation |
| `/api/v1/ground-reports/{id}/recalculate-trust` | POST | Bearer (any role) | Re-runs trust pipeline for stale reports |

### 3.6 Idempotency (Redis + DB Dual-Layer)

Idempotency now has two layers:

1. **Redis (fast path):** `idempotency:report:{user_id}:{key}` → 24h TTL
2. **Database fallback:** `ground_reports WHERE user_id = ? AND idempotency_key = ?` via partial unique index `uix_ground_reports_user_idempotency`

Verified: identical request with same `Idempotency-Key` header returns the same `report_id` even when Redis is unavailable (confirmed in integration test `test_idempotency_key_replay`).

### 3.7 Rate Limiting

Redis-backed sliding window per user. **Fail-open policy** — Redis unavailability emits a `WARNING` log but does NOT block submission. Verified in all integration tests (Redis connection refused, all tests pass).

### 3.8 Security Invariants

| Invariant | Status |
|---|---|
| JWT authentication required for all ground report endpoints | ✅ |
| RBAC enforced: status moderation restricted to `official`/`admin` | ✅ |
| Passwords hashed with Argon2 | ✅ |
| Sensitive fields redacted from structured logs | ✅ |

---

## Phase Isolation — Certified Regression

> **CRITICAL PRINCIPLE:** A ground report MUST NOT automatically become trusted risk intelligence.

| Invariant | Mechanism | Verified |
|---|---|---|
| `ENABLE_GROUND_REPORT_RISK_INFLUENCE = False` | Feature flag in `adapter.py` | ✅ |
| Phase 1B tables are read-only from Phase 3 | Geo-plausibility reads only; no writes | ✅ |
| `road_network_edges` count unchanged after ground report operations | `test_database_immutability_of_prior_phases` | ✅ |
| `road_network_nodes` count unchanged | `test_database_immutability_of_prior_phases` | ✅ |
| `historical_landslides` count unchanged | `test_database_immutability_of_prior_phases` | ✅ |
| Phase 2A risk scores not modified | No writes to `risk_assessments` from Phase 3 | ✅ |

---

## Known Limitations (By Design)

> These limitations are documented explicitly as required by the Phase 3 specification.

1. **Ground reports are NOT verified truth.** Trust scores are probabilistic estimates based on spatial context, temporal freshness, user history, and peer corroboration — NOT confirmed field verification.
2. **Automated risk influence is disabled.** `ENABLE_GROUND_REPORT_RISK_INFLUENCE = False` must be explicitly changed by an authorised administrator to enable Phase 3 data influencing Phase 2A risk scores. This requires a dedicated risk integration review.
3. **Idempotency requires Redis for sub-millisecond performance at scale.** The DB fallback is correct but slower under high concurrency.
4. **User reliability scores bootstrap at baseline values.** New users start at `50.0` (citizens) / `70.0` (officials). Longitudinal accuracy data improves scores over time.
5. **Corroboration window is fixed at ±24 hours within 2km radius.** Reports outside this window do not contribute to corroboration regardless of physical proximity.
6. **No real-time push notifications.** Trust recalculation is on-demand via `POST /recalculate-trust`, not automatic on peer report submission.

---

## Defects Found and Resolved During Verification

| Defect | Root Cause | Fix |
|---|---|---|
| `ProgrammingError: function st_cast(geometry, unknown) does not exist` | `func.ST_Cast(..., "geography")` emits a string literal type that PostgreSQL rejects for geography cast | Replaced all 6 occurrences across `adapter.py`, `geo_plausibility.py`, `deduplication.py`, `corroboration.py` with `cast(..., Geography)` from `geoalchemy2` |
| `422 Unprocessable Entity` on second report in corroboration/duplicate tests | `observed_at = now + timedelta(hours=1)` exceeded the 5-minute future timestamp guard | Changed to `now - timedelta(hours=1)` / `now - timedelta(minutes=15)` |
| Idempotency replay fails when Redis unavailable | Idempotency was Redis-only; cache read/write both fail-open silently, creating duplicate DB rows | Added `idempotency_key` column to `ground_reports`, DB-level partial unique index `(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL`, and DB fallback lookup in the POST handler |

---

## Certification

```
Phase 3: Ground Intelligence & Trust-Weighted Reporting Engine
Status:  CERTIFIED ✅
Tests:   188/188 passed
Date:    2026-09-04
```

All prior phase certifications (Phase 0, 1B, 2A, 2B, 2C) remain intact and unmodified.
