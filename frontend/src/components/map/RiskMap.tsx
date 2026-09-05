import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { MapLayerMouseEvent, MapMouseEvent } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

// Provide self-contained worker chunk to MapLibre in Vite
maplibregl.setWorkerUrl(maplibreWorkerUrl);
import { useMapContext } from '../../context/MapContext';
import { hazardsToGeoJSON } from '../../data/mockRiskData';
import { groundObservationsToGeoJSON } from '../../data/groundIntelligence';
import { alertsToGeoJSON } from '../../data/alertsData';
import { areHazardsVisible, isLayerActive } from '../../data/layers';
import { MAP_CONFIG, MAP_LAYER_IDS, MAP_SOURCE_IDS } from '../../data/mapConfig';
import { formatCoordinate } from '../../utils/riskStyles';
import type { LandslideItem, RoadEdgeItem, SosListItem } from '../../services/api';
import type { FeatureCollection, Point } from 'geojson';
import './RiskMap.css';

const HAZARD_LAYER_IDS = [
  MAP_LAYER_IDS.hazardsPulse,
  MAP_LAYER_IDS.hazardsGlow,
  MAP_LAYER_IDS.hazards,
  MAP_LAYER_IDS.hazardsSelected,
  MAP_LAYER_IDS.hazardsLabel,
];

const ROAD_LAYER_IDS = [
  MAP_LAYER_IDS.roadsCasing,
  MAP_LAYER_IDS.roads,
  MAP_LAYER_IDS.roadsHighlight,
  MAP_LAYER_IDS.roadsFailed,
  MAP_LAYER_IDS.roadsIsolated,
  MAP_LAYER_IDS.roadsLabel,
  MAP_LAYER_IDS.impactNodesPulse,
  MAP_LAYER_IDS.impactNodes,
  MAP_LAYER_IDS.impactNodesLabel,
];

const GROUND_INTEL_LAYER_IDS = [
  MAP_LAYER_IDS.groundIntelGlow,
  MAP_LAYER_IDS.groundIntel,
  MAP_LAYER_IDS.groundIntelLabel,
];

const ALERT_LAYER_IDS = [
  MAP_LAYER_IDS.alertsPulse,
  MAP_LAYER_IDS.alerts,
  MAP_LAYER_IDS.alertsLabel,
];

const LANDSLIDE_LAYER_IDS = [
  MAP_LAYER_IDS.landslidesClusters,
  MAP_LAYER_IDS.landslidesClusterCount,
  MAP_LAYER_IDS.landslidesUnclustered,
  MAP_LAYER_IDS.landslidesLabel,
];

const SOS_LAYER_IDS = [
  MAP_LAYER_IDS.sosPulse,
  MAP_LAYER_IDS.sos,
  MAP_LAYER_IDS.sosLabel,
];

const LIVE_RISK_LAYER_IDS = [
  MAP_LAYER_IDS.liveRiskMarkerPulse,
  MAP_LAYER_IDS.liveRiskMarker,
];

// ── GeoJSON converters for real backend data ─────────────────────────────
function landslidesToGeoJSON(items: LandslideItem[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: items.map((l) => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [l.longitude, l.latitude] },
      properties: {
        id: l.id,
        gsi_slide_no: l.gsi_slide_no,
        slide_name: l.slide_name || l.location_description || `GSI #${l.gsi_slide_no}`,
        state: l.state,
        district: l.district,
        movement_type: l.movement_type || 'Mass Movement',
        material: l.material || 'Debris',
        event_date: l.event_date,
      },
    })),
  };
}

function viewportRoadsToGeoJSON(items: RoadEdgeItem[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: items.map((r) => ({
      type: 'Feature' as const,
      id: r.id,
      geometry: {
        type: 'LineString' as const,
        coordinates: r.coordinates,
      },
      properties: {
        id: r.id,
        name: r.name || `Way ${r.osm_way_id}`,
        highwayClass: r.highway_class,
        status: 'open',
        bridge: r.bridge,
        tunnel: r.tunnel,
        length_m: r.length_m,
      },
    })),
  };
}

function sosListToGeoJSON(items: SosListItem[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: items.map((s) => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [s.longitude, s.latitude] },
      properties: {
        id: s.id,
        severity: s.severity,
        status: s.status,
        risk_level: s.risk_level,
        created_at: s.created_at,
      },
    })),
  };
}

function setupMapLayers(map: maplibregl.Map) {
  // 1. Add Road Network Source & Layers — starts empty, filled by viewport loading
  map.addSource(MAP_SOURCE_IDS.roads, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  // Road casing for crisp cartographic separation
  map.addLayer({
    id: MAP_LAYER_IDS.roadsCasing,
    type: 'line',
    source: MAP_SOURCE_IDS.roads,
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
    },
    paint: {
      'line-color': '#ffffff',
      'line-width': [
        'match',
        ['get', 'highwayClass'],
        'trunk',
        5,
        'primary',
        4,
        3,
      ],
      'line-opacity': 0.65,
    },
  });

  // Main Road Line
  map.addLayer({
    id: MAP_LAYER_IDS.roads,
    type: 'line',
    source: MAP_SOURCE_IDS.roads,
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
    },
    paint: {
      'line-color': [
        'match',
        ['get', 'status'],
        'critical',
        '#c24d2c',
        'caution',
        '#b0821e',
        '#5a7894',
      ],
      'line-width': [
        'match',
        ['get', 'highwayClass'],
        'trunk',
        2.8,
        'primary',
        2.2,
        1.6,
      ],
      'line-opacity': 0.85,
    },
  });

  // Simulation: Road Highlight (Active/Selected Corridor)
  map.addLayer({
    id: MAP_LAYER_IDS.roadsHighlight,
    type: 'line',
    source: MAP_SOURCE_IDS.roads,
    filter: ['==', ['get', 'id'], ''],
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
    },
    paint: {
      'line-color': '#0284c7',
      'line-width': 7,
      'line-opacity': 0.8,
      'line-blur': 1,
    },
  });

  // Simulation: Failed Road Line (Severed/Breached corridor)
  map.addLayer({
    id: MAP_LAYER_IDS.roadsFailed,
    type: 'line',
    source: MAP_SOURCE_IDS.roads,
    filter: ['==', ['get', 'id'], ''],
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
    },
    paint: {
      'line-color': '#dc2626',
      'line-width': 4.5,
      'line-dasharray': [2, 1.5],
      'line-opacity': 0.95,
    },
  });

  // Simulation: Isolated Downstream Corridor Segments
  map.addLayer({
    id: MAP_LAYER_IDS.roadsIsolated,
    type: 'line',
    source: MAP_SOURCE_IDS.roads,
    filter: ['==', ['get', 'id'], ''],
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
    },
    paint: {
      'line-color': '#d97706',
      'line-width': 3.5,
      'line-dasharray': [3, 2],
      'line-opacity': 0.9,
    },
  });

  // Road Highway Labels
  map.addLayer({
    id: MAP_LAYER_IDS.roadsLabel,
    type: 'symbol',
    source: MAP_SOURCE_IDS.roads,
    minzoom: 8,
    layout: {
      'symbol-placement': 'line',
      'text-field': ['get', 'name'],
      'text-size': 9.5,
      'text-font': ['Open Sans Regular'],
      'text-letter-spacing': 0.05,
    },
    paint: {
      'text-color': '#475569',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.5,
    },
  });

  // 2. Simulation Impact Nodes Source & Layers
  map.addSource(MAP_SOURCE_IDS.impactNodes, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  // Impact Nodes Pulse Ring
  map.addLayer({
    id: MAP_LAYER_IDS.impactNodesPulse,
    type: 'circle',
    source: MAP_SOURCE_IDS.impactNodes,
    paint: {
      'circle-radius': 16,
      'circle-color': '#dc2626',
      'circle-opacity': 0.25,
      'circle-blur': 0.45,
    },
  });

  // Impact Nodes Marker
  map.addLayer({
    id: MAP_LAYER_IDS.impactNodes,
    type: 'circle',
    source: MAP_SOURCE_IDS.impactNodes,
    paint: {
      'circle-radius': 6,
      'circle-color': '#dc2626',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.95,
    },
  });

  // Impact Nodes Label
  map.addLayer({
    id: MAP_LAYER_IDS.impactNodesLabel,
    type: 'symbol',
    source: MAP_SOURCE_IDS.impactNodes,
    minzoom: 7.5,
    layout: {
      'text-field': ['get', 'label'],
      'text-size': 9,
      'text-font': ['Open Sans Semibold'],
      'text-offset': [0, 1.3],
      'text-anchor': 'top',
    },
    paint: {
      'text-color': '#991b1b',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.5,
    },
  });

  // 3. Add Hazards Source & Layers
  map.addSource(MAP_SOURCE_IDS.hazards, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  // Critical hazard restrained pulse ring
  map.addLayer({
    id: MAP_LAYER_IDS.hazardsPulse,
    type: 'circle',
    source: MAP_SOURCE_IDS.hazards,
    filter: ['==', ['get', 'riskLevel'], 'CRITICAL'],
    paint: {
      'circle-radius': 26,
      'circle-color': '#8e1c2e',
      'circle-opacity': 0.15,
      'circle-blur': 0.5,
    },
  });

  // Hazard ambient glow
  map.addLayer({
    id: MAP_LAYER_IDS.hazardsGlow,
    type: 'circle',
    source: MAP_SOURCE_IDS.hazards,
    filter: ['!=', ['get', 'selected'], true],
    paint: {
      'circle-radius': [
        'match',
        ['get', 'riskLevel'],
        'LOW',
        11,
        'MODERATE',
        15,
        'HIGH',
        20,
        'CRITICAL',
        26,
        14,
      ],
      'circle-color': [
        'match',
        ['get', 'riskLevel'],
        'LOW',
        '#3b7a57',
        'MODERATE',
        '#b0821e',
        'HIGH',
        '#c24d2c',
        'CRITICAL',
        '#8e1c2e',
        '#64748b',
      ],
      'circle-opacity': 0.14,
      'circle-blur': 0.45,
    },
  });

  // Core Hazard Circle with severity-based sizing
  map.addLayer({
    id: MAP_LAYER_IDS.hazards,
    type: 'circle',
    source: MAP_SOURCE_IDS.hazards,
    paint: {
      'circle-radius': [
        'case',
        ['get', 'selected'],
        [
          'match',
          ['get', 'riskLevel'],
          'LOW',
          11,
          'MODERATE',
          15,
          'HIGH',
          21,
          'CRITICAL',
          27,
          13,
        ],
        [
          'match',
          ['get', 'riskLevel'],
          'LOW',
          7.5,
          'MODERATE',
          11,
          'HIGH',
          15,
          'CRITICAL',
          20,
          10,
        ],
      ],
      'circle-color': [
        'match',
        ['get', 'riskLevel'],
        'LOW',
        '#3b7a57',
        'MODERATE',
        '#b0821e',
        'HIGH',
        '#c24d2c',
        'CRITICAL',
        '#8e1c2e',
        '#64748b',
      ],
      'circle-opacity': 0.92,
      'circle-stroke-width': ['case', ['get', 'selected'], 2.5, 1.5],
      'circle-stroke-color': '#ffffff',
    },
  });

  // Selected Hazard Outer Halo Ring
  map.addLayer({
    id: MAP_LAYER_IDS.hazardsSelected,
    type: 'circle',
    source: MAP_SOURCE_IDS.hazards,
    filter: ['==', ['get', 'selected'], true],
    paint: {
      'circle-radius': [
        'match',
        ['get', 'riskLevel'],
        'LOW',
        17,
        'MODERATE',
        22,
        'HIGH',
        28,
        'CRITICAL',
        35,
        20,
      ],
      'circle-color': 'transparent',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#182230',
      'circle-stroke-opacity': 0.85,
    },
  });

  // Location Names Label
  map.addLayer({
    id: MAP_LAYER_IDS.hazardsLabel,
    type: 'symbol',
    source: MAP_SOURCE_IDS.hazards,
    minzoom: 6.5,
    layout: {
      'text-field': ['get', 'location'],
      'text-size': 11,
      'text-font': ['Open Sans Semibold'],
      'text-offset': [0, 1.3],
      'text-anchor': 'top',
      'text-letter-spacing': 0.04,
    },
    paint: {
      'text-color': '#182230',
      'text-halo-color': '#ffffff',
      'text-halo-width': 2,
      'text-halo-blur': 0.5,
    },
  });

  // 4. Ground Intelligence Source & Layers (Field & Citizen Observations)
  map.addSource(MAP_SOURCE_IDS.groundIntel, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.groundIntelGlow,
    type: 'circle',
    source: MAP_SOURCE_IDS.groundIntel,
    paint: {
      'circle-radius': 14,
      'circle-color': '#0d9488',
      'circle-opacity': 0.2,
      'circle-blur': 0.45,
    },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.groundIntel,
    type: 'circle',
    source: MAP_SOURCE_IDS.groundIntel,
    paint: {
      'circle-radius': ['case', ['get', 'selected'], 9, 6.5],
      'circle-color': '#0f766e',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.95,
    },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.groundIntelLabel,
    type: 'symbol',
    source: MAP_SOURCE_IDS.groundIntel,
    minzoom: 7.2,
    layout: {
      'text-field': ['concat', 'OBS · ', ['get', 'category']],
      'text-size': 8.5,
      'text-font': ['Open Sans Semibold'],
      'text-offset': [0, 1.25],
      'text-anchor': 'top',
    },
    paint: {
      'text-color': '#0f766e',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.5,
    },
  });

  // 5. Spatial Alerts Source & Layers
  map.addSource(MAP_SOURCE_IDS.alerts, {    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.alertsPulse,
    type: 'circle',
    source: MAP_SOURCE_IDS.alerts,
    paint: {
      'circle-radius': 22,
      'circle-color': [
        'match',
        ['get', 'severity'],
        'CRITICAL',
        '#dc2626',
        '#ea580c',
      ],
      'circle-opacity': 0.22,
      'circle-blur': 0.5,
    },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.alerts,
    type: 'circle',
    source: MAP_SOURCE_IDS.alerts,
    paint: {
      'circle-radius': ['case', ['get', 'selected'], 11, 8],
      'circle-color': [
        'match',
        ['get', 'severity'],
        'CRITICAL',
        '#b91c1c',
        '#c2410c',
      ],
      'circle-stroke-width': 2.5,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.95,
    },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.alertsLabel,
    type: 'symbol',
    source: MAP_SOURCE_IDS.alerts,
    minzoom: 6.5,
    layout: {
      'text-field': ['concat', '⚠ ', ['get', 'location']],
      'text-size': 9.5,
      'text-font': ['Open Sans Semibold'],
      'text-offset': [0, 1.3],
      'text-anchor': 'top',
    },
    paint: {
      'text-color': '#991b1b',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.8,
    },
  });

  // 6. SOS markers source & layers — populated from real SOS backend records
  map.addSource(MAP_SOURCE_IDS.sos, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.sosPulse,
    type: 'circle',
    source: MAP_SOURCE_IDS.sos,
    paint: {
      'circle-radius': 24,
      'circle-color': '#c24d2c',
      'circle-opacity': 0.18,
      'circle-blur': 0.5,
    },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.sos,
    type: 'circle',
    source: MAP_SOURCE_IDS.sos,
    paint: {
      'circle-radius': 9,
      'circle-color': '#c24d2c',
      'circle-stroke-width': 2.5,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.95,
    },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.sosLabel,
    type: 'symbol',
    source: MAP_SOURCE_IDS.sos,
    minzoom: 6,
    layout: {
      'text-field': ['concat', 'SOS · ', ['get', 'severity']],
      'text-size': 9.5,
      'text-font': ['Open Sans Semibold'],
      'text-offset': [0, 1.4],
      'text-anchor': 'top',
    },
    paint: {
      'text-color': '#a63d22',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.8,
    },
  });

  // 7. GSI Historical Landslide Source — clustered for 31,417+ records
  map.addSource(MAP_SOURCE_IDS.landslides, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
    cluster: true,
    clusterMaxZoom: 12,
    clusterRadius: 50,
  });

  // Cluster circles (aggregated)
  map.addLayer({
    id: MAP_LAYER_IDS.landslidesClusters,
    type: 'circle',
    source: MAP_SOURCE_IDS.landslides,
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': [
        'step',
        ['get', 'point_count'],
        '#6b8e5e',   // <10
        10, '#b0821e', // 10-50
        50, '#c24d2c', // 50+
      ],
      'circle-radius': [
        'step',
        ['get', 'point_count'],
        15,
        10, 20,
        50, 28,
      ],
      'circle-opacity': 0.85,
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
    },
  });

  // Cluster count labels
  map.addLayer({
    id: MAP_LAYER_IDS.landslidesClusterCount,
    type: 'symbol',
    source: MAP_SOURCE_IDS.landslides,
    filter: ['has', 'point_count'],
    layout: {
      'text-field': '{point_count_abbreviated}',
      'text-size': 10,
      'text-font': ['Open Sans Semibold'],
    },
    paint: {
      'text-color': '#ffffff',
    },
  });

  // Individual unclustered landslide points
  map.addLayer({
    id: MAP_LAYER_IDS.landslidesUnclustered,
    type: 'circle',
    source: MAP_SOURCE_IDS.landslides,
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-radius': 6,
      'circle-color': '#6b8e5e',
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.9,
    },
  });

  // Landslide name labels (zoom > 9)
  map.addLayer({
    id: MAP_LAYER_IDS.landslidesLabel,
    type: 'symbol',
    source: MAP_SOURCE_IDS.landslides,
    filter: ['!', ['has', 'point_count']],
    minzoom: 9,
    layout: {
      'text-field': ['get', 'slide_name'],
      'text-size': 8.5,
      'text-font': ['Open Sans Regular'],
      'text-offset': [0, 1.2],
      'text-anchor': 'top',
    },
    paint: {
      'text-color': '#4a6741',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.5,
    },
  });

  // 8. Live Risk Evaluation Marker — shows selected eval coords
  map.addSource(MAP_SOURCE_IDS.liveRiskPoint, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.liveRiskMarkerPulse,
    type: 'circle',
    source: MAP_SOURCE_IDS.liveRiskPoint,
    paint: {
      'circle-radius': 20,
      'circle-color': '#0284c7',
      'circle-opacity': 0.2,
      'circle-blur': 0.5,
    },
  });

  map.addLayer({
    id: MAP_LAYER_IDS.liveRiskMarker,
    type: 'circle',
    source: MAP_SOURCE_IDS.liveRiskPoint,
    paint: {
      'circle-radius': 7,
      'circle-color': '#0284c7',
      'circle-stroke-width': 3,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.95,
    },
  });
}

export function RiskMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const pulseRef = useRef<number | null>(null);
  const coordsRef = useRef<HTMLDivElement>(null);

  const [mapError, setMapError] = useState<string | null>(null);
  const [isMapLoaded, setIsMapLoaded] = useState(false);

  const {
    hazards,
    selectedHazardId,
    selectedHazard,
    selectHazard,
    layers,
    selectedRoadId,
    simulationPhase,
    simulationResult,
    selectRoad,
    observations,
    selectedObservationId,
    selectedObservation,
    selectObservation,
    alerts,
    selectedAlertId,
    selectedAlert,
    selectAlert,
    sosState,
    evalCoords,
    // Phase 2 — Dynamic viewport data
    landslides,
    selectLandslide,
    viewportRoads,
    updateViewport,
    hasDataInViewport,
    sosList,
    selectSos,
    selectLocation,
  } = useMapContext();

  const selectHazardRef = useRef(selectHazard);
  const selectRoadRef = useRef(selectRoad);
  const selectObservationRef = useRef(selectObservation);
  const selectAlertRef = useRef(selectAlert);
  const selectLandslideRef = useRef(selectLandslide);
  const selectSosRef = useRef(selectSos);
  const selectLocationRef = useRef(selectLocation);
  const updateViewportRef = useRef(updateViewport);
  useEffect(() => {
    selectHazardRef.current = selectHazard;
    selectRoadRef.current = selectRoad;
    selectObservationRef.current = selectObservation;
    selectAlertRef.current = selectAlert;
    selectLandslideRef.current = selectLandslide;
    selectSosRef.current = selectSos;
    selectLocationRef.current = selectLocation;
    updateViewportRef.current = updateViewport;
  }, [selectHazard, selectRoad, selectObservation, selectAlert, selectLandslide, selectSos, selectLocation, updateViewport]);

  // Auto-resize observer when container dimensions change
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(() => {
      mapRef.current?.resize();
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_CONFIG.style,
      center: MAP_CONFIG.center,
      zoom: MAP_CONFIG.zoom,
      minZoom: MAP_CONFIG.minZoom,
      maxZoom: MAP_CONFIG.maxZoom,
      attributionControl: false,
    });
    (window as any).__map = map;

    map.on('error', (e) => {
      console.error('[MAPLIBRE ERROR]', e.error?.message || e.error || e);
      const errMsg = e.error?.message || (typeof e.error === 'string' ? e.error : '');
      if (errMsg.includes('WebGL') || errMsg.includes('401') || errMsg.includes('403') || errMsg.includes('Failed to fetch')) {
        setMapError(`Geographic basemap service error: ${errMsg}`);
      }
    });

    // Compass and zoom controls top-right
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left');

    map.on('load', () => {
      setupMapLayers(map);
      setIsMapLoaded(true);
      setMapError(null);
      map.resize();

      // Initial data population
      const source = map.getSource(MAP_SOURCE_IDS.hazards) as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(hazardsToGeoJSON(hazards, selectedHazardId));
      }

      const groundSource = map.getSource(MAP_SOURCE_IDS.groundIntel) as maplibregl.GeoJSONSource | undefined;
      if (groundSource) {
        groundSource.setData(groundObservationsToGeoJSON(observations, selectedObservationId));
      }

      const alertSource = map.getSource(MAP_SOURCE_IDS.alerts) as maplibregl.GeoJSONSource | undefined;
      if (alertSource) {
        alertSource.setData(alertsToGeoJSON(alerts, selectedAlertId));
      }

      // Click hazard to select
      map.on('click', MAP_LAYER_IDS.hazards, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature?.properties?.id) return;
        selectHazardRef.current(feature.properties.id as string);
      });

      // Click road to select for simulation
      map.on('click', MAP_LAYER_IDS.roads, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature?.properties?.id) return;
        selectRoadRef.current(feature.properties.id as string);
      });

      // Click ground observation
      map.on('click', MAP_LAYER_IDS.groundIntel, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature?.properties?.id) return;
        selectObservationRef.current(feature.properties.id as string);
      });

      // Click alert
      map.on('click', MAP_LAYER_IDS.alerts, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature?.properties?.id) return;
        selectAlertRef.current(feature.properties.id as string);
      });

      // Click unclustered landslide
      map.on('click', MAP_LAYER_IDS.landslidesUnclustered, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature?.properties?.id) return;
        selectLandslideRef.current(feature.properties.id as string);
      });

      // Click cluster to zoom in
      map.on('click', MAP_LAYER_IDS.landslidesClusters, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const source = map.getSource(MAP_SOURCE_IDS.landslides) as maplibregl.GeoJSONSource;
        source.getClusterExpansionZoom(feature.properties?.cluster_id as number).then((zoom) => {
          const geom = feature.geometry as Point;
          map.easeTo({
            center: geom.coordinates as [number, number],
            zoom,
          });
        });
      });

      // Click SOS marker
      map.on('click', MAP_LAYER_IDS.sos, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature?.properties?.id) return;
        selectSosRef.current(feature.properties.id as string);
      });

      // Hover cursors
      const hoverLayers = [
        MAP_LAYER_IDS.hazards,
        MAP_LAYER_IDS.roads,
        MAP_LAYER_IDS.groundIntel,
        MAP_LAYER_IDS.alerts,
        MAP_LAYER_IDS.landslidesUnclustered,
        MAP_LAYER_IDS.landslidesClusters,
        MAP_LAYER_IDS.sos,
      ];
      for (const layerId of hoverLayers) {
        map.on('mouseenter', layerId, () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', layerId, () => {
          map.getCanvas().style.cursor = '';
        });
      }

      // Click on background — selects location for live risk evaluation
      map.on('click', (e: MapMouseEvent) => {
        const interactiveLayers = [
          MAP_LAYER_IDS.hazards,
          MAP_LAYER_IDS.roads,
          MAP_LAYER_IDS.groundIntel,
          MAP_LAYER_IDS.alerts,
          MAP_LAYER_IDS.landslidesUnclustered,
          MAP_LAYER_IDS.landslidesClusters,
          MAP_LAYER_IDS.sos,
        ];
        const features = map.queryRenderedFeatures(e.point, {
          layers: interactiveLayers,
        });
        if (features.length === 0) {
          // Click on empty map — evaluate this coordinate
          selectLocationRef.current({
            latitude: e.lngLat.lat,
            longitude: e.lngLat.lng,
            name: `${e.lngLat.lat.toFixed(4)}°N, ${e.lngLat.lng.toFixed(4)}°E`,
            source: 'map-click',
          });
        }
      });

      // Viewport-based data loading — fires on map movement
      map.on('moveend', () => {
        const bounds = map.getBounds();
        updateViewportRef.current([
          bounds.getWest(),
          bounds.getSouth(),
          bounds.getEast(),
          bounds.getNorth(),
        ]);
      });

      // Trigger initial viewport load
      const initBounds = map.getBounds();
      updateViewportRef.current([
        initBounds.getWest(),
        initBounds.getSouth(),
        initBounds.getEast(),
        initBounds.getNorth(),
      ]);

      // Telemetry coordinates tracking
      map.on('mousemove', (e: MapMouseEvent) => {
        if (!coordsRef.current) return;
        const { lat, lng } = formatCoordinate(e.lngLat.lat, e.lngLat.lng);
        coordsRef.current.innerHTML = `<span>${lat}</span><span>${lng}</span>`;
      });
    });

    mapRef.current = map;

    // Pulse loop for critical hazards, impact nodes, and alerts
    const animatePulse = () => {
      if (mapRef.current) {
        const t = Date.now() / 1000;

        // Hazard pulse
        if (mapRef.current.getLayer(MAP_LAYER_IDS.hazardsPulse)) {
          const opacity = 0.12 + Math.sin(t * 2.2) * 0.08;
          const radius = 24 + Math.sin(t * 2.2) * 4;
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.hazardsPulse, 'circle-opacity', opacity);
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.hazardsPulse, 'circle-radius', radius);
        }

        // Impact nodes pulse
        if (mapRef.current.getLayer(MAP_LAYER_IDS.impactNodesPulse)) {
          const nodePulseRadius = 15 + Math.sin(t * 3.5) * 5;
          const nodePulseOpacity = 0.25 + Math.sin(t * 3.5) * 0.15;
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.impactNodesPulse, 'circle-radius', nodePulseRadius);
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.impactNodesPulse, 'circle-opacity', nodePulseOpacity);
        }

        // Alerts pulse
        if (mapRef.current.getLayer(MAP_LAYER_IDS.alertsPulse)) {
          const alertRadius = 20 + Math.sin(t * 3.0) * 5;
          const alertOpacity = 0.22 + Math.sin(t * 3.0) * 0.12;
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.alertsPulse, 'circle-radius', alertRadius);
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.alertsPulse, 'circle-opacity', alertOpacity);
        }

        // SOS pulse
        if (mapRef.current.getLayer(MAP_LAYER_IDS.sosPulse)) {
          const sosRadius = 22 + Math.sin(t * 2.5) * 6;
          const sosOpacity = 0.18 + Math.sin(t * 2.5) * 0.10;
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.sosPulse, 'circle-radius', sosRadius);
          mapRef.current.setPaintProperty(MAP_LAYER_IDS.sosPulse, 'circle-opacity', sosOpacity);
        }
      }
      pulseRef.current = requestAnimationFrame(animatePulse);
    };
    pulseRef.current = requestAnimationFrame(animatePulse);

    return () => {
      if (pulseRef.current) cancelAnimationFrame(pulseRef.current);
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- map init runs once; data synced by dedicated effects below
  }, []);

  // Update Hazard GeoJSON data on hazards or selection change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource(MAP_SOURCE_IDS.hazards) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    source.setData(hazardsToGeoJSON(hazards, selectedHazardId));
  }, [hazards, selectedHazardId]);

  // Synchronize Hazard layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const visible = areHazardsVisible(layers) ? 'visible' : 'none';
    for (const layerId of HAZARD_LAYER_IDS) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible);
      }
    }
  }, [layers]);

  // Synchronize Road network visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const visible = isLayerActive(layers, 'roads') ? 'visible' : 'none';
    for (const layerId of ROAD_LAYER_IDS) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible);
      }
    }
  }, [layers]);

  // Synchronize Road Failure Simulation Layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const highlightLayer = map.getLayer(MAP_LAYER_IDS.roadsHighlight);
    const failedLayer = map.getLayer(MAP_LAYER_IDS.roadsFailed);
    const isolatedLayer = map.getLayer(MAP_LAYER_IDS.roadsIsolated);
    const impactNodesSource = map.getSource(MAP_SOURCE_IDS.impactNodes) as maplibregl.GeoJSONSource | undefined;

    if (!highlightLayer || !failedLayer || !isolatedLayer || !impactNodesSource) return;

    if (simulationPhase === 'selected' || simulationPhase === 'simulating') {
      // Highlight selected corridor
      map.setFilter(MAP_LAYER_IDS.roadsHighlight, ['==', ['get', 'id'], selectedRoadId || '']);
      map.setFilter(MAP_LAYER_IDS.roadsFailed, ['==', ['get', 'id'], '']);
      map.setFilter(MAP_LAYER_IDS.roadsIsolated, ['==', ['get', 'id'], '']);
      impactNodesSource.setData({ type: 'FeatureCollection', features: [] });
    } else if (simulationPhase === 'failed' && simulationResult) {
      // Show severed road & isolated downstream components
      map.setFilter(MAP_LAYER_IDS.roadsHighlight, ['==', ['get', 'id'], '']);
      map.setFilter(MAP_LAYER_IDS.roadsFailed, ['==', ['get', 'id'], selectedRoadId || '']);

      const isolatedIds = simulationResult.isolatedSegmentIds;
      if (isolatedIds.length > 0) {
        map.setFilter(MAP_LAYER_IDS.roadsIsolated, ['in', ['get', 'id'], ['literal', isolatedIds]]);
      } else {
        map.setFilter(MAP_LAYER_IDS.roadsIsolated, ['==', ['get', 'id'], '']);
      }

      // Populate affected impact nodes
      impactNodesSource.setData({
        type: 'FeatureCollection',
        features: simulationResult.affectedCoordinates.map((coord, idx) => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: coord,
          },
          properties: {
            id: idx,
            label: `Node #${idx + 1}`,
          },
        })),
      });
    } else {
      // Idle — clear simulation layers
      map.setFilter(MAP_LAYER_IDS.roadsHighlight, ['==', ['get', 'id'], '']);
      map.setFilter(MAP_LAYER_IDS.roadsFailed, ['==', ['get', 'id'], '']);
      map.setFilter(MAP_LAYER_IDS.roadsIsolated, ['==', ['get', 'id'], '']);
      impactNodesSource.setData({ type: 'FeatureCollection', features: [] });
    }
  }, [simulationPhase, selectedRoadId, simulationResult]);

  // Smooth flyTo on road selection (uses viewport roads from PostGIS)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedRoadId) return;

    const road = viewportRoads.find((r) => r.id === selectedRoadId);
    if (!road || !road.coordinates || road.coordinates.length === 0) return;

    const midIdx = Math.floor(road.coordinates.length / 2);
    const center = road.coordinates[midIdx];

    map.flyTo({
      center,
      zoom: 8.8,
      duration: 1000,
      essential: true,
    });
  }, [selectedRoadId, viewportRoads]);

  // Smooth flyTo on hazard selection
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedHazard) return;

    map.flyTo({
      center: [selectedHazard.longitude, selectedHazard.latitude],
      zoom: MAP_CONFIG.flyToZoom,
      duration: MAP_CONFIG.flyToDuration,
      essential: true,
    });
  }, [selectedHazard]);

  // Synchronize Ground Intelligence layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const visible = isLayerActive(layers, 'ground-intelligence') ? 'visible' : 'none';
    for (const layerId of GROUND_INTEL_LAYER_IDS) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible);
      }
    }
  }, [layers]);

  // Synchronize Alerts layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const visible = isLayerActive(layers, 'alerts') ? 'visible' : 'none';
    for (const layerId of ALERT_LAYER_IDS) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible);
      }
    }
  }, [layers]);

  // Update Ground Intel GeoJSON
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource(MAP_SOURCE_IDS.groundIntel) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    source.setData(groundObservationsToGeoJSON(observations, selectedObservationId));
  }, [observations, selectedObservationId]);

  // Update Alerts GeoJSON
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource(MAP_SOURCE_IDS.alerts) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    source.setData(alertsToGeoJSON(alerts, selectedAlertId));
  }, [alerts, selectedAlertId]);

  // Sync SOS source with real SOS list from backend
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource(MAP_SOURCE_IDS.sos) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    // Real SOS records from backend + locally submitted SOS
    const baseSosGeo = sosListToGeoJSON(sosList);
    if (sosState.step === 'done' && evalCoords) {
      baseSosGeo.features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [evalCoords.lon, evalCoords.lat] },
        properties: {
          id: sosState.sosId ?? 'sos-active',
          severity: 'ACTIVE',
          status: 'ACTIVE',
          risk_level: sosState.riskLevel ?? '',
          created_at: new Date().toISOString(),
        },
      });
    }
    source.setData(baseSosGeo);
  }, [sosList, sosState, evalCoords]);

  // Sync SOS layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const visible = isLayerActive(layers, 'sos') ? 'visible' : 'none';
    for (const layerId of SOS_LAYER_IDS) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible);
      }
    }
  }, [layers]);

  // Sync GSI Historical Landslides data
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource(MAP_SOURCE_IDS.landslides) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    source.setData(landslidesToGeoJSON(landslides));
  }, [landslides]);

  // Sync Landslide layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const visible = isLayerActive(layers, 'landslides') ? 'visible' : 'none';
    for (const layerId of LANDSLIDE_LAYER_IDS) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible);
      }
    }
  }, [layers]);

  // Sync Viewport Roads data from PostGIS
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource(MAP_SOURCE_IDS.roads) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    source.setData(viewportRoadsToGeoJSON(viewportRoads));
  }, [viewportRoads]);

  // Sync Live Risk evaluation marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource(MAP_SOURCE_IDS.liveRiskPoint) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    if (evalCoords) {
      source.setData({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [evalCoords.lon, evalCoords.lat] },
          properties: { id: 'eval-point' },
        }],
      });
    } else {
      source.setData({ type: 'FeatureCollection', features: [] });
    }
  }, [evalCoords]);

  // Sync Live Risk layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const visible = isLayerActive(layers, 'risk') ? 'visible' : 'none';
    for (const layerId of LIVE_RISK_LAYER_IDS) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible);
      }
    }
  }, [layers]);

  // Smooth flyTo on observation selection
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedObservation) return;

    map.flyTo({
      center: [selectedObservation.longitude, selectedObservation.latitude],
      zoom: 10.5,
      duration: 1000,
      essential: true,
    });
  }, [selectedObservation]);

  // Smooth flyTo on alert selection
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedAlert) return;

    map.flyTo({
      center: [selectedAlert.longitude, selectedAlert.latitude],
      zoom: 10.2,
      duration: 1000,
      essential: true,
    });
  }, [selectedAlert]);

  return (
    <div className="risk-map">
      <div ref={containerRef} className="risk-map__canvas" />
      {mapError && (
        <div className="risk-map__error-banner" role="alert">
          <div className="risk-map__error-title">Geographic Basemap Unavailable</div>
          <div className="risk-map__error-desc">{mapError}</div>
        </div>
      )}
      {!isMapLoaded && !mapError && (
        <div className="risk-map__loading-indicator">
          <div className="risk-map__loading-spinner" />
          <span>CONNECTING TO OPENSTREETMAP BASEMAP...</span>
        </div>
      )}
      {isMapLoaded && !hasDataInViewport && (
        <div className="risk-map__no-data-notice" role="status">
          <span className="risk-map__no-data-icon">⊘</span>
          NO VERIFIED DATA IN THIS AREA
        </div>
      )}
      <div ref={coordsRef} className="risk-map__coords font-mono" aria-live="polite">
        <span>30.3800° N</span>
        <span>79.5600° E</span>
      </div>
    </div>
  );
}

