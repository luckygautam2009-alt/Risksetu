/**
 * WeatherPanel — compact floating panel showing live weather + 3-day forecast.
 *
 * DATA HONESTY:
 *  - Shows "Current precipitation" (hourly) — never "72H rainfall".
 *  - Shows "Forecast precipitation" for each forecast day.
 *  - If backend unavailable → explicit unavailable state.
 *  - Source label: "LIVE · Open-Meteo"
 */
import { useEffect } from 'react';
import { useMapContext } from '../../context/MapContext';
import './WeatherPanel.css';

const WMO_ICON: Record<number, string> = {
  0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
  45: '🌫️', 48: '🌫️',
  51: '🌦️', 53: '🌦️', 55: '🌧️',
  61: '🌧️', 63: '🌧️', 65: '🌧️',
  71: '❄️', 73: '❄️', 75: '❄️', 77: '❄️',
  80: '🌦️', 81: '🌧️', 82: '⛈️',
  85: '🌨️', 86: '🌨️',
  95: '⛈️', 96: '⛈️', 99: '⛈️',
};

function weatherIcon(code: number | null | undefined): string {
  if (code == null) return '—';
  return WMO_ICON[code] ?? '🌡️';
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

interface Props {
  onClose: () => void;
}

export function WeatherPanel({ onClose }: Props) {
  const { weather, selectedHazard, evalCoords } = useMapContext();

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const locationName = selectedHazard?.location ?? (
    evalCoords ? `${evalCoords.lat.toFixed(3)}°N, ${evalCoords.lon.toFixed(3)}°E` : 'No location selected'
  );
  const noLocation = !evalCoords && !selectedHazard;

  return (
    <div className="wx-panel" role="region" aria-label="Live weather panel">
      {/* ── Header ── */}
      <div className="wx-panel__header">
        <div className="wx-panel__title-group">
          <span className="wx-panel__icon" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z" />
            </svg>
          </span>
          <span className="wx-panel__title font-mono">LIVE WEATHER</span>
        </div>
        <button
          type="button"
          className="wx-panel__close"
          onClick={onClose}
          aria-label="Close weather panel"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* ── Location ── */}
      <div className="wx-panel__location">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
          <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" />
        </svg>
        <span>{locationName}</span>
      </div>

      {/* ── Body ── */}
      <div className="wx-panel__body">
        {noLocation && (
          <div className="wx-panel__empty">
            <p>Select a location on the map to view live weather.</p>
          </div>
        )}

        {!noLocation && weather.state === 'loading' && (
          <div className="wx-panel__loading">
            <span className="wx-panel__spinner" aria-hidden="true" />
            <span>Fetching live weather…</span>
          </div>
        )}

        {!noLocation && weather.state === 'error' && (
          <div className="wx-panel__unavail">
            <span className="wx-panel__unavail-icon" aria-hidden="true">⚠</span>
            <span>Unable to retrieve weather. Retry by selecting the location again.</span>
          </div>
        )}

        {!noLocation && weather.state === 'success' && !weather.data?.current && (
          <div className="wx-panel__unavail">
            <span className="wx-panel__unavail-icon" aria-hidden="true">⚠</span>
            <span>Live weather unavailable.{weather.data?.error_message ? ` ${weather.data.error_message}` : ''}</span>
          </div>
        )}

        {!noLocation && weather.state === 'success' && weather.data?.current && (
          <>
            {/* ── Provider Status Banner ── */}
            {(weather.data.provider_status === 'cached' || weather.data.data_freshness_seconds > 300) && (
              <div className="wx-panel__stale-banner font-mono">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>
                  {weather.data.provider_status === 'cached' ? 'CACHED' : 'STALE'}
                  {' · Data is '}{ Math.round(weather.data.data_freshness_seconds / 60)} min old
                </span>
              </div>
            )}

            {/* ── Current Conditions ── */}
            <section className="wx-panel__current" aria-label="Current conditions">
              <div className="wx-panel__section-label font-mono">CURRENT CONDITIONS</div>

              <div className="wx-panel__hero">
                <div className="wx-panel__temp-block">
                  <span className="wx-panel__emoji" aria-hidden="true">
                    {weatherIcon(weather.data.current.weather_code)}
                  </span>
                  <span className="wx-panel__temp">
                    {weather.data.current.temperature_c.toFixed(1)}°C
                  </span>
                </div>
                <div className="wx-panel__condition">
                  {weather.data.current.weather_description}
                </div>
              </div>

              <div className="wx-panel__grid">
                <div className="wx-panel__metric">
                  <span className="wx-panel__metric-label font-mono">PRECIP. (current hr)</span>
                  <span className="wx-panel__metric-val">
                    {weather.data.current.precipitation_mm.toFixed(1)} mm
                  </span>
                </div>
                <div className="wx-panel__metric">
                  <span className="wx-panel__metric-label font-mono">HUMIDITY</span>
                  <span className="wx-panel__metric-val">
                    {weather.data.current.relative_humidity_pct.toFixed(0)}%
                  </span>
                </div>
                <div className="wx-panel__metric">
                  <span className="wx-panel__metric-label font-mono">WIND</span>
                  <span className="wx-panel__metric-val">
                    {weather.data.current.wind_speed_kmh.toFixed(0)} km/h
                  </span>
                </div>
                <div className="wx-panel__metric">
                  <span className="wx-panel__metric-label font-mono">PROVIDER</span>
                  <span className="wx-panel__metric-val wx-panel__metric-val--muted">
                    {weather.data.provider_status === 'cached' ? 'CACHED' : weather.data.provider_status?.toUpperCase() ?? 'OK'}
                  </span>
                </div>
                {weather.data.data_freshness_seconds > 0 && (
                  <div className="wx-panel__metric">
                    <span className="wx-panel__metric-label font-mono">UPDATED</span>
                    <span className="wx-panel__metric-val wx-panel__metric-val--muted">
                      {Math.round(weather.data.data_freshness_seconds / 60)} min ago
                    </span>
                  </div>
                )}
              </div>
            </section>

            {/* ── 3-Day Forecast ── */}
            {weather.data.forecast && weather.data.forecast.length > 0 && (
              <section className="wx-panel__forecast" aria-label="3-day forecast">
                <div className="wx-panel__section-label font-mono">3-DAY FORECAST</div>
                <div className="wx-panel__forecast-strip">
                  {weather.data.forecast.slice(0, 3).map((day, i) => (
                    <div key={i} className="wx-panel__forecast-day">
                      <span className="wx-panel__forecast-date">
                        {i === 0 ? 'TODAY' : formatDate(day.date)}
                      </span>
                      <span className="wx-panel__forecast-emoji" aria-hidden="true">
                        {weatherIcon(day.weather_code)}
                      </span>
                      <span className="wx-panel__forecast-temp">
                        {day.temperature_max_c.toFixed(0)}° / {day.temperature_min_c.toFixed(0)}°
                      </span>
                      <span className="wx-panel__forecast-cond">
                        {day.weather_description}
                      </span>
                      <span className="wx-panel__forecast-precip font-mono">
                        ↓ {day.precipitation_sum_mm.toFixed(1)} mm
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ── Hourly Forecast Honesty ── */}
            <div className="wx-panel__hourly-unavail font-mono">
              Hourly forecast unavailable from current provider
            </div>
          </>
        )}
      </div>

      {/* ── Footer: source label ── */}
      <div className="wx-panel__footer font-mono">
        LIVE WEATHER · OPEN-METEO · No API key required
      </div>
    </div>
  );
}
