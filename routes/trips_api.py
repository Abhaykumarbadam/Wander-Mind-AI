"""
Clean API endpoints for trips - fetching single trip or latest trip
"""

import os
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from pymongo import MongoClient
from bson import ObjectId
import firebase_admin.auth
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/trips", tags=["trips-api"])

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "WanderMindAI")

client = MongoClient(MONGODB_URI)
db = client[MONGO_DBNAME]
trips_col = db["trips"]
itineraries_col = db["itineraries"]


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

def serialize_trip(trip: dict) -> dict:
    """Convert MongoDB ObjectId to string for JSON serialization."""
    if trip and "_id" in trip:
        trip["_id"] = str(trip["_id"])
    return trip


# ------------------------- ENDPOINTS -------------------------

@router.get("/{trip_id}")
async def get_trip_by_id(trip_id: str, user: dict = Depends(verify_firebase_user)):
    """
    Get a single trip by trip_id or MongoDB _id.
    
    Args:
        trip_id: Either the MongoDB ObjectId or the trip_id field
    
    Returns:
        Complete trip object with all fields
    """
    try:
        user_id = user["uid"]
        
        # Try to find by MongoDB _id first (if valid ObjectId)
        if ObjectId.is_valid(trip_id):
            trip = trips_col.find_one({"_id": ObjectId(trip_id), "user_id": user_id})
        else:
            # Otherwise try trip_id field
            trip = trips_col.find_one({"trip_id": trip_id, "user_id": user_id})
        
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        
        return serialize_trip(trip)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trip: {str(e)}")


@router.get("/by-session")
async def get_trip_by_session(session_id: str, user: dict = Depends(verify_firebase_user)):
    """
    Get a trip by session_id.
    Checks trips collection first, then falls back to itineraries collection.
    
    Args:
        session_id: The session ID associated with the trip
    
    Returns:
        Trip object with matching session_id
    """
    try:
        user_id = user["uid"]
        
        # First, try to find in trips collection
        trip = trips_col.find_one({"session_id": session_id, "user_id": user_id})
        
        if trip:
            return serialize_trip(trip)
        
        # Fallback: Check itineraries collection
        itinerary = itineraries_col.find_one({"session_id": session_id, "user_id": user_id})
        
        if not itinerary:
            raise HTTPException(status_code=404, detail=f"No trip or itinerary found for session_id: {session_id}")
        
        # Convert itinerary to trip format
        cities = itinerary.get("cities", [])
        location = cities[0] if cities else "Unknown Destination"
        
        # Build trip-like response from itinerary
        trip_from_itinerary = {
            "_id": str(itinerary.get("_id")),
            "user_id": itinerary.get("user_id"),
            "session_id": session_id,
            "location": location,
            "cities": cities,
            "start_date": itinerary.get("start_date"),
            "end_date": itinerary.get("end_date"),
            "itinerary_text": itinerary.get("itinerary", ""),
            "inner_locations": itinerary.get("locations", []),
            "source": "itinerary",
            "created_at": itinerary.get("created_at"),
            "updated_at": itinerary.get("updated_at")
        }
        
        return trip_from_itinerary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trip by session: {str(e)}")


@router.get("/latest/user")
async def get_latest_trip(user: dict = Depends(verify_firebase_user)):
    """
    Get the most recent trip for the authenticated user.
    
    Returns:
        The latest trip object sorted by created_at
    """
    try:
        user_id = user["uid"]
        
        # Find the most recent trip
        trip = trips_col.find_one(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        )
        
        if not trip:
            raise HTTPException(status_code=404, detail="No trips found for this user")
        
        return serialize_trip(trip)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching latest trip: {str(e)}")


@router.get("/all/user")
async def get_all_user_trips(user: dict = Depends(verify_firebase_user)):
    """
    Get all trips for the authenticated user.
    
    Returns:
        List of all trips sorted by created_at (newest first)
    """
    try:
        user_id = user["uid"]
        
        trips = list(trips_col.find(
            {"user_id": user_id}
        ).sort("created_at", -1))
        
        # Serialize all trips
        for trip in trips:
            serialize_trip(trip)
        
        return {
            "status": "success",
            "count": len(trips),
            "trips": trips
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trips: {str(e)}")
