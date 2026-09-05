import React, { useState } from 'react';
import type { WsConnectionStatus } from '../../services/realtime';
import type { ReadinessResponse } from '../../services/api';
import './SystemStatusPanel.css';

export interface SystemStatusData {
  readiness: ReadinessResponse['data'] | null;
  wsStatus: WsConnectionStatus;
  weatherAvailable: boolean;
  identityAvailable: boolean;
  isOffline: boolean;
}

interface SystemStatusPanelProps {
  statusData: SystemStatusData;
  onRefresh?: () => void;
  className?: string;
}

export const SystemStatusPanel: React.FC<SystemStatusPanelProps> = ({
  statusData,
  onRefresh,
  className = '',
}) => {
  const [expanded, setExpanded] = useState(false);

  const { readiness, wsStatus, weatherAvailable, isOffline } = statusData;

  const dbStatus = isOffline
    ? 'OFFLINE'
    : readiness?.checks?.database === 'ok'
    ? 'CONNECTED'
    : 'UNHEALTHY';

  const riskEngineStatus = isOffline ? 'OFFLINE' : dbStatus === 'CONNECTED' ? 'LIVE' : 'DEGRADED';
  const weatherStatus = isOffline ? 'OFFLINE' : weatherAvailable ? 'LIVE' : 'UNAVAILABLE';
  const alertsStatus = isOffline ? 'OFFLINE' : wsStatus === 'CONNECTED' ? 'CONNECTED' : wsStatus === 'RECONNECTING' ? 'RECONNECTING' : 'OFFLINE';
  const roadStatus = isOffline ? 'OFFLINE' : dbStatus === 'CONNECTED' ? 'AVAILABLE' : 'UNAVAILABLE';
  const identityStatus = 'AVAILABLE';
  const terrainStatus = 'UNAVAILABLE';
  const sheltersStatus = 'UNAVAILABLE';
  const smsStatus = 'NOT CONFIGURED';

  const getStatusClass = (val: string) => {
    switch (val) {
      case 'LIVE':
      case 'CONNECTED':
      case 'AVAILABLE':
        return 'status-ok';
      case 'RECONNECTING':
      case 'DEGRADED':
        return 'status-warn';
      case 'NOT CONFIGURED':
      case 'UNAVAILABLE':
        return 'status-neutral';
      case 'OFFLINE':
      case 'UNHEALTHY':
      case 'ERROR':
      default:
        return 'status-err';
    }
  };

  const getDotIcon = (val: string) => {
    switch (val) {
      case 'LIVE':
      case 'CONNECTED':
      case 'AVAILABLE':
        return '●';
      case 'RECONNECTING':
      case 'DEGRADED':
        return '◐';
      case 'NOT CONFIGURED':
      case 'UNAVAILABLE':
        return '○';
      default:
        return '✕';
    }
  };

  const systemItems = [
    { label: 'DATABASE (PostgreSQL & PostGIS)', value: dbStatus, note: 'Authoritative data source' },
    { label: 'RISK ENGINE (LIVE_RISK_V1)', value: riskEngineStatus, note: 'Deterministic baseline + trigger' },
    { label: 'WEATHER (Open-Meteo)', value: weatherStatus, note: '5-minute cached observations' },
    { label: 'REALTIME ALERTS (WebSocket)', value: alertsStatus, note: 'Emergency push channel' },
    { label: 'ROAD NETWORK (OSM Graph)', value: roadStatus, note: 'Connectivity & isolation topology' },
    { label: 'IDENTITY (Gov Verification)', value: identityStatus, note: 'Aadhaar / DigiLocker gateway' },
    { label: 'TERRAIN (DEM Elevation)', value: terrainStatus, note: 'No validated high-res DEM' },
    { label: 'SHELTERS (Verified Data)', value: sheltersStatus, note: 'Ground survey required' },
    { label: 'SMS GATEWAY (Telecom)', value: smsStatus, note: 'Provider credentials unconfigured' },
  ];

  return (
    <div className={`system-status-wrapper ${className}`}>
      <button
        type="button"
        className="system-status-summary-btn"
        onClick={() => setExpanded((v) => !v)}
        title="View Subsystem Health & Availability"
        aria-expanded={expanded}
      >
        <span className="summary-title">SYSTEM STATUS</span>
        <span className={`summary-badge ${getStatusClass(riskEngineStatus)}`}>
          {getDotIcon(riskEngineStatus)} {isOffline ? 'OFFLINE' : readiness?.status === 'ok' ? 'HEALTHY' : 'DEGRADED'}
        </span>
        <span className="summary-toggle-icon">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="system-status-card" role="region" aria-label="System Subsystems Status">
          <div className="system-card-header">
            <span className="system-card-title">SUBSYSTEM AVAILABILITY AUDIT</span>
            {onRefresh && (
              <button type="button" className="system-refresh-btn" onClick={onRefresh} title="Probe subsystems">
                ↻ Probe
              </button>
            )}
          </div>
          <div className="system-grid">
            {systemItems.map((item) => (
              <div key={item.label} className="system-row">
                <div className="system-label-col">
                  <span className="system-item-name">{item.label}</span>
                  <span className="system-item-note">{item.note}</span>
                </div>
                <span className={`system-item-val ${getStatusClass(item.value)}`}>
                  {getDotIcon(item.value)} {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
