import type { ReactNode } from 'react';
import './SectionLabel.css';

export interface SectionLabelProps {
  children: ReactNode;
  count?: number | string;
  badge?: ReactNode;
  action?: ReactNode;
  variant?: 'default' | 'accent' | 'muted';
  className?: string;
}

export function SectionLabel({
  children,
  count,
  badge,
  action,
  variant = 'default',
  className = '',
}: SectionLabelProps) {
  return (
    <div className={`section-label section-label--${variant} ${className}`.trim()}>
      <div className="section-label__leading">
        <span className="section-label__text">{children}</span>
        {count !== undefined && <span className="section-label__count font-mono">{count}</span>}
        {badge}
      </div>
      {action && <div className="section-label__action">{action}</div>}
    </div>
  );
}
