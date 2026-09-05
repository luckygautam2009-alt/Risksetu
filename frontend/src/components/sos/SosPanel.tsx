/**
 * SosPanel — compact floating emergency SOS confirmation and status panel.
 *
 * Flow:
 *   confirm → (submit) → done | error
 *
 * Uses backend POST /api/v1/sos with real selected coordinates.
 * Includes direct shortcuts for Call 112 / Call 108 emergency dispatch.
 * Shows honest shelter status and offline queue status if disconnected.
 * Phase 2: Evidence photo attachment with identity verification guard.
 */
import { useState, useEffect, useRef } from 'react';
import { useMapContext } from '../../context/MapContext';
import { fetchNearbyShelters, uploadEvidence } from '../../services/api';
import type { SheltersResponse, EvidenceUploadResponse } from '../../services/api';
import { t } from '../../utils/i18n';
import './SosPanel.css';

interface Props {
  onClose: () => void;
}

const RISK_COLOR: Record<string, string> = {
  CRITICAL: '#8e1c2e',
  HIGH: '#c24d2c',
  MODERATE: '#b0821e',
  LOW: '#3b7a57',
};

export function SosPanel({ onClose }: Props) {
  const {
    evalCoords,
    selectedHazard,
    liveRisk,
    sosState,
    closeSosPanel,
    submitSos,
    language,
    identityStatus,
    openIdentityModal,
  } = useMapContext();

  const [desc, setDesc] = useState('');
  const [severity, setSeverity] = useState<'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'>('HIGH');
  const [shelters, setShelters] = useState<SheltersResponse['data'] | null>(null);
  const [sheltersLoading, setSheltersLoading] = useState(false);

  // Evidence attachment state
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidencePreview, setEvidencePreview] = useState<string | null>(null);
  const [evidenceUploading, setEvidenceUploading] = useState(false);
  const [evidenceResult, setEvidenceResult] = useState<EvidenceUploadResponse['data'] | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isVerified = identityStatus?.is_verified ?? false;

  const handleEvidenceSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setEvidenceFile(file);
    setEvidenceError(null);
    setEvidenceResult(null);
    // Create preview URL
    const url = URL.createObjectURL(file);
    setEvidencePreview(url);
  };

  const handleEvidenceUpload = async () => {
    if (!evidenceFile) return;
    setEvidenceUploading(true);
    setEvidenceError(null);
    try {
      const res = await uploadEvidence(evidenceFile);
      setEvidenceResult(res.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Evidence upload failed.';
      setEvidenceError(msg);
    } finally {
      setEvidenceUploading(false);
    }
  };

  const clearEvidence = () => {
    setEvidenceFile(null);
    setEvidencePreview(null);
    setEvidenceResult(null);
    setEvidenceError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Cleanup preview URL on unmount
  useEffect(() => {
    return () => {
      if (evidencePreview) URL.revokeObjectURL(evidencePreview);
    };
  }, [evidencePreview]);

  const locationName = selectedHazard?.location
    ?? (evalCoords ? `${evalCoords.lat.toFixed(4)}°N, ${evalCoords.lon.toFixed(4)}°E` : null);

  const noLocation = !evalCoords && !selectedHazard;

  // Load shelter data after SOS is done
  useEffect(() => {
    if (sosState.step !== 'done' || !evalCoords) return;
    setSheltersLoading(true);
    fetchNearbyShelters(evalCoords.lat, evalCoords.lon, 20000)
      .then((res) => setShelters(res.data))
      .catch(() => setShelters(null))
      .finally(() => setSheltersLoading(false));
  }, [sosState.step, evalCoords]);

  // Escape to close
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  const handleClose = () => { closeSosPanel(); onClose(); };

  const riskLevel = liveRisk.data?.risk.level ?? null;
  const riskScore = liveRisk.data?.risk.score ?? null;
  const riskConf = liveRisk.data?.risk.confidence ?? null;

  return (
    <div className="sos-panel" role="dialog" aria-modal="true" aria-label="SOS Emergency panel">
      {/* ── Header ── */}
      <div className="sos-panel__header">
        <div className="sos-panel__title-group">
          <span className="sos-panel__sos-badge font-mono">SOS</span>
          <span className="sos-panel__title font-mono">{t(language, 'emergencyReport')}</span>
        </div>
        <button
          type="button"
          className="sos-panel__close"
          onClick={handleClose}
          aria-label="Close SOS panel"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="sos-panel__body">

        {/* ── Emergency Dispatch Quick Dial (Call 112 / Call 108) ── */}
        <div className="sos-panel__direct-dial">
          <div className="sos-panel__dial-title font-mono">IMMEDIATE EMERGENCY CONTACTS</div>
          <div className="sos-panel__dial-buttons">
            <a href="tel:112" className="sos-panel__dial-btn sos-panel__dial-112">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
              <span>{t(language, 'call112')}</span>
            </a>
            <a href="tel:108" className="sos-panel__dial-btn sos-panel__dial-108">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
              <span>{t(language, 'call108')}</span>
            </a>
          </div>
        </div>

        {/* ── Step: confirm ── */}
        {(sosState.step === 'confirm' || sosState.step === 'error') && (
          <>
            <p className="sos-panel__prompt">
              Send an emergency location report to the system?
            </p>

            {/* Location */}
            <div className="sos-panel__location-box">
              <div className="sos-panel__loc-row">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" />
                </svg>
                <span className="sos-panel__loc-name">
                  {noLocation ? 'No location selected — select a location first.' : locationName}
                </span>
              </div>
              {evalCoords && (
                <div className="sos-panel__coords font-mono">
                  {evalCoords.lat.toFixed(5)}°N · {evalCoords.lon.toFixed(5)}°E
                </div>
              )}
            </div>

            {/* Current risk context */}
            {riskLevel && (
              <div
                className="sos-panel__risk-ctx"
                style={{ borderLeftColor: RISK_COLOR[riskLevel] ?? '#64748b' }}
              >
                <span className="sos-panel__risk-label font-mono">CURRENT RISK</span>
                <div className="sos-panel__risk-row">
                  <span
                    className="sos-panel__risk-level font-mono"
                    style={{ color: RISK_COLOR[riskLevel] ?? '#64748b' }}
                  >
                    {riskLevel}
                  </span>
                  {riskScore != null && (
                    <span className="sos-panel__risk-score font-mono">
                      {riskScore.toFixed(1)} / 100
                    </span>
                  )}
                  {riskConf != null && (
                    <span className="sos-panel__risk-conf">
                      Confidence {riskConf.toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Severity */}
            <div className="sos-panel__field">
              <label className="sos-panel__field-label font-mono" htmlFor="sos-sev">
                SEVERITY
              </label>
              <select
                id="sos-sev"
                className="sos-panel__select font-mono"
                value={severity}
                onChange={(e) => setSeverity(e.target.value as typeof severity)}
              >
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>

            {/* Description */}
            <div className="sos-panel__field">
              <label className="sos-panel__field-label font-mono" htmlFor="sos-desc">
                DESCRIPTION (optional)
              </label>
              <textarea
                id="sos-desc"
                className="sos-panel__textarea"
                rows={2}
                maxLength={500}
                placeholder="Describe the emergency…"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
              />
            </div>

            {/* ── Evidence Photo Attachment (Phase 2) ── */}
            <div className="sos-panel__field">
              <label className="sos-panel__field-label font-mono">
                COMMUNITY EVIDENCE · TRIAGE (optional)
              </label>
              <div style={{ fontSize: '9px', color: '#94a3b8', marginBottom: '6px' }}>
                Image does not prove hazard occurrence automatically. Evaluated via officer triage.
              </div>

              {!isVerified ? (
                <div className="sos-panel__verify-guard">
                  <div className="sos-panel__verify-guard-text">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    </svg>
                    <span>Identity verification required to attach evidence</span>
                  </div>
                  <button
                    type="button"
                    className="sos-panel__verify-btn font-mono"
                    onClick={openIdentityModal}
                  >
                    VERIFY IDENTITY
                  </button>
                </div>
              ) : (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleEvidenceSelect}
                    style={{ display: 'none' }}
                    id="sos-evidence-file"
                  />

                  {!evidenceFile && !evidenceResult && (
                    <button
                      type="button"
                      className="sos-panel__evidence-select font-mono"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                        <circle cx="8.5" cy="8.5" r="1.5" />
                        <polyline points="21 15 16 10 5 21" />
                      </svg>
                      ATTACH PHOTO EVIDENCE
                    </button>
                  )}

                  {evidenceFile && !evidenceResult && (
                    <div className="sos-panel__evidence-preview">
                      {evidencePreview && (
                        <img
                          src={evidencePreview}
                          alt="Evidence preview"
                          className="sos-panel__evidence-thumb"
                        />
                      )}
                      <div className="sos-panel__evidence-info">
                        <span className="font-mono" style={{ fontSize: '10px' }}>
                          {evidenceFile.name} ({(evidenceFile.size / 1024).toFixed(0)} KB)
                        </span>
                        <div className="sos-panel__evidence-actions">
                          <button
                            type="button"
                            className="sos-panel__evidence-upload-btn font-mono"
                            onClick={handleEvidenceUpload}
                            disabled={evidenceUploading}
                          >
                            {evidenceUploading ? 'UPLOADING…' : 'UPLOAD & VERIFY'}
                          </button>
                          <button
                            type="button"
                            className="sos-panel__evidence-clear font-mono"
                            onClick={clearEvidence}
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {evidenceResult && (
                    <div className="sos-panel__evidence-confirmed">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      <div className="sos-panel__evidence-confirmed-info font-mono">
                        <div>EVIDENCE UPLOADED</div>
                        <div style={{ fontSize: '9px', color: '#94a3b8' }}>
                          SHA256: {evidenceResult.sha256_checksum?.slice(0, 16)}…
                        </div>
                        <div style={{ fontSize: '9px', color: '#94a3b8' }}>
                          ID: {evidenceResult.evidence_id?.slice(0, 12)}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="sos-panel__evidence-clear font-mono"
                        onClick={clearEvidence}
                        title="Remove and reselect"
                      >
                        ✕
                      </button>
                    </div>
                  )}

                  {evidenceError && (
                    <div className="sos-panel__error" role="alert" style={{ marginTop: '4px' }}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                      </svg>
                      {evidenceError}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Error */}
            {sosState.step === 'error' && (
              <div className="sos-panel__error" role="alert">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                {sosState.error}
              </div>
            )}

            {/* Actions */}
            <div className="sos-panel__actions">
              <button
                type="button"
                className="sos-panel__btn-send"
                disabled={noLocation}
                onClick={() => submitSos(desc || undefined, severity)}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                </svg>
                SEND SOS
              </button>
              <button type="button" className="sos-panel__btn-cancel" onClick={handleClose}>
                CANCEL
              </button>
            </div>
          </>
        )}

        {/* ── Step: submitting ── */}
        {sosState.step === 'submitting' && (
          <div className="sos-panel__submitting">
            <span className="sos-panel__spinner" aria-hidden="true" />
            <span>Submitting emergency report…</span>
          </div>
        )}

        {/* ── Step: done ── */}
        {sosState.step === 'done' && (
          <>
            {/* Success header */}
            <div className="sos-panel__success">
              <div className="sos-panel__success-icon" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3b7a57" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <div>
                <div className="sos-panel__success-title font-mono">
                  {sosState.isOfflineQueued ? 'SOS QUEUED ON THIS DEVICE' : 'SOS SENT'}
                </div>
                {sosState.sosId && (
                  <div className="sos-panel__success-id font-mono">
                    {sosState.isOfflineQueued ? `LOCAL QUEUE ID: ${sosState.sosId.slice(0, 16)}` : `DB ID: ${sosState.sosId.slice(0, 16)}`}
                  </div>
                )}
              </div>
            </div>

            {/* Offline notice if queued */}
            {sosState.isOfflineQueued && (
              <div className="sos-panel__offline-banner font-mono">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 1l22 22M16.72 11.06A10.94 10.94 0 0 1 19 12.55M5 12.55a10.94 10.94 0 0 1 5.17-2.39M10.71 5.05A16 16 0 0 1 22.58 9M1.42 9a15.91 15.91 0 0 1 4.7-2.88M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01" />
                </svg>
                <span>Device is offline. SOS queued on this device in local storage. Not yet received by emergency responders. Will submit to server automatically once connectivity is restored.</span>
              </div>
            )}

            {/* Status */}
            <div className="sos-panel__status-row font-mono">
              <span className="sos-panel__status-label">STATUS</span>
              <span className="sos-panel__status-val sos-panel__status-active">
                {sosState.isOfflineQueued ? 'QUEUED ON LOCAL DEVICE (PENDING BACKEND SYNC)' : 'SERVER RECEIVED (POSTGRESQL RECORDED)'}
              </span>
            </div>

            {/* Risk context from backend */}
            {sosState.riskLevel && (
              <div
                className="sos-panel__risk-ctx"
                style={{ borderLeftColor: RISK_COLOR[sosState.riskLevel] ?? '#64748b' }}
              >
                <span className="sos-panel__risk-label font-mono">RISK SNAPSHOT AT SOS CREATION</span>
                <div className="sos-panel__risk-row">
                  <span
                    className="sos-panel__risk-level font-mono"
                    style={{ color: RISK_COLOR[sosState.riskLevel] ?? '#64748b' }}
                  >
                    {sosState.riskLevel}
                  </span>
                  {riskScore != null && (
                    <span className="sos-panel__risk-score font-mono">{riskScore.toFixed(1)} / 100</span>
                  )}
                  {liveRisk.data?.risk?.confidence != null && (
                    <span className="sos-panel__risk-score font-mono" style={{ color: '#94a3b8' }}>
                      ({liveRisk.data.risk.confidence}% CONF.)
                    </span>
                  )}
                </div>
                {liveRisk.data?.weather && (
                  <div className="font-mono" style={{ fontSize: '10px', color: '#94a3b8', marginTop: '4px' }}>
                    WEATHER: {liveRisk.data.weather.precipitation_mm ?? 0}mm rain · {liveRisk.data.weather.provider || 'Live Weather Provider'}
                  </div>
                )}
                <div className="font-mono" style={{ fontSize: '9px', color: '#64748b', marginTop: '3px' }}>
                  SNAPSHOT TIME: {new Date().toLocaleTimeString()} · {locationName}
                </div>
              </div>
            )}

            {/* Response Guidance / Recommendations */}
            {liveRisk.data?.recommended_actions && liveRisk.data.recommended_actions.length > 0 && (
              <div className="sos-panel__guidance">
                <div className="sos-panel__guidance-label font-mono">RESPONSE GUIDANCE</div>
                {liveRisk.data.recommended_actions.slice(0, 3).map((a) => (
                  <div key={a.action_id} className="sos-panel__guidance-item">
                    <span className="sos-panel__guidance-dot" aria-hidden="true" />
                    {a.description}
                  </div>
                ))}
              </div>
            )}

            {/* Shelter availability */}
            <div className="sos-panel__shelters">
              <div className="sos-panel__guidance-label font-mono">NEARBY SHELTERS</div>
              {sheltersLoading && (
                <div className="sos-panel__submitting" style={{ padding: '6px 0' }}>
                  <span className="sos-panel__spinner" aria-hidden="true" />
                  <span>Checking shelter database…</span>
                </div>
              )}
              {!sheltersLoading && (shelters?.data_status === 'unavailable' || !shelters) && (
                <div className="sos-panel__shelter-unavail">
                  <span className="sos-panel__unavail-tag font-mono">VERIFIED SHELTER DATA UNAVAILABLE</span>
                  <p>Authoritative NDMA / State Disaster Management shelter dataset is not yet loaded into PostgreSQL. No unverified or synthetic shelter records are generated.</p>
                </div>
              )}
              {!sheltersLoading && shelters?.data_status === 'available' && (
                <div className="sos-panel__shelter-list">
                  {shelters.shelters.slice(0, 3).map((s) => (
                    <div key={s.id} className="sos-panel__shelter-item">
                      <span className="sos-panel__shelter-name">{s.name}</span>
                      <span className="sos-panel__shelter-dist font-mono">
                        {(s.distance_m / 1000).toFixed(1)} km
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {!sheltersLoading && shelters?.data_status === 'empty' && (
                <div className="sos-panel__shelter-unavail">
                  <p>No shelters found within 20 km of this location.</p>
                </div>
              )}
            </div>

            <button
              type="button"
              className="sos-panel__btn-cancel"
              style={{ marginTop: '8px' }}
              onClick={handleClose}
            >
              CLOSE
            </button>
          </>
        )}

        {/* ── Official Legal Disclaimer ── */}
        <div className="sos-panel__disclaimer">
          {t(language, 'emergencyDisclaimer')}
        </div>

      </div>
    </div>
  );
}
