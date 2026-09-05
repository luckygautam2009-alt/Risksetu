"""Fictional scenarios only. Never seeded in live mode."""
from datetime import datetime, timezone, timedelta
from app import config
from app.store import repo
from app.services.risk_engine import calculate_risk

def seed():
    if config.DATA_MODE != 'mock' or repo.all('risk_zones'):
        return
    areas=[('Shillong',25.5788,91.8933,'East Khasi Hills','Meghalaya',150,310,38,82,5,.8,12500),
           ('Laitumkhrah · Shillong',25.5686,91.8972,'East Khasi Hills','Meghalaya',128,270,24,70,3,.58,4200),
           ('Mawlai · Shillong',25.6067,91.8797,'East Khasi Hills','Meghalaya',162,335,36,84,5,.76,5100),
           ('Upper Shillong',25.5488,91.8585,'East Khasi Hills','Meghalaya',176,360,43,88,6,.84,3000),
           ('Polo · Shillong',25.5868,91.8915,'East Khasi Hills','Meghalaya',118,248,16,68,2,.48,3900),
           ('Nongthymmai · Shillong',25.5588,91.9115,'East Khasi Hills','Meghalaya',142,292,31,78,4,.69,4600),
           ('Sohra',25.27,91.73,'East Khasi Hills','Meghalaya',220,480,48,94,8,.9,6800),
           ('Guwahati',26.1445,91.7362,'Kamrup Metropolitan','Assam',48,110,14,48,1,.3,28000),
           ('Gangtok',27.3314,88.6138,'Gangtok','Sikkim',170,370,46,87,7,.85,9100),
           ('Aizawl',23.7271,92.7176,'Aizawl','Mizoram',120,250,40,78,6,.8,11000),
           ('Itanagar',27.0844,93.6053,'Papum Pare','Arunachal Pradesh',130,280,34,76,4,.7,8100),
           ('Kohima',25.6751,94.1086,'Kohima','Nagaland',85,180,35,64,3,.65,7600),
           ('Imphal',24.817,93.9368,'Imphal West','Manipur',60,150,18,61,2,.4,18000),
           ('Agartala',23.8315,91.2868,'West Tripura','Tripura',75,165,12,67,1,.35,22000)]
    for name,lat,lon,district,state,r24,r72,slope,soil,history,susc,pop in areas:
        features={'rainfall_24h_mm':r24,'rainfall_72h_mm':r72,'slope_deg':slope,'soil_moisture_pct':soil,'historical_landslides':history,'susceptibility':susc}
        risk=calculate_risk(features)
        repo.insert('risk_zones', {'name':name,'latitude':lat,'longitude':lon,'district':district,'state':state,
            'risk_score':risk['risk_score'],'risk_level':risk['risk_level'],'landslide_probability':None,
            'features':features,'contributing_factors':risk['contributing_factors'],'radius_m':1400 if 'Shillong' in name else 4000,
            'estimated_population':pop, **config.provenance('RiskSetu demo scenario','MOCK')})
        for n in range(3):
            repo.insert('historical_landslides', {'external_id':f'DEMO-{name}-{n}', 'latitude':lat+.018*(n-1),
                'longitude':lon+.022*(n-1),'district':district,'state':state,'severity':'MODERATE',
                'event_date':(datetime.now(timezone.utc)-timedelta(days=140+420*n)).date().isoformat(),
                'metadata':{'fictional':True}, **config.provenance('Synthetic inventory example','MOCK')})
    person=next(p for p in repo.all('profiles') if p['role']=='citizen')
    for kind,lat,lon,desc,sev in [('Road blockage',25.594,91.884,'Demo: debris reported along the hillside road near Shillong.','HIGH'),
        ('Slope crack',25.56,91.905,'Demo: visible cracks reported after sustained rainfall.','MODERATE'),
        ('Landslide',25.286,91.743,'Demo: slope movement reported near Sohra; field verification needed.','CRITICAL')]:
        repo.insert('incidents', {'type':kind,'latitude':lat,'longitude':lon,'description':desc,'severity':sev,
            'status':'PENDING','reporter_id':person['id'],'confirmation_count':0,'community_confidence_score':0,
            'client_id':f'seed-{lat}', **config.provenance('Synthetic citizen report','MOCK')})

    # Demo emergency resources for local/offline UX only. Replace with verified live data in production.
    if not repo.all('emergency_resources'):
        for name,kind,lat,lon,phone in [
            ('Demo Emergency Hospital - Shillong','HOSPITAL',25.574,91.884,'108'),
            ('Demo Police Control - Shillong','POLICE',25.576,91.893,'112'),
            ('Demo Emergency Hospital - Guwahati','HOSPITAL',26.150,91.760,'108'),
            ('Demo Police Control - Guwahati','POLICE',26.143,91.736,'112'),
        ]:
            repo.insert('emergency_resources',{'name':name,'type':kind,'latitude':lat,'longitude':lon,'phone':phone,'verified':False,**config.provenance('Synthetic emergency resource','MOCK')})

def seed_emergency_resources():
    if config.DATA_MODE != 'mock' or repo.all('emergency_resources'):
        return
    for name,kind,lat,lon,phone in [
        ('Demo Emergency Hospital - Shillong','HOSPITAL',25.574,91.884,'108'),
        ('Demo Police Control - Shillong','POLICE',25.576,91.893,'112'),
        ('Demo Emergency Hospital - Guwahati','HOSPITAL',26.150,91.760,'108'),
        ('Demo Police Control - Guwahati','POLICE',26.143,91.736,'112'),
    ]:
        repo.insert('emergency_resources',{'name':name,'type':kind,'latitude':lat,'longitude':lon,'phone':phone,'verified':False,**config.provenance('Synthetic emergency resource','MOCK')})
