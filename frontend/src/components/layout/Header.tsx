import { Badge } from '../ui/Badge';
import { SystemStatusPanel } from '../common/SystemStatusPanel';
import { useMapContext } from '../../context/MapContext';
import './Header.css';

const DATA_INDICATORS = ['GSI', 'IMD', 'OSM'] as const;

export function Header() {
  const { isDemoRunning, systemStatus, probeSystemReadiness } = useMapContext();
  return (
    <header className="header" role="banner">
      <div className="header__brand">
        <div className="header__insignia" aria-hidden="true">
          <svg viewBox="0 0 28 28" fill="none" className="header__insignia-svg">
            <path
              d="M14 2L26 8.5V19.5L14 26L2 19.5V8.5L14 2Z"
              stroke="var(--color-geo-blue)"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path
              d="M14 7L21 11V17L14 21L7 17V11L14 7Z"
              stroke="var(--color-geo-teal)"
              strokeWidth="1.2"
              fill="rgba(47, 117, 117, 0.08)"
            />
            <circle cx="14" cy="14" r="2.5" fill="var(--color-risk-low)" />
          </svg>
        </div>

        <div className="header__title-group">
          <h1 className="header__title">RISKSETU AI</h1>
          <p className="header__subtitle">EARLY WARNING &amp; LANDSLIDE INTELLIGENCE</p>
        </div>
      </div>

      <div className="header__right">
        {isDemoRunning && (
          <span className="header__demo-badge" aria-label="Demo mode active">
            <span className="header__demo-dot" aria-hidden="true" />
            DEMO
          </span>
        )}

        <SystemStatusPanel
          statusData={systemStatus}
          onRefresh={probeSystemReadiness}
        />

        <div className="header__divider" aria-hidden="true" />

        <div className="header__indicators" aria-label="Active data sources">
          {DATA_INDICATORS.map((indicator) => (
            <Badge key={indicator} variant="source" size="sm">
              {indicator}
            </Badge>
          ))}
        </div>
      </div>
    </header>
  );
}


