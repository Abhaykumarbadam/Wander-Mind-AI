"""
Trip tracking + map visualization
Manages user trips with status (completed, ongoing, upcoming) and coordinates
"""

import os
import json
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pymongo import MongoClient
import firebase_admin.auth
from dotenv import load_dotenv

# Utility imports
from utils.geocoding import geocode_location, batch_geocode
from utils.timezone_service import get_timezone_by_location
from utils.location_extractor import get_trip_data

# DB helpers
from db.mongo import save_itinerary, save_locations

load_dotenv()

router = APIRouter(prefix="/trips", tags=["trips"])

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "WanderMindAI")

client = MongoClient(MONGODB_URI)
db = client[MONGO_DBNAME]

trips_col = db["trips"]
itineraries_col = db["itineraries"]


# ------------------------- MODELS -------------------------

class TripCreate(BaseModel):
    location: str
    start_date: str  # "YYYY-MM-DD"
    end_date: str
    status: Optional[Literal["upcoming", "ongoing", "completed"]] = None
    notes: Optional[str] = None
    accommodation: Optional[str] = None

    # Optional sync with Itinerary collection
    session_id: Optional[str] = None
    itinerary_text: Optional[str] = None


class TripUpdate(BaseModel):
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[Literal["upcoming", "ongoing", "completed"]] = None
    notes: Optional[str] = None
    accommodation: Optional[str] = None


class ItinerarySaveRequest(BaseModel):
    session_id: str
    itinerary_text: str
    cities: List[str]
    start_date: str
    end_date: str
    location: Optional[str] = None
    notes: Optional[str] = None
    accommodation: Optional[str] = None
    # New fields for structured data
    days: Optional[List[Dict]] = None
    inner_locations: Optional[List[Dict]] = None
    budget_inr: Optional[int] = None
    duration: Optional[int] = None


# ------------------------- AUTH -------------------------

async def verify_firebase_user(authorization: str = Header(None)):
    """Verify Firebase ID token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split("Bearer ")[1]
    try:
        decoded = firebase_admin.auth.verify_id_token(token)
        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# ------------------------- HELPERS -------------------------

def auto_status(start_date: str, end_date: str) -> str:
    """Determine trip status automatically based on dates."""
    try:
        today = datetime.now().date()
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()

        if today < start:
            return "upcoming"
        elif start <= today <= end:
            return "ongoing"
        return "completed"
    except:
        return "upcoming"


# ------------------------- ROUTES -------------------------

@router.post("/create")
async def create_trip(
    trip: TripCreate,
    user: dict = Depends(verify_firebase_user)
):
    """Create a new trip with geocoding & optional itinerary sync."""
    try:
        user_id = user["uid"]

        # Geocode
        geo = geocode_location(trip.location)
        if not geo:
            # Fallback if geocoding fails
            geo = {"lat": 0, "lng": 0, "formatted_address": trip.location}

        # Timezone
        tz = get_timezone_by_location(geo["lat"], geo["lng"])

        # Determine status automatically if missing
        status = trip.status or auto_status(trip.start_date, trip.end_date)

        # Build doc
        now = datetime.utcnow().isoformat()
        trip_doc = {
            "user_id": user_id,
            "location": trip.location,
            "formatted_address": geo.get("formatted_address"),
            "coordinates": {"lat": geo["lat"], "lng": geo["lng"]},
            "country": geo.get("country"),
            "country_code": geo.get("country_code"),
            "city": geo.get("city"),
            "timezone": tz["timezone"] if tz else geo.get("timezone"),

            "start_date": trip.start_date,
            "end_date": trip.end_date,
            "status": status,
            "notes": trip.notes,
            "accommodation": trip.accommodation,

            "created_at": now,
            "updated_at": now,
        }

        result = trips_col.insert_one(trip_doc)
        trip_doc["_id"] = str(result.inserted_id)

        # Sync itinerary if provided
        if trip.session_id and trip.itinerary_text:
            # Parse itinerary for structured data
            parsed_data = get_trip_data(trip.itinerary_text)
            structured = parsed_data.get("structured_itinerary") or {}
            
            save_itinerary(
                user_id=user_id,
                session_id=trip.session_id,
                itinerary_text=trip.itinerary_text,
                cities=[trip.location],
                start_date=trip.start_date,
                end_date=trip.end_date,
                days=structured.get("days"),
                inner_locations=parsed_data.get("geocoded_locations"),
                budget_inr=structured.get("budget_inr"),
                duration=structured.get("duration")
            )

        return {"status": "success", "message": "Trip created", "trip": trip_doc}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error creating trip: {str(e)}")


@router.post("/itinerary/save")
async def save_user_itinerary(
    data: ItinerarySaveRequest,
    user: dict = Depends(verify_firebase_user)
):
    """Save raw itinerary from LLM to DB."""
    try:
        user_id = user["uid"]
        
        # If structured data is missing, try to parse it from text
        days = data.days
        inner_locations = data.inner_locations
        budget = data.budget_inr
        duration = data.duration
        
        if not days or not inner_locations:
            parsed = get_trip_data(data.itinerary_text)
            structured = parsed.get("structured_itinerary") or {}
            
            if not days:
                days = structured.get("days")
            if not inner_locations:
                # Use geocoded locations from parser
                inner_locations = parsed.get("geocoded_locations")
            if not budget:
                budget = structured.get("budget_inr")
            if not duration:
                duration = structured.get("duration")

        save_itinerary(
            user_id=user_id,
            session_id=data.session_id,
            itinerary_text=data.itinerary_text,
            cities=data.cities,
            start_date=data.start_date,
            end_date=data.end_date,
            location=data.location,
            notes=data.notes,
            accommodation=data.accommodation,
            days=days,
            inner_locations=inner_locations,
            budget_inr=budget,
            duration=duration
        )
        
        return {"status": "success", "message": "Itinerary saved"}
    except Exception as e:
        raise HTTPException(500, f"Error saving itinerary: {str(e)}")


@router.post("/sync-itinerary-to-trip")
async def sync_itinerary_to_trip(
    session_id: str,
    itinerary_data: Optional[ItinerarySaveRequest] = None,
    user: dict = Depends(verify_firebase_user)
):
    """
    Sync an itinerary to the trips collection (idempotent).
    Creates a new trip or updates existing trip with the same session_id.
    """
    try:
        user_id = user["uid"]
        
        # 1. Try to fetch itinerary from DB
        itinerary = itineraries_col.find_one({"session_id": session_id, "user_id": user_id})
        
        # 2. If not found, check if we have data to save it
        if not itinerary:
            if itinerary_data:
                # Call the save endpoint logic directly
                await save_user_itinerary(itinerary_data, user)
                # Fetch again
                itinerary = itineraries_col.find_one({"session_id": session_id, "user_id": user_id})
            
            if not itinerary:
                raise HTTPException(404, f"Itinerary not found for session: {session_id}")
        
        # Extract trip data from itinerary
        cities = itinerary.get("cities", [])
        location = itinerary.get("location") or (cities[0] if cities else "Unknown Destination")
        start_date = itinerary.get("start_date")
        end_date = itinerary.get("end_date")
        
        if not start_date or not end_date:
            raise HTTPException(400, "Itinerary missing start_date or end_date")
        
        # Check if trip already exists for this session_id (idempotent)
        existing_trip = trips_col.find_one({"session_id": session_id, "user_id": user_id})
        
        # Prepare trip document fields
        # Prepare trip document fields
        trip_fields = {
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if location: trip_fields["destination"] = location
        if location: trip_fields["location"] = location
        if start_date: trip_fields["start_date"] = start_date
        if end_date: trip_fields["end_date"] = end_date
        
        trip_fields["status"] = auto_status(start_date, end_date)
        
        # Extract travelers from itinerary or default to 1
        if itinerary.get("travelers"):
            trip_fields["travelers"] = itinerary["travelers"]
        else:
            trip_fields["travelers"] = 1
        
        # Only update these if they exist in the itinerary source
        if itinerary.get("itinerary"): trip_fields["notes"] = itinerary["itinerary"]
        if itinerary.get("accommodation"): trip_fields["accommodation"] = itinerary["accommodation"]
        if itinerary.get("budget_inr"): trip_fields["budget_in_inr"] = itinerary["budget_inr"]
        if itinerary.get("budget_in_inr"): trip_fields["budget_in_inr"] = itinerary["budget_in_inr"]
        
        # Don't overwrite with empty lists
        if itinerary.get("inner_locations"): trip_fields["inner_locations"] = itinerary["inner_locations"]
        if itinerary.get("inner_locations"): trip_fields["locations"] = itinerary["inner_locations"]
        if itinerary.get("days"): trip_fields["days"] = itinerary["days"]

        if existing_trip:
            # Update existing trip
            trips_col.update_one(
                {"_id": existing_trip["_id"]},
                {"$set": trip_fields}
            )
            trip_id = str(existing_trip["_id"])
            message = "Trip updated from itinerary"
        else:
            # Create new trip
            # Geocode the location
            geo = geocode_location(location)
            if not geo:
                geo = {"lat": 0, "lng": 0, "formatted_address": location}
            
            tz = get_timezone_by_location(geo.get("lat", 0), geo.get("lng", 0))
            
            trip_doc = {
                "user_id": user_id,
                "session_id": session_id,
                "formatted_address": geo.get("formatted_address", location),
                "coordinates": {"lat": geo.get("lat", 0), "lng": geo.get("lng", 0)},
                "country": geo.get("country"),
                "city": geo.get("city"),
                "timezone": tz.get("timezone") if tz else None,
                "created_at": datetime.utcnow().isoformat(),
                **trip_fields
            }
            
            result = trips_col.insert_one(trip_doc)
            trip_id = str(result.inserted_id)
            message = "Trip created from itinerary"
        
        # Fetch the final trip
        from bson import ObjectId
        final_trip = trips_col.find_one({"_id": ObjectId(trip_id)})
        final_trip["_id"] = str(final_trip["_id"])
        
        return {
            "status": "success",
            "message": message,
            "trip": final_trip
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error syncing itinerary to trip: {str(e)}")


@router.get("/itinerary")
async def get_user_itinerary(user: dict = Depends(verify_firebase_user)):
    """
    Get user's complete travel itinerary organized by timeline.
    Combines data from both trips and itineraries collections.
    """
    try:
        user_id = user["uid"]
        
        # Fetch trips
        trips = list(trips_col.find({"user_id": user_id}).sort("start_date", 1))
        
        # Process trips
        processed_trips = []
        for trip in trips:
            trip["_id"] = str(trip["_id"])
            
            # Ensure duration
            if "duration" not in trip and trip.get("start_date") and trip.get("end_date"):
                try:
                    start = datetime.fromisoformat(trip["start_date"])
                    end = datetime.fromisoformat(trip["end_date"])
                    trip["duration"] = (end - start).days + 1
                except:
                    trip["duration"] = 1
            
            # Ensure formatted dates
            if trip.get("start_date"):
                try:
                    s = datetime.fromisoformat(trip["start_date"])
                    trip["formatted_start"] = s.strftime("%B %d, %Y")
                    trip["formatted_start_short"] = s.strftime("%b %d")
                except: pass
                
            if trip.get("end_date"):
                try:
                    e = datetime.fromisoformat(trip["end_date"])
                    trip["formatted_end"] = e.strftime("%B %d, %Y")
                    trip["formatted_end_short"] = e.strftime("%b %d")
                except: pass
                
            # Ensure status
            if not trip.get("status"):
                trip["status"] = auto_status(trip.get("start_date"), trip.get("end_date"))
                
            # Ensure inner_locations and days exist
            if "inner_locations" not in trip:
                trip["inner_locations"] = []
            if "days" not in trip:
                trip["days"] = []
                
            # Use full_itinerary_text for notes if available
            if "notes" in trip and trip["notes"]:
                trip["full_itinerary_text"] = trip["notes"]
            
            processed_trips.append(trip)
        
        # Organize by status
        organized_trips = {
            "upcoming": [t for t in processed_trips if t.get("status") == "upcoming"],
            "ongoing": [t for t in processed_trips if t.get("status") == "ongoing"],
            "completed": [t for t in processed_trips if t.get("status") == "completed"]
        }
        
        counts = {
            "upcoming": len(organized_trips["upcoming"]),
            "ongoing": len(organized_trips["ongoing"]),
            "completed": len(organized_trips["completed"]),
            "total": len(processed_trips)
        }
        
        return {
            "status": "success",
            "trips": organized_trips,
            "counts": counts,
            "total_trips": len(processed_trips)
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error fetching itinerary: {str(e)}")


@router.get("/map-data")
async def get_map_data(user: dict = Depends(verify_firebase_user)):
    """Return map-ready trip data."""
    # Reuse get_user_itinerary logic for consistency
    data = await get_user_itinerary(user)
    return {
        "status": "success",
        "user_id": user["uid"],
        "map_data": data["trips"],
        "total_trips": data["total_trips"]
    }


@router.put("/{trip_id}")
async def update_trip(
    trip_id: str,
    trip_update: TripUpdate,
    user: dict = Depends(verify_firebase_user)
):
    """Update an existing trip."""
    try:
        from bson import ObjectId
        user_id = user["uid"]

        existing = trips_col.find_one({"_id": ObjectId(trip_id), "user_id": user_id})
        if not existing:
            raise HTTPException(404, "Trip not found")

        update_doc = {"updated_at": datetime.utcnow().isoformat()}

        if trip_update.location:
            geo = geocode_location(trip_update.location)
            if geo:
                update_doc.update({
                    "location": trip_update.location,
                    "formatted_address": geo.get("formatted_address"),
                    "coordinates": {"lat": geo["lat"], "lng": geo["lng"]},
                    "country": geo.get("country"),
                    "city": geo.get("city"),
                })

        for field in ["start_date", "end_date", "status", "notes", "accommodation"]:
            value = getattr(trip_update, field)
            if value is not None:
                update_doc[field] = value

        trips_col.update_one({"_id": ObjectId(trip_id)}, {"$set": update_doc})
        updated = trips_col.find_one({"_id": ObjectId(trip_id)})
        updated["_id"] = str(updated["_id"])

        return {"status": "success", "message": "Trip updated", "trip": updated}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error updating trip: {str(e)}")


@router.delete("/{trip_id}")
async def delete_trip(trip_id: str, user: dict = Depends(verify_firebase_user)):
    """Delete a trip."""
    try:
        from bson import ObjectId
        user_id = user["uid"]
        res = trips_col.delete_one({"_id": ObjectId(trip_id), "user_id": user_id})

        if res.deleted_count == 0:
            raise HTTPException(404, "Trip not found")

        return {"status": "success", "message": "Trip deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error deleting trip: {str(e)}")


@router.get("/search")
async def search_destinations(query: str, user: dict = Depends(verify_firebase_user)):
    """Search destinations using geocoding API."""
    try:
        results = batch_geocode([query]) # Use batch just for consistency or single
        # Actually batch_geocode returns a dict, let's use geocode_location directly or list
        # But geocode_location returns one result.
        # Let's use Nominatim search directly if we want suggestions, but our utils return single best match.
        # For now, just return the single best match as a list of 1
        
        geo = geocode_location(query)
        suggestions = []
        if geo:
            suggestions.append({
                "name": geo.get("formatted_address", query),
                "country": geo.get("country", ""),
                "lat": geo.get("lat"),
                "lng": geo.get("lng"),
                "city": geo.get("city", "")
            })

        return {"status": "success", "suggestions": suggestions}

    except Exception as e:
        raise HTTPException(500, f"Error searching destinations: {str(e)}")
