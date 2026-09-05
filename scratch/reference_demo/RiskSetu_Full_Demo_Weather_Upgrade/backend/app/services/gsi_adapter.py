"""Adapter boundary for GSI/Bhusanket/Bhukosh landslide inventory/susceptibility data.
Download/use datasets according to official access terms, normalize to GeoJSON/CSV, then ingest here.
"""
import json
from pathlib import Path
DATA=Path(__file__).parents[1]/'data'/'sample_zones.geojson'
def load_zones():
    return json.loads(DATA.read_text()) if DATA.exists() else {'type':'FeatureCollection','features':[]}
