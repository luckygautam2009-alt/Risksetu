import type { LayerItem } from '../types';

export const DEFAULT_LAYERS: LayerItem[] = [
  { id: 'live-risk', label: 'LIVE RISK', active: true, category: 'intelligence' },
  { id: 'historical-landslides', label: 'HISTORICAL GSI', active: true, category: 'hazard' },
  { id: 'community-signals', label: 'COMMUNITY SIGNALS', active: true, category: 'intelligence' },
  { id: 'sos', label: 'SOS EVENTS', active: true, category: 'intelligence' },
  { id: 'alerts', label: 'ALERTS', active: true, category: 'intelligence' },
  { id: 'road-network', label: 'ROAD NETWORK', active: true, category: 'network' },
  { id: 'road-risk', label: 'ROAD RISK', active: true, category: 'network' },
];

export function isLayerActive(layers: LayerItem[], id: string): boolean {
  // Support aliases for layer IDs
  if (id === 'landslides') return layers.find((l) => l.id === 'historical-landslides' || l.id === 'landslides')?.active ?? false;
  if (id === 'risk') return layers.find((l) => l.id === 'live-risk' || l.id === 'risk')?.active ?? false;
  if (id === 'roads') return layers.find((l) => l.id === 'road-network' || l.id === 'roads')?.active ?? false;
  if (id === 'ground-intelligence') return layers.find((l) => l.id === 'community-signals' || l.id === 'ground-intelligence')?.active ?? false;
  return layers.find((l) => l.id === id)?.active ?? false;
}

export function areHazardsVisible(layers: LayerItem[]): boolean {
  return isLayerActive(layers, 'historical-landslides') || isLayerActive(layers, 'live-risk');
}

