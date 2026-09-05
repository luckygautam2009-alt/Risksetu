import React from 'react';
import './StateViews.css';

interface LoadingStateProps {
  message?: string;
  subtext?: string;
  size?: 'small' | 'medium' | 'large';
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading verified intelligence...',
  subtext,
  size = 'medium',
  className = '',
}) => {
  return (
    <div className={`state-view-container state-loading state-${size} ${className}`} role="status">
      <div className="state-spinner" aria-hidden="true" />
      <span className="state-title">{message}</span>
      {subtext && <span className="state-subtext">{subtext}</span>}
    </div>
  );
};

interface ErrorStateProps {
  title?: string;
  message?: string;
  status?: number;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Intelligence Retrieval Failed',
  message = 'Unable to fetch authoritative data from server.',
  status,
  onRetry,
  className = '',
}) => {
  return (
    <div className={`state-view-container state-error ${className}`} role="alert">
      <div className="state-icon-error" aria-hidden="true">⚠️</div>
      <div className="state-content">
        <div className="state-title-row">
          <span className="state-title">{title}</span>
          {status !== undefined && status > 0 && (
            <span className="state-status-pill">HTTP {status}</span>
          )}
        </div>
        <p className="state-message">{message}</p>
        {onRetry && (
          <button type="button" className="state-retry-btn" onClick={onRetry}>
            ↻ Retry Request
          </button>
        )}
      </div>
    </div>
  );
};

interface EmptyStateProps {
  title: string;
  message?: string;
  icon?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  message,
  icon = '📋',
  actionLabel,
  onAction,
  className = '',
}) => {
  return (
    <div className={`state-view-container state-empty ${className}`}>
      <div className="state-icon" aria-hidden="true">{icon}</div>
      <span className="state-title">{title}</span>
      {message && <p className="state-message">{message}</p>}
      {actionLabel && onAction && (
        <button type="button" className="state-action-btn" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
};

interface UnavailableStateProps {
  title: string;
  reason?: string;
  provider?: string;
  className?: string;
}

export const UnavailableState: React.FC<UnavailableStateProps> = ({
  title,
  reason = 'Dataset or upstream provider is not configured in this environment.',
  provider,
  className = '',
}) => {
  return (
    <div className={`state-view-container state-unavailable ${className}`}>
      <div className="state-header-row">
        <span className="state-badge-unavailable">○ UNAVAILABLE</span>
        {provider && <span className="state-provider-tag">{provider}</span>}
      </div>
      <span className="state-title">{title}</span>
      <p className="state-message">{reason}</p>
    </div>
  );
};

interface StaleDataStateProps {
  lastUpdated: string;
  freshnessSeconds?: number | null;
  className?: string;
}

export const StaleDataState: React.FC<StaleDataStateProps> = ({
  lastUpdated,
  freshnessSeconds,
  className = '',
}) => {
  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return ts;
    }
  };

  const ageText = freshnessSeconds ? `${Math.round(freshnessSeconds / 60)}m ago` : formatTime(lastUpdated);

  return (
    <div className={`state-stale-banner ${className}`}>
      <span className="state-stale-dot" aria-hidden="true">⏱</span>
      <span className="state-stale-text">
        Cached Operational View · Last Updated: <strong>{ageText}</strong>
      </span>
    </div>
  );
};
