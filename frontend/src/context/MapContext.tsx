import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { DEFAULT_LAYERS } from '../data/layers';
import {
  getDetailedHazardById,
  type DetailedHazard,
  type RoadMeta,
} from '../data/mockRiskData';
import {
  type SimulationPhase,
  type SimulationResult,
} from '../services/roadImpact';
import {
  type GroundObservation,
} from '../data/groundIntelligence';
import {
  type SpatialAlert,
  type AlertSeverity,
  type AlertStatus,
  type UserRole,
} from '../data/alertsData';
import {
  type PriorityItem,
} from '../data/priorityData';
import {
  fetchLiveRisk,
  fetchWeather,
  fetchRoadRisk,
  runImpactSimulation,
  createSos,
  fetchRegionalWatches,
  fetchIdentityMe,
  fetchAlerts,
  fetchGroundReports,
  fetchReadiness,
  fetchLandslidesViewport,
  fetchRoadsViewport,
  fetchSosList,
  getEvidenceFileUrl,
  getAuthToken,
  acknowledgeAlertApi,
  resolveAlertApi,
  dismissAlertApi,
  evaluatePriority,
  type LandslideItem,
  type RoadEdgeItem,
  type SosListItem,
  type IdentityStatusData,
  type RegionalWatchItem,
  type LiveRiskResponse,
  type WeatherResponse,
  type RoadRiskResponse,
  type SimulationApiResponse,
  type ReadinessResponse,
  ApiError,
} from '../services/api';
import { realtimeClient, type WsConnectionStatus, type RealtimeAlertEvent } from '../services/realtime';
import { IdentityVerificationModal } from '../components/identity/IdentityVerificationModal';
import { queueSOS, getQueuedSOS, getQueuedReports, syncOfflineQueue } from '../services/offline';
import type { SupportedLanguage } from '../utils/i18n';
import type { LayerId, LayerItem } from '../types';

export interface SelectedLocation {
  latitude: number;
  longitude: number;
  name?: string;
  source?: string;
}

export type WorkflowTab = 'risk' | 'impact' | 'priority' | 'alerts';
export type FetchState = 'idle' | 'loading' | 'success' | 'error' | 'unavailable';

// ---------------------------------------------------------------------------
// Live API state shapes
// ---------------------------------------------------------------------------

export interface LiveRiskState {
  state: FetchState;
  data: LiveRiskResponse['data'] | null;
  error: string | null;
}

export interface WeatherState {
  state: FetchState;
  data: WeatherResponse['data'] | null;
  error: string | null;
}

export interface RoadRiskState {
  state: FetchState;
  data: RoadRiskResponse['data'] | null;
  error: string | null;
}

export interface SimulationApiState {
  state: FetchState;
  data: SimulationApiResponse['data'] | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// SOS panel state
// ---------------------------------------------------------------------------
export type SosStep = 'idle' | 'confirm' | 'submitting' | 'done' | 'error';

export interface SosState {
  step: SosStep;
  sosId: string | null;
  riskLevel: string | null;
  error: string | null;
  isOfflineQueued?: boolean;
}

interface MapContextValue {
  // Dynamic Location & Spatial State
  selectedLocation: SelectedLocation | null;
  selectLocation: (loc: SelectedLocation | null) => void;

  hazards: DetailedHazard[];
  selectedHazardId: string | null;
  selectedHazard: DetailedHazard | null;
  selectHazard: (id: string | null) => void;
  layers: LayerItem[];
  toggleLayer: (id: LayerId) => void;

  // GSI Historical Landslides & Viewport Loading
  landslides: LandslideItem[];
  selectedLandslideId: string | null;
  selectedLandslide: LandslideItem | null;
  selectLandslide: (id: string | null) => void;
  viewportRoads: RoadEdgeItem[];
  viewportBbox: [number, number, number, number] | null;
  updateViewport: (bbox: [number, number, number, number]) => void;
  hasDataInViewport: boolean;

  // Real SOS Layer
  sosList: SosListItem[];
  loadSosList: () => Promise<void>;
  selectedSosId: string | null;
  selectSos: (id: string | null) => void;

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
  evaluateLocationPriority: (lat: number, lon: number, name?: string) => Promise<void>;
  priorityLoading: boolean;
  priorityError: string | null;

  // Demo Mode (17-Step Guided Tour)
  isDemoRunning: boolean;
  demoStep: number;
  isDemoPaused: boolean;
  startDemo: () => void;
  stopDemo: () => void;
  pauseDemo: () => void;
  resumeDemo: () => void;
  prevDemoStep: () => void;
  nextDemoStep: () => void;
  setDemoStep: (step: number) => void;

  // Language & i18n
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;

  // Modals & UI Actions
  reportModalOpen: boolean;
  openReportModal: () => void;
  closeReportModal: () => void;
  officerModalOpen: boolean;
  openOfficerModal: () => void;
  closeOfficerModal: () => void;

  // Offline Status
  isOffline: boolean;
  pendingSyncCount: number;
  triggerManualSync: () => Promise<void>;

  // Regional Watch
  regionalWatches: RegionalWatchItem[];
  loadRegionalWatches: () => Promise<void>;

  // Identity & Verification
  identityStatus: IdentityStatusData | null;
  identityModalOpen: boolean;
  openIdentityModal: () => void;
  closeIdentityModal: () => void;
  refreshIdentityStatus: () => Promise<void>;

  // ── LIVE API STATE ──────────────────────────────────────────────────────
  /** Coordinates of the currently evaluated location */
  evalCoords: { lat: number; lon: number } | null;

  /** LIVE_RISK_V1 result for selected location */
  liveRisk: LiveRiskState;
  /** Weather from Open-Meteo for selected location */
  weather: WeatherState;
  /** Road-risk assessment for selected road */
  roadRisk: RoadRiskState;
  /** Backend impact simulation (Phase 2B real API) */
  backendSimulation: SimulationApiState;

  // ── SOS ─────────────────────────────────────────────────────────────────
  sosState: SosState;
  openSosPanel: () => void;
  closeSosPanel: () => void;
  submitSos: (description?: string, severity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL') => Promise<void>;

  // ── Real-Time WebSocket & Notifications ─────────────────────────────────
  wsStatus: WsConnectionStatus;
  soundEnabled: boolean;
  setSoundEnabled: (enabled: boolean) => void;
  soundBlocked: boolean;
  enableEmergencySound: () => Promise<boolean>;
  notificationPermission: NotificationPermission | 'unsupported';
  requestNotificationPermission: () => Promise<void>;
  realtimeEvents: RealtimeAlertEvent[];

  // ── Demo-driven panel triggers ───────────────────────────────────────────
  /** Incremented by demo to signal Dashboard to open the weather panel */
  demoOpenWeather: number;
  /** Incremented by demo to signal Dashboard to open the SOS panel */
  demoOpenSos: number;
  triggerDemoWeather: () => void;
  triggerDemoSos: () => void;

  // ── Global System Status & Data Refresh ─────────────────────────────────
  systemStatus: {
    readiness: ReadinessResponse['data'] | null;
    wsStatus: WsConnectionStatus;
    weatherAvailable: boolean;
    identityAvailable: boolean;
    isOffline: boolean;
  };
  probeSystemReadiness: () => Promise<void>;
  refreshOperationalData: () => Promise<void>;
}

const MapContext = createContext<MapContextValue | null>(null);

// ---------------------------------------------------------------------------
// Helpers — map SimulationApiResponse → SimulationResult for existing map layer
// ---------------------------------------------------------------------------
function apiSimToResult(api: SimulationApiResponse['data'], roadName: string): SimulationResult {
  const sevScore = api.isolation_severity;
  return {
    wayId: String(api.blocked_edge.osm_way_id ?? api.blocked_edge.from_node_id),
    roadName: api.blocked_edge.name ?? roadName,
    highwayClass: api.blocked_edge.highway_class ?? 'primary',
    status: api.connectivity_impact.component_increase > 0 ? 'critical' : 'open',
    before: {
      components: api.graph_stats_before.connected_components,
      nodes: api.graph_stats_before.total_nodes,
    },
    after: {
      components: api.graph_stats_after.connected_components,
      nodes: api.graph_stats_after.total_nodes,
    },
    nodesAffected: api.connectivity_impact.nodes_affected,
    deltaComponents: api.connectivity_impact.component_increase,
    isolationSeverity:
      sevScore >= 75 ? 'CRITICAL' :
      sevScore >= 50 ? 'HIGH' :
      sevScore >= 25 ? 'MODERATE' : 'LOW',
    affectedCoordinates: [],
    isolatedSegmentIds: [],
    simulatedAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function MapProvider({ children }: { children: ReactNode }) {
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [selectedHazardId, setSelectedHazardId] = useState<string | null>(null);
  const [layers, setLayers] = useState<LayerItem[]>(DEFAULT_LAYERS);

  // GSI Historical Landslides & Viewport Loading
  const [landslides, setLandslides] = useState<LandslideItem[]>([]);
  const [selectedLandslideId, setSelectedLandslideId] = useState<string | null>(null);
  const [viewportRoads, setViewportRoads] = useState<RoadEdgeItem[]>([]);
  const [viewportBbox, setViewportBbox] = useState<[number, number, number, number] | null>(null);
  const [hasDataInViewport, setHasDataInViewport] = useState<boolean>(true);

  // Real SOS Layer
  const [sosList, setSosList] = useState<SosListItem[]>([]);
  const [selectedSosId, setSelectedSosId] = useState<string | null>(null);

  // Simulation State (local mock kept for map layer compatibility)
  const [selectedRoadId, setSelectedRoadId] = useState<string | null>(null);
  const [simulationPhase, setSimulationPhase] = useState<SimulationPhase>('idle');
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);

  const [workflowTab, setWorkflowTab] = useState<WorkflowTab>('risk');
  const [observations, setObservations] = useState<GroundObservation[]>([]);
  const [selectedObservationId, setSelectedObservationId] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<SpatialAlert[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<UserRole>('Incident Commander');
  const [priorityList, setPriorityList] = useState<PriorityItem[]>([]);
  const [priorityLoading, setPriorityLoading] = useState(false);
  const [priorityError, setPriorityError] = useState<string | null>(null);
  const [selectedPriorityId, setSelectedPriorityId] = useState<string | null>(null);

  // Demo Mode (17-Step Guided Tour)
  const [isDemoRunning, setIsDemoRunning] = useState(false);
  const [demoStep, setDemoStepState] = useState<number>(0);
  const [isDemoPaused, setIsDemoPaused] = useState(false);

  // Language & i18n
  const [language, setLanguage] = useState<SupportedLanguage>('en');

  // Modals & UI Actions
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [officerModalOpen, setOfficerModalOpen] = useState(false);
  const openReportModal = useCallback(() => setReportModalOpen(true), []);
  const closeReportModal = useCallback(() => setReportModalOpen(false), []);
  const openOfficerModal = useCallback(() => setOfficerModalOpen(true), []);
  const closeOfficerModal = useCallback(() => setOfficerModalOpen(false), []);

  // Offline Status & Queued Items
  const [isOffline, setIsOffline] = useState(typeof navigator !== 'undefined' ? !navigator.onLine : false);
  const [pendingSyncCount, setPendingSyncCount] = useState(0);

  const refreshPendingCount = useCallback(async () => {
    try {
      const s = await getQueuedSOS();
      const r = await getQueuedReports();
      setPendingSyncCount(s.length + r.length);
    } catch {
      setPendingSyncCount(0);
    }
  }, []);

  const triggerManualSync = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return;
    await syncOfflineQueue();
    await refreshPendingCount();
  }, [refreshPendingCount]);

  useEffect(() => {
    const handleOnline = () => {
      setIsOffline(false);
      syncOfflineQueue().then(() => refreshPendingCount());
    };
    const handleOffline = () => {
      setIsOffline(true);
      refreshPendingCount();
    };
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    refreshPendingCount();
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [refreshPendingCount]);

  // Regional Watch
  const [regionalWatches, setRegionalWatches] = useState<RegionalWatchItem[]>([]);
  const loadRegionalWatches = useCallback(async () => {
    try {
      const res = await fetchRegionalWatches();
      setRegionalWatches(res.data);
    } catch {
      setRegionalWatches([]);
    }
  }, []);

  // Real Alerts
  const loadAlerts = useCallback(async () => {
    try {
      const res = await fetchAlerts();
      if (res && res.data && Array.isArray(res.data.alerts)) {
        const mapped: SpatialAlert[] = res.data.alerts.map((a) => ({
          id: a.id,
          hazardId: a.id,
          location: a.title || `Alert Area (${a.latitude.toFixed(2)}, ${a.longitude.toFixed(2)})`,
          corridorName: `Corridor ${a.latitude.toFixed(2)}°N, ${a.longitude.toFixed(2)}°E`,
          wayId: a.id,
          severity: (a.severity === 'CRITICAL' || a.severity === 'HIGH' || a.severity === 'MODERATE' ? a.severity : 'HIGH') as AlertSeverity,
          status: (a.status === 'ACTIVE' || a.status === 'ACKNOWLEDGED' || a.status === 'RESOLVED' || a.status === 'DISMISSED' ? a.status : 'ACTIVE') as AlertStatus,
          title: a.title || 'Hazard Alert',
          summary: a.title || 'Spatially localized emergency alert',
          immediateActions: [
            { id: `${a.id}-act1`, label: 'Assess field road status', targetAgency: 'PWD / Border Roads', completed: false },
            { id: `${a.id}-act2`, label: 'Issue localized broadcast', targetAgency: 'DEOC Warning Cell', completed: false },
          ],
          latitude: a.latitude,
          longitude: a.longitude,
          triggeredAt: a.created_at,
          acknowledgedBy: undefined,
          resolvedBy: undefined,
          priorityScore: a.priority_score ?? undefined,
          recommendedAction: a.recommended_action,
          alertType: a.alert_type,
        }));
        setAlerts(mapped);
      }
    } catch {
      // Keep empty if none
    }
  }, []);

  // Real Ground Reports
  const loadObservations = useCallback(async () => {
    try {
      const res = await fetchGroundReports();
      if (res && res.data && Array.isArray(res.data.reports)) {
        const mapped: GroundObservation[] = res.data.reports.map((r: any) => ({
          id: r.report_id || r.id,
          hazardId: r.report_id || r.id,
          location: r.description ? r.description.slice(0, 35) : `Sector (${r.latitude?.toFixed(2) ?? '0'}, ${r.longitude?.toFixed(2) ?? '0'})`,
          title: r.description ? r.description.slice(0, 40) : 'Ground Incident Report',
          description: r.description || 'Ground observation report',
          category: (['ROCKFALL', 'ROAD_CRACK', 'DEBRIS_ACCUMULATION', 'SLOPE_SLUMP', 'RUNOFF_SURGE'].includes(r.report_type) ? r.report_type : 'ROCKFALL') as any,
          trustScore: typeof r.trust?.trust_score === 'number' ? r.trust.trust_score : 75,
          confidence: (r.trust?.trust_score ?? 75) >= 70 ? 'HIGH' : (r.trust?.trust_score ?? 75) >= 40 ? 'MEDIUM' : 'LOW',
          riskInfluence: r.risk_influence_eligible ? 'ELIGIBLE' : 'PROVISIONAL',
          corroboration: (r.trust?.components?.corroboration ?? 0) > 0 ? 'AVAILABLE' : 'PENDING',
          corroborationCount: r.trust?.components?.corroboration ?? 0,
          reporterType: 'Citizen Observer',
          reportedAt: r.observed_at || r.created_at || new Date().toISOString(),
          latitude: r.latitude ?? 0,
          longitude: r.longitude ?? 0,
          status: r.status === 'VERIFIED' ? 'VERIFIED' : 'REVIEW_PENDING',
          evidenceId: r.evidence_id,
          photoUrl: r.evidence_id ? getEvidenceFileUrl(r.evidence_id) : undefined,
        }));
        setObservations(mapped);
      }
    } catch {
      // Keep empty if none
    }
  }, []);

  // Real SOS List
  const loadSosList = useCallback(async () => {
    try {
      const res = await fetchSosList();
      if (res && res.data && Array.isArray(res.data.items)) {
        setSosList(res.data.items);
      }
    } catch {
      setSosList([]);
    }
  }, []);

  // System Readiness Probe
  const [readinessData, setReadinessData] = useState<ReadinessResponse['data'] | null>(null);
  const probeSystemReadiness = useCallback(async () => {
    try {
      const res = await fetchReadiness();
      setReadinessData(res.data);
    } catch {
      setReadinessData(null);
    }
  }, []);

  // Identity & Verification State
  const [identityStatus, setIdentityStatus] = useState<IdentityStatusData | null>(null);
  const [identityModalOpen, setIdentityModalOpen] = useState(false);

  const openIdentityModal = useCallback(() => setIdentityModalOpen(true), []);
  const closeIdentityModal = useCallback(() => setIdentityModalOpen(false), []);

  const refreshIdentityStatus = useCallback(async () => {
    try {
      const res = await fetchIdentityMe();
      setIdentityStatus(res.data);
    } catch {
      setIdentityStatus(null);
    }
  }, []);

  const refreshOperationalData = useCallback(async () => {
    await Promise.allSettled([
      loadAlerts(),
      loadObservations(),
      loadSosList(),
      loadRegionalWatches(),
      refreshIdentityStatus(),
      probeSystemReadiness(),
    ]);
  }, [loadAlerts, loadObservations, loadSosList, loadRegionalWatches, refreshIdentityStatus, probeSystemReadiness]);

  useEffect(() => {
    refreshOperationalData();
    const probeTimer = setInterval(probeSystemReadiness, 30000);
    return () => clearInterval(probeTimer);
  }, [refreshOperationalData, probeSystemReadiness]);

  // ── Live API state ──────────────────────────────────────────────────────
  const [evalCoords, setEvalCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [liveRisk, setLiveRisk] = useState<LiveRiskState>({ state: 'idle', data: null, error: null });
  const [weather, setWeather] = useState<WeatherState>({ state: 'idle', data: null, error: null });
  const [roadRisk, setRoadRisk] = useState<RoadRiskState>({ state: 'idle', data: null, error: null });
  const [backendSimulation, setBackendSimulation] = useState<SimulationApiState>({
    state: 'idle', data: null, error: null,
  });

  // ── SOS ─────────────────────────────────────────────────────────────────
  const [sosState, setSosState] = useState<SosState>({
    step: 'idle', sosId: null, riskLevel: null, error: null,
  });

  // ── Real-Time WebSocket & Notifications ─────────────────────────────────
  const [wsStatus, setWsStatus] = useState<WsConnectionStatus>('DISCONNECTED');
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [soundBlocked, setSoundBlocked] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification !== 'undefined' ? Notification.permission : 'unsupported',
  );
  const [realtimeEvents, setRealtimeEvents] = useState<RealtimeAlertEvent[]>([]);
  const emergencyAudioRef = useRef<AudioContext | null>(null);

  const enableEmergencySound = useCallback(async (): Promise<boolean> => {
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) {
        setSoundBlocked(true);
        return false;
      }

      let ctx = emergencyAudioRef.current;
      if (!ctx || ctx.state === 'closed') {
        ctx = new AudioCtx();
        emergencyAudioRef.current = ctx;
      }

      if (ctx.state === 'suspended') {
        await ctx.resume();
      }

      // Play an imperceptible short pulse to prime audio playback under browser policy
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.001, ctx.currentTime);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.05);

      setSoundBlocked(false);
      setSoundEnabled(true);
      return true;
    } catch {
      setSoundBlocked(true);
      return false;
    }
  }, []);

  const requestNotificationPermission = useCallback(async () => {
    if (typeof Notification === 'undefined') {
      setNotificationPermission('unsupported');
      return;
    }
    try {
      const perm = await Notification.requestPermission();
      setNotificationPermission(perm);
    } catch {
      setNotificationPermission('denied');
    }
  }, []);

  // Connect WebSocket on mount when auth token is available
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      realtimeClient.connect(token);
    }

    const unsubStatus = realtimeClient.onStatusChange((status) => {
      setWsStatus(status);
    });

    const unsubEvents = realtimeClient.onEvent((event) => {
      setRealtimeEvents((prev) => [event, ...prev].slice(0, 100));

      // Play emergency sound if enabled
      if (soundEnabled && event.data?.severity === 'CRITICAL') {
        try {
          const AudioCtx =
            window.AudioContext ||
            (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          if (!AudioCtx) {
            setSoundBlocked(true);
          } else {
            let ctx = emergencyAudioRef.current;
            if (!ctx || ctx.state === 'closed') {
              ctx = new AudioCtx();
              emergencyAudioRef.current = ctx;
            }

            if (ctx.state === 'suspended') {
              ctx.resume().catch(() => setSoundBlocked(true));
              if (ctx.state === 'suspended') {
                setSoundBlocked(true);
              }
            }

            if (ctx.state === 'running') {
              const osc = ctx.createOscillator();
              const gain = ctx.createGain();
              osc.type = 'square';
              osc.frequency.setValueAtTime(800, ctx.currentTime);
              osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.15);
              osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.3);
              gain.gain.setValueAtTime(0.12, ctx.currentTime);
              gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
              osc.connect(gain);
              gain.connect(ctx.destination);
              osc.start();
              osc.stop(ctx.currentTime + 0.5);
              setSoundBlocked(false);
            }
          }
        } catch {
          setSoundBlocked(true);
        }
      }

      // Map focus on real critical alert or SOS
      if (
        event.data?.location &&
        (event.data?.severity === 'CRITICAL' || event.event === 'SOS_ALERT_CREATED')
      ) {
        setSelectedLocation({
          latitude: event.data.location.latitude,
          longitude: event.data.location.longitude,
          name: `Critical Alert Area (${event.data.location.latitude.toFixed(2)}, ${event.data.location.longitude.toFixed(2)})`,
        });
        setEvalCoords({
          lat: event.data.location.latitude,
          lon: event.data.location.longitude,
        });
        if (event.data?.alert_id) {
          setSelectedAlertId(event.data.alert_id);
        }
      }

      // Browser notification if permitted
      if (
        typeof Notification !== 'undefined' &&
        Notification.permission === 'granted' &&
        event.event === 'SOS_ALERT_CREATED'
      ) {
        try {
          new Notification('⚠️ RISKSETU EMERGENCY', {
            body: `${event.data.severity} SOS alert at ${event.data.location.latitude.toFixed(4)}°N, ${event.data.location.longitude.toFixed(4)}°E`,
            tag: event.data.alert_id,
            requireInteraction: true,
          });
        } catch {
          // notification creation failed
        }
      }
    });

    return () => {
      unsubStatus();
      unsubEvents();
      realtimeClient.disconnect();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [soundEnabled]);

  // ── Demo panel triggers ──────────────────────────────────────────────────
  const [demoOpenWeather, setDemoOpenWeather] = useState(0);
  const [demoOpenSos, setDemoOpenSos] = useState(0);

  const triggerDemoWeather = useCallback(() => setDemoOpenWeather((n) => n + 1), []);
  const triggerDemoSos = useCallback(() => setDemoOpenSos((n) => n + 1), []);

  // Abort controller for live risk fetches
  const liveRiskAbortRef = useRef<AbortController | null>(null);

  // ── Dynamic Location Selection ──────────────────────────────────────────
  const selectLocation = useCallback((loc: SelectedLocation | null) => {
    setSelectedLocation(loc);
    if (loc) {
      setEvalCoords({ lat: loc.latitude, lon: loc.longitude });
      setSelectedObservationId(null);
      setSelectedAlertId(null);
      setSelectedHazardId(null);
      // Clear live state so panel shows loading immediately
      setLiveRisk({ state: 'loading', data: null, error: null });
      setWeather({ state: 'loading', data: null, error: null });
      setRoadRisk({ state: 'loading', data: null, error: null });
    } else {
      setEvalCoords(null);
      setLiveRisk({ state: 'idle', data: null, error: null });
      setWeather({ state: 'idle', data: null, error: null });
      setRoadRisk({ state: 'idle', data: null, error: null });
    }
  }, []);

  // ── Fetch live risk + weather + road risk whenever evalCoords change ────
  useEffect(() => {
    if (!evalCoords) return;
    const { lat, lon } = evalCoords;

    // Abort any in-flight request
    liveRiskAbortRef.current?.abort();
    const ctrl = new AbortController();
    liveRiskAbortRef.current = ctrl;

    // 1. Fetch live risk
    setLiveRisk({ state: 'loading', data: null, error: null });
    fetchLiveRisk(lat, lon)
      .then((res) => {
        if (ctrl.signal.aborted) return;
        setLiveRisk({ state: 'success', data: res.data, error: null });
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        const msg = err instanceof Error ? err.message : 'Live risk unavailable.';
        setLiveRisk({ state: 'error', data: null, error: msg });
      });

    // 2. Fetch weather
    setWeather({ state: 'loading', data: null, error: null });
    fetchWeather(lat, lon)
      .then((res) => {
        if (ctrl.signal.aborted) return;
        setWeather({ state: 'success', data: res.data, error: null });
      })
      .catch((_weatherErr: unknown) => {
        if (ctrl.signal.aborted) return;
        setWeather({ state: 'error', data: null, error: 'Weather unavailable.' });
      });

    // 3. Fetch road risk
    setRoadRisk({ state: 'loading', data: null, error: null });
    fetchRoadRisk(lat, lon)
      .then((res) => {
        if (ctrl.signal.aborted) return;
        setRoadRisk({ state: 'success', data: res.data, error: null });
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        setRoadRisk({
          state: 'error',
          data: null,
          error: err instanceof Error ? err.message : 'Road risk unavailable.',
        });
      });

    return () => ctrl.abort();
  }, [evalCoords]);

  // ── Fetch road risk when a road is selected ──────────────────────────────
  useEffect(() => {
    const hazard = selectedHazardId ? getDetailedHazardById(selectedHazardId) : null;
    if (!selectedRoadId || !hazard) return;

    const lat = hazard.latitude;
    const lon = hazard.longitude;

    setRoadRisk({ state: 'loading', data: null, error: null });
    fetchRoadRisk(lat, lon)
      .then((res) => setRoadRisk({ state: 'success', data: res.data, error: null }))
      .catch((err: unknown) => {
        setRoadRisk({
          state: 'error',
          data: null,
          error: err instanceof Error ? err.message : 'Road risk unavailable.',
        });
      });
  }, [selectedRoadId, selectedHazardId]);

  // ── Demo ─────────────────────────────────────────────────────────────────
  const startDemo = useCallback(() => {
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
    setIsDemoPaused(false);
    // Reset live state
    setLiveRisk({ state: 'idle', data: null, error: null });
    setWeather({ state: 'idle', data: null, error: null });
    setRoadRisk({ state: 'idle', data: null, error: null });
    setBackendSimulation({ state: 'idle', data: null, error: null });
  }, []);

  const stopDemo = useCallback(() => {
    setIsDemoRunning(false);
    setIsDemoPaused(false);
    setDemoStepState(0);
  }, []);

  const pauseDemo = useCallback(() => {
    setIsDemoPaused(true);
  }, []);

  const resumeDemo = useCallback(() => {
    setIsDemoPaused(false);
  }, []);

  const prevDemoStep = useCallback(() => {
    setDemoStepState((s) => Math.max(0, s - 1));
  }, []);

  const nextDemoStep = useCallback(() => {
    setDemoStepState((s) => Math.min(16, s + 1));
  }, []);

  const setDemoStep = useCallback((step: number) => {
    setDemoStepState(step);
  }, []);

  // ── Selection callbacks ──────────────────────────────────────────────────
  const selectHazard = useCallback((id: string | null) => {
    setSelectedHazardId(id);
    if (id) {
      const hazard = getDetailedHazardById(id);
      if (hazard) {
        setSelectedLocation({
          latitude: hazard.latitude,
          longitude: hazard.longitude,
          name: hazard.location,
        });
        setEvalCoords({ lat: hazard.latitude, lon: hazard.longitude });
      }
      setSelectedObservationId(null);
      setSelectedAlertId(null);
      // Clear stale live state so panel shows loading immediately
      setLiveRisk({ state: 'loading', data: null, error: null });
      setWeather({ state: 'loading', data: null, error: null });
      setRoadRisk({ state: 'loading', data: null, error: null });
    } else {
      setSelectedLocation(null);
      setEvalCoords(null);
    }
  }, []);

  const selectObservation = useCallback((id: string | null) => {
    setSelectedObservationId(id);
    if (id) {
      setSelectedHazardId(null);
      setSelectedAlertId(null);
      setSelectedLandslideId(null);
      setSelectedSosId(null);
    }
  }, []);

  const viewportDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateViewport = useCallback((bbox: [number, number, number, number]) => {
    setViewportBbox(bbox);
    if (viewportDebounceRef.current) {
      clearTimeout(viewportDebounceRef.current);
    }
    viewportDebounceRef.current = setTimeout(async () => {
      const [minLon, minLat, maxLon, maxLat] = bbox;
      try {
        const [lsRes, roadsRes] = await Promise.allSettled([
          fetchLandslidesViewport(minLat, maxLat, minLon, maxLon, 250),
          fetchRoadsViewport(minLat, maxLat, minLon, maxLon, 150),
        ]);

        const newLandslides = lsRes.status === 'fulfilled' ? lsRes.value.data.items : [];
        const newRoads = roadsRes.status === 'fulfilled' ? roadsRes.value.data.items : [];

        setLandslides(newLandslides);
        setViewportRoads(newRoads);

        const hasData = newLandslides.length > 0 || newRoads.length > 0 || alerts.length > 0 || observations.length > 0 || sosList.length > 0;
        setHasDataInViewport(hasData);
      } catch {
        // preserve state
      }
    }, 350);
  }, [alerts.length, observations.length, sosList.length]);

  const selectLandslide = useCallback((id: string | null) => {
    setSelectedLandslideId(id);
    if (id) {
      const found = landslides.find((l) => l.id === id);
      if (found) {
        setSelectedLocation({
          latitude: found.latitude,
          longitude: found.longitude,
          name: found.slide_name || found.location_description || `GSI #${found.gsi_slide_no}`,
        });
        setEvalCoords({ lat: found.latitude, lon: found.longitude });
      }
      setSelectedHazardId(null);
      setSelectedObservationId(null);
      setSelectedAlertId(null);
      setSelectedSosId(null);
      setLiveRisk({ state: 'loading', data: null, error: null });
      setWeather({ state: 'loading', data: null, error: null });
      setRoadRisk({ state: 'loading', data: null, error: null });
    }
  }, [landslides]);

  const selectSos = useCallback((id: string | null) => {
    setSelectedSosId(id);
    if (id) {
      const found = sosList.find((s) => s.id === id);
      if (found) {
        setSelectedLocation({
          latitude: found.latitude,
          longitude: found.longitude,
          name: `SOS Event (${found.severity})`,
        });
        setEvalCoords({ lat: found.latitude, lon: found.longitude });
      }
      setSelectedHazardId(null);
      setSelectedLandslideId(null);
      setSelectedObservationId(null);
      setSelectedAlertId(null);
    }
  }, [sosList]);

  const selectAlert = useCallback((id: string | null) => {
    setSelectedAlertId(id);
    if (id) {
      setSelectedHazardId(null);
      setSelectedObservationId(null);
      setSelectedLandslideId(null);
      setSelectedSosId(null);
      setWorkflowTab('alerts');
    }
  }, []);

  const acknowledgeAlert = useCallback(
    async (id: string) => {
      // Suspend ongoing emergency audio if playing
      if (emergencyAudioRef.current && emergencyAudioRef.current.state === 'running') {
        try {
          await emergencyAudioRef.current.suspend();
        } catch {
          // ignore
        }
      }

      setAlerts((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, status: 'ACKNOWLEDGED', acknowledgedBy: `${userRole} (Logged)` } : a,
        ),
      );
      try {
        await acknowledgeAlertApi(id);
      } catch (err) {
        console.warn('Backend acknowledgeAlertApi call failed (optimistic update preserved):', err);
      }
    },
    [userRole],
  );

  const resolveAlert = useCallback(
    async (id: string) => {
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, status: 'RESOLVED', resolvedBy: `${userRole} (Field Cleared)` } : a,
        ),
      );
      try {
        await resolveAlertApi(id);
      } catch (err) {
        console.warn('Backend resolveAlertApi call failed (optimistic update preserved):', err);
      }
    },
    [userRole],
  );

  const dismissAlert = useCallback(async (id: string) => {
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, status: 'DISMISSED' } : a)));
    try {
      await dismissAlertApi(id);
    } catch (err) {
      console.warn('Backend dismissAlertApi call failed (optimistic update preserved):', err);
    }
  }, []);

  const selectPriority = useCallback(
    (id: string | null) => {
      setSelectedPriorityId(id);
      if (id) {
        const item = priorityList.find((p) => p.id === id);
        if (item) {
          if (item.latitude && item.longitude) {
            setSelectedLocation({
              latitude: item.latitude,
              longitude: item.longitude,
              name: item.location,
            });
            setEvalCoords({ lat: item.latitude, lon: item.longitude });
          }
          setSelectedHazardId(item.hazardId);
        }
      }
    },
    [priorityList],
  );

  const evaluateLocationPriority = useCallback(
    async (lat: number, lon: number, name?: string) => {
      setPriorityLoading(true);
      setPriorityError(null);
      try {
        const res = await evaluatePriority({
          latitude: lat,
          longitude: lon,
          search_radius_m: 5000,
        });
        const d = res.data;
        const newItem: PriorityItem = {
          rank: 1,
          id: d.candidate_id || `prio-${lat.toFixed(4)}-${lon.toFixed(4)}`,
          hazardId: d.candidate_id || `eval-${lat.toFixed(4)}-${lon.toFixed(4)}`,
          location: name || `Sector (${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E)`,
          subdivision: 'Himalayan Assessment Zone',
          priorityLevel: (['CRITICAL', 'HIGH', 'MODERATE', 'LOW'].includes(d.priority_level)
            ? d.priority_level
            : 'HIGH') as any,
          priorityScore: d.priority_score,
          riskScore: d.risk_score,
          isolationSeverity: (['CRITICAL', 'HIGH', 'MODERATE', 'LOW'].includes(d.risk_level)
            ? d.risk_level
            : 'HIGH') as any,
          isolationNodes: d.nodes_affected ?? 0,
          urgency: d.urgency_score > 70 ? 'IMMEDIATE' : d.urgency_score > 40 ? 'ELEVATED' : 'STANDARD',
          contrastReason:
            d.explanation ||
            `Priority score ${d.priority_score.toFixed(1)} evaluated via multi-criteria model (Risk 40% + Impact 45% + Urgency 15%).`,
          latitude: d.latitude,
          longitude: d.longitude,
          riskContribution: d.breakdown?.risk_contribution,
          isolationContribution: d.breakdown?.impact_contribution,
          urgencyContribution: d.breakdown?.urgency_contribution,
          rationale: d.explanation,
          limitations: d.limitations,
        };

        setPriorityList((prev) => {
          const filtered = prev.filter((p) => p.id !== newItem.id);
          return [newItem, ...filtered].map((p, idx) => ({ ...p, rank: idx + 1 }));
        });
        setSelectedPriorityId(newItem.id);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Priority evaluation failed';
        setPriorityError(msg);
      } finally {
        setPriorityLoading(false);
      }
    },
    [],
  );

  // Dynamic roads converted from real PostGIS viewport roads
  const dynamicRoadsList: RoadMeta[] = useMemo(() => {
    return viewportRoads.map((r) => ({
      id: r.id,
      wayId: String(r.osm_way_id),
      name: r.name || `OSM Way ${r.osm_way_id} (${r.highway_class})`,
      highwayClass: r.highway_class,
      status: r.bridge ? 'caution' : 'open',
    }));
  }, [viewportRoads]);

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
      setRoadRisk({ state: 'idle', data: null, error: null });
    }
  }, []);

  const resetSimulation = useCallback(() => {
    setSimulationPhase(selectedRoadId ? 'selected' : 'idle');
    setSimulationResult(null);
    setBackendSimulation({ state: 'idle', data: null, error: null });
  }, [selectedRoadId]);

  // ── Start simulation — real backend simulation via POST /api/v1/impact/simulate-road-blockage ──
  const startSimulation = useCallback(
    async (overrideRoadId?: string) => {
      const roadIdToSimulate = overrideRoadId ?? selectedRoadId;
      const road = dynamicRoadsList.find((r) => r.id === roadIdToSimulate) ?? dynamicRoadsList[0];

      const roadId = road ? road.id : (roadIdToSimulate || 'simulated-segment');
      const roadName = road ? road.name : 'Target Road Segment';

      setSelectedRoadId(roadId);
      setSimulationPhase('simulating');
      setWorkflowTab('impact');
      setBackendSimulation({ state: 'loading', data: null, error: null });

      let lat = selectedLocation?.latitude ?? evalCoords?.lat;
      let lon = selectedLocation?.longitude ?? evalCoords?.lon;

      if ((!lat || !lon) && road) {
        const foundEdge = viewportRoads.find((vr) => vr.id === road.id);
        if (foundEdge && foundEdge.coordinates && foundEdge.coordinates.length > 0) {
          lon = foundEdge.coordinates[0][0];
          lat = foundEdge.coordinates[0][1];
        }
      }

      const targetLat = lat ?? 30.2936;
      const targetLon = lon ?? 79.5603;

      try {
        const result = await runImpactSimulation(targetLat, targetLon, 5000, 1000);
        setBackendSimulation({ state: 'success', data: result.data, error: null });
        setSimulationResult(apiSimToResult(result.data, roadName));
        setSimulationPhase('failed');
      } catch (err: unknown) {
        setSimulationPhase('selected');
        const msg = err instanceof Error ? err.message : 'Road impact simulation service unavailable.';
        setBackendSimulation({
          state: 'unavailable',
          data: null,
          error: `DATA UNAVAILABLE: ${msg}. No synthetic road closure data generated.`,
        });
        setSimulationResult(null);
      }
    },
    [selectedRoadId, selectedLocation, evalCoords, dynamicRoadsList, viewportRoads],
  );

  // ── SOS ─────────────────────────────────────────────────────────────────
  const openSosPanel = useCallback(() => {
    setSosState({ step: 'confirm', sosId: null, riskLevel: liveRisk.data?.risk.level ?? null, error: null });
  }, [liveRisk.data]);

  const closeSosPanel = useCallback(() => {
    setSosState({ step: 'idle', sosId: null, riskLevel: null, error: null });
  }, []);

  const submitSos = useCallback(
    async (description?: string, severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' = 'HIGH') => {
      const coords = evalCoords;
      if (!coords) return;

      setSosState((prev) => ({ ...prev, step: 'submitting', error: null }));

      // If browser is offline, queue locally via IndexedDB
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        try {
          const localId = `local_sos_${Date.now()}`;
          await queueSOS({
            id: localId,
            latitude: coords.lat,
            longitude: coords.lon,
            severity,
            description,
            createdAt: new Date().toISOString(),
            status: 'QUEUED_OFFLINE',
          });
          await refreshPendingCount();
          setSosState({
            step: 'done',
            sosId: localId,
            riskLevel: liveRisk.data?.risk.level ?? 'HIGH',
            error: null,
            isOfflineQueued: true,
          });
          return;
        } catch {
          setSosState((prev) => ({ ...prev, step: 'error', error: 'Failed to queue SOS offline.' }));
          return;
        }
      }

      try {
        const res = await createSos({ latitude: coords.lat, longitude: coords.lon, severity, description });
        setSosState({
          step: 'done',
          sosId: res.data.id,
          riskLevel: res.data.risk_context.risk_level,
          error: null,
          isOfflineQueued: false,
        });
      } catch (err: unknown) {
        // If network error, attempt to queue offline as fallback
        if (
          err instanceof TypeError ||
          (err instanceof Error && err.message.toLowerCase().includes('failed to fetch'))
        ) {
          try {
            const localId = `local_sos_${Date.now()}`;
            await queueSOS({
              id: localId,
              latitude: coords.lat,
              longitude: coords.lon,
              severity,
              description,
              createdAt: new Date().toISOString(),
              status: 'QUEUED_OFFLINE',
            });
            await refreshPendingCount();
            setSosState({
              step: 'done',
              sosId: localId,
              riskLevel: liveRisk.data?.risk.level ?? 'HIGH',
              error: null,
              isOfflineQueued: true,
            });
            return;
          } catch {
            // fall through to error
          }
        }
        const msg =
          err instanceof ApiError && err.status === 401
            ? 'Authentication required. Sign in to submit SOS.'
            : err instanceof Error
            ? err.message
            : 'SOS submission failed. Please try again.';
        setSosState((prev) => ({ ...prev, step: 'error', error: msg }));
      }
    },
    [evalCoords, liveRisk.data, refreshPendingCount],
  );

  // ── Computed selectors ───────────────────────────────────────────────────
  const selectedLandslide = useMemo<LandslideItem | null>(
    () => (selectedLandslideId ? landslides.find((l) => l.id === selectedLandslideId) ?? null : null),
    [selectedLandslideId, landslides],
  );

  const dynamicHazards = useMemo<DetailedHazard[]>(() => {
    return landslides.map((l) => ({
      id: l.id,
      latitude: l.latitude,
      longitude: l.longitude,
      location: l.slide_name || l.location_description || `GSI #${l.gsi_slide_no}`,
      elevationM: 1500,
      basin: l.state,
      subdivision: l.district,
      riskScore: 65,
      riskLevel: 'MODERATE' as const,
      confidence: 85,
      confidenceLevel: 'HIGH' as const,
      historicalEvidence: `GSI ${l.gsi_slide_no} · ${l.movement_type || 'Mass Movement'} · Material: ${l.material || 'Debris'}`,
      rainfall: 'IMD Climatology Corridor',
      terrain: l.location_description || 'Himalayan Mountain Slope',
      coordinatesFormatted: {
        lat: `${l.latitude.toFixed(4)}° N`,
        lng: `${l.longitude.toFixed(4)}° E`,
      },
      factors: [
        {
          name: 'gsi_historical_proximity',
          displayName: 'GSI Historical Incident',
          score: 85,
          weight: 0.5,
          summary: `Recorded event on ${l.event_date || 'GSI Catalog'}. Movement: ${l.movement_type || 'Debris Slide'}`,
        },
      ],
    }));
  }, [landslides]);

  const selectedHazard = useMemo<DetailedHazard | null>(() => {
    if (selectedHazardId) {
      const found = getDetailedHazardById(selectedHazardId) || dynamicHazards.find((h) => h.id === selectedHazardId);
      if (found) return found;
    }
    if (selectedLandslide) {
      const riskScore = liveRisk.data?.risk?.score ?? 65;
      const riskLevel = (liveRisk.data?.risk?.level ?? 'MODERATE') as any;
      const conf = liveRisk.data?.risk?.confidence ?? 85;
      return {
        id: selectedLandslide.id,
        latitude: selectedLandslide.latitude,
        longitude: selectedLandslide.longitude,
        location: selectedLandslide.slide_name || selectedLandslide.location_description || `GSI #${selectedLandslide.gsi_slide_no}`,
        elevationM: liveRisk.data?.terrain?.elevation_m ?? 1500,
        basin: selectedLandslide.state,
        subdivision: selectedLandslide.district,
        riskScore,
        riskLevel,
        confidence: conf,
        confidenceLevel: conf > 75 ? 'HIGH' : 'MEDIUM',
        historicalEvidence: `GSI Catalog Slide #${selectedLandslide.gsi_slide_no} · Movement: ${selectedLandslide.movement_type || 'Rockfall / Debris'} · Material: ${selectedLandslide.material || 'Residual Soil'}`,
        rainfall: liveRisk.data?.weather?.precipitation_mm !== undefined && liveRisk.data?.weather?.precipitation_mm !== null
          ? `${liveRisk.data.weather.precipitation_mm}mm precipitation`
          : 'Live Satellite Weather Feed',
        terrain: liveRisk.data?.terrain?.slope_degrees !== undefined && liveRisk.data?.terrain?.slope_degrees !== null
          ? `Slope ${liveRisk.data.terrain.slope_degrees}°`
          : selectedLandslide.location_description || 'Himalayan Slope',
        coordinatesFormatted: {
          lat: `${selectedLandslide.latitude.toFixed(4)}° N`,
          lng: `${selectedLandslide.longitude.toFixed(4)}° E`,
        },
        factors: (liveRisk.data?.contributing_factors || []).map((f) => ({
          name: f.factor,
          displayName: f.factor.replace(/_/g, ' ').toUpperCase(),
          score: typeof f.value === 'number' ? f.value : 65,
          weight: 0.25,
          summary: f.description,
        })),
      };
    }
    if (selectedLocation) {
      const riskScore = liveRisk.data?.risk?.score ?? 50;
      const riskLevel = (liveRisk.data?.risk?.level ?? 'MODERATE') as any;
      const conf = liveRisk.data?.risk?.confidence ?? 70;
      return {
        id: `loc-${selectedLocation.latitude.toFixed(4)}-${selectedLocation.longitude.toFixed(4)}`,
        latitude: selectedLocation.latitude,
        longitude: selectedLocation.longitude,
        location: selectedLocation.name || `Sector ${selectedLocation.latitude.toFixed(3)}°N, ${selectedLocation.longitude.toFixed(3)}°E`,
        elevationM: liveRisk.data?.terrain?.elevation_m ?? 1800,
        basin: 'Operational Watershed',
        subdivision: 'Operational Spatial Sector',
        riskScore,
        riskLevel,
        confidence: conf,
        confidenceLevel: conf > 75 ? 'HIGH' : 'MEDIUM',
        historicalEvidence: liveRisk.data?.historical?.summary || 'Standard Geological Context',
        rainfall: liveRisk.data?.weather?.precipitation_mm !== undefined && liveRisk.data?.weather?.precipitation_mm !== null
          ? `${liveRisk.data.weather.precipitation_mm}mm precipitation`
          : 'Live Weather Feed',
        terrain: liveRisk.data?.terrain?.slope_degrees !== undefined && liveRisk.data?.terrain?.slope_degrees !== null
          ? `Slope ${liveRisk.data.terrain.slope_degrees}°`
          : 'Mountainous Slope',
        coordinatesFormatted: {
          lat: `${selectedLocation.latitude.toFixed(4)}° N`,
          lng: `${selectedLocation.longitude.toFixed(4)}° E`,
        },
        factors: (liveRisk.data?.contributing_factors || []).map((f) => ({
          name: f.factor,
          displayName: f.factor.replace(/_/g, ' ').toUpperCase(),
          score: typeof f.value === 'number' ? f.value : 50,
          weight: 0.25,
          summary: f.description,
        })),
      };
    }
    return null;
  }, [selectedHazardId, selectedLandslide, selectedLocation, liveRisk.data, dynamicHazards]);

  const selectedRoad = useMemo<RoadMeta | null>(
    () => (selectedRoadId ? dynamicRoadsList.find((r) => r.id === selectedRoadId) ?? null : null),
    [selectedRoadId, dynamicRoadsList],
  );

  const selectedObservation = useMemo<GroundObservation | null>(
    () => (selectedObservationId ? observations.find((o) => o.id === selectedObservationId) ?? null : null),
    [selectedObservationId, observations],
  );

  const selectedAlert = useMemo<SpatialAlert | null>(
    () => (selectedAlertId ? alerts.find((a) => a.id === selectedAlertId) ?? null : null),
    [selectedAlertId, alerts],
  );

  const selectedPriority = useMemo<PriorityItem | null>(
    () => (selectedPriorityId ? priorityList.find((p) => p.id === selectedPriorityId) ?? null : null),
    [selectedPriorityId, priorityList],
  );

  const value = useMemo(
    () => ({
      selectedLocation,
      selectLocation,
      hazards: dynamicHazards,
      selectedHazardId,
      selectedHazard,
      selectHazard,
      layers,
      toggleLayer,
      // GSI Historical Landslides & Viewport Loading
      landslides,
      selectedLandslideId,
      selectedLandslide,
      selectLandslide,
      viewportRoads,
      viewportBbox,
      updateViewport,
      hasDataInViewport,
      // Real SOS Layer
      sosList,
      loadSosList,
      selectedSosId,
      selectSos,
      roadsList: dynamicRoadsList,
      selectedRoadId,
      selectedRoad,
      simulationPhase,
      simulationResult,
      selectRoad,
      startSimulation,
      resetSimulation,
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
      evaluateLocationPriority,
      priorityLoading,
      priorityError,
      // Demo Mode
      isDemoRunning,
      demoStep,
      isDemoPaused,
      startDemo,
      stopDemo,
      pauseDemo,
      resumeDemo,
      prevDemoStep,
      nextDemoStep,
      setDemoStep,
      // Language & i18n
      language,
      setLanguage,
      // Modals & UI Actions
      reportModalOpen,
      openReportModal,
      closeReportModal,
      officerModalOpen,
      openOfficerModal,
      closeOfficerModal,
      // Offline Status
      isOffline,
      pendingSyncCount,
      triggerManualSync,
      // Identity & Verification
      identityStatus,
      identityModalOpen,
      openIdentityModal,
      closeIdentityModal,
      refreshIdentityStatus,
      // Regional Watch
      regionalWatches,
      loadRegionalWatches,
      // Live API
      evalCoords,
      liveRisk,
      weather,
      roadRisk,
      backendSimulation,
      // SOS
      sosState,
      openSosPanel,
      closeSosPanel,
      submitSos,
      // Real-Time
      wsStatus,
      soundEnabled,
      setSoundEnabled,
      soundBlocked,
      enableEmergencySound,
      notificationPermission,
      requestNotificationPermission,
      realtimeEvents,
      // Demo panel signals
      demoOpenWeather,
      demoOpenSos,
      triggerDemoWeather,
      triggerDemoSos,
      // Global System Status
      systemStatus: {
        readiness: readinessData,
        wsStatus,
        weatherAvailable: weather.state === 'success',
        identityAvailable: true,
        isOffline,
      },
      probeSystemReadiness,
      refreshOperationalData,
    }),
    [
      selectedLocation, selectLocation,
      selectedHazardId, selectedHazard, selectHazard,
      dynamicHazards,
      layers, toggleLayer,
      landslides, selectedLandslideId, selectedLandslide, selectLandslide,
      viewportRoads, viewportBbox, updateViewport, hasDataInViewport,
      sosList, loadSosList, selectedSosId, selectSos,
      selectedRoadId, selectedRoad, dynamicRoadsList, simulationPhase, simulationResult,
      selectRoad, startSimulation, resetSimulation,
      workflowTab,
      observations, selectedObservationId, selectedObservation, selectObservation,
      alerts, selectedAlertId, selectedAlert, selectAlert,
      acknowledgeAlert, resolveAlert, dismissAlert,
      userRole,
      priorityList, selectedPriorityId, selectedPriority, selectPriority,
      evaluateLocationPriority, priorityLoading, priorityError,
      isDemoRunning, demoStep, isDemoPaused, startDemo, stopDemo, pauseDemo, resumeDemo, prevDemoStep, nextDemoStep, setDemoStep,
      language,
      reportModalOpen, openReportModal, closeReportModal,
      officerModalOpen, openOfficerModal, closeOfficerModal,
      isOffline, pendingSyncCount, triggerManualSync,
      identityStatus, identityModalOpen, openIdentityModal, closeIdentityModal, refreshIdentityStatus,
      regionalWatches, loadRegionalWatches,
      evalCoords, liveRisk, weather, roadRisk, backendSimulation,
      sosState, openSosPanel, closeSosPanel, submitSos,
      wsStatus, soundEnabled, soundBlocked, enableEmergencySound, notificationPermission, requestNotificationPermission, realtimeEvents,
      demoOpenWeather, demoOpenSos, triggerDemoWeather, triggerDemoSos,
      readinessData, probeSystemReadiness, refreshOperationalData,
    ],
  );

  return (
    <MapContext.Provider value={value}>
      {children}
      <IdentityVerificationModal
        isOpen={identityModalOpen}
        onClose={closeIdentityModal}
        identityStatus={identityStatus}
        onStatusUpdated={refreshIdentityStatus}
      />
    </MapContext.Provider>
  );
}

// eslint-disable-next-line react/only-export-components
export function useMapContext(): MapContextValue {
  const ctx = useContext(MapContext);
  if (!ctx) throw new Error('useMapContext must be used within MapProvider');
  return ctx;
}
