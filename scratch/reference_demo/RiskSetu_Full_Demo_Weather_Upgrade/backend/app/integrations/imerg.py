"""Optional NASA GPM IMERG Early Run GIS adapter.

This adapter is disabled unless PPS_USERNAME/PPS_PASSWORD are configured.
It downloads the latest small GIS accumulation ZIP from the NASA PPS HTTPS
listing, samples the total-precipitation GeoTIFF using its world file, and
returns a point estimate. IMERG Early Run has latency and must not be presented
as live radar or as a flood forecast.

NASA Earthdata tokens are retained as an optional configuration for future
GES-DISC/CMR access, but PPS GIS HTTPS access normally uses PPS credentials.
"""
from __future__ import annotations
import io
import os
import re
import time
import zipfile
from typing import Any

import httpx
from PIL import Image

BASE_URL = os.getenv("NASA_IMERG_PPS_BASE_URL", "https://jsimpsonhttps.pps.eosdis.nasa.gov/imerg/gis/early/").rstrip("/") + "/"
CACHE_SECONDS = int(os.getenv("IMERG_CACHE_SECONDS", "1800"))
_cache: dict[tuple[str, float, float], tuple[float, dict[str, Any] | None]] = {}


def configured() -> bool:
    return bool(os.getenv("PPS_USERNAME", "").strip() and os.getenv("PPS_PASSWORD", "").strip())


def _auth():
    return (os.getenv("PPS_USERNAME", "").strip(), os.getenv("PPS_PASSWORD", "").strip())


def _pick_link(html: str, period: str) -> str | None:
    # NASA filenames contain .3hr.zip or .1day.zip (version-dependent naming may vary).
    patterns = [r'href=["\']([^"\']*\.' + re.escape(period) + r'\.zip)["\']', r'href=["\']([^"\']*' + re.escape(period) + r'[^"\']*\.zip)["\']']
    links=[]
    for pattern in patterns:
        links.extend(re.findall(pattern, html, flags=re.I))
    links=[x for x in links if '3IMERG' in x.upper() or 'IMERG' in x.upper()]
    return sorted(set(links))[-1] if links else None


def _sample_zip(blob: bytes, lat: float, lon: float) -> float | None:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=z.namelist()
        tif=next((n for n in names if n.lower().endswith(('.tif','.tiff')) and ('tp' in n.lower() or 'total' in n.lower())),None)
        if not tif:
            tif=next((n for n in names if n.lower().endswith(('.tif','.tiff'))),None)
        tfw=next((n for n in names if n.lower().endswith(('.tfw','.wld'))),None)
        if not tif or not tfw:
            return None
        vals=[float(x.strip()) for x in z.read(tfw).decode('ascii','ignore').splitlines() if x.strip()][:6]
        if len(vals)<6: return None
        A,D,B,E,C,F=vals
        if abs(B)>1e-9 or abs(D)>1e-9 or A==0 or E==0:
            return None
        col=round((lon-C)/A); row=round((lat-F)/E)
        img=Image.open(io.BytesIO(z.read(tif)))
        if not (0<=col<img.width and 0<=row<img.height): return None
        value=img.getpixel((col,row))
        if isinstance(value,tuple): value=value[0]
        try: value=float(value)
        except (TypeError,ValueError): return None
        if value<0 or value>=65000: return None
        # PPS GIS 30min/3hr/1day accumulation products are scaled x10 (0.1 mm).
        return round(value/10.0,1)


async def accumulation(lat: float, lon: float, period: str = "1day") -> dict[str, Any] | None:
    if period not in {"3hr","1day"} or not configured():
        return None
    key=(period,round(lat,2),round(lon,2)); now=time.time()
    if key in _cache and now-_cache[key][0]<CACHE_SECONDS:
        return _cache[key][1]
    try:
        async with httpx.AsyncClient(timeout=45,auth=_auth(),follow_redirects=True) as client:
            listing=await client.get(BASE_URL); listing.raise_for_status()
            link=_pick_link(listing.text,period)
            if not link:
                _cache[key]=(now,None); return None
            url=link if link.startswith('http') else BASE_URL+link.lstrip('/')
            response=await client.get(url); response.raise_for_status()
        mm=_sample_zip(response.content,lat,lon)
        result=None if mm is None else {"precipitation_mm":mm,"period":period,"source":"NASA GPM IMERG Early Run","data_mode":"LIVE","source_url":url,"latency_note":"Near-real-time satellite accumulation; not live radar and not a flood forecast."}
        _cache[key]=(now,result); return result
    except Exception:
        _cache[key]=(now,None); return None
