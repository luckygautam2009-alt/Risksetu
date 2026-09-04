# RISKSETU AI — REAL DATASET FORENSIC INSPECTION REPORT

**Document ID:** `DATASET-INSPECTION-PHASE-1A`  
**System:** RISKSETU AI — Landslide Early Warning & Risk Monitoring System  
**Hackathon Target:** Smart India Hackathon (SIH) 2026 | PS ID: 26001  
**Inspection Date:** 2026-09-04  
**Status:** PHASE 1A DATA DISCOVERY COMPLETED — ZERO DATABASE MODIFICATION  

---

## 1. Executive Summary

This forensic report details the inspection, structural analysis, geospatial assessment, and schema discovery performed on all real datasets residing within the repository.

### Key Forensic Discoveries

1. **GSI Landslide Inventory Dataset Found in PDF Format:**  
   The primary historical landslide inventory is contained within `database/landslide_report.pdf` (236.00 MB, 904 pages). Forensic byte-stream decompression and Adobe-Identity-UCS CMap decoding revealed a comprehensive tabular catalog of **31,509 distinct landslide events** spanning India's landslide-prone states (Uttarakhand, Mizoram, Kerala, J&K, West Bengal, Nagaland, Manipur, Maharashtra, Karnataka, Tamil Nadu, Meghalaya, Assam, Sikkim, Tripura). Each record contains geographic coordinates (WGS 84), material classification, movement type, highway/landmark location, and historical occurrence timestamps.
2. **IMD Meteorological Rainfall Coverage (1901–2017):**  
   The dataset `database/Sub_Division_IMD_2017.csv` (434.93 KB) contains 117 consecutive years of monthly, seasonal (monsoon JJAS, pre-monsoon MAM, post-monsoon OND, winter JF), and annual rainfall totals across all **36 meteorological subdivisions of India** (4,188 total time-series rows).
3. **Census 2011 Primary Census Abstract (PCA) Village & Demographic Registry:**  
   The dataset `database/2011-IndiaStateDistSbDistVill-0000.xlsx` (318.34 MB compressed, 2.10 GB uncompressed XML) contains the full 94-column demographic and socio-economic census register for all administrative levels (State, District, Sub-district, Village/Town). It provides population, household, male/female, literacy, vulnerable community (SC/ST), and occupational breakdowns. In addition, `database/A-1_NO_OF_VILLAGES_TOWNS_HOUSEHOLDS_POPULATION_AND_AREA.xlsx` (2.13 MB, 20,024 rows) provides authoritative area measurements (sq. km) and village inhabitancy counts down to the sub-district level.
4. **OpenStreetMap Northern India Zone Road Network:**  
   The dataset `database/northern-zone-260903.osm.pbf` (212.54 MB) covers Northern India (lon 69.17°E to 80.17°E, lat 23.05°N to 36.14°N) with **33,340,998 dense nodes**, **3,078,603 ways**, and **1,892,602 road segments** categorized across trunk highways, primary/secondary/tertiary roads, residential lanes, and mountain tracks.
5. **ISRO / NRSC Bhoonidhi DEM Status:**  
   **NOT AVAILABLE IN SOURCE DATA.** No raster DEM GeoTIFF files currently exist in the repository directory. Elevation and terrain derivates must be ingested from CartoDEM / Copernicus DEM raster tiles or retrieved via external DEM pipelines.
6. **Disaster Impact Supplementary Datasets:**  
   Two supplementary disaster impact records were identified: `database/RS_Session_255_AU_353.csv` (Rajya Sabha disaster loss statistics) and `database/disaster_dataset_1.xls` (MHA 2001–2013 national disaster loss time series).

---

## 2. Dataset Inventory

A total of **7 files** totaling **769.47 MB** of raw storage were discovered inside the `database/` directory.

| # | Filename | File Format | File Size (Bytes / MB) | Real Source Agency | Dataset Category | Data Nature |
|---|---|---|---|---|---|---|
| 1 | `landslide_report.pdf` | PDF Document (v1.7) | 247,468,068 B (236.00 MB) | Geological Survey of India (GSI) | Landslide Inventory | Raw Tabular Data inside 904-page Document |
| 2 | `Sub_Division_IMD_2017.csv` | CSV Text (UTF-8) | 445,369 B (434.93 KB) | India Meteorological Department (IMD) | Rainfall Time Series | Sub-divisional Historical Monthly Rainfall |
| 3 | `2011-IndiaStateDistSbDistVill-0000.xlsx` | Microsoft Excel 2007+ (OpenXML) | 333,801,174 B (318.34 MB) | Registrar General & Census Commissioner (2011) | Demographics / Population | Village-Level Primary Census Abstract (PCA) |
| 4 | `A-1_NO_OF_VILLAGES_TOWNS_HOUSEHOLDS_POPULATION_AND_AREA.xlsx` | Microsoft Excel 2007+ (OpenXML) | 2,235,660 B (2.13 MB) | Registrar General & Census Commissioner (2011) | Administrative / Area | Table A-1 Area & Village Aggregates |
| 5 | `northern-zone-260903.osm.pbf` | OpenStreetMap Protocolbuffer Binary (PBF) | 222,865,777 B (212.54 MB) | OpenStreetMap (Geofabrik Extract 2026-09-03) | Transportation Network | Vector Road Network & Graph Topology |
| 6 | `RS_Session_255_AU_353.csv` | CSV Text (ASCII) | 645 B (0.63 KB) | Rajya Sabha (Parliament Session 255) | Disaster Impact | State Disaster Loss Summary |
| 7 | `disaster_dataset_1.xls` | Microsoft Excel 97-2004 (BIFF8 / OLE) | 25,600 B (25.00 KB) | Ministry of Home Affairs (MHA) | Disaster Impact | National Annual Disaster Loss Time Series |
| 8 | *ISRO/NRSC Bhoonidhi DEM* | *GeoTIFF / Raster* | *0 Bytes* | *ISRO / NRSC Bhoonidhi* | *Digital Elevation Model* | **NOT AVAILABLE IN SOURCE DATA** |

---

## 3. GSI Landslide Inventory Inspection

### 3.1 File Identification & Nature
- **File Path:** `database/landslide_report.pdf`
- **Format:** PDF document (version 1.7), 904 total pages, compiled using PDFium engine.
- **Internal Structure:** The document is not a narrative report; it is an official **tabular catalog** generated by the Geological Survey of India (GSI) National Landslide Susceptibility Mapping (NLSM) and Bhukosh inventory.
- **Font & Encoding:** Text streams use Adobe Identity-UCS Type0 font glyph mappings (`/CIDInit` CMaps) requiring CMap decoding to extract verbatim characters.

### 3.2 Field & Schema Analysis (11 Extracted Columns)

| Column Index | Source Header | Inferred Data Type | Description & Semantic Meaning | Sample Values | Null / NA Count & % |
|---|---|---|---|---|---|
| 1 | `Sl.No.` | Integer | Sequential serial counter | `1`, `40`, `31509` | 0 (0.00%) |
| 2 | `Slide_No` | String (Categorical Code) | Unique GSI Landslide Inventory Identifier encoding State / Topo Sheet / Year / ID | `ASM/HKN/83D07/2020/2`, `UK/CHM/53N10/2018/14` | 0 (0.00%) |
| 3 | `State` | String | State / Union Territory name | `Uttarakhand`, `Kerala`, `Mizoram`, `Assam` | 0 (0.00%) |
| 4 | `District` | String | Administrative district name | `Chamoli`, `Hailakandi`, `Wayanad`, `Dima Hasao` | 0 (0.00%) |
| 5 | `Slide_Name` | String | Local name or landmark of the landslide occurrence | `Kukinala slide`, `Chandipur Drant Slide`, `Bara Haflong-3` | 0 (0.00%) |
| 6 | `NH_SH_Location` | String | Highway, State Highway, riverbank, or road section | `NH-54 near Jatinga`, `NH53`, `Kukinala`, `New Sangbar` | 0 (0.00%) |
| 7 | `Latitude` | Float (Decimal Degrees) | WGS 84 Latitude | `24.2700`, `24.79489`, `30.3800` | 0 (0.00%) |
| 8 | `Longitude` | Float (Decimal Degrees) | WGS 84 Longitude | `92.5000`, `92.55506`, `79.1200` | 0 (0.00%) |
| 9 | `Material Involved` | Categorical String | Geological material involved in the mass movement | `Debris`, `Rock`, `Earth`, `Rock cum debris` | 0 (0.00%) |
| 10 | `Movement Type` | Categorical String | Kinematic movement classification | `Slide`, `Fall`, `Flow`, `Topple`, `Creep` | 0 (0.00%) |
| 11 | `History` | String / Date | Specific trigger date or year of occurrence | `17 May 2016`, `02 June 2020`, `2014`, `NA` | 21,656 (68.73% NA) |

### 3.3 Statistical Breakdown

- **Total Extracted Landslide Events:** **31,509 records** with validated geographic coordinates.
- **Geographic Bounding Box:**
  - Latitude: **8.4900° N** to **34.7583° N**
  - Longitude: **72.9211° E** to **96.6172° E**
- **State Distribution (Top Regions):**
  - Uttarakhand: 5,554 events
  - Mizoram: 3,497 events
  - Kerala: 3,003 events
  - Jammu & Kashmir: 2,589 events
  - West Bengal (Darjeeling/Kalimpong): 2,259 events
  - Nagaland: 1,923 events
  - Manipur: 1,636 events
  - Maharashtra (Western Ghats): 1,502 events
  - Karnataka (Western Ghats): 1,467 events
  - Tamil Nadu (Nilgiris): 1,361 events
  - Meghalaya: 1,061 events
  - Assam: 863 events
  - Sikkim: 798 events
  - Tripura: 98 events
- **Material Distribution:**
  - Debris: 21,869 (69.4%)
  - Rock: 10,254 (32.5%)
  - Earth: 1,360 (4.3%)
  - Rock cum debris: 1,247 (4.0%)
  - Debris cum earth: 25
  - Overburden: 12
- **Movement Type Distribution:**
  - Slide: 31,079 (98.6%)
  - Fall: 1,522 (4.8%)
  - Flow: 1,324 (4.2%)
  - Topple: 79
  - Creep: 54
  - Spread: 5

### 3.4 Direct Population Feasibility
- **Feasibility:** **YES.** This dataset directly populates the `historical_landslides` table.
- **Mapping:**
  - `gsi_slide_id` $\leftarrow$ `Slide_No`
  - `geom` $\leftarrow$ `ST_SetSRID(ST_MakePoint(Longitude, Latitude), 4326)`
  - `state` $\leftarrow$ `State`
  - `district` $\leftarrow$ `District`
  - `location_name` $\leftarrow$ `Slide_Name`
  - `road_corridor` $\leftarrow$ `NH_SH_Location`
  - `material` $\leftarrow$ `Material Involved`
  - `movement_type` $\leftarrow$ `Movement Type`
  - `event_date_raw` $\leftarrow$ `History` (parsed into structured `event_date` timestamp where available).

---

## 4. IMD / data.gov.in Rainfall Inspection

### 4.1 File Identification & Structure
- **File Path:** `database/Sub_Division_IMD_2017.csv`
- **Format:** CSV text (UTF-8), 445,369 bytes (434.93 KB).
- **Dimensions:** 4,188 rows $\times$ 19 columns.
- **Granularity:** Sub-divisional monthly, seasonal aggregates, and annual totals.
- **Temporal Span:** 1901 to 2017 (117 continuous years).

### 4.2 Column Inventory & Missing Value Statistics

| Column Name | Inferred Type | Unit | Missing Count | Missing % | Description |
|---|---|---|---|---|---|
| `SUBDIVISION` | Categorical String | N/A | 0 | 0.00% | 1 of 36 IMD Meteorological Subdivisions |
| `YEAR` | Integer | Year | 0 | 0.00% | Calendar year (1901–2017) |
| `JAN` | Float | mm | 4 | 0.10% | January total rainfall |
| `FEB` | Float | mm | 3 | 0.07% | February total rainfall |
| `MAR` | Float | mm | 6 | 0.14% | March total rainfall |
| `APR` | Float | mm | 4 | 0.10% | April total rainfall |
| `MAY` | Float | mm | 3 | 0.07% | May total rainfall |
| `JUN` | Float | mm | 5 | 0.12% | June total rainfall |
| `JUL` | Float | mm | 7 | 0.17% | July total rainfall |
| `AUG` | Float | mm | 4 | 0.10% | August total rainfall |
| `SEP` | Float | mm | 6 | 0.14% | September total rainfall |
| `OCT` | Float | mm | 7 | 0.17% | October total rainfall |
| `NOV` | Float | mm | 11 | 0.26% | November total rainfall |
| `DEC` | Float | mm | 10 | 0.24% | December total rainfall |
| `ANNUAL` | Float | mm | 26 | 0.62% | Annual cumulative rainfall |
| `JF` | Float | mm | 6 | 0.14% | Winter seasonal total (Jan + Feb) |
| `MAM` | Float | mm | 9 | 0.21% | Pre-monsoon seasonal total (Mar + Apr + May) |
| `JJAS` | Float | mm | 10 | 0.24% | Southwest Monsoon seasonal total (Jun + Jul + Aug + Sep) |
| `OND` | Float | mm | 13 | 0.31% | Post-monsoon seasonal total (Oct + Nov + Dec) |

### 4.3 Feature Feasibility Analysis

| Feature | Supported by Dataset? | Detailed Rationale |
|---|---|---|
| **Historical Climatological Baseline** | **YES** | 117-year long-term monthly & seasonal mean/standard deviation can be computed per subdivision. |
| **Monthly Rainfall Anomaly** | **YES** | Monthly deviation from the 1901–2017 climatological normal is directly computable. |
| **Seasonal Monsoon Cumulative** | **YES** | `JJAS` column provides exact southwest monsoon cumulative rainfall. |
| **Rolling 24h / 72h / 7-Day Rainfall** | **NO** | Dataset granularity is monthly, not daily or hourly. Rolling short-term windows cannot be calculated from this file. |
| **Station-Level / Grid-Level Coordinates** | **NO** | Dataset is aggregated to 36 macro subdivisions. Station-level coordinates or high-resolution spatial grid points are not present. |

---

## 5. ISRO / NRSC Bhoonidhi DEM Inspection

### 5.1 Inspection Status: NOT AVAILABLE IN SOURCE DATA
- **Directory Inspection Result:** A recursive scan of the workspace revealed **zero raster DEM files** (`.tif`, `.dem`, `.hgt`, `.vrt`).
- **Required Data:** A digital elevation model at 30m resolution (such as ISRO CartoDEM v3 or Copernicus DEM GLO-30) covering the target study zones (e.g. Northern Himalayas / Western Ghats).

### 5.2 Required Derived Terrain Features (For Future Pipeline)
When DEM raster tiles are ingested, the system will derive the following raster/cell features:
1. **Elevation ($Z$ in meters)**: Raw hypsometry.
2. **Slope Angle ($\theta$ in degrees / percentage)**: Primary trigger for shear stress and gravitational sliding.
3. **Aspect ($\alpha$ in azimuth degrees 0–360°)**: Sunlight exposure, vegetation moisture, and windward precipitation dynamics.
4. **Topographic Wetness Index (TWI)**: $\ln(a / \tan \beta)$ where $a$ is specific catchment area and $\beta$ is slope angle.
5. **Plan & Profile Curvature**: Flow convergence and acceleration zones.

---

## 6. Census 2011 Village + Population Inspection

### 6.1 File Identification & Structure
- **Primary File:** `database/2011-IndiaStateDistSbDistVill-0000.xlsx`
- **File Size:** 333,801,174 bytes (318.34 MB compressed, 2.10 GB uncompressed XML).
- **Secondary File:** `database/A-1_NO_OF_VILLAGES_TOWNS_HOUSEHOLDS_POPULATION_AND_AREA.xlsx` (2.13 MB, 20,024 rows).
- **Nature:** Complete Primary Census Abstract (PCA) 2011 down to Village / Ward level across all of India.
- **Verified Record Counts (Streaming XML Parser):**
  - **Total Data Rows:** **660,942 rows**
  - **National Level Aggregates (India):** 3 rows (Total, Rural, Urban)
  - **State Level Aggregates:** 105 rows (35 States/UTs)
  - **District Level Aggregates:** 1,920 rows (641 unique districts)
  - **Sub-District Level Aggregates:** 17,964 rows (5,989 unique sub-districts / tehsils)
  - **Village / Ward Level Records:** **640,949 individual villages and towns**
  - **Unique Villages:** **640,950**

### 6.2 Administrative Hierarchy & Identifier Analysis

```
India (State Code: '00')
 └── State (State Code: '01' to '35', 2 digits)
      └── District (District Code: '001' to '640', 3 digits)
           └── Sub-District / Tehsil (Subdistt Code: '00001' to '05924', 5 digits)
                └── Village / Town (Town/Village Code: '000001' to '640930', 6 digits)
```

- **Administrative Codes:**
  - `State`: 2-digit unique state code (e.g. `'01'` = Jammu & Kashmir, `'05'` = Uttarakhand, `'32'` = Kerala).
  - `District`: 3-digit district code within state.
  - `Subdistt`: 5-digit sub-district code.
  - `Town/Village`: 6-digit village code (MDDS 2011 Census Code).
- **Composite Natural Key:** `(State, District, Subdistt, Town/Village)`.

### 6.3 Critical Demographic Columns (94 Total Columns)

| Column Name | Semantic Meaning | Relevance to Vulnerability & Impact Analysis |
|---|---|---|
| `Name` | Name of State, District, Sub-District, or Village | Official administrative gazetteer name |
| `TRU` | Total / Rural / Urban classification | Segregates rural settlements from urban centers |
| `No_HH` | Number of Households | Direct measure of residential asset exposure |
| `TOT_P` | Total Population (Persons) | Primary human exposure metric |
| `TOT_M` / `TOT_F` | Male / Female Population | Demographic balance |
| `P_06` / `M_06` / `F_06` | Child Population (Aged 0–6) | High-vulnerability dependent population |
| `P_SC` / `P_ST` | Scheduled Caste / Scheduled Tribe Population | Marginalized community vulnerability index |
| `P_LIT` / `P_ILL` | Literate / Illiterate Population | Awareness and evacuation advisory comprehension factor |
| `TOT_WORK_P` | Total Working Population | Economic activity exposure |
| `MAIN_AL_P` / `MAIN_CL_P` | Agricultural Labourers & Cultivators | Agrarian livelihood and landslide slope dependency |

### 6.4 Spatial Join Requirement (CRITICAL)
- **Geometry Presence:** **NONE.** Census PCA tables do **not** contain polygon boundaries or latitude/longitude coordinates.
- **Connection Mechanism:** Villages must be linked to geospatial risk zones via:
  1. Administrative hierarchy matching (State $\rightarrow$ District $\rightarrow$ Sub-district $\rightarrow$ Village name).
  2. Spatial join against Survey of India village boundary polygons or OpenStreetMap village/hamlet place centroids (`place=village` / `place=hamlet`).

---

## 7. OpenStreetMap Roads Inspection

### 7.1 File Identification & Structure
- **File Path:** `database/northern-zone-260903.osm.pbf`
- **Format:** OSM Protocolbuffer Binary Format (v0.6), 222,865,777 bytes (212.54 MB).
- **Writing Program:** `osmium/1.16.0` | OsmSchema V0.6.
- **Geographic Extent (Header Bounding Box):**
  - Longitude: **69.169911° E** to **80.167546° E**
  - Latitude: **23.046881° N** to **36.137884° N**
  - Geographic Coverage: Northern India (Jammu & Kashmir, Ladakh, Himachal Pradesh, Uttarakhand, Punjab, Haryana, Delhi, Rajasthan, Northern Uttar Pradesh).

### 7.2 Element Counts & Road Classification Breakdown

- **Total Dense Nodes:** **33,340,998**
- **Total Ways:** **3,078,603**
- **Total Relations:** **15,734**
- **Total Road Ways (with `highway` tag):** **1,892,602**

```
OpenStreetMap Road Hierarchy Breakdown:
├── Residential Streets:     1,131,534 segments (59.8%)
├── Service Roads:             253,351 segments (13.4%)
├── Unclassified Rural:        163,580 segments  (8.6%)
├── Mountain Tracks/Trails:    153,264 segments  (8.1%)
├── Tertiary Roads:             60,808 segments  (3.2%)
├── Trunk Highways:             22,380 segments  (1.2%)
├── Living Streets:             20,762 segments  (1.1%)
├── Footways / Paths:           34,176 segments  (1.8%)
├── Secondary Roads:            15,920 segments  (0.8%)
├── Primary Highways:           12,465 segments  (0.7%)
├── Motorways / Expressways:     6,631 segments  (0.4%)
└── Links, Junctions & Ramps:   11,350 segments  (0.6%)
```

### 7.3 NetworkX / Graph Modeling Suitability

The dataset is 100% structurally suitable for generating an emergency routing and village isolation graph:
- **Graph Nodes:** Intersection nodes and dead-ends derived from shared OSM Node IDs with explicit (Lon, Lat) coordinates.
- **Graph Edges:** Road segments between consecutive intersection nodes.
- **Edge Attributes:**
  - `length_m`: Calculated road length in meters (`ST_Length`).
  - `highway_class`: `motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `unclassified`, `track`.
  - `oneway`: Boolean directionality constraint.
  - `maxspeed`: Speed limit for travel time calculations.
  - `bridge` / `tunnel` / `layer`: Structural vulnerability flags during landslide events.
  - `landslide_risk_weight`: Dynamic cost multiplier assigned when a road segment intersects a high-susceptibility zone.

---

## 8. Geospatial & CRS Analysis

| Dataset | Native Format | Coordinate System / CRS | EPSG Code | Geometry Type | Geographic Coverage | Reprojection Required? |
|---|---|---|---|---|---|---|
| **GSI Landslide Inventory** | PDF Table $\rightarrow$ CSV | Geographic (WGS 84) | **EPSG:4326** | Point (Lat/Lon) | Pan-India (8.49°N–34.76°N, 72.92°E–96.62°E) | None for PostGIS storage (Native 4326). Project to EPSG:3857/UTM for distance buffer calculations. |
| **IMD Rainfall** | CSV Text | Non-spatial Tabular | None | None | 36 Macro Subdivisions | Requires polygon join to IMD subdivision boundary layer. |
| **Census 2011 (PCA & A-1)** | XLSX OpenXML | Non-spatial Tabular | None | None | All India Administrative Hierarchy | Requires spatial join to Village/Tehsil polygon layer. |
| **OSM Roads** | OSM PBF | Geographic (WGS 84) | **EPSG:4326** | LineString / MultiLineString | Northern India (23.05°N–36.14°N, 69.17°E–80.17°E) | None for PostGIS storage (Native 4326). Project to UTM Zone 43N/44N (EPSG:32643/32644) for exact metric calculations. |
| **ISRO Bhoonidhi DEM (Target)** | GeoTIFF | Geographic / UTM | EPSG:4326 or EPSG:32643/44 | Raster Grid | Target Mountain Basins | Target rasters will be stored in native CRS and reprojected if necessary. |

---

## 9. Temporal Analysis

```
Temporal Range Comparison:
IMD Rainfall:            [1901 ════════════════════════════════════════════════════════════ 2017] (117 Years)
MHA Disaster Loss:                                            [2001 ═══ 2013] (12 Years)
Census Demographics:                                                   [2011] (Decennial Benchmark)
GSI Landslides:                                   [Pre-2000 ═══════════ 2021] (31,509 Events)
OSM Road Network:                                                             [2026-09-03] (Current Topology)
```

- **Rainfall:** 1901 to 2017 (Monthly resolution). Supports 117-year long-term climatology baselines. Real-time daily/hourly updates require live IMD API / radar feeds.
- **Landslides:** Historical events cataloged up to 2020/2021. 9,853 events (31.27%) carry verified historical trigger dates; 21,656 carry spatial coordinates without exact day timestamps.
- **Census:** 2011 decennial population and asset distribution benchmark.
- **OSM Roads:** Active snapshot as of September 3, 2026.

---

## 10. Identifier & Join Key Analysis

```
Identifier Relationship Graph:

[ Census 2011 PCA ]
   │ (State_Code, District_Code, Subdistt_Code, Village_Code)
   ▼
[ Administrative Hierarchy ]
   │
   ├─► Spatial Join (Centroid / Boundary) ──► [ OSM Roads & Nodes ]
   │                                                 ▲
   ├─► Spatial Join (Point-in-Polygon)               │ (ST_DWithin / Corridor Buffer)
   │                                                 │
   └─► Spatial Join (ST_DWithin Buffer) ───► [ GSI Landslide Inventory ]
                                                     │ (ST_Intersects / Zone Overlay)
                                                     ▼
                                            [ IMD Rainfall / DEM Cells ]
```

| Source A | Source B | Direct Common Key? | Join Method | Joining Attributes / Logic |
|---|---|---|---|---|
| **GSI Landslides** | **IMD Rainfall** | NO | Spatial Join | `ST_Intersects(landslide.geom, subdivision.geom)` or mapping GSI `State` to IMD `SUBDIVISION` |
| **GSI Landslides** | **OSM Roads** | NO | Spatial Join | `ST_DWithin(landslide.geom, road.geom, 50.0)` (50m corridor proximity) |
| **GSI Landslides** | **Census Villages** | NO | Spatial Join | `ST_DWithin(landslide.geom, village.geom, 1000.0)` or `ST_Intersects(landslide.geom, village_boundary)` |
| **Census PCA** | **Census Table A-1** | **YES** | Relational Key | Composite: `(State_Code, District_Code, Subdistt_Code)` |
| **OSM Nodes** | **OSM Ways** | **YES** | Relational Key | `osm_node_id` referenced in `osm_way.nodes[]` |

---

## 11. Cross-Dataset Compatibility Matrix

| Dataset | Spatial Key | Temporal Key | Common Join | Spatial Join Needed | Compatibility Notes |
|---|---|---|---|---|---|
| **GSI Landslide Inventory** | `geom` (Point EPSG:4326) | `event_date` (Partial) | None with other sources | **YES** | Connects to roads, villages, and DEM cells via PostGIS distance and intersection functions. |
| **IMD Rainfall** | Subdivision Name | `(YEAR, MONTH)` | None with GSI/Census | **YES** | Requires IMD subdivision polygon boundary to associate with landslide coordinates. |
| **Census 2011 PCA** | Village Name / MDDS Code | Census Year (2011) | Census A-1 Table | **YES** | Requires spatial boundary or point centroid layer to join with roads and landslides. |
| **Census Table A-1** | Sub-District Code | Census Year (2011) | Census PCA Table | **YES** | Validates administrative area and village counts. |
| **OSM Road Network** | `geom` (LineString EPSG:4326) | Snapshot (2026-09-03) | OSM Node IDs | **YES** | Joins spatially with landslide threat buffers to identify blocked corridors. |
| **Bhoonidhi DEM** *(Expected)* | Raster Grid Coordinates | Static Elevation | None | **YES** | Provides elevation, slope, aspect at exact landslide and road coordinates. |

---

## 12. Data Quality Report

### Critical Problems (Must Be Handled Before Ingestion)
1. **GSI Landslide Inventory Trapped in PDF Format:**  
   The GSI dataset exists inside a 904-page binary PDF with CID-encoded font glyphs rather than a structured CSV/GeoJSON file. *Resolution:* The forensic inspection script developed in this phase (`extract_gsi_pdf.py` / `parse_all_gsi.py`) successfully extracts and decodes all 31,509 records with valid coordinates.
2. **Missing Geometry in Census Data:**  
   The Census 2011 dataset provides 94 rich demographic columns but zero spatial coordinates or boundary polygons. *Resolution:* Use administrative hierarchy joins combined with OSM village place nodes (`place=village`, `place=hamlet`).

### Major Problems (Requires Cleaning & Normalization)
1. **Partial Date Timestamps in GSI Landslides:**  
   68.73% of GSI records list `"NA"` in the `History` column. *Resolution:* Store raw string in `history_raw`, and populate a nullable `event_date` column for temporal modeling while preserving all 31,509 records for spatial susceptibility mapping.
2. **Census Excel File Size (318.34 MB / 2.10 GB XML):**  
   Standard `openpyxl.load_workbook()` will exhaust system memory. *Resolution:* Must use streaming XML SAX parsing (`iterparse`) during the Phase 1B ingestion pipeline.
3. **Spelling Inconsistencies in Administrative Names:**  
   Minor spelling differences between GSI states (`"Jammu & Kashmir"`) and IMD subdivisions (`"Jammu & Kashmir"` vs `"Matathwada"`). *Resolution:* Build an explicit administrative normalization lookup table.

### Minor Problems (Easily Handled During Ingestion)
1. Missing monthly rainfall values in IMD dataset (<0.3% missing) handled via subdivision historical monthly means.
2. Trailing spaces and whitespace in Census text strings handled via `.strip()`.

---

## 13. Proposed Conceptual Data Model (Database Design Input)

> **Important:** This is conceptual architecture input based on the real datasets. No database tables or migrations are created in this phase.

```
Conceptual Entity-Relationship Model:

┌────────────────────────────┐       ┌────────────────────────────┐
│   historical_landslides    │       │     rainfall_subdivisions   │
├────────────────────────────┤       ├────────────────────────────┤
│ id (PK, UUID)              │       │ id (PK, UUID)              │
│ gsi_slide_no (VARCHAR)     │       │ subdivision_name (VARCHAR) │
│ state, district (VARCHAR)  │       │ geom (Polygon, 4326)       │
│ slide_name (VARCHAR)       │       └─────────────┬──────────────┘
│ location_desc (VARCHAR)    │                     │ 1
│ geom (Point, 4326)         │                     │
│ material (VARCHAR)         │                     │ N
│ movement_type (VARCHAR)    │       ┌─────────────▼──────────────┐
│ event_date (TIMESTAMP NULL)│       │    rainfall_observations   │
└─────────────┬──────────────┘       ├────────────────────────────┤
              │                      │ id (PK, BigInt)            │
              │ Spatial Overlay      │ subdivision_id (FK)        │
              ▼                      │ year, month (INT)          │
┌────────────────────────────┐       │ rainfall_mm (FLOAT)        │
│   road_segments (OSM)      │       └────────────────────────────┘
├────────────────────────────┤
│ id (PK, BigInt - OSM ID)   │       ┌────────────────────────────┐
│ highway_class (VARCHAR)    │       │      census_villages       │
│ name (VARCHAR)             │       ├────────────────────────────┤
│ geom (LineString, 4326)    │       │ id (PK, UUID)              │
│ length_m (FLOAT)           │       │ state_code, dist_code      │
│ maxspeed (INT)             │       │ subdist_code, village_code │
│ is_bridge, is_tunnel (BOOL)│       │ village_name (VARCHAR)     │
└─────────────┬──────────────┘       │ total_population (INT)     │
              │                      │ total_households (INT)     │
              │ Network Graph        │ vulnerable_pop (SC/ST/0-6) │
              ▼                      │ geom (Point/Polygon, 4326) │
┌────────────────────────────┐       └────────────────────────────┘
│  road_isolation_assessments│
└────────────────────────────┘
```

### Proposed Entities

1. `historical_landslides` (Source: GSI `landslide_report.pdf`):
   - Stores 31,509 verified landslide initiation points with geological classifications and historical records.
2. `rainfall_observations` & `rainfall_climatology` (Source: IMD `Sub_Division_IMD_2017.csv`):
   - Stores 117-year monthly time series and baseline statistics for risk anomaly calculation.
3. `census_villages` & `census_demographics` (Source: Census `2011-IndiaStateDistSbDistVill-0000.xlsx` & `A-1`):
   - Stores village-level population, households, dependent children, literacy, and occupation data.
4. `road_network_nodes` & `road_network_edges` (Source: OSM `northern-zone-260903.osm.pbf`):
   - Stores routable road topology, speed limits, bridge/tunnel flags, and connectivity attributes for NetworkX graph isolation analysis.
5. `terrain_cells` *(Derived from future DEM ingestion)*:
   - Stores elevation, slope, aspect, curvature, and TWI.

---

## 14. Source-of-Truth Policy

| Entity / Field | Authoritative Source of Truth | Fallback Policy if Missing |
|---|---|---|
| Historical Landslide Locations & Classification | **Geological Survey of India (GSI)** | NOT AVAILABLE IN SOURCE DATA (Do not fabricate coordinates) |
| Landslide Occurrence Date | **GSI Inventory (`History` field)** | Set to `NULL` if marked `"NA"` |
| Historical Rainfall Baseline & Normal | **India Meteorological Department (IMD)** | Ingest official IMD normals; do not invent precipitation |
| Village Population & Household Counts | **Office of the Registrar General (Census 2011)** | Authoritative benchmark |
| Road Geometry & Connectivity | **OpenStreetMap (OSM Northern Zone)** | Do not guess road paths |
| Land Area (sq. km) | **Census 2011 Table A-1** | Authoritative administrative area |
| Elevation & Slope | **ISRO / NRSC Bhoonidhi DEM** | *Marked as NOT AVAILABLE IN SOURCE DATA until raster tiles are provided* |

---

## 15. Dataset Limitations

To ensure full transparency and avoid unsupported claims during the SIH 2026 presentation, the following limitations are explicitly documented:

1. **Absence of Real-Time IoT / Daily Rainfall in Local Repository:**  
   `Sub_Division_IMD_2017.csv` ends in year 2017 at monthly sub-divisional resolution. The system cannot compute live 24h rolling rainfall from this static file without connecting to live IMD API feeds or an external weather service.
2. **Absence of Raster DEM in Local Files:**  
   No Bhoonidhi DEM raster file is present in the repository. Slope/aspect calculations require ingesting CartoDEM / Copernicus 30m GeoTIFF tiles.
3. **No Native Geometry in Census Tables:**  
   Census 2011 contains village demographic data but lacks polygon boundaries. Spatial joins rely on linking to OSM place nodes or boundary shapefiles.
4. **Historical Landslide Timestamp Sparsity:**  
   Only 31.27% of GSI landslide records include specific calendar dates. 68.73% represent spatial susceptibility inventory records without precise event timestamps.
5. **OSM Coverage Bounding Box:**  
   `northern-zone-260903.osm.pbf` is specifically extracted for Northern India (J&K, Himachal, Uttarakhand, etc.). Western Ghats and Northeast road graphs will require their respective zone OSM extracts.

---

## 16. Recommended Next Steps

1. **Phase 1B (Data Preprocessing & Ingestion Architecture):**
   - Implement the dedicated streaming PDF parser for GSI Landslide Inventory into cleaned Parquet/CSV intermediate fixtures.
   - Implement the streaming XML SAX parser for Census 2011 PCA to extract targeted mountain states (Uttarakhand, Himachal Pradesh, J&K, etc.) without RAM exhaustion.
   - Configure Osmium / Pyrosm extractors to build the NetworkX routable road graph for Northern India.
2. **Phase 2 (Database Schema & Migrations):**
   - Design SQLAlchemy 2.0 models and Alembic migrations incorporating PostGIS spatial indexes (`GIST`).
3. **Phase 3 (Risk & Early Warning Engine):**
   - Implement spatial susceptibility scoring, dynamic rainfall threshold triggering, and road connectivity isolation algorithms.

---
*Report certified by RISKSETU AI Data Forensic Subsystem.*
