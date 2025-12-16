# core/llm.py
import os
import time
from pathlib import Path
from dotenv import dotenv_values
from typing import List, Dict
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

env = Path(__file__).resolve().parent.parent / ".env"
if env.exists():
    cfg = dotenv_values(str(env))
    for k,v in cfg.items():
        if v is not None: os.environ[k] = v

OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")

def _to_msgs(msgs: List[Dict[str,str]]):
    out=[]
    system_msg = None
    
    for m in msgs:
        c = m.get("content", "")
        r = m.get("role", "user").lower()
        if r == "user":
            out.append(HumanMessage(content=c))
        elif r == "system":
            # Gemini only allows SystemMessage at the beginning
            # Store the first one, ignore subsequent ones
            if system_msg is None:
                system_msg = SystemMessage(content=c)
        else:
            # assistant role
            out.append(AIMessage(content=c))
    
    # Insert system message at the beginning if it exists
    if system_msg:
        out.insert(0, system_msg)
    
    return out

def chat(messages: List[Dict[str,str]], temperature=0.3, max_tokens=1500) -> str:
    """Synchronous chat call - for backwards compatibility"""
    model = ChatOpenAI(
        model = OPENAI_MODEL,
        api_key = OPENAI_API_KEY,
        temperature = temperature,
        max_tokens = max_tokens
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
        model = ChatOpenAI(
            model = OPENAI_MODEL,
            api_key = OPENAI_API_KEY,
            temperature = temperature,
            max_tokens = max_tokens
        )
        lc_msgs = _to_msgs(messages)
        try:
            # Simple retry logic for rate limits
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    resp = model.invoke(lc_msgs)
                    return resp.content
                except Exception as e:
                    if "429" in str(e) or "ResourceExhausted" in str(e):
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                            print(f"Rate limit hit, retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                    raise e
        except Exception as e:
            print(f"LLM Error: {e}")
            return "I'm having a bit of trouble thinking right now. Could you try again in a moment?"
    
    # Run the blocking call in a thread pool to avoid blocking the event loop
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _chat_sync),
            timeout=timeout_sec
        )
        return result
    except asyncio.TimeoutError:
        print(f"LLM call timed out after {timeout_sec} seconds")
        return "I'm taking a bit longer than expected to process this request. The AI service might be busy right now. Please try again in a moment."

async def run_gemini(prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    return await chat_async(messages)
