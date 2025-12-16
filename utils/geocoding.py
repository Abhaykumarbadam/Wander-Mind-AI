"""
Geocoding utilities using OpenCage API with Nominatim fallback.
Converts location names to coordinates for map visualization.
"""
import os
import time
import requests
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()

OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY")
OPENCAGE_BASE_URL = "https://api.opencagedata.com/geocode/v1/json"
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"

# Simple in-memory cache to avoid hitting APIs repeatedly for the same location
_GEOCODE_CACHE = {}

def geocode_location(location: str) -> Optional[Dict]:
    """
    Convert location name to coordinates using OpenCage (preferred) or Nominatim (fallback).
    
    Args:
        location: Location name (e.g., "Paris, France")
    
    Returns:
        Dict with lat, lng, formatted_address, country, city, etc.
    """
    if not location:
        return None
        
    # Check cache
    if location in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[location]

    result = None
    
    # Try OpenCage first if key exists
    if OPENCAGE_API_KEY:
        result = _geocode_opencage(location)
    
    # Fallback to Nominatim
    if not result:
        result = _geocode_nominatim(location)
        
    if result:
        _GEOCODE_CACHE[location] = result
        
    return result

def _geocode_opencage(location: str) -> Optional[Dict]:
    try:
        params = {
            "q": location,
            "key": OPENCAGE_API_KEY,
            "limit": 1,
            "no_annotations": 0
        }
        response = requests.get(OPENCAGE_BASE_URL, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data["results"]:
                res = data["results"][0]
                geom = res["geometry"]
                comps = res["components"]
                anns = res.get("annotations", {})
                return {
                    "lat": geom["lat"],
                    "lng": geom["lng"],
                    "formatted_address": res["formatted"],
                    "country": comps.get("country", ""),
                    "country_code": comps.get("country_code", "").upper(),
                    "city": comps.get("city") or comps.get("town") or comps.get("village", ""),
                    "timezone": anns.get("timezone", {}).get("name", ""),
                    "source": "opencage"
                }
    except Exception as e:
        print(f"OpenCage error for {location}: {e}")
    return None

def _geocode_nominatim(location: str) -> Optional[Dict]:
    try:
        # Nominatim requires a User-Agent
        headers = {'User-Agent': 'WanderMindAI/1.0'}
        params = {
            "q": location,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }
        response = requests.get(NOMINATIM_BASE_URL, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                res = data[0]
                addr = res.get("address", {})
                return {
                    "lat": float(res["lat"]),
                    "lng": float(res["lon"]),
                    "formatted_address": res.get("display_name"),
                    "country": addr.get("country", ""),
                    "country_code": addr.get("country_code", "").upper(),
                    "city": addr.get("city") or addr.get("town") or addr.get("village", ""),
                    "timezone": "", # Nominatim doesn't provide timezone directly
                    "source": "nominatim"
                }
    except Exception as e:
        print(f"Nominatim error for {location}: {e}")
    return None

def batch_geocode(locations: List[str]) -> Dict[str, Optional[Dict]]:
    """Geocode multiple locations."""
    results = {}
    for loc in locations:
        results[loc] = geocode_location(loc)
        # Be nice to Nominatim if we are using it (1 sec delay)
        if not OPENCAGE_API_KEY:
            time.sleep(1.1) 
    return results
