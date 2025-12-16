import os
import re
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "WanderMindAI")

client = MongoClient(MONGODB_URI)
db = client[MONGO_DBNAME]
sessions_col = db["sessions"]
users_col = db["users"]
itineraries_col = db["itineraries"]

def iso():
    return datetime.utcnow().isoformat() + "Z"

def save_itinerary_direct(user_id: str, session_id: str, itinerary_text: str, cities: list, start_date: str, end_date: str):
    """Save generated itinerary to database"""
    print(f"DEBUG: Saving itinerary for user {user_id}, session {session_id}")
    
    try:
        result = itineraries_col.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$set": {
                    "itinerary": itinerary_text,
                    "cities": cities,
                    "start_date": start_date,
                    "end_date": end_date,
                    "updated_at": iso()
                },
                "$setOnInsert": {
                    "id": f"{user_id}{session_id}",
                    "user_id": user_id,
                    "session_id": session_id,
                    "created_at": iso()
                }
            },
            upsert=True
        )
        print(f"DEBUG: Itinerary saved. Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}")
    except Exception as e:
        print(f"ERROR: Failed to save itinerary: {e}")

def save_locations_direct(user_id: str, session_id: str, locations: list):
    """Save extracted locations for map visualization"""
    print(f"DEBUG: Saving {len(locations)} locations for user {user_id}, session {session_id}")
    
    try:
        result = itineraries_col.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$set": {
                    "locations": locations,
                    "updated_at": iso()
                }
            },
            upsert=True
        )
        print(f"DEBUG: Locations saved. Matched: {result.matched_count}, Modified: {result.modified_count}")
    except Exception as e:
        print(f"ERROR: Failed to save locations: {e}")

def is_itinerary_message(content: str) -> bool:
    """Check if a message looks like an itinerary"""
    patterns = [
        r"Day \d+:",
        r"\*\*Day \d+\*\*",
        r"Morning \(",
        r"Afternoon \(",
        r"Evening \(",
        r"Transport:",
        r"How to get there:",
    ]
    return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)

def extract_dates_from_profile(user_id: str):
    """Get start and end dates from user profile"""
    user_doc = users_col.find_one({"user_id": user_id})
    if user_doc and "profile" in user_doc:
        profile = user_doc["profile"]
        return profile.get("start_date"), profile.get("end_date"), profile.get("destination")
    return None, None, None

def sync_all_itineraries():
    """Find all sessions with itineraries and sync them"""
    print("Starting itinerary sync...")
    
    # Find all sessions
    sessions = sessions_col.find({})
    synced_count = 0
    
    for session in sessions:
        user_id = session.get("user_id")
        session_id = session.get("_id")  # Use _id as session_id
        messages = session.get("messages", [])
        
        if not user_id or not session_id:
            print(f"Skipping session - missing user_id or session_id")
            continue
        
        # Find assistant messages that look like itineraries
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if is_itinerary_message(content) and len(content) > 500:  # Substantial itinerary
                    print(f"\nFound itinerary in session {session_id} for user {user_id}")
                    print(f"  Itinerary length: {len(content)} characters")
                    
                    # Get dates and destination from profile
                    start_date, end_date, destination = extract_dates_from_profile(user_id)
                    
                    # Extract cities from the itinerary text if destination not in profile
                    cities = []
                    if destination:
                        cities = [destination]
                    else:
                        # Try to extract from itinerary text
                        city_match = re.search(r"Trip to (.+?)[\n:]", content, re.IGNORECASE)
                        if city_match:
                            cities = [city_match.group(1).strip()]
                    
                    if not cities:
                        cities = ["Unknown"]
                    
                    # Save to itineraries collection
                    try:
                        save_itinerary_direct(
                            user_id=user_id,
                            session_id=session_id,
                            itinerary_text=content,
                            cities=cities,
                            start_date=start_date,
                            end_date=end_date
                        )
                        print(f"✓ Saved itinerary for session {session_id}")
                        
                        # Extract and save locations
                        try:
                            # Simple location extraction from bold text
                            locations = []
                            bold_pattern = r"\*\*([^*]+)\*\*"
                            matches = re.findall(bold_pattern, content)
                            
                            exclude_terms = [
                                "morning", "afternoon", "evening", "lunch", "dinner", 
                                "day", "night", "breakfast", "arrival", "departure",
                                "check-in", "check-out", "optional", "note", "tip",
                                "pro tip", "cost", "time needed", "how to get there",
                                "what to do", "what to expect", "transport"
                            ]
                            
                            seen = set()
                            for m in matches:
                                clean = m.strip()
                                if clean.lower() not in exclude_terms and len(clean) > 2 and clean.lower() not in seen:
                                    seen.add(clean.lower())
                                    locations.append({"name": clean})
                            
                            if locations:
                                save_locations_direct(user_id, session_id, locations[:15])  # Limit to 15
                                print(f"✓ Saved {len(locations[:15])} locations for map")
                        except Exception as e:
                            print(f"✗ Error extracting locations: {e}")
                        
                        synced_count += 1
                        break  # Only sync the first itinerary per session
                    except Exception as e:
                        print(f"✗ Error saving itinerary: {e}")
    
    print(f"\n{'='*60}")
    print(f"Sync complete! Synced {synced_count} itineraries.")
    print(f"{'='*60}")

if __name__ == "__main__":
    sync_all_itineraries()
