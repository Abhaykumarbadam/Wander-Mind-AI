"""
This file contains the API endpoints for fetching booking information for flights,
hotels, and other transportation. It uses the Aviationstack API for flights and
an LLM for other suggestions.
"""
import os
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import httpx
from core.llm import chat_async

router = APIRouter(prefix="/booking", tags=["booking"])

AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY", "a6004bd5950e0c72b00c36b60d361b64")
AVIATIONSTACK_API_URL = "http://api.aviationstack.com/v1/flights"

@router.get("/flights")
async def get_flights(
    origin: str = Query(..., description="IATA code of the origin airport (e.g., 'JFK')"),
    destination: str = Query(..., description="IATA code of the destination airport (e.g., 'LAX')"),
    flight_date: str = Query(..., description="Flight date in YYYY-MM-DD format")
):
    """
    Fetch flight information from the Aviationstack API.
    """
    if not AVIATIONSTACK_API_KEY:
        raise HTTPException(status_code=500, detail="Aviationstack API key is not configured.")

    params = {
        "access_key": AVIATIONSTACK_API_KEY,
        "dep_iata": origin,
        "arr_iata": destination,
        "flight_date": flight_date,
        "limit": 10  # Limit to 10 results for performance
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(AVIATIONSTACK_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return {"error": data["error"].get("info", "Unknown Aviationstack error")}

            # Simplify the response for the frontend
            simplified_flights = []
            for flight in data.get("data", []):
                simplified_flights.append({
                    "airline": flight.get("airline", {}).get("name", "N/A"),
                    "flight_number": flight.get("flight", {}).get("iata", "N/A"),
                    "departure_airport": flight.get("departure", {}).get("airport", "N/A"),
                    "departure_time": flight.get("departure", {}).get("scheduled", "N/A"),
                    "arrival_airport": flight.get("arrival", {}).get("airport", "N/A"),
                    "arrival_time": flight.get("arrival", {}).get("scheduled", "N'A"),
                    "status": flight.get("flight_status", "N/A")
                })
            return {"flights": simplified_flights}

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Error fetching flight data: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/accommodations")
async def get_accommodation_suggestions(
    destination: str = Query(..., description="The city for which to get suggestions (e.g., 'Paris')"),
    budget: Optional[str] = Query("moderate", description="Budget level (e.g., 'budget', 'moderate', 'luxury')")
):
    """
    Use an LLM to generate hotel, train, and bus suggestions.
    """
    prompt = f"""
    Provide a concise list of accommodation and transportation suggestions for a trip to {destination} with a {budget} budget.
    Your response MUST be a JSON object with the following structure:
    {{
      "hotels": [
        {{ "name": "Hotel Name", "type": "e.g., Boutique Hotel", "price_range": "e.g., $150-$250", "reason": "Why it's a good choice" }},
        {{ "name": "Another Hotel", "type": "e.g., Hostel", "price_range": "e.g., $30-$50", "reason": "Good for solo travelers" }}
      ],
      "trains": [
        {{ "name": "Train Service Name", "details": "e.g., High-speed train to nearby cities", "tip": "Book in advance for cheaper fares" }}
      ],
      "buses": [
        {{ "name": "Bus Company", "details": "e.g., Connects major tourist spots", "tip": "A cost-effective way to explore the region" }}
      ]
    }}
    Provide 2-3 suggestions for each category. Do not include any text outside of the JSON object.
    """

    try:
        response_text = await chat_async(
            messages=[{"role": "system", "content": "You are a travel booking assistant that returns only JSON."}, {"role": "user", "content": prompt}],
            temperature=0.5
        )
        # Find the JSON object in the response
        import json
        json_match = response_text[response_text.find('{'):response_text.rfind('}')+1]
        return json.loads(json_match)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get LLM suggestions: {str(e)}")
