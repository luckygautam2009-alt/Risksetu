/**
 * RISKSETU AI — Real-Time WebSocket Client
 *
 * Manages authenticated WebSocket connection to /api/v1/alerts/ws
 * with automatic reconnection, heartbeat, and missed-alert reconciliation.
 *
 * Connection states: CONNECTED | RECONNECTING | DISCONNECTED
 *
 * All alert data originates from PostgreSQL via the backend WebSocket stream.
 * No synthetic or fabricated events are generated client-side.
 */

import { fetchAlerts } from './api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WsConnectionStatus = 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';

export interface RealtimeAlertEvent {
  event: string;
  data: {
    alert_id: string;
    sos_id?: string;
    severity: string;
    location: {
      latitude: number;
      longitude: number;
    };
    description?: string | null;
    evidence_count?: number;
    risk_context?: {
      risk_score: number | null;
      risk_level: string | null;
    };
    created_at: string;
    source: string;
  };
}

export type RealtimeEventCallback = (event: RealtimeAlertEvent) => void;
export type StatusChangeCallback = (status: WsConnectionStatus) => void;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const HEARTBEAT_INTERVAL_MS = 30_000; // 30s ping
const RECONNECT_BASE_DELAY_MS = 2_000; // 2s initial
const RECONNECT_MAX_DELAY_MS = 60_000; // 60s cap
const MAX_RECONNECT_ATTEMPTS = 20;

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private status: WsConnectionStatus = 'DISCONNECTED';
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private token: string | null = null;
  private intentionalClose = false;

  private eventListeners: Set<RealtimeEventCallback> = new Set();
  private statusListeners: Set<StatusChangeCallback> = new Set();

  // ── Public API ──────────────────────────────────────────────────────────

  /** Connect to the WebSocket with a JWT token. */
  connect(token: string): void {
    this.token = token;
    this.intentionalClose = false;
    this.reconnectAttempts = 0;
    this._establishConnection();
  }

  /** Gracefully disconnect. */
  disconnect(): void {
    this.intentionalClose = true;
    this._cleanup();
    this._setStatus('DISCONNECTED');
  }

  /** Register a listener for incoming alert events. */
  onEvent(callback: RealtimeEventCallback): () => void {
    this.eventListeners.add(callback);
    return () => this.eventListeners.delete(callback);
  }

  /** Register a listener for connection status changes. */
  onStatusChange(callback: StatusChangeCallback): () => void {
    this.statusListeners.add(callback);
    // Immediately emit current status
    callback(this.status);
    return () => this.statusListeners.delete(callback);
  }

  /** Get current connection status. */
  getStatus(): WsConnectionStatus {
    return this.status;
  }

  // ── Internal ────────────────────────────────────────────────────────────

  private _buildWsUrl(): string {
    const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let wsBase: string;

    if (base.startsWith('http')) {
      // Absolute URL: convert http(s) to ws(s)
      wsBase = base.replace(/^http/, 'ws');
    } else if (base) {
      // Relative path
      wsBase = `${protocol}//${window.location.host}${base}`;
    } else {
      wsBase = `${protocol}//${window.location.host}`;
    }

    return `${wsBase}/api/v1/alerts/ws?token=${encodeURIComponent(this.token ?? '')}`;
  }

  private _establishConnection(): void {
    this._cleanup();

    if (!this.token) {
      this._setStatus('DISCONNECTED');
      return;
    }

    try {
      const url = this._buildWsUrl();
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._setStatus('CONNECTED');
        this._startHeartbeat();
        // Reconcile missed alerts on reconnect
        this._reconcileMissedAlerts();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string);
          // Skip pong heartbeat responses
          if (data?.type === 'pong') return;
          // Dispatch event to listeners
          if (data?.event) {
            const alertEvent = data as RealtimeAlertEvent;
            this.eventListeners.forEach((cb) => {
              try {
                cb(alertEvent);
              } catch {
                // listener error silenced
              }
            });
          }
        } catch {
          // malformed message ignored
        }
      };

      this.ws.onclose = () => {
        this._stopHeartbeat();
        if (!this.intentionalClose) {
          this._scheduleReconnect();
        } else {
          this._setStatus('DISCONNECTED');
        }
      };

      this.ws.onerror = () => {
        // onclose will fire after onerror
      };
    } catch {
      this._scheduleReconnect();
    }
  }

  private _scheduleReconnect(): void {
    if (this.intentionalClose) return;
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this._setStatus('DISCONNECTED');
      return;
    }

    this._setStatus('RECONNECTING');
    const delay = Math.min(
      RECONNECT_BASE_DELAY_MS * Math.pow(1.5, this.reconnectAttempts),
      RECONNECT_MAX_DELAY_MS,
    );
    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => this._establishConnection(), delay);
  }

  private _startHeartbeat(): void {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: 'ping' }));
        } catch {
          // send failed, reconnect will happen via onclose
        }
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private _cleanup(): void {
    this._stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.onopen = null;
        this.ws.onmessage = null;
        this.ws.onclose = null;
        this.ws.onerror = null;
        if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
          this.ws.close();
        }
      } catch {
        // ignore
      }
      this.ws = null;
    }
  }

  private _setStatus(newStatus: WsConnectionStatus): void {
    if (this.status === newStatus) return;
    this.status = newStatus;
    this.statusListeners.forEach((cb) => {
      try {
        cb(newStatus);
      } catch {
        // listener error silenced
      }
    });
  }

  /**
   * On reconnect, query the REST API for active alerts to catch any events
   * missed during the disconnection window. Only queries DB-backed alerts.
   */
  private async _reconcileMissedAlerts(): Promise<void> {
    try {
      const res = await fetchAlerts('ACTIVE', 20);
      if (res?.data?.alerts) {
        // Emit synthetic reconciliation events for any active alerts
        for (const alert of res.data.alerts) {
          const reconciliationEvent: RealtimeAlertEvent = {
            event: 'ALERT_RECONCILED',
            data: {
              alert_id: alert.id,
              severity: alert.severity,
              location: {
                latitude: alert.latitude,
                longitude: alert.longitude,
              },
              created_at: alert.created_at,
              source: 'RECONCILIATION',
            },
          };
          this.eventListeners.forEach((cb) => {
            try {
              cb(reconciliationEvent);
            } catch {
              // listener error silenced
            }
          });
        }
      }
    } catch {
      // Reconciliation is best-effort; connection is already live
    }
  }
}

// ---------------------------------------------------------------------------
// Singleton instance
// ---------------------------------------------------------------------------

export const realtimeClient = new RealtimeClient();
