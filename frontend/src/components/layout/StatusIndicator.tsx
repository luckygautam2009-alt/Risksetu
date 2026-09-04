import type { SystemStatus } from '../../types';
import './StatusIndicator.css';

export interface StatusIndicatorProps {
  status: SystemStatus;
  label: string;
  detail?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export function StatusIndicator({
  status,
  label,
  detail,
  size = 'md',
  className = '',
}: StatusIndicatorProps) {
  return (
    <div className={`status-indicator status-indicator--${size} ${className}`.trim()} role="status">
      <span
        className={`status-indicator__dot status-indicator__dot--${status}`}
        aria-hidden="true"
      />
      <div className="status-indicator__text">
        <span className="status-indicator__label">{label}</span>
        {detail && <span className="status-indicator__detail font-mono">{detail}</span>}
      </div>
    </div>
  );
}

