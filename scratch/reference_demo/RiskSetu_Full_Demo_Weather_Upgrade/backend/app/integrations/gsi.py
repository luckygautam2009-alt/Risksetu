"""Inventory normalization shared by the CLI and future approved feed adapters."""
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path

def normalize_file(path, source='GSI', mode='CACHED'):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
    else:
        payload=json.loads(path.read_text(encoding='utf-8-sig'))
        rows=payload.get('features',payload.get('records',[])) if isinstance(payload,dict) else payload
    normalized=[]
    for index,row in enumerate(rows,1):
        try:
            props=row.get('properties',row)
            if 'geometry' in row:
                if row['geometry']['type']!='Point':
                    raise ValueError('Inventory geometry must be Point')
                lon,lat=row['geometry']['coordinates'][:2]
            else:
                lat=props.get('latitude',props.get('lat'))
                lon=props.get('longitude',props.get('lon',props.get('lng')))
            lat,lon=float(lat),float(lon)
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90<=lat<=90 and -180<=lon<=180):
                raise ValueError('Invalid coordinates')
            event=date.fromisoformat(str(props.get('event_date',props.get('date','')))[:10]).isoformat()
            district=str(props.get('district','Unknown')); state=str(props.get('state','Unknown'))
            fingerprint=f'{source}|{lat:.5f}|{lon:.5f}|{event}'
            normalized.append({'external_id':hashlib.sha256(fingerprint.encode()).hexdigest(),
                'latitude':lat,'longitude':lon,'event_date':event,'district':district,'state':state,
                'severity':props.get('severity',props.get('type','UNKNOWN')),'source':source,'data_mode':mode,
                'metadata':props})
        except (TypeError,ValueError,KeyError) as e:
            raise ValueError(f'Row {index}: {e}') from e
    return normalized
