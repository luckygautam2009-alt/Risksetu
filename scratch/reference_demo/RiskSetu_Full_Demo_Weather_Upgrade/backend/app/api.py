import asyncio
import io
import os
import time
from contextlib import asynccontextmanager
from collections import defaultdict,deque
from datetime import datetime,timezone,timedelta
from uuid import uuid4
import httpx
from PIL import Image
from fastapi import FastAPI,Depends,File,HTTPException,Request,UploadFile,Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse,JSONResponse,FileResponse
from app import config
from app.settings_values import supabase_service_headers
from app.auth import admin,create_user,current_user,demo_seed,issue_session,officer,password_hash,public_profile
from app.integrations import bhuvan,gemini,imerg,terrain as terrain_api,flood as flood_api
from app.integrations.weather import current as current_weather
from app.models import Approval,Confirmation,Dispatch,IncidentCreate,Location,Login,ProfileUpdate,RiskRequest,RoadUpdate,RouteRequest,Shelter,Signup,Verify,SOSCreate,SOSUpdate,OfficerMassAlert
from app.seed import seed,seed_emergency_resources
from app.services.events import audit,nearby_notifications,notify,publish,stream,MESSAGES
from app.services.geo import distance,nearby
from app.services.risk_engine import calculate_risk,calculate_multi_risk,safety_guidance
from app.services.routes import safe_routes,fresh
from app.services.regional import scan as regional_scan,relevant as regional_relevant
from app.services.ml_runtime import predict as ml_predict
from app.services.osint import scan as osint_scan
from app.store import now,repo

@asynccontextmanager
async def lifespan(app):
    demo_seed(); seed(); seed_emergency_resources()
    yield

app=FastAPI(title='RiskSetu API',version='1.0.0',docs_url='/api/docs',redoc_url=None,lifespan=lifespan)

# Allow RiskSetu frontend during local development.
# Vite may start on 5173, 5174, 5175, etc.
default_origins = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
    'http://localhost:5175',
    'http://127.0.0.1:5175',
    'http://localhost:5176',
    'http://127.0.0.1:5176',
]

env_origins = [
    origin.strip()
    for origin in os.getenv('CORS_ORIGINS', '').split(',')
    if origin.strip()
]

allowed_origins = list(dict.fromkeys(default_origins + env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=['GET','POST','PATCH','PUT','DELETE','OPTIONS'],
    allow_headers=['*'],
)
limits=defaultdict(deque)
mutation_lock=asyncio.Lock()

@app.middleware('http')
async def headers_and_rate_limit(request:Request,call_next):
    if request.method not in {'GET','HEAD','OPTIONS'}:
        key=f"{request.client.host if request.client else 'local'}:{'auth' if '/auth/' in request.url.path else 'write'}"
        t=time.time(); bucket=limits[key]
        while bucket and bucket[0]<t-60: bucket.popleft()
        if len(bucket)>=(15 if key.endswith('auth') else 60): return JSONResponse({'detail':'Rate limit exceeded; try again shortly'},429)
        bucket.append(t)
    try: content_length=int(request.headers.get('content-length','0'))
    except ValueError: return JSONResponse({'detail':'Invalid Content-Length'},400)
    if content_length>6*1024*1024: return JSONResponse({'detail':'Request too large'},413)
    response=await call_next(request)
    response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Cache-Control':'no-store'})
    return response

@app.exception_handler(httpx.HTTPError)
async def provider_error(request,exc): return JSONResponse({'detail':'External provider unavailable. Check server configuration.'},503)

def find_email(email): return next((p for p in repo.all('profiles') if p['email'].lower()==email.lower()),None)
def incident_or_404(key):
    item=repo.get('incidents',key)
    if not item: raise HTTPException(404,'Incident not found')
    return item
def checked_location(lat,lon):
    if not (-90<=lat<=90 and -180<=lon<=180): raise HTTPException(422,'Invalid coordinates')
    return {'latitude':lat,'longitude':lon}
def query_nearby(table,lat,lon,radius): return nearby(repo.all(table),checked_location(lat,lon),max(0,min(radius,1000000)))
def public_incident(item): return {k:v for k,v in item.items() if k not in {'reporter_id','client_id','verified_by'}}

@app.get('/health')
@app.get('/api/health')
def health(): return {'status':'ok','product':'RiskSetu',**config.provenance('RiskSetu API')}

@app.get('/api/config')
def public_config():
    return {'data_mode':config.DATA_MODE.upper(),'supabase_url':config.SUPABASE_URL if config.DATA_MODE=='live' else '',
        'supabase_anon_key':config.SUPABASE_ANON_KEY if config.DATA_MODE=='live' else '',
        'confirmation_radius_m':1000,'max_media_bytes':5242880,
        'weather_primary':'Open-Meteo','weather_fallback':'IndianAPI','imerg_configured':imerg.configured(),
        'maps':'OpenStreetMap','routing':'OSRM'}

@app.post('/api/auth/signup')
async def signup(body:Signup):
    if len(body.password)<10 or '@' not in body.email: raise HTTPException(422,'Enter a valid email and a password with at least 10 characters')
    async with mutation_lock:
        if find_email(body.email): raise HTTPException(409,'Account already exists')
        if config.DATA_MODE=='live':
            async with httpx.AsyncClient(timeout=15) as client:
                r=await client.post(f'{config.SUPABASE_URL}/auth/v1/signup',headers={'apikey':config.SUPABASE_ANON_KEY},json={'email':body.email,'password':body.password,'data':{'full_name':body.full_name}})
            if r.status_code>=400: raise HTTPException(400,'Signup failed; check email and password requirements')
            return {'message':'Check your email to complete signup.'}
        return issue_session(create_user(body.email,body.password,body.full_name))

@app.post('/api/auth/login')
def login(body:Login):
    if config.DATA_MODE=='live':
        with httpx.Client(timeout=15) as client:
            r=client.post(f'{config.SUPABASE_URL}/auth/v1/token?grant_type=password',headers={'apikey':config.SUPABASE_ANON_KEY},json=body.model_dump())
        if r.status_code!=200: raise HTTPException(401,'Invalid email or password')
        return r.json()
    profile=find_email(body.email)
    if not profile or not __import__('hmac').compare_digest(profile['password_hash'],password_hash(body.password,profile['salt'])):
        raise HTTPException(401,'Invalid email or password')
    return issue_session(profile)

@app.post('/api/auth/logout')
def logout(request:Request,user=Depends(current_user)):
    from app.auth import sessions
    token=request.headers.get('authorization','').removeprefix('Bearer ')
    if config.DATA_MODE=='mock': sessions.pop(token,None)
    else:
        with httpx.Client(timeout=15) as client:
            client.post(f'{config.SUPABASE_URL}/auth/v1/logout',headers={'apikey':config.SUPABASE_ANON_KEY,'Authorization':f'Bearer {token}'}).raise_for_status()
    return {'signed_out':True}

@app.get('/api/auth/me')
def me(user=Depends(current_user)): return user

@app.patch('/api/profiles/me')
def profile_update(body:ProfileUpdate,user=Depends(current_user)):
    return public_profile(repo.update('profiles',user['id'],body.model_dump()))

@app.post('/api/profiles/request-officer')
def request_officer(user=Depends(current_user)):
    return public_profile(repo.update('profiles',user['id'],{'officer_requested':True}))

@app.get('/api/admin/officer-requests')
def officer_requests(user=Depends(admin)):
    return [public_profile(p) for p in repo.all('profiles') if p.get('officer_requested')]

@app.post('/api/admin/officer-requests/{user_id}')
def approve_officer(user_id:str,body:Approval,user=Depends(admin)):
    target=repo.get('profiles',user_id)
    if not target or target['role']=='admin': raise HTTPException(400,'Invalid approval target')
    result=repo.update('profiles',user_id,{'role':'officer' if body.approved else 'citizen','officer_verified':body.approved,'officer_requested':False})
    audit(user,'OFFICER_APPROVAL',user_id,{'approved':body.approved}); return public_profile(result)

@app.post('/risk/predict')
@app.post('/api/risk/predict')
def predict(req:RiskRequest): return {**calculate_risk(req.model_dump()),**config.provenance('RiskSetu transparent baseline')}


@app.get('/api/risk/current')
async def current_risk(latitude:float,longitude:float):
    checked_location(latitude,longitude)
    weather_data=None
    try:
        weather_data=await current_weather(latitude,longitude)
    except HTTPException:
        weather_data=None
    terrain_data,flood_data=await asyncio.gather(terrain_api.terrain(latitude,longitude),flood_api.discharge(latitude,longitude))
    nearby_history=query_nearby('historical_landslides',latitude,longitude,25000)
    real_history=[h for h in nearby_history if str(h.get('data_mode','')).upper()!='MOCK']
    history_signal=real_history if real_history else nearby_history
    nearby_incidents=[i for i in query_nearby('incidents',latitude,longitude,10000) if i.get('status') not in {'REJECTED','RESOLVED'}]
    nearby_zones=query_nearby('risk_zones',latitude,longitude,10000)
    zone=nearby_zones[0] if nearby_zones else None
    features={}
    if weather_data:
        windows=weather_data.get('forecast_windows') or []
        forecast6=sum(float(w.get('precipitation_mm') or 0) for w in windows if int(w.get('hours') or 0)<=6) if windows else None
        features.update({
            'rainfall_24h_mm':weather_data.get('rainfall_24h'),
            'rainfall_72h_mm':weather_data.get('rainfall_72h'),
            'soil_moisture_pct':weather_data.get('soil_moisture_pct'),
            'satellite_rainfall_24h_mm':weather_data.get('satellite_rainfall_24h'),
            'forecast_rain_6h_mm':round(forecast6,1) if forecast6 is not None else None,
        })
    if terrain_data:
        features['slope_deg']=terrain_data.get('slope_deg')
        features['elevation_m']=terrain_data.get('elevation_m')
    if zone:
        zf=zone.get('features') or {}
        # Susceptibility may come from an imported/verified zone, but terrain is now sourced independently.
        features['susceptibility']=zf.get('susceptibility')
    features['historical_landslides']=len(history_signal) if history_signal else None
    signal=0
    for item in nearby_incidents:
        signal += 30 if item.get('status')=='VERIFIED' else 18 if item.get('severity') in {'HIGH','CRITICAL'} else 8
    features['citizen_signal_score']=min(100,signal) if nearby_incidents else 0
    if flood_data:
        features['flood_signal_score']=flood_data.get('flood_signal_score')
    risk=calculate_multi_risk(features)
    ml=ml_predict({
        'rainfall_24h_mm':features.get('rainfall_24h_mm'),
        'rainfall_72h_mm':features.get('rainfall_72h_mm'),
        'soil_moisture_pct':features.get('soil_moisture_pct'),
        'slope_deg':features.get('slope_deg'),
        'historical_landslides':features.get('historical_landslides'),
        'susceptibility':features.get('susceptibility'),
    })
    regional_events=regional_relevant(await regional_scan(),latitude,longitude)
    elevated_regional=any(e.get('severity') in {'WARNING','EMERGENCY'} for e in regional_events)
    guidance=safety_guidance(risk.get('risk_level'),features.get('rainfall_24h_mm'),elevated_regional)
    return {**risk,'guidance':guidance,'weather':weather_data,'terrain':terrain_data,'flood_context':flood_data,'ml':ml,'regional_alerts':regional_events,
        'nearby_active_incidents':len(nearby_incidents),'nearby_history_count':len(history_signal),'historical_source':'NASA/imported' if real_history else ('DEMO' if nearby_history else 'UNAVAILABLE'),
        'coverage_note':'Uses free weather/soil-moisture proxy, DEM terrain and GloFAS river context when available. Missing values are not fabricated.',
        **config.provenance('RiskSetu free multi-source assessment')}

@app.get('/api/regional-hazards')
async def regional_hazards():
    return {'items':await regional_scan(),**config.provenance('RiskSetu regional rainfall screening')}

@app.get('/api/regional-hazards/impact')
async def regional_impact(latitude:float,longitude:float):
    checked_location(latitude,longitude)
    items=regional_relevant(await regional_scan(),latitude,longitude)
    return {'items':items,'message':'Regional rainfall screening only; downstream flood impact requires hydrological/official data.',**config.provenance('RiskSetu regional screening')}

@app.post('/api/sos')
async def create_sos(body:SOSCreate,user=Depends(current_user)):
    async with mutation_lock:
        duplicate=next((x for x in repo.all('sos_events') if x.get('client_id')==body.client_id and x.get('user_id')==user['id']),None)
        if duplicate: return duplicate
        resources=query_nearby('emergency_resources',body.latitude,body.longitude,100000)[:8]
        item=repo.insert('sos_events',{**body.model_dump(),'user_id':user['id'],'status':'ACTIVE','assigned_officer_id':None,
            'nearest_resources':resources,**config.provenance('User SOS')})
        for p in repo.all('profiles'):
            if p.get('role') in {'officer','admin'} and p.get('officer_verified'):
                notify(p['id'],None,'SOS','ACTIVE SOS',f"{user.get('full_name','A user')} requested emergency help at {body.latitude:.5f}, {body.longitude:.5f}.",'EMERGENCY')
        publish('sos')
        return item

@app.get('/api/sos/{key}')
def get_sos(key:str,user=Depends(current_user)):
    item=repo.get('sos_events',key)
    if not item: raise HTTPException(404,'SOS not found')
    if item.get('user_id')!=user['id'] and not (user.get('role') in {'officer','admin'} and user.get('officer_verified')): raise HTTPException(403,'Not permitted')
    return item

@app.get('/api/officer/sos')
def officer_sos(user=Depends(officer)):
    rank={'ACTIVE':4,'ACKNOWLEDGED':3,'DISPATCHED':2,'RESOLVED':1,'CANCELLED':0}
    items=sorted(repo.all('sos_events'),key=lambda x:(rank.get(x.get('status'),0),x.get('created_at','')),reverse=True)
    return {'items':items}

@app.patch('/api/officer/sos/{key}')
def update_sos(key:str,body:SOSUpdate,user=Depends(officer)):
    if not repo.get('sos_events',key): raise HTTPException(404,'SOS not found')
    changes=body.model_dump(); changes['assigned_officer_id']=changes.get('assigned_officer_id') or user['id']; changes['updated_at']=now()
    item=repo.update('sos_events',key,changes); audit(user,'SOS_STATUS',key,changes); publish('sos'); return item

@app.get('/api/emergency/resources')
def emergency_resources(latitude:float,longitude:float,radius_m:int=100000):
    checked_location(latitude,longitude)
    return {'items':query_nearby('emergency_resources',latitude,longitude,min(radius_m,300000)),
            'national_contacts':[{'name':'India Emergency Response Support System','number':'112','type':'EMERGENCY'}, {'name':'Ambulance','number':'108','type':'AMBULANCE'}],
            'message':'Nearest facilities are shown only when a verified/configured resource dataset is available.'}

@app.get('/api/risk/nearby')
def risks(latitude:float=25.5788,longitude:float=91.8933,radius_m:int=1000000):
    return {'items':query_nearby('risk_zones',latitude,longitude,radius_m),**config.provenance('RiskSetu repository')}

@app.get('/weather/{lat}/{lon}')
async def legacy_weather(lat:float,lon:float):
    checked_location(lat,lon); return await current_weather(lat,lon)

@app.get('/api/weather/current')
async def weather(latitude:float,longitude:float):
    checked_location(latitude,longitude); return await current_weather(latitude,longitude)

@app.get('/api/terrain/current')
def terrain(latitude:float,longitude:float):
    checked_location(latitude,longitude); return bhuvan.terrain(latitude,longitude)

@app.get('/api/landslides/history')
def history(latitude:float=25.5788,longitude:float=91.8933,radius_m:int=1000000,years:int|None=Query(None,ge=1,le=100),state:str|None=None,district:str|None=None):
    rows=query_nearby('historical_landslides',latitude,longitude,radius_m)
    if years:
        cutoff=(datetime.now(timezone.utc)-timedelta(days=365.25*years)).date()
        rows=[r for r in rows if datetime.fromisoformat(r['event_date']).date()>=cutoff]
    if state: rows=[r for r in rows if r.get('state','').lower()==state.lower()]
    if district: rows=[r for r in rows if r.get('district','').lower()==district.lower()]
    return {'items':rows,**config.provenance('RiskSetu normalized inventory')}

@app.get('/api/incidents/nearby')
@app.get('/api/incidents')
def incidents(latitude:float|None=None,longitude:float|None=None,radius_m:int=200000,status:str|None=None):
    rows=repo.all('incidents') if latitude is None or longitude is None else query_nearby('incidents',latitude,longitude,radius_m)
    if status: rows=[r for r in rows if r['status']==status]
    return {'items':[public_incident(x) for x in sorted(rows,key=lambda x:x['created_at'],reverse=True)],**config.provenance('RiskSetu incidents')}

@app.post('/api/incidents')
async def create_incident(body:IncidentCreate,user=Depends(current_user)):
    async with mutation_lock:
        duplicate=next((x for x in repo.all('incidents') if x.get('client_id')==body.client_id),None)
        if duplicate:
            if duplicate['reporter_id']!=user['id']: raise HTTPException(409,'Client report identifier already used')
            return public_incident(duplicate)
        if any(i['reporter_id']==user['id'] and distance(i,body.model_dump())<50 and i['type']==body.type and i['status'] not in {'REJECTED','RESOLVED'} for i in repo.all('incidents')):
            raise HTTPException(409,'A nearby active report of this type already exists')
        item=repo.insert('incidents',{**body.model_dump(),'status':'PENDING','reporter_id':user['id'],'confirmation_count':0,
            'community_confidence_score':0,**config.provenance('Citizen')})
    nearby_notifications(item); publish('new_incident'); return public_incident(item)

@app.post('/reports')
async def legacy_report(latitude:float,longitude:float,description:str='',media:UploadFile|None=File(None)):
    checked_location(latitude,longitude)
    return {'accepted':True,'latitude':latitude,'longitude':longitude,'description':description,'filename':media.filename if media else None,'status':'pending_verification','persisted':False,'deprecated':'Use authenticated /api/incidents for persistent reporting'}

@app.post('/api/incidents/{key}/media')
async def upload_media(key:str,file:UploadFile=File(...),user=Depends(current_user)):
    incident=incident_or_404(key)
    if incident['reporter_id']!=user['id']: raise HTTPException(403,'Only the reporter may upload evidence')
    if file.content_type not in {'image/jpeg','image/png','image/webp','video/mp4'}: raise HTTPException(415,'JPEG, PNG, WebP or MP4 only')
    data=await file.read(5*1024*1024+1)
    if len(data)>5*1024*1024: raise HTTPException(413,'Media must be no larger than 5 MB')
    if file.content_type=='video/mp4':
        if len(data)<12 or data[4:8]!=b'ftyp': raise HTTPException(422,'Invalid MP4 container')
        ext='mp4'
    else:
        try:
            img=Image.open(io.BytesIO(data)); img.verify()
            formats={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}
            if formats.get(img.format)!=file.content_type: raise ValueError()
            # Re-encode to strip EXIF/GPS and reject decompression bombs.
            img=Image.open(io.BytesIO(data)); img.thumbnail((2400,2400)); cleaned=io.BytesIO()
            img.convert('RGB').save(cleaned,format='JPEG',quality=88); data=cleaned.getvalue(); ext='jpg'
        except Exception: raise HTTPException(422,'Invalid or oversized image')
    mime='video/mp4' if ext=='mp4' else 'image/jpeg'
    name=f"{user['id']}/{key}/{uuid4()}.{ext}"
    if config.DATA_MODE=='live':
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.post(f'{config.SUPABASE_URL}/storage/v1/object/incident-media/{name}',headers={**supabase_service_headers(config.SUPABASE_SERVICE_ROLE_KEY),'Content-Type':mime},content=data); r.raise_for_status()
    else:
        target=config.MEDIA_DIR/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    record=repo.insert('incident_media',{'incident_id':key,'storage_url':name,'media_type':mime,'ai_analysis':None})
    try:
        analysis=await gemini.analyze(incident,data if ext!='mp4' else None,mime)
    except HTTPException:
        analysis={'status':'UNAVAILABLE','recommended_verification':'Officer review required; media was saved successfully.'}
    repo.update('incident_media',record['id'],{'ai_analysis':analysis}); return {**record,'ai_analysis':analysis}

@app.get('/api/incidents/{key}/media')
def list_media(key:str,user=Depends(current_user)):
    incident=incident_or_404(key)
    if incident['reporter_id']!=user['id'] and not (user['role'] in {'officer','admin'} and user.get('officer_verified')): raise HTTPException(403,'Not permitted')
    return {'items':[{**m,'storage_url':None} for m in repo.all('incident_media') if m['incident_id']==key]}

@app.get('/api/media/{key}')
def download_media(key:str,user=Depends(current_user)):
    record=repo.get('incident_media',key)
    if not record: raise HTTPException(404,'Media not found')
    incident=incident_or_404(record['incident_id'])
    if incident['reporter_id']!=user['id'] and not (user['role'] in {'officer','admin'} and user.get('officer_verified')): raise HTTPException(403,'Not permitted')
    if config.DATA_MODE=='mock': return FileResponse(config.MEDIA_DIR/record['storage_url'],media_type=record['media_type'])
    with httpx.Client(timeout=20) as client:
        r=client.post(f"{config.SUPABASE_URL}/storage/v1/object/sign/incident-media/{record['storage_url']}",headers=supabase_service_headers(config.SUPABASE_SERVICE_ROLE_KEY),json={'expiresIn':60}); r.raise_for_status()
    return {'url':config.SUPABASE_URL+'/storage/v1'+r.json()['signedURL']}

@app.post('/api/incidents/{key}/confirm')
async def confirm(key:str,body:Confirmation,user=Depends(current_user)):
    async with mutation_lock:
        incident=incident_or_404(key)
        if incident['status'] not in {'PENDING','COMMUNITY_CONFIRMED'}: raise HTTPException(409,'This incident is no longer accepting community responses')
        if user['id']==incident['reporter_id']: raise HTTPException(409,'Reporters cannot confirm their own report')
        if any(c['incident_id']==key and c['user_id']==user['id'] for c in repo.all('incident_confirmations')): raise HTTPException(409,'You already responded')
        meters=distance(body.model_dump(),incident)
        if meters>1000: raise HTTPException(403,'Confirmation requires a current location within 1 km')
        c=repo.insert('incident_confirmations',{'incident_id':key,'user_id':user['id'],'confirmation':body.confirmation,'distance_from_incident':round(meters)})
        confirmations=[x for x in repo.all('incident_confirmations') if x['incident_id']==key]
        yes=sum(x['confirmation']=='YES' for x in confirmations); no=sum(x['confirmation']=='NO' for x in confirmations)
        zones=nearby(repo.all('risk_zones'),incident,5000)
        evidence=max((z.get('risk_score',0)/100 for z in zones if fresh(z)),default=0)*.2
        score=round(max(0,min(1,.2+min(yes,4)*.13-no*.12+evidence)),2)
        status='COMMUNITY_CONFIRMED' if yes>=2 and score>=.65 else 'PENDING'
        repo.update('incidents',key,{'confirmation_count':yes,'community_confidence_score':score,'status':status})
    if status=='COMMUNITY_CONFIRMED':
        for p in repo.all('profiles'):
            if p['role'] in {'officer','admin'} and p.get('officer_verified'): notify(p['id'],key,'VERIFICATION','Community-confirmed report',f"{incident['type']} requires authorized review",'WARNING')
    publish('new_confirmation'); return c

@app.post('/api/incidents/{key}/verify')
async def verify(key:str,body:Verify,user=Depends(officer)):
    async with mutation_lock:
        incident_or_404(key); item=repo.update('incidents',key,{'status':body.status,'verified_at':now(),'verified_by':user['id'],'verification_notes':body.notes})
    audit(user,'INCIDENT_STATUS',key,body.model_dump()); publish('incident_verification'); return public_incident(item)

@app.post('/api/incidents/{key}/dispatch')
def dispatch(key:str,body:Dispatch,user=Depends(officer)):
    incident_or_404(key); item=repo.insert('dispatches',{'incident_id':key,**body.model_dump(),'status':'ASSIGNED','updated_at':now(),'assigned_by':user['id']})
    audit(user,'DISPATCH',key,body.model_dump()); publish('dispatch'); return item

@app.get('/api/officer/dispatches')
def dispatches(user=Depends(officer)): return {'items':repo.all('dispatches')}

@app.post('/api/dispatches/{key}/complete')
def complete_dispatch(key:str,user=Depends(officer)):
    if not repo.get('dispatches',key): raise HTTPException(404,'Dispatch not found')
    audit(user,'DISPATCH_COMPLETE',key,{}); return repo.update('dispatches',key,{'status':'COMPLETED','updated_at':now()})

@app.get('/api/incidents/{key}/briefing')
async def briefing(key:str,user=Depends(officer)):
    incident=incident_or_404(key)
    try: weather_data=await current_weather(incident['latitude'],incident['longitude'])
    except HTTPException: weather_data={'status':'UNAVAILABLE'}
    context={'incident':public_incident(incident),'confirmations':[{'confirmation':c['confirmation'],'distance_from_incident':c['distance_from_incident']} for c in repo.all('incident_confirmations') if c['incident_id']==key],
        'weather':weather_data,'risk_zones':nearby(repo.all('risk_zones'),incident,5000)[:3],
        'historical_landslides':nearby(repo.all('historical_landslides'),incident,5000)[:10],
        'shelters':shelters(incident['latitude'],incident['longitude'])['items'],
        'road_hazards':nearby(repo.all('road_hazards'),incident,5000)[:3]}
    return {'context':context,**await gemini.briefing(context)}

@app.post('/api/routes/safe')
async def route(body:RouteRequest,user=Depends(current_user)): return await safe_routes(body.origin.model_dump(),body.destination.model_dump())

@app.get('/api/shelters/nearby')
def shelters(latitude:float,longitude:float,radius_m:int=50000):
    rows=[s for s in query_nearby('shelters',latitude,longitude,min(radius_m,200000)) if s.get('verified') and s.get('active') and s['capacity']>s['current_occupancy']]
    safe=[]
    for s in rows:
        intersect=[z for z in repo.all('risk_zones') if distance(s,z)<=z.get('radius_m',1000)]
        if not intersect or not all(fresh(z) and z['risk_score']<55 for z in intersect): continue
        safe.append({**s,'available_capacity':s['capacity']-s['current_occupancy'],'route_assessment':'REQUIRED'})
    return {'items':safe,'message':None if safe else 'No verified shelter data currently available.',**config.provenance('Officer-verified shelter registry')}

@app.post('/api/shelters/{key}/route')
async def shelter_route(key:str,body:Location,user=Depends(current_user)):
    item=repo.get('shelters',key)
    if not item or item['id'] not in {s['id'] for s in shelters(body.latitude,body.longitude,200000)['items']}: raise HTTPException(409,'Shelter is unavailable or lacks current low-risk coverage')
    return await safe_routes(body.model_dump(),{'latitude':item['latitude'],'longitude':item['longitude']})

@app.get('/api/officer/shelters')
def all_shelters(user=Depends(officer)): return {'items':repo.all('shelters')}

@app.post('/api/shelters')
def add_shelter(body:Shelter,user=Depends(officer)):
    if body.current_occupancy>body.capacity: raise HTTPException(422,'Occupancy exceeds capacity')
    item=repo.insert('shelters',{**body.model_dump(),'verified_by':user['id'],**config.provenance('Authorized officer')}); audit(user,'SHELTER_CREATE',item['id'],{}); publish('shelter'); return item

@app.patch('/api/shelters/{key}')
def update_shelter(key:str,body:Shelter,user=Depends(officer)):
    if not repo.get('shelters',key): raise HTTPException(404,'Shelter not found')
    if body.current_occupancy>body.capacity: raise HTTPException(422,'Occupancy exceeds capacity')
    audit(user,'SHELTER_UPDATE',key,{}); return repo.update('shelters',key,{**body.model_dump(),'updated_at':now()})

@app.get('/api/roads')
def roads(): return {'items':repo.all('road_hazards')}

@app.post('/api/roads')
async def road_status(body:RoadUpdate,user=Depends(officer)):
    async with mutation_lock:
        existing=next((r for r in repo.all('road_hazards') if r['road_identifier']==body.road_identifier),None)
        if body.incident_id: incident_or_404(body.incident_id)
        data={**body.model_dump(),'geometry':{'type':'Point','coordinates':[body.longitude,body.latitude]},'updated_by':user['id'],**config.provenance('Authorized officer')}
        item=repo.update('road_hazards',existing['id'],data) if existing else repo.insert('road_hazards',data)
    audit(user,'ROAD_UPDATE',item['id'],body.model_dump()); publish('road_status'); return item

@app.post('/api/location')
async def user_location(body:Location,user=Depends(current_user)):
    async with mutation_lock:
        old=next((x for x in repo.all('user_locations') if x['user_id']==user['id']),None)
        data={**body.model_dump(),'updated_at':now()}
        item=repo.update('user_locations',old['id'],data) if old else repo.insert('user_locations',{'user_id':user['id'],**data})
    for incident in nearby(repo.all('incidents'),body.model_dump(),5000):
        if incident['status'] not in {'REJECTED','RESOLVED'}: nearby_notifications(incident)
    for zone in nearby(repo.all('risk_zones'),body.model_dump(),5000):
        if fresh(zone) and zone['risk_score']>=55:
            notify(user['id'],None,'ZONE_'+zone['id'],'Elevated area risk',MESSAGES.get(user.get('preferred_language'),MESSAGES['en']),'WARNING')
    return item

@app.get('/api/notifications')
def notifications(user=Depends(current_user)): return {'items':sorted([n for n in repo.all('notifications') if n['user_id']==user['id']],key=lambda n:n['created_at'],reverse=True)}

@app.post('/api/notifications/{key}/read')
def read_notification(key:str,user=Depends(current_user)):
    n=repo.get('notifications',key)
    if not n or n['user_id']!=user['id']: raise HTTPException(404,'Notification not found')
    return repo.update('notifications',key,{'read':True})

@app.get('/api/events')
def realtime(request:Request,user=Depends(current_user)):
    return StreamingResponse(stream(request),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})


@app.post('/api/officer/mass-alert')
def officer_mass_alert(body:OfficerMassAlert,user=Depends(officer)):
    center=body.model_dump()
    targets=[]
    cutoff=datetime.now(timezone.utc)-timedelta(hours=1)
    for loc in repo.all('user_locations'):
        try:
            if datetime.fromisoformat(loc['updated_at']) < cutoff: continue
        except Exception:
            continue
        if distance(loc,center)<=body.radius_m:
            targets.append(loc)
            notify(loc['user_id'],None,'SIREN_ALERT' if body.siren else 'OFFICER_ALERT',body.title,body.message,body.severity)
    audit(user,'MASS_ALERT','geofence',{'latitude':body.latitude,'longitude':body.longitude,'radius_m':body.radius_m,'targets':len(targets),'siren':body.siren})
    publish('mass_alert')
    return {'sent_to':len(targets),'radius_m':body.radius_m,'siren_requested':body.siren,'delivery_note':'In-app/browser siren requires the citizen device to have RiskSetu open/installed and browser notification/audio permission. This web prototype cannot override phone silent mode or trigger government cell-broadcast sirens.',**config.provenance('RiskSetu officer geofence alert')}

@app.get('/api/incidents/{key}/inspection')
async def incident_inspection(key:str,user=Depends(officer)):
    incident=incident_or_404(key)
    resources=[]
    for r in nearby(repo.all('emergency_resources'),incident,50000):
        if r.get('type')!='HOSPITAL': continue
        try:
            route_data=await safe_routes({'latitude':incident['latitude'],'longitude':incident['longitude']},{'latitude':r['latitude'],'longitude':r['longitude']})
            routes=route_data.get('routes',[])
        except Exception:
            routes=[]
        resources.append({**r,'routes':routes[:3],'recommended_route_id':next((x['id'] for x in routes if x.get('classification','').startswith(('SAFE','SAFEST'))),None)})
    return {'incident':public_incident(incident),'hospitals':resources[:3],'note':'Routes exclude known blocked/critical incident corridors and penalize mapped risk zones. Unknown coverage is not labelled safe.',**config.provenance('RiskSetu incident inspection')}

@app.get('/api/officer/intelligence')
async def officer_intelligence(user=Depends(officer)):
    return await osint_scan()

@app.post('/api/officer/intelligence/scan')
async def officer_intelligence_scan(user=Depends(officer)):
    result=await osint_scan(); audit(user,'OSINT_SCAN','public-sources',{'results':len(result.get('items',[]))}); publish('intelligence_scan'); return result

@app.get('/api/officer/overview')
def overview(user=Depends(officer)):
    incidents=repo.all('incidents'); zones=repo.all('risk_zones')
    return {'critical_zones':sum(z['risk_level']=='CRITICAL' for z in zones),'active_incidents':sum(i['status'] not in {'RESOLVED','REJECTED'} for i in incidents),
        'awaiting_verification':sum(i['status'] in {'PENDING','COMMUNITY_CONFIRMED'} for i in incidents),'road_blockages':sum(x['status']=='BLOCKED' for x in repo.all('road_hazards')),
        'population_at_risk':sum(z.get('estimated_population',0) for z in zones if z['risk_level'] in {'HIGH','CRITICAL'}),'available_shelters':sum(bool(x.get('active') and x.get('verified')) for x in repo.all('shelters')),
        'incident_queue':sorted(incidents,key=lambda x:({'CRITICAL':4,'HIGH':3,'MODERATE':2,'LOW':1}[x['severity']],x['status']=='COMMUNITY_CONFIRMED'),reverse=True),**config.provenance('RiskSetu operational repository')}

@app.get('/api/officer/high-risk-populations')
def populations(user=Depends(officer)):
    rows=[]
    for z in repo.all('risk_zones'):
        if z['risk_level'] not in {'HIGH','CRITICAL'}: continue
        pop=z.get('estimated_population',0); priority=round(min(100,z['risk_score']*.7+min(pop/1000,30)),1)
        shelter_list=shelters(z['latitude'],z['longitude'])['items']
        rows.append({**z,'estimated_exposed_population':pop,'exposure_priority_score':priority,'verified_shelters_nearby':len(shelter_list),'road_accessibility':'Requires route assessment'})
    return {'items':sorted(rows,key=lambda r:r['exposure_priority_score'],reverse=True),**config.provenance('RiskSetu exposure heuristic')}

# Serve the production SPA on the API origin when a frontend build is available.
# This also enables a real offline/PWA smoke test without a separate reverse proxy.
from fastapi.staticfiles import StaticFiles
frontend_dist=config.ROOT/'frontend'/'dist'
if frontend_dist.is_dir():
    app.mount('/',StaticFiles(directory=frontend_dist,html=True),name='frontend')
