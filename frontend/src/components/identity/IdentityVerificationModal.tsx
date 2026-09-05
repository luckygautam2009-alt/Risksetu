import React, { useState } from 'react';
import {
  type IdentityProviderType,
  type IdentityStatusData,
  startIdentityVerification,
  ApiError,
} from '../../services/api';
import './IdentityVerificationModal.css';

interface IdentityVerificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  identityStatus: IdentityStatusData | null;
  onStatusUpdated: () => Promise<void>;
}

export const IdentityVerificationModal: React.FC<IdentityVerificationModalProps> = ({
  isOpen,
  onClose,
  identityStatus,
  onStatusUpdated,
}) => {
  const [selectedProvider, setSelectedProvider] = useState<IdentityProviderType>('AADHAAR');
  const [consentObtained, setConsentObtained] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  if (!isOpen) return null;

  const isVerified = identityStatus?.is_verified ?? false;

  const handleStartVerification = async () => {
    if (!consentObtained) {
      setIsError(true);
      setMessage('Explicit citizen consent is required before initiating government identity verification.');
      return;
    }

    setLoading(true);
    setMessage(null);
    setIsError(false);

    try {
      const res = await startIdentityVerification(selectedProvider, true);
      if (!res.is_provider_available) {
        setIsError(true);
        setMessage(res.message || 'Verification provider unavailable in this environment.');
      } else if (res.redirect_url) {
        window.location.href = res.redirect_url;
      } else {
        setMessage(res.message || 'Verification initiated.');
        await onStatusUpdated();
      }
    } catch (err: unknown) {
      setIsError(true);
      if (err instanceof ApiError) {
        setMessage(`Verification error (${err.status}): ${err.body}`);
      } else {
        setMessage('Failed to connect to identity service.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="identity-modal-overlay">
      <div className="identity-modal-container">
        <div className="identity-modal-header">
          <div className="identity-modal-title">
            <span>🛡️</span> Government Identity Verification
          </div>
          <button className="identity-close-btn" onClick={onClose}>
            &times;
          </button>
        </div>

        <div className="identity-modal-body">
          {/* Current Status Header */}
          <div className={`identity-status-banner ${isVerified ? 'verified' : 'unverified'}`}>
            <span>{isVerified ? '✅' : '⚠️'}</span>
            <div>
              <strong>
                Status: {identityStatus?.status ?? 'UNVERIFIED'}
              </strong>
              {isVerified && identityStatus?.minimal_reference && (
                <div style={{ fontSize: '0.8rem', opacity: 0.8, marginTop: '2px' }}>
                  Reference: {identityStatus.minimal_reference} | Verified At: {identityStatus.verified_at ? new Date(identityStatus.verified_at).toLocaleDateString() : 'N/A'}
                </div>
              )}
            </div>
          </div>

          {!isVerified && (
            <>
              <p style={{ fontSize: '0.9rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                To upload photographic evidence or issue evidence-backed ground reports, citizens must verify their identity via Aadhaar or DigiLocker.
              </p>

              {/* Provider Selection */}
              <div className="identity-provider-cards">
                <div
                  className={`provider-card ${selectedProvider === 'AADHAAR' ? 'selected' : ''}`}
                  onClick={() => setSelectedProvider('AADHAAR')}
                >
                  <div className="provider-title">🏛️ Aadhaar Verification</div>
                  <div className="provider-desc">Official UIDAI gateway verification via OTP / Consent.</div>
                </div>

                <div
                  className={`provider-card ${selectedProvider === 'DIGILOCKER' ? 'selected' : ''}`}
                  onClick={() => setSelectedProvider('DIGILOCKER')}
                >
                  <div className="provider-title">📁 DigiLocker OAuth2</div>
                  <div className="provider-desc">Digital locker consent protocol verification.</div>
                </div>
              </div>

              {/* Consent Box */}
              <div className="consent-checkbox-container">
                <input
                  type="checkbox"
                  id="consent-check"
                  checked={consentObtained}
                  onChange={(e) => setConsentObtained(e.target.checked)}
                />
                <label htmlFor="consent-check" className="consent-label">
                  I grant explicit consent to RiskSetu AI to verify my identity via government APIs. No raw Aadhaar numbers, OTPs, or biometrics are stored or logged.
                </label>
              </div>
            </>
          )}

          {/* Feedback message */}
          {message && (
            <div className={`identity-message-box ${isError ? 'error' : 'info'}`}>
              {message}
            </div>
          )}
        </div>

        <div className="identity-modal-footer">
          <button className="identity-secondary-btn" onClick={onClose}>
            {isVerified ? 'Close' : 'Cancel'}
          </button>

          {!isVerified && (
            <button
              className="identity-primary-btn"
              onClick={handleStartVerification}
              disabled={loading || !consentObtained}
            >
              {loading ? 'Initiating...' : `Verify via ${selectedProvider}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
