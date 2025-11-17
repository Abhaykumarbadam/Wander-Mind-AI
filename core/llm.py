# core/llm.py
import os
from pathlib import Path
from dotenv import dotenv_values
from typing import List, Dict
import asyncio

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

env = Path(__file__).resolve().parent.parent / ".env"
if env.exists():
    cfg = dotenv_values(str(env))
    for k,v in cfg.items():
        if v is not None: os.environ[k] = v

GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY","")

def _to_msgs(msgs: List[Dict[str,str]]):
    out=[]
    for m in msgs:
        c = m.get("content", "")
        r = m.get("role", "user").lower()
        if r == "user":
            out.append(HumanMessage(content=c))
        elif r == "system":
            # Gemini via LangChain handles SystemMessage properly
            out.append(SystemMessage(content=c))
        else:
            # assistant role
            out.append(AIMessage(content=c))
    return out

def chat(messages: List[Dict[str,str]], temperature=0.3, max_tokens=1500) -> str:
    """Synchronous chat call - for backwards compatibility"""
    model = ChatGoogleGenerativeAI(
        model = GEMINI_MODEL,
        google_api_key = GOOGLE_API_KEY,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens
        }
    )
    lc_msgs = _to_msgs(messages)
    resp = model.invoke(lc_msgs)
    return resp.content

async def chat_async(messages: List[Dict[str,str]], temperature=0.3, max_tokens=1500, timeout_sec=60) -> str:
    """Async chat call with timeout support - recommended for production"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    def _chat_sync():
        model = ChatGoogleGenerativeAI(
            model = GEMINI_MODEL,
            google_api_key = GOOGLE_API_KEY,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }
        )
        lc_msgs = _to_msgs(messages)
        resp = model.invoke(lc_msgs)
        return resp.content
    
    # Run the blocking call in a thread pool to avoid blocking the event loop
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _chat_sync),
            timeout=timeout_sec
        )
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(f"LLM call timed out after {timeout_sec} seconds")
