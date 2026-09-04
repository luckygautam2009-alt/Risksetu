import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './Button.css';

export type ButtonVariant =
  | 'default'
  | 'primary'
  | 'secondary'
  | 'subtle'
  | 'ghost'
  | 'outline'
  | 'danger';

export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  active?: boolean;
  icon?: ReactNode;
  iconRight?: ReactNode;
  children?: ReactNode;
}

export function Button({
  variant = 'default',
  size = 'md',
  active = false,
  icon,
  iconRight,
  className = '',
  children,
  ...props
}: ButtonProps) {
  const activeClass = active ? 'btn--active' : '';

  return (
    <button
      className={`btn btn--${variant} btn--${size} ${activeClass} ${className}`.trim()}
      {...props}
    >
      {icon && <span className="btn__icon" aria-hidden="true">{icon}</span>}
      {children && <span className="btn__text">{children}</span>}
      {iconRight && <span className="btn__icon-right" aria-hidden="true">{iconRight}</span>}
    </button>
  );
}

