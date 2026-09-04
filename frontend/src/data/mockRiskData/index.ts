import type { Hazard, GeoJsonFeatureCollection } from '../../types';

export interface RiskFactor {
  name: string;
  displayName: string;
  score: number;
  weight: number;
  summary: string;
}

export interface DetailedHazard extends Hazard {
  elevationM: number;
  basin: string;
  subdivision: string;
  confidenceLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  factors: RiskFactor[];
  coordinatesFormatted: {
    lat: string;
    lng: string;
  };
}

export const MOCK_HAZARDS: DetailedHazard[] = [
  {
    id: 'hz-chamoli',
    latitude: 30.2936,
    longitude: 79.5603,
    location: 'Chamoli',
    elevationM: 1475,
    basin: 'Alaknanda Basin',
    subdivision: 'Uttarakhand Himalayan Sector',
    riskScore: 98.9,
    riskLevel: 'CRITICAL',
    confidence: 68.6,
    confidenceLevel: 'MEDIUM',
    historicalEvidence: 'High — 14 events since 2010 (GSI Inventory)',
    rainfall: 'Extreme — 340mm / 72h (+185% over baseline)',
    terrain: 'Steep slope (>45°), fractured quartzites and gneisses',
    coordinatesFormatted: { lat: '30.2936° N', lng: '79.5603° E' },
    factors: [
      { name: 'rainfall_anomaly', displayName: 'Precipitation Anomaly', score: 96.4, weight: 0.35, summary: 'Extreme 72h antecedent rainfall exceeding trigger thresholds' },
      { name: 'historical_proximity', displayName: 'Historical GSI Density', score: 92.0, weight: 0.25, summary: 'Located in high-recurrence debris flow corridor' },
      { name: 'slope_steepness', displayName: 'Slope Gradient (>45°)', score: 88.5, weight: 0.25, summary: 'Unstable mountain wall with scarp progression' },
      { name: 'road_exposure', displayName: 'NH-58 Transportation Exposure', score: 82.0, weight: 0.15, summary: 'Critical pilgrim & supply arterial directly adjacent' },
    ],
  },
  {
    id: 'hz-joshimath',
    latitude: 30.555,
    longitude: 79.564,
    location: 'Joshimath',
    elevationM: 1875,
    basin: 'Dhauliganga / Alaknanda Confluence',
    subdivision: 'Chamoli District Subsector',
    riskScore: 87.2,
    riskLevel: 'CRITICAL',
    confidence: 74.1,
    confidenceLevel: 'HIGH',
    historicalEvidence: 'High — active subsidence and moraine displacement',
    rainfall: 'Heavy — 280mm / 72h (+140% over baseline)',
    terrain: 'Old landslide debris cover, low shear resistance',
    coordinatesFormatted: { lat: '30.5550° N', lng: '79.5640° E' },
    factors: [
      { name: 'subsidence_velocity', displayName: 'Moraine Ground Movement', score: 94.0, weight: 0.35, summary: 'Progressive toe erosion by underlying riverbeds' },
      { name: 'rainfall_anomaly', displayName: 'Rainfall Infiltration', score: 82.5, weight: 0.25, summary: 'Percolation destabilizing unstratified moraine material' },
      { name: 'historical_proximity', displayName: 'Past Subsidence Records', score: 90.0, weight: 0.25, summary: 'Documented continuous settlement since 1976 Mishra Committee' },
      { name: 'urban_density', displayName: 'Infrastructure Weight', score: 76.0, weight: 0.15, summary: 'Dense settlements overlying paleo-landslide deposit' },
    ],
  },
  {
    id: 'hz-gangtok',
    latitude: 27.3314,
    longitude: 88.6139,
    location: 'Gangtok',
    elevationM: 1650,
    basin: 'Ranichu / Teesta Catchment',
    subdivision: 'East Sikkim Ridge',
    riskScore: 72.4,
    riskLevel: 'HIGH',
    confidence: 61.3,
    confidenceLevel: 'MEDIUM',
    historicalEvidence: 'Moderate — 6 events recorded since 2015',
    rainfall: 'Elevated — 210mm / 72h (+85% anomaly)',
    terrain: 'Urban slope interface, weathered chlorite-phyllites',
    coordinatesFormatted: { lat: '27.3314° N', lng: '88.6139° E' },
    factors: [
      { name: 'slope_loading', displayName: 'Slope Cut Surcharge', score: 78.0, weight: 0.30, summary: 'Terraced construction along steep hill contours' },
      { name: 'rainfall_anomaly', displayName: 'Monsoon Saturation', score: 74.5, weight: 0.30, summary: 'Subsurface aquifer surcharge along fracture lines' },
      { name: 'geological_bedding', displayName: 'Phyllite Foliation Dip', score: 68.0, weight: 0.25, summary: 'Bedding planes inclined toward valley floor' },
      { name: 'highway_proximity', displayName: 'NH-10 Lifeline Criticality', score: 85.0, weight: 0.15, summary: 'Sole connectivity highway to plains' },
    ],
  },
  {
    id: 'hz-darjeeling',
    latitude: 27.041,
    longitude: 88.266,
    location: 'Darjeeling',
    elevationM: 2042,
    basin: 'Balason / Mahananda Valley',
    subdivision: 'Sub-Himalayan Hill Tracts',
    riskScore: 58.3,
    riskLevel: 'HIGH',
    confidence: 55.8,
    confidenceLevel: 'MEDIUM',
    historicalEvidence: 'Moderate — tea-estate slope slippages',
    rainfall: 'Heavy — 195mm / 72h (+70% anomaly)',
    terrain: 'Terraced hillside with mica schists and weathered regolith',
    coordinatesFormatted: { lat: '27.0410° N', lng: '88.2660° E' },
    factors: [
      { name: 'rainfall_anomaly', displayName: 'High Intensity Precipitation', score: 65.0, weight: 0.35, summary: 'Cloudburst frequency elevated in south-facing hills' },
      { name: 'soil_depth', displayName: 'Residual Soil Thickness', score: 62.0, weight: 0.30, summary: 'Thick colluvium mantle over steeply dipping bedrock' },
      { name: 'drainage_choking', displayName: 'Surface Runoff Drainage', score: 54.0, weight: 0.20, summary: 'Urban drainage siltation along natural jhoras' },
      { name: 'slope_stability', displayName: 'Historical Stability Index', score: 52.0, weight: 0.15, summary: 'Historical slippage along hill cart roads' },
    ],
  },
  {
    id: 'hz-tehri',
    latitude: 30.381,
    longitude: 78.48,
    location: 'Tehri Garhwal',
    elevationM: 1550,
    basin: 'Bhagirathi Catchment',
    subdivision: 'Garhwal Lesser Himalayas',
    riskScore: 62.1,
    riskLevel: 'HIGH',
    confidence: 59.2,
    confidenceLevel: 'MEDIUM',
    historicalEvidence: 'Moderate — reservoir rim slope destabilization',
    rainfall: 'Heavy — 225mm / 72h (+95% anomaly)',
    terrain: 'Reservoir rim slopes, phyllites with sheared shear zones',
    coordinatesFormatted: { lat: '30.3810° N', lng: '78.4800° E' },
    factors: [
      { name: 'reservoir_drawdown', displayName: 'Rim Drawdown Saturation', score: 71.0, weight: 0.35, summary: 'Fluctuations in reservoir impoundment destabilizing toe' },
      { name: 'rainfall_anomaly', displayName: 'Catchment Inflow Rate', score: 66.0, weight: 0.30, summary: 'Intense short-duration spells saturating hillocks' },
      { name: 'geotechnical_class', displayName: 'Sheared Phyllite Bedrock', score: 58.0, weight: 0.20, summary: 'Weakly cemented rock prone to planar sliding' },
      { name: 'infrastructure_risk', displayName: 'Access Road Network', score: 48.0, weight: 0.15, summary: 'Local bypass corridors susceptible to blockages' },
    ],
  },
  {
    id: 'hz-rudraprayag',
    latitude: 30.284,
    longitude: 78.981,
    location: 'Rudraprayag',
    elevationM: 895,
    basin: 'Mandakini / Alaknanda Confluence',
    subdivision: 'Kedarnath Pilgrimage Route',
    riskScore: 55.8,
    riskLevel: 'HIGH',
    confidence: 52.4,
    confidenceLevel: 'MEDIUM',
    historicalEvidence: 'Moderate — river canyon wall failures',
    rainfall: 'Elevated — 180mm / 72h (+60% anomaly)',
    terrain: 'River-cut valley walls, quartzitic and amphibolite terraces',
    coordinatesFormatted: { lat: '30.2840° N', lng: '78.9810° E' },
    factors: [
      { name: 'fluvial_undercutting', displayName: 'River Toe Erosion', score: 64.0, weight: 0.35, summary: 'Turbulent monsoon river discharges undercutting rock face' },
      { name: 'rainfall_anomaly', displayName: 'Localized Downpours', score: 58.0, weight: 0.30, summary: 'Valley convection currents creating rapid runoff' },
      { name: 'joint_spacing', displayName: 'Steep Rock Jointing', score: 51.0, weight: 0.20, summary: 'Multiple intersecting joint sets facilitating wedge failures' },
      { name: 'transportation_hazard', displayName: 'NH-107 Confluence Link', score: 52.0, weight: 0.15, summary: 'Critical bottleneck junction for pilgrimage routes' },
    ],
  },
  {
    id: 'hz-mangan',
    latitude: 27.509,
    longitude: 88.534,
    location: 'Mangan',
    elevationM: 1310,
    basin: 'Upper Teesta Basin',
    subdivision: 'North Sikkim District',
    riskScore: 45.2,
    riskLevel: 'MODERATE',
    confidence: 48.7,
    confidenceLevel: 'LOW',
    historicalEvidence: 'Low — 2 events since 2018',
    rainfall: 'Moderate — 120mm / 72h (Normal monsoon range)',
    terrain: 'Forest-covered ridge with moderate glacial till cover',
    coordinatesFormatted: { lat: '27.5090° N', lng: '88.5340° E' },
    factors: [
      { name: 'slope_angle', displayName: 'Moderate Ridge Incline', score: 48.0, weight: 0.35, summary: '25-35° forested slope with natural root cohesion' },
      { name: 'rainfall_anomaly', displayName: 'Stable Rainfall Pattern', score: 42.0, weight: 0.30, summary: 'No significant deviation from historical seasonal median' },
      { name: 'soil_cohesion', displayName: 'Glacial Till Stability', score: 46.0, weight: 0.20, summary: 'Cohesive till matrix with moderate drainage capacity' },
      { name: 'connectivity', displayName: 'North Sikkim Highway', score: 45.0, weight: 0.15, summary: 'Single lane arterial with sporadic debris clearance' },
    ],
  },
  {
    id: 'hz-pelling',
    latitude: 27.3,
    longitude: 88.24,
    location: 'Pelling',
    elevationM: 2150,
    basin: 'Rangit River Basin',
    subdivision: 'West Sikkim Foothills',
    riskScore: 38.7,
    riskLevel: 'MODERATE',
    confidence: 44.2,
    confidenceLevel: 'LOW',
    historicalEvidence: 'Low — isolated minor rockfalls',
    rainfall: 'Moderate — 105mm / 72h (-5% baseline)',
    terrain: 'Moderate slope, stable granitic gneiss geology',
    coordinatesFormatted: { lat: '27.3000° N', lng: '88.2400° E' },
    factors: [
      { name: 'bedrock_competence', displayName: 'Competent Granitic Gneiss', score: 32.0, weight: 0.40, summary: 'Massive, unweathered rock formation with low fracture density' },
      { name: 'rainfall_anomaly', displayName: 'Precipitation Inflow', score: 41.0, weight: 0.30, summary: 'Sub-threshold precipitation without excessive pore pressures' },
      { name: 'slope_stability', displayName: 'Gentle Slope Profile', score: 40.0, weight: 0.20, summary: 'Stable topography with extensive dense vegetation' },
      { name: 'infrastructure', displayName: 'Touristic Road Circuit', score: 35.0, weight: 0.10, summary: 'Well-maintained road embankments and culverts' },
    ],
  },
  {
    id: 'hz-kalimpong',
    latitude: 27.061,
    longitude: 88.475,
    location: 'Kalimpong',
    elevationM: 1250,
    basin: 'Relli / Teesta Catchment',
    subdivision: 'Kalimpong District Ridge',
    riskScore: 22.4,
    riskLevel: 'LOW',
    confidence: 71.5,
    confidenceLevel: 'HIGH',
    historicalEvidence: 'Minimal — active sensor monitoring, no recent slips',
    rainfall: 'Normal — 65mm / 72h (-25% below trigger)',
    terrain: 'Gentle foothill gradient, stable quartzites',
    coordinatesFormatted: { lat: '27.0610° N', lng: '88.4750° E' },
    factors: [
      { name: 'geological_integrity', displayName: 'Quartzite Foundation', score: 20.0, weight: 0.40, summary: 'Intact bedrock with high compressive strength' },
      { name: 'rainfall_anomaly', displayName: 'Low Rainfall Intake', score: 24.0, weight: 0.30, summary: 'Rainfall well below critical infiltration threshold' },
      { name: 'monitoring_coverage', displayName: 'Ground Sensor Array', score: 18.0, weight: 0.20, summary: 'Continuous piezometer and inclinometer telemetry installed' },
      { name: 'road_condition', displayName: 'Highway Reinforcement', score: 26.0, weight: 0.10, summary: 'Bio-engineering and gabion retaining walls completed' },
    ],
  },
  {
    id: 'hz-itanagar',
    latitude: 27.101,
    longitude: 93.623,
    location: 'Itanagar',
    elevationM: 320,
    basin: 'Dikrong River Basin',
    subdivision: 'Arunachal Sub-Himalayan Foothills',
    riskScore: 18.3,
    riskLevel: 'LOW',
    confidence: 68.9,
    confidenceLevel: 'HIGH',
    historicalEvidence: 'Minimal — flat terrace plateau, zero incidents',
    rainfall: 'Normal — 58mm / 72h',
    terrain: 'Low-relief alluvial plateau edge, low slope angle (<15°)',
    coordinatesFormatted: { lat: '27.1010° N', lng: '93.6230° E' },
    factors: [
      { name: 'topographic_slope', displayName: 'Alluvial Flat Gradient', score: 14.0, weight: 0.45, summary: 'Gentle terrain incapable of gravitational mass movement' },
      { name: 'rainfall_anomaly', displayName: 'Sub-threshold Rainfall', score: 22.0, weight: 0.30, summary: 'Normal hydrological discharge rates through river plains' },
      { name: 'seismic_coefficient', displayName: 'Sub-plateau Rigidity', score: 18.0, weight: 0.15, summary: 'Stable river terrace sediments with deep water table' },
      { name: 'settlement_safety', displayName: 'Urban Plan Buffers', score: 16.0, weight: 0.10, summary: 'Adequate clearance from cliff edges and flood zones' },
    ],
  },
];

/* Himalayan Transportation Road Network GeoJSON Corridors (OSM Northern Zone Corridors) */
export const MOCK_ROAD_NETWORK: GeoJsonFeatureCollection<{
  id: string;
  wayId: string;
  name: string;
  highwayClass: string;
  status: 'open' | 'caution' | 'critical';
  surface: string;
}> = {
  type: 'FeatureCollection',
  features: [
    // NH-58: Rishikesh — Devprayag — Srinagar — Rudraprayag — Chamoli — Joshimath — Badrinath
    {
      type: 'Feature',
      id: 'road-nh58',
      properties: {
        id: 'road-nh58',
        wayId: '33815196',
        name: 'NH-58 (Badrinath Lifeline Corridor)',
        highwayClass: 'trunk',
        status: 'critical',
        surface: 'asphalt',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [78.48, 30.381], // Tehri/Srinagar
          [78.981, 30.284], // Rudraprayag
          [79.22, 30.32], // Karnaprayag
          [79.45, 30.35], // Nandaprayag
          [79.5603, 30.2936], // Chamoli
          [79.54, 30.45], // Helang
          [79.564, 30.555], // Joshimath
          [79.49, 30.74], // Badrinath
        ],
      },
    },
    // NH-107: Rudraprayag — Tilwara — Agastmuni — Guptkashi — Sonprayag — Kedarnath
    {
      type: 'Feature',
      id: 'road-nh107',
      properties: {
        id: 'road-nh107',
        wayId: '41924830',
        name: 'NH-107 (Mandakini Valley Corridor)',
        highwayClass: 'primary',
        status: 'caution',
        surface: 'asphalt',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [78.981, 30.284], // Rudraprayag
          [79.03, 30.38], // Tilwara
          [79.07, 30.52], // Guptkashi
          [79.02, 30.63], // Sonprayag
          [79.066, 30.735], // Kedarnath
        ],
      },
    },
    // NH-10: Siliguri — Sevoke — Kalimpong Junction — Rangpo — Singtam — Gangtok
    {
      type: 'Feature',
      id: 'road-nh10',
      properties: {
        id: 'road-nh10',
        wayId: '58201447',
        name: 'NH-10 (Sikkim Lifeline Corridor)',
        highwayClass: 'trunk',
        status: 'caution',
        surface: 'asphalt',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [88.43, 26.72], // Siliguri
          [88.47, 26.88], // Sevoke
          [88.475, 27.061], // Kalimpong
          [88.52, 27.17], // Rangpo
          [88.49, 27.23], // Singtam
          [88.6139, 27.3314], // Gangtok
        ],
      },
    },
    // NH-310: Gangtok — Karponang — Tsomgo Lake — Nathu La Pass
    {
      type: 'Feature',
      id: 'road-nh310',
      properties: {
        id: 'road-nh310',
        wayId: '72341109',
        name: 'NH-310 (Nathu La High-Altitude Arterial)',
        highwayClass: 'secondary',
        status: 'open',
        surface: 'asphalt',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [88.6139, 27.3314], // Gangtok
          [88.72, 27.37], // Tsomgo
          [88.83, 27.39], // Nathu La
        ],
      },
    },
    // North Sikkim Highway: Gangtok — Dikchu — Mangan — Chungthang
    {
      type: 'Feature',
      id: 'road-north-sikkim',
      properties: {
        id: 'road-north-sikkim',
        wayId: '91023475',
        name: 'North Sikkim Highway (Teesta Valley)',
        highwayClass: 'secondary',
        status: 'caution',
        surface: 'paved',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [88.6139, 27.3314], // Gangtok
          [88.58, 27.42], // Dikchu
          [88.534, 27.509], // Mangan
          [88.64, 27.60], // Chungthang
        ],
      },
    },
    // Hill Cart Road: Siliguri — Kurseong — Ghum — Darjeeling
    {
      type: 'Feature',
      id: 'road-darjeeling-hill',
      properties: {
        id: 'road-darjeeling-hill',
        wayId: '65834021',
        name: 'Hill Cart Road (Darjeeling Ridge Highway)',
        highwayClass: 'primary',
        status: 'caution',
        surface: 'asphalt',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [88.43, 26.72], // Siliguri
          [88.27, 26.88], // Kurseong
          [88.24, 27.01], // Ghum
          [88.266, 27.041], // Darjeeling
          [88.24, 27.3], // Pelling link
        ],
      },
    },
  ],
};

export interface RoadMeta {
  id: string;
  wayId: string;
  name: string;
  highwayClass: string;
  status: 'open' | 'caution' | 'critical';
}

export const MOCK_ROADS_LIST: RoadMeta[] = MOCK_ROAD_NETWORK.features.map((f) => ({
  id: f.properties.id,
  wayId: f.properties.wayId,
  name: f.properties.name,
  highwayClass: f.properties.highwayClass,
  status: f.properties.status,
}));

const HAZARD_TO_CORRIDOR: Record<string, string> = {
  chamoli: 'road-nh58',
  joshimath: 'road-nh58',
  kedarnath: 'road-nh107',
  gangtok: 'road-nh10',
  'nathu-la': 'road-nh310',
  mangan: 'road-north-sikkim',
  darjeeling: 'road-darjeeling-hill',
  tehri: 'road-nh58',
  munsiari: 'road-nh58',
  pelling: 'road-darjeeling-hill',
};

export function getAdjacentCorridor(hazardId: string): RoadMeta | undefined {
  const roadId = HAZARD_TO_CORRIDOR[hazardId] ?? 'road-nh58';
  return MOCK_ROADS_LIST.find((r) => r.id === roadId);
}

export function getDetailedHazardById(id: string): DetailedHazard | undefined {
  return MOCK_HAZARDS.find((h) => h.id === id);
}

/* Evidence pillar grouping for Phase 3 Risk Story panel */

const HISTORICAL_FACTOR_NAMES = new Set([
  'historical_proximity',
  'past_subsidence',
  'historical_evidence',
  'historical_stability',
  'monitoring_coverage',
]);

const RAINFALL_FACTOR_NAMES = new Set([
  'rainfall_anomaly',
  'rainfall_infiltration',
  'catchment_inflow',
  'localized_downpours',
  'stable_rainfall',
  'monsoon_saturation',
  'high_intensity_precipitation',
  'precipitation_inflow',
  'sub_threshold_rainfall',
  'low_rainfall_intake',
]);

const TERRAIN_FACTOR_NAMES = new Set([
  'slope_steepness',
  'slope_angle',
  'slope_loading',
  'slope_stability',
  'geological_bedding',
  'geological_integrity',
  'bedrock_competence',
  'soil_depth',
  'soil_cohesion',
  'geotechnical_class',
  'subsidence_velocity',
  'fluvial_undercutting',
  'joint_spacing',
  'drainage_choking',
  'reservoir_drawdown',
  'topographic_slope',
  'seismic_coefficient',
]);

export interface EvidenceGroup {
  pillar: 'historical' | 'rainfall' | 'terrain';
  label: string;
  sublabel: string;
  score: number | null; // null = data pending
  weight: number | null;
  summary: string | null;
  rawText: string; // always available from hazard text fields
  pending: boolean;
}

export function getEvidenceGroups(hazard: DetailedHazard): EvidenceGroup[] {
  const find = (set: Set<string>) =>
    hazard.factors.find((f) => set.has(f.name)) ?? null;

  const historicalFactor = find(HISTORICAL_FACTOR_NAMES);
  const rainfallFactor = find(RAINFALL_FACTOR_NAMES);
  const terrainFactor = find(TERRAIN_FACTOR_NAMES);

  return [
    {
      pillar: 'historical',
      label: 'Historical Evidence',
      sublabel: 'GSI Landslide Inventory',
      score: historicalFactor?.score ?? null,
      weight: historicalFactor?.weight ?? null,
      summary: historicalFactor?.summary ?? null,
      rawText: hazard.historicalEvidence,
      pending: historicalFactor === null,
    },
    {
      pillar: 'rainfall',
      label: 'Rainfall Signal',
      sublabel: 'IMD 72h Precipitation',
      score: rainfallFactor?.score ?? null,
      weight: rainfallFactor?.weight ?? null,
      summary: rainfallFactor?.summary ?? null,
      rawText: hazard.rainfall,
      pending: rainfallFactor === null,
    },
    {
      pillar: 'terrain',
      label: 'Terrain Signal',
      sublabel: 'Geological & Slope Assessment',
      score: terrainFactor?.score ?? null,
      weight: terrainFactor?.weight ?? null,
      summary: terrainFactor?.summary ?? null,
      rawText: hazard.terrain,
      pending: terrainFactor === null,
    },
  ];
}

export function getRiskAssessmentConclusion(hazard: DetailedHazard): string {
  const topFactor = [...hazard.factors].sort((a, b) => b.score * b.weight - a.score * a.weight)[0];
  const secondFactor = [...hazard.factors].sort((a, b) => b.score * b.weight - a.score * a.weight)[1];

  switch (hazard.riskLevel) {
    case 'CRITICAL':
      return `${topFactor.displayName} and ${secondFactor?.displayName ?? 'compound signals'} converge to exceed critical thresholds. Immediate monitoring recommended.`;
    case 'HIGH':
      return `${topFactor.displayName} drives elevated instability. ${secondFactor?.displayName ?? 'Secondary signals'} compound the risk. Enhanced surveillance warranted.`;
    case 'MODERATE':
      return `${topFactor.displayName} warrants precautionary observation. Conditions are manageable but require continued monitoring.`;
    case 'LOW':
      return `Current conditions within acceptable parameters. ${topFactor.displayName} remains stable. Routine sensor monitoring maintained.`;
    default:
      return 'Insufficient signal data for definitive assessment.';
  }
}

export function hazardsToGeoJSON(
  hazards: DetailedHazard[] = MOCK_HAZARDS,
  selectedId: string | null = null,
): GeoJsonFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: hazards.map((h) => ({
      type: 'Feature',
      id: h.id,
      geometry: {
        type: 'Point',
        coordinates: [h.longitude, h.latitude],
      },
      properties: {
        id: h.id,
        location: h.location,
        riskScore: h.riskScore,
        riskLevel: h.riskLevel,
        confidence: h.confidence,
        rainfall: h.rainfall,
        terrain: h.terrain,
        elevationM: h.elevationM,
        selected: h.id === selectedId,
      },
    })),
  };
}
