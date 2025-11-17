# utils/helpers.py
import re
from datetime import datetime
from typing import Dict, List, Optional
from dateutil import parser as dateparser

SLOT_OPTIONS = {
    "pace": [
        "Slow (soak, late starts)",
        "Balanced (mix iconic + chill)",
        "Packed (full days, many spots)"
    ],
    "accommodation_level": [
        "Hostel (budget & social)",
        "Mid-range (comfort + value)",
        "Boutique (aesthetic, curated)",
        "Luxury (premium experience)"
    ],
    "travelers": ["Solo", "Couple", "Family", "Friends group"],
    "diet": ["No preference", "Vegetarian", "Vegan", "Jain", "Halal", "Kosher"],
    "interests": ["Museums","Temples","Gardens","Hiking","Nightlife","Cafes","Food","Beaches","History","Photography","Tea"],
    "transport_preference": [
        "Public transit first (metros/buses)",
        "Mostly rideshare/taxis",
        "Rental car/self-drive",
        "Walking-heavy / minimal vehicles"
    ],
}

def missing_slots(profile: Dict) -> List[str]:
    return [k for k, v in profile.items() if not v]

def merge_soft(existing: Dict, newbits: Dict) -> Dict:
    out = dict(existing or {})
    for k, v in (newbits or {}).items():
        if v is not None and out.get(k) in (None, "", []):
            out[k] = v
    return out

def apply_user_corrections(profile: Dict, message_text: str) -> Dict:
    """Quick rule-based updates for explicit corrections like 'change end date...' etc."""
    if not message_text: return profile
    txt = message_text.lower()
    out = dict(profile)
    
    # Only apply if user explicitly says "change" or if field is currently empty
    is_explicit_change = "change" in txt or "update" in txt or "modify" in txt
    
    if ("end date" in txt or "till" in txt or "until" in txt) and (is_explicit_change or not out.get("end_date")):
        d = _coerce_iso_date(message_text)
        if d: out["end_date"] = d
    if ("start date" in txt or "from " in txt) and (is_explicit_change or not out.get("start_date")):
        d = _coerce_iso_date(message_text)
        if d: out["start_date"] = d
    return out

def _coerce_iso_date(val: Optional[str]) -> Optional[str]:
    if not val: return None
    try:
        d = dateparser.parse(str(val), dayfirst=False, yearfirst=False)
        return d.date().isoformat() if d else None
    except Exception:
        return None

def infer_transport_pref(msgs: List[str]) -> Optional[str]:
    if not msgs: return None
    txt = "\n".join(msgs).lower()
    if any(k in txt for k in ["metro","subway","bus","train","public transit","tram"]):
        return "Public transit first (metros/buses)"
    if any(k in txt for k in ["uber","ola","taxi","cab","rideshare","ride share"]):
        return "Mostly rideshare/taxis"
    if any(k in txt for k in ["rental car","self drive","self-drive","rent a car"]):
        return "Rental car/self-drive"
    if any(k in txt for k in ["walk","walking","on foot"]):
        return "Walking-heavy / minimal vehicles"
    return None

def infer_departure_location(msgs: List[str]) -> Optional[str]:
    """Infer departure location from messages, being careful not to confuse with destination."""
    if not msgs: return None
    txt = "\n".join(msgs).lower()
    
    # Check for explicit departure keywords first (most reliable)
    m = re.search(r"(?i)(?:from|departing from|leaving from|flying from)\s+([A-Za-z .,'-]{2,40})", txt)
    if m:
        loc = m.group(1).strip().rstrip(' .,!?:;')
        # Don't extract if it's mentioned as destination
        if "destination" not in txt[:txt.find(loc.lower())] and "going to" not in txt[:txt.find(loc.lower())]:
            return loc
    
    # Check for airport mentions (usually departure)
    airport_match = re.search(r"([A-Za-z .,'-]{2,40})\s+airport", txt, re.IGNORECASE)
    if airport_match:
        loc = airport_match.group(1).strip().rstrip(' .,!?:;')
        # Only use if not mentioned as destination
        if "destination" not in txt[:txt.find(loc.lower())] and "going to" not in txt[:txt.find(loc.lower())]:
            return loc
    
    # Last resort: airport code (3 letters)
    m2 = re.search(r"\b([A-Z]{3})\b", "\n".join(msgs))
    return m2.group(1) if m2 else None

def parse_destinations(dest_field: Optional[str]) -> List[str]:
    if not dest_field: return []
    txt = dest_field.replace("&", "and")
    parts = re.split(r",| and ", txt, flags=re.I)
    cities = [p.strip().title() for p in parts if p.strip()]
    seen, out = set(), []
    for c in cities:
        if c not in seen:
            seen.add(c); out.append(c)
    return out

def trip_total_days(profile: Dict) -> Optional[int]:
    sd, ed = profile.get("start_date"), profile.get("end_date")
    if not (sd and ed): return None
    try:
        d1 = datetime.strptime(sd, "%Y-%m-%d"); d2 = datetime.strptime(ed, "%Y-%m-%d")
        return (d2 - d1).days + 1
    except Exception:
        return None

def normalize_city_split(cities: List[str], total_days: int, split: Optional[List[Dict[str, object]]]) -> Optional[List[Dict[str, int]]]:
    if not cities or not total_days or total_days <= 0: return None
    if split:
        cleaned, sum_days = [], 0
        for item in split:
            city = str(item.get("city","")).strip().title()
            try: days = int(item.get("days", 0))
            except: days = 0
            if city and days > 0:
                cleaned.append({"city": city, "days": days}); sum_days += days
        if not cleaned: return None
        cleaned = [c for c in cleaned if c["city"] in cities] or cleaned
        if sum_days != total_days:
            scaled = []
            for it in cleaned:
                approx = max(1, round(it["days"] * (total_days / max(1, sum_days))))
                scaled.append({"city": it["city"], "days": approx})
            drift = total_days - sum(x["days"] for x in scaled)
            i = 0
            while drift != 0 and scaled:
                idx = i % len(scaled)
                if drift > 0:  scaled[idx]["days"] += 1; drift -= 1
                else:
                    if scaled[idx]["days"] > 1:
                        scaled[idx]["days"] -= 1; drift += 1
                i += 1
            cleaned = scaled
        return cleaned
    base = total_days // len(cities)
    rem = total_days % len(cities)
    return [{"city": c, "days": base + (1 if i < rem else 0)} for i, c in enumerate(cities)]

def slice_split_for_window(split: List[Dict[str,int]], start_day: int, end_day: int) -> List[Dict[str,int]]:
    out, day_cursor = [], 1
    for item in split:
        city, days = item["city"], int(item["days"])
        city_start, city_end = day_cursor, day_cursor + days - 1
        s = max(city_start, start_day); e = min(city_end, end_day)
        if s <= e: out.append({"city": city, "days": (e - s + 1)})
        day_cursor += days
        if day_cursor > end_day: break
    return out or split

def build_option_block_for(slot: str) -> str:
    from .helpers import SLOT_OPTIONS as _S  # circular safe in same file context
    opts = _S.get(slot)
    if not opts:
        if slot == "display_name":  return "Enter your name or nickname."  # no option buttons for name
        if slot == "destination":   return "Tell me the destination city/cities (1–3 max)."
        if slot == "start_date":    return "Start date (YYYY-MM-DD)."
        if slot == "end_date":      return "End date (YYYY-MM-DD)."
        if slot == "budget_in_inr": return "Total budget in INR (e.g., 120000 or 1.5L)."
        if slot == "departure_location": return "Your departure city or airport code (e.g., Mumbai or BOM)."
        return ""
    bullets = "\n".join([f"• {o}" for o in opts])
    return f"Options:\n{bullets}\nWhich one fits best?"
