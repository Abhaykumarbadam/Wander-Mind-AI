# db/mongo.py
import os
from datetime import datetime
from typing import Dict, List, Optional

from pymongo import MongoClient

# ---- ENV ----
MONGODB_URI  = os.getenv("MONGODB_URI", "")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "wander_ai")

# ---- CLIENT / DB / COLLECTIONS (no truthiness on PyMongo objects) ----
client = MongoClient(MONGODB_URI) if MONGODB_URI else None
db = client[MONGO_DBNAME] if client is not None else None
users_col = db["users"] if db is not None else None
sessions_col = db["sessions"] if db is not None else None

# ---- REQUIRED SLOTS (trip planning only - display_name is optional UX field, NOT required) ----
REQUIRED_SLOTS = [
    "destination", "start_date", "end_date", "budget_in_inr", "travelers",
    "pace", "interests", "diet", "transport_preference", "accommodation_level",
    "departure_location"
]

TRIP_FIELDS = [
    "destination",
    "start_date",
    "end_date",
    "budget_in_inr",
    "travelers",
    "departure_location",
]

PREFERENCE_FIELDS = [
    "pace",
    "interests",
    "diet",
    "transport_preference",
    "accommodation_level",
]

SESSION_METADATA_DEFAULTS = {
    "preferences_prompted": False,
    "preferences_confirmed": False,
    "profile_snapshot": None,
    "confirmed_preferences": [],
    "last_prompted_at": None,
}

def iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

# ============ PROFILES ============

def get_or_create_profile(user_id: str) -> Dict:
    if users_col is None:
        return {"_id": user_id, "profile": {k: None for k in REQUIRED_SLOTS}}

    doc = users_col.find_one({"_id": user_id})
    if doc:
        return doc

    new_doc = {
        "_id": user_id,
        "profile": {k: None for k in REQUIRED_SLOTS},
        "created_at": iso()
    }
    users_col.insert_one(new_doc)
    return new_doc


def save_profile(user_id: str, profile: Dict):
    if users_col is None:
        return
    users_col.update_one(
        {"_id": user_id},
        {"$set": {"profile": profile, "updated_at": iso()}},
        upsert=True
    )

# ============ SESSIONS ============

def get_or_create_session(session_id: Optional[str], user_id: str) -> str:
    if sessions_col is None:
        import uuid
        return session_id or str(uuid.uuid4())

    if session_id:
        doc = sessions_col.find_one({"_id": session_id})
        if doc:
            return session_id

    import uuid
    sid = str(uuid.uuid4())
    sessions_col.insert_one({
        "_id": sid,
        "user_id": user_id,
        "messages": [],
        "mode": "collecting",
        "metadata": SESSION_METADATA_DEFAULTS.copy(),
        "created_at": iso()
    })
    return sid


def append_message(session_id: str, role: str, content: str):
    if sessions_col is None:
        return
    sessions_col.update_one(
        {"_id": session_id},
        {"$push": {"messages": {"role": role, "content": content, "ts": iso()}}},
        upsert=True
    )


def get_last_user_messages(session_id: str, k: int = 5) -> List[str]:
    if sessions_col is None:
        return []
    doc = sessions_col.find_one({"_id": session_id}, {"messages": 1}) or {"messages": []}
    msgs = doc.get("messages") or []
    return [m.get("content") for m in msgs if m.get("role") == "user"][-k:]


def get_recent_messages(session_id: str, k: int = 8) -> List[Dict]:
    if sessions_col is None:
        return []
    doc = sessions_col.find_one({"_id": session_id}, {"messages": 1}) or {"messages": []}
    return (doc.get("messages") or [])[-k:]


def get_session_mode(session_id: str) -> Optional[str]:
    if sessions_col is None:
        return None
    doc = sessions_col.find_one({"_id": session_id}, {"mode": 1})
    return (doc or {}).get("mode")


def set_session_mode(session_id: str, mode: str):
    if sessions_col is None:
        return
    sessions_col.update_one(
        {"_id": session_id},
        {"$set": {"mode": mode, "updated_at": iso()}},
        upsert=True
    )

# ============ ITINERARIES ============

itineraries_col = db["itineraries"] if db is not None else None

def save_itinerary(user_id: str, session_id: str, itinerary_text: str, cities: List[str], start_date: Optional[str], end_date: Optional[str]):
    """Save generated itinerary to database"""
    if itineraries_col is None:
        return
    itineraries_col.update_one(
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

def get_itinerary(user_id: str, session_id: Optional[str] = None) -> Optional[Dict]:
    """Get latest itinerary for user (optionally filtered by session)"""
    if itineraries_col is None:
        return None
    query = {"user_id": user_id}
    if session_id:
        query["session_id"] = session_id
    doc = itineraries_col.find_one(query, sort=[("updated_at", -1)])
    return doc


# ============ PROFILE UTILITIES ============

def reset_trip_fields(user_id: str, fields: Optional[List[str]] = None):
    """Clear trip-specific fields while keeping long-term preferences."""
    if users_col is None:
        return

    reset_fields = fields or TRIP_FIELDS
    updates = {f"profile.{field}": None for field in reset_fields}

    if not updates:
        return

    users_col.update_one(
        {"_id": user_id},
        {
            "$set": {**updates, "updated_at": iso()}
        },
        upsert=True
    )


def get_session_metadata(session_id: str) -> Dict:
    if sessions_col is None:
        return SESSION_METADATA_DEFAULTS.copy()
    doc = sessions_col.find_one({"_id": session_id}, {"metadata": 1})
    metadata = (doc or {}).get("metadata") or {}
    merged = SESSION_METADATA_DEFAULTS.copy()
    merged.update({k: v for k, v in metadata.items() if v is not None})
    return merged


def update_session_metadata(session_id: str, updates: Dict):
    if sessions_col is None or not updates:
        return
    metadata_updates = {f"metadata.{k}": v for k, v in updates.items()}
    sessions_col.update_one(
        {"_id": session_id},
        {
            "$set": {
                **metadata_updates,
                "updated_at": iso()
            }
        }
    )


def clear_session_state(session_id: str):
    """Reset session metadata flags (used when starting fresh confirmation loop)."""
    if sessions_col is None:
        return
    sessions_col.update_one(
        {"_id": session_id},
        {
            "$set": {
                "metadata": SESSION_METADATA_DEFAULTS.copy(),
                "updated_at": iso()
            }
        }
    )