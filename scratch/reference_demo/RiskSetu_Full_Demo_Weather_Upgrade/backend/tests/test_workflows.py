import io
from uuid import uuid4
from PIL import Image
from app.store import repo,now
from app.services.routes import score_route
from app.services.risk_engine import calculate_risk

def report(client,headers,**kwargs):
    return client.post('/api/incidents',headers=headers,json={'latitude':25.61,'longitude':91.92,'type':'Falling rocks','description':'Rocks on the hillside road after rainfall.','severity':'HIGH','client_id':str(uuid4()),**kwargs})

def test_legacy_compatibility_and_invalid_inputs(client):
    assert client.get('/health').json()['status']=='ok'
    body={'latitude':25.58,'longitude':91.89,'rainfall_24h_mm':150,'rainfall_72h_mm':310,'soil_moisture_pct':82,'slope_deg':38,'historical_landslides':5,'susceptibility':.8}
    response=client.post('/risk/predict',json=body)
    assert response.status_code==200
    assert response.json()['risk_score']==73.2
    assert response.json()['landslide_probability'] is None
    assert not response.json()['operational_warning']
    assert client.post('/risk/predict',json={**body,'latitude':91}).status_code==422
    assert client.post('/risk/predict',json={**body,'slope_deg':-1}).status_code==422
    assert client.get('/weather/25.58/91.89').json()['data_mode']=='MOCK'
    assert client.post('/reports?latitude=25&longitude=91&description=legacy').json()['accepted']

def test_permissions_and_role_injection(client,identities):
    assert client.get('/api/officer/overview').status_code==401
    assert client.get('/api/officer/overview',headers=identities['citizen']).status_code==403
    assert client.get('/api/officer/overview',headers=identities['officer']).status_code==200
    assert client.post('/api/auth/signup',json={'email':'evil@test.invalid','password':'longpassword123','full_name':'Test','role':'admin'}).status_code==422
    assert client.patch('/api/profiles/me',headers=identities['citizen'],json={'full_name':'Test','preferred_language':'en','role':'admin'}).status_code==422

def test_report_persistence_idempotency_and_privacy(client,identities):
    key=str(uuid4()); first=report(client,identities['citizen'],client_id=key)
    assert first.status_code==200,first.text
    again=report(client,identities['citizen'],client_id=key)
    assert again.json()['id']==first.json()['id']
    assert report(client,identities['officer'],client_id=key).status_code==409
    assert repo.get('incidents',first.json()['id'])['description']
    public=client.get('/api/incidents').json()['items']
    assert all('reporter_id' not in i and 'client_id' not in i for i in public)

def test_confirmation_limits_and_no_auto_verification(client,identities):
    incident=report(client,identities['citizen']).json(); key=incident['id']
    body={'latitude':incident['latitude'],'longitude':incident['longitude'],'confirmation':'YES'}
    assert client.post(f'/api/incidents/{key}/confirm',headers=identities['citizen'],json=body).status_code==409
    assert client.post(f'/api/incidents/{key}/confirm',headers=identities['officer'],json={**body,'latitude':26}).status_code==403
    assert client.post(f'/api/incidents/{key}/confirm',headers=identities['officer'],json=body).status_code==200
    assert client.post(f'/api/incidents/{key}/confirm',headers=identities['officer'],json=body).status_code==409
    assert client.post(f'/api/incidents/{key}/confirm',headers=identities['admin'],json=body).status_code==200
    assert repo.get('incidents',key)['status']!='VERIFIED'

def test_verified_incident_cannot_be_downgraded_by_votes(client,identities):
    key=report(client,identities['citizen']).json()['id']
    endpoint=f'/api/incidents/{key}/verify'
    payload={'status':'VERIFIED','notes':'Field team confirmed the reported incident.'}
    assert client.post(endpoint,headers=identities['citizen'],json=payload).status_code==403
    assert client.post(endpoint,headers=identities['officer'],json=payload).status_code==200
    assert client.post(f'/api/incidents/{key}/confirm',headers=identities['admin'],json={'latitude':25.61,'longitude':91.92,'confirmation':'NO'}).status_code==409
    assert repo.get('incidents',key)['status']=='VERIFIED'
    assert repo.all('audit_logs')[-1]['action']=='INCIDENT_STATUS'

def test_officer_approval_only_by_admin(client,identities):
    profile=client.post('/api/profiles/request-officer',headers=identities['citizen']).json()
    endpoint='/api/admin/officer-requests/'+profile['id']
    assert client.post(endpoint,headers=identities['officer'],json={'approved':True}).status_code==403
    assert client.post(endpoint,headers=identities['admin'],json={'approved':True}).status_code==200
    assert client.get('/api/officer/overview',headers=identities['citizen']).status_code==200

def test_media_validation_and_authorization(client,identities):
    key=report(client,identities['citizen']).json()['id']
    path=f'/api/incidents/{key}/media'
    assert client.post(path,headers=identities['citizen'],files={'file':('evil.png',b'not an image','image/png')}).status_code==422
    stream=io.BytesIO(); Image.new('RGB',(10,10)).save(stream,format='PNG')
    r=client.post(path,headers=identities['citizen'],files={'file':('evidence.png',stream.getvalue(),'image/png')})
    assert r.status_code==200,r.text
    assert r.json()['ai_analysis']['data_mode']=='MOCK'
    media_id=r.json()['id']
    assert client.get('/api/media/'+media_id).status_code==401
    assert client.get('/api/media/'+media_id,headers=identities['officer']).status_code==200

def test_routes_hard_exclusion_and_coverage():
    route={'coordinates':[[91,25],[91.001,25]],'distance_m':100}
    blocked={'latitude':25,'longitude':91.0005,'status':'BLOCKED','road_identifier':'TEST'}
    result=score_route(route,[],[],[blocked])
    assert result['excluded'] and result['classification']=='AVOID ROUTE'
    unknown=score_route(route,[],[],[])
    assert not unknown['assessment_complete'] and unknown['classification']=='CAUTION ROUTE'
    zone={'latitude':25,'longitude':91,'risk_score':25,'risk_level':'LOW','radius_m':1000,'updated_at':now()}
    covered=score_route(route,[zone],[],[])
    assert covered['coverage']==1 and covered['route_risk_score']==25
    critical={'latitude':25,'longitude':91,'status':'PENDING','severity':'CRITICAL','type':'Landslide'}
    assert score_route(route,[zone],[critical],[])['excluded']

def test_route_api_and_road_update(client,identities):
    req={'origin':{'latitude':25.57,'longitude':91.89},'destination':{'latitude':25.59,'longitude':91.90}}
    assert client.post('/api/routes/safe',json=req).status_code==401
    response=client.post('/api/routes/safe',headers=identities['citizen'],json=req)
    assert response.status_code==200,response.text
    assert len(response.json()['routes'])==3
    assert all(r['data_mode']=='MOCK' for r in response.json()['routes'])
    road={'latitude':25.58,'longitude':91.9,'road_identifier':'test-road','status':'BLOCKED','risk_score':100}
    assert client.post('/api/roads',headers=identities['citizen'],json=road).status_code==403
    first=client.post('/api/roads',headers=identities['officer'],json=road).json()
    second=client.post('/api/roads',headers=identities['officer'],json={**road,'status':'OPEN'}).json()
    assert first['id']==second['id'] and len(repo.all('road_hazards'))==1

def test_shelter_capacity_and_unknown_risk(client,identities):
    assert client.get('/api/shelters/nearby?latitude=25.58&longitude=91.89').json()['items']==[]
    s={'name':'Verified test shelter','latitude':26.1445,'longitude':91.7362,'capacity':10,'current_occupancy':11,'contact':'Test contact','district':'Kamrup','state':'Assam','verified':True,'active':True}
    assert client.post('/api/shelters',headers=identities['officer'],json=s).status_code==422
    s['current_occupancy']=2
    assert client.post('/api/shelters',headers=identities['citizen'],json=s).status_code==403
    key=client.post('/api/shelters',headers=identities['officer'],json=s).json()['id']
    assert client.get('/api/shelters/nearby?latitude=26.1445&longitude=91.7362').json()['items'][0]['available_capacity']==8
    client.patch('/api/shelters/'+key,headers=identities['officer'],json={**s,'current_occupancy':10})
    assert client.get('/api/shelters/nearby?latitude=26.1445&longitude=91.7362').json()['items']==[]

def test_notifications_are_private(client,identities):
    client.post('/api/location',headers=identities['officer'],json={'latitude':25.594,'longitude':91.884})
    notifications=client.get('/api/notifications',headers=identities['officer']).json()['items']
    assert notifications
    assert client.post('/api/notifications/'+notifications[0]['id']+'/read',headers=identities['citizen']).status_code==404
    assert client.post('/api/notifications/'+notifications[0]['id']+'/read',headers=identities['officer']).status_code==200

def test_dispatch_and_briefing(client,identities):
    key=report(client,identities['citizen']).json()['id']
    r=client.post('/api/incidents/'+key+'/dispatch',headers=identities['officer'],json={'assigned_team':'District team','priority':'HIGH','instructions':'Arrange expert assessment through control room.'})
    assert r.status_code==200
    assert client.post('/api/dispatches/'+r.json()['id']+'/complete',headers=identities['officer']).json()['status']=='COMPLETED'
    briefing=client.get('/api/incidents/'+key+'/briefing',headers=identities['officer'])
    assert briefing.status_code==200,briefing.text
    assert briefing.json()['data_mode']=='MOCK' and 'weather' in briefing.json()['context']

def test_inventory_parser(tmp_path):
    from app.integrations.gsi import normalize_file
    path=tmp_path/'inventory.csv'
    path.write_text('latitude,longitude,event_date,district,state\n25.5,91.8,2024-01-02,Test,Assam\n25.5,91.8,2024-01-02,Test,Assam\n')
    rows=normalize_file(path)
    assert rows[0]['external_id']==rows[1]['external_id']
    assert rows[0]['data_mode']=='CACHED'

def test_logout_revokes_session(client,identities):
    assert client.post('/api/auth/logout',headers=identities['citizen']).status_code==200
    assert client.get('/api/auth/me',headers=identities['citizen']).status_code==401
