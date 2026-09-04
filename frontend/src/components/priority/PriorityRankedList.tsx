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
  } = useMapContext();

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

      {/* ── RANKED INTERVENTION LIST ── */}
      <div className="prio-panel__body">
        <div className="prio-panel__list-header font-mono">
          <span>RANKED INTERVENTION TARGETS ({priorityList.length})</span>
          <span>WEIGHTED FORMULA</span>
        </div>

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

                {/* Corridor Link */}
                <div className="prio-card__corridor font-mono">
                  <span>CORRIDOR: {item.adjacentCorridor}</span>
                  <span className="prio-card__jump">Inspect →</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
