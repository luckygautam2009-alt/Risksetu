import React from 'react';
import './DataSourceBadge.css';

export type DataSourceType =
  | 'GSI'
  | 'IMD'
  | 'OPEN-METEO'
  | 'OSM'
  | 'POSTGIS'
  | 'LIVE_RISK_V1'
  | 'COMMUNITY SIGNAL'
  | 'OSINT';

export type DataModeType = 'LIVE' | 'HISTORICAL' | 'FORECAST' | 'COMMUNITY' | 'SIMULATION';

interface DataSourceBadgeProps {
  source: DataSourceType | string;
  mode?: DataModeType;
  updatedAt?: string | null;
  freshnessSeconds?: number | null;
  className?: string;
  compact?: boolean;
}

export const DataSourceBadge: React.FC<DataSourceBadgeProps> = ({
  source,
  mode,
  updatedAt,
  freshnessSeconds,
  className = '',
  compact = false,
}) => {
  const getModeClass = (m?: DataModeType) => {
    switch (m) {
      case 'LIVE':
        return 'mode-live';
      case 'HISTORICAL':
        return 'mode-historical';
      case 'FORECAST':
        return 'mode-forecast';
      case 'COMMUNITY':
        return 'mode-community';
      case 'SIMULATION':
        return 'mode-simulation';
      default:
        return 'mode-default';
    }
  };

  const formatAge = (): string | null => {
    if (freshnessSeconds !== undefined && freshnessSeconds !== null) {
      if (freshnessSeconds < 60) return `${Math.round(freshnessSeconds)}s ago`;
      const mins = Math.round(freshnessSeconds / 60);
      if (mins < 60) return `${mins}m ago`;
      return `${Math.round(mins / 60)}h ago`;
    }
    if (updatedAt) {
      try {
        const d = new Date(updatedAt);
        const now = new Date();
        const diffMs = now.getTime() - d.getTime();
        const diffMins = Math.round(diffMs / 60000);
        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        return `${Math.round(diffMins / 60)}h ago`;
      } catch {
        return null;
      }
    }
    return null;
  };

  const ageString = formatAge();

  return (
    <div className={`data-source-badge ${compact ? 'badge-compact' : ''} ${className}`}>
      {mode && (
        <span className={`badge-mode-pill ${getModeClass(mode)}`}>
          {mode === 'LIVE' && <span className="live-pulse-dot" aria-hidden="true" />}
          {mode}
        </span>
      )}
      <span className="badge-source-name">{source}</span>
      {ageString && <span className="badge-age">{ageString}</span>}
    </div>
  );
};
