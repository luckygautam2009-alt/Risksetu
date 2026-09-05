/**
 * RISKSETU AI — Centralized Authoritative API Client.
 *
 * All backend communications strictly flow through this module.
 * - Enforces zero fake fallback data.
 * - Handles JWT injection, timeouts, network interruptions, and structured errors (401, 403, 404, 422, 429, 500).
 * - Field names match backend FastAPI / Pydantic schemas exactly.
 */

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

// ---------------------------------------------------------------------------
// Unified Error Model
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  path: string;
  body: string;
  detail?: string;
  code?: string;

  constructor(status: number, path: string, body: string, detail?: string, code?: string) {
    super(`API ${status} at ${path}${detail ? ': ' + detail : ''}`);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
    this.body = body;
    this.detail = detail;
    this.code = code;
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

// ---------------------------------------------------------------------------
// Token & Auth Storage
// ---------------------------------------------------------------------------

let _inMemoryToken: string | null = null;

export function setAuthToken(token: string | null): void {
  _inMemoryToken = token;
  if (typeof localStorage !== 'undefined') {
    if (token) {
      localStorage.setItem('risksetu_auth_token', token);
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('risksetu_auth_token');
      localStorage.removeItem('token');
    }
  }
}

export function getAuthToken(): string | null {
  if (_inMemoryToken) return _inMemoryToken;
  if (typeof localStorage !== 'undefined') {
    return localStorage.getItem('risksetu_auth_token') || localStorage.getItem('token');
  }
  return null;
}

export function authHeaders(customToken?: string | null): Record<string, string> {
  const token = customToken || getAuthToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export function getAuthHeaders(token?: string | null): Record<string, string> {
  const t = token || getAuthToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

// ---------------------------------------------------------------------------
// Unified Request Pipeline
// ---------------------------------------------------------------------------

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  token?: string | null;
  headers?: Record<string, string>;
  timeoutMs?: number;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, token, headers = {}, timeoutMs = 15000 } = options;
  const mergedHeaders: Record<string, string> = { ...headers };

  if (!(body instanceof FormData) && !mergedHeaders['Content-Type']) {
    mergedHeaders['Content-Type'] = 'application/json';
  }

  const authToken = token !== undefined ? token : getAuthToken();
  if (authToken && !mergedHeaders['Authorization']) {
    mergedHeaders['Authorization'] = `Bearer ${authToken}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers: mergedHeaders,
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const rawText = await res.text().catch(() => '');
      let parsedDetail: string | undefined;
      let parsedCode: string | undefined;
      try {
        const json = JSON.parse(rawText);
        parsedDetail = json.detail || json.message || json.error;
        parsedCode = json.code || json.error_code;
      } catch {
        parsedDetail = rawText;
      }
      throw new ApiError(res.status, path, rawText, parsedDetail, parsedCode);
    }

    if (res.status === 204) {
      return {} as T;
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof ApiError) {
      throw err;
    }
    const isAbort = (err as Error)?.name === 'AbortError';
    throw new ApiError(
      0,
      path,
      isAbort ? 'Request timed out' : (err as Error)?.message || 'Network request failed',
      isAbort ? `Request timed out after ${timeoutMs}ms` : 'Network connection failed'
    );
  }
}

async function get<T>(path: string, token?: string | null): Promise<T> {
  return request<T>(path, { method: 'GET', token });
}

async function post<T>(path: string, body?: unknown, token?: string | null, headers?: Record<string, string>): Promise<T> {
  return request<T>(path, { method: 'POST', body, token, headers });
}

// ---------------------------------------------------------------------------
// Health & System Readiness — GET /health, GET /readiness
// ---------------------------------------------------------------------------

export interface ReadinessResponse {
  data: {
    status: 'ok' | 'degraded' | 'unhealthy' | string;
    checks: {
      database: string;
      redis: string;
      postgis?: string;
      [key: string]: string | undefined;
    };
  };
  meta: Record<string, unknown>;
}

export async function fetchHealth(): Promise<{ data: { status: string }; meta: Record<string, unknown> }> {
  return get<{ data: { status: string }; meta: Record<string, unknown> }>('/health');
}

export async function fetchReadiness(): Promise<ReadinessResponse> {
  return get<ReadinessResponse>('/readiness');
}

// ---------------------------------------------------------------------------
// Live Risk — GET /api/v1/live-risk
// ---------------------------------------------------------------------------

export interface LiveRiskResponse {
  data: {
    location: { latitude: number; longitude: number };
    timestamp: string;
    risk: { score: number; level: string; confidence: number };
    historical: {
      status: string;
      score: number | null;
      level: string | null;
      confidence: number | null;
      calculation_version: string | null;
      summary: string | null;
    };
    weather: {
      status: string;
      provider: string;
      precipitation_mm: number | null;
      temperature_c: number | null;
      humidity_pct: number | null;
      wind_speed_kmh: number | null;
      weather_code: number | null;
      description: string | null;
      observation_time: string | null;
      fetched_at: string | null;
      freshness_seconds: number | null;
      forecast_3day_precip_mm: number[];
      error_message: string | null;
    };
    ml: { status: string; susceptibility_score: number | null; model_version: string | null; reason: string | null };
    terrain: { status: string; elevation_m: number | null; slope_degrees: number | null; aspect: string | null; reason: string | null };
    contributing_factors: Array<{ factor: string; description: string; value: unknown; source: string }>;
    unavailable_inputs: string[];
    recommended_actions: Array<{ action_id: string; description: string; priority: string }>;
    data_freshness: {
      assessment_generated_at: string;
      historical_data_version: string | null;
      weather_observation_time: string | null;
      weather_fetched_at: string | null;
      weather_freshness_seconds: number | null;
    };
    engine_version: string;
  };
  meta: { request_id: string };
}

export async function fetchLiveRisk(lat: number, lon: number): Promise<LiveRiskResponse> {
  return get<LiveRiskResponse>(`/api/v1/live-risk?lat=${lat}&lon=${lon}`);
}

// ---------------------------------------------------------------------------
// Weather — GET /api/v1/weather/current
// ---------------------------------------------------------------------------

export interface WeatherResponse {
  data: {
    latitude: number;
    longitude: number;
    provider: string;
    provider_status: string;
    fetched_at: string;
    current: {
      timestamp: string;
      temperature_c: number;
      relative_humidity_pct: number;
      precipitation_mm: number;
      wind_speed_kmh: number;
      weather_code: number;
      weather_description: string;
    } | null;
    forecast: Array<{
      date: string;
      precipitation_sum_mm: number;
      temperature_max_c: number;
      temperature_min_c: number;
      weather_code: number;
      weather_description: string;
    }>;
    data_freshness_seconds: number;
    error_message: string | null;
  };
  meta: { request_id: string };
}

export async function fetchWeather(lat: number, lon: number): Promise<WeatherResponse> {
  return get<WeatherResponse>(`/api/v1/weather/current?lat=${lat}&lon=${lon}`);
}

// ---------------------------------------------------------------------------
// Road Risk — POST /api/v1/road-risk/evaluate
// ---------------------------------------------------------------------------

export interface RoadRiskResponse {
  data: {
    road: {
      edge_db_id: string | null;
      osm_way_id: number | null;
      from_node_id: number;
      to_node_id: number;
      highway_class: string | null;
      name: string | null;
      length_m: number;
      bridge: boolean;
      tunnel: boolean;
      distance_from_target_m: number | null;
    };
    blockage: {
      predicted_risk_score: number;
      risk_level: string;
      confidence: number;
      status: string;
      closure_status: string;
      traffic_status: string;
    };
    factors: Array<{ name: string; description: string; value: unknown; source: string; contribution_pts: number }>;
    connectivity: {
      simulation_type: string;
      components_before: number;
      components_after: number;
      component_increase: number;
      nodes_affected: number;
      edges_in_affected_components: number;
      isolation_severity: number;
      is_bridge_edge: boolean;
      simulation_error: string | null;
    };
    unavailable_inputs: string[];
    recommendations: Array<{ action_id: string; description: string; priority: string }>;
    data_freshness: { assessment_generated_at: string; weather_observation_time: string | null };
    engine_version: string;
  };
  meta: { request_id: string };
}

export async function fetchRoadRisk(
  lat: number,
  lon: number,
  radiusM = 5000,
  searchRadiusM = 1000,
): Promise<RoadRiskResponse> {
  return post<RoadRiskResponse>('/api/v1/road-risk/evaluate', {
    latitude: lat,
    longitude: lon,
    radius_m: radiusM,
    search_radius_m: searchRadiusM,
  });
}

// ---------------------------------------------------------------------------
// Road impact simulation — POST /api/v1/impact/simulate-road-blockage
// ---------------------------------------------------------------------------

export interface SimulationApiResponse {
  data: {
    simulation_type: string;
    target_location: { latitude: number; longitude: number };
    subgraph_radius_m: number;
    blocked_edge: {
      edge_db_id: string | null;
      osm_way_id: number | null;
      from_node_id: number;
      to_node_id: number;
      highway_class: string | null;
      name: string | null;
      length_m: number;
      bridge: boolean;
      is_bridge_edge: boolean;
      distance_from_target_m: number | null;
    };
    connectivity_impact: {
      components_before: number;
      components_after: number;
      component_increase: number;
      nodes_affected: number;
      edges_in_affected_components: number;
      is_bridge_edge: boolean;
      articulation_points_near_blockage: number[];
    };
    isolation_severity: number;
    isolated_components: Array<{ component_index: number; node_count: number; edge_count: number }>;
    graph_stats_before: { total_nodes: number; total_edges: number; connected_components: number };
    graph_stats_after: { total_nodes: number; total_edges: number; connected_components: number };
    summary_explanation: string;
    limitations: string[];
  };
  meta: { request_id: string };
}

export async function runImpactSimulation(
  lat: number,
  lon: number,
  radiusM = 5000,
  searchRadiusM = 1000,
): Promise<SimulationApiResponse> {
  return post<SimulationApiResponse>('/api/v1/impact/simulate-road-blockage', {
    latitude: lat,
    longitude: lon,
    radius_m: radiusM,
    search_radius_m: searchRadiusM,
  });
}

// ---------------------------------------------------------------------------
// Priority Engine — POST /api/v1/priority/evaluate & /rank
// ---------------------------------------------------------------------------

export interface PriorityBreakdownDetail {
  risk_contribution: number;
  impact_contribution: number;
  urgency_contribution: number;
  priority_score: number;
  priority_level: string;
}

export interface PriorityEvaluationRequest {
  candidate_id?: string;
  latitude: number;
  longitude: number;
  risk_score?: number;
  risk_level?: string;
  risk_confidence?: number;
  isolation_severity?: number;
  component_increase?: number;
  nodes_affected?: number;
  edges_in_affected_components?: number;
  is_bridge_edge?: boolean;
  radius_m?: number;
  search_radius_m?: number;
}

export interface PriorityEvaluationData {
  candidate_id: string;
  latitude: number;
  longitude: number;
  priority_score: number;
  priority_level: string;
  breakdown: PriorityBreakdownDetail;
  risk_score: number;
  risk_level: string;
  risk_confidence: number;
  isolation_severity: number;
  component_increase: number;
  nodes_affected: number;
  edges_in_affected_components: number;
  is_bridge_edge: boolean;
  urgency_score: number;
  calculation_version: string;
  explanation: string;
  limitations: string[];
}

export interface PriorityEvaluationResponse {
  data: PriorityEvaluationData;
  meta: { request_id: string };
}

export async function evaluatePriority(payload: PriorityEvaluationRequest): Promise<PriorityEvaluationResponse> {
  return post<PriorityEvaluationResponse>('/api/v1/priority/evaluate', payload);
}

// ---------------------------------------------------------------------------
// Alerts — GET /api/v1/alerts
// ---------------------------------------------------------------------------

export interface AlertsApiResponse {
  data: {
    total_count: number;
    limit: number;
    offset: number;
    alerts: Array<{
      id: string;
      alert_type: string;
      severity: string;
      title: string;
      location_description?: string;
      latitude: number;
      longitude: number;
      status: string;
      priority_score: number | null;
      priority_level: string | null;
      created_at: string;
      source_reference?: string;
      recommended_action?: string;
    }>;
  };
  meta: { request_id: string };
}

export async function fetchAlerts(status?: string, limit = 50): Promise<AlertsApiResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set('status', status);
  return get<AlertsApiResponse>(`/api/v1/alerts?${params.toString()}`);
}

export async function acknowledgeAlertApi(alertId: string, reason?: string): Promise<unknown> {
  return post(`/api/v1/alerts/${alertId}/acknowledge`, { reason: reason || 'Acknowledged in operational command center' });
}

export async function resolveAlertApi(alertId: string, reason?: string): Promise<unknown> {
  return post(`/api/v1/alerts/${alertId}/resolve`, { reason: reason || 'Resolved in operational command center' });
}

export async function dismissAlertApi(alertId: string, reason?: string): Promise<unknown> {
  return post(`/api/v1/alerts/${alertId}/dismiss`, { reason: reason || 'Dismissed in operational command center' });
}

// ---------------------------------------------------------------------------
// SOS — POST /api/v1/sos  (unauthenticated for demo; real deployment needs JWT)
// ---------------------------------------------------------------------------

export interface SosCreateRequest {
  latitude: number;
  longitude: number;
  severity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  description?: string;
  evidence_id?: string;
}

export interface SosResponse {
  data: {
    id: string;
    latitude: number;
    longitude: number;
    severity: string;
    status: string;
    description: string | null;
    risk_context: {
      risk_score: number | null;
      risk_level: string | null;
      risk_confidence: number | null;
      weather_status: string | null;
      live_risk_available: boolean;
    };
    linked_alert_id: string | null;
    created_at: string;
  };
  meta: { request_id: string };
}

export async function createSos(
  body: SosCreateRequest,
  authToken?: string,
): Promise<SosResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  const res = await fetch(`${BASE}/api/v1/sos`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/sos', text);
  }
  return res.json() as Promise<SosResponse>;
}

// ---------------------------------------------------------------------------
// Historical Landslides (GSI) — GET /api/v1/landslides
// ---------------------------------------------------------------------------

export interface LandslideItem {
  id: string;
  gsi_slide_no: string;
  slide_name: string | null;
  state: string;
  district: string;
  location_description: string | null;
  road_corridor: string | null;
  latitude: number;
  longitude: number;
  movement_type: string | null;
  material: string | null;
  event_date: string | null;
  source_dataset: string;
}

export interface LandslidesResponse {
  data: {
    total_count: number;
    limit: number;
    offset: number;
    items: LandslideItem[];
  };
  meta: { request_id?: string };
}

export async function fetchLandslidesViewport(
  minLat?: number,
  maxLat?: number,
  minLon?: number,
  maxLon?: number,
  limit = 200,
  offset = 0,
): Promise<LandslidesResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (minLat !== undefined && maxLat !== undefined && minLon !== undefined && maxLon !== undefined) {
    params.set('min_lat', String(minLat));
    params.set('max_lat', String(maxLat));
    params.set('min_lon', String(minLon));
    params.set('max_lon', String(maxLon));
  }
  return get<LandslidesResponse>(`/api/v1/landslides?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// OSM Road Network Viewport — GET /api/v1/roads
// ---------------------------------------------------------------------------

export interface RoadEdgeItem {
  id: string;
  osm_way_id: number;
  highway_class: string;
  name: string | null;
  bridge: boolean;
  tunnel: boolean;
  length_m: number;
  coordinates: [number, number][];
}

export interface RoadsResponse {
  data: {
    total_count: number;
    limit: number;
    items: RoadEdgeItem[];
  };
  meta: { request_id?: string };
}

export async function fetchRoadsViewport(
  minLat: number,
  maxLat: number,
  minLon: number,
  maxLon: number,
  limit = 150,
): Promise<RoadsResponse> {
  const params = new URLSearchParams({
    min_lat: String(minLat),
    max_lat: String(maxLat),
    min_lon: String(minLon),
    max_lon: String(maxLon),
    limit: String(limit),
  });
  return get<RoadsResponse>(`/api/v1/roads?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Shelters — GET /api/v1/shelters/nearby
// ---------------------------------------------------------------------------

export interface SheltersResponse {
  data: {
    data_status: 'available' | 'unavailable' | 'empty';
    data_source_note: string;
    query_lat: number;
    query_lon: number;
    radius_m: number;
    total_found: number;
    shelters: Array<{
      id: string;
      name: string;
      facility_type: string | null;
      latitude: number;
      longitude: number;
      distance_m: number;
      capacity_persons: number | null;
      is_accessible: boolean | null;
      data_source: string;
      suitability_score: number | null;
      connectivity_note: string;
    }>;
    limitations: string[];
  };
  meta: { request_id: string };
}

export async function fetchNearbyShelters(
  lat: number,
  lon: number,
  radiusM = 20000,
): Promise<SheltersResponse> {
  return get<SheltersResponse>(
    `/api/v1/shelters/nearby?lat=${lat}&lon=${lon}&radius_m=${radiusM}`,
  );
}

// ---------------------------------------------------------------------------
// Ground Reports — POST /api/v1/ground-reports, GET /api/v1/ground-reports
// ---------------------------------------------------------------------------

export interface GroundReportSubmitRequest {
  report_type: string;
  description: string;
  latitude: number;
  longitude: number;
  observed_at: string;
  evidence_id?: string;
}

export interface GroundReportResponse {
  data: {
    report_id: string;
    user_id: string;
    report_type: string;
    description: string;
    latitude: number;
    longitude: number;
    observed_at: string;
    status: string;
    trust: {
      trust_score: number;
      trust_class: string;
      components: {
        geo_plausibility: number;
        temporal_freshness: number;
        user_reliability: number;
        corroboration: number;
      };
    };
    risk_influence_eligible: boolean;
    explanation: {
      summary: string;
      breakdown: string[];
    };
    created_at: string;
  };
  meta: { request_id: string };
}

export async function submitGroundReport(
  body: GroundReportSubmitRequest,
  token?: string,
): Promise<GroundReportResponse> {
  const res = await fetch(`${BASE}/api/v1/ground-reports`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/ground-reports', text);
  }
  return res.json() as Promise<GroundReportResponse>;
}

export async function fetchGroundReports(
  limit = 20,
  offset = 0,
  token?: string,
): Promise<{ data: { total_count: number; reports: Array<any> } }> {
  const res = await fetch(`${BASE}/api/v1/ground-reports?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/ground-reports', text);
  }
  return res.json();
}

export async function moderateGroundReportStatus(
  reportId: string,
  newStatus: 'ACCEPTED' | 'REJECTED' | 'REVIEW_REQUIRED',
  reason: string,
  token?: string,
): Promise<GroundReportResponse> {
  const res = await fetch(`${BASE}/api/v1/ground-reports/${reportId}/status`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify({ status: newStatus, reason }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, `/api/v1/ground-reports/${reportId}/status`, text);
  }
  return res.json() as Promise<GroundReportResponse>;
}

// ---------------------------------------------------------------------------
// Officer SOS Operations — GET /api/v1/sos, POST acknowledge, POST resolve
// ---------------------------------------------------------------------------

export interface SosListItem {
  id: string;
  latitude: number;
  longitude: number;
  severity: string;
  status: string;
  risk_level: string | null;
  created_at: string;
}

export async function fetchSosList(
  statusFilter?: string,
  limit = 50,
  offset = 0,
  token?: string,
): Promise<{ data: { total_count: number; items: SosListItem[] } }> {
  const q = statusFilter ? `&status=${statusFilter}` : '';
  const res = await fetch(`${BASE}/api/v1/sos?limit=${limit}&offset=${offset}${q}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/sos', text);
  }
  return res.json();
}

export async function acknowledgeSos(
  sosId: string,
  reason: string,
  token?: string,
): Promise<SosResponse> {
  const res = await fetch(`${BASE}/api/v1/sos/${sosId}/acknowledge`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, `/api/v1/sos/${sosId}/acknowledge`, text);
  }
  return res.json() as Promise<SosResponse>;
}

export async function resolveSos(
  sosId: string,
  reason: string,
  token?: string,
): Promise<SosResponse> {
  const res = await fetch(`${BASE}/api/v1/sos/${sosId}/resolve`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, `/api/v1/sos/${sosId}/resolve`, text);
  }
  return res.json() as Promise<SosResponse>;
}

// ---------------------------------------------------------------------------
// Mass Alert — POST /api/v1/alerts/generate
// ---------------------------------------------------------------------------

export interface GenerateAlertRequest {
  latitude: number;
  longitude: number;
  risk_score: number;
  risk_level: string;
  risk_confidence: number;
  isolation_severity?: string;
  priority_score?: number;
  priority_level?: string;
  ground_intelligence_summary?: string;
  source_reference?: string;
}

export async function generateMassAlert(
  body: GenerateAlertRequest,
  token?: string,
): Promise<{ data: any; meta: { was_created: boolean } }> {
  const res = await fetch(`${BASE}/api/v1/alerts/generate`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/alerts/generate', text);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// OSINT — Public-Source Intelligence (GET & POST)
// ---------------------------------------------------------------------------

export interface OsintLead {
  area: string;
  latitude: number;
  longitude: number;
  hazard: string;
  severity: string;
  confidence: string;
  corroboration_score: number;
  evidence_count: number;
  independent_sources: number;
  rainfall_24h_mm: number;
  affected_areas: string[];
  impact_window: string;
  recommended_action: string;
  analysis_note: string;
  evidence: Array<{
    source: string;
    source_type: string;
    title: string;
    summary: string;
    url?: string;
    published_at?: string;
  }>;
  source: string;
  data_mode: string;
  updated_at: string;
}

export async function fetchOsintLeads(): Promise<{ data: OsintLead[] }> {
  return get<{ data: OsintLead[] }>('/api/v1/osint');
}

export async function scanOsintLeads(): Promise<{ data: OsintLead[] }> {
  return post<{ data: OsintLead[] }>('/api/v1/osint/scan', {});
}

// ---------------------------------------------------------------------------
// Regional Watch — GET /api/v1/regional-watch
// ---------------------------------------------------------------------------

export interface RegionalWatchItem {
  id: string;
  name: string;
  hazard_type: string;
  severity: string;
  title: string;
  message: string;
  latitude: number;
  longitude: number;
  region: string;
  country: string;
  affected_regions: string[];
  forecast_rain_mm: number;
  confidence: string;
  verified: boolean;
  source: string;
  data_mode: string;
  updated_at: string;
}

export async function fetchRegionalWatches(): Promise<{ data: RegionalWatchItem[] }> {
  return get<{ data: RegionalWatchItem[] }>('/api/v1/regional-watch');
}

// ---------------------------------------------------------------------------
// Identity Verification & Evidence Upload — API & Types
// ---------------------------------------------------------------------------

export type IdentityProviderType = 'AADHAAR' | 'DIGILOCKER';
export type IdentityStatus = 'UNVERIFIED' | 'VERIFICATION_PENDING' | 'VERIFIED' | 'VERIFICATION_FAILED' | 'EXPIRED';

export interface IdentityStatusData {
  user_id: string;
  status: IdentityStatus;
  is_verified: boolean;
  provider: IdentityProviderType | null;
  verified_at: string | null;
  expires_at: string | null;
  minimal_reference: string | null;
  failure_code: string | null;
  failure_message: string | null;
}

export interface IdentityStatusResponse {
  data: IdentityStatusData;
  meta: Record<string, unknown>;
}

export interface IdentityStartResponse {
  success: boolean;
  provider: IdentityProviderType;
  status: IdentityStatus;
  provider_transaction_id?: string | null;
  redirect_url?: string | null;
  state_token?: string | null;
  message: string;
  is_provider_available: boolean;
  meta?: Record<string, unknown>;
}

export interface EvidenceUploadResponse {
  data: {
    evidence_id: string;
    owner_user_id: string;
    mime_type: string;
    original_filename: string;
    file_size_bytes: number;
    sha256_checksum: string;
    upload_status: string;
    created_at: string;
  };
  meta: Record<string, unknown>;
}

export async function fetchIdentityMe(token?: string): Promise<IdentityStatusResponse> {
  const authHeaders = getAuthHeaders(token);
  const res = await fetch(`${BASE}/api/v1/identity/me`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/identity/me', text);
  }
  return res.json() as Promise<IdentityStatusResponse>;
}

export async function startIdentityVerification(
  provider: IdentityProviderType,
  consentObtained: boolean,
  redirectUri?: string,
  token?: string
): Promise<IdentityStartResponse> {
  const authHeaders = getAuthHeaders(token);
  const res = await fetch(`${BASE}/api/v1/identity/verification/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify({ provider, consent_obtained: consentObtained, redirect_uri: redirectUri }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/identity/verification/start', text);
  }
  return res.json() as Promise<IdentityStartResponse>;
}

export async function uploadEvidence(file: File, token?: string): Promise<EvidenceUploadResponse> {
  const authHeaders = getAuthHeaders(token);
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE}/api/v1/evidence/upload`, {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/evidence/upload', text);
  }
  return res.json() as Promise<EvidenceUploadResponse>;
}

// ---------------------------------------------------------------------------
// SOS Lifecycle — Cancel, Audit Trail
// ---------------------------------------------------------------------------

export async function cancelSos(
  sosId: string,
  reason: string,
  token?: string,
): Promise<SosResponse> {
  const res = await fetch(`${BASE}/api/v1/sos/${sosId}/cancel`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, `/api/v1/sos/${sosId}/cancel`, text);
  }
  return res.json() as Promise<SosResponse>;
}

export interface SosAuditEntry {
  id: string;
  action: string;
  actor_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export async function fetchSosAudits(
  sosId: string,
  token?: string,
): Promise<{ data: SosAuditEntry[] }> {
  const res = await fetch(`${BASE}/api/v1/sos/${sosId}/audits`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, `/api/v1/sos/${sosId}/audits`, text);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Alert Subscriptions — GET /api/v1/subscriptions/me, POST /api/v1/subscriptions
// ---------------------------------------------------------------------------

export interface AlertSubscriptionItem {
  id: string;
  notification_type: string;
  enabled: boolean;
  geofence_radius_km: number | null;
  created_at: string;
  updated_at: string;
}

export interface AlertSubscriptionsResponse {
  data: AlertSubscriptionItem[];
  meta: Record<string, unknown>;
}

export async function fetchAlertSubscriptions(
  token?: string,
): Promise<AlertSubscriptionsResponse> {
  const res = await fetch(`${BASE}/api/v1/subscriptions/me`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/subscriptions/me', text);
  }
  return res.json() as Promise<AlertSubscriptionsResponse>;
}

export async function updateAlertSubscriptions(
  subscriptions: Array<{
    notification_type: string;
    enabled: boolean;
    geofence_radius_km?: number | null;
  }>,
  token?: string,
): Promise<AlertSubscriptionsResponse> {
  const res = await fetch(`${BASE}/api/v1/subscriptions`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ subscriptions }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, '/api/v1/subscriptions', text);
  }
  return res.json() as Promise<AlertSubscriptionsResponse>;
}

// ---------------------------------------------------------------------------
// Evidence File — URL builder for direct binary download
// ---------------------------------------------------------------------------

/**
 * Returns the URL for downloading an evidence file.
 * The actual endpoint serves the binary with authentication.
 */
export function getEvidenceFileUrl(evidenceId: string): string {
  return `${BASE}/api/v1/evidence/${evidenceId}/file`;
}

