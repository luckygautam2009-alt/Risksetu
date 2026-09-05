"""Import NASA Global Landslide Catalog CSV into RiskSetu's local/Supabase repository.

Free prototype workflow:
  python scripts/import_nasa_glc.py --download
or
  python scripts/import_nasa_glc.py path/to/Global_Landslide_Catalog_Export_rows.csv

The NASA Open Data export is historical (one-time export, current to 2016), so it
is used as a historical signal only, never as a live hazard feed.
"""
from __future__ import annotations
import argparse,csv,io,sys
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.store import repo
from app import config

NASA_CSV='https://data.nasa.gov/docs/legacy/Global_Landslide_Catalog_Export/Global_Landslide_Catalog_Export_rows.csv'
NER=(22.0,30.8,88.0,97.8)


def pick(row,*names):
    lower={k.lower().strip():v for k,v in row.items() if k}
    for name in names:
        v=lower.get(name.lower())
        if v not in (None,''): return v
    return None


def rows_from_download():
    r=httpx.get(NASA_CSV,timeout=60,follow_redirects=True);r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('csv',nargs='?');ap.add_argument('--download',action='store_true');ap.add_argument('--all',action='store_true',help='Do not limit to North-East India bounding box');args=ap.parse_args()
    if args.download: rows=rows_from_download()
    elif args.csv:
        with open(args.csv,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    else: ap.error('Give a CSV path or use --download')
    existing={str(x.get('external_id')) for x in repo.all('historical_landslides')}
    added=skipped=0
    for row in rows:
        try:
            lat=float(pick(row,'latitude','lat'));lon=float(pick(row,'longitude','lon','lng'))
        except (TypeError,ValueError): skipped+=1;continue
        if not args.all and not (NER[0]<=lat<=NER[1] and NER[2]<=lon<=NER[3]): continue
        event_id=str(pick(row,'event_id','id','event_import_id') or f'NASA-{lat:.5f}-{lon:.5f}-{pick(row,"event_date") or "unknown"}')
        if event_id in existing: continue
        size=(pick(row,'landslide_size','size') or 'unknown').upper()
        sev='CRITICAL' if size in {'VERY_LARGE','CATASTROPHIC'} else 'HIGH' if size=='LARGE' else 'MODERATE' if size in {'MEDIUM','SMALL'} else 'LOW'
        repo.insert('historical_landslides',{
            'external_id':event_id,'latitude':lat,'longitude':lon,
            'district':pick(row,'admin_division_name','location_description') or 'Unknown',
            'state':pick(row,'country_name') or 'Unknown','severity':sev,
            'event_date':pick(row,'event_date','date') or 'unknown',
            'metadata':{'category':pick(row,'landslide_category'),'trigger':pick(row,'landslide_trigger'),'size':pick(row,'landslide_size'),'title':pick(row,'event_title')},
            **config.provenance('NASA Global Landslide Catalog historical export','LIVE')
        });existing.add(event_id);added+=1
    print(f'Imported {added} NASA historical landslide records; skipped {skipped} malformed rows. DATA_MODE={config.DATA_MODE}')

if __name__=='__main__': main()
