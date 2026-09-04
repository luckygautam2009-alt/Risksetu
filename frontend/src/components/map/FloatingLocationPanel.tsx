import { useEffect, useState, type ReactElement } from 'react';
import { useMapContext } from '../../context/MapContext';
import { useAnimatedNumber } from '../../hooks/useAnimatedNumber';
import {
  getAdjacentCorridor,
  getEvidenceGroups,
  getRiskAssessmentConclusion,
} from '../../data/mockRiskData';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import type { EvidenceGroup } from '../../data/mockRiskData';
import './FloatingLocationPanel.css';

/* Pillar icon paths */
const PILLAR_ICONS: Record<EvidenceGroup['pillar'], ReactElement> = {
  historical: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22V12M12 12L5 8M12 12l7-4M5 8V18l7 4M19 8v10l-7 4" />
    </svg>
  ),
  rainfall: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 17.58A5 5 0 0018 8h-1.26A8 8 0 104 16.25M8 19v1M8 22v1M12 21v1M12 18v1M16 19v1M16 22v1" />
    </svg>
  ),
  terrain: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 18l5-10 4 6 3-4 6 8H3z" />
    </svg>
  ),
};

function EvidenceBar({
  score,
  pending,
  delay,
  animated,
}: {
  score: number | null;
  pending: boolean;
  delay: number;
  animated: boolean;
}) {
  if (pending || score === null) return null;

  const barColor =
    score >= 75 ? 'var(--color-risk-high)' :
    score >= 50 ? 'var(--color-risk-moderate)' :
    'var(--color-risk-low)';

  return (
    <div className="evidence-bar__track">
      <div
        className="evidence-bar__fill"
        style={{
          width: animated ? `${score}%` : '0%',
          background: barColor,
          transitionDelay: `${delay}ms`,
        }}
      />
    </div>
  );
}

export function FloatingLocationPanel() {
  const { selectedHazard, selectHazard, selectRoad, startSimulation } = useMapContext();
  const [animated, setAnimated] = useState(false);

  // Trigger bar animations one frame after mount
  useEffect(() => {
    if (!selectedHazard) return;
    const id = requestAnimationFrame(() => {
      setAnimated(false);
      requestAnimationFrame(() => setAnimated(true));
    });
    return () => cancelAnimationFrame(id);
  }, [selectedHazard]);

  const animatedScore = useAnimatedNumber(selectedHazard?.riskScore ?? 0, 750);
  const animatedConfidence = useAnimatedNumber(selectedHazard?.confidence ?? 0, 600);

  if (!selectedHazard) return null;

  const evidenceGroups = getEvidenceGroups(selectedHazard);
  const conclusion = getRiskAssessmentConclusion(selectedHazard);
  const corridor = getAdjacentCorridor(selectedHazard.id);

  const handleCopyCoords = () => {
    const text = `${selectedHazard.coordinatesFormatted.lat}, ${selectedHazard.coordinatesFormatted.lng}`;
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="rp" key={selectedHazard.id}>
      {/* ── HEADER ── */}
      <div className="rp__header">
        <div className="rp__header-meta">
          <span className="rp__location">{selectedHazard.location.toUpperCase()}</span>
          <span className="rp__sector">{selectedHazard.subdivision}</span>
        </div>
        <IconButton
          label="Close panel"
          size="xs"
          variant="ghost"
          onClick={() => selectHazard(null)}
          icon={
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          }
        />
      </div>

      {/* ── COORDINATES ── */}
      <div className="rp__coords">
        <span className="rp__coord">{selectedHazard.coordinatesFormatted.lat}</span>
        <span className="rp__coord-dot" aria-hidden="true">·</span>
        <span className="rp__coord">{selectedHazard.coordinatesFormatted.lng}</span>
        <span className="rp__elev">↑ {selectedHazard.elevationM.toLocaleString()} m</span>
      </div>

      {/* ── SCROLLABLE BODY ── */}
      <div className="rp__body">

        {/* Risk Assessment */}
        <section className="rp__section" aria-label="Risk Assessment">
          <div className="rp__section-label">RISK ASSESSMENT</div>

          <div className="rp__score-row rp__animate rp__animate--delay-1">
            <div className="rp__score-block">
              <span className={`rp__score rp__score--${selectedHazard.riskLevel}`}>
                {animatedScore.toFixed(1)}
              </span>
              <span className="rp__score-unit">/ 100</span>
            </div>
            <Badge
              variant="risk"
              riskLevel={selectedHazard.riskLevel}
              size="md"
              dot
              pulse={selectedHazard.riskLevel === 'CRITICAL'}
            >
              {selectedHazard.riskLevel}
            </Badge>
          </div>

          <div className="rp__confidence rp__animate rp__animate--delay-2">
            <span className="rp__confidence-label">CONFIDENCE</span>
            <div className="rp__confidence-track">
              <div
                className="rp__confidence-fill"
                style={{ width: `${animatedConfidence}%` }}
              />
            </div>
            <span className={`rp__confidence-value rp__confidence-value--${selectedHazard.confidenceLevel}`}>
              {animatedConfidence.toFixed(1)}%
            </span>
          </div>
        </section>

        {/* Divider */}
        <div className="rp__rule" />

        {/* Risk Story */}
        <section className="rp__section" aria-label="Risk explanation">
          <div className="rp__story-heading">WHY IS THIS LOCATION AT RISK?</div>

          {evidenceGroups.map((ev, i) => {
            const animDelay = i * 2; // CSS animation delay class index
            const barDelay = 300 + i * 180; // ms for bar transition
            return (
              <div key={ev.pillar}>
                {/* Evidence Pillar Card */}
                <div className={`rp__evidence rp__animate rp__animate--delay-${3 + animDelay}`}>
                  <div className="rp__evidence-header">
                    <span className="rp__evidence-icon">{PILLAR_ICONS[ev.pillar]}</span>
                    <div className="rp__evidence-title-block">
                      <span className="rp__evidence-title">{ev.label.toUpperCase()}</span>
                      <span className="rp__evidence-sublabel">{ev.sublabel}</span>
                    </div>
                    {ev.pending ? (
                      <span className="rp__evidence-pending">DATA PENDING</span>
                    ) : (
                      <span className={`rp__evidence-score rp__evidence-score--${
                        (ev.score ?? 0) >= 75 ? 'high' : (ev.score ?? 0) >= 50 ? 'mod' : 'low'
                      }`}>
                        {ev.score}
                      </span>
                    )}
                  </div>

                  {/* Evidence Bar */}
                  <EvidenceBar
                    score={ev.score}
                    pending={ev.pending}
                    delay={barDelay}
                    animated={animated}
                  />

                  {/* Summary text */}
                  <p className="rp__evidence-summary">
                    {ev.pending
                      ? ev.rawText
                      : (ev.summary ?? ev.rawText)}
                  </p>

                  {/* Raw text tag (secondary context) */}
                  {!ev.pending && ev.summary && (
                    <p className="rp__evidence-raw">{ev.rawText}</p>
                  )}
                </div>

                {/* Chain connector — "+" between pillars */}
                {i < evidenceGroups.length - 1 && (
                  <div className="rp__chain-connector" aria-hidden="true">
                    <div className="rp__chain-line" />
                    <span className="rp__chain-op">+</span>
                    <div className="rp__chain-line" />
                  </div>
                )}
              </div>
            );
          })}

          {/* Conclusion Arrow + Block */}
          <div className="rp__chain-connector rp__animate rp__animate--delay-9" aria-hidden="true">
            <div className="rp__chain-line" />
            <span className="rp__chain-op rp__chain-op--arrow">↓</span>
            <div className="rp__chain-line" />
          </div>

          <div className={`rp__conclusion rp__conclusion--${selectedHazard.riskLevel} rp__animate rp__animate--delay-9`}>
            <span className="rp__conclusion-label">RISK ASSESSMENT</span>
            <p className="rp__conclusion-text">{conclusion}</p>
          </div>

          {/* Adjacent Corridor & Direct Simulation Trigger (HAZARD -> ROAD FAILURE) */}
          {corridor && (
            <div className="rp__corridor-box rp__animate rp__animate--delay-9">
              <div className="rp__corridor-header">
                <span className="rp__corridor-tag font-mono">ADJACENT CORRIDOR</span>
                <span className="rp__corridor-way font-mono">Way {corridor.wayId}</span>
              </div>
              <div className="rp__corridor-name">{corridor.name}</div>
              <p className="rp__corridor-desc">
                Active hazard directly jeopardizes lifeline connectivity. High risk of debris flow blockage.
              </p>
              <button
                type="button"
                className="rp__sim-btn"
                onClick={() => {
                  selectRoad(corridor.id);
                  startSimulation(corridor.id);
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
                SIMULATE ROAD FAILURE
              </button>
            </div>
          )}
        </section>
      </div>

      {/* ── FOOTER ── */}
      <div className="rp__footer">
        <button
          type="button"
          className="rp__action"
          onClick={() => selectHazard(selectedHazard.id)}
        >
          Center View
        </button>
        <button type="button" className="rp__action" onClick={handleCopyCoords}>
          Copy Coordinates
        </button>
        <button type="button" className="rp__action">
          Export Brief
        </button>
      </div>
    </div>
  );
}
