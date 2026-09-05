"""Transparent prototype risk model with explicit missing-data handling.

Weights are normalized across inputs that are actually available. This avoids
fabricating slope, soil moisture, rainfall or historical values.
"""
from __future__ import annotations

def clamp(x): return max(0.0, min(1.0, float(x)))

def _norm(value, scale):
    return None if value is None else clamp(float(value)/scale)

def calculate_risk(d):
    values = {
        'rain24': (_norm(d.get('rainfall_24h_mm'), 200), .28),
        'rain72': (_norm(d.get('rainfall_72h_mm'), 400), .20),
        'soil_moisture': (_norm(d.get('soil_moisture_pct'), 100), .14),
        'slope': (_norm(d.get('slope_deg'), 60), .12),
        'history': (_norm(d.get('historical_landslides',0) if d.get('historical_landslides') is not None else None, 10), .08),
        'susceptibility': (None if d.get('susceptibility') is None else clamp(d.get('susceptibility')), .10),
        'incident_signal': (_norm(d.get('citizen_signal_score'), 100), .08),
    }
    present = {k:(v,w) for k,(v,w) in values.items() if v is not None}
    core_keys=['rain24','rain72','soil_moisture','slope','history','susceptibility']
    complete_core=all(values[k][0] is not None for k in core_keys)
    if not present:
        return {'risk_score':None,'severity':'UNKNOWN','risk_level':'UNKNOWN','operational_warning':False,
            'landslide_probability':None,'flood_probability':None,'model_version':'transparent-baseline-v2',
            'probability_status':'Insufficient data','contributing_factors':['No supported risk inputs are currently available'],
            'missing_features':list(values.keys()),'note':'Prototype estimate only. Not an official warning.','factors':{k:v for k,(v,_) in values.items()}}
    if complete_core:
        # Preserve v1 scoring for existing seeded zones and API compatibility.
        old_weights={'rain24':.22,'rain72':.16,'soil_moisture':.18,'slope':.16,'history':.10,'susceptibility':.18}
        score=round(100*sum(values[k][0]*old_weights[k] for k in core_keys),1)
    else:
        total_weight = sum(w for _,w in present.values())
        score = round(100*sum(v*w for v,w in present.values())/total_weight, 1)
    level = 'LOW' if score < 30 else 'MODERATE' if score < 55 else 'HIGH' if score < 75 else 'CRITICAL'
    reasons=[]
    if values['rain24'][0] is not None and values['rain24'][0] >= .5: reasons.append('Heavy rainfall over the last 24 hours')
    if values['rain72'][0] is not None and values['rain72'][0] >= .5: reasons.append('Sustained rainfall over 72 hours')
    if values['soil_moisture'][0] is not None and values['soil_moisture'][0] >= .7: reasons.append('High near-surface soil moisture')
    if values['slope'][0] is not None and values['slope'][0] >= .5: reasons.append('Steep terrain where terrain data is available')
    if values['history'][0] is not None and values['history'][0] >= .3: reasons.append('Previous landslide activity nearby')
    if values['susceptibility'][0] is not None and values['susceptibility'][0] >= .7: reasons.append('Elevated susceptibility data')
    if values['incident_signal'][0] is not None and values['incident_signal'][0] >= .4: reasons.append('Nearby active community/verified hazard signals')
    missing=[k for k,(v,_) in values.items() if v is None]
    return {'risk_score':score,'severity':level,'risk_level':level,'operational_warning':False,
            'landslide_probability':None,'flood_probability':None,'model_version':'transparent-baseline-v2',
            'probability_status':'Uncalibrated decision-support score; event probability unavailable',
            'contributing_factors':reasons or ['Available inputs are not currently elevated'],
            'missing_features':missing,'note':'Prototype estimate only. Not an official landslide or flood warning.',
            'factors':{k:v for k,(v,_) in values.items()}}

def safety_guidance(level, rain24=None, regional=False):
    level=(level or 'UNKNOWN').upper()
    if level=='CRITICAL':
        message='Severe hazard conditions are indicated. Avoid travel, steep slopes, river banks, drains and flooded roads; move to a safer location if authorities advise it.'
    elif level=='HIGH':
        message='High rainfall-related hazard risk. Avoid unnecessary travel and stay away from unstable slopes, fast-moving water and flooded roads.'
    elif level=='MODERATE':
        message='Conditions are elevated. Stay alert, monitor warnings and avoid vulnerable routes during heavy rain.'
    elif level=='LOW':
        message='No major immediate hazard is indicated by currently available inputs. Continue monitoring local conditions.'
    else:
        message='Risk cannot be fully assessed because required data is unavailable. Use local observations and official warnings.'
    if regional:
        message += ' Regional/upstream rainfall screening also shows an elevated signal; downstream impact is possible but not confirmed.'
    return message


def _weighted_score(entries):
    present=[(v,w) for v,w in entries if v is not None]
    if not present: return None
    total=sum(w for _,w in present)
    return round(100*sum(v*w for v,w in present)/total,1)


def _level(score):
    if score is None: return 'UNKNOWN'
    return 'LOW' if score < 30 else 'MODERATE' if score < 55 else 'HIGH' if score < 75 else 'CRITICAL'


def calculate_multi_risk(d):
    """Prototype multi-hazard score using only available, sourced inputs.

    Scores are decision-support indices, not calibrated event probabilities.
    The legacy calculate_risk() remains unchanged for backwards compatibility.
    """
    rain24=_norm(d.get('rainfall_24h_mm'),200)
    rain72=_norm(d.get('rainfall_72h_mm'),400)
    soil=_norm(d.get('soil_moisture_pct'),55)  # volumetric proxy: ~0.55 m3/m3 treated as saturated screening signal
    slope=_norm(d.get('slope_deg'),45)
    history=_norm(d.get('historical_landslides'),8)
    susc=None if d.get('susceptibility') is None else clamp(d.get('susceptibility'))
    satellite=_norm(d.get('satellite_rainfall_24h_mm'),200)
    incident=_norm(d.get('citizen_signal_score'),100)
    river=_norm(d.get('flood_signal_score'),100)
    forecast=_norm(d.get('forecast_rain_6h_mm'),80)

    landslide=_weighted_score([
        (rain24,.20),(rain72,.16),(soil,.18),(slope,.20),(history,.10),(susc,.06),(satellite,.06),(incident,.04)
    ])
    flood=_weighted_score([
        (river,.32),(rain24,.19),(rain72,.12),(soil,.12),(satellite,.10),(forecast,.10),(incident,.05)
    ])
    available=[x for x in (landslide,flood) if x is not None]
    overall=round(max(available)*.7 + min(available)*.3,1) if len(available)==2 else (available[0] if available else None)

    factors=[]
    if rain24 is not None and rain24>=.5: factors.append('Heavy 24-hour rainfall')
    if rain72 is not None and rain72>=.5: factors.append('Sustained 72-hour rainfall')
    if soil is not None and soil>=.65: factors.append('Elevated modelled soil moisture')
    if slope is not None and slope>=.55: factors.append('Steep terrain from DEM screening')
    if history is not None and history>=.25: factors.append('Historical landslide activity nearby')
    if satellite is not None and satellite>=.5: factors.append('IMERG satellite rainfall is elevated')
    if river is not None and river>=.45: factors.append('GloFAS river-discharge anomaly is elevated')
    if forecast is not None and forecast>=.35: factors.append('Near-term forecast rainfall is elevated')
    if incident is not None and incident>=.35: factors.append('Nearby community/verified hazard reports')

    keys={
        'rainfall_24h_mm':d.get('rainfall_24h_mm'),'rainfall_72h_mm':d.get('rainfall_72h_mm'),
        'soil_moisture_pct':d.get('soil_moisture_pct'),'slope_deg':d.get('slope_deg'),
        'historical_landslides':d.get('historical_landslides'),'satellite_rainfall_24h_mm':d.get('satellite_rainfall_24h_mm'),
        'flood_signal_score':d.get('flood_signal_score'),'forecast_rain_6h_mm':d.get('forecast_rain_6h_mm'),
    }
    present=sum(v is not None for v in keys.values())
    quality=round(100*present/len(keys))
    return {
        'risk_score':overall,'risk_level':_level(overall),'severity':_level(overall),
        'landslide_score':landslide,'landslide_level':_level(landslide),
        'flood_score':flood,'flood_level':_level(flood),
        'contributing_factors':factors or ['Available sourced inputs are not currently elevated'],
        'data_quality_pct':quality,'missing_features':[k for k,v in keys.items() if v is None],
        'model_version':'multi-hazard-transparent-v3','probability_status':'Decision-support indices; not calibrated event probabilities',
        'note':'Prototype screening only. Follow official warnings and local authorities.'
    }
