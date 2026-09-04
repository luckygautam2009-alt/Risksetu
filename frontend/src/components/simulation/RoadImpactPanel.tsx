import { useEffect, useState } from 'react';
import { useMapContext } from '../../context/MapContext';
import { useAnimatedNumber } from '../../hooks/useAnimatedNumber';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import './RoadImpactPanel.css';

const SEQUENCE_STEPS = [
  { id: 'hazard', label: 'HAZARD', sub: 'Mass Inflow' },
  { id: 'failure', label: 'ROAD FAILURE', sub: 'Way Severed' },
  { id: 'disruption', label: 'NETWORK DISRUPTION', sub: 'Topological Split' },
  { id: 'isolation', label: 'ISOLATION', sub: '42 Nodes Cutoff' },
  { id: 'impact', label: 'IMPACT', sub: 'Critical Severity' },
] as const;

export function RoadImpactPanel() {
  const { simulationResult, resetSimulation, startSimulation, selectedRoad } = useMapContext();
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      setAnimated(false);
      requestAnimationFrame(() => setAnimated(true));
    });
    return () => cancelAnimationFrame(id);
  }, [simulationResult?.wayId]);

  const animatedNodes = useAnimatedNumber(simulationResult?.nodesAffected ?? 42, 600);
  const animatedBefore = useAnimatedNumber(simulationResult?.before.components ?? 18, 400);
  const animatedAfter = useAnimatedNumber(simulationResult?.after.components ?? 19, 500);

  if (!simulationResult) return null;

  return (
    <div className="impact-panel" role="region" aria-label="Road failure impact intelligence">
      {/* ── HEADER ── */}
      <div className="impact-panel__header">
        <div className="impact-panel__title-block">
          <div className="impact-panel__overline font-mono">
            <span className="impact-panel__pulse-dot" aria-hidden="true" />
            ROAD FAILURE
          </div>
          <h2 className="impact-panel__way font-mono">Way {simulationResult.wayId}</h2>
          <p className="impact-panel__corridor">{simulationResult.roadName}</p>
        </div>

        <IconButton
          label="Dismiss impact panel"
          size="xs"
          variant="ghost"
          onClick={resetSimulation}
          icon={
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          }
        />
      </div>

      {/* ── SEVERITY BANNER ── */}
      <div className={`impact-panel__banner impact-panel__banner--${simulationResult.isolationSeverity.toLowerCase()}`}>
        <div className="impact-panel__banner-left">
          <span className="impact-panel__banner-label font-mono">ISOLATION SEVERITY</span>
          <span className="impact-panel__banner-val font-mono">{simulationResult.isolationSeverity}</span>
        </div>
        <Badge variant="risk" riskLevel="CRITICAL" size="sm" dot pulse>
          TOPOLOGICAL BREACH
        </Badge>
      </div>

      {/* ── SCROLLABLE BODY ── */}
      <div className="impact-panel__body">
        {/* ── SEQUENCE VISUALIZER: HAZARD → FAILURE → DISRUPTION → ISOLATION → IMPACT ── */}
        <section className="impact-panel__section" aria-label="Disruption Sequence">
          <div className="impact-panel__section-title font-mono">DISRUPTION SEQUENCE</div>
          <div className="impact-seq">
            {SEQUENCE_STEPS.map((step, idx) => (
              <div key={step.id} className="impact-seq__item">
                <div className={`impact-seq__node ${animated ? 'impact-seq__node--active' : ''}`}>
                  <span className="impact-seq__step-num font-mono">{idx + 1}</span>
                  <span className="impact-seq__step-name">{step.label}</span>
                </div>
                {idx < SEQUENCE_STEPS.length - 1 && (
                  <div className="impact-seq__arrow" aria-hidden="true">
                    →
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ── CORE METRICS (Exact Prompt Specifications) ── */}
        <section className="impact-panel__section" aria-label="Network Disruption Metrics">
          <div className="impact-panel__section-title font-mono">NETWORK DISRUPTION METRICS</div>

          <div className="impact-grid">
            {/* BEFORE */}
            <div className="impact-card">
              <span className="impact-card__label font-mono">BEFORE</span>
              <div className="impact-card__val-row">
                <span className="impact-card__val font-mono">{Math.round(animatedBefore)}</span>
                <span className="impact-card__unit">components</span>
              </div>
              <span className="impact-card__sub">Baseline Connected Graph</span>
            </div>

            {/* AFTER */}
            <div className="impact-card impact-card--danger">
              <span className="impact-card__label font-mono">AFTER</span>
              <div className="impact-card__val-row">
                <span className="impact-card__val impact-card__val--danger font-mono">
                  {Math.round(animatedAfter)}
                </span>
                <span className="impact-card__unit">components</span>
              </div>
              <span className="impact-card__sub impact-card__sub--danger">
                +{simulationResult.deltaComponents} Isolated Subgraph
              </span>
            </div>

            {/* NODES AFFECTED */}
            <div className="impact-card impact-card--highlight">
              <span className="impact-card__label font-mono">NODES AFFECTED</span>
              <div className="impact-card__val-row">
                <span className="impact-card__val impact-card__val--critical font-mono">
                  {Math.round(animatedNodes)}
                </span>
                <span className="impact-card__unit">nodes</span>
              </div>
              <span className="impact-card__sub">Downstream Valley Grid</span>
            </div>

            {/* ISOLATION SEVERITY */}
            <div className="impact-card">
              <span className="impact-card__label font-mono">ISOLATION SEVERITY</span>
              <div className="impact-card__val-row">
                <span className="impact-card__val impact-card__val--severity font-mono">
                  {simulationResult.isolationSeverity}
                </span>
              </div>
              <span className="impact-card__sub">Zero Alternate Arterials</span>
            </div>
          </div>
        </section>

        {/* ── TOPOLOGICAL NARRATIVE ── */}
        <section className="impact-panel__section" aria-label="Network Narrative">
          <div className="impact-panel__section-title font-mono">TOPOLOGICAL IMPACT BRIEF</div>
          <div className="impact-panel__narrative">
            <p>
              Severing <strong>Way {simulationResult.wayId}</strong> causes immediate graph partition.
              The downstream transportation cluster fragments into an isolated component comprising{' '}
              <strong>{simulationResult.nodesAffected} critical road vertices</strong>.
            </p>
            <div className="impact-panel__callout">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>Emergency transit to medical facilities delayed by estimated 8.4 hours via foot reconnaissance.</span>
            </div>
          </div>
        </section>

        {/* ── ISOLATED SEGMENTS & COORDINATES ── */}
        <section className="impact-panel__section" aria-label="Downstream Isolated Segments">
          <div className="impact-panel__section-title font-mono">ISOLATED REACHES &amp; CUTOFF NODES</div>
          <div className="impact-nodes-list font-mono">
            {simulationResult.affectedCoordinates.map((coord, i) => (
              <div key={i} className="impact-nodes-list__item">
                <span className="impact-nodes-list__idx">#{i + 1}</span>
                <span className="impact-nodes-list__coord">
                  {coord[1].toFixed(4)}°N, {coord[0].toFixed(4)}°E
                </span>
                <span className="impact-nodes-list__tag">ISOLATED</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* ── FOOTER ACTIONS ── */}
      <div className="impact-panel__footer">
        <button
          type="button"
          className="impact-panel__btn impact-panel__btn--primary"
          onClick={resetSimulation}
        >
          Restore Baseline Network
        </button>
        <button
          type="button"
          className="impact-panel__btn impact-panel__btn--secondary"
          onClick={() => startSimulation(selectedRoad?.id)}
        >
          Re-simulate
        </button>
      </div>
    </div>
  );
}
