"""Durable local demo store and Supabase REST repository. All filters are server-owned."""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
import httpx
from app import config
from app.settings_values import supabase_service_headers

def now():
    return datetime.now(timezone.utc).isoformat()

class Repository:
    def __init__(self):
        self.lock = threading.RLock()
        if config.DATA_MODE == 'mock':
            with self.connect() as c:
                c.execute('CREATE TABLE IF NOT EXISTS records (collection TEXT, id TEXT, data TEXT NOT NULL, PRIMARY KEY(collection,id))')

    def connect(self):
        return sqlite3.connect(config.DB_PATH, timeout=20)

    def remote(self, method, table, **kwargs):
        headers = {**supabase_service_headers(config.SUPABASE_SERVICE_ROLE_KEY),
                   'Prefer': 'return=representation'}
        with httpx.Client(timeout=20) as client:
            response = client.request(method, f'{config.SUPABASE_URL}/rest/v1/{table}', headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else []

    def all(self, table):
        if config.DATA_MODE == 'live':
            rows, offset = [], 0
            while True:
                page = self.remote('GET', table, params={'select': '*', 'order': 'id', 'limit': 500, 'offset': offset})
                rows.extend(page)
                if len(page) < 500:
                    return rows
                offset += len(page)
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute('SELECT data FROM records WHERE collection=?', (table,))]

    def get(self, table, key):
        if config.DATA_MODE == 'live':
            rows = self.remote('GET', table, params={'id': f'eq.{key}', 'select': '*'})
            return rows[0] if rows else None
        with self.connect() as c:
            row = c.execute('SELECT data FROM records WHERE collection=? AND id=?', (table, key)).fetchone()
            return json.loads(row[0]) if row else None

    def insert(self, table, data):
        item = {'id': str(uuid.uuid4()), 'created_at': now(), **data}
        if config.DATA_MODE == 'live':
            return self.remote('POST', table, json=item)[0]
        with self.lock, self.connect() as c:
            c.execute('INSERT INTO records VALUES (?,?,?)', (table, item['id'], json.dumps(item)))
        return item

    def update(self, table, key, changes):
        if config.DATA_MODE == 'live':
            rows = self.remote('PATCH', table, params={'id': f'eq.{key}'}, json=changes)
            return rows[0] if rows else None
        with self.lock, self.connect() as c:
            row = c.execute('SELECT data FROM records WHERE collection=? AND id=?', (table, key)).fetchone()
            if not row:
                return None
            item = {**json.loads(row[0]), **changes}
            c.execute('UPDATE records SET data=? WHERE collection=? AND id=?', (json.dumps(item), table, key))
        return item

repo = Repository()
