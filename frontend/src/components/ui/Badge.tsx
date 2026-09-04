import type { ReactNode } from 'react';
import type { RiskLevel } from '../../types';
import './Badge.css';

export type BadgeVariant = 'default' | 'source' | 'risk' | 'telemetry' | 'accent' | 'outline';
export type BadgeSize = 'sm' | 'md';

export interface BadgeProps {
  variant?: BadgeVariant;
  riskLevel?: RiskLevel;
  size?: BadgeSize;
  dot?: boolean;
  pulse?: boolean;
  children: ReactNode;
  className?: string;
}

export function Badge({
  variant = 'default',
  riskLevel,
  size = 'md',
  dot = false,
  pulse = false,
  children,
  className = '',
}: BadgeProps) {
  const riskClass = riskLevel ? `badge--risk-${riskLevel.toLowerCase()}` : '';
  const pulseClass = pulse ? 'badge--pulse' : '';

  return (
    <span
      className={`badge badge--${variant} badge--${size} ${riskClass} ${pulseClass} ${className}`.trim()}
    >
      {dot && <span className="badge__dot" aria-hidden="true" />}
      <span className="badge__content">{children}</span>
    </span>
  );
}

