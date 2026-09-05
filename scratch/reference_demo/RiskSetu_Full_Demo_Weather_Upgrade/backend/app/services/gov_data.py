"""Compatibility helpers for external data status.

Weather is now provided through app.integrations.indianapi. Historical
landslide inventory is optional and may be empty until an approved/imported
source is available.
"""
import os


def weather_status():
    return {
        "configured": bool(os.getenv("INDIANAPI_KEY", "").strip()),
        "source": "IndianAPI Weather",
    }


def historical_inventory_status():
    return {
        "configured": False,
        "source": "Optional imported/community inventory",
        "message": "No GSI dataset is required for the application to run.",
    }
