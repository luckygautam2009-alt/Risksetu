import { useState } from 'react';
import { submitGroundReport, uploadEvidence, ApiError } from '../../services/api';
import { queueReport } from '../../services/offline';
import { useMapContext } from '../../context/MapContext';
import './ReportIncidentModal.css';

interface Props {
  onClose: () => void;
}

const REPORT_TYPES = [
  { id: 'LANDSLIDE', label: 'Landslide / Slope Failure' },
  { id: 'SLOPE_CRACK', label: 'Slope Surface Crack' },
  { id: 'ROAD_BLOCKAGE', label: 'Blocked Road / Debris' },
  { id: 'FLASH_FLOOD', label: 'Flash Flood / Water Inundation' },
  { id: 'HEAVY_RAIN', label: 'Intense Cloudburst / Heavy Rain' },
  { id: 'FALLING_ROCKS', label: 'Falling Rocks / Rolling Stones' },
  { id: 'OTHER', label: 'Other Hazardous Observation' },
];

export function ReportIncidentModal({ onClose }: Props) {
  const { evalCoords, selectedHazard, identityStatus, openIdentityModal } = useMapContext();

  const initialLat = evalCoords?.lat ?? selectedHazard?.latitude ?? 30.2936;
  const initialLon = evalCoords?.lon ?? selectedHazard?.longitude ?? 79.5603;

  const [reportType, setReportType] = useState('LANDSLIDE');
  const [severity, setSeverity] = useState<'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'>('HIGH');
  const [latitude, setLatitude] = useState(initialLat);
  const [longitude, setLongitude] = useState(initialLon);
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [gpsStatus, setGpsStatus] = useState<string | null>(null);

  // Evidence state
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [uploadingEvidence, setUploadingEvidence] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [evidenceFileName, setEvidenceFileName] = useState<string | null>(null);

  const isVerified = identityStatus?.is_verified ?? false;

  const handleGps = () => {
    if (!navigator.geolocation) {
      setGpsStatus('Geolocation not supported on this device.');
      return;
    }
    setGpsStatus('Acquiring GPS fix…');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(Number(pos.coords.latitude.toFixed(5)));
        setLongitude(Number(pos.coords.longitude.toFixed(5)));
        setGpsStatus('GPS coordinates updated.');
      },
      () => {
        setGpsStatus('GPS permission denied or unavailable.');
      },
      { timeout: 8000 }
    );
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setEvidenceError(null);
    setUploadingEvidence(true);

    try {
      const res = await uploadEvidence(file);
      setEvidenceId(res.data.evidence_id);
      setEvidenceFileName(file.name);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          setEvidenceError('Identity verification is required before uploading photographic evidence.');
        } else {
          setEvidenceError(`Upload failed (${err.status}): ${err.body}`);
        }
      } else {
        setEvidenceError('Failed to upload image evidence.');
      }
    } finally {
      setUploadingEvidence(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);

    const nowIso = new Date().toISOString();

    if (!navigator.onLine) {
      try {
        await queueReport({
          id: `rep-${crypto.randomUUID()}`,
          reportType,
          description,
          severity,
          latitude,
          longitude,
          observedAt: nowIso,
          createdAt: nowIso,
          status: 'QUEUED_OFFLINE',
        });
        setSuccess('Report queued on this device. It will automatically transmit to RiskSetu responders when internet connectivity returns.');
      } catch (err: any) {
        setError(err?.message || 'Failed to save offline report.');
      } finally {
        setBusy(false);
      }
      return;
    }

    try {
      const res = await submitGroundReport({
        report_type: reportType,
        description,
        latitude,
        longitude,
        observed_at: nowIso,
        evidence_id: evidenceId ?? undefined,
      });

      setSuccess(
        `Observation recorded with Trust Score ${res.data.trust.trust_score.toFixed(1)}/100 (${res.data.trust.trust_class}). ${res.data.explanation.summary}`
      );
    } catch (err: any) {
      setError(err?.message || 'Submission error. Check backend connection or try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="report-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="report-modal-title">
      <div className="report-modal">
        <div className="report-modal__header">
          <div className="report-modal__title-group">
            <span className="report-modal__badge font-mono">FIELD OBSERVATION</span>
            <h2 id="report-modal-title" className="report-modal__title font-mono">REPORT AN INCIDENT</h2>
          </div>
          <button type="button" className="report-modal__close" onClick={onClose} aria-label="Close dialog">
            ✕
          </button>
        </div>

        <div className="report-modal__body">
          <p className="report-modal__disclaimer">
            Report from a safe location. Do not approach an unstable slope or moving water to collect evidence.
          </p>

          {success ? (
            <div className="report-modal__success-box">
              <div className="report-modal__success-icon">✓</div>
              <p className="report-modal__success-text">{success}</p>
              <button type="button" className="report-modal__btn-primary" onClick={onClose}>
                DONE
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="report-modal__form">
              <div className="report-modal__grid-2">
                <div className="report-modal__field">
                  <label className="report-modal__label font-mono" htmlFor="rep-type">INCIDENT TYPE</label>
                  <select
                    id="rep-type"
                    className="report-modal__select"
                    value={reportType}
                    onChange={(e) => setReportType(e.target.value)}
                  >
                    {REPORT_TYPES.map((t) => (
                      <option key={t.id} value={t.id}>{t.label}</option>
                    ))}
                  </select>
                </div>

                <div className="report-modal__field">
                  <label className="report-modal__label font-mono" htmlFor="rep-sev">OBSERVED SEVERITY</label>
                  <select
                    id="rep-sev"
                    className="report-modal__select font-mono"
                    value={severity}
                    onChange={(e) => setSeverity(e.target.value as any)}
                  >
                    <option value="LOW">LOW — Minor cracking / slight trickle</option>
                    <option value="MODERATE">MODERATE — Partial lane blockage</option>
                    <option value="HIGH">HIGH — Full corridor block / active slide</option>
                    <option value="CRITICAL">CRITICAL — Ongoing failure / life safety risk</option>
                  </select>
                </div>
              </div>

              <div className="report-modal__coords-box">
                <div className="report-modal__coords-head">
                  <span className="report-modal__label font-mono">OBSERVATION COORDINATES</span>
                  <button type="button" className="report-modal__btn-gps" onClick={handleGps}>
                    Use Current GPS
                  </button>
                </div>
                <div className="report-modal__coords-row">
                  <input
                    type="number"
                    step="0.0001"
                    className="report-modal__input font-mono"
                    value={latitude}
                    onChange={(e) => setLatitude(parseFloat(e.target.value) || 0)}
                    aria-label="Latitude"
                  />
                  <input
                    type="number"
                    step="0.0001"
                    className="report-modal__input font-mono"
                    value={longitude}
                    onChange={(e) => setLongitude(parseFloat(e.target.value) || 0)}
                    aria-label="Longitude"
                  />
                </div>
                {gpsStatus && <p className="report-modal__gps-status font-mono">{gpsStatus}</p>}
              </div>

              <div className="report-modal__field">
                <label className="report-modal__label font-mono" htmlFor="rep-desc">WHAT DID YOU OBSERVE?</label>
                <textarea
                  id="rep-desc"
                  className="report-modal__textarea"
                  rows={3}
                  required
                  minLength={8}
                  maxLength={1000}
                  placeholder="Describe slope movement, nearby milestones/culverts, weather conditions, or blocked traffic…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              {/* Evidence Section */}
              <div className="report-modal__field" style={{ marginTop: '0.75rem' }}>
                <label className="report-modal__label font-mono">
                  PHOTOGRAPHIC EVIDENCE (OPTIONAL)
                </label>
                {isVerified ? (
                  <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.85rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileChange}
                      disabled={uploadingEvidence}
                      style={{ color: '#cbd5e1', fontSize: '0.85rem' }}
                    />
                    {uploadingEvidence && <p style={{ fontSize: '0.8rem', color: '#60a5fa', marginTop: '0.4rem' }}>⏳ Verifying image integrity (Pillow/Magic bytes & SHA256)...</p>}
                    {evidenceId && (
                      <p style={{ fontSize: '0.8rem', color: '#34d399', marginTop: '0.4rem' }}>
                        ✅ Evidence verified & attached: {evidenceFileName} (ID: {evidenceId.slice(0, 8)}...)
                      </p>
                    )}
                    {evidenceError && (
                      <p style={{ fontSize: '0.8rem', color: '#fca5a5', marginTop: '0.4rem' }}>
                        ⚠️ {evidenceError}
                      </p>
                    )}
                  </div>
                ) : (
                  <div style={{ background: 'rgba(245, 158, 11, 0.1)', padding: '0.85rem', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.3)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ fontSize: '0.825rem', color: '#fbbf24' }}>
                      🔒 Verified identity required to attach photographic evidence.
                    </div>
                    <button
                      type="button"
                      onClick={openIdentityModal}
                      style={{ background: '#f59e0b', color: '#000000', border: 'none', padding: '0.35rem 0.75rem', borderRadius: '6px', fontSize: '0.775rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                    >
                      Verify Identity
                    </button>
                  </div>
                )}
              </div>

              {error && (
                <div className="report-modal__error-box" role="alert">
                  ⚠ {error}
                </div>
              )}

              <div className="report-modal__actions">
                <button
                  type="submit"
                  className="report-modal__btn-primary"
                  disabled={busy || description.trim().length < 8}
                >
                  {busy ? 'SUBMITTING…' : !navigator.onLine ? 'QUEUE REPORT (OFFLINE)' : 'SUBMIT REPORT'}
                </button>
                <button type="button" className="report-modal__btn-cancel" onClick={onClose}>
                  CANCEL
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
