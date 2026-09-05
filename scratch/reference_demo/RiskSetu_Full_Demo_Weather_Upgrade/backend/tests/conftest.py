import os
import tempfile
from pathlib import Path
import pytest

test_dir=tempfile.TemporaryDirectory(prefix='risksetu-tests-')
os.environ['DATA_MODE']='mock'
os.environ['RISKSETU_DB_PATH']=str(Path(test_dir.name)/'test.sqlite3')
os.environ['RISKSETU_MEDIA_DIR']=str(Path(test_dir.name)/'uploads')

@pytest.fixture()
def client():
    from app.api import app,limits
    from app.store import repo
    from fastapi.testclient import TestClient
    with repo.connect() as c: c.execute('DELETE FROM records')
    limits.clear()
    with TestClient(app) as c:
        yield c

@pytest.fixture()
def identities(client):
    result={}
    for role in ('citizen','officer','admin'):
        r=client.post('/api/auth/login',json={'email':role+'@risksetu.demo','password':'RiskSetuDemo!2026'})
        assert r.status_code==200,r.text
        result[role]={'Authorization':'Bearer '+r.json()['access_token']}
    return result
