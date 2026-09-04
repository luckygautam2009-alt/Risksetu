import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { DEFAULT_LAYERS } from '../data/layers';
import {
  getDetailedHazardById,
  MOCK_HAZARDS,
  MOCK_ROADS_LIST,
  type DetailedHazard,
  type RoadMeta,
} from '../data/mockRiskData';
import {
  simulateRoadBlockage,
  type SimulationPhase,
  type SimulationResult,
} from '../services/roadImpact';
import {
  MOCK_GROUND_OBSERVATIONS,
  type GroundObservation,
} from '../data/groundIntelligence';
import {
  MOCK_ALERTS,
  type SpatialAlert,
  type UserRole,
} from '../data/alertsData';
import {
  RANKED_PRIORITY_LIST,
  type PriorityItem,
} from '../data/priorityData';
import type { LayerId, LayerItem } from '../types';

export type WorkflowTab = 'risk' | 'impact' | 'priority' | 'alerts';
export type DemoStep = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;

interface MapContextValue {
  hazards: DetailedHazard[];
  selectedHazardId: string | null;
  selectedHazard: DetailedHazard | null;
  selectHazard: (id: string | null) => void;
  layers: LayerItem[];
  toggleLayer: (id: LayerId) => void;

  // Road Simulation
  roadsList: RoadMeta[];
  selectedRoadId: string | null;
  selectedRoad: RoadMeta | null;
  simulationPhase: SimulationPhase;
  simulationResult: SimulationResult | null;
  selectRoad: (id: string | null) => void;
  startSimulation: (roadId?: string) => Promise<void>;
  resetSimulation: () => void;

  // Workflow Mode
  workflowTab: WorkflowTab;
  setWorkflowTab: (tab: WorkflowTab) => void;

  // Ground Intelligence
  observations: GroundObservation[];
  selectedObservationId: string | null;
  selectedObservation: GroundObservation | null;
  selectObservation: (id: string | null) => void;

  // Spatial Alerts & Operations
  alerts: SpatialAlert[];
  selectedAlertId: string | null;
  selectedAlert: SpatialAlert | null;
  selectAlert: (id: string | null) => void;
  acknowledgeAlert: (id: string) => void;
  resolveAlert: (id: string) => void;
  dismissAlert: (id: string) => void;
  userRole: UserRole;
  setUserRole: (role: UserRole) => void;

  // Intervention Priority
  priorityList: PriorityItem[];
  selectedPriorityId: string | null;
  selectedPriority: PriorityItem | null;
  selectPriority: (id: string | null) => void;

  // Demo Mode
  isDemoRunning: boolean;
  demoStep: DemoStep;
  startDemo: () => void;
  stopDemo: () => void;
  setDemoStep: (step: DemoStep) => void;
}

const MapContext = createContext<MapContextValue | null>(null);

export function MapProvider({ children }: { children: ReactNode }) {
  const [selectedHazardId, setSelectedHazardId] = useState<string | null>(null);
  const [layers, setLayers] = useState<LayerItem[]>(DEFAULT_LAYERS);

  // Simulation State
  const [selectedRoadId, setSelectedRoadId] = useState<string | null>(null);
  const [simulationPhase, setSimulationPhase] = useState<SimulationPhase>('idle');
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);

  // Continuous Workflow State
  const [workflowTab, setWorkflowTab] = useState<WorkflowTab>('risk');

  // Ground Intelligence State
  const [observations] = useState<GroundObservation[]>(MOCK_GROUND_OBSERVATIONS);
  const [selectedObservationId, setSelectedObservationId] = useState<string | null>(null);

  // Alerts State
  const [alerts, setAlerts] = useState<SpatialAlert[]>(MOCK_ALERTS);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<UserRole>('Incident Commander');

  // Priority State
  const [priorityList] = useState<PriorityItem[]>(RANKED_PRIORITY_LIST);
  const [selectedPriorityId, setSelectedPriorityId] = useState<string | null>(null);

  // Demo Mode State
  const [isDemoRunning, setIsDemoRunning] = useState(false);
  const [demoStep, setDemoStepState] = useState<DemoStep>(0);

  const startDemo = useCallback(() => {
    // Reset all selections first
    setSelectedHazardId(null);
    setSelectedRoadId(null);
    setSimulationPhase('idle');
    setSimulationResult(null);
    setSelectedObservationId(null);
    setSelectedAlertId(null);
    setSelectedPriorityId(null);
    setWorkflowTab('risk');
    setDemoStepState(0);
    setIsDemoRunning(true);
  }, []);

  const stopDemo = useCallback(() => {
    setIsDemoRunning(false);
    setDemoStepState(0);
  }, []);

  const setDemoStep = useCallback((step: DemoStep) => {
    setDemoStepState(step);
  }, []);

  const selectHazard = useCallback((id: string | null) => {
    setSelectedHazardId(id);
    if (id) {
      setSelectedObservationId(null);
      setSelectedAlertId(null);
    }
  }, []);

  const selectObservation = useCallback((id: string | null) => {
    setSelectedObservationId(id);
    if (id) {
      setSelectedHazardId(null);
      setSelectedAlertId(null);
    }
  }, []);

  const selectAlert = useCallback((id: string | null) => {
    setSelectedAlertId(id);
    if (id) {
      setSelectedHazardId(null);
      setSelectedObservationId(null);
      setWorkflowTab('alerts');
    }
  }, []);

  const acknowledgeAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id
          ? {
              ...a,
              status: 'ACKNOWLEDGED',
              acknowledgedBy: `${userRole} (Station Logged)`,
            }
          : a,
      ),
    );
  }, [userRole]);

  const resolveAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id
          ? {
              ...a,
              status: 'RESOLVED',
              resolvedBy: `${userRole} (Field Cleared)`,
            }
          : a,
      ),
    );
  }, [userRole]);

  const dismissAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id
          ? {
              ...a,
              status: 'DISMISSED',
            }
          : a,
      ),
    );
  }, []);

  const selectPriority = useCallback((id: string | null) => {
    setSelectedPriorityId(id);
    if (id) {
      const item = RANKED_PRIORITY_LIST.find((p) => p.id === id);
      if (item) {
        setSelectedHazardId(item.hazardId);
      }
    }
  }, []);

  const toggleLayer = useCallback((id: LayerId) => {
    setLayers((prev) =>
      prev.map((layer) => (layer.id === id ? { ...layer, active: !layer.active } : layer)),
    );
  }, []);

  const selectRoad = useCallback((id: string | null) => {
    setSelectedRoadId(id);
    if (id) {
      setSimulationPhase('selected');
    } else {
      setSimulationPhase('idle');
      setSimulationResult(null);
    }
  }, []);

  const resetSimulation = useCallback(() => {
    setSimulationPhase(selectedRoadId ? 'selected' : 'idle');
    setSimulationResult(null);
  }, [selectedRoadId]);

  const startSimulation = useCallback(
    async (overrideRoadId?: string) => {
      const roadIdToSimulate = overrideRoadId || selectedRoadId || 'road-nh58';
      const road = MOCK_ROADS_LIST.find((r) => r.id === roadIdToSimulate);
      if (!road) return;

      setSelectedRoadId(road.id);
      setSimulationPhase('simulating');
      setWorkflowTab('impact');

      try {
        const result = await simulateRoadBlockage({
          roadId: road.id,
          wayId: road.wayId,
        });
        setSimulationResult(result);
        setSimulationPhase('failed');
      } catch (err) {
        console.error('Simulation failed:', err);
        setSimulationPhase('selected');
      }
    },
    [selectedRoadId],
  );

  const selectedHazard = useMemo(
    () => (selectedHazardId ? getDetailedHazardById(selectedHazardId) ?? null : null),
    [selectedHazardId],
  );

  const selectedRoad = useMemo(
    () => (selectedRoadId ? MOCK_ROADS_LIST.find((r) => r.id === selectedRoadId) ?? null : null),
    [selectedRoadId],
  );

  const selectedObservation = useMemo(
    () => (selectedObservationId ? observations.find((o) => o.id === selectedObservationId) ?? null : null),
    [selectedObservationId, observations],
  );

  const selectedAlert = useMemo(
    () => (selectedAlertId ? alerts.find((a) => a.id === selectedAlertId) ?? null : null),
    [selectedAlertId, alerts],
  );

  const selectedPriority = useMemo(
    () => (selectedPriorityId ? priorityList.find((p) => p.id === selectedPriorityId) ?? null : null),
    [selectedPriorityId, priorityList],
  );

  const value = useMemo(
    () => ({
      hazards: MOCK_HAZARDS,
      selectedHazardId,
      selectedHazard,
      selectHazard,
      layers,
      toggleLayer,
      roadsList: MOCK_ROADS_LIST,
      selectedRoadId,
      selectedRoad,
      simulationPhase,
      simulationResult,
      selectRoad,
      startSimulation,
      resetSimulation,

      // Phase 5 Workflow & Intelligence
      workflowTab,
      setWorkflowTab,
      observations,
      selectedObservationId,
      selectedObservation,
      selectObservation,
      alerts,
      selectedAlertId,
      selectedAlert,
      selectAlert,
      acknowledgeAlert,
      resolveAlert,
      dismissAlert,
      userRole,
      setUserRole,
      priorityList,
      selectedPriorityId,
      selectedPriority,
      selectPriority,

      // Demo
      isDemoRunning,
      demoStep,
      startDemo,
      stopDemo,
      setDemoStep,
    }),
    [
      selectedHazardId,
      selectedHazard,
      selectHazard,
      layers,
      toggleLayer,
      selectedRoadId,
      selectedRoad,
      simulationPhase,
      simulationResult,
      selectRoad,
      startSimulation,
      resetSimulation,
      workflowTab,
      observations,
      selectedObservationId,
      selectedObservation,
      selectObservation,
      alerts,
      selectedAlertId,
      selectedAlert,
      selectAlert,
      acknowledgeAlert,
      resolveAlert,
      dismissAlert,
      userRole,
      priorityList,
      selectedPriorityId,
      selectedPriority,
      selectPriority,
      isDemoRunning,
      demoStep,
      startDemo,
      stopDemo,
      setDemoStep,
    ],
  );

  return <MapContext.Provider value={value}>{children}</MapContext.Provider>;
}

// eslint-disable-next-line react/only-export-components -- co-locating context hook with provider is standard React practice
export function useMapContext(): MapContextValue {
  const ctx = useContext(MapContext);
  if (!ctx) {
    throw new Error('useMapContext must be used within MapProvider');
  }
  return ctx;
}
