import type { HTMLAttributes, ReactNode } from 'react';
import './Panel.css';

export type PanelVariant = 'surface' | 'floating' | 'dock' | 'flat';
export type PanelPadding = 'none' | 'sm' | 'md' | 'lg';

export interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  variant?: PanelVariant;
  padding?: PanelPadding;
  interactive?: boolean;
  className?: string;
  children: ReactNode;
}

export function Panel({
  variant = 'surface',
  padding = 'md',
  interactive = false,
  className = '',
  children,
  ...props
}: PanelProps) {
  const interactiveClass = interactive ? 'panel--interactive' : '';

  return (
    <div
      className={`panel panel--${variant} panel--pad-${padding} ${interactiveClass} ${className}`.trim()}
      {...props}
    >
      {children}
    </div>
  );
}

export interface PanelHeaderProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}

export function PanelHeader({
  title,
  subtitle,
  badge,
  actions,
  className = '',
  children,
}: PanelHeaderProps) {
  if (children) {
    return <div className={`panel__header ${className}`.trim()}>{children}</div>;
  }

  return (
    <div className={`panel__header ${className}`.trim()}>
      <div className="panel__title-group">
        <div className="panel__title-row">
          {title && <h3 className="panel__title">{title}</h3>}
          {badge && <div className="panel__badge">{badge}</div>}
        </div>
        {subtitle && <p className="panel__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="panel__actions">{actions}</div>}
    </div>
  );
}

export function PanelBody({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`panel__body ${className}`.trim()}>{children}</div>;
}

export function PanelFooter({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`panel__footer ${className}`.trim()}>{children}</div>;
}

