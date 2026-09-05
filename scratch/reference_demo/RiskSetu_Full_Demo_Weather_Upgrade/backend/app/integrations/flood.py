"""Free river-discharge context from Open-Meteo Flood API / GloFAS.

This is coarse (~5 km) hydrological guidance. It must not be represented as a
local gauge measurement or as an official flood warning.
"""
from __future__ import annotations

import os
import statistics
import time
from typing import Any

import httpx

BASE_URL = os.getenv("OPEN_METEO_FLOOD_URL", "https://flood-api.open-meteo.com/v1/flood")
CACHE_SECONDS = int(os.getenv("FLOOD_CACHE_SECONDS", "1800"))
_cache: dict[tuple[float, float], tuple[float, dict[str, Any] | None]] = {}


def _nums(values):
    out=[]
    for v in values or []:
        try:
            if v is not None: out.append(float(v))
        except (TypeError, ValueError):
            pass
    return out


async def discharge(lat: float, lon: float) -> dict[str, Any] | None:
    key=(round(lat,3),round(lon,3)); now=time.time()
    if key in _cache and now-_cache[key][0] < CACHE_SECONDS:
        cached=_cache[key][1]
        return None if cached is None else {**cached,"data_mode":"CACHED"}
    params={
        "latitude":lat,"longitude":lon,"daily":"river_discharge,river_discharge_mean,river_discharge_max",
        "past_days":30,"forecast_days":7,"timezone":"UTC","cell_selection":"nearest",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.get(BASE_URL,params=params,headers={"Accept":"application/json"}); r.raise_for_status()
        data=r.json() or {}; daily=data.get("daily") or {}; times=daily.get("time") or []
        discharge=_nums(daily.get("river_discharge")); means=_nums(daily.get("river_discharge_mean")); maxima=_nums(daily.get("river_discharge_max"))
        series=daily.get("river_discharge") or []
        if not series: return None
        # past_days=30 means the final seven entries are forecast days in normal responses.
        hist=_nums(series[:-7] if len(series)>7 else series)
        fc=_nums(series[-7:] if len(series)>=7 else [])
        current=hist[-1] if hist else (fc[0] if fc else None)
        baseline=statistics.median(hist) if hist else None
        forecast_max=max(fc) if fc else None
        ratio=(current/baseline) if current is not None and baseline and baseline>0 else None
        forecast_ratio=(forecast_max/baseline) if forecast_max is not None and baseline and baseline>0 else None
        # Relative anomaly score, deliberately conservative because this is not a gauge.
        score=None
        rmax=max([x for x in (ratio,forecast_ratio) if x is not None],default=None)
        if rmax is not None:
            score=round(max(0,min(100,(rmax-0.8)/2.2*100)),1)
        result={
            "current_discharge_m3s":round(current,2) if current is not None else None,
            "baseline_30d_median_m3s":round(baseline,2) if baseline is not None else None,
            "forecast_7d_max_m3s":round(forecast_max,2) if forecast_max is not None else None,
            "relative_discharge_ratio":round(ratio,2) if ratio is not None else None,
            "forecast_ratio":round(forecast_ratio,2) if forecast_ratio is not None else None,
            "flood_signal_score":score,
            "source":"Open-Meteo Flood API · GloFAS",
            "data_mode":"LIVE",
            "coverage_note":"Modelled discharge for the largest river represented near the coordinate (~5 km grid); not a local river gauge.",
            "dates":times[-7:] if times else [],
        }
        _cache[key]=(now,result); return result
    except Exception:
        if key in _cache:
            cached=_cache[key][1]
            return None if cached is None else {**cached,"data_mode":"STALE"}
        return None
