import os
from pathlib import Path
from dotenv import load_dotenv
from app.settings_values import parse_data_mode, supabase_keys

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
load_dotenv(ROOT / 'backend' / '.env', override=False)
DATA_MODE = parse_data_mode(os.getenv('DATA_MODE'))
SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY = supabase_keys(os.environ)
DB_PATH = os.getenv('RISKSETU_DB_PATH', str(ROOT / 'backend' / 'risksetu.sqlite3'))
MEDIA_DIR = Path(os.getenv('RISKSETU_MEDIA_DIR', str(ROOT / 'backend' / 'uploads')))
if DATA_MODE == 'live' and not all([SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY]):
    raise RuntimeError('Live mode requires all Supabase server settings; no mock fallback is permitted.')

def provenance(source, mode=None):
    from datetime import datetime, timezone
    return {'source': source, 'data_mode': (mode or DATA_MODE).upper(),
            'updated_at': datetime.now(timezone.utc).isoformat()}
