/**
 * Road Impact Simulation Types & Contracts
 *
 * Operational simulations are performed by the certified FastAPI backend:
 * POST /api/v1/impact/simulate-road-blockage
 *
 * No synthetic, mock, or hardcoded road failure data is generated.
 */

export type IsolationSeverity = 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';

export type SimulationPhase = 'idle' | 'selected' | 'simulating' | 'failed';

/** Matches the API request body */
export interface RoadBlockageRequest {
  wayId: string;
  roadId: string;
  latitude?: number;
  longitude?: number;
  direction?: 'both' | 'forward' | 'backward';
}

/** Network connectivity snapshot */
export interface ConnectivitySnapshot {
  components: number;
  nodes: number;
}

/** Matches the UI representation of backend simulation results */
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
  isBridgeEdge?: boolean;
  limitations?: string[];
}
