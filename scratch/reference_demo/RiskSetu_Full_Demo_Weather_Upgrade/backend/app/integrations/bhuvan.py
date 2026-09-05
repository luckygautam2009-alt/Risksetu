"""Open/approved terrain feature interface. Live ingestion must supply measured features."""
from app import config
from app.store import repo
from app.services.geo import nearby
from fastapi import HTTPException

def terrain(lat,lon):
    zones=nearby(repo.all('risk_zones'),{'latitude':lat,'longitude':lon},5000)
    if not zones:
        raise HTTPException(404,'No terrain coverage available at this location')
    z=zones[0]; f=z.get('features',{})
    return {'latitude':lat,'longitude':lon,'slope_angle':f.get('slope_deg'),
        'elevation':f.get('elevation'),'soil_moisture':f.get('soil_moisture_pct'),
        'land_cover':f.get('land_cover'),'vegetation_index':f.get('vegetation_index'),
        **config.provenance(z['source'],z['data_mode'])}
