from loguru import logger
from .config import settings
try:
    import google.generativeai as genai
except Exception:
    genai = None


def ensure_genai():
    if genai is None:
        raise RuntimeError("google.generativeai lib not installed. Install via pip install google-generativeai")
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set in .env")


def generate_answer(system_prompt: str, user_prompt: str) -> str:
    ensure_genai()
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    resp = genai.chat.completions.create(model=settings.GEMINI_LLM_MODEL, messages=messages, temperature=0.0, max_output_tokens=800)
    # The exact shape may vary; try to extract the content
    try:
        content = resp.choices[0].message['content']
    except Exception:
        # fallback
        content = getattr(resp, 'content', str(resp))
    logger.debug("LLM response obtained")
    return content
