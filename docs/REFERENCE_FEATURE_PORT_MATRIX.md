# RISKSETU AI — REFERENCE FEATURE PORT MATRIX

Comprehensive classification and mapping of all features from `RiskSetu_Full_Demo_Weather_Upgrade` to the certified RISKSETU AI architecture.

**Authoritative Backend Baseline:** 633 tests passing (PostgreSQL, PostGIS, Redis, SQLAlchemy, Alembic, FastAPI layered architecture).

---

## Classification Taxonomy

| Status | Definition |
| :--- | :--- |
| **ALREADY EXISTS** | Feature is fully certified and operational in current backend and/or frontend. |
| **PARTIALLY EXISTS** | Backend capability or partial frontend component exists; requires integration or UI enhancement. |
| **MISSING** | Valid, high-value feature present in reference ZIP but completely absent in current project. |
| **NOT SAFE TO PORT** | Violates scientific honesty, creates fake data, or bypasses certified architecture. |
| **REQUIRES VERIFIED DATA** | Can only be displayed when an authoritative/verified dataset is loaded; otherwise marked UNAVAILABLE. |
| **REQUIRES EXTERNAL PROVIDER** | Depends on an external API or credentials (e.g. NASA PPS credentials). |

---

## Master Feature Matrix

| # | Feature | Reference Implementation | Current Status | Current Equivalent | Port Required? | Layer | Data Source | Risk Level | Implementation Plan |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | **Live Weather: Current Conditions** | Open-Meteo current conditions (`temperature_2m`, `precipitation`, `relative_humidity_2m`, `wind_speed_10m`, `weather_code`) | **ALREADY EXISTS** | `GET /api/v1/weather/current`, `WeatherPanel.tsx`, `useMapContext` | UI Polish | Frontend | Open-Meteo API | Low | Ensure prominent `[ WEATHER ]` action in top bar and header, displaying live temperature, precip, humidity, wind, and WMO condition icon. |
| **02** | **Weather: 3-Day Forecast** | Open-Meteo 3-day daily forecast (`precipitation_sum`, `temp_max`, `temp_min`, `weather_code`) | **ALREADY EXISTS** | `GET /api/v1/weather/current` (`forecast` array in schema) | UI Polish | Frontend | Open-Meteo API | Low | Display 3-day forecast cards in `WeatherPanel.tsx` with date, min/max temp, precipitation sum, and weather emoji. |
| **03** | **Weather: Forecast Windows** | 1h, 3h, 6h, 12h forecast accumulation windows with rain level (LOW/MODERATE/HIGH/CRITICAL) | **PARTIALLY EXISTS** | Daily forecast available in `WeatherResponse`; hourly windows can be derived or marked unavailable if not provided | UI Enhancement | Frontend | Open-Meteo API | Low | Display forecast windows where available; if provider only returns daily sums, show daily forecast windows honestly without fabricating hourly curves. |
| **04** | **Modelled Soil Moisture Proxy** | Open-Meteo numerical model 0-27 cm aggregated proxy | **MISSING** | Currently not exposed in `WeatherResponse` | Optional UI / Isolated Backend | Frontend / Backend | Open-Meteo hourly soil moisture | Low | Clearly label as "numerical model proxy (0-27 cm), not a physical field sensor". If backend doesn't fetch it, display UNAVAILABLE. |
| **05** | **NASA GPM IMERG Satellite Rainfall** | IMERG early run GIS point sampling (requires NASA PPS credentials) | **REQUIRES EXTERNAL PROVIDER** | None | Do Not Fabricate | External | NASA PPS | Medium | Keep optional. Never call live radar or deterministic flood forecast. If no PPS credentials configured, display UNAVAILABLE. |
| **06** | **Copernicus DEM Elevation & Slope** | Open-Meteo Elevation API + 5-point stencil slope calculation | **REQUIRES VERIFIED DATA** | Phase 1B schema supports terrain; `LIVE_RISK_V1` explicitly reports `terrain.status = "unavailable"` | Maintain Honesty | Backend / Frontend | Validated DEM (pending) | High | **CRITICAL SCIENTIFIC RULE:** Do NOT invent terrain values. Display "Terrain intelligence UNAVAILABLE" honestly. |
| **07** | **GloFAS River Discharge Context** | Open-Meteo Flood API / GloFAS river discharge context (~5 km grid) | **REQUIRES EXTERNAL PROVIDER** | None | Optional Context | Backend / Frontend | Open-Meteo Flood API | Medium | If integrated, clearly label as coarse basin guidance (~5 km), never a local river gauge or deterministic flood prediction. |
| **08** | **Regional / Upstream Rainfall Screening Watch** | 6 monitoring points across eastern Himalayan corridor (Tibet, Arunachal, Bhutan, Nepal, Meghalaya) | **PARTIALLY EXISTS** | Regional hazard concepts exist; needs UI banner and dedicated screening service | Port Required | Frontend / Isolated Backend | Open-Meteo point screening | Low | Expose "REGIONAL RAINFALL WATCH" / "UPSTREAM RAINFALL SCREENING" in UI. Never call it "Flood prediction". |
| **09** | **Multi-Hazard Risk Distinction** | Separate Landslide, Flood, and Overall Area Risk scores | **ALREADY EXISTS** | `LIVE_RISK_V1` provides certified composite risk score, level, confidence, and factors | UI Enhancement | Frontend | Certified Risk Engine | Low | Clearly distinguish Landslide Risk, Flood/Flash-flood Risk, and Overall Risk in UI only when backend signals support them. |
| **10** | **Emergency SOS: Citizen Submission** | Floating SOS button, confirm location, select emergency type, optional details, immediate status | **ALREADY EXISTS** | `POST /api/v1/sos`, `SosPanel.tsx`, `useMapContext` | UI Enhancement | Frontend | Certified SOS Engine | Low | Elevate SOS button visibility (floating action + top action bar). Ensure full flow: Confirm location -> Select type -> Add message -> Send -> Show risk context -> Show recommendations. |
| **11** | **Emergency Call Shortcuts (112 / 108)** | Quick dial links to National Emergency Number (112) and Medical Emergency (108) | **MISSING** | Missing in current `SosPanel` | Port Required | Frontend | Standard telephony (`tel:112`, `tel:108`) | Low | Add quick-call links in `SosPanel.tsx` with explicit disclaimer: "RiskSetu does not replace official emergency services." |
| **12** | **Offline SOS Queue & Auto-Sync** | IndexedDB persistence of SOS reports when offline, automatic sync upon reconnection | **MISSING** | Current frontend lacks IndexedDB SOS queue | Port Required | Frontend | Browser IndexedDB (`idb`) | Medium | Port `offline.ts` queue logic: When offline, queue SOS locally, label "SOS queued on this device". On reconnect, sync to `POST /api/v1/sos`. Only show "SOS SENT" after backend 201 response. |
| **13** | **Emergency Facilities / Shelters** | Verified shelters and emergency resources discovery | **ALREADY EXISTS** | `GET /api/v1/shelters/nearby`, `GET /api/v1/sos/{id}/recommendations` | UI Enhancement | Frontend / Backend | PostGIS `shelters` table | High | If backend returns `data_status: "unavailable"`, display "VERIFIED SHELTER DATA UNAVAILABLE". Never fabricate fake shelter markers or hospital pins. |
| **14** | **Citizen Field Incident Reporting** | Citizen report submission (Landslide, Crack, Blocked Road, Flood, Rockfall, etc.) | **PARTIALLY EXISTS** | Certified Ground Intelligence backend (`POST /api/v1/ground-reports`, `GroundReport` model) exists; frontend lacks reporting form | Port Required | Frontend | Certified Ground Intelligence Engine | Medium | Create `ReportIncidentModal.tsx` connected to `POST /api/v1/ground-reports`. Expose prominent `[ REPORT ]` button in header/action bar. Support offline queuing. |
| **15** | **Community Verification (500m / 1km)** | Nearby citizens can confirm/deny/unsure reported observations | **PARTIALLY EXISTS** | Corroboration engine in Phase 3 backend; UI lacks citizen confirmation prompt | Port Required | Frontend | Ground Intelligence Corroboration Engine | Medium | Add confirmation UI on selected ground observation. Clearly label as "COMMUNITY SIGNAL", never "VERIFIED TRUTH". Citizen votes do not override official verification. |
| **16** | **Officer Incident Inspection & Moderation** | Officer can review evidence, accept/reject/resolve reports, add notes, record response | **ALREADY EXISTS** | `PATCH /api/v1/ground-reports/{id}/status`, `GroundReportAudit`, RBAC | Port Required | Frontend | Certified Ground Intelligence RBAC | Low | Provide officer inspection drawer: review trust score breakdown, verify or reject, record operational justification. |
| **17** | **Officer Mass Alert / Geofenced Siren** | Geofenced area alert (500m, 1km, 3km), severity, instruction, in-app siren request | **ALREADY EXISTS** | `POST /api/v1/alerts/generate`, `Alert` model, `AlertAudit`, RBAC | Port Required | Frontend | Certified Alerts Engine | Medium | Add `MassAlertModal.tsx` for officers. Trigger `POST /api/v1/alerts/generate`. Siren request must remain opt-in; explicitly state it cannot override phone silent mode. |
| **18** | **Officer SOS Queue** | Queue of active citizen SOS requests with status, risk context, acknowledge/resolve actions | **ALREADY EXISTS** | `GET /api/v1/sos`, `POST /api/v1/sos/{id}/acknowledge`, `POST /api/v1/sos/{id}/resolve` | Port Required | Frontend | Certified SOS Engine | Low | Add Officer SOS Queue panel in the operations view allowing officers to review active SOS, see coordinates, acknowledge, and resolve. |
| **19** | **Route Risk Assessment vs Navigation** | Route hazard scoring, blocked corridor avoidance, travel advice | **PARTIALLY EXISTS** | Road Risk (`POST /api/v1/road-risk/evaluate`) and Road Isolation (`POST /api/v1/impact/simulate`) exist. OSRM turn-by-turn routing is not certified in current backend | Port Required (Carefully) | Frontend / Backend | Certified Road Graph & Connectivity | High | Clearly distinguish **ROUTE RISK ASSESSMENT** from **NAVIGATION**. Do not claim turn-by-turn navigation without an authoritative routing engine. Lower-risk route != guaranteed safe. |
| **20** | **Road Status: Predicted Risk vs Closure** | Open / Caution / Blocked status indicator | **ALREADY EXISTS** | Road Risk engine returns `predicted_risk_score`. `closure_status` is explicitly `UNKNOWN` | UI Enhancement | Frontend | Certified Road Risk Engine | High | Maintain strict distinction: Predicted blockage risk is NOT confirmed closure. `closure_status = UNKNOWN` must remain visible. |
| **21** | **Population Exposure Estimation** | Population at risk and exposure priority scoring | **ALREADY EXISTS** | Phase 1B Census demographic tables + Phase 2C priority engine | UI Enhancement | Frontend | Census 2011 / A-1 Data Foundation | Medium | Show estimated population exposure only where spatial aggregation is scientifically defensible. Label derived estimates clearly. |
| **22** | **Public-Source AI Hazard Intelligence (OSINT)** | RSS scan (GDACS, news) + weather corroboration for early situational awareness | **MISSING** | Missing in current project | Port Required | Isolated Module | Public RSS + Open-Meteo | Medium | Add isolated OSINT module (`app/services/osint.py` and `app/api/v1/osint.py`) for officer decision support. Treated strictly as leads, never proof. Output `PREPARE_EVACUATION_REVIEW`. |
| **23** | **PWA & Service Worker Offline Cache** | Service worker caching static app shell, Web App Manifest, offline indicator | **MISSING** | Current frontend is standard SPA without service worker | Port Required | Frontend | Service Worker API (`sw.js`), Cache Storage | Low | Add `sw.js` and `manifest.webmanifest`. Display prominent `OFFLINE` / `CACHED DATA` badge when connection is lost. |
| **24** | **Browser Notifications (Opt-in)** | Native browser push/desktop notifications for high-priority alerts | **MISSING** | Missing in current frontend | Port Required | Frontend | Web Notifications API | Low | Opt-in from Settings or action bar. Never spam permission request on initial load. |
| **25** | **Emergency Web Siren** | Synthesized audio tone via Web AudioContext for critical emergency alerts | **MISSING** | Missing in current frontend | Port Required | Frontend | Web AudioContext API | Low | Opt-in siren toggle in Settings. Synthesize emergency tone. Label clearly: "Browser/PWA siren — requires permission, does not override device silent mode." |
| **26** | **Multilingual Support (EN / HI / AS)** | Lightweight translation layer for English, Hindi, and Assamese | **MISSING** | Current frontend is English-only | Port Required | Frontend | Client-side i18n dictionary | Low | Add `i18n.ts` supporting English, हिन्दी, and অসমীয়া. Translate navigation, basic action labels, SOS, alerts, and safety instructions. Preserve source-language evidence. |
| **27** | **Data Provenance Badges** | Explicit labeling of data origin (GSI, IMD, Open-Meteo, PostGIS, Census, Citizen, OSINT) | **PARTIALLY EXISTS** | Some provenance tags exist; needs consistent visual tokens across all panels | UI Enhancement | Frontend | Certified Metadata | Low | Add compact, standardized provenance badges to every card and metric. |
| **28** | **Data Quality & Missing Data Honesty** | "Missing != safe" principle: show UNAVAILABLE, not 0 or LOW | **ALREADY EXISTS** | Certified in `LIVE_RISK_V1` and `WeatherPanel` | Maintain & Strengthen | Frontend / Backend | Certified Contracts | High | Maintain across all components: when data is missing, display UNAVAILABLE, never fabricated numbers. |
| **29** | **Full Guided Judge Demo Walkthrough** | 17-step end-to-end interactive demo walkthrough across all certified capabilities | **PARTIALLY EXISTS** | 10-step basic timer controller in `DemoController.tsx` | Port Required (High Priority) | Frontend | Certified APIs & Scenarios | Low | Transform `DemoController.tsx` into a 17-step guided demo with Previous, Play/Pause, Next, Exit, progress bar, and real backend API calls. |
| **30** | **Prominent Action Visibility** | Direct visible entry points: [WEATHER], [SOS], [SIMULATE ROAD FAILURE], [ALERTS], [REPORT] | **PARTIALLY EXISTS** | Weather, SOS, Simulate Road Failure exist in UI; Report and OSINT need top-level access | UI Enhancement | Frontend | UI Layout | Low | Ensure all 5 core actions are directly discoverable in the top dock/action bar without digging into sub-menus. |

---

## Port Decision Summary

- **Total features audited:** 30
- **Already fully certified / present:** 9
- **Partially present (requires frontend wiring or UI port):** 9
- **Missing high-value safe features to port:** 9
  - Offline SOS Queue & Auto-Sync (IndexedDB)
  - Emergency Call Shortcuts (112, 108) with legal disclaimers
  - Citizen Incident Reporting Form (`[ REPORT ]`) mapped to `POST /api/v1/ground-reports`
  - Officer Inspection & Moderation Workspace
  - Officer Mass Alert Modal connected to `POST /api/v1/alerts/generate`
  - Officer SOS Queue Panel
  - Public-Source AI Hazard Intelligence (OSINT decision-support lead module)
  - PWA Service Worker & Offline Cache Shell
  - Multilingual Translation Layer (English, Hindi, Assamese)
  - Guided 17-step Judge Demo Walkthrough with full user controls
- **Requires verified data / do not fabricate:** 3 (Terrain DEM, Verified Shelters, Traffic/Closure feeds)
- **External provider credentials required:** 1 (NASA PPS IMERG)
