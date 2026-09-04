import { useMapContext } from '../../context/MapContext';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import './GroundObservationPanel.css';

export function GroundObservationPanel() {
  const { selectedObservation, selectObservation, selectHazard } = useMapContext();

  if (!selectedObservation) return null;

  return (
    <div className="obs-panel" role="region" aria-label="Field Ground Observation Intelligence">
      {/* ── HEADER ── */}
      <div className="obs-panel__header">
        <div className="obs-panel__header-meta">
          <div className="obs-panel__tag font-mono">
            <span className="obs-panel__tag-dot" aria-hidden="true" />
            FIELD OBSERVATION
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

      {/* ── CORE INTELLIGENCE METRICS (Exact Prompt Specifications) ── */}
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
          <span className="obs-card__sub">{selectedObservation.corroborationCount} Independent Reports</span>
        </div>
      </div>

      {/* ── CRITICAL SYSTEM DISCLAIMER (Never call trust score probability of truth) ── */}
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
            <span>STATUS: {selectedObservation.status}</span>
          </div>
        </div>
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
