import type { LayerItem } from '../types';

export const DEFAULT_LAYERS: LayerItem[] = [
  { id: 'terrain', label: 'Terrain', active: true, category: 'terrain' },
  { id: 'landslides', label: 'Landslides', active: true, category: 'hazard' },
  { id: 'rainfall', label: 'Rainfall', active: false, category: 'hazard' },
  { id: 'roads', label: 'Road Network', active: true, category: 'network' },
  { id: 'risk', label: 'Risk Assessment', active: true, category: 'intelligence' },
  { id: 'ground-intelligence', label: 'Ground Intel', active: true, category: 'intelligence' },
  { id: 'alerts', label: 'Active Alerts', active: true, category: 'intelligence' },
];

export function isLayerActive(layers: LayerItem[], id: string): boolean {
  return layers.find((l) => l.id === id)?.active ?? false;
}

export function areHazardsVisible(layers: LayerItem[]): boolean {
  return isLayerActive(layers, 'landslides') || isLayerActive(layers, 'risk') || isLayerActive(layers, 'rainfall');
}

