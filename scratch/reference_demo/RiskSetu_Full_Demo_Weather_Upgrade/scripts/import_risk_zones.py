"""Import assessed risk cells with measured features and explicit source timestamps."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.models import RiskRequest
from app.services.risk_engine import calculate_risk
from app.store import repo

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('file');p.add_argument('--dry-run',action='store_true');args=p.parse_args()
    rows=json.loads(Path(args.file).read_text(encoding='utf-8-sig'))
    validated=[]
    for row in rows:
        req=RiskRequest.model_validate({**row['features'],'latitude':row['latitude'],'longitude':row['longitude']})
        t=datetime.fromisoformat(row['updated_at'])
        if t.tzinfo is None or t>datetime.now(timezone.utc): raise ValueError('Observation time must include timezone and must not be in the future')
        if row['data_mode'] not in {'CACHED','LIVE','MOCK'} or not row['source']: raise ValueError('Explicit provenance required')
        if not 0<float(row.get('radius_m',1000))<=50000: raise ValueError('Cell radius must be 0–50 km')
        result=calculate_risk(req.model_dump())
        validated.append({**row,'risk_score':result['risk_score'],'risk_level':result['risk_level'],'landslide_probability':None,'contributing_factors':result['contributing_factors']})
    for row in validated:
        if not args.dry_run:
            key=row.get('id')
            if key and repo.get('risk_zones',key): repo.update('risk_zones',key,row)
            else: repo.insert('risk_zones',row)
    print(f'{"Validated" if args.dry_run else "Imported"} {len(validated)} risk cells')

if __name__=='__main__':main()
