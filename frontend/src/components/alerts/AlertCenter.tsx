import { useState, useMemo } from 'react';
import { useMapContext } from '../../context/MapContext';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import type { UserRole } from '../../data/alertsData';
import './AlertCenter.css';

const ROLES: UserRole[] = ['Incident Commander', 'Field Analyst', 'Disaster Response Lead'];

type FilterTab = 'ALL' | 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED';

export function AlertCenter() {
  const {
    alerts,
    selectAlert,
    acknowledgeAlert,
    resolveAlert,
    dismissAlert,
    userRole,
    setUserRole,
    selectLocation,
    setWorkflowTab,
    soundBlocked,
    enableEmergencySound,
    soundEnabled,
    setSoundEnabled,
  } = useMapContext();

  const [filterTab, setFilterTab] = useState<FilterTab>('ALL');

  const filteredAlerts = useMemo(() => {
    if (filterTab === 'ALL') return alerts;
    return alerts.filter((a) => a.status === filterTab);
  }, [alerts, filterTab]);

  const counts = useMemo(() => {
    return {
      ALL: alerts.length,
      ACTIVE: alerts.filter((a) => a.status === 'ACTIVE').length,
      ACKNOWLEDGED: alerts.filter((a) => a.status === 'ACKNOWLEDGED').length,
      RESOLVED: alerts.filter((a) => a.status === 'RESOLVED').length,
      DISMISSED: alerts.filter((a) => a.status === 'DISMISSED').length,
    };
  }, [alerts]);

  const handleInspect = (alert: (typeof alerts)[0]) => {
    selectLocation({
      latitude: alert.latitude,
      longitude: alert.longitude,
      name: alert.location,
    });
    selectAlert(alert.id);
  };

  return (
    <div className="alert-center" role="region" aria-label="Operational Alert Command Center">
      {/* ── HEADER ── */}
      <div className="alert-center__header">
        <div className="alert-center__title-group">
          <div className="alert-center__overline font-mono">
            <span className="alert-center__live-dot" aria-hidden="true" />
            OPERATIONAL DECISION SUPPORT · REAL-TIME ALERTS
          </div>
          <h2 className="alert-center__heading">ALERT COMMAND CENTER</h2>
        </div>

        <IconButton
          label="Close alert center"
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

      {/* ── SOUND AUTOPLAY NOTICE IF BLOCKED ── */}
      {soundBlocked && (
        <div className="alert-center__sound-alert font-mono">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
            <line x1="23" y1="9" x2="17" y2="15" />
            <line x1="17" y1="9" x2="23" y2="15" />
          </svg>
          <span>EMERGENCY SOUND BLOCKED BY BROWSER</span>
          <button
            className="alert-center__sound-btn font-mono"
            onClick={() => enableEmergencySound()}
          >
            ENABLE SOUND
          </button>
        </div>
      )}

      {/* ── OPERATIONAL ROLE BAR ── */}
      <div className="alert-center__role-bar">
        <div className="alert-center__role-info">
          <span className="alert-center__role-label font-mono">OPERATIONAL ROLE:</span>
          <select
            className="alert-center__role-select font-mono"
            value={userRole}
            onChange={(e) => setUserRole(e.target.value as UserRole)}
            aria-label="Select active user operational role"
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </div>

        <button
          className={`alert-center__audio-toggle font-mono ${soundEnabled ? 'alert-center__audio-toggle--on' : ''}`}
          onClick={() => setSoundEnabled(!soundEnabled)}
          title={soundEnabled ? 'Emergency sound enabled' : 'Emergency sound muted'}
        >
          {soundEnabled ? '🔊 SOUND ON' : '🔇 SOUND MUTED'}
        </button>
      </div>

      {/* ── FILTER TABS ── */}
      <div className="alert-center__tabs" role="tablist">
        {(['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED'] as FilterTab[]).map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={filterTab === tab}
            className={`alert-center__tab font-mono ${filterTab === tab ? 'alert-center__tab--active' : ''}`}
            onClick={() => setFilterTab(tab)}
          >
            {tab} <span className="alert-center__tab-count">({counts[tab]})</span>
          </button>
        ))}
      </div>

      {/* ── ALERT LIST ── */}
      <div className="alert-center__body">
        {filteredAlerts.length === 0 ? (
          <div className="alert-center__empty">
            <div className="alert-center__empty-icon">✓</div>
            <div className="alert-center__empty-title font-mono">NO {filterTab} ALERTS</div>
            <p className="alert-center__empty-desc">
              No alerts currently recorded under status filter &quot;{filterTab}&quot;. Spatially localized emergency monitoring active.
            </p>
          </div>
        ) : (
          <div className="alert-center__list">
            {filteredAlerts.map((alert) => {
              const isCritical = alert.severity === 'CRITICAL';
              return (
                <div
                  key={alert.id}
                  className={`alert-card ${isCritical ? 'alert-card--critical' : ''} alert-card--${alert.status.toLowerCase()}`}
                >
                  <div className="alert-card__top">
                    <div className="alert-card__badges">
                      <span className={`alert-card__sev font-mono alert-card__sev--${alert.severity.toLowerCase()}`}>
                        {isCritical && <span className="alert-card__pulse" aria-hidden="true" />}
                        {alert.severity}
                      </span>
                      <Badge variant="source" size="sm">
                        {alert.status}
                      </Badge>
                      {alert.priorityScore !== undefined && (
                        <span className="alert-card__prio font-mono">
                          PRIO: {alert.priorityScore.toFixed(0)}
                        </span>
                      )}
                    </div>
                    <span className="alert-card__time font-mono">{alert.triggeredAt}</span>
                  </div>

                  <h3 className="alert-card__title">{alert.title}</h3>

                  <div className="alert-card__location font-mono">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
                      <circle cx="12" cy="10" r="3" />
                    </svg>
                    <span>
                      {alert.location} · {alert.latitude.toFixed(4)}°N, {alert.longitude.toFixed(4)}°E
                    </span>
                  </div>

                  {alert.summary && (
                    <p className="alert-card__summary">{alert.summary}</p>
                  )}

                  {alert.recommendedAction && (
                    <div className="alert-card__rec font-mono">
                      <strong>ACTION:</strong> {alert.recommendedAction}
                    </div>
                  )}

                  {/* Audit information */}
                  {(alert.acknowledgedBy || alert.resolvedBy) && (
                    <div className="alert-card__audit font-mono">
                      {alert.resolvedBy ? (
                        <span>RESOLVED BY: {alert.resolvedBy}</span>
                      ) : (
                        <span>ACKNOWLEDGED BY: {alert.acknowledgedBy}</span>
                      )}
                    </div>
                  )}

                  {/* Card Actions */}
                  <div className="alert-card__actions">
                    <button
                      className="alert-card__btn alert-card__btn--inspect font-mono"
                      onClick={() => handleInspect(alert)}
                    >
                      INSPECT ON MAP →
                    </button>

                    {alert.status === 'ACTIVE' && (
                      <button
                        className="alert-card__btn alert-card__btn--ack font-mono"
                        onClick={() => acknowledgeAlert(alert.id)}
                      >
                        ACKNOWLEDGE
                      </button>
                    )}

                    {(alert.status === 'ACTIVE' || alert.status === 'ACKNOWLEDGED') && (
                      <button
                        className="alert-card__btn alert-card__btn--resolve font-mono"
                        onClick={() => resolveAlert(alert.id)}
                      >
                        RESOLVE
                      </button>
                    )}

                    {alert.status !== 'RESOLVED' && alert.status !== 'DISMISSED' && (
                      <button
                        className="alert-card__btn alert-card__btn--dismiss font-mono"
                        onClick={() => dismissAlert(alert.id)}
                      >
                        DISMISS
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── FOOTER: PROVENANCE ── */}
      <div className="alert-center__footer font-mono">
        ALERT DATA · FASTAPI RISKSETU BACKEND · POSTGIS SPATIAL REPOSITORY
      </div>
    </div>
  );
}
