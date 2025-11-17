# app.py
import os, json
from datetime import datetime
from typing import Dict, List, Optional
import asyncio

# this loads .env manually and injects into os.environ BEFORE anything

from fastapi import FastAPI, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from dotenv import load_dotenv
load_dotenv()


from core.llm import chat, chat_async
from core.prompts import BASE_SYSTEM_AURA, ASKER_SYSTEM, ITINERARY_SYSTEM_PROMPT
from core.extract import extract_profile, extract_deltas, extract_profile_updates
from db.mongo import (
    get_or_create_profile, save_profile,
    get_or_create_session, append_message,
    get_last_user_messages, get_recent_messages,
    get_session_mode, set_session_mode,
    save_itinerary, get_itinerary,
    reset_trip_fields, get_session_metadata,
    update_session_metadata,
    PREFERENCE_FIELDS, TRIP_FIELDS
)
from utils.helpers import (
    missing_slots, merge_soft, apply_user_corrections,
    infer_transport_pref, infer_departure_location,
    parse_destinations, trip_total_days,
    normalize_city_split, slice_split_for_window,
    build_option_block_for
)

# RAG helper (uses src package RAG helper)
try:
    from src.rag import generate_answer as rag_generate_answer
except Exception:
    rag_generate_answer = None

load_dotenv(dotenv_path="/Users/himatejagudi/Desktop/WM2/.env")

# allow multiple origins (comma-separated)
origins = ["*"]

app = FastAPI(title="Aura Travel — LC + OpenAI + Mongo", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# ——— Models
from pydantic import BaseModel
class MessageRequest(BaseModel):
    user_message: Optional[str] = ""
    session_id: Optional[str] = None

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
    # Filter out display_name from gaps - it's optional UX, not a trip planning requirement
    gaps = [g for g in missing_slots(profile) if g != "display_name"]
    priority = ["destination","start_date","end_date","budget_in_inr","travelers","pace",
                "interests","diet","transport_preference","accommodation_level","departure_location"]
    gaps_sorted = sorted(gaps, key=lambda x: priority.index(x) if x in priority else 999)
    prompts = {
        "departure_location": "Where will you depart from? (City/airport)",
        "destination": "Where we headed?",
        "start_date": "When do you want to start?",
        "end_date": "And when do you wrap?",
        "budget_in_inr": "What's the total budget (INR), hotel included?",
        "travelers": "Who's rolling?",
        "pace": "How fast are we vibing?",
        "interests": "Pick your top vibes (you can say multiple).",
        "diet": "Any food rules I should respect?",
        "transport_preference": "How do you prefer to get around?",
        "accommodation_level": "Stay vibe?"
    }
    qs = []
    for g in gaps_sorted[:2]:
        if g in prompts:  # Safety check - only ask about known trip slots
            qs.append(f"{prompts[g]}\n{build_option_block_for(g)}")
    return "\n\n".join(qs) if qs else "All set."
import firebase_admin
from firebase_admin import credentials, auth as fb_auth

cred = credentials.Certificate("/Users/himatejagudi/Desktop/WM2/wandermindauth.json")
firebase_admin.initialize_app(cred)

def get_uid_from_token(authorization_header: Optional[str]) -> str:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    try:
        token = authorization_header.split("Bearer ")[1].strip()
        decoded = fb_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception as e:
        from fastapi import HTTPException, status
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
        session_meta_updates.update({
            "preferences_prompted": False,
            "preferences_confirmed": False,
            "confirmed_preferences": [],
        })
    if session_meta.get("profile_snapshot") is None:
        session_meta_updates["profile_snapshot"] = safe_snapshot(profile)

    # 2) store incoming + quick rules
    if body.user_message:
        append_message(session_id, "user", body.user_message)
        profile = apply_user_corrections(profile, body.user_message)

    # 3) deltas first (fill missing or overwrite when explicitly stated)
    last_user = get_last_user_messages(session_id, k=5)
    try:
        deltas = extract_deltas(last_user[-3:], profile)
        if isinstance(deltas, dict) and deltas:
            print(f"EXTRACTED DELTAS: {deltas}")
            for k, v in deltas.items():
                if v is None:
                    continue
                current_value = profile.get(k)
                if isinstance(v, list):
                    if current_value != v:
                        profile[k] = v
                else:
                    if current_value != v:
                        profile[k] = v
    except Exception as e:
        print(f"Delta extraction error: {e}")

    # simple heuristics if extractor missed (only for fields that are still missing)
    if not profile.get("transport_preference"):
        guess = infer_transport_pref(last_user)
        if guess:
            profile["transport_preference"] = guess
    # Only infer departure_location if it's missing AND we have explicit departure keywords
    if not profile.get("departure_location"):
        dep = infer_departure_location(last_user)
        if dep:
            profile["departure_location"] = dep

    # 4) fill remaining (soft-merge)
    try:
        llm_bits = extract_profile(last_user, profile)
        print(f"EXTRACTED PROFILE BITS: {llm_bits}")
        profile = merge_soft(profile, llm_bits)
    except Exception as e:
        print(f"Profile extraction error: {e}")
        llm_bits = {}
        profile = merge_soft(profile, llm_bits)

    # 5) handle explicit updates/confirmations from user memories
    try:
        update_payload = extract_profile_updates(last_user[-3:], profile)
    except Exception as e:
        print(f"profile update extraction error: {e}")
        update_payload = {"updates": {}, "confirmations": []}

    confirmed_pref_fields = set(session_meta.get("confirmed_preferences") or [])
    preference_updates = []

    for field, value in (update_payload.get("updates") or {}).items():
        if value is None:
            continue
        current_value = profile.get(field)
        if isinstance(value, list):
            needs_update = current_value != value
        else:
            needs_update = current_value != value
        if needs_update:
            profile[field] = value
            if field in PREFERENCE_FIELDS:
                preference_updates.append(field)

    confirmations = [
        field for field in (update_payload.get("confirmations") or [])
        if field in PREFERENCE_FIELDS
    ]

    if preference_updates:
        confirmed_pref_fields.update(preference_updates)
    if confirmations:
        confirmed_pref_fields.update(confirmations)

    if confirmed_pref_fields:
        session_meta_updates["confirmed_preferences"] = sorted(set(confirmed_pref_fields))
        session_meta_updates["preferences_confirmed"] = True

    save_profile(user_id, profile)

    # Track existing preferences for conversational memory
    preferences_memory = {
        key: profile.get(key)
        for key in PREFERENCE_FIELDS
        if profile.get(key) not in (None, "", [])
    }

    print("PROFILE DEBUG:", profile)

    def persist_session_meta():
        if session_meta_updates:
            update_session_metadata(session_id, session_meta_updates)
            session_meta.update(session_meta_updates)
            session_meta_updates.clear()

    # 6) ask next questions OR done
    gaps = missing_slots(profile)
    if gaps:
        known_fields = {k: v for k, v in profile.items() if v not in (None, "", [])}
        missing_list = gaps

        history = get_recent_messages(session_id, k=10)
        history_msgs = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]

        context_parts = []
        if known_fields:
            context_parts.append(f"Here's what I know about their trip so far: {json.dumps(known_fields, ensure_ascii=False)}")
        if missing_list:
            context_parts.append(f"Still need to find out: {', '.join(missing_list)}")

        qblock = build_questions(profile)
        if qblock and qblock != "All set.":
            context_parts.append(f"Questions I could ask next: {qblock}")

        context_text = "\n".join(context_parts) if context_parts else "Starting fresh conversation."

        should_prompt_preferences = (
            bool(preferences_memory)
            and not session_meta.get("preferences_prompted")
        )

        def summarize_preferences(pref_dict: Dict[str, object]) -> str:
            labels = {
                "pace": "trip pace",
                "interests": "interests",
                "diet": "diet preferences",
                "transport_preference": "getting around",
                "accommodation_level": "stay style",
            }
            phrases = []
            for key, value in pref_dict.items():
                label = labels.get(key, key.replace("_", " "))
                if isinstance(value, list):
                    val_text = ", ".join(value)
                else:
                    val_text = str(value)
                phrases.append(f"{label}: {val_text}")
            return "; ".join(phrases)

        preference_summary = summarize_preferences(preferences_memory) if preferences_memory else ""

        messages = [
            {"role": "system", "content": BASE_SYSTEM_AURA},
            {"role": "system", "content": ASKER_SYSTEM},
        ]

        if should_prompt_preferences:
            messages.append({
                "role": "system",
                "content": (
                    "You remember the traveller's established preferences from their last trip. "
                    f"These were: {preference_summary}. Mention this memory warmly, confirm whether they "
                    "want to keep or update these details for the new trip, and encourage them to adjust anything that no longer fits."
                )
            })
            session_meta_updates["preferences_prompted"] = True
            session_meta_updates["last_prompted_at"] = datetime.utcnow().isoformat() + "Z"

        messages.extend(history_msgs)

        if context_parts:
            messages.append({
                "role": "system",
                "content": f"[Internal context - use this to inform your response naturally: {context_text}]"
            })

        # Optionally augment the LLM call with retrieval-augmented context from the knowledge base
        try:
            if rag_generate_answer and body.user_message:
                try:
                    rag_res = rag_generate_answer(body.user_message, top_k=6)
                    rag_summary = rag_res.get("answer") if isinstance(rag_res, dict) else None
                    rag_sources = rag_res.get("sources") if isinstance(rag_res, dict) else None
                    if rag_summary:
                        messages.append({
                            "role": "system",
                            "content": f"[Knowledge base summary - use to inform answer: {rag_summary} \nSources: {', '.join(rag_sources or [])}]"
                        })
                except Exception as e:
                    # don't block the main flow on RAG errors
                    print(f"RAG retrieval error (ask branch): {e}")
        except Exception:
            pass

        assistant_text = await chat_async(messages, temperature=0.7, max_tokens=1000, timeout_sec=60)
        append_message(session_id, "assistant", assistant_text)
        persist_session_meta()
        return JSONResponse({"type": "ask", "session_id": session_id, "assistant_message": assistant_text})

    # All slots filled - respond naturally, not with a static message
    history = get_recent_messages(session_id, k=10)
    history_msgs = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]

    known_fields = {k: v for k, v in profile.items() if v not in (None, "", [])}

    messages = [
        {"role": "system", "content": BASE_SYSTEM_AURA},
        {"role": "system", "content": "The user has provided all trip details. Respond naturally and professionally as a travel consultant. Let them know you're ready to create their detailed itinerary. Be conversational, warm, and helpful - like a personal travel concierge."}
    ]
    messages.extend(history_msgs)
    messages.append({
        "role": "system",
        "content": f"[All trip details collected: {json.dumps(known_fields, ensure_ascii=False)}. Respond naturally to confirm you're ready to plan.]"
    })

    last_user_msg = (body.user_message or "").lower()
    wants_itinerary = any(phrase in last_user_msg for phrase in [
        "make the plan", "create itinerary", "generate itinerary", "plan my trip",
        "show itinerary", "give me itinerary", "yes", "sure", "go ahead", "let's do it"
    ])

    if wants_itinerary:
        persist_session_meta()
        return JSONResponse({
            "type": "ready_for_plan",
            "session_id": session_id,
            "message": "Perfect! Creating your detailed itinerary now...",
            "profile": known_fields
        })

    # Optionally add RAG-provided context before the final confirmation/chat reply
    try:
        last_user_for_rag = (body.user_message or "") or (history_msgs[-1]['content'] if history_msgs else "")
        if rag_generate_answer and last_user_for_rag:
            try:
                rag_res = rag_generate_answer(last_user_for_rag, top_k=6)
                rag_summary = rag_res.get("answer") if isinstance(rag_res, dict) else None
                rag_sources = rag_res.get("sources") if isinstance(rag_res, dict) else None
                if rag_summary:
                    messages.append({
                        "role": "system",
                        "content": f"[Knowledge base summary - use to inform answer: {rag_summary} \nSources: {', '.join(rag_sources or [])}]"
                    })
            except Exception as e:
                print(f"RAG retrieval error (confirm branch): {e}")
    except Exception:
        pass

    confirm = await chat_async(messages, temperature=0.7, max_tokens=500, timeout_sec=60)
    append_message(session_id, "assistant", confirm)
    persist_session_meta()
    return JSONResponse({"type": "complete", "session_id": session_id, "message": confirm})

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

    must = [s for s in ["destination","start_date","end_date"] if not profile.get(s)]
    if must:
        return JSONResponse(status_code=400, content={"type":"error","message":f"Missing: {', '.join(must)}"})

    cities = parse_destinations(profile.get("destination"))
    if not cities:
        return JSONResponse(status_code=400, content={"type":"error","message":"No destination parsed."})

    total_days = trip_total_days(profile)
    if not total_days or total_days <= 0:
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

    # Store itinerary in user profile for persistence
    save_itinerary(user_id, body.session_id, itinerary, [s["city"] for s in split], profile.get("start_date"), profile.get("end_date"))
    
    return JSONResponse({
        "type":"itinerary",
        "session_id": body.session_id,
        "cities":[s["city"] for s in split],
        "itinerary": itinerary,
        "start_date": profile.get("start_date"),
        "end_date": profile.get("end_date")
    })

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