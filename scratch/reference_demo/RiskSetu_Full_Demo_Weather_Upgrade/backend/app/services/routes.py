from datetime import datetime,timezone
from app.store import repo
from app.services.geo import sample_line,line_distance,distance
from app.integrations.maps import alternatives

def fresh(row):
    try:
        t=datetime.fromisoformat(row['updated_at'])
        return t.tzinfo is not None and 0 <= (datetime.now(timezone.utc)-t).total_seconds()<3600
    except (ValueError,KeyError):
        return False

def score_route(route,zones,incidents,roads):
    points=sample_line(route['coordinates'],200)
    scores=[]; covered=0; reasons=[]; excluded=False
    usable=[z for z in zones if fresh(z)]
    for p in points:
        intersect=[z for z in usable if distance(p,z)<=z.get('radius_m',1000)]
        if intersect:
            covered+=1; scores.append(max(z['risk_score'] for z in intersect))
    score=max(scores,default=0)*.65+(sum(scores)/len(scores) if scores else 0)*.35
    for z in usable:
        if line_distance(z,route['coordinates'])<=z.get('radius_m',1000) and z['risk_score']>=55:
            reasons.append(f"{z['risk_level']} risk near {z.get('name','risk zone')}; rainfall and terrain contribute")
    for i in incidents:
        if i['status'] in {'REJECTED','RESOLVED'}: continue
        if line_distance(i,route['coordinates'])<=500:
            if i['severity']=='CRITICAL' or (i['status']=='VERIFIED' and i['type']=='Road blockage'):
                excluded=True
            score+=20
            reasons.append(f"{i['status']} {i['type']} within 500 m of route")
    for road in roads:
        if line_distance(road,route['coordinates'])<=300 and road['status']!='OPEN':
            excluded |= road['status']=='BLOCKED'
            score+=30
            reasons.append(f"{road['road_identifier']}: {road['status']}")
    coverage=round(covered/max(1,len(points)),2)
    unknown=coverage<.95
    if unknown: reasons.append(f'Risk data covers only {round(coverage*100)}% of sampled route; unassessed sections')
    return {**route,'route_risk_score':round(min(score,100),1),'excluded':excluded,'coverage':coverage,
        'assessment_complete':not unknown,'classification':'AVOID ROUTE' if excluded or score>=75 else ('CAUTION ROUTE' if unknown or score>=30 else 'LOW-RISK ROUTE'),
        'reasons':reasons or ['No known elevated landslide, incident or road hazard found in available coverage'],
        'notice':'Lower-risk route based on currently available data. Never a guarantee of safety.'}

async def safe_routes(origin,destination):
    options=await alternatives(origin,destination)
    result=[score_route(r,repo.all('risk_zones'),repo.all('incidents'),repo.all('road_hazards')) for r in options]
    result.sort(key=lambda r:(r['excluded'],not r['assessment_complete'],r['route_risk_score'],r['distance_m']))
    eligible=[r for r in result if not r['excluded'] and r['assessment_complete'] and r['route_risk_score']<75]
    if eligible:
        eligible[0]['classification']='SAFE ROUTE · NO KNOWN ELEVATED RISK' if eligible[0]['route_risk_score']<30 else 'SAFEST AVAILABLE ROUTE'
    for r in result:
        if r['excluded'] or r['route_risk_score']>=75:
            r['travel_advice']='HIGH RISK — reschedule if possible or use a lower-risk alternative.'
        elif not r['assessment_complete']:
            r['travel_advice']='UNASSESSED SECTIONS — risk coverage is incomplete; do not treat this route as safe.'
        elif r['route_risk_score']>=30:
            r['travel_advice']='MODERATE RISK — avoid unnecessary travel and proceed only after checking current alerts.'
        else:
            r['travel_advice']='No known elevated risk found in currently available route data.'
    return {'routes':result,'recommended_route_id':eligible[0]['id'] if eligible else None,
        'message':'Lower-risk option among assessed alternatives' if eligible else 'No sufficiently assessed lower-risk route is available.'}
