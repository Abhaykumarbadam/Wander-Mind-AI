"""
Trip tracking + map visualization
Manages user trips with status (completed, ongoing, upcoming) and coordinates
"""

import os
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Literal
from pymongo import MongoClient
import firebase_admin.auth
from dotenv import load_dotenv
from datetime import datetime

# Utility imports
from utils.geocoding import geocode_location
from utils.timezone_service import get_timezone_by_location
from utils.location_extractor import get_trip_locations

# DB helpers
from db.mongo import save_itinerary, save_locations

load_dotenv()

router = APIRouter(prefix="/trips", tags=["trips"])

# MongoDB setup
MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "wandermind")

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
    today = datetime.now().date()
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()

    if today < start:
        return "upcoming"
    elif start <= today <= end:
        return "ongoing"
    return "completed"


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
            raise HTTPException(400, f"Could not geocode location: {trip.location}")

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
            save_itinerary(
                user_id=user_id,
                session_id=trip.session_id,
                itinerary_text=trip.itinerary_text,
                cities=[trip.location],
                start_date=trip.start_date,
                end_date=trip.end_date,
            )

            try:
                locs = get_trip_locations(trip.itinerary_text)
                if locs:
                    save_locations(user_id, trip.session_id, locs)
            except Exception as e:
                print("Location extraction failed:", e)

        return {"status": "success", "message": "Trip created", "trip": trip_doc}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error creating trip: {str(e)}")


@router.get("/list")
async def list_trips(
    status: Optional[str] = None,
    user: dict = Depends(verify_firebase_user)
):
    """Return all trips for user, optionally filtered by status."""
    try:
        user_id = user["uid"]

        query = {"user_id": user_id}
        if status:
            query["status"] = status

        trips = list(trips_col.find(query).sort("start_date", -1))

        for t in trips:
            t["_id"] = str(t["_id"])

        return {
            "status": "success",
            "count": len(trips),
            "trips": trips
        }

    except Exception as e:
        raise HTTPException(500, f"Error fetching trips: {str(e)}")


@router.get("/map-data")
async def get_map_data(user: dict = Depends(verify_firebase_user)):
    """Return map-ready trip data grouped by status."""
    try:
        user_id = user["uid"]
        trips = list(trips_col.find({"user_id": user_id}))

        map_data = {"completed": [], "ongoing": [], "upcoming": []}

        for trip in trips:
            data = {
                "id": str(trip["_id"]),
                "location": trip["location"],
                "formatted_address": trip.get("formatted_address"),
                "coordinates": trip.get("coordinates"),
                "country": trip.get("country"),
                "city": trip.get("city"),
                "start_date": trip.get("start_date"),
                "end_date": trip.get("end_date"),
                "notes": trip.get("notes"),
                "accommodation": trip.get("accommodation"),
                "timezone": trip.get("timezone")
            }

            status = trip.get("status", "upcoming")
            map_data[status].append(data)

        return {
            "status": "success",
            "user_id": user_id,
            "map_data": map_data,
            "total_trips": len(trips),
        }

    except Exception as e:
        raise HTTPException(500, f"Error fetching map data: {str(e)}")


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

        # Handle location updates
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

        # Other updates
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
        results = geocode_location(query)
        if not results:
            return {"status": "success", "suggestions": []}

        suggestions = []
        for r in results[:5]:
            suggestions.append({
                "name": r.get("formatted", ""),
                "country": r.get("components", {}).get("country", ""),
                "lat": r.get("geometry", {}).get("lat"),
                "lng": r.get("geometry", {}).get("lng"),
                "confidence": r.get("confidence"),
            })

        return {"status": "success", "suggestions": suggestions}

    except Exception as e:
        raise HTTPException(500, f"Error searching destinations: {str(e)}")


# ------------------------- ITINERARY ENDPOINTS -------------------------

@router.get("/itinerary")
async def get_user_itinerary(user: dict = Depends(verify_firebase_user)):
    """
    Get user's complete travel itinerary organized by timeline.
    Combines data from both trips and itineraries collections.
    """
    try:
        user_id = user["uid"]
        
        # Fetch from both collections
        trips_from_trips = list(trips_col.find({"user_id": user_id}).sort("start_date", 1))
        itineraries_from_itin = list(itineraries_col.find({"user_id": user_id}))
        
        # Convert itineraries to trip format
        trips_from_itineraries = []
        for itin in itineraries_from_itin:
            cities = itin.get("cities", [])
            location = cities[0] if cities else "Unknown"
            
            trip = {
                "_id": str(itin.get("_id")),
                "user_id": itin.get("user_id"),
                "location": location,
                "start_date": itin.get("start_date"),
                "end_date": itin.get("end_date"),
                "notes": itin.get("itinerary", "")[:200] + "..." if len(itin.get("itinerary", "")) > 200 else itin.get("itinerary", ""),
                "session_id": itin.get("session_id"),
                "source": "itinerary"
            }
            trips_from_itineraries.append(trip)
        
        # Mark trips from trips collection
        for trip in trips_from_trips:
            trip["source"] = "trip"
        
        # Combine both sources
        all_trips = trips_from_trips + trips_from_itineraries
        
        # Process and format trips
        for trip in all_trips:
            if "_id" in trip and not isinstance(trip["_id"], str):
                trip["_id"] = str(trip["_id"])
            
            # Add duration
            if trip.get("start_date") and trip.get("end_date"):
                try:
                    start = datetime.fromisoformat(trip["start_date"])
                    end = datetime.fromisoformat(trip["end_date"])
                    trip["duration"] = (end - start).days + 1
                except:
                    trip["duration"] = 1
            
            # Format dates
            if trip.get("start_date"):
                try:
                    start_date = datetime.fromisoformat(trip["start_date"])
                    trip["formatted_start"] = start_date.strftime("%B %d, %Y")
                    trip["formatted_start_short"] = start_date.strftime("%b %d")
                except:
                    trip["formatted_start"] = trip["start_date"]
                    trip["formatted_start_short"] = trip["start_date"]
            
            if trip.get("end_date"):
                try:
                    end_date = datetime.fromisoformat(trip["end_date"])
                    trip["formatted_end"] = end_date.strftime("%B %d, %Y")
                    trip["formatted_end_short"] = end_date.strftime("%b %d")
                except:
                    trip["formatted_end"] = trip["end_date"]
                    trip["formatted_end_short"] = trip["end_date"]
            
            # Auto-determine status
            if not trip.get("status"):
                today = datetime.now().date()
                if trip.get("start_date") and trip.get("end_date"):
                    try:
                        start_date = datetime.fromisoformat(trip["start_date"]).date()
                        end_date = datetime.fromisoformat(trip["end_date"]).date()
                        
                        if today < start_date:
                            trip["status"] = "upcoming"
                        elif start_date <= today <= end_date:
                            trip["status"] = "ongoing"
                        else:
                            trip["status"] = "completed"
                    except:
                        trip["status"] = "upcoming"
                else:
                    trip["status"] = "upcoming"
        
        # Organize by status
        organized_trips = {
            "upcoming": [t for t in all_trips if t.get("status") == "upcoming"],
            "ongoing": [t for t in all_trips if t.get("status") == "ongoing"],
            "completed": [t for t in all_trips if t.get("status") == "completed"]
        }
        
        # Add counts
        counts = {
            "upcoming": len(organized_trips["upcoming"]),
            "ongoing": len(organized_trips["ongoing"]),
            "completed": len(organized_trips["completed"]),
            "total": len(all_trips)
        }
        
        return {
            "status": "success",
            "trips": organized_trips,
            "counts": counts,
            "total_trips": len(all_trips)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error fetching itinerary: {str(e)}")


@router.post("/sync-itinerary-to-trip")
async def sync_itinerary_to_trip(
    session_id: str,
    user: dict = Depends(verify_firebase_user)
):
    """
    Sync an itinerary to the trips collection (idempotent).
    Creates a new trip or updates existing trip with the same session_id.
    """
    try:
        user_id = user["uid"]
        
        # Fetch itinerary
        itinerary = itineraries_col.find_one({"session_id": session_id, "user_id": user_id})
        if not itinerary:
            raise HTTPException(404, f"Itinerary not found for session: {session_id}")
        
        # Extract trip data from itinerary
        cities = itinerary.get("cities", [])
        location = cities[0] if cities else "Unknown Destination"
        start_date = itinerary.get("start_date")
        end_date = itinerary.get("end_date")
        
        if not start_date or not end_date:
            raise HTTPException(400, "Itinerary missing start_date or end_date")
        
        # Check if trip already exists for this session_id (idempotent)
        existing_trip = trips_col.find_one({"session_id": session_id, "user_id": user_id})
        
        if existing_trip:
            # Update existing trip
            update_doc = {
                "location": location,
                "start_date": start_date,
                "end_date": end_date,
                "status": auto_status(start_date, end_date),
                "notes": itinerary.get("itinerary", "")[:500],
                "updated_at": datetime.utcnow().isoformat()
            }
            
            trips_col.update_one(
                {"_id": existing_trip["_id"]},
                {"$set": update_doc}
            )
            
            trip_id = str(existing_trip["_id"])
            message = "Trip updated from itinerary"
        else:
            # Create new trip
            geo = geocode_location(location)
            if not geo:
                geo = {"lat": 0, "lng": 0}
            
            tz = get_timezone_by_location(geo.get("lat", 0), geo.get("lng", 0))
            
            trip_doc = {
                "user_id": user_id,
                "session_id": session_id,
                "location": location,
                "formatted_address": geo.get("formatted_address", location),
                "coordinates": {"lat": geo.get("lat", 0), "lng": geo.get("lng", 0)},
                "country": geo.get("country"),
                "city": geo.get("city"),
                "timezone": tz.get("timezone") if tz else None,
                "start_date": start_date,
                "end_date": end_date,
                "status": auto_status(start_date, end_date),
                "notes": itinerary.get("itinerary", "")[:500],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
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
