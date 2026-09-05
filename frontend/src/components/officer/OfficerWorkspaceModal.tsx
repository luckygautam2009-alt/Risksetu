import { useState, useEffect, useRef } from 'react';
import { useMapContext } from '../../context/MapContext';
import {
  fetchSosList,
  acknowledgeSos,
  resolveSos,
  cancelSos,
  generateMassAlert,
  fetchOsintLeads,
  scanOsintLeads,
  fetchSosAudits,
  type SosListItem,
  type OsintLead,
  type SosAuditEntry,
} from '../../services/api';
import { t } from '../../utils/i18n';
import './OfficerWorkspaceModal.css';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = 'sos_queue' | 'mass_alert' | 'osint_intel';

export function OfficerWorkspaceModal({ isOpen, onClose }: Props) {
  const { language, selectedHazard, evalCoords, userRole, liveRisk } = useMapContext();
  const [activeTab, setActiveTab] = useState<TabType>('sos_queue');

  // Tab 1: SOS Queue
  const [sosList, setSosList] = useState<SosListItem[]>([]);
  const [sosLoading, setSosLoading] = useState(false);
  const [sosActionId, setSosActionId] = useState<string | null>(null);
  const [expandedSosId, setExpandedSosId] = useState<string | null>(null);
  const [sosAudits, setSosAudits] = useState<Record<string, SosAuditEntry[]>>({});
  const [cancelReason, setCancelReason] = useState('');

  // Tab 2: Mass Alert
  const [alertRadius, setAlertRadius] = useState<number>(1000);
  const [alertSeverity, setAlertSeverity] = useState<'WARNING' | 'CRITICAL' | 'EVACUATION'>('CRITICAL');
  const [alertHeadline, setHeadline] = useState('LANDSLIDE DEBRIS FLOW WARNING');
  const [alertMessage, setMessage] = useState(
    'Debris flow triggered upstream. Evacuate low-lying riverbed and roadside corridors immediately.',
  );
  const [alertSubmitting, setAlertSubmitting] = useState(false);
  const [alertSuccess, setAlertSuccess] = useState<string | null>(null);
  const [sirenPlaying, setSirenPlaying] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const oscRef = useRef<OscillatorNode | null>(null);

  // Tab 3: OSINT Leads
  const [osintLeads, setOsintLeads] = useState<OsintLead[]>([]);
  const [osintLoading, setOsintLoading] = useState(false);
  const [osintScanning, setOsintScanning] = useState(false);

  // ESC to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  // Load SOS list when SOS tab is active
  useEffect(() => {
    if (!isOpen || activeTab !== 'sos_queue') return;
    setSosLoading(true);
    fetchSosList()
      .then((res) => setSosList(res.data.items))
      .catch(() => setSosList([]))
      .finally(() => setSosLoading(false));
  }, [isOpen, activeTab]);

  // Load OSINT leads when OSINT tab is active
  useEffect(() => {
    if (!isOpen || activeTab !== 'osint_intel') return;
    setOsintLoading(true);
    fetchOsintLeads()
      .then((res) => setOsintLeads(res.data))
      .catch(() => setOsintLeads([]))
      .finally(() => setOsintLoading(false));
  }, [isOpen, activeTab]);

  // Handle SOS actions
  const handleAcknowledgeSos = async (id: string) => {
    setSosActionId(id);
    try {
      await acknowledgeSos(id, `${userRole} (Officer Workspace)`);
      setSosList((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'ACKNOWLEDGED' } : s)),
      );
    } catch (err: unknown) {
      console.error('Failed to acknowledge SOS in database:', err);
    } finally {
      setSosActionId(null);
    }
  };

  const handleResolveSos = async (id: string) => {
    setSosActionId(id);
    try {
      await resolveSos(id, `${userRole} (Officer Workspace)`);
      setSosList((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'RESOLVED' } : s)),
      );
    } catch (err: unknown) {
      console.error('Failed to resolve SOS in database:', err);
    } finally {
      setSosActionId(null);
    }
  };

  const handleCancelSos = async (id: string) => {
    if (!cancelReason.trim()) return;
    setSosActionId(id);
    try {
      await cancelSos(id, cancelReason.trim());
      setSosList((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'CANCELLED' } : s)),
      );
      setCancelReason('');
    } catch (err: unknown) {
      console.error('Failed to cancel SOS in database:', err);
    } finally {
      setSosActionId(null);
    }
  };

  const handleExpandSos = async (id: string) => {
    if (expandedSosId === id) {
      setExpandedSosId(null);
      return;
    }
    setExpandedSosId(id);
    // Load audit trail
    if (!sosAudits[id]) {
      try {
        const res = await fetchSosAudits(id);
        setSosAudits((prev) => ({ ...prev, [id]: res.data }));
      } catch {
        setSosAudits((prev) => ({ ...prev, [id]: [] }));
      }
    }
  };

  // Trigger web siren synthesis
  const toggleSirenSound = () => {
    if (sirenPlaying) {
      if (oscRef.current) {
        oscRef.current.stop();
        oscRef.current.disconnect();
        oscRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close();
        audioCtxRef.current = null;
      }
      setSirenPlaying(false);
    } else {
      try {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.4);
        osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.8);

        gain.gain.setValueAtTime(0.15, ctx.currentTime);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();

        audioCtxRef.current = ctx;
        oscRef.current = osc;
        setSirenPlaying(true);

        // Auto stop after 5 seconds
        setTimeout(() => {
          if (oscRef.current) {
            try { oscRef.current.stop(); oscRef.current.disconnect(); oscRef.current = null; } catch {}
          }
          if (audioCtxRef.current) {
            try { audioCtxRef.current.close(); audioCtxRef.current = null; } catch {}
          }
          setSirenPlaying(false);
        }, 5000);
      } catch {
        // audio synthesis blocked
      }
    }
  };

  // Stop siren on unmount/close
  useEffect(() => {
    return () => {
      if (oscRef.current) {
        try { oscRef.current.stop(); oscRef.current.disconnect(); } catch {}
      }
      if (audioCtxRef.current) {
        try { audioCtxRef.current.close(); } catch {}
      }
    };
  }, []);

  // Handle Mass Alert Broadcast
  const [alertError, setAlertError] = useState<string | null>(null);

  const handleBroadcastAlert = async () => {
    const lat = evalCoords?.lat ?? selectedHazard?.latitude;
    const lon = evalCoords?.lon ?? selectedHazard?.longitude;
    if (lat === undefined || lon === undefined) {
      setAlertError('Coordinates unavailable. Select a hazard or location on the map first.');
      return;
    }
    if (!liveRisk.data?.risk) {
      setAlertError('Live risk assessment unavailable for this location. Cannot generate alert without backend risk evaluation.');
      return;
    }

    setAlertSubmitting(true);
    setAlertSuccess(null);
    setAlertError(null);
    try {
      const res = await generateMassAlert({
        latitude: lat,
        longitude: lon,
        risk_score: liveRisk.data.risk.score,
        risk_level: liveRisk.data.risk.level,
        risk_confidence: liveRisk.data.risk.confidence,
        source_reference: `Officer Geofenced Broadcast — ${alertSeverity} — ${alertRadius}m perimeter`,
      });
      const alertId = res.data?.id ?? 'RECORDED';
      setAlertSuccess(
        `Alert persisted to database (ID: ${alertId}) across ${alertRadius}m perimeter. SMS GATEWAY · NOT CONFIGURED (No cellular carrier credentials).`,
      );
      toggleSirenSound();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Database alert generation failed.';
      setAlertError(`Alert generation failed: ${msg}. No unverified alert was created.`);
    } finally {
      setAlertSubmitting(false);
    }
  };

  // Handle manual OSINT scan trigger
  const handleTriggerScan = async () => {
    setOsintScanning(true);
    try {
      const res = await scanOsintLeads();
      setOsintLeads(res.data);
    } catch (err: unknown) {
      console.error('OSINT scan failed:', err);
      setOsintLeads([]);
    } finally {
      setOsintScanning(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="officer-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="officer-modal" onClick={(e) => e.stopPropagation()}>
        {/* ── Modal Header ── */}
        <div className="officer-modal__header">
          <div className="officer-modal__title-group">
            <span className="officer-modal__badge font-mono">OFFICER HQ</span>
            <h2 className="officer-modal__title font-mono">{t(language, 'officerWorkspace')}</h2>
          </div>
          <button
            type="button"
            className="officer-modal__close"
            onClick={onClose}
            aria-label="Close officer modal"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* ── Navigation Tabs ── */}
        <div className="officer-modal__tabs">
          <button
            type="button"
            className={`officer-tab font-mono ${activeTab === 'sos_queue' ? 'active' : ''}`}
            onClick={() => setActiveTab('sos_queue')}
          >
            {t(language, 'sosQueue')} ({sosList.length})
          </button>
          <button
            type="button"
            className={`officer-tab font-mono ${activeTab === 'mass_alert' ? 'active' : ''}`}
            onClick={() => setActiveTab('mass_alert')}
          >
            {t(language, 'massAlertBroadcast')}
          </button>
          <button
            type="button"
            className={`officer-tab font-mono ${activeTab === 'osint_intel' ? 'active' : ''}`}
            onClick={() => setActiveTab('osint_intel')}
          >
            {t(language, 'osintScanner')}
          </button>
        </div>

        {/* ── Tab Content ── */}
        <div className="officer-modal__body">
          {/* TAB 1: SOS QUEUE */}
          {activeTab === 'sos_queue' && (
            <div className="officer-sos-view">
              <div className="officer-section-hdr">
                <span className="font-mono">DISPATCH STATUS: ACTIVE MONITORING</span>
                <button
                  type="button"
                  className="officer-refresh-btn font-mono"
                  onClick={() => {
                    setSosLoading(true);
                    fetchSosList()
                      .then((r) => setSosList(r.data.items))
                      .catch(() => setSosList([]))
                      .finally(() => setSosLoading(false));
                  }}
                >
                  ↻ Refresh
                </button>
              </div>

              {sosLoading && (
                <div className="officer-loading font-mono">Querying certified SOS dispatch table…</div>
              )}

              {!sosLoading && sosList.length === 0 && (
                <div className="officer-empty font-mono">
                  No pending SOS incidents in active queue. Standby mode active.
                </div>
              )}

              {!sosLoading && sosList.length > 0 && (
                <div className="officer-sos-list">
                  {sosList.map((item) => (
                    <div key={item.id} className={`officer-sos-card ${expandedSosId === item.id ? 'expanded' : ''}`}>
                      <div
                        className="officer-sos-top"
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleExpandSos(item.id)}
                      >
                        <div className="officer-sos-meta">
                          <span className={`officer-sev-tag font-mono sev-${item.severity.toLowerCase()}`}>
                            {item.severity}
                          </span>
                          <span className="officer-sos-id font-mono">ID: {item.id.slice(0, 8)}</span>
                        </div>
                        <span className={`officer-status-badge font-mono status-${item.status.toLowerCase()}`}>
                          {item.status}
                        </span>
                      </div>

                      <div className="officer-sos-coords font-mono">
                        {item.latitude.toFixed(5)}°N, {item.longitude.toFixed(5)}°E
                      </div>

                      {/* ── Expanded Detail Card ── */}
                      {expandedSosId === item.id && (
                        <div className="officer-sos-detail">
                          {/* Risk Snapshot */}
                          {item.risk_level && (
                            <div className="officer-sos-risk-snap font-mono">
                              <span className="officer-detail-label">RISK SNAPSHOT</span>
                              <span className={`officer-risk-val risk-${item.risk_level?.toLowerCase()}`}>
                                {item.risk_level}
                              </span>
                            </div>
                          )}

                          {/* Timestamp */}
                          <div className="officer-detail-row font-mono">
                            <span className="officer-detail-label">CREATED</span>
                            <span>{new Date(item.created_at).toLocaleString()}</span>
                          </div>

                          {/* Audit Timeline */}
                          <div className="officer-audit-section">
                            <span className="officer-detail-label font-mono">AUDIT TRAIL</span>
                            {sosAudits[item.id] ? (
                              sosAudits[item.id].length > 0 ? (
                                <div className="officer-audit-list">
                                  {sosAudits[item.id].map((audit) => (
                                    <div key={audit.id} className="officer-audit-item font-mono">
                                      <span className="officer-audit-action">{audit.action}</span>
                                      <span className="officer-audit-time">
                                        {new Date(audit.created_at).toLocaleTimeString()}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <span className="font-mono" style={{ fontSize: '10px', color: '#94a3b8' }}>
                                  No audit entries recorded.
                                </span>
                              )
                            ) : (
                              <span className="font-mono" style={{ fontSize: '10px', color: '#64748b' }}>
                                Loading audit trail…
                              </span>
                            )}
                          </div>
                        </div>
                      )}

                      <div className="officer-sos-actions font-mono">
                        {item.status === 'ACTIVE' && (
                          <button
                            type="button"
                            className="officer-btn officer-btn--ack"
                            disabled={sosActionId === item.id}
                            onClick={() => handleAcknowledgeSos(item.id)}
                          >
                            {sosActionId === item.id ? 'Updating…' : 'ACKNOWLEDGE'}
                          </button>
                        )}
                        {item.status !== 'RESOLVED' && item.status !== 'CANCELLED' && (
                          <button
                            type="button"
                            className="officer-btn officer-btn--res"
                            disabled={sosActionId === item.id}
                            onClick={() => handleResolveSos(item.id)}
                          >
                            {sosActionId === item.id ? 'Updating…' : 'MARK RESOLVED'}
                          </button>
                        )}
                        {item.status !== 'CANCELLED' && item.status !== 'RESOLVED' && expandedSosId === item.id && (
                          <div className="officer-cancel-row">
                            <input
                              type="text"
                              className="officer-cancel-input font-mono"
                              placeholder="Cancellation reason…"
                              value={cancelReason}
                              onChange={(e) => setCancelReason(e.target.value)}
                            />
                            <button
                              type="button"
                              className="officer-btn officer-btn--cancel"
                              disabled={sosActionId === item.id || !cancelReason.trim()}
                              onClick={() => handleCancelSos(item.id)}
                            >
                              CANCEL SOS
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: MASS ALERT BROADCAST */}
          {activeTab === 'mass_alert' && (
            <div className="officer-alert-view">
              <div className="officer-alert-disclaimer">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <span>
                  <strong>Official Dispatch Authority:</strong> Geofenced mass siren and broadcast signals will transmit
                  simulated alerts across designated cellular and local terminal relays. Web audio siren is opt-in and cannot override hardware silent mode.
                </span>
              </div>

              <div className="officer-form-group">
                <label className="font-mono">PERIMETER RADIUS</label>
                <div className="officer-radio-group">
                  {[500, 1000, 3000, 5000].map((r) => (
                    <button
                      key={r}
                      type="button"
                      className={`officer-pill font-mono ${alertRadius === r ? 'selected' : ''}`}
                      onClick={() => setAlertRadius(r)}
                    >
                      {r >= 1000 ? `${r / 1000} km` : `${r} m`}
                    </button>
                  ))}
                </div>
              </div>

              <div className="officer-form-group">
                <label className="font-mono">SEVERITY LEVEL</label>
                <select
                  className="officer-select font-mono"
                  value={alertSeverity}
                  onChange={(e) => setAlertSeverity(e.target.value as typeof alertSeverity)}
                >
                  <option value="WARNING">WARNING (High Probability)</option>
                  <option value="CRITICAL">CRITICAL (Direct Threat)</option>
                  <option value="EVACUATION">EVACUATION ORDER (Immediate Hazard)</option>
                </select>
              </div>

              <div className="officer-form-group">
                <label className="font-mono">ALERT HEADLINE</label>
                <input
                  type="text"
                  className="officer-input font-mono"
                  value={alertHeadline}
                  onChange={(e) => setHeadline(e.target.value)}
                />
              </div>

              <div className="officer-form-group">
                <label className="font-mono">DISPATCH MESSAGE</label>
                <textarea
                  className="officer-textarea font-mono"
                  rows={3}
                  value={alertMessage}
                  onChange={(e) => setMessage(e.target.value)}
                />
              </div>

              {alertSuccess && (
                <div className="officer-alert-success font-mono">
                  ✓ {alertSuccess}
                </div>
              )}

              {alertError && (
                <div className="officer-alert-error font-mono" style={{ color: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '8px 12px', borderRadius: '4px', marginBottom: '12px', fontSize: '12px' }}>
                  ⚠ {alertError}
                </div>
              )}

              <div className="officer-sms-status font-mono" style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '12px', padding: '6px 10px', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: '4px' }}>
                <strong style={{ color: '#f59e0b' }}>SMS GATEWAY · NOT CONFIGURED</strong> — Carrier SMS credentials are not provisioned in backend configuration. No synthetic &quot;SMS SENT&quot; confirmations are permitted.
              </div>

              <div className="officer-form-actions">
                <button
                  type="button"
                  className="officer-btn-broadcast font-mono"
                  disabled={alertSubmitting}
                  onClick={handleBroadcastAlert}
                >
                  {alertSubmitting ? 'DISPATCHING…' : '⚡ TRANSMIT GEOFENCED BROADCAST'}
                </button>
                <button
                  type="button"
                  className={`officer-btn-siren font-mono ${sirenPlaying ? 'active' : ''}`}
                  onClick={toggleSirenSound}
                >
                  {sirenPlaying ? '■ STOP WEB SIREN' : '▶ TEST WEB SIREN AUDIO'}
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: OSINT PUBLIC SCANNER */}
          {activeTab === 'osint_intel' && (
            <div className="officer-osint-view">
              <div className="officer-section-hdr">
                <span className="font-mono">OPEN SOURCE INTELLIGENCE (GDACS + NEWS + WEATHER)</span>
                <button
                  type="button"
                  className="officer-refresh-btn font-mono"
                  disabled={osintScanning}
                  onClick={handleTriggerScan}
                >
                  {osintScanning ? 'Scanning Feeds…' : '⚡ Trigger Live Scan'}
                </button>
              </div>

              <div className="officer-osint-disclaimer">
                <strong>Decision-Support Notice:</strong> OSINT reports represent publicly indexed indicators
                cross-referenced with localized Open-Meteo precipitation signals. Not certified ground truth.
              </div>

              {osintLoading && (
                <div className="officer-loading font-mono">Scanning global disaster feeds…</div>
              )}

              {!osintLoading && osintLeads.length === 0 && (
                <div className="officer-empty font-mono">
                  NO ACTIVE PUBLIC-SOURCE SIGNAL. Scanned public disaster feeds (GDACS & regional news) — no qualifying hazard signals detected in corridor.
                </div>
              )}

              {!osintLoading && osintLeads.length > 0 && (
                <div className="officer-osint-list">
                  {osintLeads.map((lead, idx) => (
                    <div key={lead.area + idx} className="officer-osint-card">
                      <div className="officer-osint-card-top">
                        <span className="officer-osint-source font-mono">{lead.source}</span>
                        <span className="officer-osint-date font-mono">{lead.updated_at}</span>
                      </div>

                      <h4 className="officer-osint-title">{lead.area} — {lead.hazard}</h4>
                      <p className="officer-osint-summary">{lead.analysis_note}</p>

                      <div className="officer-osint-grid font-mono">
                        <div>
                          <span className="osint-k">HAZARD:</span>{' '}
                          <span className="osint-v">{lead.hazard}</span>
                        </div>
                        <div>
                          <span className="osint-k">CONFIDENCE:</span>{' '}
                          <span className="osint-v">{lead.confidence}</span>
                        </div>
                        <div>
                          <span className="osint-k">RAINFALL 24h:</span>{' '}
                          <span className="osint-v">{lead.rainfall_24h_mm} mm</span>
                        </div>
                        <div>
                          <span className="osint-k">RECOMMENDATION:</span>{' '}
                          <span className="osint-v osint-rec">{lead.recommended_action}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
