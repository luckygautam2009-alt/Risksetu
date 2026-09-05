import { useState } from 'react';
import { useMapContext } from '../../context/MapContext';
import { t } from '../../utils/i18n';
import './RegionalWatchBanner.css';

export function RegionalWatchBanner() {
  const { regionalWatches, language } = useMapContext();
  const [dismissed, setDismissed] = useState(false);

  // Filter for high-severity watches
  const activeAlerts = regionalWatches.filter(
    (w) => w.severity === 'HIGH' || w.severity === 'CRITICAL',
  );

  if (dismissed || activeAlerts.length === 0) return null;

  const topAlert = activeAlerts[0];
  const isWarning = topAlert.severity === 'CRITICAL';

  return (
    <div
      className={`regional-watch-banner ${isWarning ? 'status-warning' : 'status-watch'}`}
      role="region"
      aria-label="Regional Catchment Weather Screening Watch"
    >
      <div className="regional-watch-banner__icon" aria-hidden="true">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
        </svg>
      </div>

      <div className="regional-watch-banner__content">
        <div className="regional-watch-banner__top font-mono">
          <span className="regional-watch-banner__badge">
            {topAlert.severity} · {topAlert.region.toUpperCase()}
          </span>
          <span className="regional-watch-banner__meta">
            {t(language, 'catchmentScreening')} · Forecast {topAlert.forecast_rain_mm.toFixed(1)}mm
          </span>
        </div>
        <p className="regional-watch-banner__desc">
          {topAlert.title} — {topAlert.message}
        </p>
      </div>

      <button
        type="button"
        className="regional-watch-banner__close font-mono"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss Regional Catchment Screening Watch banner"
      >
        ✕
      </button>
    </div>
  );
}
