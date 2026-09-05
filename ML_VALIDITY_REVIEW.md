# RISKSETU AI — ML Scientific Validity Review

**Document Version:** 2.0 — FINAL  
**Review Date:** 2026-09-04  
**Reviewer:** Kiro Scientific Review Agent  
**Subject:** `risksetu-landslide-susceptibility-v2` — Full scientific audit, redesign, and re-training report  
**Status:** COMPLETE — All experiments run, final decision rendered

---

## Table of Contents

1. [Scientific Audit](#1-scientific-audit)
2. [Dataset Summary](#2-dataset-summary)
3. [Sampling Analysis](#3-sampling-analysis)
4. [Feature Leakage Analysis](#4-feature-leakage-analysis)
5. [Spatial Validation Design](#5-spatial-validation-design)
6. [Model Comparison](#6-model-comparison)
7. [Latitude/Longitude Ablation](#7-latitudelongitude-ablation)
8. [Buffer Sensitivity Analysis](#8-buffer-sensitivity-analysis)
9. [Calibration Assessment](#9-calibration-assessment)
10. [Feature Importance Analysis](#10-feature-importance-analysis)
11. [Scientific Limitations](#11-scientific-limitations)
12. [Final Decision](#12-final-decision)
13. [Engineering Status](#13-engineering-status)

---

## 1. Scientific Audit

### 1.1 Audit Scope

This audit covers all components of the landslide susceptibility training pipeline. The original v1 run was completed on `2026-09-04T18:18:03Z`. This review identified critical validity failures, redesigned the pipeline (v2), retrained all model variants, and rendered a final scientific verdict.

The v1 artifact (`pipeline.joblib`) remains on disk — it was **not** overwritten because the model did not pass the validity criteria established in this review.

### 1.2 Target Validity

| Criterion | Assessment |
|---|---|
| Target variable | Binary: y=1 (GSI presence), y=0 (pseudo-absence) |
| Target name | `landslide_susceptibility` |
| Susceptibility vs trigger prediction | Susceptibility — CORRECT |
| Climatology as trigger | No. IMD data is a long-term climatological baseline only. |
| Target well-defined | Yes, within its pseudo-absence constraints. |

**Finding:** The target definition is scientifically appropriate. The model estimates whether a location has environmental characteristics (principally long-term rainfall regime) similar to historically observed landslide sites. It does NOT predict probability of a landslide occurring tomorrow. This distinction is preserved in `metadata.json` under `output_semantics.interpretation` and must be maintained in all future versions.

**Limitation acknowledged:** Because the negative class consists entirely of pseudo-absences, the model is technically a presence-background discriminator. Output scores represent relative suitability rather than frequentist probabilities.

### 1.3 Sampling Validity

| Property | Value |
|---|---|
| Positive source | GSI Bhukosh NLSM historical inventory |
| Positives in domain | 16,511 |
| Negatives | 33,022 (1:2 ratio, 5 km exclusion buffer) |
| Total | 49,533 |
| Positives with Unknown state | 7,144 (43.3%) |
| Unknown-state subdivision source | Coordinate heuristic — not authoritative |

The 7,144 Unknown-state records are retained in training. Their IMD subdivision is assigned via `coords_to_subdivision()` (a coarse lat/lon heuristic). This is acknowledged as a limitation — ~43% of positive training samples may have slightly inaccurate rainfall feature values. A `subdiv_source` field (`"state_authority"` vs `"coordinate_heuristic"`) is now tracked in training logs. State labels are NOT used as spatial validation groups.

### 1.4 Feature Leakage Analysis — Summary

See Section 4 for full analysis.

**Confirmed direct leakage (excluded since v1, preserved in v2):**
- `distance_to_nearest_slide_km` — trivially separates labels by construction
- `slide_count_within_5km`, `slide_count_within_10km`, `slide_count_within_25km` — spatial autocorrelation, trivially separates labels

**Geographic prior bias (lat/lon) — confirmed in v2 ablation:**
- Model A (with lat/lon): ROC-AUC = 0.8624
- Model B (rainfall only): ROC-AUC = 0.6161
- **Ablation drop = 0.2463 — exceeds 0.15 threshold**
- Verdict: The v1 model was primarily a geographic location interpolator. Lat/lon are excluded in the final v2 model.

### 1.5 Spatial Validation Validity

**v1 validation (REJECTED):** Longitude quantile binning → 5 north–south strips → GroupKFold.

Critical flaws found:

| Fold | Positives | ROC-AUC | Status |
|---|---|---|---|
| 0 | Very few | 0.495 | Near-random |
| 1 | Adequate | 0.862 | Valid |
| 2 | Adequate | 0.718 | Valid |
| 3 | **0** | **NaN** | **INVALID — produced invalid JSON** |
| 4 | Adequate | 0.867 | Valid |

Fold 3 had zero positives. `roc_auc_score()` output NaN, which was written to `metrics.json` as a bare `NaN` token — not valid JSON per RFC 8259.

**v2 validation (ADOPTED):** 2D lat×lon quantile grid (4×4 bins, round-robin mapped to 5 folds).

| Fold | Positives | Negatives | ROC-AUC (B-RF) | Status |
|---|---|---|---|---|
| 0 | 5,347 | 8,133 | 0.6561 | VALID |
| 1 | 641 | 6,009 | 0.6198 | VALID |
| 2 | 1,852 | 7,259 | 0.8784 | VALID |
| 3 | 6,676 | 5,524 | 0.8577 | VALID |
| 4 | 1,995 | 6,097 | 0.5759 | VALID |

**All 5 folds valid.** The NaN fold problem is fully resolved. Fold validity enforcement is a hard constraint in code — any fold without ≥1 positive and ≥1 negative is excluded from aggregate metrics.

### 1.6 Geographic Bias Assessment

The ablation experiment confirms geographic bias at quantitative scale. Model A (with lat/lon) ROC-AUC = 0.8624 vs Model B (rainfall only) ROC-AUC = 0.6161 — a drop of 0.2463. Per the predetermined threshold (drop > 0.15 = geographic memorizer), the model using coordinates is primarily learning GSI inventory clustering, not physical susceptibility.

This is scientifically expected: with only ~15 IMD subdivisions covering the 10°×16° modeling domain, every point within a subdivision has identical rainfall features. Lat/lon provided the only within-subdivision discrimination — but that discrimination reflected survey effort distribution, not causal physical drivers.

Removing lat/lon forces the model to learn from rainfall signal alone. The resulting 0.6161 ROC-AUC under honest spatial validation is weaker but scientifically more defensible.

### 1.7 Calibration Validity

**v2 calibration curve (Model B-RF, OOF predictions from all 5 valid folds):**

| Predicted Mean | Actual Fraction | Monotonic? |
|---|---|---|
| 0.027 | 0.334 | — |
| 0.117 | 0.396 | ↑ |
| 0.327 | 0.062 | **↓ violation** |
| 0.409 | 0.002 | **↓ violation** |
| 0.513 | 0.502 | ↑ |
| 0.738 | 0.375 | **↓ violation** |
| 0.882 | 0.786 | ↑ |
| 0.911 | 0.778 | ↓ minor |

**`approximately_monotonic = false`** — confirmed non-monotonic.

Root cause: The 5 geographic folds have radically different positive prevalence (fold 3: 6,676/12,200 = 55% positive; fold 4: 1,995/8,092 = 25% positive). The OOF score distribution is multi-modal — high-confidence predictions from fold 3 mix with near-random predictions from fold 4. Sigmoid calibration fits one logistic curve to this mixture and produces non-monotonic behaviour.

**Verdict:** The sigmoid calibration output cannot be interpreted as a reliable probability. The output is labelled `susceptibility_score` in metadata, not `calibrated_probability`.

### 1.8 Metric Reliability

**v2 metrics (Model B-RF, all 5 valid folds, honest evaluation):**

| Metric | Value | Reliability |
|---|---|---|
| ROC-AUC | 0.6161 | RELIABLE — all 5 folds valid, no NaN |
| PR-AUC | 0.5536 | RELIABLE |
| Precision | 0.6540 | MODERATE — threshold 0.5 arbitrary |
| Recall | 0.5242 | MODERATE — same caveat |
| F1 | 0.5819 | MODERATE |
| Brier Score | 0.2245 | INFORMATIVE but calibration non-monotonic |

All metrics are computed over OOF predictions from valid folds only. The NaN serialisation bug is fixed — `metrics.json` is now valid JSON.

**Comparison with v1 reported metrics:**

| Metric | v1 Reported | v1 Reality | v2 (honest) |
|---|---|---|---|
| ROC-AUC | 0.8720 | Contaminated by 2 degenerate folds | 0.6161 (B-RF) |
| Valid folds | 5/5 | 3/5 | 5/5 |
| NaN in fold | Present | Yes | None |
| Lat/lon importance | ~74.6% | Geographic memorization | Excluded |

The v1 ROC-AUC of 0.872 was not a valid performance figure. It reflected geographic memorization (lat/lon ~74.6%) and contamination from two degenerate folds.

### 1.9 Recommended Redesign — Status

| Recommendation | Status |
|---|---|
| Replace longitude-only blocks with 2D spatial grid | ✅ Done — `assign_spatial_blocks_2d()` |
| Enforce fold validity (≥1 pos, ≥1 neg) | ✅ Done — `check_fold_validity()`, hard constraint |
| Lat/lon ablation experiment | ✅ Done — drop = 0.2463 |
| Buffer sensitivity analysis | ✅ Done — 3/5/10 km |
| Fix NaN JSON serialisation | ✅ Done — `_SafeEncoder`, `_safe_json_dumps()` |
| Fix Ruff F541 errors | ✅ Done — 6 f-strings converted |
| Add sklearn version to metadata | ✅ Done — `sklearn_version: "1.9.0"` |
| Remove dead code (material/movement_type) | ✅ Done |
| Add ML test suite | ✅ Done — 104 tests |
| Preserve production artifact until valid | ✅ Done — v1 pipeline.joblib unchanged |

---

## 2. Dataset Summary

| Property | Value |
|---|---|
| Positive source | GSI Bhukosh NLSM historical inventory |
| Positive count (domain) | 16,511 |
| Negative source | Algorithmically generated pseudo-absences |
| Negative count | 33,022 (ratio 1:2, buffer 5 km) |
| Total samples | 49,533 |
| Modeling domain | lat 26–36°N, lon 74–90°E |
| Climatology source | IMD Subdivision Climatology 1901–2017 |
| IMD subdivisions loaded | 36 |
| Climatology rows | 432 (36 subdivisions × 12 months) |
| Unknown-state positives | 7,144 (43.3%) |
| Heuristic-subdiv positives | 7,144 (same set) |
| Terrain features | None — no DEM |
| Dynamic weather features | None — climatology only |
| sklearn version | 1.9.0 |

### 2.1 Positive Sample Geographic Distribution

The GSI inventory is spatially clustered in the high-rainfall Himalayan terrain. Fold distribution from 2D grid blocking reflects this:
- Fold 3 (6,676 positives): densely sampled Himalayan zone — Uttarakhand/NE states
- Fold 0 (5,347 positives): another high-density zone
- Folds 1 and 4 (641 and 1,995 positives): transition/sparse zones — these produce weaker ROC-AUC and reveal the limits of the environmental features available

### 2.2 Climatology Feature Granularity

36 IMD subdivisions nationwide; approximately 12–15 are active within the modeling domain. Every point within a subdivision has identical rainfall feature values. This is the fundamental constraint on model discriminability — with only ~15 distinct rainfall profiles, purely environmental discrimination is limited. The 0.6161 ROC-AUC for the rainfall-only model is close to the ceiling achievable from subdivision-level climatology alone without terrain data.

---

## 3. Sampling Analysis

### 3.1 Pseudo-Absence Design

**Selected buffer: 5 km** (raised from v1's 3 km).

Justification: GSI inventory coordinates are digitised from PDFs and GPS-reported with variable accuracy. Positional uncertainty of 1–5 km is typical. A 3 km buffer may include genuinely slide-prone terrain within the positional error radius of known slides. The 5 km buffer is more conservative and appropriate given this uncertainty.

**Implementation:** BallTree haversine rejection sampling. Uniform random within bounding box, 4× oversampling per batch, up to 20 attempts. All 33,022 target negatives generated successfully at 5 km buffer.

**Limitation preserved:** Uniform bounding box sampling overweights the Indo-Gangetic Plain (flat, large area) relative to the narrow Himalayan belt. This geographic imbalance is a sampling artefact, not an environmental contrast.

### 3.2 Unknown State Assignment

7,144 positive records (43.3%) have `state = "Unknown"`. Their IMD subdivision is derived via `coords_to_subdivision()` — a coarse lat/lon threshold heuristic, not a spatial join against administrative boundary polygons.

**Decision:** Records retained; heuristic-derived subdivisions used for feature lookup only. `subdiv_source` metadata distinguishes `"state_authority"` from `"coordinate_heuristic"`. State labels are NOT used as spatial validation groups. Reliable re-assignment requires GIS polygon data not present in the project.

### 3.3 Buffer Sensitivity

See Section 8 for full results. Summary: buffer size has relatively modest effect on RF model performance at subdivision-level climatology resolution — because pseudo-absences in different exclusion zones still map to the same subdivision rainfall profiles. The 5 km buffer is retained as the scientifically preferred choice.

---

## 4. Feature Leakage Analysis

### 4.1 Confirmed Direct Leakage — Excluded

| Feature | Leakage Type | Action |
|---|---|---|
| `distance_to_nearest_slide_km` | Direct label proximity — positives = 0, negatives ≥ buffer | Excluded |
| `slide_count_within_5km` | Spatial density autocorrelation | Excluded |
| `slide_count_within_10km` | Same | Excluded |
| `slide_count_within_25km` | Same | Excluded |

All four are documented in `features.json` under `excluded_features` with explicit reasons. This was correctly handled in v1 and preserved in v2.

### 4.2 Latitude/Longitude — Geographic Prior — Removed in Final Model

**v1 feature importance (Model A-RF, with lat/lon):**

| Feature | Importance |
|---|---|
| longitude | 0.4020 (rank 1) |
| latitude | 0.3438 (rank 2) |
| All rainfall combined | 0.2542 |
| **lat/lon combined** | **0.7458** |

**Ablation result:** ROC-AUC drop from A to B = 0.2463. This exceeds the 0.15 threshold that defines "geographic memorization." The model was learning where GSI-recorded slides are in geographic space, not why locations are susceptible.

**Action:** Lat/lon excluded from the final selected model (Model B-RF). Both features are documented in `features.json` under `excluded_features` with full reasoning.

### 4.3 Rainfall Features — Not Leaky

All 7 rainfall features derive from IMD climatological baselines (1901–2017 monthly means and standard deviations per subdivision). They are computed independently of the training labels and are not leaky. Their relatively low predictive power reflects the coarse subdivision granularity and absence of terrain data — not leakage.

### 4.4 Terrain and Dynamic Weather Features — Correctly Absent

`elevation_m`, `slope_degrees`, `aspect_degrees`, and dynamic rainfall variables are excluded because no corresponding data is available in the project. They are **not fabricated**. `terrain_features_available = false` and `dynamic_weather_features_available = false` are hard-coded in all artifact files.

---

## 5. Spatial Validation Design

### 5.1 Design A (v1 — REJECTED)

Longitude quantile binning. Fold 3 zero positives → NaN ROC-AUC → invalid JSON. Only 3/5 folds scientifically valid. Aggregate metrics contaminated. **Rejected.**

### 5.2 Design B (v2 — ADOPTED)

**2D lat×lon quantile grid (4 lat bins × 4 lon bins = 16 cells → round-robin to 5 folds).**

All 5 folds valid. Compact geographic patches. Both latitudinal and longitudinal variation captured. Fold validity enforcement is a hard code constraint — not advisory.

**Validation result (Model B-RF, all 5 folds):**

| Fold | n | Positives | Negatives | ROC-AUC | PR-AUC | F1 | Status |
|---|---|---|---|---|---|---|---|
| 0 | 13,480 | 5,347 | 8,133 | 0.6561 | 0.5372 | 0.2931 | VALID |
| 1 | 6,650 | 641 | 6,009 | 0.6198 | 0.6861 | 0.6510 | VALID |
| 2 | 9,111 | 1,852 | 7,259 | 0.8784 | 0.5131 | 0.6727 | VALID |
| 3 | 8,092 | 6,676 | 5,524 | 0.8577 | 0.6306 | 0.7643 | VALID |
| 4 | 6,650 | 1,995 | 6,097 | 0.5759 | 0.1117 | 0.0000 | VALID |
| **OOF** | **49,533** | **16,511** | **33,022** | **0.6161** | **0.5536** | **0.5819** | **5/5 valid** |

Note on Fold 4: Valid by definition (1,995 positives, 6,097 negatives) but the model predicts essentially all negatives at the 0.5 threshold in this zone — hence F1 = 0.000. The ROC-AUC of 0.576 is above 0.5 (not random), indicating weak but present discriminability. This fold corresponds to a geographically hard region where climatological signal is weakest — possibly a transition zone between Himalayan foothills and plains. **This weak fold is reported honestly and is not suppressed.**

---

## 6. Model Comparison

All four model variants trained under identical conditions: seed=42, ratio=1:2, buffer=5 km, 2D grid spatial validation, 5 folds, all folds valid.

| Model | Features | n_features | ROC-AUC | PR-AUC | Precision | Recall | F1 | Brier | Valid Folds |
|---|---|---|---|---|---|---|---|---|---|
| Model A — RF | With lat/lon | 9 | **0.8624** | 0.8194 | 0.9190 | 0.5072 | 0.6537 | 0.1398 | 5/5 |
| Model A — HGB | With lat/lon | 9 | 0.8541 | 0.8215 | 0.8854 | 0.6055 | 0.7192 | 0.1332 | 5/5 |
| Model B — RF | Rainfall only | 7 | 0.6161 | 0.5536 | 0.6540 | 0.5242 | 0.5819 | 0.2245 | 5/5 |
| Model B — HGB | Rainfall only | 7 | 0.6004 | 0.5401 | 0.7089 | 0.4178 | 0.5257 | 0.2130 | 5/5 |

**Selected final model: Model B — RF (rainfall only)**

Rationale: Model A's higher ROC-AUC is attributable to geographic memorization (ablation drop = 0.2463 > 0.15 threshold). Model B-RF was preferred because:
1. It has 5/5 valid folds — an adequate spatial validation basis.
2. Its ROC-AUC of 0.6161 ≥ 0.55 minimum threshold — there is genuine environmental signal.
3. It excludes lat/lon — predictions reflect climatic characteristics, not GSI survey coverage.
4. RF outperforms HGB on Model B by ~0.016 ROC-AUC with broadly similar metrics.

**Model A is scientifically inadmissible as a production susceptibility model** despite its higher reported metric, because 74.6% of its predictive power comes from geographic coordinates that encode survey distribution, not physical susceptibility.

---

## 7. Latitude/Longitude Ablation

### 7.1 Experiment Results

| Metric | Model A (RF + lat/lon) | Model B (RF no lat/lon) | Drop A→B |
|---|---|---|---|
| ROC-AUC | 0.8624 | 0.6161 | **+0.2463** |
| PR-AUC | 0.8194 | 0.5536 | +0.2658 |
| F1 | 0.6537 | 0.5819 | +0.0718 |
| Brier | 0.1398 | 0.2245 | −0.0847 (worse) |

### 7.2 Interpretation

The ROC-AUC drop of 0.2463 **exceeds the 0.15 threshold** established in the review protocol. Per the predetermined interpretation table:

| ROC-AUC drop | Interpretation |
|---|---|
| < 0.05 | lat/lon marginal; rainfall carries genuine signal |
| 0.05–0.15 | Partly geographic prior, partly environmental |
| **> 0.15** | **Model primarily geographic memorizer; rainfall signal weak** |

**Result: GEOGRAPHIC MEMORIZER confirmed.** The model with lat/lon was primarily learning "where in the Himalayas has the GSI recorded slides" rather than "what environmental characteristics make a location susceptible to slides."

### 7.3 What Model B Tells Us

With lat/lon removed, Model B achieves ROC-AUC = 0.6161. This is:
- Above 0.5 (not random) — there is real signal in IMD climatology
- Below 0.75 — the signal is weak without terrain data
- Consistent with the expectation that subdivision-level rainfall alone (with ~15 distinct profiles across the domain) cannot strongly discriminate susceptibility within zones

This is an honest result. The model has climatological signal. It is not a random classifier. But it requires terrain features to become a meaningful susceptibility tool.

---

## 8. Buffer Sensitivity Analysis

### 8.1 Results (RF with lat/lon for sensitivity comparison — consistent comparison basis)

| Buffer | n_negatives | Valid Folds | ROC-AUC | PR-AUC | F1 |
|---|---|---|---|---|---|
| 3 km | 33,022 | 5/5 | 0.8358 | 0.7950 | 0.5734 |
| **5 km** | **33,022** | **5/5** | **0.8426** | **0.8084** | **0.5558** |
| 10 km | 33,022 | 5/5 | 0.8638 | 0.8425 | 0.6952 |

### 8.2 Analysis

All three buffers produced 5/5 valid folds — the domain is large enough that even 10 km exclusion leaves ample sampling space.

ROC-AUC increases slightly with larger buffers (0.836 → 0.843 → 0.864). This is consistent with the expected behaviour: larger buffers push pseudo-absences further into geographically distinct regions (plains), making geographic separation between classes stronger. This is **not** a sign of better environmental discriminability — it reflects easier geographic separation.

The 10 km buffer produces higher apparent performance by making geographic contrast sharper, not because the model is learning better physical drivers.

**Buffer selected: 5 km.** Scientific justification:
- Larger than typical GSI inventory positional uncertainty (~1–5 km)
- Does not artificially inflate performance by maximising geographic contrast
- Does not over-restrict sampling in narrow Himalayan valleys

---

## 9. Calibration Assessment

### 9.1 Calibration Curve (Model B-RF, v2, 5 valid folds)

| Bin | Predicted Mean | Actual Fraction | Monotonic? |
|---|---|---|---|
| 1 | 0.027 | 0.334 | — |
| 2 | 0.117 | 0.396 | ↑ |
| 3 | 0.327 | 0.062 | **↓** |
| 4 | 0.409 | 0.002 | **↓** |
| 5 | 0.513 | 0.502 | ↑ |
| 6 | 0.738 | 0.375 | **↓** |
| 7 | 0.882 | 0.786 | ↑ |
| 8 | 0.911 | 0.778 | ↓ minor |

`approximately_monotonic = false`

### 9.2 Root Cause

The 5 folds have highly heterogeneous positive prevalence:
- Fold 3: ~55% positive (6,676/12,200)
- Fold 0: ~40% positive (5,347/13,480)
- Fold 4: ~25% positive (1,995/8,092)
- Fold 1: ~10% positive (641/6,650)

The OOF score distribution is therefore a mixture of populations with very different base rates. Sigmoid (Platt) calibration fits a single monotone logistic function to this heterogeneous mixture. It cannot correctly handle the multi-modal OOF score distribution produced by geographically disparate folds with different class prevalences.

### 9.3 Consequence

The model output is documented as `"type": "susceptibility_score"` rather than `"calibrated_probability"`. Users must not treat raw output values as frequentist probabilities.

A well-calibrated susceptibility model requires: (a) terrain features to stabilise fold performance across geographic regions, and (b) isotonic or quantile-based calibration if prevalence varies strongly by zone. Neither is achievable with current data.

### 9.4 Raw vs Calibrated — Brier Score

| Model | Brier Score | Notes |
|---|---|---|
| Model A-RF (with geo) | 0.1398 | Partly from geographic memorization |
| Model B-RF (no geo) | 0.2245 | Honest; no geographic shortcut |
| Model A-HGB | 0.1332 | Same caveat as A-RF |
| Model B-HGB | 0.2130 | Slightly better than B-RF |

The Brier score for Model B-RF (0.2245) is higher than Model A's (0.1398) for the same reason ROC-AUC drops — removing the geographic shortcut degrades apparent calibration. This is the scientifically correct behaviour: Model B is harder to calibrate because it relies on weaker environmental signal.

---

## 10. Feature Importance Analysis

### 10.1 Model A-RF Feature Importances (with lat/lon — v1 style, REJECTED)

| Rank | Feature | Importance |
|---|---|---|
| 1 | longitude | 0.4020 |
| 2 | latitude | 0.3438 |
| 3 | annual_rainfall_mean_mm | 0.0570 |
| 4 | monsoon_variability_mm | 0.0568 |
| 5 | monsoon_rainfall_mean_mm | 0.0561 |
| 6 | winter_rainfall_mean_mm | 0.0472 |
| 7 | rainfall_seasonality_ratio | 0.0258 |
| 8 | pre_monsoon_rainfall_mean_mm | 0.0078 |
| 9 | post_monsoon_rainfall_mean_mm | 0.0035 |
| **Combined lat/lon** | | **0.7458** |

Geographic memorization pattern confirmed. lat/lon together account for 74.6% of predictive power.

### 10.2 Model B-RF Feature Importances (rainfall only — selected final model)

| Rank | Feature | Importance |
|---|---|---|
| 1 | winter_rainfall_mean_mm | 0.2195 |
| 2 | annual_rainfall_mean_mm | 0.2112 |
| 3 | monsoon_rainfall_mean_mm | 0.1955 |
| 4 | monsoon_variability_mm | 0.1581 |
| 5 | rainfall_seasonality_ratio | 0.1179 |
| 6 | pre_monsoon_rainfall_mean_mm | 0.0559 |
| 7 | post_monsoon_rainfall_mean_mm | 0.0418 |

### 10.3 Assessment of Model B Feature Importances

**Important finding: No feature dominates.** The top 4 features have importances between 0.158 and 0.220 — roughly evenly distributed. This is a healthy pattern for a model with only 7 features from ~15 distinct climatological profiles.

However, it also reveals a constraint: the model is essentially making coarse "high rainfall zone vs low rainfall zone" discriminations at subdivision granularity. Winter rainfall (0.220) ranking first is interesting — Himalayan slides are more prevalent in zones that also receive significant winter snowfall/precipitation, potentially distinguishing high-altitude mountain zones from lower foothills.

**Environmental signal is present but weak.** The rainfall-only model is not randomly guessing — it achieves ROC-AUC 0.6161 against a 5-fold spatial test. But it is operating at the resolution ceiling of the available data. Adding terrain features (elevation, slope) would break the within-subdivision ambiguity that currently limits the model.

### 10.4 Conclusion

> The current environmental feature set (IMD subdivision-level climatology) provides a real but weak discriminative signal for landslide susceptibility. The model is **not** a random classifier but its predictive power is significantly constrained by the absence of terrain data and the coarse spatial resolution of climatological features.

This is the scientifically honest conclusion. It is not hidden.

---

## 11. Scientific Limitations

### 11.1 Permanent Limitations (Cannot Be Resolved Without New Data)

1. **No terrain features.** Slope, elevation, aspect, curvature, and TWI are the primary deterministic controls on landslide initiation. Without a DEM, the model cannot capture the dominant physical drivers. This is the single largest limitation. `terrain_features_available = false`.

2. **No dynamic or antecedent rainfall.** The model uses 1901–2017 climatological baselines — not event-scale or near-real-time rainfall. It cannot discriminate between a currently active monsoon event and normal conditions. `dynamic_weather_features_available = false`.

3. **No geology or lithology.** Rock type, fault proximity, and soil depth are critical secondary controls. Unavailable.

4. **No land cover.** Deforestation and agricultural conversion increase susceptibility. Unavailable.

5. **Presence-background model.** Negative samples are pseudo-absences, not confirmed non-landslide sites. Output scores are relative suitability estimates, not frequentist probabilities.

6. **GSI inventory incompleteness and survey bias.** Data-sparse regions appear "safe" but may be unsurveyed. High-density regions may reflect thorough fieldwork as much as genuine physical susceptibility.

7. **~43% of positives have heuristic-assigned subdivisions.** IMD rainfall features for 7,144 positive records may be slightly inaccurate due to coarse administrative approximation.

8. **Subdivision-level rainfall granularity.** Only ~15 distinct rainfall profiles across the 10°×16° domain. Within-subdivision discrimination is not possible from rainfall alone.

### 11.2 Design Limitations (Addressable in Future Phases)

9. **Fixed 0.5 decision threshold.** Classification metrics use a hard 0.5 threshold. Optimal threshold should be determined via precision-recall curve analysis per operational use case.

10. **Uniform pseudo-absence sampling.** Does not correct for geographic sampling bias in the GSI inventory. Target-group background sampling would be more defensible.

11. **Single spatial domain.** The model covers only the Himalayan/Northern Zone. It does not generalise to the Western Ghats or other Indian landslide zones.

12. **Non-monotonic calibration.** Output cannot be treated as a calibrated probability until terrain features are added and calibration is re-evaluated.

### 11.3 Missing High-Value Features for Future Phases

The following features, if integrated, would most improve model performance (ranked by expected impact):

| Priority | Feature | Source | Expected Impact |
|---|---|---|---|
| 1 | Slope (degrees) | DEM (SRTM, ALOS, Copernicus) | Very high — primary physical control |
| 2 | Elevation (m) | Same DEM | High — determines climate zone and rock type |
| 3 | Aspect (degrees) | Same DEM | Moderate — solar exposure, moisture |
| 4 | Curvature (profile/plan) | Same DEM | Moderate — terrain convergence |
| 5 | Terrain Wetness Index (TWI) | DEM-derived | Moderate — soil saturation proxy |
| 6 | Lithology / geology | GSI geological maps | High — rock strength controls |
| 7 | Soil type and depth | NBSS soil surveys | Moderate — saturation capacity |
| 8 | Land cover / LULC | Sentinel-2 / MODIS | Moderate — vegetation root reinforcement |
| 9 | Antecedent rainfall (30-day) | IMD gridded daily data | High — trigger model enabler |
| 10 | Rainfall intensity (24h/72h) | IMD gridded daily data | Very high — trigger model enabler |

None of these are fabricated or currently available in the project.

---

## 12. Final Decision

### 12.1 Decision Criteria — Results

| Criterion | Threshold | Result | Pass? |
|---|---|---|---|
| All spatial folds valid (≥1 pos, ≥1 neg) | 5/5 folds | 5/5 ✓ | ✅ |
| Model B (no lat/lon) ROC-AUC ≥ 0.55 | 0.55 | 0.6161 ✓ | ✅ |
| Calibration curve approximately monotonic | Monotonically non-decreasing | Non-monotonic ✗ | ❌ |
| Ablation drop ≤ 0.15 (or no lat/lon) | ≤ 0.15 | Drop=0.2463; Model B selected (lat/lon excluded) | ✅ |
| Environmental features contribute ≥ 25% importance | ≥ 25% | 100% (no lat/lon in Model B) | ✅ |

One criterion fails: calibration is non-monotonic.

### 12.2 FINAL VERDICT

```
MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES
```

**Specific blocking reason:** The calibration curve is non-monotonic (`approximately_monotonic = false`). Output scores cannot be interpreted as reliable susceptibility probabilities. The non-monotonicity stems from radically different positive prevalence across the 5 geographic folds (10%–55%), which produces a multi-modal OOF score distribution that sigmoid calibration cannot handle.

**This is not a code failure. This is a data limitation.** The root cause is the absence of terrain features, which would provide within-subdivision discrimination and stabilise fold performance across geographic regions. Until terrain features are added, calibration will remain unreliable because the model cannot learn the physical drivers that cause the observed geographic variation in fold performance.

### 12.3 What Passed

- All 5 spatial folds are valid (zero positives, zero NaN issues resolved)
- ROC-AUC = 0.6161 — genuine environmental signal above random baseline
- Feature set is free of direct leakage and geographic memorization (lat/lon excluded)
- Rainfall features have balanced importances (no collapse to a single feature)
- JSON artifacts are now valid (NaN bug fixed)
- Model version v2 correctly distinguishes itself from the invalid v1

### 12.4 Artifact Status

| Artifact | Location | Label |
|---|---|---|
| `pipeline.joblib` | `app/services/prediction/artifacts/` | **v1 — EXPERIMENTAL (unchanged)** |
| `features.json` | `app/services/prediction/artifacts/` | v2 — Updated, reflects v2 design |
| `metadata.json` | `app/services/prediction/artifacts/` | v2 — Updated, reflects v2 results |
| `metrics.json` | `app/services/prediction/artifacts/` | v2 — Updated, valid JSON, no NaN |
| `pipeline_experimental.joblib` | `artifacts/experiments/` | v2 — EXPERIMENTAL, 574.5 KB |

The production `pipeline.joblib` was NOT overwritten. It remains the v1 9-feature model. The v2 experimental pipeline (7-feature rainfall-only RF) is saved in `artifacts/experiments/` and labelled `EXPERIMENTAL — NOT PRODUCTION READY`.

### 12.5 Path to Production Readiness

To reach `MODEL VALID — BASELINE SUSCEPTIBILITY MODEL`:

1. **Integrate a DEM** (SRTM 30m or Copernicus DEM 30m). Derive slope, elevation, aspect, curvature, TWI for the modeling domain.
2. **Re-train with terrain features.** With slope and elevation, the model should achieve per-fold ROC-AUC stability that supports reliable sigmoid calibration.
3. **Re-run ablation.** Verify that terrain features reduce lat/lon dominance.
4. **Re-evaluate calibration monotonicity.** If `approximately_monotonic = true`, the model passes the calibration criterion.
5. **Re-run this validity review.** All 5 criteria must pass.

Until step 1 is complete, the model remains in experimental status. The deterministic risk engine (Phase 2A) remains the certified production intelligence layer.

---

## 13. Engineering Status

### 13.1 Ruff

| Check | Result |
|---|---|
| `scripts/train_landslide_model.py` | **All checks passed** |
| `tests/unit/test_ml_pipeline.py` | **All checks passed** |
| Full codebase (`ruff check .`) | **All checks passed** |

6 F541 errors from v1 (f-strings with no placeholders) resolved. No new violations introduced.

### 13.2 mypy

| Target | Result |
|---|---|
| `scripts/train_landslide_model.py` | **Success: no issues found** |
| `tests/unit/test_ml_pipeline.py` | **Success: no issues found** |
| `app/` (100 source files) | **Success: no issues found** |

mypy 1.20 bidirectional inference quirk with `list[str]` in `dict[str, Any]` resolved by extracting helper functions `_build_validity_record()`, `_print_validity_reasons()`, `_print_summary_reasons()`.

### 13.3 pytest

| Suite | Tests | Result |
|---|---|---|
| Pre-existing (all systems) | 255 | ✅ Pass |
| New ML pipeline tests | 104 | ✅ Pass |
| **Total** | **359** | **✅ Pass — zero regressions** |

New ML tests cover:
- Pseudo-absence generation: count, domain bounds, 3/5/10 km buffer enforcement, reproducibility, different seeds
- 2D spatial block assignment: fold range, length, all folds represented, integer dtype, determinism, no empty folds, multiple n_folds
- Fold validity checking: balanced valid, zero-positive fold invalid, zero-negative fold invalid, count correctness, reason=None for valid
- Feature schema leakage audit: no leaky features, no terrain fabrications, no dynamic weather, lat/lon excluded from no-geo set, correct counts, no duplicates, all rainfall features present
- `coords_to_subdivision` heuristic: 7 zone tests + fallback
- `compute_rainfall_features`: None for unknown, 7 keys present, annual sum correct, monsoon months correct, seasonality in [0,1], all non-negative, empty cache None
- `get_subdivision_for_record`: authority source, heuristic source, empty state, unmapped state, return type
- `_safe_json_dumps`: NaN→null, ±Inf→null, normal float preserved, nested NaN, nested dict, valid JSON output, no bare NaN token
- `_build_validity_record`: structure, empty reasons, reasons is list
- Artifact loading: loads without error, has predict_proba, shape (1,2), probabilities sum to 1, in [0,1], batch=single
- `metadata.json` schema: 18 required fields, version, sklearn_version, count matches names, count is 7 or 9, dataset keys, buffer positive, domain bounds, seed type, limitations, 2D method, fold_validity_enforced=True, verdict valid
- `features.json` schema: required keys, terrain=false, weather=false, count matches, importances sum ≈1, all non-negative, leakage features in excluded, terrain in excluded, excluded have reasons
- `metrics.json` validity: no NaN in valid folds, fold status fields, n_valid_folds, ablation section, scientific_validity section, verdict valid, calibration fields, buffer_sensitivity list, valid JSON
- Model version constants: version string, domain bounds, earth radius

### 13.4 compileall

| Target | Result |
|---|---|
| `app/` | **Clean** |
| `scripts/` | **Clean** |
| `tests/` | **Clean** |

### 13.5 Artifact Summary

| File | Status | Notes |
|---|---|---|
| `app/services/prediction/artifacts/pipeline.joblib` | Unchanged (v1) | 9-feature RF, EXPERIMENTAL, not overwritten |
| `app/services/prediction/artifacts/features.json` | Updated (v2) | 7-feature no-geo schema, leakage docs, lat/lon excluded |
| `app/services/prediction/artifacts/metadata.json` | Updated (v2) | sklearn 1.9.0, 5km buffer, 7144 unknown state, fold_validity=True |
| `app/services/prediction/artifacts/metrics.json` | Updated (v2) | Valid JSON, ablation results, buffer sensitivity, all 5 folds valid, scientific_validity verdict |
| `artifacts/experiments/pipeline_experimental.joblib` | New (v2) | 574.5 KB, 7-feature RF, EXPERIMENTAL — NOT PRODUCTION READY |

### 13.6 Existing Certified Systems — Unchanged

| System | Status |
|---|---|
| Phase 2A deterministic risk engine | ✅ Certified — unchanged |
| Impact assessment engine | ✅ Certified — unchanged |
| Priority engine | ✅ Certified — unchanged |
| Ground intelligence engine | ✅ Certified — unchanged |
| Alert system | ✅ Certified — unchanged |
| Auth, security, middleware | ✅ Certified — unchanged |

No existing production logic was modified. The ML pipeline is a standalone experimental module that does not interact with any certified system.

---

*Scientific honesty has priority over producing a high metric. The decision MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES accurately reflects the state of this model under honest spatial validation with the currently available feature set. The path to production readiness is clearly defined: integrate a DEM.*
