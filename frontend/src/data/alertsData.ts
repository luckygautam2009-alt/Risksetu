/**
 * Spatial Alerts & Operational Decision Support
 *
 * Each alert is spatially anchored to a hazard/corridor point and
 * includes prioritized immediate actions with operational lifecycle states.
 */

import type { GeoJsonFeatureCollection } from '../types';

export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MODERATE';
export type AlertStatus = 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED';
export type UserRole = 'Incident Commander' | 'Field Analyst' | 'Disaster Response Lead';

export interface AlertActionItem {
  id: string;
  label: string;
  targetAgency: string;
  completed: boolean;
}

export interface SpatialAlert {
  id: string;
  hazardId: string;
  location: string;
  corridorName: string;
  wayId: string;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  summary: string;
  immediateActions: AlertActionItem[];
  latitude: number;
  longitude: number;
  triggeredAt: string;
  acknowledgedBy?: string;
  resolvedBy?: string;
}

export const MOCK_ALERTS: SpatialAlert[] = [
  {
    id: 'alert-chamoli-01',
    hazardId: 'chamoli',
    location: 'CHAMOLI',
    corridorName: 'NH-58 Badrinath Lifeline Corridor',
    wayId: '33815196',
    severity: 'CRITICAL',
    status: 'ACTIVE',
    title: 'CRITICAL ALERT: Slope Failure & Lifeline Severance Threat',
    summary: 'High-volume rainfall anomaly and joint rock mass instability threaten complete arterial isolation of 42 downstream settlements.',
    immediateActions: [
      { id: 'act-1', label: 'Assess road connectivity', targetAgency: 'PWD & Border Roads', completed: false },
      { id: 'act-2', label: 'Verify field conditions', targetAgency: 'SDRF Field Recon Unit', completed: false },
      { id: 'act-3', label: 'Prepare downstream warning', targetAgency: 'District Emergency Operations (DEOC)', completed: false },
    ],
    latitude: 30.2936,
    longitude: 79.5603,
    triggeredAt: '8 mins ago',
  },
  {
    id: 'alert-joshimath-01',
    hazardId: 'joshimath',
    location: 'JOSHIMATH',
    corridorName: 'NH-58 Upper Badrinath Spur',
    wayId: '33815196',
    severity: 'CRITICAL',
    status: 'ACTIVE',
    title: 'CRITICAL ALERT: Rapid Embankment Subsidence',
    summary: 'Continuous groundwater saturation accelerating toe deformation along key pilgrim transit spur.',
    immediateActions: [
      { id: 'act-4', label: 'Assess road connectivity', targetAgency: 'BRO Heavy Transit Cell', completed: false },
      { id: 'act-5', label: 'Verify field conditions', targetAgency: 'Geotechnical Recon Team', completed: false },
      { id: 'act-6', label: 'Prepare downstream warning', targetAgency: 'Local Municipal Council', completed: false },
    ],
    latitude: 30.555,
    longitude: 79.564,
    triggeredAt: '24 mins ago',
  },
  {
    id: 'alert-rudraprayag-01',
    hazardId: 'rudraprayag',
    location: 'RUDRAPRAYAG',
    corridorName: 'NH-107 Mandakini Valley Corridor',
    wayId: '41924830',
    severity: 'HIGH',
    status: 'ACKNOWLEDGED',
    title: 'HIGH ALERT: Valley Corridor Flash Undercut',
    summary: 'Mandakini River swell eroding road embankment toe; single-lane traffic restriction recommended.',
    immediateActions: [
      { id: 'act-7', label: 'Assess road connectivity', targetAgency: 'Traffic Control Division', completed: true },
      { id: 'act-8', label: 'Verify field conditions', targetAgency: 'Forestry & Soil Patrol', completed: false },
      { id: 'act-9', label: 'Prepare downstream warning', targetAgency: 'DEOC Rudraprayag', completed: false },
    ],
    latitude: 30.284,
    longitude: 78.981,
    triggeredAt: '42 mins ago',
    acknowledgedBy: 'Incident Commander (Capt. Rawat)',
  },
  {
    id: 'alert-gangtok-01',
    hazardId: 'gangtok',
    location: 'GANGTOK',
    corridorName: 'NH-10 Sikkim Lifeline Corridor',
    wayId: '58201447',
    severity: 'HIGH',
    status: 'ACTIVE',
    title: 'HIGH ALERT: Trans-Basin Sediment Spillway Surge',
    summary: 'Surface debris torrent overflowing culvert network along eastern hill flank.',
    immediateActions: [
      { id: 'act-10', label: 'Assess road connectivity', targetAgency: 'Sikkim PWD', completed: false },
      { id: 'act-11', label: 'Verify field conditions', targetAgency: 'District Disaster Unit', completed: false },
      { id: 'act-12', label: 'Prepare downstream warning', targetAgency: 'Urban Local Body', completed: false },
    ],
    latitude: 27.3314,
    longitude: 88.6139,
    triggeredAt: '1h 15m ago',
  },
];

export function alertsToGeoJSON(
  alerts: SpatialAlert[] = MOCK_ALERTS,
  selectedId: string | null = null,
): GeoJsonFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: alerts.map((alert) => ({
      type: 'Feature',
      id: alert.id,
      geometry: {
        type: 'Point',
        coordinates: [alert.longitude, alert.latitude],
      },
      properties: {
        id: alert.id,
        location: alert.location,
        severity: alert.severity,
        status: alert.status,
        title: alert.title,
        selected: alert.id === selectedId,
      },
    })),
  };
}
