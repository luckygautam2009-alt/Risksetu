/**
 * Road Impact Simulation Service
 *
 * This module provides the simulation interface for road blockage impact analysis.
 * The `simulateRoadBlockage` function is a mock implementation that matches the
 * real backend API contract:
 *
 *   POST /api/v1/impact/simulate-road-blockage
 *   Body: { way_id: string, road_id: string, direction?: 'both' | 'forward' | 'backward' }
 *
 * To connect the real backend, replace only the body of `simulateRoadBlockage` with:
 *   const res = await fetch('/api/v1/impact/simulate-road-blockage', {
 *     method: 'POST',
 *     headers: { 'Content-Type': 'application/json' },
 *     body: JSON.stringify({ way_id: req.wayId, road_id: req.roadId, direction: req.direction }),
 *   });
 *   if (!res.ok) throw new Error(`Simulation failed: ${res.statusText}`);
 *   const data = await res.json();
 *   return mapApiResponse(data); // snake_case → camelCase
 */

export type IsolationSeverity = 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';

export type SimulationPhase = 'idle' | 'selected' | 'simulating' | 'failed';

/** Matches the API request body (camelCase) */
export interface RoadBlockageRequest {
  wayId: string;
  roadId: string;
  direction?: 'both' | 'forward' | 'backward';
}

/** Network connectivity snapshot */
export interface ConnectivitySnapshot {
  components: number;
  nodes: number;
}

/** Matches the API response (camelCase mapping of snake_case JSON) */
export interface SimulationResult {
  wayId: string;
  roadName: string;
  highwayClass: string;
  status: 'open' | 'caution' | 'critical';
  before: ConnectivitySnapshot;
  after: ConnectivitySnapshot;
  nodesAffected: number;
  deltaComponents: number;
  isolationSeverity: IsolationSeverity;
  affectedCoordinates: [number, number][];
  isolatedSegmentIds: string[];
  simulatedAt: string;
}

/* ── Mock results (keyed by road feature ID) ──────────────────────────── */

const MOCK_RESULTS: Record<string, SimulationResult> = {
  'road-nh58': {
    wayId: '33815196',
    roadName: 'NH-58 Badrinath Lifeline Corridor',
    highwayClass: 'trunk',
    status: 'critical',
    before: { components: 18, nodes: 284 },
    after: { components: 19, nodes: 284 },
    nodesAffected: 42,
    deltaComponents: 1,
    isolationSeverity: 'CRITICAL',
    affectedCoordinates: [
      [79.5603, 30.2936],
      [79.54, 30.45],
      [79.564, 30.555],
      [79.49, 30.74],
    ],
    isolatedSegmentIds: ['road-nh107'],
    simulatedAt: '',
  },
  'road-nh107': {
    wayId: '41924830',
    roadName: 'NH-107 Mandakini Valley Corridor',
    highwayClass: 'primary',
    status: 'caution',
    before: { components: 12, nodes: 148 },
    after: { components: 14, nodes: 148 },
    nodesAffected: 18,
    deltaComponents: 2,
    isolationSeverity: 'HIGH',
    affectedCoordinates: [
      [79.03, 30.38],
      [79.07, 30.52],
      [79.02, 30.63],
      [79.066, 30.735],
    ],
    isolatedSegmentIds: [],
    simulatedAt: '',
  },
  'road-nh10': {
    wayId: '58201447',
    roadName: 'NH-10 Sikkim Lifeline Corridor',
    highwayClass: 'trunk',
    status: 'caution',
    before: { components: 15, nodes: 196 },
    after: { components: 16, nodes: 196 },
    nodesAffected: 28,
    deltaComponents: 1,
    isolationSeverity: 'CRITICAL',
    affectedCoordinates: [
      [88.52, 27.17],
      [88.49, 27.23],
      [88.6139, 27.3314],
    ],
    isolatedSegmentIds: ['road-nh310', 'road-north-sikkim'],
    simulatedAt: '',
  },
  'road-nh310': {
    wayId: '72341109',
    roadName: 'NH-310 Nathu La High-Altitude Arterial',
    highwayClass: 'secondary',
    status: 'open',
    before: { components: 8, nodes: 72 },
    after: { components: 9, nodes: 72 },
    nodesAffected: 12,
    deltaComponents: 1,
    isolationSeverity: 'MODERATE',
    affectedCoordinates: [
      [88.72, 27.37],
      [88.83, 27.39],
    ],
    isolatedSegmentIds: [],
    simulatedAt: '',
  },
  'road-north-sikkim': {
    wayId: '91023475',
    roadName: 'North Sikkim Highway (Teesta Valley)',
    highwayClass: 'secondary',
    status: 'caution',
    before: { components: 10, nodes: 124 },
    after: { components: 11, nodes: 124 },
    nodesAffected: 15,
    deltaComponents: 1,
    isolationSeverity: 'HIGH',
    affectedCoordinates: [
      [88.58, 27.42],
      [88.534, 27.509],
      [88.64, 27.60],
    ],
    isolatedSegmentIds: [],
    simulatedAt: '',
  },
  'road-darjeeling-hill': {
    wayId: '65834021',
    roadName: 'Hill Cart Road (Darjeeling Ridge Highway)',
    highwayClass: 'primary',
    status: 'caution',
    before: { components: 9, nodes: 118 },
    after: { components: 10, nodes: 118 },
    nodesAffected: 22,
    deltaComponents: 1,
    isolationSeverity: 'HIGH',
    affectedCoordinates: [
      [88.27, 26.88],
      [88.24, 27.01],
      [88.266, 27.041],
      [88.24, 27.3],
    ],
    isolatedSegmentIds: [],
    simulatedAt: '',
  },
};

/**
 * Simulate a road blockage and return connectivity impact analysis.
 *
 * ── MOCK IMPLEMENTATION ──
 * Replace this function body with a real fetch() to connect the live backend.
 * The interface (RoadBlockageRequest → SimulationResult) remains unchanged.
 */
export async function simulateRoadBlockage(
  req: RoadBlockageRequest,
): Promise<SimulationResult> {
  // Simulate backend processing latency (800ms matches real API baseline)
  await new Promise<void>((resolve) => setTimeout(resolve, 820));

  const base = MOCK_RESULTS[req.roadId];
  if (!base) {
    throw new Error(`No simulation data for road ID: ${req.roadId}`);
  }

  return { ...base, simulatedAt: new Date().toISOString() };
}
