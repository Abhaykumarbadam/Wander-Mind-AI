"""
Accommodation search and pricing routes using Booking.com API via RapidAPI
"""
import os
import requests
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin.auth

load_dotenv()

router = APIRouter(prefix="/accommodations", tags=["accommodations"])

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
BOOKING_API_HOST = "booking-com.p.rapidapi.com"


class AccommodationSearchRequest(BaseModel):
    location: str
    checkin_date: str  # Format: YYYY-MM-DD
    checkout_date: str  # Format: YYYY-MM-DD
    adults: int = 2
    children: int = 0
    room_qty: int = 1
    units: str = "metric"  # or "imperial"
    currency: str = "USD"
    locale: str = "en-us"


class AccommodationDetails(BaseModel):
    hotel_id: str
    checkin_date: str
    checkout_date: str
    adults: int = 2
    children: int = 0
    room_qty: int = 1
    currency: str = "USD"
    locale: str = "en-us"


async def verify_firebase_user(authorization: str = None):
    """Dependency to verify Firebase ID token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = firebase_admin.auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@router.post("/search")
async def search_accommodations(
    request: AccommodationSearchRequest,
    user: dict = Depends(verify_firebase_user)
):
    """
    Search for accommodations using Booking.com API
    Returns list of hotels/properties with prices
    """
    if not RAPIDAPI_KEY:
        raise HTTPException(status_code=500, detail="RAPIDAPI_KEY not configured")
    
    try:
        # Step 1: Get destination ID from location name
        location_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
        location_params = {
            "name": request.location,
            "locale": request.locale
        }
        location_headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": BOOKING_API_HOST
        }
        
        location_response = requests.get(
            location_url,
            headers=location_headers,
            params=location_params,
            timeout=15
        )
        location_response.raise_for_status()
        location_data = location_response.json()
        
        if not location_data:
            raise HTTPException(status_code=404, detail=f"Location '{request.location}' not found")
        
        dest_id = location_data[0].get("dest_id")
        dest_type = location_data[0].get("dest_type", "city")
        
        # Step 2: Search hotels at that destination
        search_url = "https://booking-com.p.rapidapi.com/v1/hotels/search"
        search_params = {
            "checkout_date": request.checkout_date,
            "units": request.units,
            "dest_id": dest_id,
            "dest_type": dest_type,
            "locale": request.locale,
            "adults_number": request.adults,
            "order_by": "popularity",
            "filter_by_currency": request.currency,
            "checkin_date": request.checkin_date,
            "room_number": request.room_qty,
            "children_number": request.children,
            "page_number": 0,
            "include_adjacency": "true"
        }
        
        search_response = requests.get(
            search_url,
            headers=location_headers,
            params=search_params,
            timeout=30
        )
        search_response.raise_for_status()
        search_data = search_response.json()
        
        # Extract and format results
        results = search_data.get("result", [])
        formatted_results = []
        
        for hotel in results[:20]:  # Limit to top 20 results
            formatted_results.append({
                "hotel_id": hotel.get("hotel_id"),
                "name": hotel.get("hotel_name"),
                "address": hotel.get("address"),
                "city": hotel.get("city"),
                "country": hotel.get("country_trans"),
                "latitude": hotel.get("latitude"),
                "longitude": hotel.get("longitude"),
                "rating": hotel.get("review_score"),
                "review_count": hotel.get("review_nr"),
                "price": hotel.get("min_total_price"),
                "currency": hotel.get("currency_code"),
                "price_breakdown": hotel.get("price_breakdown", {}),
                "url": hotel.get("url"),
                "main_photo": hotel.get("main_photo_url"),
                "distance_from_center": hotel.get("distance"),
                "amenities": hotel.get("hotel_facilities", [])[:10]  # Top 10 amenities
            })
        
        return {
            "status": "success",
            "location": request.location,
            "dest_id": dest_id,
            "checkin": request.checkin_date,
            "checkout": request.checkout_date,
            "adults": request.adults,
            "children": request.children,
            "rooms": request.room_qty,
            "total_results": len(results),
            "results": formatted_results,
            "user_id": user.get("uid")
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Booking.com API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.post("/details")
async def get_accommodation_details(
    request: AccommodationDetails,
    user: dict = Depends(verify_firebase_user)
):
    """
    Get detailed information and room options for a specific hotel
    """
    if not RAPIDAPI_KEY:
        raise HTTPException(status_code=500, detail="RAPIDAPI_KEY not configured")
    
    try:
        url = "https://booking-com.p.rapidapi.com/v1/hotels/room-list"
        
        params = {
            "hotel_id": request.hotel_id,
            "arrival_date": request.checkin_date,
            "departure_date": request.checkout_date,
            "adults_number": request.adults,
            "room_qty": request.room_qty,
            "children_number": request.children,
            "units": "metric",
            "currency": request.currency,
            "locale": request.locale
        }
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": BOOKING_API_HOST
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        
        data = response.json()
        
        # Format room data
        rooms = []
        for room_block in data:
            for room in room_block.get("rooms", []):
                rooms.append({
                    "room_id": room.get("room_id"),
                    "name": room.get("room_name"),
                    "description": room.get("room_info", {}).get("room_type", ""),
                    "max_occupancy": room.get("max_occupancy"),
                    "photos": room.get("photos", [])[:5],  # First 5 photos
                    "facilities": room.get("facilities", []),
                    "price": room_block.get("min_price"),
                    "currency": room_block.get("currency_code"),
                    "cancellation_policy": room_block.get("refundable_until", "Non-refundable")
                })
        
        return {
            "status": "success",
            "hotel_id": request.hotel_id,
            "checkin": request.checkin_date,
            "checkout": request.checkout_date,
            "available_rooms": rooms,
            "user_id": user.get("uid")
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Booking.com API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Details fetch error: {str(e)}")


@router.get("/popular/{location}")
async def get_popular_accommodations(
    location: str,
    user: dict = Depends(verify_firebase_user)
):
    """
    Get popular accommodations for a location without requiring dates
    Useful for browsing/planning phase
    """
    if not RAPIDAPI_KEY:
        raise HTTPException(status_code=500, detail="RAPIDAPI_KEY not configured")
    
    try:
        # Get destination ID
        location_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": BOOKING_API_HOST
        }
        
        location_response = requests.get(
            location_url,
            headers=headers,
            params={"name": location, "locale": "en-us"},
            timeout=10
        )
        location_response.raise_for_status()
        location_data = location_response.json()
        
        if not location_data:
            raise HTTPException(status_code=404, detail=f"Location '{location}' not found")
        
        dest_id = location_data[0].get("dest_id")
        
        # Get hotel list
        list_url = "https://booking-com.p.rapidapi.com/v1/hotels/search"
        
        # Use dates 30 days from now for reference pricing
        from datetime import timedelta
        checkin = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        checkout = (datetime.now() + timedelta(days=31)).strftime("%Y-%m-%d")
        
        list_response = requests.get(
            list_url,
            headers=headers,
            params={
                "dest_id": dest_id,
                "dest_type": "city",
                "checkin_date": checkin,
                "checkout_date": checkout,
                "adults_number": 2,
                "order_by": "popularity",
                "filter_by_currency": "USD",
                "locale": "en-us",
                "room_number": 1,
                "page_number": 0
            },
            timeout=20
        )
        list_response.raise_for_status()
        list_data = list_response.json()
        
        results = list_data.get("result", [])[:15]  # Top 15
        
        formatted = []
        for hotel in results:
            formatted.append({
                "hotel_id": hotel.get("hotel_id"),
                "name": hotel.get("hotel_name"),
                "rating": hotel.get("review_score"),
                "review_count": hotel.get("review_nr"),
                "price_from": hotel.get("min_total_price"),
                "currency": hotel.get("currency_code"),
                "photo": hotel.get("main_photo_url"),
                "address": hotel.get("address_trans"),
                "city": hotel.get("city_trans")
            })
        
        return {
            "status": "success",
            "location": location,
            "results": formatted,
            "user_id": user.get("uid")
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
