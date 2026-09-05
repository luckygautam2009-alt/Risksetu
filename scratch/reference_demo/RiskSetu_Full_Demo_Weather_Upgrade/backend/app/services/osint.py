"""Zero-cost public-source hazard intelligence.
Uses public RSS/feeds as corroborating signals; social posts are accepted only as unverified leads.
Never issues evacuation orders automatically.
"""
import asyncio, os, re
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET
import httpx
from app import config
from app.store import repo
from app.integrations.weather import current as current_weather
from app.services.risk_engine import calculate_multi_risk

TERMS=('landslide','landslip','flash flood','flood','heavy rain','cloudburst','road blocked','slope failure')
NER=('meghalaya','shillong','assam','guwahati','arunachal','nagaland','manipur','mizoram','tripura','sikkim','north east india','northeast india')
FEEDS=[
 ('GDACS','https://www.gdacs.org/xml/rss.xml','OFFICIAL_AGGREGATOR'),
 ('Google News','https://news.google.com/rss/search?q=(landslide%20OR%20%22flash%20flood%22%20OR%20%22heavy%20rain%22)%20(Meghalaya%20OR%20Assam%20OR%20Arunachal%20OR%20Sikkim%20OR%20Nagaland%20OR%20Manipur%20OR%20Mizoram%20OR%20Tripura)&hl=en-IN&gl=IN&ceid=IN:en','NEWS_AGGREGATOR'),
]

def _text(el, name):
    x=el.find(name); return (x.text or '').strip() if x is not None else ''

def _items(xml, source, source_type):
    root=ET.fromstring(xml); out=[]
    for item in root.findall('.//item')[:40]:
        title=_text(item,'title'); desc=re.sub('<[^>]+>',' ',_text(item,'description')); link=_text(item,'link'); pub=_text(item,'pubDate')
        text=f'{title} {desc}'.lower()
        if not any(t in text for t in TERMS): continue
        if source!='GDACS' and not any(p in text for p in NER): continue
        out.append({'source':source,'source_type':source_type,'title':title[:300],'summary':re.sub(r'\s+',' ',desc)[:700], 'url':link,'published_at':pub,'raw_text':f'{title}. {desc}'[:1600]})
    return out

async def fetch_public_leads():
    leads=[]
    async with httpx.AsyncClient(timeout=12,follow_redirects=True,headers={'User-Agent':'RiskSetu/1.0 disaster-research prototype'}) as client:
        for source,url,kind in FEEDS:
            try:
                r=await client.get(url); r.raise_for_status(); leads.extend(_items(r.text,source,kind))
            except Exception:
                continue
    return leads

def _area(text):
    t=text.lower()
    mapping=[('Shillong',25.5788,91.8933),('Guwahati',26.1445,91.7362),('Sikkim',27.5330,88.5122),('Arunachal Pradesh',27.1004,93.6167),('Manipur',24.6637,93.9063),('Mizoram',23.1645,92.9376),('Nagaland',26.1584,94.5624),('Tripura',23.9408,91.9882),('Assam',26.2006,92.9376),('Meghalaya',25.4670,91.3662)]
    for name,lat,lon in mapping:
        if name.lower() in t: return name,lat,lon
    return 'North-East India',25.5788,91.8933

async def analyse_leads(leads):
    groups={}
    for x in leads:
        area,lat,lon=_area(x['raw_text']); groups.setdefault((area,lat,lon),[]).append(x)
    results=[]
    for (area,lat,lon),items in list(groups.items())[:12]:
        unique_sources=len(set(x['source'] for x in items)); official=sum(x['source_type']=='OFFICIAL_AGGREGATOR' for x in items)
        try: weather=await current_weather(lat,lon)
        except Exception: weather={}
        rain24=weather.get('rainfall_24h') or 0; rain72=weather.get('rainfall_72h') or rain24
        corroboration=min(100, unique_sources*22 + official*25 + min(30,rain24/3))
        confidence='HIGH' if corroboration>=70 else 'MEDIUM' if corroboration>=40 else 'LOW'
        hazard='FLOOD/LANDSLIDE' if any('landslide' in x['raw_text'].lower() for x in items) and any('flood' in x['raw_text'].lower() for x in items) else ('LANDSLIDE' if any('landslide' in x['raw_text'].lower() for x in items) else 'FLOOD/HEAVY RAIN')
        severity='HIGH' if rain24>=80 or corroboration>=75 else 'MODERATE' if rain24>=35 or corroboration>=45 else 'WATCH'
        affected=[area]
        action='OFFICER_REVIEW'
        if severity=='HIGH' and confidence in {'MEDIUM','HIGH'}: action='PREPARE_EVACUATION_REVIEW'
        results.append({'area':area,'latitude':lat,'longitude':lon,'hazard':hazard,'severity':severity,'confidence':confidence,'corroboration_score':round(corroboration),
          'evidence_count':len(items),'independent_sources':unique_sources,'rainfall_24h_mm':rain24,'affected_areas':affected,
          'impact_window':'Current / next 24h requires forecast review' if severity=='HIGH' else 'No reliable impact time established',
          'recommended_action':action,'analysis_note':'Public reports are leads, not proof. RiskSetu corroborates them with independent sources and weather signals; an authorized officer must verify before evacuation or public emergency action.',
          'evidence':[{k:v for k,v in x.items() if k!='raw_text'} for x in items[:5]],**config.provenance('RiskSetu public-source corroboration')})
    return sorted(results,key=lambda x:(x['severity']=='HIGH',x['corroboration_score']),reverse=True)

async def scan():
    if config.DATA_MODE=='mock':
        return {'items':[{'area':'Upper Shillong / East Khasi Hills','latitude':25.54,'longitude':91.86,'hazard':'LANDSLIDE + HEAVY RAIN','severity':'HIGH','confidence':'HIGH','corroboration_score':86,'evidence_count':4,'independent_sources':3,'rainfall_24h_mm':112,'affected_areas':['Upper Shillong','Laitkor','Shillong–Sohra corridor'],'impact_window':'Elevated risk in the next 6–12h (DEMO scenario)','recommended_action':'PREPARE_EVACUATION_REVIEW','analysis_note':'DEMO: multiple simulated public/official reports corroborated with elevated rainfall. Officer review required before any evacuation order.','evidence':[{'source':'DEMO · GDACS','source_type':'OFFICIAL_AGGREGATOR','title':'Flood/heavy-rain signal near Meghalaya','summary':'Synthetic judge-demo evidence','url':'','published_at':'DEMO'},{'source':'DEMO · Local news','source_type':'NEWS_AGGREGATOR','title':'Slope movement reported on hill road','summary':'Synthetic judge-demo evidence','url':'','published_at':'DEMO'}],**config.provenance('Synthetic OSINT judge scenario','MOCK')}],**config.provenance('RiskSetu OSINT demo','MOCK')}
    leads=await fetch_public_leads(); return {'items':await analyse_leads(leads),**config.provenance('Public RSS + weather corroboration','LIVE')}
