import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './IconButton.css';

export type IconButtonSize = 'xs' | 'sm' | 'md' | 'lg';
export type IconButtonVariant = 'default' | 'subtle' | 'ghost' | 'outline' | 'primary' | 'active';

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon: ReactNode;
  size?: IconButtonSize;
  variant?: IconButtonVariant;
  active?: boolean;
}

export function IconButton({
  label,
  icon,
  size = 'md',
  variant = 'default',
  active = false,
  className = '',
  ...props
}: IconButtonProps) {
  const activeClass = active ? 'icon-btn--active' : '';

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`icon-btn icon-btn--${variant} icon-btn--${size} ${activeClass} ${className}`.trim()}
      {...props}
    >
      <span className="icon-btn__icon" aria-hidden="true">
        {icon}
      </span>
    </button>
  );
}
