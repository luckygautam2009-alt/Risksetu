import { useState } from 'react';
import { useMapContext } from '../../context/MapContext';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import { moderateGroundReportStatus } from '../../services/api';
import { t } from '../../utils/i18n';
import './GroundObservationPanel.css';

export function GroundObservationPanel() {
  const {
    selectedObservation,
    selectObservation,
    selectHazard,
    userRole,
    language,
  } = useMapContext();

  const [communityVote, setCommunityVote] = useState<'confirmed' | 'denied' | 'unsure' | null>(null);
  const [moderationState, setModerationState] = useState<{
    status: 'idle' | 'loading' | 'success' | 'error';
    newStatus?: string;
    errorMsg?: string;
  }>({ status: 'idle' });

  if (!selectedObservation) return null;

  const handleCommunityVote = (type: 'confirmed' | 'denied' | 'unsure') => {
    setCommunityVote(type);
  };

  const handleModeration = async (decision: 'ACCEPTED' | 'REJECTED' | 'REVIEW_REQUIRED') => {
    setModerationState({ status: 'loading' });
    try {
      await moderateGroundReportStatus(selectedObservation.id, decision, `Moderated by ${userRole}`);
      setModerationState({ status: 'success', newStatus: decision });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Moderation failed';
      setModerationState({ status: 'error', errorMsg: msg });
    }
  };

  const isOfficer = userRole === 'Incident Commander' || userRole === 'Disaster Response Lead';

  return (
    <div className="obs-panel" role="region" aria-label="Field Ground Observation Intelligence">
      {/* ── HEADER ── */}
      <div className="obs-panel__header">
        <div className="obs-panel__header-meta">
          <div className="obs-panel__tag font-mono">
            <span className="obs-panel__tag-dot" aria-hidden="true" />
            {selectedObservation.status === 'VERIFIED' ? 'OFFICIALLY VERIFIED REPORT' : 'COMMUNITY SIGNAL · TRIAGE'}
          </div>
          <h2 className="obs-panel__location font-mono">{selectedObservation.location.toUpperCase()}</h2>
        </div>

        <IconButton
          label="Close observation"
          size="xs"
          variant="ghost"
          onClick={() => selectObservation(null)}
          icon={
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          }
        />
      </div>

      {/* ── CORE INTELLIGENCE METRICS ── */}
      <div className="obs-panel__grid">
        {/* Trust Score */}
        <div className="obs-card">
          <span className="obs-card__label font-mono">Trust Score</span>
          <span className="obs-card__val font-mono">{selectedObservation.trustScore.toFixed(2)}</span>
          <span className="obs-card__sub">Multi-Factor Heuristic</span>
        </div>

        {/* Confidence */}
        <div className="obs-card">
          <span className="obs-card__label font-mono">Confidence</span>
          <span className="obs-card__val obs-card__val--highlight font-mono">
            {selectedObservation.confidence}
          </span>
          <span className="obs-card__sub">Spatial Plausibility</span>
        </div>

        {/* Risk Influence */}
        <div className="obs-card">
          <span className="obs-card__label font-mono">Risk Influence</span>
          <span className="obs-card__val obs-card__val--eligible font-mono">
            {selectedObservation.riskInfluence}
          </span>
          <span className="obs-card__sub">Calibrated Weighting</span>
        </div>

        {/* Corroboration */}
        <div className="obs-card">
          <span className="obs-card__label font-mono">Corroboration</span>
          <span className="obs-card__val font-mono">
            {selectedObservation.corroboration}
          </span>
          <span className="obs-card__sub">{selectedObservation.corroborationCount} Reports</span>
        </div>
      </div>

      {/* ── CRITICAL SYSTEM DISCLAIMER ── */}
      <div className="obs-panel__disclaimer">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>
          <strong>Algorithmic Heuristic:</strong> Trust score reflects evaluated source fidelity,
          corroboration clustering, and temporal freshness. It does not denote mathematical probability of truth.
        </span>
      </div>

      {/* ── FIELD REPORT CONTENT ── */}
      <div className="obs-panel__body">
        <div className="obs-panel__report">
          <div className="obs-panel__report-top">
            <Badge variant="source" size="sm">
              {selectedObservation.category.replace('_', ' ')}
            </Badge>
            <span className="obs-panel__time font-mono">Logged {selectedObservation.reportedAt}</span>
          </div>

          <h3 className="obs-panel__report-title">{selectedObservation.title}</h3>
          <p className="obs-panel__report-desc">{selectedObservation.description}</p>

          <div className="obs-panel__reporter-box font-mono">
            <span>SOURCE: {selectedObservation.reporterType.toUpperCase()}</span>
            <span>STATUS: {moderationState.newStatus ?? selectedObservation.status}</span>
          </div>
        </div>

        {/* ── COMMUNITY SIGNAL (500m PROXIMITY PEER VERIFICATION) ── */}
        <div className="obs-panel__community-box">
          <div className="obs-panel__community-header">
            <span className="obs-panel__community-title font-mono">{t(language, 'communitySignal')} (500m)</span>
            <span className="obs-panel__community-badge font-mono">NON-AUTHORITATIVE</span>
          </div>
          <p className="obs-panel__community-hint">
            Are you currently within visual distance of this hazard location?
          </p>
          <div className="obs-panel__community-actions">
            <button
              type="button"
              className={`obs-panel__comm-btn ${communityVote === 'confirmed' ? 'active confirm' : ''}`}
              onClick={() => handleCommunityVote('confirmed')}
            >
              ✓ {t(language, 'confirmObservation')}
            </button>
            <button
              type="button"
              className={`obs-panel__comm-btn ${communityVote === 'denied' ? 'active deny' : ''}`}
              onClick={() => handleCommunityVote('denied')}
            >
              ✗ {t(language, 'disputeObservation')}
            </button>
            <button
              type="button"
              className={`obs-panel__comm-btn ${communityVote === 'unsure' ? 'active unsure' : ''}`}
              onClick={() => handleCommunityVote('unsure')}
            >
              ? {t(language, 'unsureObservation')}
            </button>
          </div>
          {communityVote && (
            <div className="obs-panel__community-feedback font-mono">
              Signal recorded locally. Contributes to peer corroboration heuristic.
            </div>
          )}
        </div>

        {/* ── OFFICIAL OFFICER MODERATION ── */}
        {isOfficer && (
          <div className="obs-panel__moderation-box">
            <div className="obs-panel__moderation-header">
              <span className="obs-panel__moderation-title font-mono">OFFICER MODERATION DISPATCH</span>
              <span className="obs-panel__moderation-role font-mono">{userRole.toUpperCase()}</span>
            </div>
            <div className="obs-panel__moderation-actions">
              <button
                type="button"
                className="obs-panel__mod-btn obs-panel__mod-btn--verify font-mono"
                disabled={moderationState.status === 'loading'}
                onClick={() => handleModeration('ACCEPTED')}
              >
                VERIFY
              </button>
              <button
                type="button"
                className="obs-panel__mod-btn obs-panel__mod-btn--reject font-mono"
                disabled={moderationState.status === 'loading'}
                onClick={() => handleModeration('REJECTED')}
              >
                REJECT
              </button>
              <button
                type="button"
                className="obs-panel__mod-btn obs-panel__mod-btn--review font-mono"
                disabled={moderationState.status === 'loading'}
                onClick={() => handleModeration('REVIEW_REQUIRED')}
              >
                REVIEW REQ.
              </button>
            </div>
            {moderationState.status === 'loading' && (
              <div className="obs-panel__mod-status font-mono">Processing moderation update…</div>
            )}
            {moderationState.status === 'success' && (
              <div className="obs-panel__mod-status obs-panel__mod-status--ok font-mono">
                Status updated to {moderationState.newStatus}
              </div>
            )}
            {moderationState.status === 'error' && (
              <div className="obs-panel__mod-status obs-panel__mod-status--err font-mono">
                {moderationState.errorMsg}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── ACTIONS ── */}
      <div className="obs-panel__footer">
        {selectedObservation.hazardId && (
          <button
            type="button"
            className="obs-panel__btn obs-panel__btn--primary"
            onClick={() => {
              if (selectedObservation.hazardId) {
                selectHazard(selectedObservation.hazardId);
              }
            }}
          >
            View Linked Hazard
          </button>
        )}
        <button
          type="button"
          className="obs-panel__btn obs-panel__btn--secondary"
          onClick={() => selectObservation(null)}
        >
          Dismiss Inspector
        </button>
      </div>
    </div>
  );
}
