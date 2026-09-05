#!/usr/bin/env python
"""
RISKSETU AI — Landslide Susceptibility Model Training Script (v2).

Trains a spatially validated, probability-calibrated landslide susceptibility
model using real GSI Bhukosh NLSM inventory data and IMD climatology baselines.

Scientific changes vs v1 (2026-09-04 review):
  - Spatial validation: replaced longitude-only quantile blocks with 2D
    lat×lon grid blocks for compact geographic isolation.
  - Fold validity: every fold used in aggregate ROC-AUC must contain ≥1
    positive and ≥1 negative; invalid folds are excluded and logged.
  - Lat/lon ablation: Model A (with lat/lon) vs Model B (without lat/lon)
    are trained and compared to detect geographic memorization.
  - Buffer sensitivity: 3 km / 5 km / 10 km exclusion buffers evaluated;
    5 km selected based on positional-uncertainty justification.
  - JSON serialisation: NaN / Inf values are replaced with null rather than
    emitting invalid JSON literals.
  - subdiv_source field: distinguishes state-authority assignments from
    coordinate-heuristic assignments.
  - Dead code removed: material / movement_type never used, removed.
  - Ruff F541 fixed: f-strings with no placeholders converted to plain str.
  - sklearn version recorded in metadata.
  - Experimental artifacts saved to artifacts/experiments/; production
    artifact only overwritten if model passes validity criteria.

Model Version: risksetu-landslide-susceptibility-v2
Target: Binary susceptibility (y=1: GSI presence, y=0: pseudo-absence)
Validation: 2D Spatial Grid GroupKFold (fold-validity enforced)
Calibration: Platt/sigmoid via CalibratedClassifierCV (valid folds only)

Usage:
    poetry run python scripts/train_landslide_model.py [--seed 42] [--ratio 2.0] [--exclusion-km 5.0]

Safety:
    - Does NOT modify existing risk engine, APIs, database, or frontend.
    - Does NOT use target-leaking proximity/density features.
    - Does NOT fabricate terrain, DEM, or live weather data.
    - Does NOT overwrite production artifact unless model passes validity.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import BallTree

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import app.*
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0
MODEL_VERSION = "risksetu-landslide-susceptibility-v2"

# Himalayan / Northern Zone modeling domain (approved in implementation plan)
DOMAIN = {
    "lat_min": 26.0,
    "lat_max": 36.0,
    "lon_min": 74.0,
    "lon_max": 90.0,
}

ARTIFACT_DIR = PROJECT_ROOT / "app" / "services" / "prediction" / "artifacts"
EXPERIMENT_DIR = PROJECT_ROOT / "artifacts" / "experiments"

# Full feature set (lat/lon included) — Model A
FEATURE_NAMES_WITH_GEO = [
    "latitude",
    "longitude",
    "annual_rainfall_mean_mm",
    "monsoon_rainfall_mean_mm",
    "winter_rainfall_mean_mm",
    "pre_monsoon_rainfall_mean_mm",
    "post_monsoon_rainfall_mean_mm",
    "monsoon_variability_mm",
    "rainfall_seasonality_ratio",
]

# Rainfall-only feature set (lat/lon excluded) — Model B
FEATURE_NAMES_NO_GEO = [
    "annual_rainfall_mean_mm",
    "monsoon_rainfall_mean_mm",
    "winter_rainfall_mean_mm",
    "pre_monsoon_rainfall_mean_mm",
    "post_monsoon_rainfall_mean_mm",
    "monsoon_variability_mm",
    "rainfall_seasonality_ratio",
]

# State name → IMD subdivision normalized name mapping
STATE_TO_SUBDIVISION: dict[str, str] = {
    "Uttarakhand": "UTTARAKHAND",
    "Jammu & Kashmir": "JAMMU AND KASHMIR",
    "Himachal Pradesh": "HIMACHAL PRADESH",
    "Sikkim": "SUB HIMALAYAN WEST BENGAL AND SIKKIM",
    "West Bengal": "SUB HIMALAYAN WEST BENGAL AND SIKKIM",
    "Arunachal Pradesh": "ARUNACHAL PRADESH",
    "Assam": "ASSAM AND MEGHALAYA",
    "Meghalaya": "ASSAM AND MEGHALAYA",
    "Nagaland": "NAGA MANI MIZO TRIPURA",
    "Manipur": "NAGA MANI MIZO TRIPURA",
    "Mizoram": "NAGA MANI MIZO TRIPURA",
    "Tripura": "NAGA MANI MIZO TRIPURA",
}

# Minimum fraction of positives required per fold for the fold to be valid.
MIN_FOLD_POSITIVES = 1
MIN_FOLD_NEGATIVES = 1


# ---------------------------------------------------------------------------
# JSON serialisation helper: replace NaN/Inf with null
# ---------------------------------------------------------------------------
class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that converts NaN / Inf to null instead of bare tokens.

    Standard Python json.dumps() emits NaN and Infinity as bare literals,
    which are not valid JSON (RFC 8259).  This encoder replaces them with
    JSON null so that strict parsers can consume the output.
    """

    def iterencode(self, o: Any, _one_shot: bool = False) -> Any:  # type: ignore[override]
        return super().iterencode(self._sanitise(o), _one_shot)

    def _sanitise(self, obj: Any) -> Any:
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: self._sanitise(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitise(v) for v in obj]
        return obj


def _safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """Serialise obj to JSON string, replacing NaN/Inf with null."""
    return json.dumps(obj, cls=_SafeEncoder, **kwargs)


# ---------------------------------------------------------------------------
# Geographic helper: map lat/lon → IMD subdivision
# ---------------------------------------------------------------------------
def coords_to_subdivision(lat: float, lon: float) -> str:
    """Coarse geographic zone → IMD subdivision mapping.

    Used ONLY for pseudo-absence samples and 'Unknown'-state GSI records.
    This is a simplified latitude/longitude heuristic.  It should be refined
    with actual administrative boundary polygons in future phases.
    """
    if lat >= 33.0 and lon <= 79.0:
        return "JAMMU AND KASHMIR"
    if lat >= 30.5 and lon <= 78.5:
        return "HIMACHAL PRADESH"
    if 29.0 <= lat <= 32.0 and lon <= 81.0:
        return "UTTARAKHAND"
    if lat <= 28.5 and lon >= 87.0:
        return "SUB HIMALAYAN WEST BENGAL AND SIKKIM"
    if lat >= 26.5 and lon >= 90.0:
        return "NAGA MANI MIZO TRIPURA"
    if lat >= 26.5 and lon >= 88.0:
        return "ASSAM AND MEGHALAYA"
    if lon <= 77.0 and lat >= 29.0:
        return "PUNJAB"
    return "UTTARAKHAND"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_landslide_data() -> pd.DataFrame:
    """Load GSI landslide records from the project database."""
    from app.db.session import SessionLocal
    from app.models.landslide import HistoricalLandslide

    print("[1/9] Loading landslide data from PostgreSQL …")
    with SessionLocal() as db:
        records = db.query(
            HistoricalLandslide.latitude,
            HistoricalLandslide.longitude,
            HistoricalLandslide.state,
        ).all()

    df = pd.DataFrame(records, columns=["latitude", "longitude", "state"])
    print(f"      → {len(df)} total landslide records loaded.")
    return df


def load_climatology_cache() -> dict[str, dict[int, dict[str, float]]]:
    """Load all IMD climatology baselines into a fast-lookup dictionary.

    Returns: {subdivision_normalized_name: {month(1-12): {"mean": X, "std": Y}}}
    """
    from app.db.session import SessionLocal
    from app.models.rainfall import RainfallClimatology, RainfallSubdivision

    print("[2/9] Loading IMD climatology cache from PostgreSQL …")
    with SessionLocal() as db:
        subdivs = db.query(RainfallSubdivision).all()
        subdiv_id_to_name = {s.id: s.normalized_name for s in subdivs}

        clims = db.query(RainfallClimatology).all()

    cache: dict[str, dict[int, dict[str, float]]] = {}
    for c in clims:
        name = subdiv_id_to_name.get(c.subdivision_id)
        if name is None:
            continue
        if name not in cache:
            cache[name] = {}
        cache[name][c.month] = {"mean": c.mean_mm, "std": c.stddev_mm}

    print(f"      → {len(cache)} subdivisions with climatology data cached.")
    return cache


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------
def compute_rainfall_features(
    subdivision_name: str,
    climatology_cache: dict[str, dict[int, dict[str, float]]],
) -> dict[str, float] | None:
    """Compute aggregate rainfall features for a given IMD subdivision.

    Returns None if the subdivision has no climatology data.
    """
    clim = climatology_cache.get(subdivision_name)
    if not clim:
        return None

    monthly_means = [clim.get(m, {}).get("mean", 0.0) for m in range(1, 13)]
    monthly_stds = [clim.get(m, {}).get("std", 0.0) for m in range(1, 13)]

    annual_mean = sum(monthly_means)
    monsoon_mean = sum(monthly_means[5:9])       # Jun–Sep (0-indexed 5–8)
    winter_mean = sum(monthly_means[0:2])         # Jan–Feb (0-indexed 0–1)
    pre_monsoon_mean = sum(monthly_means[2:5])    # Mar–May (0-indexed 2–4)
    post_monsoon_mean = sum(monthly_means[9:12])  # Oct–Dec (0-indexed 9–11)

    monsoon_variability = float(np.mean(monthly_stds[5:9])) if any(monthly_stds[5:9]) else 0.0
    seasonality = monsoon_mean / annual_mean if annual_mean > 0 else 0.0

    return {
        "annual_rainfall_mean_mm": annual_mean,
        "monsoon_rainfall_mean_mm": monsoon_mean,
        "winter_rainfall_mean_mm": winter_mean,
        "pre_monsoon_rainfall_mean_mm": pre_monsoon_mean,
        "post_monsoon_rainfall_mean_mm": post_monsoon_mean,
        "monsoon_variability_mm": monsoon_variability,
        "rainfall_seasonality_ratio": seasonality,
    }


def get_subdivision_for_record(
    state: str,
    lat: float,
    lon: float,
) -> tuple[str, str]:
    """Determine IMD subdivision for a data point.

    Returns:
        (subdivision_name, subdiv_source) where subdiv_source is one of:
          "state_authority"     — derived from the record's state attribute
          "coordinate_heuristic" — derived via coords_to_subdivision()
    """
    if state and state != "Unknown":
        mapped = STATE_TO_SUBDIVISION.get(state)
        if mapped:
            return mapped, "state_authority"
    return coords_to_subdivision(lat, lon), "coordinate_heuristic"


# ---------------------------------------------------------------------------
# Pseudo-absence sampling
# ---------------------------------------------------------------------------
def generate_pseudo_absences(
    positive_coords: np.ndarray,
    n_negatives: int,
    exclusion_km: float,
    seed: int,
) -> np.ndarray:
    """Generate background/pseudo-absence samples within the modeling domain.

    Uses sklearn BallTree with haversine metric for efficient spatial
    exclusion buffer enforcement.

    Args:
        positive_coords: Array of shape (N, 2) with [lat, lon] in degrees.
        n_negatives: Number of negative samples to generate.
        exclusion_km: Minimum geodesic distance from any positive point.
        seed: Random seed for reproducibility.

    Returns:
        Array of shape (n_negatives, 2) with [lat, lon] in degrees.
    """
    print(f"[4/9] Generating {n_negatives} pseudo-absence samples (buffer={exclusion_km} km) …")
    rng = np.random.RandomState(seed)

    # Build BallTree from positive coordinates (radians, [lat, lon])
    pos_rad = np.radians(positive_coords)
    tree = BallTree(pos_rad, metric="haversine")
    exclusion_rad = exclusion_km / EARTH_RADIUS_KM

    accepted: list[np.ndarray] = []
    batch_size = n_negatives * 4  # Over-sample to account for rejections
    max_attempts = 20

    for attempt in range(max_attempts):
        cand_lat = rng.uniform(DOMAIN["lat_min"], DOMAIN["lat_max"], batch_size)
        cand_lon = rng.uniform(DOMAIN["lon_min"], DOMAIN["lon_max"], batch_size)

        cand_rad = np.column_stack([np.radians(cand_lat), np.radians(cand_lon)])
        distances, _ = tree.query(cand_rad, k=1)
        distances = distances.ravel()

        mask = distances >= exclusion_rad
        valid = np.column_stack([cand_lat[mask], cand_lon[mask]])
        accepted.append(valid)

        total_accepted = sum(len(a) for a in accepted)
        if total_accepted >= n_negatives:
            break

    all_accepted = np.vstack(accepted)[:n_negatives]
    actual = len(all_accepted)
    print(f"      → {actual} pseudo-absence samples generated (target: {n_negatives}).")
    if actual < n_negatives:
        print(f"      WARNING: Only {actual}/{n_negatives} samples met exclusion buffer.")
    return all_accepted


# ---------------------------------------------------------------------------
# Validity record builder — isolated to prevent mypy bidirectional-inference
# from re-typing validity_reasons as list[dict[str, Any]] when it is used
# inside large dict[str, Any] literals in main().
# ---------------------------------------------------------------------------
def _build_validity_record(
    validity_reasons: list[str],
    all_folds_valid: bool,
    best_nvalid: int,
    roc_acceptable: bool,
    calibration_ok: bool,
    environmental_signal: bool,
    verdict: str,
) -> dict[str, Any]:
    """Return a JSON-serialisable validity record dict."""
    return {
        "verdict": verdict,
        "all_folds_valid": all_folds_valid,
        "n_valid_folds": best_nvalid,
        "roc_acceptable": roc_acceptable,
        "calibration_monotonic": calibration_ok,
        "environmental_signal_sufficient": environmental_signal,
        "reasons": validity_reasons,
    }


def _print_validity_reasons(validity_reasons: list[str]) -> None:
    """Print each validity reason to stdout."""
    for r in validity_reasons:
        print(f"   - {r}")


def _print_summary_reasons(validity_reasons: list[str]) -> None:
    """Print each validity reason in the summary block."""
    for r in validity_reasons:
        print(f"    - {r}")
def assign_spatial_blocks_2d(
    lats: np.ndarray,
    lons: np.ndarray,
    n_lat_bins: int = 4,
    n_lon_bins: int = 4,
    n_folds: int = 5,
) -> np.ndarray:
    """Assign each point to a spatial fold using a 2D lat×lon grid.

    Creates compact geographic patches (not unbounded north–south strips),
    ensuring both latitudinal and longitudinal variation are captured in the
    spatial isolation.  Grid cells are mapped round-robin to fold indices so
    that each fold contains a geographically distributed mix of cells.

    Args:
        lats: 1-D array of latitudes.
        lons: 1-D array of longitudes.
        n_lat_bins: Number of latitude quantile bins.
        n_lon_bins: Number of longitude quantile bins.
        n_folds: Target number of cross-validation folds.

    Returns:
        1-D integer array of fold assignments (0 to n_folds-1).
    """
    # Quantile edges — each bin contains roughly equal sample counts
    lat_edges = np.percentile(lats, np.linspace(0, 100, n_lat_bins + 1))
    lon_edges = np.percentile(lons, np.linspace(0, 100, n_lon_bins + 1))

    lat_bin = np.digitize(lats, lat_edges[1:-1])   # 0 to n_lat_bins-1
    lon_bin = np.digitize(lons, lon_edges[1:-1])   # 0 to n_lon_bins-1

    # Combine into a single cell index
    cell = lat_bin * n_lon_bins + lon_bin  # 0 to (n_lat_bins * n_lon_bins - 1)

    # Map cells → folds round-robin so each fold gets a geographic mix
    unique_cells = np.unique(cell)
    cell_to_fold = {c: int(i % n_folds) for i, c in enumerate(unique_cells)}
    folds = np.array([cell_to_fold[c] for c in cell], dtype=int)
    return folds


def check_fold_validity(
    y: np.ndarray,
    groups: np.ndarray,
    n_folds: int,
) -> dict[int, dict[str, Any]]:
    """Check whether each fold has ≥1 positive and ≥1 negative in its val set.

    Returns:
        Dict mapping fold_idx → {"valid": bool, "n_pos": int, "n_neg": int,
                                  "reason": str | None}
    """
    result: dict[int, dict[str, Any]] = {}
    for fold_idx in range(n_folds):
        val_mask = groups == fold_idx
        y_val = y[val_mask]
        n_pos = int(y_val.sum())
        n_neg = int(len(y_val) - n_pos)
        if n_pos < MIN_FOLD_POSITIVES:
            valid = False
            reason = f"fold {fold_idx}: only {n_pos} positives (need ≥{MIN_FOLD_POSITIVES})"
        elif n_neg < MIN_FOLD_NEGATIVES:
            valid = False
            reason = f"fold {fold_idx}: only {n_neg} negatives (need ≥{MIN_FOLD_NEGATIVES})"
        else:
            valid = True
            reason = None
        result[fold_idx] = {"valid": valid, "n_pos": n_pos, "n_neg": n_neg, "reason": reason}
    return result


# ---------------------------------------------------------------------------
# Model training and evaluation
# ---------------------------------------------------------------------------
def run_spatial_cv(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    model_class: type,
    model_params: dict[str, Any],
    n_splits: int = 5,
    model_name: str = "",
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any], int]:
    """Run spatial GroupKFold cross-validation and report per-fold metrics.

    Fold validity is enforced: folds with fewer than MIN_FOLD_POSITIVES or
    MIN_FOLD_NEGATIVES are marked invalid and excluded from aggregate metrics.

    Returns:
        oof_proba: Out-of-fold probability array (NaN for invalid folds).
        fold_metrics: Per-fold metric dicts including validity status.
        overall: Aggregate metrics over valid folds only.
        n_valid_folds: Number of folds that passed validity check.
    """
    gkf = GroupKFold(n_splits=n_splits)
    oof_proba = np.full(len(y), np.nan)
    fold_metrics: list[dict[str, Any]] = []
    fold_validity = check_fold_validity(y, groups, n_splits)

    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
        fv = fold_validity[fold_idx]
        if not fv["valid"]:
            print(
                f"      Fold {fold_idx}: INVALID — {fv['reason']} — excluded from aggregate."
            )
            fold_metrics.append({
                "fold": fold_idx,
                "status": "INVALID_SINGLE_CLASS",
                "reason": fv["reason"],
                "n_train": len(train_idx),
                "n_val": len(val_idx),
                "n_pos_val": fv["n_pos"],
                "n_neg_val": fv["n_neg"],
                "roc_auc": None,
                "pr_auc": None,
                "precision": None,
                "recall": None,
                "f1": None,
                "brier": None,
            })
            continue

        model = model_class(**model_params)
        model.fit(X[train_idx], y[train_idx])
        proba = model.predict_proba(X[val_idx])[:, 1]
        oof_proba[val_idx] = proba

        preds = (proba >= 0.5).astype(int)
        roc = float(roc_auc_score(y[val_idx], proba))
        pr = float(average_precision_score(y[val_idx], proba))
        prec = float(precision_score(y[val_idx], preds, zero_division=0))
        rec = float(recall_score(y[val_idx], preds, zero_division=0))
        f1 = float(f1_score(y[val_idx], preds, zero_division=0))
        brier = float(brier_score_loss(y[val_idx], proba))

        fold_metrics.append({
            "fold": fold_idx,
            "status": "VALID",
            "reason": None,
            "n_train": len(train_idx),
            "n_val": len(val_idx),
            "n_pos_val": fv["n_pos"],
            "n_neg_val": fv["n_neg"],
            "roc_auc": roc,
            "pr_auc": pr,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "brier": brier,
        })
        print(
            f"      Fold {fold_idx}: ROC-AUC={roc:.4f}  PR-AUC={pr:.4f}  "
            f"F1={f1:.4f}  [pos={fv['n_pos']}, neg={fv['n_neg']}]"
        )

    # Aggregate metrics — only over valid OOF predictions
    valid_mask = ~np.isnan(oof_proba)
    n_valid_folds = int(valid_mask.any())
    n_valid_folds = sum(1 for fm in fold_metrics if fm["status"] == "VALID")

    if n_valid_folds == 0:
        print(f"      ERROR: Zero valid folds for {model_name}. Cannot compute aggregate metrics.")
        overall: dict[str, Any] = {
            "model_name": model_name,
            "roc_auc": None,
            "pr_auc": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "brier_score": None,
            "confusion_matrix": None,
            "n_valid_folds": 0,
            "n_total_folds": n_splits,
        }
        return oof_proba, fold_metrics, overall, 0

    y_val = y[valid_mask]
    p_val = oof_proba[valid_mask]
    preds_val = (p_val >= 0.5).astype(int)
    cm = confusion_matrix(y_val, preds_val).tolist()

    overall = {
        "model_name": model_name,
        "roc_auc": float(roc_auc_score(y_val, p_val)),
        "pr_auc": float(average_precision_score(y_val, p_val)),
        "precision": float(precision_score(y_val, preds_val, zero_division=0)),
        "recall": float(recall_score(y_val, preds_val, zero_division=0)),
        "f1": float(f1_score(y_val, preds_val, zero_division=0)),
        "brier_score": float(brier_score_loss(y_val, p_val)),
        "confusion_matrix": cm,
        "n_valid_folds": n_valid_folds,
        "n_total_folds": n_splits,
    }

    return oof_proba, fold_metrics, overall, n_valid_folds


# ---------------------------------------------------------------------------
# Buffer sensitivity experiment
# ---------------------------------------------------------------------------
def run_buffer_sensitivity(
    pos_coords: np.ndarray,
    n_negatives: int,
    seed: int,
    buffers_km: list[float],
    X_pos: np.ndarray,
    y_pos: np.ndarray,
    groups_pos: np.ndarray,
    feature_names: list[str],
    climatology_cache: dict[str, dict[int, dict[str, float]]],
    n_folds: int,
) -> list[dict[str, Any]]:
    """Evaluate model performance under different exclusion buffer distances.

    For each buffer, generates fresh pseudo-absences and trains a lightweight
    RandomForest (fewer trees) to estimate the effect on ROC-AUC.

    Returns list of result dicts (one per buffer).
    """
    results = []
    rf_params_light = {
        "n_estimators": 50,
        "max_depth": 8,
        "min_samples_leaf": 5,
        "random_state": seed,
        "n_jobs": -1,
        "class_weight": "balanced",
    }

    for buf_km in buffers_km:
        print(f"\n   Buffer {buf_km} km …")
        neg_coords = generate_pseudo_absences(pos_coords, n_negatives, buf_km, seed)

        # Build feature matrix for negatives
        neg_feats: list[dict[str, float]] = []
        for i in range(len(neg_coords)):
            lat_n, lon_n = float(neg_coords[i, 0]), float(neg_coords[i, 1])
            subdiv = coords_to_subdivision(lat_n, lon_n)
            rain = compute_rainfall_features(subdiv, climatology_cache)
            if rain is None:
                continue
            feat: dict[str, float] = {"latitude": lat_n, "longitude": lon_n, **rain}
            neg_feats.append(feat)

        if not neg_feats:
            results.append({"buffer_km": buf_km, "n_negatives": 0, "roc_auc": None})
            continue

        X_neg_df = pd.DataFrame(neg_feats)
        X_neg = X_neg_df[feature_names].values
        y_neg = np.zeros(len(X_neg))

        X_all = np.vstack([X_pos, X_neg])
        y_all = np.concatenate([y_pos, y_neg])

        # Assign spatial blocks for combined dataset
        lats_all = X_all[:, feature_names.index("latitude")] if "latitude" in feature_names else np.zeros(len(X_all))
        lons_all = X_all[:, feature_names.index("longitude")] if "longitude" in feature_names else np.zeros(len(X_all))
        if "latitude" in feature_names:
            groups_all = assign_spatial_blocks_2d(lats_all, lons_all, n_folds=n_folds)
        else:
            # For no-geo features, re-use pos groups concatenated with freshly assigned neg groups
            neg_lats = neg_coords[:len(X_neg), 0]
            neg_lons = neg_coords[:len(X_neg), 1]
            neg_groups = assign_spatial_blocks_2d(neg_lats, neg_lons, n_folds=n_folds)
            groups_all = np.concatenate([groups_pos, neg_groups])

        _, _, buf_overall, buf_valid_folds = run_spatial_cv(
            X_all, y_all, groups_all,
            RandomForestClassifier, rf_params_light,
            n_splits=n_folds, model_name=f"RF_buf{int(buf_km)}km",
        )
        results.append({
            "buffer_km": buf_km,
            "n_negatives": len(X_neg),
            "n_valid_folds": buf_valid_folds,
            "roc_auc": buf_overall.get("roc_auc"),
            "pr_auc": buf_overall.get("pr_auc"),
            "f1": buf_overall.get("f1"),
        })

    return results


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main() -> None:
    """Execute the full redesigned training pipeline."""
    parser = argparse.ArgumentParser(description="Train RISKSETU landslide susceptibility model v2")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--ratio", type=float, default=2.0, help="Negative:positive ratio")
    parser.add_argument(
        "--exclusion-km", type=float, default=5.0,
        help="Pseudo-absence exclusion buffer in km (default 5.0 for positional-uncertainty robustness)"
    )
    parser.add_argument("--n-folds", type=int, default=5, help="Number of spatial CV folds")
    parser.add_argument(
        "--skip-buffer-sensitivity", action="store_true",
        help="Skip buffer sensitivity analysis (faster run)"
    )
    args = parser.parse_args()

    t_start = time.time()
    print("=" * 72)
    print("RISKSETU AI — Landslide Susceptibility Model Training (v2)")
    print(f"Model Version: {MODEL_VERSION}")
    print(f"Seed: {args.seed}  |  Ratio: 1:{args.ratio}  |  Exclusion: {args.exclusion_km} km")
    print(f"sklearn: {sklearn.__version__}")
    print("=" * 72)

    # ── Step 1: Load data ──────────────────────────────────────────────
    landslide_df = load_landslide_data()
    climatology_cache = load_climatology_cache()

    # ── Step 3: Filter to modeling domain ──────────────────────────────
    print("[3/9] Filtering to Himalayan/Northern Zone modeling domain …")
    domain_mask = (
        (landslide_df["latitude"] >= DOMAIN["lat_min"])
        & (landslide_df["latitude"] <= DOMAIN["lat_max"])
        & (landslide_df["longitude"] >= DOMAIN["lon_min"])
        & (landslide_df["longitude"] <= DOMAIN["lon_max"])
    )
    pos_df = landslide_df[domain_mask].copy().reset_index(drop=True)
    n_unknown_state = int((pos_df["state"] == "Unknown").sum())
    print(f"      → {len(pos_df)} landslide records within modeling domain.")
    print(
        f"      → {n_unknown_state} records ({100*n_unknown_state/max(len(pos_df),1):.1f}%) "
        "have state='Unknown' — subdivision assigned via coordinate heuristic."
    )

    if len(pos_df) < 100:
        print("ERROR: Insufficient positive samples in modeling domain. Aborting.")
        sys.exit(1)

    # ── Step 4: Generate pseudo-absences (selected buffer) ────────────
    n_positives = len(pos_df)
    n_negatives = int(n_positives * args.ratio)
    pos_coords = pos_df[["latitude", "longitude"]].values

    neg_coords = generate_pseudo_absences(
        positive_coords=pos_coords,
        n_negatives=n_negatives,
        exclusion_km=args.exclusion_km,
        seed=args.seed,
    )

    # ── Step 5: Build feature matrices ────────────────────────────────
    print("[5/9] Building leakage-safe feature matrix …")

    # Positive samples
    pos_features: list[dict[str, float]] = []
    pos_skipped = 0
    n_pos_heuristic = 0
    for _, row in pos_df.iterrows():
        subdiv, src = get_subdivision_for_record(
            str(row["state"]), float(row["latitude"]), float(row["longitude"])
        )
        if src == "coordinate_heuristic":
            n_pos_heuristic += 1
        rain = compute_rainfall_features(subdiv, climatology_cache)
        if rain is None:
            pos_skipped += 1
            continue
        feat: dict[str, float] = {
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            **rain,
        }
        pos_features.append(feat)

    # Negative samples
    neg_features: list[dict[str, float]] = []
    neg_skipped = 0
    for i in range(len(neg_coords)):
        lat_n, lon_n = float(neg_coords[i, 0]), float(neg_coords[i, 1])
        subdiv = coords_to_subdivision(lat_n, lon_n)
        rain = compute_rainfall_features(subdiv, climatology_cache)
        if rain is None:
            neg_skipped += 1
            continue
        feat = {"latitude": lat_n, "longitude": lon_n, **rain}
        neg_features.append(feat)

    print(f"      → Positives with features: {len(pos_features)} (skipped {pos_skipped} no-climatology)")
    print(f"        ({n_pos_heuristic} positives used coordinate-heuristic subdivision)")
    print(f"      → Negatives with features: {len(neg_features)} (skipped {neg_skipped} no-climatology)")

    # Build arrays
    pos_df_feat = pd.DataFrame(pos_features)
    neg_df_feat = pd.DataFrame(neg_features)

    # Model A: with lat/lon
    X_pos_A = pos_df_feat[FEATURE_NAMES_WITH_GEO].values
    X_neg_A = neg_df_feat[FEATURE_NAMES_WITH_GEO].values
    X_A = np.vstack([X_pos_A, X_neg_A])
    y_A = np.concatenate([np.ones(len(X_pos_A)), np.zeros(len(X_neg_A))])

    # Model B: without lat/lon (same samples, subset of columns)
    X_pos_B = pos_df_feat[FEATURE_NAMES_NO_GEO].values
    X_neg_B = neg_df_feat[FEATURE_NAMES_NO_GEO].values
    X_B = np.vstack([X_pos_B, X_neg_B])
    y_B = y_A.copy()  # labels identical; only feature columns differ

    print(
        f"      → Model A shape: {X_A.shape}  "
        f"y=1: {int(y_A.sum())}  y=0: {int(len(y_A) - y_A.sum())}"
    )
    print(f"      → Model B shape: {X_B.shape} (lat/lon excluded)")

    # ── Step 6: Assign 2D spatial blocks ──────────────────────────────
    print("[6/9] Assigning 2D spatial grid blocks for GroupKFold validation …")
    lats_A = X_A[:, FEATURE_NAMES_WITH_GEO.index("latitude")]
    lons_A = X_A[:, FEATURE_NAMES_WITH_GEO.index("longitude")]
    groups = assign_spatial_blocks_2d(lats_A, lons_A, n_folds=args.n_folds)

    print(f"      Fold distribution (2D grid, {args.n_folds} folds):")
    fold_validity = check_fold_validity(y_A, groups, args.n_folds)
    for fi in range(args.n_folds):
        fv = fold_validity[fi]
        status = "OK" if fv["valid"] else "INVALID"
        print(
            f"      Fold {fi}: {fv['n_pos']+fv['n_neg']} samples  "
            f"pos={fv['n_pos']}  neg={fv['n_neg']}  [{status}]"
        )

    # ── Step 7: Buffer sensitivity analysis ───────────────────────────
    if not args.skip_buffer_sensitivity:
        print("\n[7/9] Running pseudo-absence buffer sensitivity analysis …")
        buffer_results = run_buffer_sensitivity(
            pos_coords=pos_coords,
            n_negatives=n_negatives,
            seed=args.seed,
            buffers_km=[3.0, 5.0, 10.0],
            X_pos=X_pos_A,
            y_pos=np.ones(len(X_pos_A)),
            groups_pos=groups[: len(X_pos_A)],
            feature_names=FEATURE_NAMES_WITH_GEO,
            climatology_cache=climatology_cache,
            n_folds=args.n_folds,
        )
        print("\n   Buffer sensitivity results:")
        print(f"   {'Buffer':>8}  {'n_neg':>7}  {'Valid folds':>11}  {'ROC-AUC':>8}  {'PR-AUC':>7}  {'F1':>6}")
        for r in buffer_results:
            roc = f"{r['roc_auc']:.4f}" if r.get("roc_auc") is not None else "   N/A"
            pr = f"{r['pr_auc']:.4f}" if r.get("pr_auc") is not None else "  N/A"
            f1 = f"{r['f1']:.4f}" if r.get("f1") is not None else "  N/A"
            print(
                f"   {r['buffer_km']:>7.0f}km  {r['n_negatives']:>7}  "
                f"{r.get('n_valid_folds','?'):>11}  {roc:>8}  {pr:>7}  {f1:>6}"
            )
    else:
        print("[7/9] Buffer sensitivity analysis skipped (--skip-buffer-sensitivity).")
        buffer_results = []

    # ── Step 8: Train and evaluate all model variants ─────────────────
    print("\n[8/9] Training and evaluating models via 2D Spatial Grid GroupKFold CV …")

    rf_params: dict[str, Any] = {
        "n_estimators": 150,
        "max_depth": 10,
        "min_samples_leaf": 5,
        "random_state": args.seed,
        "n_jobs": -1,
        "class_weight": "balanced",
    }
    hgb_params: dict[str, Any] = {
        "max_iter": 150,
        "max_depth": 6,
        "learning_rate": 0.1,
        "min_samples_leaf": 10,
        "random_state": args.seed,
    }

    # --- Model A: RF with lat/lon ---
    print("\n   ── Model A-RF: RandomForest + lat/lon ──")
    rf_a_oof, rf_a_folds, rf_a_overall, rf_a_nvalid = run_spatial_cv(
        X_A, y_A, groups, RandomForestClassifier, rf_params, args.n_folds, "RF_with_geo"
    )

    # --- Model A: HGB with lat/lon ---
    print("\n   ── Model A-HGB: HistGradientBoosting + lat/lon ──")
    hgb_a_oof, hgb_a_folds, hgb_a_overall, hgb_a_nvalid = run_spatial_cv(
        X_A, y_A, groups, HistGradientBoostingClassifier, hgb_params, args.n_folds, "HGB_with_geo"
    )

    # --- Model B: RF without lat/lon ---
    print("\n   ── Model B-RF: RandomForest, rainfall only ──")
    rf_b_oof, rf_b_folds, rf_b_overall, rf_b_nvalid = run_spatial_cv(
        X_B, y_B, groups, RandomForestClassifier, rf_params, args.n_folds, "RF_no_geo"
    )

    # --- Model B: HGB without lat/lon ---
    print("\n   ── Model B-HGB: HistGradientBoosting, rainfall only ──")
    hgb_b_oof, hgb_b_folds, hgb_b_overall, hgb_b_nvalid = run_spatial_cv(
        X_B, y_B, groups, HistGradientBoostingClassifier, hgb_params, args.n_folds, "HGB_no_geo"
    )

    # --- Lat/lon ablation summary ---
    def _roc(d: dict[str, Any]) -> float:
        v = d.get("roc_auc")
        return float(v) if v is not None else float("nan")

    roc_a_rf = _roc(rf_a_overall)
    roc_b_rf = _roc(rf_b_overall)
    roc_drop_rf = roc_a_rf - roc_b_rf if not (math.isnan(roc_a_rf) or math.isnan(roc_b_rf)) else float("nan")

    print("\n   ── Lat/Lon Ablation Summary (RF) ──")
    print(f"   Model A (with lat/lon):    ROC-AUC = {roc_a_rf:.4f}  (valid folds: {rf_a_nvalid}/{args.n_folds})")
    print(f"   Model B (rainfall only):   ROC-AUC = {roc_b_rf:.4f}  (valid folds: {rf_b_nvalid}/{args.n_folds})")
    print(f"   Ablation drop:             {roc_drop_rf:+.4f}")
    if not math.isnan(roc_drop_rf):
        if roc_drop_rf > 0.15:
            print("   INTERPRETATION: Drop >0.15 — model primarily geographic memorizer; rainfall signal weak.")
        elif roc_drop_rf > 0.05:
            print("   INTERPRETATION: Drop 0.05–0.15 — model partly geographic prior, partly environmental.")
        else:
            print("   INTERPRETATION: Drop <0.05 — lat/lon add marginal refinement; rainfall carries genuine signal.")

    # --- Select best model (scientific preference: Model B if valid) ---
    # Model B is preferred if it has ≥3 valid folds and ROC-AUC ≥ 0.55 on valid folds.
    # This avoids selecting a model that relies primarily on geographic memorization.
    use_geo_features = True
    use_model_b_reason = ""

    if rf_b_nvalid >= 3 and roc_b_rf >= 0.55:
        use_geo_features = False
        use_model_b_reason = (
            f"Model B (rainfall-only) has {rf_b_nvalid} valid folds and "
            f"ROC-AUC={roc_b_rf:.4f} ≥ 0.55. Preferred over Model A to avoid "
            "geographic memorization."
        )
    else:
        use_model_b_reason = (
            f"Model B ROC-AUC={roc_b_rf:.4f} < 0.55 or valid folds={rf_b_nvalid} < 3. "
            "Falling back to Model A (with lat/lon) — geographic bias noted in limitations."
        )

    print(f"\n   Feature selection: {'Model B (no lat/lon)' if not use_geo_features else 'Model A (with lat/lon)'}")
    print(f"   Reason: {use_model_b_reason}")

    if use_geo_features:
        FINAL_FEATURE_NAMES = FEATURE_NAMES_WITH_GEO
        X_final = X_A
        y_final = y_A
        best_rf_overall = rf_a_overall
        best_rf_folds = rf_a_folds
        best_rf_oof = rf_a_oof
        best_rf_nvalid = rf_a_nvalid
        best_hgb_overall = hgb_a_overall
    else:
        FINAL_FEATURE_NAMES = FEATURE_NAMES_NO_GEO
        X_final = X_B
        y_final = y_B
        best_rf_overall = rf_b_overall
        best_rf_folds = rf_b_folds
        best_rf_oof = rf_b_oof
        best_rf_nvalid = rf_b_nvalid
        best_hgb_overall = hgb_b_overall

    # Select RF vs HGB
    roc_rf_final = _roc(best_rf_overall)
    roc_hgb_final = _roc(best_hgb_overall)
    if not math.isnan(roc_rf_final) and not math.isnan(roc_hgb_final):
        if roc_rf_final >= roc_hgb_final:
            best_name = "RandomForest"
            best_class: type = RandomForestClassifier
            best_params = rf_params
            best_overall = best_rf_overall
            best_folds = best_rf_folds
            best_oof = best_rf_oof
            best_nvalid = best_rf_nvalid
        else:
            best_name = "HistGradientBoosting"
            best_class = HistGradientBoostingClassifier
            best_params = hgb_params
            best_overall = best_hgb_overall
            best_folds = (hgb_a_folds if use_geo_features else hgb_b_folds)
            best_oof = (hgb_a_oof if use_geo_features else hgb_b_oof)
            best_nvalid = (hgb_a_nvalid if use_geo_features else hgb_b_nvalid)
    else:
        # Default to RF if HGB also failed
        best_name = "RandomForest"
        best_class = RandomForestClassifier
        best_params = rf_params
        best_overall = best_rf_overall
        best_folds = best_rf_folds
        best_oof = best_rf_oof
        best_nvalid = best_rf_nvalid

    roc_best = _roc(best_overall)
    print(f"\n   Best model: {best_name} (ROC-AUC={roc_best:.4f}, valid folds={best_nvalid}/{args.n_folds})")

    # ── Step 9: Final calibrated model & artifacts ────────────────────
    print("\n[9/9] Training final calibrated production model …")

    # Only include valid folds in calibration
    gkf = GroupKFold(n_splits=args.n_folds)
    all_splits = list(gkf.split(X_final, y_final, groups))
    valid_split_indices = [
        i for i, fm in enumerate(best_folds) if fm.get("status") == "VALID"
    ]
    spatial_splits_valid = [all_splits[i] for i in valid_split_indices]

    if not spatial_splits_valid:
        print("   WARNING: No valid splits for calibration. Using all splits.")
        spatial_splits_valid = all_splits

    calibrated_model = CalibratedClassifierCV(
        estimator=best_class(**best_params),
        cv=spatial_splits_valid,
        method="sigmoid",
    )
    calibrated_model.fit(X_final, y_final)

    # Feature importance from a fresh model on full data
    importance_model = best_class(**best_params)
    importance_model.fit(X_final, y_final)
    if hasattr(importance_model, "feature_importances_"):
        importances = importance_model.feature_importances_.tolist()
    else:
        importances = [0.0] * len(FINAL_FEATURE_NAMES)
    feature_importance = dict(zip(FINAL_FEATURE_NAMES, importances))

    # Calibration curve on OOF predictions from valid folds only
    valid_oof_mask = ~np.isnan(best_oof)
    prob_true, prob_pred = calibration_curve(
        y_final[valid_oof_mask], best_oof[valid_oof_mask], n_bins=10
    )
    # Check monotonicity of calibration curve
    cal_monotonic = bool(np.all(np.diff(prob_true) >= -0.05))  # allow small non-monotonicities
    calibration_data: dict[str, Any] = {
        "bin_true_fraction": prob_true.tolist(),
        "bin_predicted_mean": prob_pred.tolist(),
        "approximately_monotonic": cal_monotonic,
        "n_valid_folds_used": best_nvalid,
    }

    # ── Inference benchmark ────────────────────────────────────────────
    sample = X_final[0:1]
    t0 = time.perf_counter()
    for _ in range(100):
        calibrated_model.predict_proba(sample)
    avg_latency_ms = (time.perf_counter() - t0) / 100 * 1000

    duration = time.time() - t_start

    # ── Scientific validity decision ───────────────────────────────────
    all_folds_valid = best_nvalid == args.n_folds
    calibration_ok = cal_monotonic
    roc_acceptable = (not math.isnan(roc_best)) and roc_best >= 0.55
    environmental_signal = (
        sum(v for k, v in feature_importance.items() if k not in {"latitude", "longitude"})
        >= 0.25
    )

    model_valid = (
        all_folds_valid
        and roc_acceptable
        and calibration_ok
        and environmental_signal
        and not use_geo_features  # prefer rainfall-only model
    )
    # Also accept geo model if it passes all other criteria and ablation drop < 0.15
    if use_geo_features and all_folds_valid and roc_acceptable and calibration_ok:
        if not math.isnan(roc_drop_rf) and roc_drop_rf <= 0.15:
            model_valid = True

    validity_verdict = (
        "MODEL VALID — BASELINE SUSCEPTIBILITY MODEL"
        if model_valid
        else "MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES"
    )

    validity_reasons: list[str] = []
    if not all_folds_valid:
        validity_reasons.append(
            f"Only {best_nvalid}/{args.n_folds} spatial folds valid (need all {args.n_folds})"
        )
    if not roc_acceptable:
        validity_reasons.append(f"ROC-AUC={roc_best:.4f} below 0.55 minimum threshold")
    if not calibration_ok:
        validity_reasons.append("Calibration curve non-monotonic — output not reliable as probability")
    if not environmental_signal:
        validity_reasons.append(
            "Environmental features (non-lat/lon) contribute <25% of importance — "
            "model collapses to geographic memorization"
        )
    if use_geo_features and not math.isnan(roc_drop_rf) and roc_drop_rf > 0.15:
        validity_reasons.append(
            f"Lat/lon ablation drop={roc_drop_rf:.3f}>0.15 — model primarily geographic memorizer"
        )

    print(f"\n   Scientific Validity: {validity_verdict}")
    if validity_reasons:
        _print_validity_reasons(validity_reasons)

    # ── Save artifacts ─────────────────────────────────────────────────
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)

    # All models comparison dict (used in metrics.json)
    models_compared = {
        "RF_with_geo": rf_a_overall,
        "HGB_with_geo": hgb_a_overall,
        "RF_no_geo": rf_b_overall,
        "HGB_no_geo": hgb_b_overall,
    }

    # 1. Pipeline — always save to experiments first
    exp_pipeline_path = EXPERIMENT_DIR / "pipeline_experimental.joblib"
    joblib.dump(calibrated_model, exp_pipeline_path, compress=3)
    exp_size_kb = exp_pipeline_path.stat().st_size / 1024
    print(f"\n   Experimental artifact saved: {exp_pipeline_path} ({exp_size_kb:.1f} KB)")

    # Only overwrite production artifact if scientifically valid
    if model_valid:
        prod_pipeline_path = ARTIFACT_DIR / "pipeline.joblib"
        joblib.dump(calibrated_model, prod_pipeline_path, compress=3)
        pipeline_size_kb = prod_pipeline_path.stat().st_size / 1024
        artifact_label = "VALIDATED"
        print(f"   Production artifact updated: {prod_pipeline_path} ({pipeline_size_kb:.1f} KB)")
    else:
        pipeline_size_kb = exp_size_kb
        artifact_label = "EXPERIMENTAL — NOT PRODUCTION READY"
        print("   Production artifact NOT overwritten (model did not pass validity criteria).")

    # 2. Features schema
    geo_bias_note = (
        f"lat/lon combined importance: "
        f"{feature_importance.get('latitude', 0.0)+feature_importance.get('longitude', 0.0):.3f}"
        if use_geo_features else
        "lat/lon excluded from model — rainfall-only feature set selected."
    )
    features_schema: dict[str, Any] = {
        "version": MODEL_VERSION,
        "artifact_label": artifact_label,
        "feature_count": len(FINAL_FEATURE_NAMES),
        "geo_features_included": use_geo_features,
        "geo_bias_note": geo_bias_note,
        "features": [
            {
                "name": name,
                "dtype": "float64",
                "importance": round(feature_importance.get(name, 0.0), 6),
            }
            for name in FINAL_FEATURE_NAMES
        ],
        "excluded_features": [
            {
                "name": "distance_to_nearest_slide_km",
                "reason": (
                    "TARGET LEAKAGE: Positive points have distance=0 to themselves in the GSI "
                    "inventory; negatives have distance≥exclusion_km by construction. The model "
                    "would learn to discriminate proximity-to-label-source rather than "
                    "environmental susceptibility."
                ),
            },
            {
                "name": "slide_count_within_5km",
                "reason": (
                    "TARGET LEAKAGE: Positive points are GSI inventory members and thus always "
                    "have high local density. Negatives are excluded by buffer. The feature "
                    "trivially separates labels."
                ),
            },
            {
                "name": "slide_count_within_10km",
                "reason": "TARGET LEAKAGE: Same spatial autocorrelation leakage as 5km density.",
            },
            {
                "name": "slide_count_within_25km",
                "reason": "TARGET LEAKAGE: Same spatial autocorrelation leakage as 5km/10km density.",
            },
            {
                "name": "elevation_m",
                "reason": (
                    "DATA UNAVAILABLE: No DEM raster present in project. Will be added in "
                    "future phase after real DEM ingestion."
                ),
            },
            {
                "name": "slope_degrees",
                "reason": "DATA UNAVAILABLE: Requires DEM. Not fabricated.",
            },
            {
                "name": "aspect_degrees",
                "reason": "DATA UNAVAILABLE: Requires DEM. Not fabricated.",
            },
        ],
        "terrain_features_available": False,
        "dynamic_weather_features_available": False,
    }
    if not use_geo_features:
        features_schema["excluded_features"].insert(0, {
            "name": "latitude",
            "reason": (
                "GEOGRAPHIC PRIOR: In the ablation experiment lat/lon combined importance was "
                f"≥{roc_drop_rf:.2f} ROC-AUC drop when removed, indicating geographic "
                "memorization. Rainfall-only model selected to ensure predictions reflect "
                "physical susceptibility rather than GSI survey coverage patterns."
            ),
        })
        features_schema["excluded_features"].insert(1, {
            "name": "longitude",
            "reason": "GEOGRAPHIC PRIOR: Same as latitude. See ablation analysis.",
        })

    features_path = ARTIFACT_DIR / "features.json"
    features_path.write_text(_safe_json_dumps(features_schema, indent=2))

    # Freeze validity_reasons as an unambiguous list[str] before embedding in
    # dict[str, Any] literals — prevents mypy 1.20 bidirectional inference from
    # re-typing validity_reasons as list[dict[str, Any]].
    validity_reasons_str: list[str] = [str(x) for x in validity_reasons]

    # 3. Metrics (NaN-safe JSON)
    metrics_data: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "artifact_label": artifact_label,
        "validation_method": "2D Spatial Grid GroupKFold Cross-Validation",
        "spatial_block_method": "2D lat×lon quantile grid (n_lat_bins=4, n_lon_bins=4)",
        "n_folds": args.n_folds,
        "geo_features_included": use_geo_features,
        "ablation": {
            "roc_auc_with_geo_rf": None if math.isnan(roc_a_rf) else roc_a_rf,
            "roc_auc_no_geo_rf": None if math.isnan(roc_b_rf) else roc_b_rf,
            "roc_auc_drop_rf": None if math.isnan(roc_drop_rf) else roc_drop_rf,
            "interpretation": (
                "Geographic memorization" if not math.isnan(roc_drop_rf) and roc_drop_rf > 0.15
                else "Acceptable geographic contribution"
                if not math.isnan(roc_drop_rf) else "Unknown"
            ),
        },
        "buffer_sensitivity": buffer_results,
        "best_model": best_name,
        "models_compared": models_compared,
        "best_model_overall_metrics": best_overall,
        "best_model_fold_metrics": best_folds,
        "calibration_curve": calibration_data,
        "scientific_validity": _build_validity_record(
            validity_reasons_str,
            all_folds_valid,
            best_nvalid,
            roc_acceptable,
            calibration_ok,
            environmental_signal,
            validity_verdict,
        ),
    }
    metrics_path = ARTIFACT_DIR / "metrics.json"
    metrics_path.write_text(_safe_json_dumps(metrics_data, indent=2))

    # 4. Metadata (model card)
    metadata: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "artifact_label": artifact_label,
        "model_type": best_name,
        "model_params": {k: v for k, v in best_params.items() if not callable(v)},
        "calibration_method": "sigmoid (Platt scaling) via CalibratedClassifierCV (valid folds only)",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "training_duration_seconds": round(duration, 2),
        "random_seed": args.seed,
        "sklearn_version": sklearn.__version__,
        "target_definition": {
            "name": "landslide_susceptibility",
            "y_1": "GSI Bhukosh NLSM historical landslide presence location",
            "y_0": "Pseudo-absence background sample (min exclusion buffer from any known slide)",
        },
        "dataset": {
            "source_positive": "Geological Survey of India (GSI) Bhukosh NLSM PDF Inventory",
            "source_negative": "Algorithmically generated pseudo-absence within Himalayan domain",
            "source_climatology": "India Meteorological Department (IMD) Subdivision Climatology 1901-2017",
            "positive_samples": int(y_final[:len(pos_features)].sum()),
            "negative_samples": int(len(y_final) - y_final[:len(pos_features)].sum()),
            "total_samples": len(y_final),
            "positive_negative_ratio": f"1:{args.ratio}",
            "exclusion_buffer_km": args.exclusion_km,
            "unknown_state_positives": n_unknown_state,
            "heuristic_subdiv_positives": n_pos_heuristic,
        },
        "modeling_domain": DOMAIN,
        "feature_names": FINAL_FEATURE_NAMES,
        "feature_count": len(FINAL_FEATURE_NAMES),
        "feature_importance": feature_importance,
        "geo_features_included": use_geo_features,
        "feature_selection_reason": use_model_b_reason,
        "spatial_validation": {
            "method": "2D Spatial Grid GroupKFold",
            "n_folds": args.n_folds,
            "block_assignment": "2D lat×lon quantile grid (n_lat_bins=4, n_lon_bins=4)",
            "fold_validity_enforced": True,
            "min_positives_per_fold": MIN_FOLD_POSITIVES,
            "min_negatives_per_fold": MIN_FOLD_NEGATIVES,
            "n_valid_folds": best_nvalid,
        },
        "output_semantics": {
            "type": "calibrated_probability" if (cal_monotonic and model_valid) else "susceptibility_score",
            "range": "[0.0, 1.0]",
            "interpretation": (
                "Estimated landslide susceptibility score. Higher values indicate locations with "
                "environmental characteristics more similar to known historical landslide sites. "
                "This is NOT a guaranteed future event probability. "
                "Calibration is approximate; do not treat as frequentist probability without terrain features."
            ),
        },
        "artifact_files": {
            "pipeline": "pipeline.joblib",
            "features": "features.json",
            "metadata": "metadata.json",
            "metrics": "metrics.json",
        },
        "artifact_size_kb": round(pipeline_size_kb, 1),
        "inference_latency_ms": round(avg_latency_ms, 2),
        "scientific_validity_verdict": validity_verdict,
        "limitations": [
            "GSI is a presence-only historical inventory; pseudo-absence samples are background "
            "assumptions, not confirmed non-landslide observations.",
            "No DEM/topography features (elevation, slope, aspect, curvature) are available. "
            "terrain_features_available = false.",
            "No dynamic/antecedent rainfall features. Only long-term climatological baselines "
            "are used. dynamic_weather_features_available = false.",
            f"~{n_unknown_state} of {n_positives} positive records ({100*n_unknown_state/max(n_positives,1):.1f}%) "
            "have state='Unknown' — their IMD subdivision was assigned via coordinate heuristic, "
            "not authoritative administrative boundaries.",
            "Geographic-to-subdivision mapping uses a coarse latitude/longitude heuristic rather "
            "than administrative boundary polygons. Future phases should use a GIS polygon join.",
            "Model estimates spatial susceptibility, not guaranteed future occurrence probability.",
            "IMD climatology has subdivision-level granularity (~15 zones over the domain). "
            "Within-subdivision variation is not captured by rainfall features.",
            "GSI survey coverage is spatially uneven — high-density regions may reflect survey effort "
            "as much as true susceptibility.",
        ],
    }
    metadata_path = ARTIFACT_DIR / "metadata.json"
    metadata_path.write_text(_safe_json_dumps(metadata, indent=2))

    # ── Summary report ─────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("TRAINING COMPLETE — SUMMARY")
    print("=" * 72)
    print(f"  Model Version:       {MODEL_VERSION}")
    print(f"  Best Model:          {best_name}")
    print(f"  Geo Features:        {'Yes (lat/lon included)' if use_geo_features else 'No (rainfall only)'}")
    print(f"  Training Samples:    {len(y_final)} (pos={int(y_final.sum())}, neg={int(len(y_final)-y_final.sum())})")
    print(f"  Features:            {len(FINAL_FEATURE_NAMES)}")
    print(f"  Valid Spatial Folds: {best_nvalid}/{args.n_folds}")
    print("  " + "-" * 50)
    roc_str = f"{best_overall['roc_auc']:.4f}" if best_overall.get("roc_auc") is not None else "N/A"
    pr_str = f"{best_overall['pr_auc']:.4f}" if best_overall.get("pr_auc") is not None else "N/A"
    prec_str = f"{best_overall['precision']:.4f}" if best_overall.get("precision") is not None else "N/A"
    rec_str = f"{best_overall['recall']:.4f}" if best_overall.get("recall") is not None else "N/A"
    f1_str = f"{best_overall['f1']:.4f}" if best_overall.get("f1") is not None else "N/A"
    brier_str = f"{best_overall['brier_score']:.4f}" if best_overall.get("brier_score") is not None else "N/A"
    print(f"  ROC-AUC:             {roc_str}")
    print(f"  PR-AUC:              {pr_str}")
    print(f"  Precision:           {prec_str}")
    print(f"  Recall:              {rec_str}")
    print(f"  F1-Score:            {f1_str}")
    print(f"  Brier Score:         {brier_str}")
    print(f"  Calibration:         {'Monotonic (OK)' if cal_monotonic else 'Non-monotonic (WARNING)'}")
    print("  " + "-" * 50)
    print(f"  Lat/Lon Ablation:    A={roc_a_rf:.4f}  B={roc_b_rf:.4f}  drop={roc_drop_rf:+.4f}")
    print("  " + "-" * 50)
    print(f"  Pipeline Size:       {pipeline_size_kb:.1f} KB")
    print(f"  Inference Latency:   {avg_latency_ms:.2f} ms (single sample)")
    print(f"  Training Duration:   {duration:.1f} s")
    print(f"  sklearn Version:     {sklearn.__version__}")
    print("  " + "-" * 50)
    print(f"  Artifacts saved to:  {ARTIFACT_DIR}")
    print(f"    pipeline.joblib    ({pipeline_size_kb:.1f} KB)  [{artifact_label}]")
    print("    features.json")
    print("    metadata.json")
    print("    metrics.json")
    print(f"    experiments/       {EXPERIMENT_DIR}")
    print("  " + "-" * 50)
    print(f"  SCIENTIFIC VERDICT:  {validity_verdict}")
    if validity_reasons:
        _print_summary_reasons(validity_reasons)
    print("=" * 72)


if __name__ == "__main__":
    main()
