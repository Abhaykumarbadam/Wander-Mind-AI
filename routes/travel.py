from fastapi import APIRouter, Request, HTTPException, Depends, Body
from firebase_admin import auth
import httpx
import os
import json
import logging
import re
from pymongo import MongoClient
from datetime import datetime
from urllib.parse import urlencode, quote
from core.llm import run_gemini

router = APIRouter()

# Logger for this module
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGODB_URI")
# Ensure MONGO_URI is set, otherwise handle gracefully or let it fail if critical
if not MONGO_URI:
    # Fallback or error? The user provided snippet assumes it works.
    # I'll assume it's set in .env
    pass

mongo_client = MongoClient(MONGO_URI)
db_name = os.getenv("MONGO_DBNAME", "wandermind_db")
db = mongo_client[db_name]
searches = db["travel_searches"]

# N8N INTEGRATION COMMENTED OUT - Using fallback only
# N8N_TRAVEL_WEBHOOK = os.getenv("N8N_TRAVEL_WEBHOOK")  # example: https://your-domain/webhook/travel-search-all
# # Provide a safe local default for development when env var is not set.
# # This prevents immediate 500 responses during local testing. Encourage setting
# # the env var in production or when running n8n on a different host.
# if not N8N_TRAVEL_WEBHOOK:
#     N8N_TRAVEL_WEBHOOK = "http://127.0.0.1:5678/webhook/travel-search-all"
#     # note: keep a server-side warning during startup rather than raising here


INDIAN_IATA_CODES = {
    "DEL",
    "BOM",
    "BLR",
    "HYD",
    "MAA",
    "CCU",
    "COK",
    "GOI",
    "AMD",
    "PNQ",
    "PAT",
    "GAU",
    "JAI",
    "TRV",
    "IXC",
    "VNS",
    "IXE",
    "IXM",
    "NAG",
    "BBI",
    "RPR",
}

INDIAN_CITIES = {
    "delhi",
    "new delhi",
    "mumbai",
    "bombay",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "chennai",
    "kolkata",
    "calcutta",
    "kochi",
    "goa",
    "ahmedabad",
    "pune",
    "patna",
    "guwahati",
    "jaipur",
    "trivandrum",
    "chandigarh",
    "varanasi",
    "mangalore",
    "madurai",
    "nagpur",
    "bhubaneswar",
    "raipur",
}


CITY_TO_IATA = {
    "hyderabad": "HYD",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "bombay": "BOM",
    "bengaluru": "BLR",
    "bangalore": "BLR",
    "chennai": "MAA",
    "kolkata": "CCU",
    "calcutta": "CCU",
    "kochi": "COK",
    "cochin": "COK",
    "goa": "GOI",
    "ahmedabad": "AMD",
    "pune": "PNQ",
    "patna": "PAT",
    "guwahati": "GAU",
    "jaipur": "JAI",
    "trivandrum": "TRV",
    "thiruvananthapuram": "TRV",
    "chandigarh": "IXC",
    "varanasi": "VNS",
    "mangalore": "IXE",
    "madurai": "IXM",
    "nagpur": "NAG",
    "bhubaneswar": "BBI",
    "raipur": "RPR",
    # Tourist destinations - map to nearest airports
    "ooty": "CJB",  # Coimbatore
    "ootacamund": "CJB",
    "coimbatore": "CJB",
    "manali": "KUU",  # Kullu-Manali
    "shimla": "SLV",  # Shimla
    "darjeeling": "IXB",  # Bagdogra
    "srinagar": "SXR",
    "kashmir": "SXR",
    "leh": "IXL",
    "ladakh": "IXL",
    "mussoorie": "DED",  # Dehradun
    "dehradun": "DED",
    "nainital": "PGH",  # Pantnagar
    "munnar": "COK",  # Cochin
    "kodaikanal": "IXM",  # Madurai
    "pondicherry": "PNY",
    "puducherry": "PNY",
    "udaipur": "UDR",
    "jodhpur": "JDH",
    "agra": "AGR",
    "amritsar": "ATQ",
    "kathmandu": "KTM",
    "dubai": "DXB",
    "singapore": "SIN",
    "bangkok": "BKK",
    "paris": "CDG",
    "london": "LHR",
    "new york": "JFK",
    "tokyo": "HND",
    "osaka": "KIX",
    "bali": "DPS",
    "denpasar": "DPS",
    "sydney": "SYD",
    "melbourne": "MEL",
    "rome": "FCO",
    "milan": "MXP",
}


def _normalize_location(value: str) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _is_domestic_trip(metadata: dict) -> bool:
    origin = metadata.get("origin")
    destination = metadata.get("destination")

    if not origin or not destination:
        return False

    origin_norm = _normalize_location(origin)
    dest_norm = _normalize_location(destination)

    # If user already supplied IATA codes, check known Indian ones
    if len(origin) == 3 and len(destination) == 3:
        return origin.upper() in INDIAN_IATA_CODES and destination.upper() in INDIAN_IATA_CODES

    return origin_norm in INDIAN_CITIES and dest_norm in INDIAN_CITIES


def _guess_iata_code(value: str):
    if not value or not isinstance(value, str):
        return None

    value_strip = value.strip()

    if re.fullmatch(r"[A-Za-z]{3}", value_strip):
        return value_strip.upper()

    paren_match = re.search(r"\(([A-Za-z]{3})\)", value_strip)
    if paren_match:
        return paren_match.group(1).upper()

    code_match = re.search(r"\b([A-Za-z]{3})\b", value_strip.upper())
    if code_match:
        candidate = code_match.group(1).upper()
        if candidate in CITY_TO_IATA.values():
            return candidate

    normalized = _normalize_location(value_strip)
    if normalized in CITY_TO_IATA:
        return CITY_TO_IATA[normalized]

    if "," in normalized:
        first = normalized.split(",")[0].strip()
        if first in CITY_TO_IATA:
            return CITY_TO_IATA[first]

    return None


def _extract_trip_window(body: dict):
    """Normalize start/end dates from request body."""
    start_date = body.get("start_date") or body.get("date")
    end_date = body.get("end_date") or start_date
    if not start_date:
        start_date = datetime.utcnow().strftime("%Y-%m-%d")
    if not end_date:
        end_date = start_date
    return start_date, end_date


def _ensure_list(value):
    return value if isinstance(value, list) else []


def _metadata_from_body(body: dict):
    start_date, end_date = _extract_trip_window(body)
    try:
        passengers = int(body.get("passengers", 1))
    except (TypeError, ValueError):
        passengers = 1
    origin = body.get("origin")
    destination = body.get("destination")
    return {
        "origin": origin,
        "destination": destination,
        "origin_code": _guess_iata_code(origin),
        "destination_code": _guess_iata_code(destination),
        "start_date": start_date,
        "end_date": end_date,
        "passengers": passengers,
    }


def _result_counts(payload: dict):
    summary = {}
    total = 0
    for key in ["flights", "hotels", "trains", "buses"]:
        count = len(_ensure_list(payload.get(key)))
        summary[key] = count
        total += count
    return total, summary


def _default_fallback_options(metadata: dict):
    origin = metadata.get("origin") or "Origin City"
    destination = metadata.get("destination") or "Destination City"
    origin_code = metadata.get("origin_code") or _guess_iata_code(origin) or (origin[:3].upper() if origin else "ORG")
    destination_code = metadata.get("destination_code") or _guess_iata_code(destination) or (destination[:3].upper() if destination else "DST")
    start_date = metadata.get("start_date")
    end_date = metadata.get("end_date")
    domestic = _is_domestic_trip(metadata)

    fallback_trains = [
        {
            "name": f"{destination} Explorer",
            "duration": "6h 30m",
            "price": "₹2,400",
            "booking_link": "https://www.irctc.co.in/",
        }
    ] if domestic else []

    fallback_buses = [
        {
            "name": f"{destination} Nightliner",
            "duration": "10h 15m",
            "price": "₹1,100",
            "booking_link": "https://www.redbus.in/",
        }
    ] if domestic else []

    return {
        "flights": [
            {
                "airline": f"{destination} Express",
                "flight_number": "WM101",
                "departure_airport": f"{origin} ({origin_code})",
                "arrival_airport": f"{destination} ({destination_code})",
                "departure_time": f"{start_date}T08:00:00",
                "arrival_time": f"{start_date}T12:00:00",
                "flight_date": start_date,
                "status": "scheduled",
                "price": "₹9,800",
                "booking_link": "https://www.makemytrip.com/",
            },
            {
                "airline": f"{origin} Airways",
                "flight_number": "WM207",
                "departure_airport": f"{origin} ({origin_code})",
                "arrival_airport": f"{destination} ({destination_code})",
                "departure_time": f"{start_date}T16:00:00",
                "arrival_time": f"{start_date}T20:30:00",
                "flight_date": start_date,
                "status": "scheduled",
                "price": "₹11,200",
                "booking_link": "https://www.makemytrip.com/",
            },
        ],
        "hotels": [
            {
                "name": f"{destination} Skyline Suites",
                "location": f"Central {destination}",
                "price": "₹12,500/night",
                "duration": f"{start_date} to {end_date}",
                "booking_link": "https://www.booking.com/",
            },
            {
                "name": f"{destination} Heritage Stay",
                "location": "Old Town",
                "price": "₹8,900/night",
                "duration": f"{start_date} to {end_date}",
                "booking_link": "https://www.airbnb.com/",
            },
        ],
        "trains": fallback_trains,
        "buses": fallback_buses,
    }


async def fetch_airport_guidance(destination: str):
    if not destination:
        return {}

    prompt = f"""
You are a travel routing assistant. A traveler is visiting "{destination}" which might not have a commercial airport in town.
Return ONLY valid JSON with the following structure:
{{
  "nearest_airport": {{
    "name": "",
    "code": "",
    "distance_km": "",
    "notes": ""
  }},
  "alternate_airports": [
    {{"name": "", "code": "", "notes": ""}}
  ],
  "railway_access": [
    {{"name": "", "notes": ""}}
  ],
  "ground_transport": [
    {{ "option": "", "notes": "" }}
  ]
}}

Rules:
- Use uppercase IATA codes when available.
- If the town already has a well-known airport, still include it as nearest.
- Keep notes concise (<= 2 sentences).
- If unsure, return empty arrays but keep JSON valid.
"""
    try:
        response = await run_gemini(prompt)
        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(response[start : end + 1])
    except Exception as err:
        logger.warning("Failed to fetch airport guidance for %s: %s", destination, err)
    return {}


async def enrich_destination_airport(metadata: dict):
    destination = metadata.get("destination")
    if not destination:
        return

    if metadata.get("destination_code"):
        return

    guidance = await fetch_airport_guidance(destination)
    if not guidance:
        return

    nearest = guidance.get("nearest_airport") or {}
    code = nearest.get("code")
    if code:
        metadata["destination_code"] = code.upper()
    metadata["airport_guidance"] = guidance


async def generate_fallback_travel_plan(body: dict, reason: str = "", metadata_override: dict | None = None) -> dict:
    """Generate transport options via Gemini (primary method, n8n disabled)."""
    metadata = metadata_override or _metadata_from_body(body)
    origin = metadata["origin"] or "Origin City"
    destination = metadata["destination"] or "Destination City"
    passengers = metadata["passengers"]
    start_date = metadata["start_date"]
    end_date = metadata["end_date"]

    prompt = f"""
The Aviationstack flight API is currently unavailable because: {reason or "an unknown error occurred"}.
Create a compact JSON object with realistic flight, hotel, train, and bus options for a trip from {origin} to {destination}
for {passengers} traveller(s) between {start_date} and {end_date}.
Return ONLY valid JSON with this structure:
{{
  "flights": [{{"airline":"","flight_number":"","departure_airport":"","arrival_airport":"","departure_time":"","arrival_time":"","flight_date":"","status":"","price":"","booking_link":""}}],
  "hotels": [{{"name":"","location":"","price":"","duration":"","booking_link":""}}],
  "trains": [{{"name":"","duration":"","price":"","booking_link":""}}],
  "buses": [{{"name":"","duration":"","price":"","booking_link":""}}],
  "messages": ["short status note"]
}}
Use INR currency and ensure booking links point to reputable aggregators (Booking, Airbnb, MakeMyTrip, Redbus, IRCTC, etc.).
"""

    parsed = {}
    try:
        response_text = await run_gemini(prompt)
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_payload = response_text[start_idx : end_idx + 1]
            parsed = json.loads(json_payload)
        else:
            logger.error("Fallback LLM response did not contain JSON: %s", response_text)
    except Exception as err:
        logger.exception("Fallback LLM generation failed: %s", err)

    defaults = _default_fallback_options(metadata)
    domestic = _is_domestic_trip(metadata)

    fallback = {
        "flights": _ensure_list(parsed.get("flights")) or defaults["flights"],
        "hotels": _ensure_list(parsed.get("hotels")) or defaults["hotels"],
        "trains": (_ensure_list(parsed.get("trains")) or defaults["trains"]) if domestic else [],
        "buses": (_ensure_list(parsed.get("buses")) or defaults["buses"]) if domestic else [],
        "metadata": parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else metadata,
        "messages": _ensure_list(parsed.get("messages")),
        "fallback_used": True,
        "source": "gemini-fallback",
    }
    if metadata_override and metadata_override.get("airport_guidance"):
        fallback["metadata"].setdefault("airport_guidance", metadata_override["airport_guidance"])
    fallback["messages"].append(
        f"Travel plan generated via Gemini: {reason or 'n8n disabled'}"
    )
    return fallback


# ------------------------
# Firebase Auth dependency
# ------------------------
async def verify_firebase_user(request: Request):
    id_token = request.headers.get("Authorization")
    if not id_token:
        raise HTTPException(status_code=401, detail="Missing Firebase token")

    id_token = id_token.replace("Bearer ", "")
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")


# ---------------------------------
# TRAVEL SEARCH ENDPOINT (main one)
# ---------------------------------
@router.post("/travel/search")
async def travel_search(request: Request, user=Depends(verify_firebase_user)):
    body = await request.json()

    # Validate body
    # Accept either a single 'date' (one-day search) OR a 'start_date' and 'end_date' range.
    required_base = ["type", "origin", "destination"]
    if any(k not in body for k in required_base):
        raise HTTPException(400, "Missing travel search parameters: 'type', 'origin', and 'destination' are required")

    has_single_date = "date" in body and body.get("date")
    has_date_range = "start_date" in body and "end_date" in body and body.get("start_date") and body.get("end_date")
    if not (has_single_date or has_date_range):
        raise HTTPException(400, "Missing travel search date: provide either 'date' or both 'start_date' and 'end_date'")

    metadata = _metadata_from_body(body)
    await enrich_destination_airport(metadata)
    data = {}
    
    # N8N INTEGRATION COMMENTED OUT - Using direct fallback
    # n8n_error_reason = None

    # # Forward request to n8n workflow
    # try:
    #     async with httpx.AsyncClient() as client:
    #         # Increase timeout because workflows may take longer when waiting for external APIs
    #         n8n_response = await client.post(
    #             N8N_TRAVEL_WEBHOOK,
    #             json=body,
    #             timeout=60
    #         )

    #     if 200 <= n8n_response.status_code < 300:
    #         try:
    #             data = n8n_response.json()
    #         except Exception as parse_err:
    #             raw = n8n_response.text
    #             n8n_error_reason = f"n8n returned non-JSON response: {parse_err}; raw={raw}"
    #     else:
    #         n8n_error_reason = f"n8n returned status {n8n_response.status_code}: {n8n_response.text}"

    # except httpx.RequestError as req_err:
    #     n8n_error_reason = f"httpx request to n8n failed: {str(req_err)}"
    # except Exception as e:
    #     n8n_error_reason = f"Unexpected error while calling n8n: {str(e)}"

    # if n8n_error_reason:
    #     logger.error("n8n workflow failed, using fallback: %s", n8n_error_reason)
    #     data = await generate_fallback_travel_plan(body, n8n_error_reason, metadata)
    # else:
    #     if not isinstance(data, dict):
    #         data = {"raw": data}

    #     flights_available = len(_ensure_list(data.get("flights"))) > 0
    #     if not flights_available:
    #         logger.warning("Aviationstack returned no flights; enriching response with fallback data")
    #         fallback_data = await generate_fallback_travel_plan(body, "Aviationstack returned no flights", metadata)
    #         data["flights"] = fallback_data.get("flights", [])
    #         data.setdefault("messages", []).append("Flights populated via fallback plan.")
    #         data["fallback_used"] = True
    #         data.setdefault("metadata", fallback_data.get("metadata"))
    #     else:
    #         data.setdefault("metadata", metadata)
    
    # Using direct fallback instead of n8n
    logger.info("Using direct fallback travel plan (n8n disabled)")
    data = await generate_fallback_travel_plan(body, "n8n integration disabled", metadata)

    # Log query to MongoDB
    try:
        total_results, category_counts = _result_counts(data)
        searches.insert_one({
            "user_id": user["uid"],
            "query": body,
            "results_count": total_results,
            "category_counts": category_counts,
            "fallback_used": bool(data.get("fallback_used")),
            "timestamp": datetime.utcnow()
        })
    except Exception as db_err:
        logger.warning("Failed to log travel search: %s", db_err)

    # Return results from fallback (n8n disabled)
    return {
        "status": "success",
        "type": body.get("type"),
        "origin": body.get("origin"),
        "destination": body.get("destination"),
        "metadata": data.get("metadata", metadata),
        "source": data.get("source", "fallback"),
        "messages": data.get("messages", []),
        "fallback_used": True,
        "flights": data.get("flights", []) if isinstance(data, dict) else [],
        "hotels": data.get("hotels", []) if isinstance(data, dict) else [],
        "trains": data.get("trains", []) if isinstance(data, dict) else [],
        "buses": data.get("buses", []) if isinstance(data, dict) else []
    }


# ============================================================================
# NEW BOOKING LINKS FEATURE - Replaces n8n workflow
# ============================================================================

async def get_nearest_airport_via_groq(city: str) -> dict:
    """
    Use Groq LLM to detect nearest major airport from city name.
    Returns dict with airport code, name, and country.
    """
    if not city:
        return {"code": "", "name": "", "country": ""}
    
    # Clean the city name
    city = city.strip()
    
    # Check if it's already a known IATA code
    city_normalized = _normalize_location(city)
    if city_normalized in CITY_TO_IATA:
        iata_code = CITY_TO_IATA[city_normalized]
        return {
            "code": iata_code,
            "name": f"{city} Airport",
            "country": "IN" if iata_code in INDIAN_IATA_CODES else "US"
        }
    
    # Use Groq/Gemini to detect airport
    prompt = f"""You are an expert travel assistant. Given the city/location/tourist destination: "{city}"

IMPORTANT INSTRUCTIONS:
1. Find the NEAREST MAJOR INTERNATIONAL AIRPORT that travelers would use to reach this destination
2. For tourist destinations, hill stations, or small towns, find the nearest big city's airport
3. ALWAYS verify the city/destination's country and region FIRST before selecting airport
4. Use 3-letter IATA codes only (NOT 4-letter ICAO codes)
5. Return ONLY valid JSON, no explanations

Return ONLY a valid JSON object with this exact structure:
{{
    "code": "XXX",
    "name": "Airport Full Name",
    "country": "2-LETTER-CODE"
}}

EXAMPLES:
- For "Ooty" (Tamil Nadu, India) return {{"code": "CJB", "name": "Coimbatore International Airport", "country": "IN"}}
- For "Manali" (Himachal Pradesh, India) return {{"code": "KUU", "name": "Kullu Manali Airport", "country": "IN"}}
- For "Goa" (India) return {{"code": "GOI", "name": "Goa International Airport", "country": "IN"}}
- For "Hyderabad" (India) return {{"code": "HYD", "name": "Rajiv Gandhi International Airport", "country": "IN"}}
- For "Dubai" (UAE) return {{"code": "DXB", "name": "Dubai International Airport", "country": "AE"}}
- For "Paris" (France) return {{"code": "CDG", "name": "Charles de Gaulle Airport", "country": "FR"}}
- For "Kashmir" (India) return {{"code": "SXR", "name": "Srinagar Airport", "country": "IN"}}
- For "Kodaikanal" (Tamil Nadu, India) return {{"code": "IXM", "name": "Madurai Airport", "country": "IN"}}

CRITICAL: 
- First identify which country/state the destination is in
- Then find the nearest airport travelers actually use
- For hill stations and tourist towns in India, use nearby city airports
- NEVER confuse Indian destinations with international locations

Return ONLY the JSON object for: "{city}" """
    
    try:
        response = await run_gemini(prompt)
        logger.info(f"🤖 Groq raw response for '{city}': {response[:200]}")
        
        # Clean response - remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Remove code blocks
            lines = response.split("\n")
            response = "\n".join([line for line in lines if not line.startswith("```")])
        response = response.strip()
        
        # Remove any "json" or "JSON" text after code block markers
        if response.lower().startswith("json"):
            response = response[4:].strip()
        
        logger.info(f"🧹 Cleaned response: {response[:200]}")
        
        airport_data = json.loads(response)
        logger.info(f"✅ Parsed airport data: {airport_data}")
        return airport_data
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error for '{city}': {e}")
        logger.error(f"   Response was: {response[:500]}")
        # Fallback - try to extract from known mappings
        city_lower = city.lower().strip()
        if city_lower in CITY_TO_IATA:
            code = CITY_TO_IATA[city_lower]
            return {
                "code": code,
                "name": f"{city} Airport",
                "country": "IN" if code in INDIAN_IATA_CODES else "US"
            }
        # Ultimate fallback
        return {
            "code": city[:3].upper() if len(city) >= 3 else "XXX",
            "name": f"{city} Airport",
            "country": "IN"
        }
    except Exception as e:
        logger.error(f"❌ Failed to get airport via Groq for '{city}': {e}")
        # Fallback - return basic structure
        return {
            "code": city[:3].upper() if len(city) >= 3 else "XXX",
            "name": f"{city} Airport",
            "country": "IN"
        }


def build_hotel_url(options: dict) -> str:
    """
    Build Booking.com hotel search URL.
    
    Args:
        options: dict with keys: destination, checkin, checkout, adults, rooms, sort
    
    Returns:
        Full Booking.com hotel search URL
    """
    destination = options.get("destination", "")
    checkin = options.get("checkin", "")
    checkout = options.get("checkout", "")
    
    # Log what we're building with
    logger.info(f"🏨 Building hotel URL for: {destination}")
    logger.info(f"   Check-in: {checkin}, Check-out: {checkout}")
    
    params = {
        "ss": destination,
        "checkin": checkin,
        "checkout": checkout,
        "group_adults": options.get("adults", 2),
        "no_rooms": options.get("rooms", 1),
        "order": options.get("sort", "bayesian_review_score")
    }
    
    # Remove empty values
    params = {k: v for k, v in params.items() if v}
    
    query_string = urlencode(params)
    url = f"https://www.booking.com/searchresults.html?{query_string}"
    logger.info(f"🏨 Generated hotel URL: {url}")
    return url


def build_flight_url(options: dict) -> str:
    """
    Build Booking.com flights search URL.
    
    Args:
        options: dict with keys:
            - origin: airport code (e.g., "HYD")
            - destination: airport code (e.g., "DXB")
            - origin_name: origin airport name
            - dest_name: destination airport name
            - origin_country: origin country code
            - dest_country: destination country code
            - depart: departure date (YYYY-MM-DD)
            - return_date: return date (YYYY-MM-DD)
            - adults: number of adults
            - children: number of children
            - trip_type: ROUNDTRIP or ONEWAY
            - cabin: ECONOMY, BUSINESS, etc.
            - sort: BEST, CHEAPEST, FASTEST
    
    Returns:
        Full Booking.com flights search URL
    """
    origin = options.get("origin", "")
    dest = options.get("destination", "")
    depart_date = options.get("depart", "")
    return_date = options.get("return_date", "")
    
    # Log what we're building with
    logger.info(f"✈️ Building flight URL for: {origin} -> {dest}")
    logger.info(f"   Dates: {depart_date} to {return_date}")
    
    if not origin or not dest:
        logger.warning("⚠️ Missing origin or destination for flight URL")
        return "https://flights.booking.com/"
    
    params = {
        "type": options.get("trip_type", "ROUNDTRIP"),
        "adults": options.get("adults", 2),
        "cabinClass": options.get("cabin", "ECONOMY"),
        "children": options.get("children", 0),
        "from": origin,
        "to": dest,
        "fromCountry": options.get("origin_country", "IN"),
        "toCountry": options.get("dest_country", "AE"),
        "fromLocationName": options.get("origin_name", origin),
        "toLocationName": options.get("dest_name", dest),
        "depart": depart_date,
        "return": return_date,
        "sort": options.get("sort", "BEST"),
        "travelPurpose": options.get("purpose", "leisure")
    }
    
    # Remove empty values
    params = {k: v for k, v in params.items() if v}
    query_string = urlencode(params)
    
    url = f"https://flights.booking.com/flights/{origin}-{dest}/?{query_string}"
    logger.info(f"✈️ Generated flight URL: {url}")
    return url


@router.post("/travel/booking-links")
async def generate_booking_links(body: dict = Body(...)):
    """
    Generate Booking.com hotel and flight URLs based on user input.
    Uses Groq/Gemini to detect nearest airport from city/location.
    
    Request body:
        - origin: origin city (e.g., "Hyderabad") - optional, will extract from metadata
        - destination: destination city (e.g., "Dubai") - optional, will extract from metadata
        - start_date: check-in / departure date (YYYY-MM-DD) - optional
        - end_date: check-out / return date (YYYY-MM-DD) - optional
        - passengers: number of passengers (default: 2)
        - rooms: number of rooms (default: 1)
        - trip_type: ROUNDTRIP or ONEWAY (default: ROUNDTRIP)
        - metadata: optional metadata object with origin/destination
    
    Returns:
        {
            "hotel_url": "https://booking.com/...",
            "flight_url": "https://flights.booking.com/...",
            "origin_airport": {...},
            "dest_airport": {...}
        }
    """
    try:
        # Extract user input - try multiple sources
        metadata = body.get("metadata", {})
        origin_city = body.get("origin") or metadata.get("origin", "")
        destination_city = body.get("destination") or metadata.get("destination", "")
        start_date = body.get("start_date") or body.get("startDate", "")
        end_date = body.get("end_date") or body.get("endDate", "")
        passengers = body.get("passengers", 2)
        rooms = body.get("rooms", 1)
        trip_type = body.get("trip_type", "ROUNDTRIP")
        
        if not destination_city:
            # If still no destination, return error with helpful message
            raise HTTPException(400, "Missing required field: destination (or destination in metadata)")
        
        # Clean and normalize destination
        destination_city = destination_city.strip()
        
        # Log received data for debugging
        logger.info(f"📥 Received booking request:")
        logger.info(f"   Origin: {origin_city}")
        logger.info(f"   Destination: {destination_city}")
        logger.info(f"   Dates: {start_date} to {end_date}")
        logger.info(f"   Passengers: {passengers}, Rooms: {rooms}")
        
        # Get airport codes from cities using Groq
        logger.info(f"🔍 Detecting airports for: {origin_city} -> {destination_city}")
        
        # Determine origin for flight: if missing or identical, suppress flight URL
        origin_city_for_flight = origin_city.strip() if origin_city and origin_city.strip().lower() != destination_city.lower() else ""

        dest_airport = await get_nearest_airport_via_groq(destination_city)
        origin_airport = {}
        if origin_city_for_flight:
            origin_airport = await get_nearest_airport_via_groq(origin_city_for_flight)
            logger.info(f"✈️ Origin Airport: {origin_airport}")
        else:
            logger.warning("⚠️ Origin missing or identical to destination; flight URL will be omitted.")
        logger.info(f"✈️ Destination Airport: {dest_airport}")
        if origin_airport and origin_airport.get('code') and dest_airport.get('code'):
            logger.info(f"🎯 Final Route: {origin_airport['code']} ({origin_airport['name']}) -> {dest_airport['code']} ({dest_airport['name']})")
        
        # Build hotel URL
        hotel_url = build_hotel_url({
            "destination": destination_city,
            "checkin": start_date,
            "checkout": end_date,
            "adults": passengers,
            "rooms": rooms
        })
        
        # Build flight URL only if distinct origin and destination airports present
        flight_url = None
        if origin_airport and origin_airport.get("code") and dest_airport.get("code") and origin_airport.get("code") != dest_airport.get("code"):
            flight_url = build_flight_url({
                "origin": origin_airport["code"],
                "destination": dest_airport["code"],
                "origin_name": origin_airport.get("name"),
                "dest_name": dest_airport.get("name"),
                "origin_country": origin_airport.get("country"),
                "dest_country": dest_airport.get("country"),
                "depart": start_date,
                "return_date": end_date,
                "adults": passengers,
                "trip_type": trip_type
            })
        else:
            if origin_airport and dest_airport and origin_airport.get("code") == dest_airport.get("code"):
                logger.warning("⚠️ Origin and destination airport codes identical; suppressing flight URL.")
        
        # Log generated URLs for verification
        logger.info("="*80)
        logger.info("🔗 BOOKING LINKS GENERATED:")
        logger.info("="*80)
        logger.info(f"✈️  FLIGHT LINK: {flight_url if flight_url else '(none)'}")
        logger.info(f"🏨 HOTEL LINK: {hotel_url}")
        logger.info("="*80)
        
        return {
            "status": "success",
            "hotel_url": hotel_url,
            "flight_url": flight_url,
            "origin_airport": origin_airport if origin_airport else {"code":"","name":"","country":""},
            "dest_airport": dest_airport
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating booking links: {e}")
        raise HTTPException(500, f"Failed to generate booking links: {str(e)}")
