# RISKSETU AI — PHASE 2A RUNTIME VERIFICATION REPORT

**Document ID:** `PHASE-2A-RUNTIME-VERIFICATION`  
**System:** RISKSETU AI — Explainable Spatial Risk Intelligence Engine  
**Hackathon Target:** Smart India Hackathon (SIH) 2026 | PS ID: 26001  
**Verification Date:** 2026-09-04  
**Engine Version:** `risk-v1` (`v1.0.0-deterministic`)  
**Execution Environment:** macOS (Darwin arm64) | PostgreSQL 17.11 + PostGIS 3.6.4 | Python 3.11.16 | FastAPI 0.115.6

---

## 1. Executive Status Summary

This document presents the complete runtime verification of the **Phase 2A Explainable Spatial Risk Intelligence Engine** against the real PostgreSQL + PostGIS database populated with authentic GSI and IMD datasets.

Zero synthetic, mocked, or fabricated database results were used for these verification procedures.

---

## 2. Real Database Status & PostGIS Verification

### 2.1 Database & PostGIS Service
- **Engine:** PostgreSQL 17.11 (Homebrew) on `aarch64-apple-darwin25.6.0`
- **Database:** `risksetu` (User: `risksetu`, Port: 5432)
- **PostGIS Extension Version Query:**
  ```sql
  SELECT PostGIS_Version();
  ```
  **Actual Result:**
  ```
              postgis_version            
  ---------------------------------------
   3.6 USE_GEOS=1 USE_PROJ=1 USE_STATS=1
  ```
- **Alembic Migration Status:**
  ```bash
  $ poetry run alembic current
  INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
  INFO  [alembic.runtime.migration] Will assume transactional DDL.
  0001_phase1b_core_tables (head)
  ```

### 2.2 Actual Table Row Counts
Verified via SQL count query against the live database:
```sql
SELECT 'historical_landslides' AS table_name, count(*) AS row_count FROM historical_landslides
UNION ALL SELECT 'rainfall_subdivisions', count(*) FROM rainfall_subdivisions
UNION ALL SELECT 'rainfall_observations', count(*) FROM rainfall_observations
UNION ALL SELECT 'rainfall_climatology', count(*) FROM rainfall_climatology;
```
**Actual Counts:**
| Table Name | Row Count | Source Dataset |
|---|---|---|
| `historical_landslides` | **31,417** | GSI National Landslide Inventory (`landslide_report.pdf`) |
| `rainfall_subdivisions` | **36** | IMD Meteorological Subdivisions (`Sub_Division_IMD_2017.csv`) |
| `rainfall_observations` | **50,256** | 117-Year Historical Monthly Precipitation (1901–2017) |
| `rainfall_climatology` | **432** | Derived Climatological Baseline ($\mu$, $\sigma$, min, max across 12 months) |

### 2.3 Spatial Index Verification
Verified presence of GIST index on `historical_landslides.geom`:
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'historical_landslides' AND indexname LIKE '%geom%';
```
**Actual Result:**
```
           indexname            |                                           indexdef                                            
--------------------------------+-----------------------------------------------------------------------------------------------
 idx_historical_landslides_geom | CREATE INDEX idx_historical_landslides_geom ON public.historical_landslides USING gist (geom)
```

### 2.4 Real PostGIS `ST_DWithin` & `ST_Distance` Execution
Executed geodetic ellipsoidal query around Uttarakhand coordinate (`29.135275°N, 80.090843°E`):
```sql
SELECT
    gsi_slide_no,
    material,
    movement_type,
    event_date,
    round((ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(80.090843, 29.135275), 4326)::geography))::numeric, 2) AS distance_meters
FROM historical_landslides
WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(80.090843, 29.135275), 4326)::geography, 5000)
ORDER BY distance_meters
LIMIT 5;
```
**Actual Result:**
```
   gsi_slide_no    | material | movement_type | event_date | distance_meters 
-------------------+----------+---------------+------------+-----------------
 CHA/62C04/2017/34 | Debris   | Slide         | 2014-01-01 |            0.00
 CHA/62C04/2017/24 | Rock     | Slide         | 2012-01-01 |         1714.24
 CHA/62C04/2017/1  | Rock     | Slide         | 2016-01-01 |         2137.20
 CHA/62C04/2017/35 | Rock     | Slide         | 2017-01-01 |         3143.30
 CHA/62C04/2017/20 | Rock     | Slide         |            |         3542.51
(5 rows)
```
- Proximity calculation: **VERIFIED** (Accurate metric distances down to centimetres on WGS 84 ellipsoid).
- Landslide attribute extraction: **VERIFIED** (GSI slide numbers, materials, movement mechanisms, dates).

---

## 3. Real API Verification

The FastAPI application was started and tested live against the real PostgreSQL database.

### 3.1 Real API Call 1: Hotspot Coordinate (Rainfall Parameters Unsupplied)
**Endpoint:** `POST /api/v1/risk/evaluate`  
**Actual Request:**
```json
{
  "latitude": 29.135275,
  "longitude": 80.090843
}
```
**Actual Response (HTTP 200 OK):**
```json
{
  "data": {
    "risk_score": 100.0,
    "risk_level": "CRITICAL",
    "confidence_score": 38.6,
    "calculation_version": "risk-v1",
    "queried_location": {
      "latitude": 29.135275,
      "longitude": 80.090843
    },
    "factors": [
      {
        "name": "historical_landslide_evidence",
        "display_name": "Historical Landslide Spatial Density & Proximity",
        "score": 100.0,
        "raw_weight": 0.5,
        "effective_weight": 1.0,
        "available": true,
        "evidence": {
          "within_5km_count": 11,
          "within_10km_count": 34,
          "within_25km_count": 142,
          "distance_to_nearest_km": 0.0,
          "closest_slide_id": "CHA/62C04/2017/34",
          "closest_slide_material": "Debris",
          "closest_slide_movement": "Slide",
          "dated_events_count": 132,
          "undated_inventory_count": 10
        },
        "explanation": "High local concentration: 11 historical landslides within 5 km (closest at 0.0 km, ID CHA/62C04/2017/34)."
      },
      {
        "name": "rainfall_climatology_anomaly",
        "display_name": "Precipitation Anomaly (IMD 117-Year Baseline)",
        "score": 0.0,
        "raw_weight": 0.3,
        "effective_weight": 0.0,
        "available": false,
        "evidence": {
          "reason": "Missing required rainfall parameters (subdivision_id, observed_rainfall_mm, and month)."
        },
        "explanation": "Rainfall factor unavailable: Observation parameters were not provided."
      },
      {
        "name": "terrain_morphometry",
        "display_name": "DEM Terrain Morphometry (Slope, Aspect, TWI)",
        "score": 0.0,
        "raw_weight": 0.2,
        "effective_weight": 0.0,
        "available": false,
        "evidence": {
          "status": "NOT AVAILABLE IN SOURCE DATA"
        },
        "explanation": "Terrain morphometry factor unavailable: No Bhoonidhi/CartoDEM raster tile is present."
      }
    ],
    "weight_redistributed": true,
    "summary_explanation": "Evaluated Risk Score: 100.0/100 (CRITICAL). Primary driver is Historical Landslide Spatial Density & Proximity (Score: 100.0, Effective Weight: 100.0%). Weights were redistributed among 1 available factor(s) (Total active weight: 50%).",
    "limitations": [
      "No Digital Elevation Model (DEM) derived terrain layers (slope, aspect, curvature, TWI) are currently present in the dataset repository.",
      "IMD precipitation data is sourced from historical sub-divisional monthly records rather than real-time telemetry or Doppler weather radar.",
      "GSI landslide inventory provides robust spatial footprint evidence, but 68.7% of historical inventory records lack precise calendar trigger timestamps.",
      "Calculations are deterministic evidence-based risk evaluations (Version 1), not probabilistic machine-learning predictions."
    ]
  },
  "meta": {
    "request_id": "8992003d-3c2b-41c6-b624-4de2f05978f2"
  }
}
```

---

### 3.2 Real API Call 2: Hotspot Coordinate + Real IMD Uttarakhand Climatology Anomaly
**Endpoint:** `POST /api/v1/risk/evaluate`  
**Actual Request:**
```json
{
  "latitude": 29.135275,
  "longitude": 80.090843,
  "rainfall_subdivision_id": "ed12460b-a803-4955-8d52-dbfebe27e762",
  "observed_rainfall_mm": 588.1,
  "month": 7,
  "year": 2026
}
```
**Actual Response (HTTP 200 OK):**
```json
{
  "data": {
    "risk_score": 87.5,
    "risk_level": "CRITICAL",
    "confidence_score": 68.6,
    "calculation_version": "risk-v1",
    "queried_location": {
      "latitude": 29.135275,
      "longitude": 80.090843
    },
    "factors": [
      {
        "name": "historical_landslide_evidence",
        "display_name": "Historical Landslide Spatial Density & Proximity",
        "score": 100.0,
        "raw_weight": 0.5,
        "effective_weight": 0.625,
        "available": true,
        "evidence": {
          "within_5km_count": 11,
          "within_10km_count": 34,
          "within_25km_count": 142,
          "distance_to_nearest_km": 0.0,
          "closest_slide_id": "CHA/62C04/2017/34",
          "closest_slide_material": "Debris",
          "closest_slide_movement": "Slide",
          "dated_events_count": 132,
          "undated_inventory_count": 10
        },
        "explanation": "High local concentration: 11 historical landslides within 5 km (closest at 0.0 km, ID CHA/62C04/2017/34)."
      },
      {
        "name": "rainfall_climatology_anomaly",
        "display_name": "Precipitation Anomaly (IMD 117-Year Baseline)",
        "score": 66.7,
        "raw_weight": 0.3,
        "effective_weight": 0.375,
        "available": true,
        "evidence": {
          "subdivision_name": "Uttarakhand",
          "month": 7,
          "year": 2026,
          "observed_rainfall_mm": 588.1,
          "climatology_mean_mm": 392.3,
          "climatology_std_mm": 97.9,
          "anomaly_mm": 195.8,
          "z_score": 2.0,
          "years_in_baseline": 117,
          "baseline_period": "1901-2017"
        },
        "explanation": "Precipitation of 588.1 mm in Jul (Uttarakhand) is significantly above normal (elevated threshold) (Mean: 392.3 mm, StdDev: 97.9 mm, Z-Score: +2.00)."
      },
      {
        "name": "terrain_morphometry",
        "display_name": "DEM Terrain Morphometry (Slope, Aspect, TWI)",
        "score": 0.0,
        "raw_weight": 0.2,
        "effective_weight": 0.0,
        "available": false,
        "evidence": {
          "status": "NOT AVAILABLE IN SOURCE DATA"
        },
        "explanation": "Terrain morphometry factor unavailable: No Bhoonidhi/CartoDEM raster tile is present."
      }
    ],
    "weight_redistributed": true,
    "summary_explanation": "Evaluated Risk Score: 87.5/100 (CRITICAL). Primary driver is Historical Landslide Spatial Density & Proximity (Score: 100.0, Effective Weight: 62.5%). Weights were redistributed among 2 available factor(s) (Total active weight: 80%).",
    "limitations": [
      "No Digital Elevation Model (DEM) derived terrain layers (slope, aspect, curvature, TWI) are currently present in the dataset repository.",
      "IMD precipitation data is sourced from historical sub-divisional monthly records rather than real-time telemetry or Doppler weather radar.",
      "GSI landslide inventory provides robust spatial footprint evidence, but 68.7% of historical inventory records lack precise calendar trigger timestamps.",
      "Calculations are deterministic evidence-based risk evaluations (Version 1), not probabilistic machine-learning predictions."
    ]
  },
  "meta": {
    "request_id": "3d3cb6d5-eebd-4eb3-9395-1500ef1f74e2"
  }
}
```

---

### 3.3 Real API Call 3: Non-Hazard Plains Coordinate (Delhi Region)
**Endpoint:** `POST /api/v1/risk/evaluate`  
**Actual Request:**
```json
{
  "latitude": 28.6139,
  "longitude": 77.2090
}
```
**Actual Response (HTTP 200 OK):**
```json
{
  "data": {
    "risk_score": 0.0,
    "risk_level": "LOW",
    "confidence_score": 10.0,
    "calculation_version": "risk-v1",
    "queried_location": {
      "latitude": 28.6139,
      "longitude": 77.209
    },
    "factors": [
      {
        "name": "historical_landslide_evidence",
        "display_name": "Historical Landslide Spatial Density & Proximity",
        "score": 0.0,
        "raw_weight": 0.5,
        "effective_weight": 1.0,
        "available": true,
        "evidence": {
          "within_5km_count": 0,
          "within_10km_count": 0,
          "within_25km_count": 0,
          "distance_to_nearest_km": null,
          "closest_slide_id": null,
          "closest_slide_material": null,
          "closest_slide_movement": null,
          "dated_events_count": 0,
          "undated_inventory_count": 0
        },
        "explanation": "No historical landslide events recorded within a 25 km radius in the GSI National Landslide Inventory."
      },
      {
        "name": "rainfall_climatology_anomaly",
        "display_name": "Precipitation Anomaly (IMD 117-Year Baseline)",
        "score": 0.0,
        "raw_weight": 0.3,
        "effective_weight": 0.0,
        "available": false,
        "evidence": {
          "reason": "Missing required rainfall parameters (subdivision_id, observed_rainfall_mm, and month)."
        },
        "explanation": "Rainfall factor unavailable: Observation parameters were not provided."
      },
      {
        "name": "terrain_morphometry",
        "display_name": "DEM Terrain Morphometry (Slope, Aspect, TWI)",
        "score": 0.0,
        "raw_weight": 0.2,
        "effective_weight": 0.0,
        "available": false,
        "evidence": {
          "status": "NOT AVAILABLE IN SOURCE DATA"
        },
        "explanation": "Terrain morphometry factor unavailable: No Bhoonidhi/CartoDEM raster tile is present."
      }
    ],
    "weight_redistributed": true,
    "summary_explanation": "Evaluated Risk Score: 0.0/100 (LOW). Primary driver is Historical Landslide Spatial Density & Proximity (Score: 0.0, Effective Weight: 100.0%). Weights were redistributed among 1 available factor(s) (Total active weight: 50%).",
    "limitations": [
      "No Digital Elevation Model (DEM) derived terrain layers (slope, aspect, curvature, TWI) are currently present in the dataset repository.",
      "IMD precipitation data is sourced from historical sub-divisional monthly records rather than real-time telemetry or Doppler weather radar.",
      "GSI landslide inventory provides robust spatial footprint evidence, but 68.7% of historical inventory records lack precise calendar trigger timestamps.",
      "Calculations are deterministic evidence-based risk evaluations (Version 1), not probabilistic machine-learning predictions."
    ]
  },
  "meta": {
    "request_id": "8af52355-3801-4467-83a8-a84cc891dc4c"
  }
}
```

---

## 4. Rainfall Verification & Subdivision Mapping Analysis

1. **Subdivision Spatial Geometry Status:**
   - The `rainfall_subdivisions` table contains 36 IMD meteorological subdivisions (`subdivision_name`, `normalized_name`, `source`).
   - It does **NOT** contain polygon spatial geometry boundaries in the source datasets.
2. **Defensible Handling:**
   - When coordinates alone are supplied, the engine **does NOT guess** or fabricate a subdivision association.
   - It marks `rainfall_climatology_anomaly.available = false`, sets `effective_weight = 0.0`, and dynamically redistributes weight to active evidence.
3. **Climatology Anomaly Calculation:**
   - When `rainfall_subdivision_id` is supplied, the engine retrieves the 117-year baseline (`rainfall_climatology`).
   - For Uttarakhand Month 7 (July):
     - $\mu = 392.3\text{ mm}$, $\sigma = 97.9\text{ mm}$
     - Observed: $588.1\text{ mm}$
     - $z = \frac{588.1 - 392.3}{97.9} = \mathbf{+2.00}$
     - Score: $\min(100.0, 2.0 \times \frac{100}{3}) = \mathbf{66.7}$
   - Anomaly calculation and dynamic scaling: **VERIFIED**.

---

## 5. Score Sanity & Mathematical Integrity Checks

All mathematical properties have been verified using real API outputs:

1. **Risk Score Range:**
   - Plains Coordinate: $0.0 \in [0, 100]$
   - Hotspot (Rainfall active): $87.5 \in [0, 100]$
   - Hotspot (Spatial only): $100.0 \in [0, 100]$
   - Condition $\forall s \in [0, 100]$: **PASSED**.
2. **Confidence Score Independence:**
   - Plains Coordinate: $10.0$ (reflects sparse local historical events and missing DEM).
   - Hotspot without rainfall: $38.6$ (high landslide density + dated event ratio, but missing rainfall & DEM).
   - Hotspot with 117-yr rainfall: $68.6$ (high density + dated events + 117-yr IMD baseline).
   - Condition $0 \le \text{confidence} \le 100$: **PASSED**.
3. **Threshold Classification:**
   - $0.0 \implies \text{LOW}$ ($[0, 24]$ range)
   - $87.5 \implies \text{CRITICAL}$ ($[75, 100]$ range)
   - $100.0 \implies \text{CRITICAL}$ ($[75, 100]$ range)
   - Condition verified against constants: **PASSED**.
4. **Weight Redistribution Sum:**
   - Spatial only: $w'_{\text{spatial}} = 1.000$ (Sum = $1.000$).
   - Spatial + Rainfall: $w'_{\text{spatial}} = 0.625$, $w'_{\text{rainfall}} = 0.375$ (Sum = $1.000$).
   - Sum condition $\sum w' = 1.0$: **PASSED**.
5. **No Silent Factor Fabrications:**
   - `terrain_morphometry` is strictly `available: false`, effective weight `0.0`.
   - `rainfall_climatology_anomaly` is strictly `available: false` when parameters are unsupplied.

---

## 6. Query Performance Measurement

Execution of the PostGIS spatial proximity and density query over all **31,417 real landslides** was profiled using PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)`:

```
Gather Merge (cost=233732.39..233732.62 rows=2 width=58) (actual time=30.192..32.048 rows=142 loops=1)
  Workers Planned: 1, Workers Launched: 1
  Buffers: shared hit=2522
  Sort Method: quicksort Memory: 30kB
  Parallel Seq Scan on historical_landslides
    Filter: st_dwithin((geom)::geography, point::geography, 25000, true)
    Rows Removed by Filter: 15638
Planning Time: 13.697 ms
Execution Time: 32.094 ms
```

- **Planning Time:** 13.70 ms
- **Execution Time:** **32.09 ms**
- **Total PostGIS Latency:** ~45.8 ms
- **Performance Evaluation:** Excellent for live REST API requests without caching.

---

## 7. Regression Suite Verification

The regression suite was executed across all components:

### 1. Pytest Unit & API Tests
```bash
$ poetry run pytest
======================== 55 passed, 3 warnings in 0.40s ========================
```

### 2. Code Quality & Formatting
```bash
$ poetry run ruff check .
All checks passed!
```

### 3. Static Type Analysis
```bash
$ poetry run mypy app/
Success: no issues found in 52 source files
```

### 4. Bytecode Compilation
```bash
$ poetry run python -m compileall -q app
# Exit code 0 (100% clean compilation)
```

---

## 8. Verified Features vs Known Limitations

### VERIFIED
- [x] PostgreSQL 17.11 + PostGIS 3.6 running locally with database `risksetu`.
- [x] Alembic migration `0001_phase1b_core_tables` applied to head.
- [x] GIST spatial index active on `historical_landslides.geom`.
- [x] 31,417 real GSI landslides ingested with accurate geodetic coordinates.
- [x] 36 IMD subdivisions and 50,256 rainfall observations ingested.
- [x] 432 derived 117-year climatological monthly baselines ($1901–2017$) stored and queried.
- [x] PostGIS `ST_DWithin` and `ST_Distance` geodetic ellipsoidal queries functioning with sub-35ms latency.
- [x] REST API endpoint `POST /api/v1/risk/evaluate` functioning live with standard response envelope.
- [x] Dynamic proportional weight redistribution verified across single and multi-factor evaluations.
- [x] Statistical $z$-score rainfall anomaly calculation verified against live baseline.
- [x] Decoupled confidence score verified across varying data completeness scenarios.
- [x] 55 unit and API tests passing with 100% success rate.

### NOT AVAILABLE / LIMITATIONS
- [!] **Bhoonidhi / CartoDEM Terrain Rasters:** No DEM raster files are present in `database/`. Slope, aspect, curvature, and TWI are flagged as unavailable; weight is proportionally redistributed.
- [!] **Subdivision Polygon Boundaries:** IMD rainfall dataset is a non-spatial CSV. Geographic coordinate-to-subdivision mapping cannot be resolved without administrative shapefiles; the API explicitly requires `rainfall_subdivision_id` rather than making guesses.
- [!] **Undated GSI Landslides:** 68.7% of historical GSI records lack day/month trigger dates. They are evaluated strictly as spatial susceptibility footprints rather than dynamic time-series triggers.
- [!] **Deterministic V1 vs ML:** This engine is explicitly a deterministic evidence synthesis engine; it is not a predictive machine-learning model.

---
**RISKSETU AI Runtime Verification** — Completed and Certified.
