"""
RISKSETU AI — Public-Source AI Hazard Intelligence (OSINT).

Disaster situational-awareness decision-support service.
Aggregates public RSS and news leads, cross-references independent source counts
and live weather/rainfall context, and presents corroborated leads for authorized
officer review.

CRITICAL SCIENTIFIC RULES:
  - Public/social reports are treated strictly as unverified LEADS, never PROOF.
  - Never issues automated evacuation orders.
  - High-confidence leads produce 'PREPARE_EVACUATION_REVIEW' for human officer evaluation.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

import httpx
import structlog

from app.services.weather.service import WeatherService

logger = structlog.get_logger("risksetu.osint")

TERMS = (
    "landslide",
    "landslip",
    "flash flood",
    "flood",
    "heavy rain",
    "cloudburst",
    "road blocked",
    "slope failure",
    "debris flow",
)

HIMALAYAN_CORRIDORS = (
    "chamoli",
    "joshimath",
    "rudraprayag",
    "uttarakhand",
    "meghalaya",
    "shillong",
    "assam",
    "guwahati",
    "sikkim",
    "gangtok",
    "arunachal",
    "nagaland",
    "manipur",
    "mizoram",
    "tripura",
    "north east",
    "himalaya",
)

FEEDS = [
    ("GDACS", "https://www.gdacs.org/xml/rss.xml", "OFFICIAL_AGGREGATOR"),
    (
        "Google News",
        "https://news.google.com/rss/search?q=(landslide%20OR%20%22flash%20flood%22%20OR%20%22heavy%20rain%22)%20(Uttarakhand%20OR%20Chamoli%20OR%20Meghalaya%20OR%20Assam%20OR%20Sikkim)&hl=en-IN&gl=IN&ceid=IN:en",
        "NEWS_AGGREGATOR",
    ),
]

_weather_service = WeatherService()


def _text(el: ET.Element, name: str) -> str:
    child = el.find(name)
    return (child.text or "").strip() if child is not None else ""


def _parse_feed_items(xml_text: str, source: str, source_type: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:30]:
        title = _text(item, "title")
        raw_desc = _text(item, "description")
        desc = re.sub(r"<[^>]+>", " ", raw_desc)
        link = _text(item, "link")
        pub = _text(item, "pubDate")
        combined = f"{title} {desc}".lower()

        if not any(term in combined for term in TERMS):
            continue
        if source != "GDACS" and not any(loc in combined for loc in HIMALAYAN_CORRIDORS):
            continue

        clean_summary = re.sub(r"\s+", " ", desc)[:500]
        items.append({
            "source": source,
            "source_type": source_type,
            "title": title[:250],
            "summary": clean_summary,
            "url": link,
            "published_at": pub,
            "raw_text": f"{title}. {clean_summary}",
        })
    return items


def _extract_area(text: str) -> tuple[str, float, float]:
    t = text.lower()
    mapping = [
        ("Chamoli", 30.2936, 79.5603),
        ("Joshimath", 30.5550, 79.5640),
        ("Rudraprayag", 30.2844, 78.9811),
        ("Shillong", 25.5788, 91.8933),
        ("Guwahati", 26.1445, 91.7362),
        ("Sikkim / Gangtok", 27.3314, 88.6138),
        ("Arunachal Pradesh", 27.1004, 93.6167),
        ("Uttarakhand", 30.0668, 79.0193),
        ("Meghalaya", 25.4670, 91.3662),
    ]
    for name, lat, lon in mapping:
        if name.lower() in t:
            return name, lat, lon
    return "Himalayan & North-East Watch Sector", 30.2936, 79.5603


async def fetch_public_leads() -> list[dict[str, Any]]:
    leads: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "RiskSetu/1.0 Disaster-Research Prototype"},
    ) as client:
        for source, url, kind in FEEDS:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    leads.extend(_parse_feed_items(resp.text, source, kind))
            except Exception as exc:  # noqa: BLE001
                logger.debug("osint_feed_fetch_failed", source=source, error=str(exc))
                continue
    return leads


async def analyse_leads(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not leads:
        return []

    groups: dict[tuple[str, float, float], list[dict[str, Any]]] = {}
    for item in leads:
        loc_key = _extract_area(item["raw_text"])
        groups.setdefault(loc_key, []).append(item)

    results: list[dict[str, Any]] = []
    for (area, lat, lon), items in list(groups.items())[:8]:
        unique_sources = len({x["source"] for x in items})
        official_count = sum(1 for x in items if x["source_type"] == "OFFICIAL_AGGREGATOR")

        try:
            weather_resp = await _weather_service.get_weather(lat, lon)
            rain_24h = (
                weather_resp.forecast[0].precipitation_sum_mm
                if weather_resp.forecast
                else (weather_resp.current.precipitation_mm if weather_resp.current else 0.0)
            )
        except Exception:
            rain_24h = 0.0

        corroboration = min(100.0, (unique_sources * 25.0) + (official_count * 20.0) + min(30.0, float(rain_24h) * 2.0))
        confidence = "HIGH" if corroboration >= 70 else "MEDIUM" if corroboration >= 40 else "LOW"

        text_block = " ".join(x["raw_text"].lower() for x in items)
        has_landslide = "landslide" in text_block or "slope" in text_block
        has_flood = "flood" in text_block or "rain" in text_block
        hazard = (
            "FLOOD/LANDSLIDE" if has_landslide and has_flood
            else "LANDSLIDE" if has_landslide
            else "FLOOD/HEAVY RAIN"
        )

        severity = (
            "HIGH" if rain_24h >= 50 or corroboration >= 75
            else "MODERATE" if rain_24h >= 20 or corroboration >= 45
            else "WATCH"
        )

        action = (
            "PREPARE_EVACUATION_REVIEW" if severity == "HIGH" and confidence in ("MEDIUM", "HIGH")
            else "OFFICER_REVIEW"
        )

        clean_evidence = [
            {k: v for k, v in x.items() if k != "raw_text"}
            for x in items[:4]
        ]

        results.append({
            "area": area,
            "latitude": lat,
            "longitude": lon,
            "hazard": hazard,
            "severity": severity,
            "confidence": confidence,
            "corroboration_score": round(corroboration, 1),
            "evidence_count": len(items),
            "independent_sources": unique_sources,
            "rainfall_24h_mm": round(float(rain_24h), 1),
            "affected_areas": [area],
            "impact_window": (
                "Elevated risk over the next 12–24h (requires forecast monitoring)"
                if severity == "HIGH"
                else "No deterministic impact window established"
            ),
            "recommended_action": action,
            "analysis_note": (
                "Public reports are treated as decision-support leads, not verified truth. "
                "Corroborated with weather signals; authorized officer must review before public action."
            ),
            "evidence": clean_evidence,
            "source": "RiskSetu OSINT Corroboration Engine",
            "data_mode": "LIVE",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    return sorted(results, key=lambda x: (x["severity"] == "HIGH", x["corroboration_score"]), reverse=True)


async def scan_osint() -> list[dict[str, Any]]:
    try:
        leads = await fetch_public_leads()
        return await analyse_leads(leads)
    except Exception as exc:  # noqa: BLE001
        logger.warning("osint_scan_failed", error=str(exc))
        return []
