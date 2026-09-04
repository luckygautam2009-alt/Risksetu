import { MapProvider } from './context/MapContext';
import { AppShell } from './components/layout/AppShell';
import { Dashboard } from './pages/Dashboard';

export default function App() {
  return (
    <MapProvider>
      <AppShell>
        <Dashboard />
      </AppShell>
    </MapProvider>
  );
}

