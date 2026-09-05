"""Run from project root using the backend Python environment."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.integrations.gsi import normalize_file
from app.store import repo,now

def main():
    parser=argparse.ArgumentParser(description='Normalize licensed GSI inventory CSV/JSON/GeoJSON')
    parser.add_argument('file'); parser.add_argument('--source',default='GSI'); parser.add_argument('--mock',action='store_true'); parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    rows=normalize_file(args.file,args.source,'MOCK' if args.mock else 'CACHED')
    existing={r['external_id'] for r in repo.all('historical_landslides')}; added=0; duplicate=0
    for row in rows:
        if row['external_id'] in existing: duplicate+=1; continue
        if not args.dry_run: repo.insert('historical_landslides',{**row,'updated_at':now()})
        existing.add(row['external_id']); added+=1
    print(f'{"Would import" if args.dry_run else "Imported"}: {added}; duplicates skipped: {duplicate}')

if __name__=='__main__': main()
