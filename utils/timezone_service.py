"""
Timezone and country data utilities using RapidAPI
Provides timezone info and country details for local reminders
"""
import os
import requests
from typing import Optional, Dict
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")


def get_timezone_by_location(lat: float, lng: float) -> Optional[Dict]:
    """
    Get timezone information for given coordinates using RapidAPI timezone service
    
    Args:
        lat: Latitude
        lng: Longitude
    
    Returns:
        Dict with timezone details or None if failed
    """
    if not RAPIDAPI_KEY:
        print("Warning: RAPIDAPI_KEY not found in environment")
        return None
    
    try:
        # Using World Time API via RapidAPI
        url = "https://world-time2.p.rapidapi.com/timezone/coordinate"
        
        querystring = {"lat": str(lat), "lng": str(lng)}
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "world-time2.p.rapidapi.com"
        }
        
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "timezone": data.get("timezone", "UTC"),
            "datetime": data.get("datetime", ""),
            "utc_offset": data.get("utc_offset", "+00:00"),
            "day_of_week": data.get("day_of_week", 0),
            "day_of_year": data.get("day_of_year", 0)
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Timezone lookup error for ({lat}, {lng}): {e}")
        return None


def get_country_info(country_code: str) -> Optional[Dict]:
    """
    Get detailed country information using RapidAPI
    
    Args:
        country_code: ISO country code (e.g., "US", "FR")
    
    Returns:
        Dict with country details or None if failed
    """
    if not RAPIDAPI_KEY:
        print("Warning: RAPIDAPI_KEY not found in environment")
        return None
    
    try:
        # Using REST Countries API via RapidAPI
        url = f"https://restcountries-v1.p.rapidapi.com/alpha/{country_code.lower()}"
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "restcountries-v1.p.rapidapi.com"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "name": data.get("name", ""),
            "capital": data.get("capital", ""),
            "region": data.get("region", ""),
            "subregion": data.get("subregion", ""),
            "population": data.get("population", 0),
            "currencies": data.get("currencies", []),
            "languages": data.get("languages", []),
            "timezones": data.get("timezones", []),
            "calling_codes": data.get("callingCodes", [])
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Country info lookup error for '{country_code}': {e}")
        return None


def calculate_local_time(timezone_offset: str) -> str:
    """
    Calculate local time given a UTC offset
    
    Args:
        timezone_offset: UTC offset string (e.g., "+05:30", "-08:00")
    
    Returns:
        Local time string in ISO format
    """
    try:
        from datetime import timezone, timedelta
        
        # Parse offset (e.g., "+05:30" or "-08:00")
        sign = 1 if timezone_offset[0] == '+' else -1
        hours, minutes = map(int, timezone_offset[1:].split(':'))
        offset = timedelta(hours=sign * hours, minutes=sign * minutes)
        
        # Calculate local time
        utc_now = datetime.now(timezone.utc)
        local_time = utc_now + offset
        
        return local_time.isoformat()
        
    except Exception as e:
        print(f"Local time calculation error: {e}")
        return datetime.now().isoformat()
