import { useState } from 'react';
import { useMapContext } from '../../context/MapContext';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';
import type { UserRole } from '../../data/alertsData';
import './AlertDetailPanel.css';

const ROLES: UserRole[] = ['Incident Commander', 'Field Analyst', 'Disaster Response Lead'];

export function AlertDetailPanel() {
  const {
    alerts,
    selectedAlert,
    selectAlert,
    acknowledgeAlert,
    resolveAlert,
    dismissAlert,
    userRole,
    setUserRole,
    startSimulation,
  } = useMapContext();

  const [actionsChecked, setActionsChecked] = useState<Record<string, boolean>>({});

  // If an alert is selected, show that alert; otherwise show the top active alert (or list)
  const currentAlert = selectedAlert ?? alerts.find((a) => a.status === 'ACTIVE') ?? alerts[0];

  if (!currentAlert) return null;

  const toggleAction = (actId: string) => {
    setActionsChecked((prev) => ({ ...prev, [actId]: !prev[actId] }));
  };

  const isCritical = currentAlert.severity === 'CRITICAL';

  return (
    <div className="alert-panel" role="region" aria-label="Spatial Alert Intelligence">
      {/* ── HEADER ── */}
      <div className="alert-panel__header">
        <div className="alert-panel__title-group">
          <div className="alert-panel__badge-row">
            <span className={`alert-panel__severity font-mono ${isCritical ? 'alert-panel__severity--critical' : 'alert-panel__severity--high'}`}>
              <span className="alert-panel__pulse-dot" aria-hidden="true" />
              {currentAlert.severity} ALERT
            </span>
            <Badge
              variant="source"
              size="sm"
            >
              STATUS: {currentAlert.status}
            </Badge>
          </div>
          <h2 className="alert-panel__location font-mono">{currentAlert.location}</h2>
          <p className="alert-panel__corridor">{currentAlert.corridorName} (Way {currentAlert.wayId})</p>
        </div>

        <IconButton
          label="Close alert panel"
          size="xs"
          variant="ghost"
          onClick={() => selectAlert(null)}
          icon={
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          }
        />
      </div>

      {/* ── USER ROLE CONTEXT BAR (Respect User Roles) ── */}
      <div className="alert-panel__role-bar">
        <div className="alert-panel__role-info">
          <span className="alert-panel__role-label font-mono">ACTIVE ROLE:</span>
          <select
            className="alert-panel__role-select font-mono"
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
        <span className="alert-panel__role-badge font-mono">AUTH: LEVEL-1 COMMAND</span>
      </div>

      {/* ── AUDIT LOG NOTIFICATION ── */}
      {(currentAlert.acknowledgedBy || currentAlert.resolvedBy) && (
        <div className="alert-panel__audit font-mono">
          {currentAlert.resolvedBy ? (
            <span>RESOLVED: {currentAlert.resolvedBy}</span>
          ) : (
            <span>ACKNOWLEDGED: {currentAlert.acknowledgedBy}</span>
          )}
        </div>
      )}

      {/* ── ALERT SUMMARY ── */}
      <div className="alert-panel__body">
        <div className="alert-panel__summary-box">
          <h3 className="alert-panel__summary-title">{currentAlert.title}</h3>
          <p className="alert-panel__summary-text">{currentAlert.summary}</p>
        </div>

        {/* ── IMMEDIATE ACTIONS (Exact Prompt Specifications) ── */}
        <section className="alert-panel__section" aria-label="Immediate Actions">
          <div className="alert-panel__section-title font-mono">
            <span>IMMEDIATE ACTIONS REQUIRED</span>
            <span>AGENCY DISPATCH</span>
          </div>

          <div className="alert-actions-list">
            {currentAlert.immediateActions.map((action) => {
              const isChecked = actionsChecked[action.id] || action.completed;
              return (
                <div
                  key={action.id}
                  className={`alert-action-card ${isChecked ? 'alert-action-card--done' : ''}`}
                  onClick={() => toggleAction(action.id)}
                  role="checkbox"
                  aria-checked={isChecked}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === ' ' || e.key === 'Enter') toggleAction(action.id);
                  }}
                >
                  <div className="alert-action-card__left">
                    <span className="alert-action-card__checkbox">
                      {isChecked && (
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </span>
                    <span className="alert-action-card__label">{action.label}</span>
                  </div>
                  <span className="alert-action-card__agency font-mono">{action.targetAgency}</span>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── LINK TO ROAD SIMULATION ── */}
        <div className="alert-panel__corridor-callout">
          <div className="alert-panel__callout-top">
            <span className="alert-panel__callout-label font-mono">TRANSPORT CORRIDOR AT RISK</span>
            <button
              type="button"
              className="alert-panel__callout-btn font-mono"
              onClick={() => {
                startSimulation('road-nh58');
              }}
            >
              Simulate Failure →
            </button>
          </div>
          <span className="alert-panel__callout-sub">{currentAlert.corridorName}</span>
        </div>
      </div>

      {/* ── OPERATIONAL LIFECYCLE ACTIONS (Exact Prompt: ACKNOWLEDGE, RESOLVE, DISMISS) ── */}
      <div className="alert-panel__footer">
        <button
          type="button"
          className="alert-panel__action-btn alert-panel__action-btn--ack"
          disabled={currentAlert.status === 'ACKNOWLEDGED' || currentAlert.status === 'RESOLVED'}
          onClick={() => acknowledgeAlert(currentAlert.id)}
          title={`Acknowledge alert as ${userRole}`}
        >
          {currentAlert.status === 'ACKNOWLEDGED' ? 'ACKNOWLEDGED' : 'ACKNOWLEDGE'}
        </button>

        <button
          type="button"
          className="alert-panel__action-btn alert-panel__action-btn--resolve"
          disabled={currentAlert.status === 'RESOLVED'}
          onClick={() => resolveAlert(currentAlert.id)}
          title={`Mark alert resolved by ${userRole}`}
        >
          {currentAlert.status === 'RESOLVED' ? 'RESOLVED' : 'RESOLVE'}
        </button>

        <button
          type="button"
          className="alert-panel__action-btn alert-panel__action-btn--dismiss"
          onClick={() => dismissAlert(currentAlert.id)}
          title="Dismiss alert notification"
        >
          DISMISS
        </button>
      </div>
    </div>
  );
}
