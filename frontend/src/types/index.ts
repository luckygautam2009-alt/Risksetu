export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export type LayerId =
  | 'landslides'
  | 'risk'
  | 'rainfall'
  | 'roads'
  | 'ground-intelligence'
  | 'alerts'
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

export interface GeoJsonFeature<P = Record<string, unknown>> {
  type: 'Feature';
  id?: string | number;
  geometry: {
    type: 'Point' | 'Polygon' | 'LineString';
    coordinates: number[] | number[][] | number[][][];
  };
  properties: P;
}

export interface GeoJsonFeatureCollection<P = Record<string, unknown>> {
  type: 'FeatureCollection';
  features: GeoJsonFeature<P>[];
}

