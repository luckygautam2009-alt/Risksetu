/**
 * Ground Intelligence Observations (Field & Citizen Reports)
 *
 * Each observation represents a spatially verified ground report.
 * IMPORTANT: In accordance with the system specification:
 * NEVER call trust score a probability of truth.
 * Trust score is an algorithmic composite of source reliability,
 * temporal freshness, and spatial corroboration.
 */

import type { GeoJsonFeatureCollection } from '../types';

export interface GroundObservation {
  id: string;
  hazardId?: string;
  location: string;
  title: string;
  description: string;
  category: 'ROCKFALL' | 'ROAD_CRACK' | 'DEBRIS_ACCUMULATION' | 'SLOPE_SLUMP' | 'RUNOFF_SURGE';
  trustScore: number; // e.g. 68.75
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  riskInfluence: 'ELIGIBLE' | 'EXCLUDED' | 'PROVISIONAL';
  corroboration: 'AVAILABLE' | 'PENDING' | 'SOLITARY';
  corroborationCount: number;
  reporterType: 'Field Engineer' | 'Citizen Observer' | 'Forest Warden' | 'PWD Team';
  reportedAt: string;
  latitude: number;
  longitude: number;
  status: 'VERIFIED' | 'REVIEW_PENDING';
  evidenceId?: string;
  photoUrl?: string;
}

export const MOCK_GROUND_OBSERVATIONS: GroundObservation[] = [
  {
    id: 'obs-chamoli-01',
    hazardId: 'chamoli',
    location: 'Chamoli — Helang Sector',
    title: 'Active rockfall debris spilling onto NH-58 shoulder',
    description: 'Angular quartzite boulders falling from 45° cut slope at km 284. Partial road obstruction on northbound lane.',
    category: 'ROCKFALL',
    trustScore: 68.75,
    confidence: 'HIGH',
    riskInfluence: 'ELIGIBLE',
    corroboration: 'AVAILABLE',
    corroborationCount: 3,
    reporterType: 'Field Engineer',
    reportedAt: '12 mins ago',
    latitude: 30.312,
    longitude: 79.548,
    status: 'VERIFIED',
  },
  {
    id: 'obs-joshimath-01',
    hazardId: 'joshimath',
    location: 'Joshimath — Upper Bazaar',
    title: 'Fresh transverse tension cracks on retaining embankment',
    description: 'Masonry retaining wall showing 15mm extension fractures after continuous seepage outflow.',
    category: 'ROAD_CRACK',
    trustScore: 74.20,
    confidence: 'HIGH',
    riskInfluence: 'ELIGIBLE',
    corroboration: 'AVAILABLE',
    corroborationCount: 4,
    reporterType: 'PWD Team',
    reportedAt: '28 mins ago',
    latitude: 30.562,
    longitude: 79.571,
    status: 'VERIFIED',
  },
  {
    id: 'obs-rudraprayag-01',
    hazardId: 'rudraprayag',
    location: 'Rudraprayag — Mandakini Confluence',
    title: 'Toe undercut and toe mud pooling along river road',
    description: 'River surge encroaching road foundation toe. Soil saturation visibly high with minor scree movement.',
    category: 'SLOPE_SLUMP',
    trustScore: 61.50,
    confidence: 'HIGH',
    riskInfluence: 'ELIGIBLE',
    corroboration: 'AVAILABLE',
    corroborationCount: 2,
    reporterType: 'Forest Warden',
    reportedAt: '45 mins ago',
    latitude: 30.291,
    longitude: 78.989,
    status: 'VERIFIED',
  },
  {
    id: 'obs-gangtok-01',
    hazardId: 'gangtok',
    location: 'Gangtok — Rangpo Link',
    title: 'Drainage culvert choked with alluvial slurry',
    description: 'Excess monsoon runoff overtopping culvert intake. Surface water sheet-flowing across highway tarmac.',
    category: 'RUNOFF_SURGE',
    trustScore: 65.10,
    confidence: 'HIGH',
    riskInfluence: 'ELIGIBLE',
    corroboration: 'AVAILABLE',
    corroborationCount: 2,
    reporterType: 'Citizen Observer',
    reportedAt: '1h 10m ago',
    latitude: 27.318,
    longitude: 88.595,
    status: 'VERIFIED',
  },
  {
    id: 'obs-mangan-01',
    hazardId: 'mangan',
    location: 'Mangan — Dikchu Spur',
    title: 'Slope slump developing above Teesta highway bend',
    description: 'Debris mantle sliding at approx 0.5m/hr. Warning signage erected by village patrol.',
    category: 'DEBRIS_ACCUMULATION',
    trustScore: 58.40,
    confidence: 'MEDIUM',
    riskInfluence: 'ELIGIBLE',
    corroboration: 'PENDING',
    corroborationCount: 1,
    reporterType: 'Citizen Observer',
    reportedAt: '2h 15m ago',
    latitude: 27.502,
    longitude: 88.541,
    status: 'REVIEW_PENDING',
  },
];

export function groundObservationsToGeoJSON(
  observations: GroundObservation[] = MOCK_GROUND_OBSERVATIONS,
  selectedId: string | null = null,
): GeoJsonFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: observations.map((obs) => ({
      type: 'Feature',
      id: obs.id,
      geometry: {
        type: 'Point',
        coordinates: [obs.longitude, obs.latitude],
      },
      properties: {
        id: obs.id,
        location: obs.location,
        title: obs.title,
        category: obs.category,
        trustScore: obs.trustScore,
        confidence: obs.confidence,
        riskInfluence: obs.riskInfluence,
        corroboration: obs.corroboration,
        selected: obs.id === selectedId,
      },
    })),
  };
}
