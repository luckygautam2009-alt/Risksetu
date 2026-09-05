/**
 * FloatingLocationPanel — right-side intelligence panel for a selected location.
 * Shows real LIVE_RISK_V1 + weather from backend. No fabricated values.
 * SOS flow is now handled by SosPanel (opened via TopActionBar / footer button).
 */
import { useEffect, useState, type ReactElement } from 'react';
import { useMapContext } from '../../context/MapContext';
import { useAnimatedNumber } from '../../hooks/useAnimatedNumber';
import { getAdjacentCorridor } from '../../data/mockRiskData';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import type { EvidenceGroup } from '../../data/mockRiskData';
import './FloatingLocationPanel.css';

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

function EvidenceBar({ score, delay, animated }: { score: number; delay: number; animated: boolean }) {
  const color = score >= 75 ? 'var(--color-risk-high)' : score >= 50 ? 'var(--color-risk-moderate)' : 'var(--color-risk-low)';
  return (
    <div className="evidence-bar__track">
      <div className="evidence-bar__fill" style={{ width: animated ? `${score}%` : '0%', background: color, transitionDelay: `${delay}ms` }} />
    </div>
  );
}

export function FloatingLocationPanel() {
  const { selectedHazard, selectHazard, selectRoad, startSimulation, liveRisk, weather, openSosPanel } = useMapContext();
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    if (!selectedHazard) return;
    const id = requestAnimationFrame(() => { setAnimated(false); requestAnimationFrame(() => setAnimated(true)); });
    return () => cancelAnimationFrame(id);
  }, [selectedHazard]);

  const displayScore  = liveRisk.state === 'success' && liveRisk.data ? liveRisk.data.risk.score      : selectedHazard?.riskScore  ?? 0;
  const displayLevel  = (liveRisk.state === 'success' && liveRisk.data ? liveRisk.data.risk.level      : selectedHazard?.riskLevel  ?? 'LOW') as 'LOW'|'MODERATE'|'HIGH'|'CRITICAL';
  const displayConf   = liveRisk.state === 'success' && liveRisk.data ? liveRisk.data.risk.confidence  : selectedHazard?.confidence ?? 0;
  const isLive        = liveRisk.state === 'success' && liveRisk.data != null;

  const animScore = useAnimatedNumber(displayScore, 750);
  const animConf  = useAnimatedNumber(displayConf,  600);

  if (!selectedHazard) return null;

  const corridor = getAdjacentCorridor(selectedHazard.id);

  const handleCopyCoords = () => {
    navigator.clipboard.writeText(`${selectedHazard.coordinatesFormatted.lat}, ${selectedHazard.coordinatesFormatted.lng}`).catch(() => {});
  };

  return (
    <div className="rp" key={selectedHazard.id}>
      {/* Header */}
      <div className="rp__header">
        <div className="rp__header-meta">
          <span className="rp__location">{selectedHazard.location.toUpperCase()}</span>
          <span className="rp__sector">{selectedHazard.subdivision}</span>
        </div>
        <IconButton label="Close panel" size="xs" variant="ghost" onClick={() => selectHazard(null)}
          icon={<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>} />
      </div>

      {/* Coordinates */}
      <div className="rp__coords">
        <span className="rp__coord">{selectedHazard.coordinatesFormatted.lat}</span>
        <span className="rp__coord-dot" aria-hidden="true">·</span>
        <span className="rp__coord">{selectedHazard.coordinatesFormatted.lng}</span>
        {liveRisk.data?.terrain?.elevation_m != null
          ? <span className="rp__elev">↑ {liveRisk.data.terrain.elevation_m.toLocaleString()} m</span>
          : <span className="rp__elev rp__elev--unavail">↑ elev. unavail.</span>}
      </div>

      <div className="rp__body">
        {/* Risk Assessment */}
        <section className="rp__section" aria-label="Risk Assessment">
          <div className="rp__section-label">
            CURRENT RISK{!isLive && liveRisk.state !== 'loading' && <span className="rp__offline-tag font-mono"> OFFLINE EST.</span>}
          </div>
          {liveRisk.state === 'loading' ? (
            <div className="rp__loading-row"><span className="rp__loading-spinner" aria-hidden="true"/><span className="rp__loading-text">Analysing location…</span></div>
          ) : (
            <>
              <div className="rp__score-row rp__animate rp__animate--delay-1">
                <div className="rp__score-block">
                  <span className={`rp__score rp__score--${displayLevel}`}>{animScore.toFixed(1)}</span>
                  <span className="rp__score-unit">/ 100</span>
                </div>
                <Badge variant="risk" riskLevel={displayLevel} size="md" dot pulse={displayLevel==='CRITICAL'}>{displayLevel}</Badge>
              </div>
              <div className="rp__confidence rp__animate rp__animate--delay-2">
                <span className="rp__confidence-label">CONFIDENCE</span>
                <div className="rp__confidence-track"><div className="rp__confidence-fill" style={{width:`${animConf}%`}}/></div>
                <span className={`rp__confidence-value rp__confidence-value--${displayConf>=60?'HIGH':displayConf>=40?'MEDIUM':'LOW'}`}>{animConf.toFixed(1)}%</span>
              </div>
              <div className="rp__engine-honesty font-mono" style={{ fontSize: '9px', color: '#94a3b8', marginTop: '6px' }}>
                LIVE RISK · RISKSETU BACKEND · ML MODEL: UNAVAILABLE
              </div>
              {liveRisk.state === 'error' && <p className="rp__error-note">⚠ Live risk unavailable — showing cached estimate.</p>}
            </>
          )}
        </section>

        <div className="rp__rule" />

        {/* WHY? */}
        <section className="rp__section" aria-label="Risk explanation">
          <div className="rp__story-heading">WHY IS THIS LOCATION AT RISK?</div>

          {/* Historical */}
          <div className="rp__evidence rp__animate rp__animate--delay-3">
            <div className="rp__evidence-header">
              <span className="rp__evidence-icon">{PILLAR_ICONS.historical}</span>
              <div className="rp__evidence-title-block">
                <span className="rp__evidence-title">HISTORICAL EVIDENCE</span>
                <span className="rp__evidence-sublabel">HISTORICAL EVIDENCE · GSI Landslide Inventory</span>
              </div>
              {liveRisk.state === 'loading' ? <span className="rp__loading-spinner" aria-hidden="true"/>
                : isLive && liveRisk.data?.historical.status === 'available'
                  ? <span className="rp__evidence-score rp__evidence-score--high">{(liveRisk.data.historical.score??0).toFixed(0)}</span>
                  : <span className="rp__evidence-pending">—</span>}
            </div>
            {isLive && liveRisk.data?.historical.score != null && <EvidenceBar score={liveRisk.data.historical.score} delay={300} animated={animated}/>}
            <p className="rp__evidence-summary">{isLive && liveRisk.data?.historical.summary ? liveRisk.data.historical.summary : selectedHazard.historicalEvidence}</p>
            <p className="rp__evidence-raw font-mono">Source: GSI Bhukosh NLSM · IMD Climatology</p>
          </div>

          <div className="rp__chain-connector" aria-hidden="true">
            <div className="rp__chain-line"/><span className="rp__chain-op">+</span><div className="rp__chain-line"/>
          </div>

          {/* Live Weather */}
          <div className="rp__evidence rp__animate rp__animate--delay-5">
            <div className="rp__evidence-header">
              <span className="rp__evidence-icon">{PILLAR_ICONS.rainfall}</span>
              <div className="rp__evidence-title-block">
                <span className="rp__evidence-title">LIVE WEATHER</span>
                <span className="rp__evidence-sublabel">{weather.state==='success'&&weather.data?.current?'LIVE WEATHER · OPEN-METEO (Current hour)':'LIVE WEATHER · OPEN-METEO'}</span>
              </div>
              {weather.state==='loading' ? <span className="rp__loading-spinner" aria-hidden="true"/>
                : weather.state==='success'&&weather.data?.current ? <span className="rp__evidence-score rp__evidence-score--mod">LIVE</span>
                : <span className="rp__evidence-pending">UNAVAIL.</span>}
            </div>
            {weather.state==='loading' && <p className="rp__evidence-summary">Fetching live weather…</p>}
            {weather.state==='success' && weather.data?.current && (
              <>
                <div className="rp__weather-grid">
                  <div className="rp__weather-item"><span className="rp__weather-label">Precip. (current hr)</span><span className="rp__weather-val">{weather.data.current.precipitation_mm.toFixed(1)} mm</span></div>
                  <div className="rp__weather-item"><span className="rp__weather-label">Temperature</span><span className="rp__weather-val">{weather.data.current.temperature_c.toFixed(1)} °C</span></div>
                  <div className="rp__weather-item"><span className="rp__weather-label">Humidity</span><span className="rp__weather-val">{weather.data.current.relative_humidity_pct.toFixed(0)}%</span></div>
                  <div className="rp__weather-item"><span className="rp__weather-label">Wind</span><span className="rp__weather-val">{weather.data.current.wind_speed_kmh.toFixed(0)} km/h</span></div>
                </div>
                <p className="rp__evidence-summary">{weather.data.current.weather_description}</p>
                {weather.data.data_freshness_seconds>0 && <p className="rp__evidence-raw font-mono">Updated {Math.round(weather.data.data_freshness_seconds/60)} min ago</p>}
                {weather.data.forecast.length>0 && (
                  <div className="rp__forecast">
                    {weather.data.forecast.slice(0,3).map((day,i)=>(
                      <div key={i} className="rp__forecast-day">
                        <span className="rp__forecast-label">+{i+1}d</span>
                        <span className="rp__forecast-precip">{day.precipitation_sum_mm.toFixed(1)} mm</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
            {(weather.state==='error'||(weather.state==='success'&&!weather.data?.current)) && (
              <p className="rp__evidence-summary rp__unavail-text">Live weather unavailable.</p>
            )}
          </div>

          <div className="rp__chain-connector" aria-hidden="true">
            <div className="rp__chain-line"/><span className="rp__chain-op">+</span><div className="rp__chain-line"/>
          </div>

          {/* Terrain */}
          <div className="rp__evidence rp__animate rp__animate--delay-7">
            <div className="rp__evidence-header">
              <span className="rp__evidence-icon">{PILLAR_ICONS.terrain}</span>
              <div className="rp__evidence-title-block">
                <span className="rp__evidence-title">TERRAIN</span>
                <span className="rp__evidence-sublabel font-mono" style={{ color: '#eab308' }}>TERRAIN · UNAVAILABLE</span>
              </div>
              <span className="rp__evidence-pending">UNAVAIL.</span>
            </div>
            <p className="rp__evidence-summary rp__unavail-text">TERRAIN · UNAVAILABLE · Validated DEM Pending. Terrain slope and DEM model not active.</p>
          </div>

          {/* Conclusion */}
          <div className="rp__chain-connector rp__animate rp__animate--delay-9" aria-hidden="true">
            <div className="rp__chain-line"/><span className="rp__chain-op rp__chain-op--arrow">↓</span><div className="rp__chain-line"/>
          </div>
          <div className={`rp__conclusion rp__conclusion--${displayLevel} rp__animate rp__animate--delay-9`}>
            <span className="rp__conclusion-label">RECOMMENDED ACTIONS</span>
            {isLive && liveRisk.data && liveRisk.data.recommended_actions.length>0
              ? liveRisk.data.recommended_actions.slice(0,3).map(a=><p key={a.action_id} className="rp__conclusion-text">• {a.description}</p>)
              : <p className="rp__conclusion-text">{displayLevel==='CRITICAL'||displayLevel==='HIGH' ? 'Immediate monitoring recommended.' : displayLevel==='MODERATE' ? 'Enhanced surveillance warranted.' : 'Routine monitoring.'}</p>}
          </div>

          {/* Adjacent corridor */}
          {corridor && (
            <div className="rp__corridor-box rp__animate rp__animate--delay-9">
              <div className="rp__corridor-header">
                <span className="rp__corridor-tag font-mono">ROAD NETWORK · OSM</span>
                <span className="rp__corridor-way font-mono">Way {corridor.wayId}</span>
              </div>
              <div className="rp__corridor-name">{corridor.name}</div>
              <div className="font-mono" style={{ fontSize: '9px', color: '#f59e0b', marginBottom: '4px' }}>
                CLOSURE STATUS · UNKNOWN (ROAD RISK ≠ ROAD CLOSURE)
              </div>
              <p className="rp__corridor-desc">Active hazard directly jeopardizes lifeline connectivity.</p>
              <button type="button" className="rp__sim-btn" onClick={() => { selectRoad(corridor.id); startSimulation(corridor.id); }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                SIMULATE ROAD FAILURE
              </button>
            </div>
          )}
        </section>
      </div>

      {/* Footer */}
      <div className="rp__footer">
        <button type="button" className="rp__action" onClick={handleCopyCoords}>Copy Coordinates</button>
        <button type="button" className="rp__action rp__action--sos-trigger" onClick={openSosPanel} title="Submit SOS emergency report">🆘 SOS</button>
      </div>
      <div className="font-mono" style={{ fontSize: '8px', color: '#64748b', textAlign: 'center', padding: '4px 8px', borderTop: '1px solid var(--color-border-subtle)', background: 'rgba(0,0,0,0.2)' }}>
        LIVE RISK · RISKSETU BACKEND · OPEN-METEO WEATHER · GSI LANDSLIDES
      </div>
    </div>
  );
}
