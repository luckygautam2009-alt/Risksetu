export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export type LayerId =
  | 'live-risk'
  | 'historical-landslides'
  | 'community-signals'
  | 'sos'
  | 'alerts'
  | 'road-network'
  | 'road-risk'
  | 'landslides'
  | 'risk'
  | 'rainfall'
  | 'roads'
  | 'ground-intelligence'
  | 'terrain';

export type SystemStatus = 'operational' | 'degraded' | 'offline' | 'calibrating';

export type DataSource = 'GSI' | 'IMD' | 'OSM';

export interface LayerItem {
  id: LayerId;
  label: string;
  active: boolean;
  category: 'terrain' | 'hazard' | 'network' | 'intelligence';
}

export interface Hazard {
  id: string;
  latitude: number;
  longitude: number;
  location: string;
  riskScore: number;
  riskLevel: RiskLevel;
  confidence: number;
  historicalEvidence: string;
  rainfall: string;
  terrain: string;
}

import type { Feature, FeatureCollection, Geometry } from 'geojson';

export type GeoJsonFeature<P = Record<string, unknown>> = Feature<Geometry, P>;
export type GeoJsonFeatureCollection<P = Record<string, unknown>> = FeatureCollection<Geometry, P>;

