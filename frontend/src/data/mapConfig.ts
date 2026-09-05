const envStyle = import.meta.env.VITE_MAP_STYLE as string | undefined;
const envApiKey = import.meta.env.VITE_MAP_API_KEY as string | undefined;

function resolveMapStyle(): string {
  if (!envStyle) {
    // Default: CARTO Positron vector tiles (OpenStreetMap-based, legitimate real cartographic basemap, zero API key required)
    return 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
  }
  if (envApiKey && envStyle.includes('{key}')) {
    return envStyle.replace('{key}', envApiKey);
  }
  return envStyle;
}

export const MAP_CONFIG = {
  style: resolveMapStyle(),
  center: [79.56, 30.38] as [number, number], // Focused on Himalayan risk corridor
  zoom: 6.8,
  minZoom: 4,
  maxZoom: 14,
  flyToZoom: 10.2,
  flyToDuration: 1200,
} as const;

export const MAP_LAYER_IDS = {
  roadsCasing: 'roads-casing',
  roads: 'roads-layer',
  roadsHighlight: 'roads-highlight-layer',
  roadsFailed: 'roads-failed-layer',
  roadsIsolated: 'roads-isolated-layer',
  roadsLabel: 'roads-label',
  impactNodesPulse: 'impact-nodes-pulse',
  impactNodes: 'impact-nodes-layer',
  impactNodesLabel: 'impact-nodes-label',
  hazardsPulse: 'hazards-pulse',
  hazardsGlow: 'hazards-glow',
  hazards: 'hazards',
  hazardsSelected: 'hazards-selected',
  hazardsLabel: 'hazards-label',
  groundIntelGlow: 'ground-intel-glow',
  groundIntel: 'ground-intel-layer',
  groundIntelLabel: 'ground-intel-label',
  alertsPulse: 'alerts-pulse',
  alerts: 'alerts-layer',
  alertsLabel: 'alerts-label',
  sosPulse: 'sos-pulse',
  sos: 'sos-layer',
  sosLabel: 'sos-label',
  landslidesClusters: 'landslides-clusters',
  landslidesClusterCount: 'landslides-cluster-count',
  landslidesUnclustered: 'landslides-unclustered',
  landslidesLabel: 'landslides-label',
  liveRiskMarkerPulse: 'live-risk-marker-pulse',
  liveRiskMarker: 'live-risk-marker',
} as const;

export const MAP_SOURCE_IDS = {
  hazards: 'hazards-source',
  roads: 'roads-source',
  impactNodes: 'impact-nodes-source',
  groundIntel: 'ground-intel-source',
  alerts: 'alerts-source',
  sos: 'sos-source',
  landslides: 'landslides-source',
  liveRiskPoint: 'live-risk-point-source',
} as const;

