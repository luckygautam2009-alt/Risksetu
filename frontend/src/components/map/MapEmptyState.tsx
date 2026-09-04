import { useMapContext } from '../../context/MapContext';
import type { RiskLevel } from '../../types';
import './MapEmptyState.css';

function riskPillClass(level: RiskLevel): string {
  if (level === 'CRITICAL') return 'map-empty-state__pill map-empty-state__pill--critical';
  if (level === 'HIGH') return 'map-empty-state__pill map-empty-state__pill--high';
  return 'map-empty-state__pill';
}

export function MapEmptyState() {
  const { hazards, selectHazard } = useMapContext();

  // Show top 4 critical/high hazards as quick-jump pills
  const topHazards = hazards
    .filter((h) => h.riskLevel === 'CRITICAL' || h.riskLevel === 'HIGH')
    .slice(0, 4);

  return (
    <div className="map-empty-state">
      <div className="map-empty-state__card">
        <svg className="map-empty-state__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="8" />
          <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
          <circle cx="12" cy="12" r="2" />
        </svg>
        <p className="map-empty-state__text">
          Select a hazard zone on the map to begin intelligence analysis
        </p>
        <div className="map-empty-state__pills">
          {topHazards.map((h) => (
            <button
              type="button"
              key={h.id}
              className={riskPillClass(h.riskLevel)}
              onClick={() => selectHazard(h.id)}
            >
              {h.location} ({h.riskScore})
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
