# app.py
import os, json, re
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
import httpx

# this loads .env manually and injects into os.environ BEFORE anything

from fastapi import FastAPI, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from dotenv import load_dotenv
load_dotenv()


from core.llm import chat, chat_async
from core.prompts import BASE_SYSTEM_AURA, ASKER_SYSTEM, ITINERARY_SYSTEM_PROMPT, DATA_STRUCTURING_SYSTEM, AURA_V2_SYSTEM
from core.extract import extract_profile, extract_deltas, extract_profile_updates, structure_itinerary_data
from db.mongo import (
    get_or_create_profile, save_profile,
    get_or_create_session, append_message,
    get_last_user_messages, get_recent_messages,
    get_session_mode, set_session_mode,
    save_itinerary, get_itinerary, save_locations, get_locations, save_trip,
    reset_trip_fields, get_session_metadata,
    update_session_metadata,
    save_chat, get_user_chats, get_chat_by_id, update_chat_title,
    PREFERENCE_FIELDS, TRIP_FIELDS,
    db, sessions_col
)
from utils.location_extractor import get_trip_locations
from utils.geocoding import geocode_location
from utils.helpers import (
    missing_slots, merge_soft, apply_user_corrections,
    infer_transport_pref, infer_departure_location,
    parse_destinations, trip_total_days,
    normalize_city_split, slice_split_for_window,
    build_option_block_for, normalize_transport_preference, SLOT_OPTIONS
)

# RAG helper (uses src package RAG helper)
try:
    from src.rag import generate_answer as rag_generate_answer
except Exception:
    rag_generate_answer = None

# load_dotenv(dotenv_path="/Users/himatejagudi/Desktop/WM2/.env")

# CORS: Allow specific origins for security (use environment variable in production)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    origins = [origin.strip() for origin in allowed_origins_env.split(",")]
else:
    # Default to local development origins
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

from routes import travel

app = FastAPI(title="Aura Travel — LC + OpenAI + Mongo", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Include routers
app.include_router(travel.router)

try:
    from routes import accommodations, trips, trips_api, booking
    app.include_router(accommodations.router)
    app.include_router(trips.router)
    app.include_router(trips_api.router)
    app.include_router(booking.router)
except ImportError as e:
    print(f"Warning: Could not import new routers: {e}")

# ——— Models
from pydantic import BaseModel
class MessageRequest(BaseModel):
    user_message: Optional[str] = ""
    session_id: Optional[str] = None

# ——— Helper Functions
async def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Convert coordinates to city name using Nominatim API"""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10&addressdetails=1"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={
                'Accept-Language': 'en-US',
                'User-Agent': 'WanderMind/1.0'
            })
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if data and data.get('address'):
                # Prefer city > town > village > state
                return (data['address'].get('city') or 
                       data['address'].get('town') or 
                       data['address'].get('village') or 
                       data['address'].get('state'))
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return None
    return None

def is_coordinates(value: str) -> bool:
    """Check if string is coordinates like '17.306, 78.536'"""
    if not value or not isinstance(value, str):
        return False
    # Match patterns like "17.306, 78.536" or "17.306,78.536"
    coord_pattern = r'^[-+]?\d+\.?\d*\s*,\s*[-+]?\d+\.?\d*$'
    return bool(re.match(coord_pattern, value.strip()))

async def parse_location_field(value: str) -> str:
    """Convert coordinates to city name if needed"""
    if not value or not isinstance(value, str):
        return value or ''
    
    trimmed = value.strip()
    
    if is_coordinates(trimmed):
        try:
            lat, lon = map(float, trimmed.split(','))
            print(f"🌍 Detected coordinates: {lat}, {lon} - reverse geocoding...")
            city = await reverse_geocode(lat, lon)
            if city:
                print(f"✅ Reverse geocoded to: {city}")
                return city
            print("⚠️ Reverse geocoding failed")
        except ValueError:
            pass
    
    return trimmed

class PlanRequest(BaseModel):
    session_id: str
    city_day_split: Optional[List[Dict[str, object]]] = None
    extra_notes: Optional[str] = ""

class NewTripRequest(BaseModel):
    reset_preferences: Optional[bool] = False


class RagRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    # mode: 'retrieve' (return raw docs), 'answer' (current behavior), 'single' (single LLM call with raw docs)
    mode: Optional[str] = None

# ——— Interview prompt builder
def build_questions(profile: Dict) -> str:
    """
    Determine the next question to ask based on a strict sequence.
    Sequence: Name -> Destination -> Dates -> Interests -> Preferences -> Budget -> Food -> Travel Style -> Departure
    """
    # 1. Name (display_name) - handled in main loop if missing, but good to have here
    if not profile.get("display_name"):
        return "What's your name?"

    # 2. Destination
    if not profile.get("destination"):
        return "Where are you planning to go? (City, Country, or Region)"

    # 3. Dates
    if not profile.get("start_date") or not profile.get("end_date"):
        return "When are you planning to travel? (Approximate dates or month is fine!)"

    # 4. Interests
    if not profile.get("interests"):
        return "What kind of activities do you enjoy? (e.g., History, Nature, Food, Adventure, Relaxing)"

    # 5. Preferences (Pace & Accommodation)
    missing_prefs = []
    if not profile.get("pace"): missing_prefs.append("pace (Relaxed, Balanced, Fast)")
    if not profile.get("accommodation_level"): missing_prefs.append("accommodation style (Hostel, Hotel, Luxury)")
    
    if missing_prefs:
        return f"What's your preferred {' and '.join(missing_prefs)}?"

    # 6. Budget
    if not profile.get("budget_in_inr"):
        return "What's your approximate total budget for the trip (in INR)?"

    # 7. Food (Diet)
    if not profile.get("diet"):
        return "Do you have any dietary preferences or restrictions? (e.g., Veg, Non-Veg, Vegan)"

    # 8. Travel Style (Transport)
    if not profile.get("transport_preference"):
        return "How do you prefer to get around locally? (Public transport, Taxi, Rental car, Walking)"

    # 9. Departure Location
    if not profile.get("departure_location"):
        return "Where will you be departing from? (City/Airport)"

    return "All set."
import firebase_admin
from firebase_admin import credentials, auth as fb_auth

firebase_cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "./wandermindauth.json")
cred = credentials.Certificate(firebase_cred_path)
firebase_admin.initialize_app(cred)

def get_uid_from_token(authorization_header: Optional[str]) -> str:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        from fastapi import HTTPException, status
        print(f"DEBUG: Missing or invalid Authorization header: {authorization_header}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    try:
        token = authorization_header.split("Bearer ")[1].strip()
        print(f"DEBUG: Token received (first 20 chars): {token[:20]}...")
        # Add clock_skew_seconds to handle slight time differences between client and server
        decoded = fb_auth.verify_id_token(token, clock_skew_seconds=10)
        print(f"DEBUG: Token verified successfully for UID: {decoded['uid']}")
        return decoded["uid"]
    except Exception as e:
        from fastapi import HTTPException, status
        print(f"DEBUG: Token verification failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")


# ——— Health
@app.get("/")
def root():
    return {"ok": True, "hint": "POST /message and /plan"}



# ——— Message
@app.post("/message")
async def message(authorization: Optional[str] = Header(None), body: MessageRequest = Body(...)):
    # 1) session + profile
    user_id = get_uid_from_token(authorization)
    prof_doc = get_or_create_profile(user_id)
    profile = dict(prof_doc.get("profile", {}))

    # --- FIX: Normalize existing transport preference if it's non-standard
    existing_transport_pref = profile.get("transport_preference")
    if existing_transport_pref and existing_transport_pref not in SLOT_OPTIONS.get("transport_preference", []):
        normalized_tp = normalize_transport_preference(existing_transport_pref)
        if normalized_tp:
            profile["transport_preference"] = normalized_tp
            save_profile(user_id, profile)
            print(f"DEBUG: Corrected non-standard transport preference from '{existing_transport_pref}' to '{normalized_tp}'")
    # --- END FIX

    # Fallback: Check root level for display_name (legacy/migration)
    if not profile.get("display_name") and prof_doc.get("display_name"):
        print(f"DEBUG: Found display_name in root doc: {prof_doc.get('display_name')}. Migrating to profile.")
        profile["display_name"] = prof_doc.get("display_name")
        save_profile(user_id, profile)
    
    # Convert coordinates to city name in departure_location
    if profile.get("departure_location") and is_coordinates(profile["departure_location"]):
        city_name = await parse_location_field(profile["departure_location"])
        if city_name != profile["departure_location"]:
            profile["departure_location"] = city_name
            save_profile(user_id, profile)
            print(f"DEBUG: Converted departure_location coordinates to city: {city_name}")

    is_new_session = body.session_id is None
    session_id = get_or_create_session(body.session_id, user_id)
    session_meta = get_session_metadata(session_id)
    session_meta_updates: Dict[str, object] = {}

    def safe_snapshot(data: Dict) -> Dict:
        try:
            return json.loads(json.dumps(data, ensure_ascii=False))
        except Exception:
            return dict(data)

    if is_new_session:
        print(f"DEBUG: New session {session_id} started. Resetting trip fields for fresh start.")
        # Reset trip-specific fields so Aura asks questions again
        for field in TRIP_FIELDS:
            profile[field] = None
        save_profile(user_id, profile)

        session_meta_updates.update({
            "preferences_prompted": False,
            "preferences_confirmed": False,
            "confirmed_preferences": [],
        })
    if session_meta.get("profile_snapshot") is None:
        session_meta_updates["profile_snapshot"] = safe_snapshot(profile)

    # 2) Save user message
    append_message(session_id, "user", body.user_message, user_id)
    
    # NEW LOGIC: Single-shot Aura V2
    
    # Build history
    recent_msgs = get_recent_messages(session_id, k=10)
    history_text = "\n".join([f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in recent_msgs])
    
    # Build prompt
    from datetime import date
    today_str = date.today().isoformat()
    
    msgs = [
        {"role": "system", "content": AURA_V2_SYSTEM},
        {"role": "user", "content": f"CURRENT DATE: {today_str}\n\nUSER PROFILE:\n{json.dumps(profile, indent=2)}\n\nCHAT HISTORY:\n{history_text}\n\nLATEST USER MESSAGE:\n{body.user_message}"}
    ]
    
    # Call LLM
    try:
        response_text = await chat_async(msgs, temperature=0.4)
        print(f"DEBUG: Raw LLM response (first 200 chars): {response_text[:200]}")
        
        # Parse JSON
        import re
        
        response_data = {}
        try:
            response_data = json.loads(response_text)
            print(f"DEBUG: Successfully parsed JSON response")
        except Exception as e:
            print(f"DEBUG: Failed to parse as JSON: {e}")
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                try:
                    response_data = json.loads(match.group(0))
                    print(f"DEBUG: Successfully extracted JSON from text")
                except Exception as e2:
                    print(f"DEBUG: Failed to extract JSON: {e2}")
        
        if not response_data:
            print(f"DEBUG: No JSON found, treating entire response as plain text")
            response_data = {"assistant_response": response_text, "action": "none"}
            
        # Apply updates
        updates = response_data.get("profile_updates", {})
        if updates:
            clean_updates = {k: v for k, v in updates.items() if v not in (None, "", [])}
            
            # --- FIX: Normalize transport preference before saving
            if "transport_preference" in clean_updates:
                original_tp = clean_updates["transport_preference"]
                normalized_tp = normalize_transport_preference(original_tp)
                if normalized_tp:
                    clean_updates["transport_preference"] = normalized_tp
                    print(f"DEBUG: Normalized incoming transport preference from '{original_tp}' to '{normalized_tp}'")
                else:
                    # If it can't be normalized, remove it to avoid saving bad data
                    del clean_updates["transport_preference"]
                    print(f"DEBUG: Removed un-normalizable transport preference: '{original_tp}'")
            # --- END FIX

            if clean_updates:
                profile.update(clean_updates)
                save_profile(user_id, profile)
                print(f"DEBUG: Updated profile: {clean_updates}")
                
        # Handle action
        action = response_data.get("action")
        assistant_reply = response_data.get("assistant_response", "I'm here to help!")
        
        # SAFETY CHECK: Ensure assistant_reply is not JSON
        if isinstance(assistant_reply, str) and assistant_reply.strip().startswith("{"):
            print(f"WARNING: assistant_reply appears to be JSON, extracting text...")
            try:
                nested_json = json.loads(assistant_reply)
                assistant_reply = nested_json.get("assistant_response", assistant_reply)
            except:
                print(f"WARNING: Could not parse nested JSON, using as-is")
        
        print(f"DEBUG: Final assistant_reply (first 100 chars): {assistant_reply[:100]}")
        
        # Save assistant message
        append_message(session_id, "assistant", assistant_reply, user_id)
        
        if is_new_session:
            save_chat(user_id, session_id)
            
        # Ensure the response sent to the frontend is the plain text message
        final_response_payload = {
            "type": "ask",
            "session_id": session_id,
            "response": assistant_reply,
            "assistant_message": assistant_reply,
            "action": action
        }

        # If the original response was JSON, include it for debugging if needed,
        # but ensure the primary response is clean.
        if isinstance(response_text, str) and response_text.strip().startswith("{"):
            final_response_payload["_raw_llm_response"] = response_data

        return JSONResponse(final_response_payload)
        
    except Exception as e:
        print(f"Error in message handler: {e}")
        return JSONResponse({
            "type": "error",
            "session_id": session_id,
            "response": "I'm having trouble connecting. Please try again.",
            "assistant_message": "I'm having trouble connecting. Please try again."
        })

# ——— Plan
@app.post("/plan")
async def plan(authorization: Optional[str] = Header(None),body: PlanRequest = Body(...)):
    from utils.helpers import (
        parse_destinations, trip_total_days, normalize_city_split,
        slice_split_for_window
    )
    user_id = get_uid_from_token(authorization)

    prof_doc = get_or_create_profile(user_id)
    profile = dict(prof_doc.get("profile", {}))
    print(f"DEBUG: /plan called for user {user_id}")
    print(f"DEBUG: Profile data: {json.dumps(profile, default=str)}")

    must = [s for s in ["destination","start_date","end_date"] if not profile.get(s)]
    if must:
        print(f"DEBUG: Missing required fields: {must}")
        return JSONResponse(status_code=400, content={"type":"error","message":f"Missing: {', '.join(must)}"})

    cities = parse_destinations(profile.get("destination"))
    print(f"DEBUG: Parsed cities: {cities}")
    if not cities:
        print("DEBUG: No destination parsed")
        return JSONResponse(status_code=400, content={"type":"error","message":"No destination parsed."})

    total_days = trip_total_days(profile)
    print(f"DEBUG: Total days: {total_days}")
    if not total_days or total_days <= 0:
        print("DEBUG: Invalid date range")
        return JSONResponse(status_code=400, content={"type":"error","message":"Invalid date range."})

    split = normalize_city_split(cities, total_days, body.city_day_split)
    if not split or (len(cities) > 1 and body.city_day_split is None):
        example_split = [{"city": c, "days": max(1, total_days // len(cities))} for c in cities]
        example_payload = {"session_id": body.session_id, "city_day_split": example_split}
        return JSONResponse({"type":"ask_split","session_id": body.session_id,
                             "assistant_message": "Multi-city detected. Tell me days per city (send back to /plan with city_day_split).",
                             "example": example_payload})

    # itinerary prompt
    def build_plan_messages(profile: Dict, split: List[Dict[str,int]], notes: str) -> List[Dict[str,str]]:
        cities_line = ", ".join([f'{d["city"]} ({d["days"]}d)' for d in split])
        constraints = []
        for k in ["diet","pace","accommodation_level","interests","transport_preference","travelers","budget_in_inr","departure_location"]:
            v = profile.get(k)
            if v is None: continue
            if k == "budget_in_inr" and isinstance(v,(int,float)):
                constraints.append(f"Budget: ₹{int(v):,}")
            else:
                constraints.append(f"{k.replace('_',' ').title()}: {v}")
        constraint_line = " | ".join(constraints) if constraints else "—"

        system = {"role":"system","content": ITINERARY_SYSTEM_PROMPT}
        user = {"role":"user","content":
                f"Create a DETAILED day-by-day itinerary for this trip:\n\n"
                f"Trip Dates: {profile.get('start_date')} to {profile.get('end_date')}\n"
                f"Cities & Days: {cities_line}\n"
                f"Traveler Details: {constraint_line}\n"
                f"Extra Notes: {notes or 'None'}\n\n"
                f"CRITICAL FORMAT REQUIREMENTS:\n"
                f"1. Use this EXACT structure for each day:\n\n"
                f"**Day [NUMBER]: [Day Title]**\n\n"
                f"**Morning ([EXACT TIME] - [EXACT TIME]):** **[Location Name]**\n"
                f"• What to do: [Step-by-step detailed instructions]\n"
                f"• How to get there: [Exact transport method, route, duration, cost]\n"
                f"• What to expect: [What they'll see/experience]\n"
                f"• Time needed: [Duration]\n"
                f"• Pro tip: [Helpful hint]\n"
                f"• Cost: [Budget range if applicable]\n\n"
                f"**Afternoon ([EXACT TIME] - [EXACT TIME]):** **[Location Name]**\n"
                f"[Same detailed format...]\n\n"
                f"**Evening ([EXACT TIME] - [EXACT TIME]):** **[Location Name]**\n"
                f"[Same detailed format...]\n\n"
                f"2. EVERY activity MUST have:\n"
                f"   - Exact time slots (e.g., '9:00 AM - 11:30 AM', '2:00 PM - 5:00 PM')\n"
                f"   - Location name in **bold**\n"
                f"   - How to get there (specific transport, route, duration, cost)\n"
                f"   - What to do (step-by-step, very clear)\n"
                f"   - What to expect (so they know what they're getting into)\n"
                f"   - Time needed (realistic duration)\n"
                f"   - Cost/budget info (if relevant)\n"
                f"   - Practical tips (what to wear, bring, best times to visit)\n\n"
                f"3. Transport instructions must be CRYSTAL CLEAR:\n"
                f"   - Exact method (metro line, bus number, taxi, walk)\n"
                f"   - Specific route/directions\n"
                f"   - Duration\n"
                f"   - Cost (if applicable)\n"
                f"   - Landmarks to look for\n\n"
                f"4. Be EXTREMELY detailed - explain like teaching a 5-year-old:\n"
                f"   - 'Take the Blue Metro Line from Station X'\n"
                f"   - 'Get off at Station Y (it's the 5th stop)'\n"
                f"   - 'Walk 200m straight, you'll see a red building'\n"
                f"   - 'The entrance is on the left side'\n\n"
                f"Make it so detailed they can follow it without asking questions. Include ALL timings, transport details, and practical information. Be thorough, clear, and helpful."}
        # Always prepend persona too
        return [{"role":"system","content": BASE_SYSTEM_AURA}, system, user]

    total = sum(s["days"] for s in split)
    chunk_size = 10
    if total <= chunk_size:
        msgs = build_plan_messages(profile, split, body.extra_notes or "")
        itinerary = await chat_async(msgs, temperature=0.35, max_tokens=3000, timeout_sec=120)
    else:
        parts, start = [], 1
        while start <= total:
            end = min(total, start + chunk_size - 1)
            sub = slice_split_for_window(split, start, end)
            msgs = build_plan_messages(profile, sub, (body.extra_notes or "") + f"\n(Generate only days {start}-{end} of the trip)")
            part_result = await chat_async(msgs, temperature=0.3, max_tokens=2200, timeout_sec=120)
            parts.append(f"DAY {start}-{end}\n" + part_result)
            start = end + 1
        itinerary = "\n\n".join(parts)

    # Structure the itinerary data
    print("Structuring itinerary data...")
    trip_object = structure_itinerary_data(profile, itinerary)
    
    if trip_object:
        trip_object["user_id"] = user_id
        trip_object["session_id"] = body.session_id
        
        # Ensure essential fields are present from profile if missing in structured data
        if not trip_object.get("destination"):
            trip_object["destination"] = profile.get("destination")
        if not trip_object.get("start_date"):
            trip_object["start_date"] = profile.get("start_date")
        if not trip_object.get("end_date"):
            trip_object["end_date"] = profile.get("end_date")
        if not trip_object.get("travelers"):
            trip_object["travelers"] = profile.get("travelers", 1)
        if not trip_object.get("budget_in_inr"):
            trip_object["budget_in_inr"] = profile.get("budget_in_inr")
        
        # Geocode locations
        print("Geocoding locations...")

        # --- Sanitization: ensure we don't store vehicle model specifics (e.g., 'SUV')
        # If the structured data or the generated text included specific vehicle types,
        # prefer the user's profile value or the generic label.
        def sanitize_transport(trip_obj, profile):
            import re
            vehicle_terms = re.compile(r"\b(suv|sedan|hatchback|jeep|innova|scorpio|fortuner|4x4|jeep)\b", re.I)

            # Normalize top-level transport_preference
            tp = trip_obj.get("transport_preference")
            profile_tp = profile.get("transport_preference")
            if isinstance(tp, str) and vehicle_terms.search(tp):
                # prefer profile value if available, otherwise fall back to generic label
                trip_obj["transport_preference"] = profile_tp or "Rental car/self-drive"

            # Also sanitize any textual fields in days/activities to remove vehicle model mentions
            for day in trip_obj.get("days", []):
                for act in day.get("activities", []):
                    for fld in ("description","title","how_to_get_there","location_name"):
                        if isinstance(act.get(fld), str) and vehicle_terms.search(act.get(fld)):
                            act[fld] = vehicle_terms.sub(lambda m: (profile_tp or "rental car"), act[fld])

        sanitize_transport(trip_object, profile)
        
        def enrich_locations(loc_list):
            if not loc_list: return
            for loc in loc_list:
                if not loc.get("lat") or not loc.get("lng"):
                    query = loc.get("geocode_query") or loc.get("name")
                    if query:
                        geo = geocode_location(query)
                        if geo:
                            loc["lat"] = geo["lat"]
                            loc["lng"] = geo["lng"]
                            print(f"Geocoded {query}: {geo['lat']}, {geo['lng']}")

        enrich_locations(trip_object.get("locations", []))
        
        # Also try to geocode activities if they have location_name
        for day in trip_object.get("days", []):
            for act in day.get("activities", []):
                if act.get("location_name") and (not act.get("lat") or not act.get("lng")):
                    query = act.get("geocode_query") or act.get("location_name")
                    if query:
                        geo = geocode_location(query)
                        if geo:
                            act["lat"] = geo["lat"]
                            act["lng"] = geo["lng"]

        # Save to TRIPS collection
        save_trip(trip_object)
        
        # Prepare response with trip identifiers
        response_data = {
            "type": "itinerary",
            "session_id": body.session_id,
            "cities": [s["city"] for s in split],
            "itinerary": itinerary,
            "start_date": profile.get("start_date"),
            "end_date": profile.get("end_date"),
            "trip_id": trip_object.get("trip_id"),
            "_id": str(trip_object.get("_id")) if trip_object.get("_id") else None,
            "destination": trip_object.get("destination") or profile.get("destination"),
            "travelers": trip_object.get("travelers") or profile.get("travelers", 1),
            "budget_in_inr": trip_object.get("budget_in_inr") or profile.get("budget_in_inr")
        }
        
    else:
        print("ERROR: Failed to structure trip object. Falling back to legacy save.")
        save_itinerary(user_id, body.session_id, itinerary, [s["city"] for s in split], profile.get("start_date"), profile.get("end_date"))
        
        response_data = {
            "type": "itinerary",
            "session_id": body.session_id,
            "cities": [s["city"] for s in split],
            "itinerary": itinerary,
            "start_date": profile.get("start_date"),
            "end_date": profile.get("end_date")
        }

    
    return JSONResponse(response_data)

@app.get("/health")
def health():
    return {"ok": True}

# ——— Chat History Endpoint
@app.get("/chat/history")
def get_chat_history(authorization: Optional[str] = Header(None), session_id: Optional[str] = None):
    """Get chat history for a session"""
    user_id = get_uid_from_token(authorization)
    if not session_id:
        return JSONResponse(status_code=400, content={"type":"error","message":"session_id required"})
    
    # Get messages and format for frontend
    messages_raw = get_recent_messages(session_id, k=50)  # Get last 50 messages
    messages = [
        {
            "role": m.get("role", "user"),
            "content": m.get("content", ""),
            "ts": m.get("ts", "")
        }
        for m in messages_raw
    ]
    return JSONResponse({"messages": messages, "session_id": session_id})

# ——— Social Media Endpoints
@app.get("/social/posts")
def get_social_posts(authorization: Optional[str] = Header(None)):
    """Get user's social media posts"""
    user_id = get_uid_from_token(authorization)
    # TODO: Implement social posts storage in MongoDB
    # For now, return empty array
    return JSONResponse({"posts": []})

@app.post("/social/posts")
def create_social_post(authorization: Optional[str] = Header(None), body: Dict = Body(...)):
    """Create a new social media post"""
    user_id = get_uid_from_token(authorization)
    # TODO: Store post in MongoDB
    return JSONResponse({"success": True, "post_id": "temp_id"})

# ——— Journal Endpoints
@app.get("/journal/entries")
def get_journal_entries(authorization: Optional[str] = Header(None)):
    """Get user's travel journal entries"""
    user_id = get_uid_from_token(authorization)
    # TODO: Implement journal storage in MongoDB
    # For now, return empty array
    return JSONResponse({"entries": []})

@app.post("/journal/entries")
def create_journal_entry(authorization: Optional[str] = Header(None), body: Dict = Body(...)):
    """Create a new journal entry"""
    user_id = get_uid_from_token(authorization)
    # TODO: Store journal entry in MongoDB
    return JSONResponse({"success": True, "entry_id": "temp_id"})

# ——— Itinerary Endpoint
@app.get("/itinerary")
def get_user_itinerary(authorization: Optional[str] = Header(None), session_id: Optional[str] = None):
    """Get stored itinerary for user"""
    user_id = get_uid_from_token(authorization)
    itinerary_doc = get_itinerary(user_id, session_id)
    
    if not itinerary_doc:
        return JSONResponse(status_code=404, content={"type":"error","message":"No itinerary found"})
    
    return JSONResponse({
        "itinerary": itinerary_doc.get("itinerary", ""),
        "cities": itinerary_doc.get("cities", []),
        "start_date": itinerary_doc.get("start_date"),
        "end_date": itinerary_doc.get("end_date"),
        "session_id": itinerary_doc.get("session_id")
    })

@app.get("/locations")
def get_trip_map_locations(authorization: Optional[str] = Header(None), session_id: Optional[str] = None):
    """Get extracted locations for the map"""
    user_id = get_uid_from_token(authorization)
    locations = get_locations(user_id, session_id)
    return JSONResponse({"locations": locations})


@app.post("/new_trip")
def new_trip(authorization: Optional[str] = Header(None), body: NewTripRequest = Body(default=NewTripRequest())):
    """Reset trip specific fields so that a returning user can plan a fresh journey."""
    user_id = get_uid_from_token(authorization)

    fields_to_reset = list(TRIP_FIELDS)
    if body.reset_preferences:
        fields_to_reset = list(dict.fromkeys(TRIP_FIELDS + PREFERENCE_FIELDS))

    reset_trip_fields(user_id, fields_to_reset)
    return JSONResponse({
        "ok": True,
        "reset_fields": fields_to_reset
    })


@app.post("/rag_query")
def rag_query(authorization: Optional[str] = Header(None), body: RagRequest = Body(...)):
    """Run a knowledge-based RAG query against the data/ knowledge base.

    Returns: {answer, sources, chunks_used}
    """
    if rag_generate_answer is None:
        return JSONResponse(status_code=501, content={"error": "RAG helper not available - ensure src.rag exists"})

    # validate auth and then run RAG
    user_id = get_uid_from_token(authorization)
    try:
        mode = (body.mode or "answer").lower()
        if mode == 'retrieve':
            # return raw retrieval results
            res = rag_generate_answer.__module__
            # call retrieve if available
            try:
                from src.rag import retrieve
                raw = retrieve(body.question, top_k=body.top_k)
                return JSONResponse({"mode": "retrieve", "results": raw})
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": f"retrieve failed: {e}"})

        elif mode in ('single', 'one', 'single_call'):
            try:
                from src.rag import generate_answer_single_call
                res = generate_answer_single_call(body.question, top_k=body.top_k)
                return JSONResponse(res)
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": f"single_call failed: {e}"})

        else:
            # default / backward-compatible: existing summarize flow
            res = rag_generate_answer(body.question, top_k=body.top_k)
            return JSONResponse(res)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ——— Chat History Endpoints ———

@app.get("/chats")
def get_chats(authorization: Optional[str] = Header(None)):
    """Get all chats for the authenticated user"""
    user_id = get_uid_from_token(authorization)
    chats = get_user_chats(user_id)
    return JSONResponse(chats)


@app.get("/dashboard/stats")
def get_dashboard_stats(authorization: Optional[str] = Header(None)):
    """Get dashboard statistics for the authenticated user"""
    from datetime import datetime
    
    user_id = get_uid_from_token(authorization)
    
    # Get all sessions with trip data
    if sessions_col is None:
        return JSONResponse({"total_trips": 0, "total_days": 0, "upcoming": 0})
    
    sessions = list(sessions_col.find({"user_id": user_id}))
    
    total_trips = len(sessions)
    total_days = 0
    upcoming = 0
    today = datetime.now().date()
    
    for session in sessions:
        # Calculate total days from start_date and end_date
        start_date_str = session.get("start_date")
        end_date_str = session.get("end_date")
        
        if start_date_str and end_date_str:
            try:
                # Parse dates (assuming YYYY-MM-DD or DD/MM/YYYY format)
                if "/" in start_date_str:
                    start_date = datetime.strptime(start_date_str, "%d/%m/%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d/%m/%Y").date()
                else:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                
                # Calculate trip duration
                days = (end_date - start_date).days + 1  # +1 to include both start and end day
                total_days += days
                
                # Check if upcoming trip
                if start_date > today:
                    upcoming += 1
            except (ValueError, TypeError):
                # Skip if date parsing fails
                pass
    
    return JSONResponse({
        "total_trips": total_trips,
        "total_days": total_days,
        "upcoming": upcoming
    })


@app.get("/chat/{session_id}")
def get_chat(session_id: str, authorization: Optional[str] = Header(None)):
    """Get specific chat by session ID"""
    user_id = get_uid_from_token(authorization)
    
    # Get session messages
    messages = get_recent_messages(session_id, k=100)
    
    return JSONResponse({
        "session_id": session_id,
        "messages": messages
    })


@app.delete("/chat/{session_id}")
def delete_chat(session_id: str, authorization: Optional[str] = Header(None)):
    """Delete a chat session and all its messages"""
    try:
        user_id = get_uid_from_token(authorization)
        
        # Get collections from db
        chats_col = db["chats"] if db is not None else None
        messages_col = db["messages"] if db is not None else None
        itineraries_col = db["itineraries"] if db is not None else None
        
        # Delete chat from chats collection
        chat_id = f"{user_id}_{session_id}"
        print(f"Attempting to delete chat: {chat_id}, session: {session_id}, user: {user_id}")
        
        deleted_count = 0
        
        if chats_col is not None:
            result = chats_col.delete_one({"_id": chat_id, "user_id": user_id})
            deleted_count += result.deleted_count
            print(f"Deleted {result.deleted_count} from chats_col")
        
        # Delete all messages for this session
        if messages_col is not None:
            result = messages_col.delete_many({"session_id": session_id, "user_id": user_id})
            deleted_count += result.deleted_count
            print(f"Deleted {result.deleted_count} messages")
        
        # Delete session data
        if sessions_col is not None:
            result = sessions_col.delete_one({"session_id": session_id, "user_id": user_id})
            deleted_count += result.deleted_count
            print(f"Deleted {result.deleted_count} sessions")
        
        # Delete itinerary if exists
        if itineraries_col is not None:
            result = itineraries_col.delete_one({"session_id": session_id, "user_id": user_id})
            deleted_count += result.deleted_count
            print(f"Deleted {result.deleted_count} itineraries")
        
        print(f"Total items deleted: {deleted_count}")
        return JSONResponse({"success": True, "message": "Chat deleted successfully", "deleted_count": deleted_count})
    except Exception as e:
        print(f"Error deleting chat: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


class ChatTitleRequest(BaseModel):
    session_id: str
    first_message: str


@app.post("/chat/title")
async def generate_chat_title(authorization: Optional[str] = Header(None), body: ChatTitleRequest = Body(...)):
    """Generate AI title for a chat based on first message"""
    user_id = get_uid_from_token(authorization)
    
    try:
        # Generate title using AI with improved prompt
        title_prompt = f"""Based on this travel query: "{body.first_message}"

Generate a short, descriptive chat title (4-6 words max) that captures the destination or trip essence.

Examples:
- "I want to visit Paris" → "Paris Trip Planning"
- "Plan a beach vacation in Bali" → "Bali Beach Vacation"
- "Family trip to Tokyo and Kyoto" → "Tokyo & Kyoto Family Trip"
- "Adventure travel in Switzerland" → "Switzerland Adventure"

Return ONLY the title, no quotes or extra text."""
        
        title_response = await chat_async(
            [
                {"role": "system", "content": "You are a travel title generator. Create concise, engaging titles that highlight the destination and trip type."},
                {"role": "user", "content": title_prompt}
            ],
            timeout_sec=10
        )
        
        title = title_response.strip().strip('"').strip("'")
        if len(title) > 50:
            title = title[:47] + "..."
        
        # Save to database
        save_chat(user_id, body.session_id, title)
        update_chat_title(user_id, body.session_id, title)
        
        return JSONResponse({"title": title})
    except Exception as e:
        print(f"Error generating title: {e}")
        # Improved fallback - try to extract key words from first message
        fallback_title = "New Travel Chat"
        if body.first_message:
            words = body.first_message.split()[:4]
            if len(words) > 0:
                fallback_title = " ".join(words).capitalize()
                if len(fallback_title) > 30:
                    fallback_title = fallback_title[:27] + "..."
        
        save_chat(user_id, body.session_id, fallback_title)
        return JSONResponse({"title": fallback_title})


class ChatTitleUpdateRequest(BaseModel):
    session_id: str
    title: str


@app.post("/chat/update-title")
async def update_chat_title_endpoint(authorization: Optional[str] = Header(None), body: ChatTitleUpdateRequest = Body(...)):
    """Update chat title (used after plan is generated)"""
    user_id = get_uid_from_token(authorization)
    
    try:
        update_chat_title(user_id, body.session_id, body.title)
        return JSONResponse({"status": "success", "title": body.title})
    except Exception as e:
        print(f"Error updating chat title: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})