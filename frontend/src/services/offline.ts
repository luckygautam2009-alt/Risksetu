/**
 * RISKSETU AI — Offline persistence and synchronization service.
 *
 * Uses native browser IndexedDB for zero-dependency local storage:
 *   - 'sos' store: queues offline emergency SOS requests.
 *   - 'reports' store: queues offline citizen ground reports.
 *   - 'cache' store: holds static snapshots of last known assessments.
 *
 * Automatically triggers synchronization when online connectivity is restored.
 */
import { createSos, submitGroundReport } from './api';

export interface PendingReport {
  id: string;
  reportType: string;
  description: string;
  severity: string;
  latitude: number;
  longitude: number;
  observedAt: string;
  createdAt: string;
  error?: string;
  status: 'QUEUED_OFFLINE' | 'SYNC_FAILED';
}

export interface PendingSOS {
  id: string;
  latitude: number;
  longitude: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  description?: string;
  createdAt: string;
  error?: string;
  status: 'QUEUED_OFFLINE' | 'SYNC_FAILED';
}

const DB_NAME = 'risksetu-local';
const DB_VERSION = 2;

function getDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB not supported'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('reports')) {
        db.createObjectStore('reports', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('sos')) {
        db.createObjectStore('sos', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('cache')) {
        db.createObjectStore('cache', { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// ---------------------------------------------------------------------------
// SOS Queue
// ---------------------------------------------------------------------------

export async function queueSOS(item: PendingSOS): Promise<void> {
  const db = await getDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('sos', 'readwrite');
    const store = tx.objectStore('sos');
    const req = store.put(item);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function getQueuedSOS(): Promise<PendingSOS[]> {
  try {
    const db = await getDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('sos', 'readonly');
      const store = tx.objectStore('sos');
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result as PendingSOS[]);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return [];
  }
}

export async function removeQueuedSOS(id: string): Promise<void> {
  const db = await getDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('sos', 'readwrite');
    const store = tx.objectStore('sos');
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

// ---------------------------------------------------------------------------
// Reports Queue
// ---------------------------------------------------------------------------

export async function queueReport(item: PendingReport): Promise<void> {
  const db = await getDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('reports', 'readwrite');
    const store = tx.objectStore('reports');
    const req = store.put(item);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function getQueuedReports(): Promise<PendingReport[]> {
  try {
    const db = await getDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('reports', 'readonly');
      const store = tx.objectStore('reports');
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result as PendingReport[]);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return [];
  }
}

export async function removeQueuedReport(id: string): Promise<void> {
  const db = await getDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('reports', 'readwrite');
    const store = tx.objectStore('reports');
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

// ---------------------------------------------------------------------------
// General Cache
// ---------------------------------------------------------------------------

export async function setLocalCache(key: string, value: unknown): Promise<void> {
  try {
    const db = await getDB();
    const entry = { key, value, savedAt: new Date().toISOString() };
    return new Promise((resolve, reject) => {
      const tx = db.transaction('cache', 'readwrite');
      const store = tx.objectStore('cache');
      const req = store.put(entry);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch {
    // Ignore cache failure
  }
}

export async function getLocalCache<T>(key: string): Promise<{ value: T; savedAt: string } | null> {
  try {
    const db = await getDB();
    return new Promise((resolve) => {
      const tx = db.transaction('cache', 'readonly');
      const store = tx.objectStore('cache');
      const req = store.get(key);
      req.onsuccess = () => {
        if (req.result) resolve(req.result as { value: T; savedAt: string });
        else resolve(null);
      };
      req.onerror = () => resolve(null);
    });
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Synchronization
// ---------------------------------------------------------------------------

let isSyncing = false;

export async function syncOfflineQueue(): Promise<{
  sosSynced: number;
  reportsSynced: number;
  errors: string[];
}> {
  if (isSyncing || typeof navigator === 'undefined' || !navigator.onLine) {
    return { sosSynced: 0, reportsSynced: 0, errors: [] };
  }

  isSyncing = true;
  let sosSynced = 0;
  let reportsSynced = 0;
  const errors: string[] = [];

  try {
    // 1. Sync queued SOS requests
    const queuedSOSList = await getQueuedSOS();
    for (const item of queuedSOSList) {
      try {
        await createSos({ latitude: item.latitude, longitude: item.longitude, severity: item.severity, description: item.description });
        await removeQueuedSOS(item.id);
        sosSynced++;
      } catch (err: any) {
        item.status = 'SYNC_FAILED';
        item.error = err?.message || 'Sync failed';
        await queueSOS(item);
        errors.push(`SOS (${item.id.slice(0, 8)}): ${item.error}`);
      }
    }

    // 2. Sync queued Citizen Ground Reports
    const queuedRepList = await getQueuedReports();
    for (const rep of queuedRepList) {
      try {
        await submitGroundReport({
          report_type: rep.reportType,
          description: rep.description,
          latitude: rep.latitude,
          longitude: rep.longitude,
          observed_at: rep.observedAt,
        });
        await removeQueuedReport(rep.id);
        reportsSynced++;
      } catch (err: any) {
        rep.status = 'SYNC_FAILED';
        rep.error = err?.message || 'Report sync failed';
        await queueReport(rep);
        errors.push(`Report (${rep.reportType}): ${rep.error}`);
      }
    }
  } finally {
    isSyncing = false;
  }

  return { sosSynced, reportsSynced, errors };
}
