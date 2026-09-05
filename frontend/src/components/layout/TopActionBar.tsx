/**
 * TopActionBar — Quick action bar with Weather, SOS, Citizen Report, Officer HQ,
 * Language Selector (EN, HI, AS), and Offline Sync status.
 *
 * Positioned top-right of the map canvas, matching the WorkflowNav visual language.
 */
import { useMapContext } from '../../context/MapContext';
import { t, type SupportedLanguage } from '../../utils/i18n';
import './TopActionBar.css';

interface Props {
  onWeatherClick: () => void;
  onSosClick: () => void;
  weatherOpen: boolean;
  sosOpen: boolean;
}

export function TopActionBar({ onWeatherClick, onSosClick, weatherOpen, sosOpen }: Props) {
  const {
    alerts,
    language,
    setLanguage,
    openReportModal,
    openOfficerModal,
    identityStatus,
    openIdentityModal,
    isOffline,
    pendingSyncCount,
    triggerManualSync,
    setWorkflowTab,
    startSimulation,
    wsStatus,
    soundEnabled,
    setSoundEnabled,
    soundBlocked,
    enableEmergencySound,
    notificationPermission,
    requestNotificationPermission,
  } = useMapContext();

  const isVerified = identityStatus?.is_verified ?? false;
  const activeAlerts = alerts.filter((a) => a.status === 'ACTIVE').length;

  const handleSimulateClick = () => {
    setWorkflowTab('impact');
    startSimulation();
  };

  return (
    <div className="top-action-bar" aria-label="Quick actions">
      <div className="top-action-bar__dock">
        {/* Identity Status Badge & Modal Trigger */}
        <button
          type="button"
          className={`top-action-bar__btn ${isVerified ? 'top-action-bar__btn--verified' : 'top-action-bar__btn--unverified'}`}
          onClick={openIdentityModal}
          title={isVerified ? `Identity Verified (${identityStatus?.minimal_reference ?? 'Gov Certified'})` : 'Verify Identity via Aadhaar / DigiLocker'}
          style={{
            borderColor: isVerified ? '#10b981' : '#f59e0b',
            color: isVerified ? '#34d399' : '#fbbf24',
          }}
        >
          <span className="top-action-bar__icon" aria-hidden="true">
            {isVerified ? '🛡️' : '⚠️'}
          </span>
          <span className="top-action-bar__label">
            {isVerified ? 'VERIFIED' : 'UNVERIFIED'}
          </span>
        </button>

        <span className="top-action-bar__divider" aria-hidden="true" />

        {/* Citizen Report Modal Button */}
        <button
          type="button"
          className="top-action-bar__btn top-action-bar__btn--report"
          onClick={openReportModal}
          title="Submit citizen field hazard observation (IndexedDB offline supported)"
        >
          <span className="top-action-bar__icon" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </span>
          <span className="top-action-bar__label">{t(language, 'submitReport')}</span>
        </button>

        <span className="top-action-bar__divider" aria-hidden="true" />

        {/* Simulate Road Failure Shortcut */}
        <button
          type="button"
          className="top-action-bar__btn top-action-bar__btn--sim"
          onClick={handleSimulateClick}
          title="Simulate road cut and calculate network isolation"
        >
          <span className="top-action-bar__icon" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="18" cy="18" r="3" /><circle cx="6" cy="6" r="3" /><path d="M13 6h3a2 2 0 0 1 2 2v7M6 9v12" />
            </svg>
          </span>
          <span className="top-action-bar__label">{t(language, 'simulateRoadFailure')}</span>
        </button>

        <span className="top-action-bar__divider" aria-hidden="true" />

        {/* Weather */}
        <button
          type="button"
          className={`top-action-bar__btn ${weatherOpen ? 'top-action-bar__btn--active' : ''}`}
          onClick={onWeatherClick}
          aria-pressed={weatherOpen}
          title="Live weather and 3-day forecast"
        >
          <span className="top-action-bar__icon" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z" />
            </svg>
          </span>
          <span className="top-action-bar__label">{t(language, 'weather')}</span>
        </button>

        <span className="top-action-bar__divider" aria-hidden="true" />

        {/* SOS */}
        <button
          type="button"
          className={`top-action-bar__btn top-action-bar__btn--sos ${sosOpen ? 'top-action-bar__btn--sos-active' : ''}`}
          onClick={onSosClick}
          aria-pressed={sosOpen}
          title="Submit an emergency SOS report for the selected location"
        >
          <span className="top-action-bar__sos-dot" aria-hidden="true" />
          <span className="top-action-bar__label">SOS</span>
          {activeAlerts > 0 && (
            <span className="top-action-bar__alert-badge font-mono" aria-label={`${activeAlerts} active alerts`}>
              {activeAlerts}
            </span>
          )}
        </button>

        <span className="top-action-bar__divider" aria-hidden="true" />

        {/* Officer Workspace Modal Button */}
        <button
          type="button"
          className="top-action-bar__btn top-action-bar__btn--officer font-mono"
          onClick={openOfficerModal}
          title="Officer Workspace: Active SOS queue, mass siren broadcast, and OSINT intel"
        >
          <span className="top-action-bar__icon" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </span>
          <span className="top-action-bar__label">OFFICER HQ</span>
        </button>

        <span className="top-action-bar__divider" aria-hidden="true" />

        {/* WebSocket Real-Time Status */}
        <button
          type="button"
          className={`top-action-bar__btn top-action-bar__btn--ws font-mono ${wsStatus === 'CONNECTED' ? 'ws-live' : wsStatus === 'RECONNECTING' ? 'ws-reconnecting' : 'ws-offline'}`}
          title={`WebSocket: ${wsStatus}`}
          style={{ cursor: 'default', pointerEvents: 'none' }}
        >
          <span className="top-action-bar__ws-dot" aria-hidden="true" style={{
            display: 'inline-block',
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            marginRight: '4px',
            backgroundColor: wsStatus === 'CONNECTED' ? '#22c55e' : wsStatus === 'RECONNECTING' ? '#eab308' : '#94a3b8',
            boxShadow: wsStatus === 'CONNECTED' ? '0 0 6px #22c55e' : 'none',
          }} />
          <span className="top-action-bar__label">
            {wsStatus === 'CONNECTED' ? 'LIVE' : wsStatus === 'RECONNECTING' ? 'RECONNECTING' : 'OFFLINE'}
          </span>
        </button>

        {/* Emergency Sound Toggle */}
        <button
          type="button"
          className={`top-action-bar__btn font-mono ${soundEnabled ? 'top-action-bar__btn--active' : ''}`}
          onClick={() => setSoundEnabled(!soundEnabled)}
          title={soundEnabled ? 'Emergency sound: ON — click to mute' : 'Emergency sound: OFF — click to enable'}
        >
          <span className="top-action-bar__icon" aria-hidden="true">
            {soundEnabled ? '🔊' : '🔇'}
          </span>
          <span className="top-action-bar__label">
            {soundEnabled ? 'SOUND ON' : 'SOUND OFF'}
          </span>
        </button>

        {/* Browser Autoplay Sound Blocked Banner */}
        {soundBlocked && (
          <button
            type="button"
            className="top-action-bar__btn font-mono"
            onClick={() => enableEmergencySound()}
            title="Emergency audio blocked by browser autoplay policy. Click to unlock."
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              borderColor: '#ef4444',
              color: '#ef4444',
            }}
          >
            <span className="top-action-bar__icon" aria-hidden="true">🔇</span>
            <span className="top-action-bar__label">SOUND BLOCKED · CLICK TO ENABLE</span>
          </button>
        )}

        {/* Browser Notification Permission Button */}
        {notificationPermission === 'default' && (
          <button
            type="button"
            className="top-action-bar__btn font-mono"
            onClick={requestNotificationPermission}
            title="Enable desktop notifications for critical emergency alerts"
          >
            <span className="top-action-bar__icon" aria-hidden="true">🔔</span>
            <span className="top-action-bar__label">ENABLE NOTIFICATIONS</span>
          </button>
        )}

        <span className="top-action-bar__divider" aria-hidden="true" />

        {/* Offline sync status */}
        {(isOffline || pendingSyncCount > 0) && (
          <button
            type="button"
            className={`top-action-bar__btn top-action-bar__btn--offline font-mono ${isOffline ? 'is-disconnected' : 'has-pending'}`}
            onClick={triggerManualSync}
            title={isOffline ? 'Offline mode: changes queued in IndexedDB' : `${pendingSyncCount} pending offline items. Click to sync.`}
          >
            <span className="offline-dot" aria-hidden="true" />
            <span>{isOffline ? 'OFFLINE' : `SYNC (${pendingSyncCount})`}</span>
          </button>
        )}

        {/* Language selector */}
        <div className="top-action-bar__lang-group" role="group" aria-label="Language selector">
          {(['en', 'hi', 'as'] as SupportedLanguage[]).map((l) => (
            <button
              key={l}
              type="button"
              className={`top-action-bar__lang-btn font-mono ${language === l ? 'active' : ''}`}
              onClick={() => setLanguage(l)}
              title={`Switch language to ${l.toUpperCase()}`}
            >
              {l === 'en' ? 'EN' : l === 'hi' ? 'हि' : 'অ'}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
