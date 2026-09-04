import type { ReactNode } from 'react';
import type { RiskLevel } from '../../types';
import './Metric.css';

export interface MetricTrend {
  direction: 'up' | 'down' | 'stable';
  label: string;
}

export interface MetricProps {
  value: string | number;
  label: string;
  unit?: string;
  trend?: MetricTrend;
  riskLevel?: RiskLevel;
  secondary?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  children?: ReactNode;
}

export function Metric({
  value,
  label,
  unit,
  trend,
  riskLevel,
  secondary,
  size = 'md',
  className = '',
  children,
}: MetricProps) {
  const riskClass = riskLevel ? `metric--risk-${riskLevel.toLowerCase()}` : '';

  return (
    <div className={`metric metric--${size} ${riskClass} ${className}`.trim()}>
      <div className="metric__header">
        <span className="metric__label">{label}</span>
        {trend && (
          <span className={`metric__trend metric__trend--${trend.direction}`}>
            {trend.direction === 'up' && '▲ '}
            {trend.direction === 'down' && '▼ '}
            {trend.direction === 'stable' && '— '}
            {trend.label}
          </span>
        )}
      </div>

      <div className="metric__value-row font-mono">
        <span className="metric__value">{value}</span>
        {unit && <span className="metric__unit">{unit}</span>}
      </div>

      {secondary && <div className="metric__secondary">{secondary}</div>}
      {children}
    </div>
  );
}

