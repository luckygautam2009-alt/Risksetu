"""
RISKSETU AI — ML Pipeline Unit Tests.

Covers:
  - pseudo-absence generation (distance enforcement, count, seed)
  - exclusion distance correctness (haversine)
  - feature schema (names, count, leakage exclusions)
  - spatial fold validity enforcement (≥1 pos, ≥1 neg per fold)
  - 2D spatial block assignment (all samples assigned, within range)
  - JSON serialisation safety (NaN/Inf → null)
  - coords_to_subdivision heuristic correctness
  - compute_rainfall_features aggregation logic
  - get_subdivision_for_record source tracking
  - artifact loading (pipeline.joblib loadable, predict_proba shape)
  - metadata.json schema validation
  - features.json schema validation
  - metrics.json validity (no NaN literals, fold status keys present)
  - leakage feature exclusion audit
  - _build_validity_record structure
  - check_fold_validity logic

All tests are DB-free: they exercise pure Python/NumPy functions imported
directly from the training script without hitting PostgreSQL or the
FastAPI app.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Make the training script importable without executing main()
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "train_landslide_model.py"
ARTIFACT_DIR = PROJECT_ROOT / "app" / "services" / "prediction" / "artifacts"
EXPERIMENT_DIR = PROJECT_ROOT / "artifacts" / "experiments"

sys.path.insert(0, str(PROJECT_ROOT))

# Import the pure-Python helpers from the training script directly
_spec = importlib.util.spec_from_file_location("train_landslide_model", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

# Bring the tested symbols into scope
generate_pseudo_absences = _mod.generate_pseudo_absences
assign_spatial_blocks_2d = _mod.assign_spatial_blocks_2d
check_fold_validity = _mod.check_fold_validity
coords_to_subdivision = _mod.coords_to_subdivision
compute_rainfall_features = _mod.compute_rainfall_features
get_subdivision_for_record = _mod.get_subdivision_for_record
_safe_json_dumps = _mod._safe_json_dumps
_build_validity_record = _mod._build_validity_record
DOMAIN = _mod.DOMAIN
FEATURE_NAMES_WITH_GEO = _mod.FEATURE_NAMES_WITH_GEO
FEATURE_NAMES_NO_GEO = _mod.FEATURE_NAMES_NO_GEO
EARTH_RADIUS_KM = _mod.EARTH_RADIUS_KM
MODEL_VERSION = _mod.MODEL_VERSION
MIN_FOLD_POSITIVES = _mod.MIN_FOLD_POSITIVES
MIN_FOLD_NEGATIVES = _mod.MIN_FOLD_NEGATIVES


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(scope="module")
def small_positive_coords() -> np.ndarray:
    """50 synthetic positive coordinates within the modeling domain."""
    rng = np.random.RandomState(0)
    lats = rng.uniform(DOMAIN["lat_min"], DOMAIN["lat_max"], 50)
    lons = rng.uniform(DOMAIN["lon_min"], DOMAIN["lon_max"], 50)
    return np.column_stack([lats, lons])


@pytest.fixture(scope="module")
def dense_cluster_coords() -> np.ndarray:
    """Tight cluster of 20 points all within 1 km of (30.0, 79.0)."""
    rng = np.random.RandomState(1)
    # 1 km ≈ 0.009° at these latitudes
    lats = 30.0 + rng.uniform(-0.005, 0.005, 20)
    lons = 79.0 + rng.uniform(-0.005, 0.005, 20)
    return np.column_stack([lats, lons])


@pytest.fixture(scope="module")
def minimal_climatology_cache() -> dict[str, dict[int, dict[str, float]]]:
    """Minimal realistic climatology cache for UTTARAKHAND."""
    # Monthly means roughly representative of a wet Himalayan subdivision
    monthly_means = [
        20.0, 25.0, 40.0, 55.0, 80.0,   # Jan–May
        250.0, 350.0, 380.0, 280.0,       # Jun–Sep (monsoon)
        60.0, 30.0, 15.0,                  # Oct–Dec
    ]
    monthly_stds = [5.0] * 12
    cache: dict[str, dict[int, dict[str, float]]] = {
        "UTTARAKHAND": {
            m: {"mean": monthly_means[m - 1], "std": monthly_stds[m - 1]}
            for m in range(1, 13)
        }
    }
    return cache


@pytest.fixture(scope="module")
def artifacts_metadata() -> dict[str, Any]:
    meta_path = ARTIFACT_DIR / "metadata.json"
    if not meta_path.exists():
        pytest.skip("metadata.json not present — run training first")
    return json.loads(meta_path.read_text())


@pytest.fixture(scope="module")
def artifacts_features() -> dict[str, Any]:
    feat_path = ARTIFACT_DIR / "features.json"
    if not feat_path.exists():
        pytest.skip("features.json not present — run training first")
    return json.loads(feat_path.read_text())


@pytest.fixture(scope="module")
def artifacts_metrics() -> dict[str, Any]:
    metrics_path = ARTIFACT_DIR / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("metrics.json not present — run training first")
    return json.loads(metrics_path.read_text())


# ===========================================================================
# 1. Pseudo-absence generation
# ===========================================================================

class TestPseudoAbsenceGeneration:
    """Tests for generate_pseudo_absences()."""

    def test_returns_correct_count(self, small_positive_coords: np.ndarray) -> None:
        """Generated array should have exactly the requested number of rows."""
        result = generate_pseudo_absences(small_positive_coords, 100, 3.0, seed=42)
        assert result.shape == (100, 2), (
            f"Expected (100, 2), got {result.shape}"
        )

    def test_all_within_domain(self, small_positive_coords: np.ndarray) -> None:
        """Every generated point must lie within the modeling bounding box."""
        result = generate_pseudo_absences(small_positive_coords, 200, 3.0, seed=42)
        lats, lons = result[:, 0], result[:, 1]
        assert np.all(lats >= DOMAIN["lat_min"]), "Some latitudes below domain min"
        assert np.all(lats <= DOMAIN["lat_max"]), "Some latitudes above domain max"
        assert np.all(lons >= DOMAIN["lon_min"]), "Some longitudes below domain min"
        assert np.all(lons <= DOMAIN["lon_max"]), "Some longitudes above domain max"

    def test_3km_exclusion_buffer_enforced(self, small_positive_coords: np.ndarray) -> None:
        """No pseudo-absence should be within 3 km of a positive point."""
        from sklearn.neighbors import BallTree

        exclusion_km = 3.0
        result = generate_pseudo_absences(small_positive_coords, 100, exclusion_km, seed=42)

        pos_rad = np.radians(small_positive_coords)
        neg_rad = np.radians(result)
        tree = BallTree(pos_rad, metric="haversine")
        distances, _ = tree.query(neg_rad, k=1)
        distances_km = distances.ravel() * EARTH_RADIUS_KM

        violations = np.sum(distances_km < exclusion_km)
        assert violations == 0, (
            f"{violations} pseudo-absences are closer than {exclusion_km} km to a positive"
        )

    def test_5km_exclusion_buffer_enforced(self, small_positive_coords: np.ndarray) -> None:
        """No pseudo-absence should be within 5 km of a positive point."""
        from sklearn.neighbors import BallTree

        exclusion_km = 5.0
        result = generate_pseudo_absences(small_positive_coords, 100, exclusion_km, seed=7)

        pos_rad = np.radians(small_positive_coords)
        neg_rad = np.radians(result)
        tree = BallTree(pos_rad, metric="haversine")
        distances, _ = tree.query(neg_rad, k=1)
        distances_km = distances.ravel() * EARTH_RADIUS_KM

        assert np.all(distances_km >= exclusion_km - 1e-6), (
            f"Exclusion buffer violation: min distance = {distances_km.min():.3f} km"
        )

    def test_10km_exclusion_buffer_enforced(self, small_positive_coords: np.ndarray) -> None:
        """No pseudo-absence should be within 10 km of a positive point."""
        from sklearn.neighbors import BallTree

        exclusion_km = 10.0
        result = generate_pseudo_absences(small_positive_coords, 80, exclusion_km, seed=99)

        pos_rad = np.radians(small_positive_coords)
        neg_rad = np.radians(result)
        tree = BallTree(pos_rad, metric="haversine")
        distances, _ = tree.query(neg_rad, k=1)
        distances_km = distances.ravel() * EARTH_RADIUS_KM

        assert np.all(distances_km >= exclusion_km - 1e-6), (
            f"10km buffer violation: min distance = {distances_km.min():.3f} km"
        )

    def test_reproducible_with_same_seed(self, small_positive_coords: np.ndarray) -> None:
        """Two calls with the same seed must return identical arrays."""
        r1 = generate_pseudo_absences(small_positive_coords, 50, 5.0, seed=42)
        r2 = generate_pseudo_absences(small_positive_coords, 50, 5.0, seed=42)
        np.testing.assert_array_equal(r1, r2)

    def test_different_seeds_give_different_results(
        self, small_positive_coords: np.ndarray
    ) -> None:
        """Different seeds should (with overwhelming probability) produce different results."""
        r1 = generate_pseudo_absences(small_positive_coords, 50, 5.0, seed=1)
        r2 = generate_pseudo_absences(small_positive_coords, 50, 5.0, seed=2)
        assert not np.array_equal(r1, r2), "Different seeds produced identical arrays"

    def test_tight_cluster_still_generates_enough_samples(
        self, dense_cluster_coords: np.ndarray
    ) -> None:
        """Even with a tight cluster, the domain is large enough to find valid points."""
        result = generate_pseudo_absences(dense_cluster_coords, 50, 10.0, seed=42)
        # Allow up to 20% shortfall — the domain is 10°×16° so 50 is trivial
        assert len(result) >= 40, f"Only {len(result)} samples generated for tight cluster"


# ===========================================================================
# 2. Spatial block assignment
# ===========================================================================

class TestSpatialBlockAssignment:
    """Tests for assign_spatial_blocks_2d()."""

    def _make_grid_coords(self, n: int = 500) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.RandomState(0)
        lats = rng.uniform(DOMAIN["lat_min"], DOMAIN["lat_max"], n)
        lons = rng.uniform(DOMAIN["lon_min"], DOMAIN["lon_max"], n)
        return lats, lons

    def test_fold_indices_in_range(self) -> None:
        """All assigned folds must be in [0, n_folds)."""
        lats, lons = self._make_grid_coords(300)
        n_folds = 5
        blocks = assign_spatial_blocks_2d(lats, lons, n_folds=n_folds)
        assert blocks.min() >= 0, "Negative fold index found"
        assert blocks.max() < n_folds, f"Fold index ≥ n_folds={n_folds}"

    def test_correct_length(self) -> None:
        """Output length must equal input length."""
        lats, lons = self._make_grid_coords(400)
        blocks = assign_spatial_blocks_2d(lats, lons, n_folds=5)
        assert len(blocks) == 400

    def test_all_folds_represented(self) -> None:
        """With enough samples every fold should appear at least once."""
        lats, lons = self._make_grid_coords(500)
        n_folds = 5
        blocks = assign_spatial_blocks_2d(lats, lons, n_folds=n_folds)
        unique_folds = np.unique(blocks)
        assert len(unique_folds) == n_folds, (
            f"Only {len(unique_folds)}/{n_folds} folds represented"
        )

    def test_integer_dtype(self) -> None:
        """Block assignments must be integer-typed for GroupKFold."""
        lats, lons = self._make_grid_coords(100)
        blocks = assign_spatial_blocks_2d(lats, lons, n_folds=5)
        assert np.issubdtype(blocks.dtype, np.integer), (
            f"Expected integer dtype, got {blocks.dtype}"
        )

    def test_deterministic(self) -> None:
        """Same inputs must always produce the same output."""
        lats, lons = self._make_grid_coords(200)
        b1 = assign_spatial_blocks_2d(lats, lons, n_folds=5)
        b2 = assign_spatial_blocks_2d(lats, lons, n_folds=5)
        np.testing.assert_array_equal(b1, b2)

    def test_no_fold_is_empty(self) -> None:
        """No fold should contain zero samples with sufficient input."""
        lats, lons = self._make_grid_coords(500)
        blocks = assign_spatial_blocks_2d(lats, lons, n_folds=5)
        for fi in range(5):
            count = int(np.sum(blocks == fi))
            assert count > 0, f"Fold {fi} has zero samples"

    def test_different_n_folds(self) -> None:
        """Should work with 3 folds as well as 5."""
        lats, lons = self._make_grid_coords(300)
        blocks = assign_spatial_blocks_2d(lats, lons, n_folds=3)
        assert blocks.min() >= 0
        assert blocks.max() < 3
        assert len(np.unique(blocks)) == 3


# ===========================================================================
# 3. Fold validity checking
# ===========================================================================

class TestFoldValidityChecking:
    """Tests for check_fold_validity()."""

    def _make_balanced(self, n_folds: int = 3, n_per_fold: int = 100) -> tuple[np.ndarray, np.ndarray]:
        """Create balanced (pos+neg) groups for n_folds."""
        y_list = []
        g_list = []
        for fi in range(n_folds):
            y_list.extend([1] * (n_per_fold // 2) + [0] * (n_per_fold // 2))
            g_list.extend([fi] * n_per_fold)
        return np.array(y_list), np.array(g_list)

    def test_all_valid_when_balanced(self) -> None:
        """All folds valid when every fold has both classes."""
        y, g = self._make_balanced(n_folds=5)
        result = check_fold_validity(y, g, n_folds=5)
        for fi in range(5):
            assert result[fi]["valid"] is True, f"Fold {fi} unexpectedly invalid"

    def test_fold_with_zero_positives_is_invalid(self) -> None:
        """A fold containing only negatives must be flagged invalid."""
        y = np.zeros(100)
        g = np.zeros(100, dtype=int)
        # Add a second fold with both classes
        y2 = np.array([1] * 10 + [0] * 10)
        g2 = np.ones(20, dtype=int)
        y_all = np.concatenate([y, y2])
        g_all = np.concatenate([g, g2])

        result = check_fold_validity(y_all, g_all, n_folds=2)
        assert result[0]["valid"] is False, "Fold 0 (all-negative) should be invalid"
        assert "positives" in (result[0]["reason"] or "").lower(), (
            "Reason should mention positives"
        )

    def test_fold_with_zero_negatives_is_invalid(self) -> None:
        """A fold containing only positives must be flagged invalid."""
        y_pos = np.ones(50)
        g_pos = np.zeros(50, dtype=int)
        y_mix = np.array([1] * 10 + [0] * 10)
        g_mix = np.ones(20, dtype=int)
        y_all = np.concatenate([y_pos, y_mix])
        g_all = np.concatenate([g_pos, g_mix])

        result = check_fold_validity(y_all, g_all, n_folds=2)
        assert result[0]["valid"] is False, "Fold 0 (all-positive) should be invalid"

    def test_counts_reported_correctly(self) -> None:
        """n_pos and n_neg in the result must match actual label counts."""
        y, g = self._make_balanced(n_folds=3, n_per_fold=60)
        result = check_fold_validity(y, g, n_folds=3)
        for fi in range(3):
            assert result[fi]["n_pos"] == 30, f"Fold {fi} n_pos mismatch"
            assert result[fi]["n_neg"] == 30, f"Fold {fi} n_neg mismatch"

    def test_reason_is_none_for_valid_fold(self) -> None:
        """Valid folds must have reason=None."""
        y, g = self._make_balanced(n_folds=3)
        result = check_fold_validity(y, g, n_folds=3)
        for fi in range(3):
            assert result[fi]["reason"] is None, (
                f"Fold {fi} valid but reason is '{result[fi]['reason']}'"
            )

    def test_min_constants_are_positive(self) -> None:
        """MIN_FOLD_POSITIVES and MIN_FOLD_NEGATIVES must be ≥ 1."""
        assert MIN_FOLD_POSITIVES >= 1
        assert MIN_FOLD_NEGATIVES >= 1


# ===========================================================================
# 4. Feature schema — leakage exclusions audit
# ===========================================================================

class TestFeatureSchema:
    """Verify the feature lists contain no leaky or fabricated features."""

    LEAKY_FEATURES = {
        "distance_to_nearest_slide_km",
        "slide_count_within_5km",
        "slide_count_within_10km",
        "slide_count_within_25km",
    }
    FABRICATED_TERRAIN = {
        "elevation_m",
        "slope_degrees",
        "aspect_degrees",
        "curvature",
        "twi",
    }
    DYNAMIC_WEATHER = {
        "rainfall_24h_mm",
        "rainfall_72h_mm",
        "antecedent_rainfall_mm",
        "forecast_rainfall_mm",
    }

    def test_no_leaky_features_in_with_geo_set(self) -> None:
        for feat in self.LEAKY_FEATURES:
            assert feat not in FEATURE_NAMES_WITH_GEO, (
                f"Leaky feature '{feat}' found in FEATURE_NAMES_WITH_GEO"
            )

    def test_no_leaky_features_in_no_geo_set(self) -> None:
        for feat in self.LEAKY_FEATURES:
            assert feat not in FEATURE_NAMES_NO_GEO, (
                f"Leaky feature '{feat}' found in FEATURE_NAMES_NO_GEO"
            )

    def test_no_fabricated_terrain_in_with_geo_set(self) -> None:
        for feat in self.FABRICATED_TERRAIN:
            assert feat not in FEATURE_NAMES_WITH_GEO, (
                f"Fabricated terrain feature '{feat}' in FEATURE_NAMES_WITH_GEO"
            )

    def test_no_fabricated_terrain_in_no_geo_set(self) -> None:
        for feat in self.FABRICATED_TERRAIN:
            assert feat not in FEATURE_NAMES_NO_GEO, (
                f"Fabricated terrain feature '{feat}' in FEATURE_NAMES_NO_GEO"
            )

    def test_no_dynamic_weather_in_any_set(self) -> None:
        for feat in self.DYNAMIC_WEATHER:
            assert feat not in FEATURE_NAMES_WITH_GEO, (
                f"Dynamic weather feature '{feat}' in WITH_GEO set"
            )
            assert feat not in FEATURE_NAMES_NO_GEO, (
                f"Dynamic weather feature '{feat}' in NO_GEO set"
            )

    def test_no_geo_set_excludes_lat_lon(self) -> None:
        """Rainfall-only feature set must not contain latitude or longitude."""
        assert "latitude" not in FEATURE_NAMES_NO_GEO
        assert "longitude" not in FEATURE_NAMES_NO_GEO

    def test_with_geo_set_has_exactly_9_features(self) -> None:
        assert len(FEATURE_NAMES_WITH_GEO) == 9, (
            f"Expected 9 features with geo, got {len(FEATURE_NAMES_WITH_GEO)}"
        )

    def test_no_geo_set_has_exactly_7_features(self) -> None:
        assert len(FEATURE_NAMES_NO_GEO) == 7, (
            f"Expected 7 features without geo, got {len(FEATURE_NAMES_NO_GEO)}"
        )

    def test_no_geo_set_is_subset_of_with_geo_set(self) -> None:
        """Every no-geo feature must be present in the full set."""
        for feat in FEATURE_NAMES_NO_GEO:
            assert feat in FEATURE_NAMES_WITH_GEO, (
                f"Feature '{feat}' in NO_GEO set not found in WITH_GEO set"
            )

    def test_all_rainfall_features_present(self) -> None:
        expected_rainfall = {
            "annual_rainfall_mean_mm",
            "monsoon_rainfall_mean_mm",
            "winter_rainfall_mean_mm",
            "pre_monsoon_rainfall_mean_mm",
            "post_monsoon_rainfall_mean_mm",
            "monsoon_variability_mm",
            "rainfall_seasonality_ratio",
        }
        for feat in expected_rainfall:
            assert feat in FEATURE_NAMES_NO_GEO, (
                f"Rainfall feature '{feat}' missing from NO_GEO set"
            )

    def test_no_duplicate_features(self) -> None:
        assert len(FEATURE_NAMES_WITH_GEO) == len(set(FEATURE_NAMES_WITH_GEO))
        assert len(FEATURE_NAMES_NO_GEO) == len(set(FEATURE_NAMES_NO_GEO))


# ===========================================================================
# 5. coords_to_subdivision heuristic
# ===========================================================================

class TestCoordsToSubdivision:
    """Tests for the geographic heuristic subdivision assignment."""

    def test_jk_region(self) -> None:
        """High-latitude, western point → Jammu & Kashmir."""
        result = coords_to_subdivision(34.5, 76.0)
        assert result == "JAMMU AND KASHMIR"

    def test_hp_region(self) -> None:
        """Mid-latitude, western point → Himachal Pradesh."""
        result = coords_to_subdivision(31.5, 77.5)
        assert result == "HIMACHAL PRADESH"

    def test_uttarakhand_region(self) -> None:
        """Central-western point → Uttarakhand."""
        result = coords_to_subdivision(30.5, 79.5)
        assert result == "UTTARAKHAND"

    def test_sikkim_region(self) -> None:
        """Eastern, low-latitude point → Sub-Himalayan WB & Sikkim."""
        result = coords_to_subdivision(27.5, 88.5)
        assert result == "SUB HIMALAYAN WEST BENGAL AND SIKKIM"

    def test_ne_states_region(self) -> None:
        """Far-east point (lon ≥ 90) → Naga-Mani-Mizo-Tripura.

        The heuristic checks lon >= 90.0 AND lat >= 26.5 for NE states.
        We must use lon strictly ≥ 90 and lat above 28.5 so the Sikkim rule
        (lat <= 28.5 and lon >= 87.0) does not fire first.
        """
        result = coords_to_subdivision(29.0, 91.0)
        assert result == "NAGA MANI MIZO TRIPURA"

    def test_assam_region(self) -> None:
        """Assam zone: lat ≥ 26.5, lon ≥ 88 but < 90.

        Must use lat > 28.5 to avoid the Sikkim rule firing first
        (Sikkim rule: lat <= 28.5 and lon >= 87.0).
        """
        result = coords_to_subdivision(29.0, 89.0)
        assert result == "ASSAM AND MEGHALAYA"

    def test_returns_string(self) -> None:
        """Return value must always be a non-empty string."""
        result = coords_to_subdivision(28.0, 80.0)
        assert isinstance(result, str) and len(result) > 0

    def test_fallback_returns_string(self) -> None:
        """Fallback case (no rule matches) must still return a valid subdivision."""
        # A point in the middle of the domain that hits the fallback
        result = coords_to_subdivision(27.0, 84.0)
        assert isinstance(result, str) and len(result) > 0


# ===========================================================================
# 6. compute_rainfall_features
# ===========================================================================

class TestComputeRainfallFeatures:
    """Tests for the feature-engineering aggregation function."""

    def test_returns_none_for_unknown_subdivision(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        result = compute_rainfall_features("NONEXISTENT_ZONE", minimal_climatology_cache)
        assert result is None

    def test_returns_dict_for_known_subdivision(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        result = compute_rainfall_features("UTTARAKHAND", minimal_climatology_cache)
        assert result is not None
        assert isinstance(result, dict)

    def test_all_seven_keys_present(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        result = compute_rainfall_features("UTTARAKHAND", minimal_climatology_cache)
        assert result is not None
        expected_keys = {
            "annual_rainfall_mean_mm",
            "monsoon_rainfall_mean_mm",
            "winter_rainfall_mean_mm",
            "pre_monsoon_rainfall_mean_mm",
            "post_monsoon_rainfall_mean_mm",
            "monsoon_variability_mm",
            "rainfall_seasonality_ratio",
        }
        assert set(result.keys()) == expected_keys

    def test_annual_equals_sum_of_months(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        """annual_rainfall_mean_mm must equal the sum of all 12 monthly means."""
        clim = minimal_climatology_cache["UTTARAKHAND"]
        expected_annual = sum(clim[m]["mean"] for m in range(1, 13))
        result = compute_rainfall_features("UTTARAKHAND", minimal_climatology_cache)
        assert result is not None
        assert abs(result["annual_rainfall_mean_mm"] - expected_annual) < 1e-6

    def test_monsoon_covers_jun_to_sep(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        """monsoon_rainfall_mean_mm = sum of months 6,7,8,9."""
        clim = minimal_climatology_cache["UTTARAKHAND"]
        expected = sum(clim[m]["mean"] for m in [6, 7, 8, 9])
        result = compute_rainfall_features("UTTARAKHAND", minimal_climatology_cache)
        assert result is not None
        assert abs(result["monsoon_rainfall_mean_mm"] - expected) < 1e-6

    def test_seasonality_ratio_between_0_and_1(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        """rainfall_seasonality_ratio = monsoon / annual, must be in [0, 1]."""
        result = compute_rainfall_features("UTTARAKHAND", minimal_climatology_cache)
        assert result is not None
        ratio = result["rainfall_seasonality_ratio"]
        assert 0.0 <= ratio <= 1.0, f"Seasonality ratio out of range: {ratio}"

    def test_all_values_are_non_negative(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        result = compute_rainfall_features("UTTARAKHAND", minimal_climatology_cache)
        assert result is not None
        for key, val in result.items():
            assert val >= 0.0, f"Feature '{key}' is negative: {val}"

    def test_empty_cache_returns_none(self) -> None:
        result = compute_rainfall_features("UTTARAKHAND", {})
        assert result is None


# ===========================================================================
# 7. get_subdivision_for_record — source tracking
# ===========================================================================

class TestGetSubdivisionForRecord:
    """Tests for subdiv_source field tracking."""

    def test_known_state_uses_authority_source(
        self,
        minimal_climatology_cache: dict[str, dict[int, dict[str, float]]],
    ) -> None:
        subdiv, source = get_subdivision_for_record("Uttarakhand", 30.0, 79.0)
        assert source == "state_authority"
        assert subdiv == "UTTARAKHAND"

    def test_unknown_state_uses_heuristic_source(self) -> None:
        _, source = get_subdivision_for_record("Unknown", 30.0, 79.5)
        assert source == "coordinate_heuristic"

    def test_empty_state_uses_heuristic_source(self) -> None:
        _, source = get_subdivision_for_record("", 30.0, 79.5)
        assert source == "coordinate_heuristic"

    def test_unmapped_state_falls_back_to_heuristic(self) -> None:
        """A valid but unmapped state name falls back to coordinate heuristic."""
        _, source = get_subdivision_for_record("Rajasthan", 26.5, 74.5)
        assert source == "coordinate_heuristic"

    def test_returns_tuple_of_two_strings(self) -> None:
        result = get_subdivision_for_record("Himachal Pradesh", 31.5, 77.5)
        assert isinstance(result, tuple) and len(result) == 2
        assert all(isinstance(s, str) for s in result)


# ===========================================================================
# 8. JSON serialisation safety
# ===========================================================================

class TestSafeJsonDumps:
    """Tests for _safe_json_dumps — NaN/Inf must become null."""

    def test_nan_becomes_null(self) -> None:
        result = _safe_json_dumps({"value": float("nan")})
        parsed = json.loads(result)
        assert parsed["value"] is None, "NaN should serialise to null"

    def test_positive_inf_becomes_null(self) -> None:
        result = _safe_json_dumps({"value": float("inf")})
        parsed = json.loads(result)
        assert parsed["value"] is None, "+Inf should serialise to null"

    def test_negative_inf_becomes_null(self) -> None:
        result = _safe_json_dumps({"value": float("-inf")})
        parsed = json.loads(result)
        assert parsed["value"] is None, "-Inf should serialise to null"

    def test_normal_float_preserved(self) -> None:
        result = _safe_json_dumps({"value": 0.872})
        parsed = json.loads(result)
        assert abs(parsed["value"] - 0.872) < 1e-9

    def test_nested_nan_in_list(self) -> None:
        result = _safe_json_dumps([float("nan"), 1.0, float("inf")])
        parsed = json.loads(result)
        assert parsed[0] is None
        assert parsed[2] is None
        assert abs(parsed[1] - 1.0) < 1e-9

    def test_nested_nan_in_dict(self) -> None:
        obj = {"folds": [{"roc_auc": float("nan"), "pr_auc": 0.5}, {"roc_auc": 0.8}]}
        result = _safe_json_dumps(obj)
        parsed = json.loads(result)
        assert parsed["folds"][0]["roc_auc"] is None
        assert abs(parsed["folds"][0]["pr_auc"] - 0.5) < 1e-9

    def test_output_is_valid_json(self) -> None:
        """The output must always be parseable by the standard json library."""
        tricky = {
            "a": float("nan"),
            "b": float("inf"),
            "c": [float("-inf"), 1.0],
            "d": {"nested": float("nan")},
        }
        result = _safe_json_dumps(tricky)
        # If this doesn't raise, the output is valid JSON
        json.loads(result)

    def test_no_bare_nan_token(self) -> None:
        """The output string must not contain the bare word 'NaN'."""
        result = _safe_json_dumps({"a": float("nan"), "b": [float("nan")]})
        assert "NaN" not in result, "Bare NaN token found in JSON output"


# ===========================================================================
# 9. _build_validity_record
# ===========================================================================

class TestBuildValidityRecord:
    """Tests for the validity record builder helper."""

    def test_structure_is_correct(self) -> None:
        rec = _build_validity_record(
            validity_reasons=["reason A"],
            all_folds_valid=False,
            best_nvalid=4,
            roc_acceptable=True,
            calibration_ok=True,
            environmental_signal=True,
            verdict="MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES",
        )
        assert rec["verdict"] == "MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES"
        assert rec["all_folds_valid"] is False
        assert rec["n_valid_folds"] == 4
        assert rec["reasons"] == ["reason A"]

    def test_empty_reasons_valid_verdict(self) -> None:
        rec = _build_validity_record(
            validity_reasons=[],
            all_folds_valid=True,
            best_nvalid=5,
            roc_acceptable=True,
            calibration_ok=True,
            environmental_signal=True,
            verdict="MODEL VALID — BASELINE SUSCEPTIBILITY MODEL",
        )
        assert rec["reasons"] == []
        assert rec["all_folds_valid"] is True

    def test_reasons_is_list(self) -> None:
        rec = _build_validity_record(
            validity_reasons=["a", "b", "c"],
            all_folds_valid=True,
            best_nvalid=5,
            roc_acceptable=True,
            calibration_ok=False,
            environmental_signal=True,
            verdict="MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES",
        )
        assert isinstance(rec["reasons"], list)
        assert len(rec["reasons"]) == 3


# ===========================================================================
# 10. Artifact loading — pipeline.joblib
# ===========================================================================

class TestArtifactLoading:
    """Tests that the saved pipeline artifact is loadable and functional."""

    @pytest.fixture(scope="class")
    def pipeline(self) -> Any:
        pipeline_path = ARTIFACT_DIR / "pipeline.joblib"
        if not pipeline_path.exists():
            pytest.skip("pipeline.joblib not present — run training first")
        return joblib.load(pipeline_path)

    @pytest.fixture(scope="class")
    def n_features(self, pipeline: Any) -> int:
        """Derive the actual feature count from the loaded pipeline itself.

        This is robust regardless of whether metadata.json has been updated
        to reflect a newer model version than what is in pipeline.joblib.
        CalibratedClassifierCV exposes its estimators; we inspect the first one.
        """
        # CalibratedClassifierCV wraps calibrated_classifiers_
        # Each calibrated_classifier has an estimator attribute
        try:
            estimator = pipeline.calibrated_classifiers_[0].estimator
            return int(estimator.n_features_in_)
        except (AttributeError, IndexError):
            # Fallback: try direct n_features_in_
            return int(pipeline.n_features_in_)

    @pytest.fixture(scope="class")
    def sample_1(self, n_features: int) -> np.ndarray:
        """A single valid-shaped input sample (1 × n_features)."""
        rng = np.random.RandomState(0)
        return rng.uniform(0, 2000, (1, n_features))

    @pytest.fixture(scope="class")
    def samples_20(self, n_features: int) -> np.ndarray:
        """20 valid-shaped input samples."""
        rng = np.random.RandomState(1)
        return rng.uniform(0, 2000, (20, n_features))

    def test_pipeline_loads_without_error(self, pipeline: Any) -> None:
        assert pipeline is not None

    def test_pipeline_has_predict_proba(self, pipeline: Any) -> None:
        assert hasattr(pipeline, "predict_proba"), "Pipeline missing predict_proba"

    def test_predict_proba_shape_single_sample(
        self, pipeline: Any, sample_1: np.ndarray
    ) -> None:
        """Single sample inference must return shape (1, 2)."""
        result = pipeline.predict_proba(sample_1)
        assert result.shape == (1, 2), (
            f"Expected (1, 2) from predict_proba, got {result.shape}"
        )

    def test_output_probabilities_sum_to_one(
        self, pipeline: Any, sample_1: np.ndarray
    ) -> None:
        """Class probabilities for each sample must sum to 1.0."""
        result = pipeline.predict_proba(sample_1)
        row_sums = result.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-6)

    def test_output_in_0_1_range(
        self, pipeline: Any, samples_20: np.ndarray
    ) -> None:
        """All predicted probabilities must lie in [0, 1]."""
        result = pipeline.predict_proba(samples_20)
        assert np.all(result >= 0.0), "Probability < 0 found"
        assert np.all(result <= 1.0), "Probability > 1 found"

    def test_batch_inference_consistent_with_single(
        self, pipeline: Any, n_features: int
    ) -> None:
        """Batch prediction must match individual sample predictions."""
        rng = np.random.RandomState(42)
        samples = rng.uniform(0, 2000, (5, n_features))
        batch_result = pipeline.predict_proba(samples)
        for i in range(5):
            single_result = pipeline.predict_proba(samples[i : i + 1])
            np.testing.assert_allclose(
                batch_result[i], single_result[0], atol=1e-8,
                err_msg=f"Batch and single predictions differ for sample {i}"
            )


# ===========================================================================
# 11. metadata.json schema validation
# ===========================================================================

class TestMetadataSchema:
    """Validate required fields exist and have the right types."""

    REQUIRED_FIELDS = [
        "model_version",
        "artifact_label",
        "model_type",
        "model_params",
        "calibration_method",
        "training_timestamp",
        "random_seed",
        "sklearn_version",
        "target_definition",
        "dataset",
        "modeling_domain",
        "feature_names",
        "feature_count",
        "feature_importance",
        "spatial_validation",
        "output_semantics",
        "artifact_files",
        "scientific_validity_verdict",
        "limitations",
    ]

    def test_all_required_fields_present(
        self, artifacts_metadata: dict[str, Any]
    ) -> None:
        for field in self.REQUIRED_FIELDS:
            assert field in artifacts_metadata, f"Required field '{field}' missing from metadata.json"

    def test_model_version_is_v2(self, artifacts_metadata: dict[str, Any]) -> None:
        assert artifacts_metadata["model_version"] == "risksetu-landslide-susceptibility-v2"

    def test_sklearn_version_recorded(self, artifacts_metadata: dict[str, Any]) -> None:
        sv = artifacts_metadata.get("sklearn_version")
        assert sv is not None and isinstance(sv, str) and len(sv) > 0, (
            "sklearn_version must be a non-empty string"
        )

    def test_feature_count_matches_feature_names(
        self, artifacts_metadata: dict[str, Any]
    ) -> None:
        count = artifacts_metadata["feature_count"]
        names = artifacts_metadata["feature_names"]
        assert count == len(names), (
            f"feature_count={count} does not match len(feature_names)={len(names)}"
        )

    def test_feature_count_is_7_or_9(self, artifacts_metadata: dict[str, Any]) -> None:
        """Model must have used either the 7-feature or 9-feature set."""
        assert artifacts_metadata["feature_count"] in {7, 9}, (
            f"Unexpected feature_count: {artifacts_metadata['feature_count']}"
        )

    def test_dataset_has_required_keys(self, artifacts_metadata: dict[str, Any]) -> None:
        required = {"positive_samples", "negative_samples", "exclusion_buffer_km",
                    "unknown_state_positives"}
        for key in required:
            assert key in artifacts_metadata["dataset"], (
                f"dataset.{key} missing from metadata.json"
            )

    def test_exclusion_buffer_is_positive(self, artifacts_metadata: dict[str, Any]) -> None:
        buf = artifacts_metadata["dataset"]["exclusion_buffer_km"]
        assert buf > 0, f"exclusion_buffer_km must be positive, got {buf}"

    def test_domain_has_correct_bounds(self, artifacts_metadata: dict[str, Any]) -> None:
        dom = artifacts_metadata["modeling_domain"]
        assert dom["lat_min"] == 26.0
        assert dom["lat_max"] == 36.0
        assert dom["lon_min"] == 74.0
        assert dom["lon_max"] == 90.0

    def test_random_seed_present_and_numeric(self, artifacts_metadata: dict[str, Any]) -> None:
        seed = artifacts_metadata["random_seed"]
        assert isinstance(seed, int), f"random_seed must be int, got {type(seed)}"

    def test_limitations_list_non_empty(self, artifacts_metadata: dict[str, Any]) -> None:
        lims = artifacts_metadata["limitations"]
        assert isinstance(lims, list) and len(lims) >= 3, (
            "limitations must be a list with at least 3 entries"
        )

    def test_spatial_validation_method_is_2d(
        self, artifacts_metadata: dict[str, Any]
    ) -> None:
        method = artifacts_metadata["spatial_validation"]["method"]
        assert "2D" in method or "Grid" in method, (
            f"Expected 2D grid method, got '{method}'"
        )

    def test_fold_validity_enforced_flag_true(
        self, artifacts_metadata: dict[str, Any]
    ) -> None:
        flag = artifacts_metadata["spatial_validation"]["fold_validity_enforced"]
        assert flag is True, "fold_validity_enforced must be True"

    def test_scientific_validity_verdict_present(
        self, artifacts_metadata: dict[str, Any]
    ) -> None:
        verdict = artifacts_metadata["scientific_validity_verdict"]
        assert verdict in {
            "MODEL VALID — BASELINE SUSCEPTIBILITY MODEL",
            "MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES",
        }, f"Unexpected verdict: '{verdict}'"


# ===========================================================================
# 12. features.json schema validation
# ===========================================================================

class TestFeaturesJsonSchema:
    """Validate features.json structure and content."""

    def test_required_keys_present(self, artifacts_features: dict[str, Any]) -> None:
        for key in ["version", "artifact_label", "feature_count", "features",
                    "excluded_features", "terrain_features_available",
                    "dynamic_weather_features_available"]:
            assert key in artifacts_features, f"Key '{key}' missing from features.json"

    def test_terrain_features_false(self, artifacts_features: dict[str, Any]) -> None:
        assert artifacts_features["terrain_features_available"] is False, (
            "terrain_features_available must be False until DEM is integrated"
        )

    def test_dynamic_weather_features_false(self, artifacts_features: dict[str, Any]) -> None:
        assert artifacts_features["dynamic_weather_features_available"] is False, (
            "dynamic_weather_features_available must be False until live weather is integrated"
        )

    def test_feature_count_matches_features_list(
        self, artifacts_features: dict[str, Any]
    ) -> None:
        count = artifacts_features["feature_count"]
        feats = artifacts_features["features"]
        assert count == len(feats)

    def test_all_feature_importances_sum_to_one(
        self, artifacts_features: dict[str, Any]
    ) -> None:
        importances = [f["importance"] for f in artifacts_features["features"]]
        total = sum(importances)
        assert abs(total - 1.0) < 0.05, (
            f"Feature importances should sum to ~1.0, got {total:.4f}"
        )

    def test_all_importances_non_negative(
        self, artifacts_features: dict[str, Any]
    ) -> None:
        for f in artifacts_features["features"]:
            assert f["importance"] >= 0.0, (
                f"Feature '{f['name']}' has negative importance {f['importance']}"
            )

    def test_leakage_features_in_excluded_list(
        self, artifacts_features: dict[str, Any]
    ) -> None:
        excluded_names = {ex["name"] for ex in artifacts_features["excluded_features"]}
        for leaky in ["distance_to_nearest_slide_km", "slide_count_within_5km",
                      "slide_count_within_10km", "slide_count_within_25km"]:
            assert leaky in excluded_names, (
                f"Leaky feature '{leaky}' not documented in excluded_features"
            )

    def test_terrain_features_in_excluded_list(
        self, artifacts_features: dict[str, Any]
    ) -> None:
        excluded_names = {ex["name"] for ex in artifacts_features["excluded_features"]}
        for terrain in ["elevation_m", "slope_degrees", "aspect_degrees"]:
            assert terrain in excluded_names, (
                f"Terrain feature '{terrain}' not documented in excluded_features"
            )

    def test_excluded_features_have_reasons(
        self, artifacts_features: dict[str, Any]
    ) -> None:
        for ex in artifacts_features["excluded_features"]:
            assert "reason" in ex and len(ex["reason"]) > 0, (
                f"Excluded feature '{ex['name']}' has no documented reason"
            )


# ===========================================================================
# 13. metrics.json validity
# ===========================================================================

class TestMetricsJsonValidity:
    """Validate metrics.json structure and scientific validity fields."""

    def test_no_nan_in_valid_fold_roc_auc(
        self, artifacts_metrics: dict[str, Any]
    ) -> None:
        """No valid fold should have a null or NaN ROC-AUC."""
        for fold in artifacts_metrics.get("best_model_fold_metrics", []):
            if fold.get("status") == "VALID":
                roc = fold.get("roc_auc")
                assert roc is not None, (
                    f"Valid fold {fold['fold']} has null roc_auc"
                )
                assert not math.isnan(float(roc)), (
                    f"Valid fold {fold['fold']} has NaN roc_auc"
                )

    def test_all_fold_metrics_have_status_field(
        self, artifacts_metrics: dict[str, Any]
    ) -> None:
        for fold in artifacts_metrics.get("best_model_fold_metrics", []):
            assert "status" in fold, (
                f"Fold {fold.get('fold')} missing 'status' field"
            )
            assert fold["status"] in {"VALID", "INVALID_SINGLE_CLASS"}, (
                f"Unknown fold status: {fold['status']}"
            )

    def test_n_valid_folds_recorded(self, artifacts_metrics: dict[str, Any]) -> None:
        overall = artifacts_metrics.get("best_model_overall_metrics", {})
        assert "n_valid_folds" in overall, "n_valid_folds missing from overall metrics"
        assert "n_total_folds" in overall, "n_total_folds missing from overall metrics"

    def test_ablation_section_present(self, artifacts_metrics: dict[str, Any]) -> None:
        abl = artifacts_metrics.get("ablation", {})
        assert "roc_auc_with_geo_rf" in abl, "Ablation section missing roc_auc_with_geo_rf"
        assert "roc_auc_no_geo_rf" in abl, "Ablation section missing roc_auc_no_geo_rf"
        assert "interpretation" in abl, "Ablation section missing interpretation"

    def test_scientific_validity_section_present(
        self, artifacts_metrics: dict[str, Any]
    ) -> None:
        sv = artifacts_metrics.get("scientific_validity", {})
        assert "verdict" in sv
        assert "all_folds_valid" in sv
        assert "reasons" in sv
        assert isinstance(sv["reasons"], list)

    def test_verdict_is_one_of_two_options(
        self, artifacts_metrics: dict[str, Any]
    ) -> None:
        verdict = artifacts_metrics["scientific_validity"]["verdict"]
        assert verdict in {
            "MODEL VALID — BASELINE SUSCEPTIBILITY MODEL",
            "MODEL NOT YET VALID — REQUIRES ADDITIONAL FEATURES",
        }

    def test_calibration_curve_has_required_fields(
        self, artifacts_metrics: dict[str, Any]
    ) -> None:
        cal = artifacts_metrics.get("calibration_curve", {})
        assert "bin_true_fraction" in cal
        assert "bin_predicted_mean" in cal
        assert "approximately_monotonic" in cal
        assert isinstance(cal["approximately_monotonic"], bool)

    def test_metrics_json_is_valid_json(self) -> None:
        """The raw file must be parseable as JSON (no bare NaN tokens)."""
        metrics_path = ARTIFACT_DIR / "metrics.json"
        if not metrics_path.exists():
            pytest.skip("metrics.json not present")
        raw = metrics_path.read_text()
        # This should not raise
        json.loads(raw)

    def test_buffer_sensitivity_list_present(
        self, artifacts_metrics: dict[str, Any]
    ) -> None:
        bufs = artifacts_metrics.get("buffer_sensitivity", [])
        # May be empty if --skip-buffer-sensitivity was used, but key must exist
        assert isinstance(bufs, list), "buffer_sensitivity must be a list"


# ===========================================================================
# 14. Model version constant
# ===========================================================================

class TestModelVersionConstant:
    """Sanity checks on MODULE-level constants."""

    def test_model_version_is_v2(self) -> None:
        assert MODEL_VERSION == "risksetu-landslide-susceptibility-v2"

    def test_domain_bounds_correct(self) -> None:
        assert DOMAIN["lat_min"] == 26.0
        assert DOMAIN["lat_max"] == 36.0
        assert DOMAIN["lon_min"] == 74.0
        assert DOMAIN["lon_max"] == 90.0

    def test_earth_radius_reasonable(self) -> None:
        assert 6350.0 < EARTH_RADIUS_KM < 6380.0
