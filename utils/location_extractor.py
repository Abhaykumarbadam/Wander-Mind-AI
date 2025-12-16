import re
import json
from typing import List, Dict, Optional, Any
from utils.geocoding import geocode_location

def extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Extracts the JSON block from the LLM response.
    """
    try:
        # Look for ```json ... ``` or just { ... } at the end
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Fallback: look for last curly brace block
        # This is risky but might catch cases where code fences are missing
        last_brace = text.rfind('}')
        first_brace = text.find('{')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            potential_json = text[first_brace:last_brace+1]
            try:
                return json.loads(potential_json)
            except:
                pass
                
        return None
    except Exception as e:
        print(f"JSON extraction error: {e}")
        return None

def extract_locations_from_itinerary(itinerary_text: str) -> List[str]:
    """
    Fallback: Extract potential location names from the itinerary text using regex.
    """
    if not itinerary_text:
        return []
    
    # Pattern: **Location Name**
    bold_pattern = r"\*\*([^*]+)\*\*"
    matches = re.findall(bold_pattern, itinerary_text)
    
    exclude_terms = [
        "morning", "afternoon", "evening", "lunch", "dinner", 
        "day", "night", "breakfast", "arrival", "departure",
        "check-in", "check-out", "optional", "note", "tip",
        "pro tip", "cost", "time needed", "how to get there",
        "what to do", "what to expect", "transport", "activity",
        "restaurant", "hotel", "accommodation"
    ]
    
    locations = []
    for m in matches:
        clean = m.strip()
        # Heuristic cleaning
        clean = re.sub(r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*-\s*", "", clean)
        
        if clean.lower() not in exclude_terms and len(clean) > 2:
            locations.append(clean)
            
    # Remove duplicates
    seen = set()
    unique_locations = []
    for loc in locations:
        if loc.lower() not in seen:
            seen.add(loc.lower())
            unique_locations.append(loc)
            
    return unique_locations

def get_trip_data(itinerary_text: str) -> Dict[str, Any]:
    """
    Main entry point: Parse itinerary text to get structured data.
    Returns a dict with 'locations' (geocoded) and 'structure' (the raw JSON if found).
    """
    
    # 1. Try to extract structured JSON
    structured_data = extract_json_from_response(itinerary_text)
    
    locations_to_geocode = []
    
    if structured_data:
        # Use inner_locations from JSON
        if "inner_locations" in structured_data:
            for item in structured_data["inner_locations"]:
                if isinstance(item, dict) and "name" in item:
                    locations_to_geocode.append(item["name"])
                elif isinstance(item, str):
                    locations_to_geocode.append(item)
                    
        # Also add places from daily activities
        if "days" in structured_data:
            for day in structured_data["days"]:
                if "activities" in day:
                    for act in day["activities"]:
                        if "place" in act:
                            locations_to_geocode.append(act["place"])
    else:
        # Fallback to regex
        locations_to_geocode = extract_locations_from_itinerary(itinerary_text)
    
    # Deduplicate
    locations_to_geocode = list(set(locations_to_geocode))[:20] # Limit to 20
    
    # Geocode
    geocoded_locations = []
    for loc_name in locations_to_geocode:
        geo = geocode_location(loc_name)
        if geo:
            # Add extra metadata if available from structured data
            geo["name"] = loc_name # Ensure name is preserved
            geocoded_locations.append(geo)
            
    return {
        "structured_itinerary": structured_data,
        "geocoded_locations": geocoded_locations
    }

# Legacy wrapper for compatibility
def get_trip_locations(itinerary_text: str) -> List[Dict]:
    data = get_trip_data(itinerary_text)
    return data["geocoded_locations"]
