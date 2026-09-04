/**
 * Intervention Priority Engine & Ranked List
 *
 * Operational Priority Formula:
 *   Priority Score = (Risk Score * 0.40) + (Isolation Impact * 0.45) + (Urgency * 0.15)
 *
 * CORE PHILOSOPHY:
 *   RISK ≠ PRIORITY
 *
 * A location with elevated physical risk but low isolation (redundant routes)
 * receives LOWER operational priority than a location with moderate risk
 * whose failure completely isolates dozens of communities.
 */

export type PriorityLevel = 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';

export interface PriorityItem {
  rank: number;
  id: string;
  hazardId: string;
  location: string;
  subdivision: string;
  priorityLevel: PriorityLevel;
  priorityScore: number; // 0-100
  riskScore: number; // 0-100
  isolationSeverity: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  isolationNodes: number; // e.g. +42 nodes
  urgency: 'IMMEDIATE' | 'ELEVATED' | 'STANDARD' | 'ROUTINE';
  contrastReason: string; // Explains why Risk ≠ Priority here
  latitude: number;
  longitude: number;
  adjacentCorridor: string;
  wayId: string;
}

export const RANKED_PRIORITY_LIST: PriorityItem[] = [
  {
    rank: 1,
    id: 'prio-chamoli',
    hazardId: 'chamoli',
    location: 'CHAMOLI',
    subdivision: 'Chamoli District, Uttarakhand',
    priorityLevel: 'CRITICAL',
    priorityScore: 99.2,
    riskScore: 98.9,
    isolationSeverity: 'CRITICAL',
    isolationNodes: 42,
    urgency: 'IMMEDIATE',
    contrastReason: 'Peak physical risk compound with catastrophic single-artery isolation (+42 nodes cutoff).',
    latitude: 30.2936,
    longitude: 79.5603,
    adjacentCorridor: 'NH-58 (Badrinath Lifeline Corridor)',
    wayId: '33815196',
  },
  {
    rank: 2,
    id: 'prio-joshimath',
    hazardId: 'joshimath',
    location: 'JOSHIMATH',
    subdivision: 'Alaknanda Gorge, Uttarakhand',
    priorityLevel: 'CRITICAL',
    priorityScore: 94.6,
    riskScore: 91.4,
    isolationSeverity: 'CRITICAL',
    isolationNodes: 36,
    urgency: 'IMMEDIATE',
    contrastReason: 'Severe valley slope subsidence threats sever upper pilgrim and military border lifelines.',
    latitude: 30.555,
    longitude: 79.564,
    adjacentCorridor: 'NH-58 (Upper Alaknanda Arterial)',
    wayId: '33815196',
  },
  {
    rank: 3,
    id: 'prio-rudraprayag',
    hazardId: 'rudraprayag',
    location: 'RUDRAPRAYAG',
    subdivision: 'Garhwal Division, Uttarakhand',
    priorityLevel: 'HIGH',
    priorityScore: 88.5,
    riskScore: 87.2,
    isolationSeverity: 'HIGH',
    isolationNodes: 18,
    urgency: 'ELEVATED',
    contrastReason: 'Confluence undercut threatens Mandakini spine corridor (+18 downstream nodes).',
    latitude: 30.284,
    longitude: 78.981,
    adjacentCorridor: 'NH-107 (Mandakini Valley Corridor)',
    wayId: '41924830',
  },
  {
    rank: 4,
    id: 'prio-gangtok',
    hazardId: 'gangtok',
    location: 'GANGTOK',
    subdivision: 'East Sikkim, Sikkim',
    priorityLevel: 'HIGH',
    priorityScore: 86.8,
    riskScore: 84.1,
    isolationSeverity: 'HIGH',
    isolationNodes: 28,
    urgency: 'ELEVATED',
    contrastReason: 'NH-10 represents the solitary heavy transit artery into the Sikkim state capital.',
    latitude: 27.3314,
    longitude: 88.6139,
    adjacentCorridor: 'NH-10 (Sikkim Lifeline Corridor)',
    wayId: '58201447',
  },
  {
    rank: 5,
    id: 'prio-tehri',
    hazardId: 'tehri',
    location: 'TEHRI REGION',
    subdivision: 'Tehri Garhwal, Uttarakhand',
    priorityLevel: 'HIGH',
    priorityScore: 78.4,
    riskScore: 92.0, // HIGHER RISK THAN RUDRAPRAYAG OR GANGTOK!
    isolationSeverity: 'LOW', // BUT ZERO NETWORK ISOLATION (Redundant bypass available)
    isolationNodes: 0,
    urgency: 'STANDARD',
    contrastReason: 'EXEMPLIFIES RISK ≠ PRIORITY: High physical hazard (92.0) but LOW isolation (0 nodes cutoff) lowers operational intervention ranking below Rudraprayag.',
    latitude: 30.381,
    longitude: 78.48,
    adjacentCorridor: 'NH-58 Bypass (Multi-lane Redundancy)',
    wayId: '33815196',
  },
  {
    rank: 6,
    id: 'prio-mangan',
    hazardId: 'mangan',
    location: 'MANGAN',
    subdivision: 'North Sikkim, Sikkim',
    priorityLevel: 'MODERATE',
    priorityScore: 72.0,
    riskScore: 76.5,
    isolationSeverity: 'MODERATE',
    isolationNodes: 15,
    urgency: 'STANDARD',
    contrastReason: 'Monsoon saturation active along upper Teesta valley with alternative forestry tracks.',
    latitude: 27.509,
    longitude: 88.534,
    adjacentCorridor: 'North Sikkim Highway (Teesta Valley)',
    wayId: '91023475',
  },
];
