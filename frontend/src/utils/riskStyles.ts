import type { RiskLevel } from '../types';

export const RISK_COLORS: Record<RiskLevel, string> = {
  LOW: '#6b8f71',
  MODERATE: '#b8a04a',
  HIGH: '#c45c3e',
  CRITICAL: '#8b2942',
};

export const RISK_RADIUS: Record<RiskLevel, number> = {
  LOW: 7,
  MODERATE: 10,
  HIGH: 14,
  CRITICAL: 18,
};

export function getRiskColor(level: RiskLevel): string {
  return RISK_COLORS[level];
}

export function getRiskRadius(level: RiskLevel, selected = false): number {
  const base = RISK_RADIUS[level];
  return selected ? base * 1.45 : base;
}

export function formatCoordinate(lat: number, lng: number): { lat: string; lng: string } {
  const latDir = lat >= 0 ? 'N' : 'S';
  const lngDir = lng >= 0 ? 'E' : 'W';
  return {
    lat: `${Math.abs(lat).toFixed(4)}° ${latDir}`,
    lng: `${Math.abs(lng).toFixed(4)}° ${lngDir}`,
  };
}
