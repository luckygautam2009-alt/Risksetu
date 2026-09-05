import { useMapContext } from '../../context/MapContext';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import './PriorityRankedList.css';

export function PriorityRankedList() {
  const {
    priorityList,
    selectedPriorityId,
    selectPriority,
    setWorkflowTab,
    selectedLocation,
    evaluateLocationPriority,
    priorityLoading,
    priorityError,
  } = useMapContext();

  const handleEvaluateCurrent = () => {
    if (selectedLocation) {
      evaluateLocationPriority(
        selectedLocation.latitude,
        selectedLocation.longitude,
        selectedLocation.name,
      );
    }
  };

  return (
    <div className="prio-panel" role="region" aria-label="Ranked Intervention Priority">
      {/* ── HEADER ── */}
      <div className="prio-panel__header">
        <div className="prio-panel__title-group">
          <div className="prio-panel__overline font-mono">
            <span className="prio-panel__dot" aria-hidden="true" />
            PART 1 · OPERATIONAL DECISION SUPPORT
          </div>
          <h2 className="prio-panel__heading">INTERVENTION PRIORITY</h2>
        </div>

        <IconButton
          label="Close priority panel"
          size="xs"
          variant="ghost"
          onClick={() => setWorkflowTab('risk')}
          icon={
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          }
        />
      </div>

      {/* ── THE CORE PRINCIPLE: RISK ≠ PRIORITY BANNER ── */}
      <div className="prio-panel__contrast-banner">
        <div className="prio-panel__contrast-title font-mono">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          OPERATIONAL PRINCIPLE: RISK ≠ PRIORITY
        </div>
        <p className="prio-panel__contrast-text">
          Intervention priority is determined by <strong>Risk (40%)</strong> + <strong>Isolation Impact (45%)</strong> + <strong>Urgency (15%)</strong>.
          A high-risk sector with redundant roads ranks <em>below</em> a moderate-risk sector where road collapse completely isolates communities.
        </p>

        {/* Contrast Mini Matrix */}
        <div className="prio-matrix">
          <div className="prio-matrix__cell">
            <span className="prio-matrix__label font-mono">SECTOR A</span>
            <span className="prio-matrix__stat">Risk 92 · Isolation LOW</span>
            <span className="prio-matrix__result prio-matrix__result--high font-mono">→ PRIORITY HIGH</span>
          </div>
          <div className="prio-matrix__vs font-mono">vs</div>
          <div className="prio-matrix__cell prio-matrix__cell--elevated">
            <span className="prio-matrix__label font-mono">SECTOR B</span>
            <span className="prio-matrix__stat">Risk 81 · Isolation CRITICAL</span>
            <span className="prio-matrix__result prio-matrix__result--critical font-mono">→ PRIORITY CRITICAL</span>
          </div>
        </div>
      </div>

      {/* ── INTERACTIVE EVALUATE TRIGGER BAR ── */}
      {selectedLocation && (
        <div className="prio-eval-bar">
          <button
            className="prio-eval-btn font-mono"
            onClick={handleEvaluateCurrent}
            disabled={priorityLoading}
          >
            {priorityLoading ? (
              <span>EVALUATING PRIORITY VIA BACKEND...</span>
            ) : (
              <span>⚡ EVALUATE PRIORITY: {selectedLocation.name ? selectedLocation.name.slice(0, 22) : 'SELECTED LOCATION'}</span>
            )}
          </button>
        </div>
      )}

      {priorityError && (
        <div className="prio-error-banner font-mono">
          ⚠ {priorityError}
        </div>
      )}

      {/* ── RANKED INTERVENTION LIST ── */}
      <div className="prio-panel__body">
        <div className="prio-panel__list-header font-mono">
          <span>RANKED INTERVENTION TARGETS ({priorityList.length})</span>
          <span>WEIGHTED FORMULA</span>
        </div>

        {priorityList.length === 0 ? (
          <div className="prio-empty-state">
            <div className="prio-empty-state__icon">📊</div>
            <div className="prio-empty-state__title font-mono">NO TARGETS EVALUATED YET</div>
            <p className="prio-empty-state__desc">
              Select any point or landslide on the map and click <strong>Evaluate Priority</strong> to calculate multi-criteria intervention priority via the certified backend engine.
            </p>
          </div>
        ) : (
          <div className="prio-list">
            {priorityList.map((item) => {
              const isSelected = selectedPriorityId === item.id;
              return (
                <div
                  key={item.id}
                  className={`prio-card ${isSelected ? 'prio-card--selected' : ''}`}
                  onClick={() => selectPriority(item.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      selectPriority(item.id);
                    }
                  }}
                >
                  <div className="prio-card__top">
                    <div className="prio-card__rank-group">
                      <span className="prio-card__rank font-mono">
                        {String(item.rank).padStart(2, '0')}
                      </span>
                      <div className="prio-card__name-block">
                        <span className="prio-card__name">{item.location}</span>
                        <span className="prio-card__sub">{item.subdivision}</span>
                      </div>
                    </div>

                    <Badge
                      variant="risk"
                      riskLevel={item.priorityLevel === 'CRITICAL' ? 'CRITICAL' : item.priorityLevel === 'HIGH' ? 'HIGH' : 'MODERATE'}
                      size="sm"
                      dot
                      pulse={item.priorityLevel === 'CRITICAL'}
                    >
                      {item.priorityLevel} PRIORITY
                    </Badge>
                  </div>

                  {/* Metric Strip */}
                  <div className="prio-card__metrics font-mono">
                    <div className="prio-card__metric">
                      <span className="prio-card__metric-label">Risk</span>
                      <span className="prio-card__metric-val">{item.riskScore.toFixed(1)}</span>
                    </div>
                    <div className="prio-card__metric-divider" aria-hidden="true">·</div>
                    <div className="prio-card__metric">
                      <span className="prio-card__metric-label">Isolation</span>
                      <span className={`prio-card__metric-val prio-card__metric-val--${item.isolationSeverity.toLowerCase()}`}>
                        +{item.isolationNodes} nodes
                      </span>
                    </div>
                    <div className="prio-card__metric-divider" aria-hidden="true">·</div>
                    <div className="prio-card__metric">
                      <span className="prio-card__metric-label">Score</span>
                      <span className="prio-card__metric-val prio-card__metric-val--score">
                        {item.priorityScore.toFixed(1)}
                      </span>
                    </div>
                  </div>

                  {/* Rationale & Contrast Note */}
                  <p className="prio-card__reason">
                    {item.contrastReason}
                  </p>

                  {/* Breakdown detail when selected */}
                  {isSelected && item.riskContribution !== undefined && (
                    <div className="prio-card__breakdown font-mono">
                      <div className="prio-card__breakdown-item">
                        <span>Risk 40%:</span> <strong>{item.riskContribution.toFixed(1)}</strong>
                      </div>
                      <div className="prio-card__breakdown-item">
                        <span>Impact 45%:</span> <strong>{(item.isolationContribution ?? 0).toFixed(1)}</strong>
                      </div>
                      <div className="prio-card__breakdown-item">
                        <span>Urgency 15%:</span> <strong>{(item.urgencyContribution ?? 0).toFixed(1)}</strong>
                      </div>
                    </div>
                  )}

                  {/* Limitations if present */}
                  {isSelected && item.limitations && item.limitations.length > 0 && (
                    <div className="prio-card__limits font-mono">
                      {item.limitations.map((lim, i) => (
                        <span key={i} className="prio-card__limit-tag">{lim}</span>
                      ))}
                    </div>
                  )}

                  {/* Corridor Link */}
                  {item.adjacentCorridor && (
                    <div className="prio-card__corridor font-mono">
                      <span>CORRIDOR: {item.adjacentCorridor}</span>
                      <span className="prio-card__jump">Inspect →</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── FOOTER: PROVENANCE & FORMULA ── */}
      <div className="prio-panel__footer font-mono">
        PRIORITY FORMULA: (Risk × 0.40) + (Impact × 0.45) + (Urgency × 0.15) · FASTAPI BACKEND
      </div>
    </div>
  );
}

