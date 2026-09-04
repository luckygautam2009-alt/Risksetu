import type { ReactNode } from 'react';
import { Header } from './Header';
import { LayerBar } from './LayerBar';
import './AppShell.css';

export interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <Header />
      <div className="app-shell__viewport">
        {children}
        <LayerBar />
      </div>
    </div>
  );
}

