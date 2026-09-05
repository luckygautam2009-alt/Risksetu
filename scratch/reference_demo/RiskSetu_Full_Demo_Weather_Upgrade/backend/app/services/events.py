import asyncio
import json
import threading
from collections import deque
from app.store import repo,now
from app.services.geo import distance

events=deque(maxlen=500)
lock=threading.Lock()
sequence=0

def publish(kind):
    global sequence
    with lock:
        sequence+=1
        events.append({'sequence':sequence,'type':kind})

async def stream(request):
    cursor=sequence
    yield 'data: {"type":"connected"}\n\n'
    while not await request.is_disconnected():
        with lock:
            pending=[e for e in events if e['sequence']>cursor]
        for event in pending:
            cursor=event['sequence']
            yield 'data: '+json.dumps(event)+'\n\n'
        yield ': heartbeat\n\n'
        await asyncio.sleep(10)

MESSAGES={
    'en':'Elevated risk nearby. Review current information and follow local authority guidance.',
    'hi':'आसपास जोखिम बढ़ा हुआ है। ताज़ा जानकारी देखें और स्थानीय प्रशासन के निर्देशों का पालन करें।',
    'as':'ওচৰত বিপদৰ আশংকা বৃদ্ধি পাইছে। শেহতীয়া তথ্য চাওক আৰু স্থানীয় প্ৰশাসনৰ নিৰ্দেশনা মানি চলক।'}

def notify(user_id, incident_id, kind, title, message, severity='WATCH'):
    existing=repo.all('notifications')
    if any(n['user_id']==user_id and n.get('incident_id')==incident_id and n['type']==kind for n in existing): return
    repo.insert('notifications',{'user_id':user_id,'incident_id':incident_id,'type':kind,'title':title,
        'message':message,'severity':severity,'read':False})
    publish('alert')

def nearby_notifications(incident):
    from datetime import datetime,timezone
    for loc in repo.all('user_locations'):
        if loc['user_id']==incident['reporter_id']: continue
        if (datetime.now(timezone.utc)-datetime.fromisoformat(loc['updated_at'])).total_seconds()>3600: continue
        meters=distance(loc,incident)
        if meters<=500:
            notify(loc['user_id'],incident['id'],'CONFIRMATION','Nearby report needs confirmation',f"Possible {incident['type'].lower()} reported {round(meters)} m away (within 500 m). Confirm only from your current safe location.")
        if meters<=5000 and incident['severity'] in {'HIGH','CRITICAL'}:
            profile=repo.get('profiles',loc['user_id']) or {}
            notify(loc['user_id'],incident['id'],'RISK','Nearby hazard report',MESSAGES.get(profile.get('preferred_language'),MESSAGES['en']), 'WARNING')

def audit(user, action, target, detail):
    repo.insert('audit_logs',{'actor_id':user['id'],'action':action,'target_id':target,'detail':detail})
