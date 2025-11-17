# core/extract.py
import json
import re
from typing import List, Dict
from core.llm import chat
from core.prompts import EXTRACT_SCHEMA_HINT, DELTA_SCHEMA_HINT

def _extract_json_from_text(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks and extra text."""
    if not text:
        return {}
    
    # Remove markdown code blocks if present
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object in the text (handles nested objects)
    # Look for content between first { and matching }
    start = text.find('{')
    if start == -1:
        return {}
    
    # Count braces to find matching closing brace
    brace_count = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    
    if end > start:
        json_str = text[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    return {}

def extract_profile(user_messages: List[str], current_profile: Dict) -> Dict:
    if not user_messages:
        return {}
    convo = "\n".join([f"- {m}" for m in user_messages if m and m.strip()])
    
    # Identify which fields are currently missing
    missing = [k for k, v in current_profile.items() if v in (None, "", [])]
    
    messages = [
        {"role":"system","content":
         "You are a JSON extraction assistant. Extract travel profile information from user messages. "
         "CRITICAL RULES:\n"
         "- Extract ONLY fields that are currently MISSING (NULL/EMPTY) in the profile\n"
         "- DO NOT extract fields that already have values - respect existing data\n"
         "- If destination is already set, DO NOT extract destination even if city is mentioned\n"
         "- If dates are already set, DO NOT extract dates even if mentioned\n"
         "- Only fill in gaps, never overwrite\n"
         "- Return ONLY valid JSON, no markdown, no explanations\n"
         "- Use INR for budget; parse formats like '50k', '1.5L', '120000'\n"
         "- Normalize dates to YYYY-MM-DD format\n"
         "- Set fields that weren't mentioned to null\n"
         "- Do NOT invent values - only extract what's explicitly mentioned\n"
         "- For interests: if multiple mentioned, return as array\n\n"
         "DESTINATION vs DEPARTURE_LOCATION:\n"
         "- destination: Where the user is GOING TO / TRAVELING TO / VISITING\n"
         "  Keywords: 'destination', 'going to', 'traveling to', 'visiting', 'trip to', 'want to go to'\n"
         "  Example: 'Dubai is destination' → destination: 'Dubai'\n"
         "- departure_location: Where the user is LEAVING FROM / DEPARTING FROM\n"
         "  Keywords: 'from', 'departing from', 'leaving from', 'flying from', 'airport'\n"
         "  Example: 'Hyderabad airport' or 'from Hyderabad' → departure_location: 'Hyderabad'\n"
         "- If user says 'Dubai is destination' and 'Hyderabad airport', extract:\n"
         "  destination: 'Dubai', departure_location: 'Hyderabad'\n"
         "- If only one city is mentioned without context, infer from keywords or ask for clarification"},
        {"role":"user","content":
         f"User messages:\n{convo}\n\n"
         f"Current profile (fields with values are already set - DO NOT extract these):\n{json.dumps(current_profile, ensure_ascii=False, indent=2)}\n\n"
         f"MISSING fields to potentially extract: {', '.join(missing) if missing else 'none'}\n\n"
         f"Extract ONLY missing fields that were mentioned. Return JSON structure (set unmentioned to null):\n{json.dumps(EXTRACT_SCHEMA_HINT, ensure_ascii=False, indent=2)}"}
    ]
    try:
        raw = chat(messages, temperature=0.1, max_tokens=800)
        obj = _extract_json_from_text(raw)
        # Normalize interests
        if isinstance(obj.get("interests"), str):
            obj["interests"] = [s.strip() for s in obj["interests"].split(",") if s.strip()]
        elif not isinstance(obj.get("interests"), list):
            obj["interests"] = None
        
        # Safety filter: only return fields that are actually missing
        filtered = {k: v for k, v in obj.items() if k in missing and v is not None}
        return filtered
    except Exception as e:
        print(f"extract_profile error: {e}")
        return {}

def extract_deltas(user_messages: List[str], current_profile: Dict) -> Dict:
    if not user_messages:
        return {}
    convo = "\n".join([f"- {m}" for m in user_messages if m and m.strip()])
    
    # Identify which fields are currently missing
    missing = [k for k, v in current_profile.items() if v in (None, "", [])]
    
    messages = [
        {"role":"system","content":
         "You are a JSON extraction assistant. Extract ONLY fields that are currently MISSING from the profile. "
         "CRITICAL RULES:\n"
         "- Extract ONLY fields that are currently NULL/EMPTY in the profile\n"
         "- DO NOT extract fields that already have values (even if mentioned in messages)\n"
         "- If user mentions a city but destination is already set, DO NOT extract destination\n"
         "- If user mentions dates but they're already set, DO NOT extract dates\n"
         "- Only extract what's explicitly missing\n"
         "- Return ONLY valid JSON, no markdown, no explanations\n"
         "- Normalize dates to YYYY-MM-DD\n"
         "- For budget: parse formats like '50k', '1.5L', '120000'\n\n"
         "DESTINATION vs DEPARTURE_LOCATION:\n"
         "- destination: Where user is GOING TO (keywords: 'destination', 'going to', 'traveling to', 'visiting')\n"
         "- departure_location: Where user is LEAVING FROM (keywords: 'from', 'departing from', 'airport', 'leaving from')\n"
         "- If user says 'Dubai is destination' → extract destination: 'Dubai'\n"
         "- If user says 'Hyderabad airport' or 'from Hyderabad' → extract departure_location: 'Hyderabad'\n"
         "- If both mentioned: extract both correctly based on context"},
        {"role":"user","content":
         f"Latest user messages:\n{convo}\n\n"
         f"Current profile (fields with values are already set - DO NOT extract these):\n{json.dumps(current_profile, ensure_ascii=False, indent=2)}\n\n"
         f"MISSING fields (only extract these if mentioned): {', '.join(missing) if missing else 'none'}\n\n"
         f"Extract ONLY missing fields that were mentioned. Return JSON structure:\n{json.dumps(DELTA_SCHEMA_HINT, ensure_ascii=False, indent=2)}"}
    ]
    try:
        raw = chat(messages, temperature=0.1, max_tokens=600)
        obj = _extract_json_from_text(raw)
        # Normalize interests
        if isinstance(obj.get("interests"), str):
            obj["interests"] = [s.strip() for s in obj["interests"].split(",") if s.strip()]
        elif not isinstance(obj.get("interests"), list):
            obj["interests"] = None
        
        # Safety filter: only return fields that are actually missing
        filtered = {k: v for k, v in obj.items() if k in missing and v is not None}
        return filtered
    except Exception as e:
        print(f"extract_deltas error: {e}")
        return {}


def extract_profile_updates(user_messages: List[str], current_profile: Dict) -> Dict:
    """
    Detect explicit user updates or confirmations for fields that may already have values.
    Returns structure:
      {
        "updates": {"field": "new value", ...},
        "confirmations": ["field_a", "field_b"]
      }
    """
    if not user_messages:
        return {"updates": {}, "confirmations": []}

    convo = "\n".join([f"- {m}" for m in user_messages if m and m.strip()])

    system_prompt = (
        "You analyse recent chat messages to see if the user explicitly UPDATED or CONFIRMED "
        "any travel profile fields. Only act when the user clearly states a change or says to keep "
        "their existing preference. Ignore casual mentions that repeat existing values without an update intent.\n\n"
        "Respond with JSON containing:\n"
        "{\n"
        '  "updates": { "field": "new value" },\n'
        '  "confirmations": ["field_name"]\n'
        "}\n\n"
        "Guidelines:\n"
        "- If the user says things like 'change hotels to mid-range', capture an update for accommodation_level.\n"
        "- If they say 'keep the luxury stays the same', add 'accommodation_level' to confirmations (no update required).\n"
        "- Fields include destination, start_date, end_date, budget_in_inr, travelers, pace, interests, diet, "
        "transport_preference, accommodation_level, departure_location.\n"
        "- Only include fields the user explicitly referenced in these recent messages.\n"
        "- For interests, return an array when multiple interests are stated. Otherwise you may return a single string.\n"
        "- If nothing was updated or confirmed, return empty arrays/objects.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content":
            f"Recent user messages:\n{convo}\n\n"
            f"Current profile snapshot:\n{json.dumps(current_profile, ensure_ascii=False, indent=2)}\n\n"
            "Return updates/confirmations as per the instructions."
        }
    ]

    try:
        raw = chat(messages, temperature=0.1, max_tokens=600)
        obj = _extract_json_from_text(raw) or {}

        updates = obj.get("updates") or {}
        confirmations = obj.get("confirmations") or []

        # Normalise interests to list when provided as comma-separated string
        if isinstance(updates.get("interests"), str):
            listified = [s.strip() for s in updates["interests"].split(",") if s.strip()]
            updates["interests"] = listified or updates["interests"]

        # Ensure confirmations is a list of distinct strings
        if isinstance(confirmations, str):
            confirmations = [confirmations]
        confirmations = [str(c) for c in confirmations if c]

        return {"updates": updates, "confirmations": confirmations}
    except Exception as exc:
        print(f"extract_profile_updates error: {exc}")
        return {"updates": {}, "confirmations": []}