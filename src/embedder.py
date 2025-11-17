from typing import List
from loguru import logger
from .config import settings
import os

try:
    import google.generativeai as genai
except Exception:
    genai = None
try:
    # Optional local fallback
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


def ensure_genai_configured():
    if genai is None:
        raise RuntimeError("google.generativeai library not installed. Please install google-generativeai")
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set in environment (.env).")


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts using configured Gemini embedding model.

    Requires GOOGLE_API_KEY set in environment and google.generativeai package.
    """
    # Prefer Google Gemini embeddings if available and configured
    if genai is not None and hasattr(genai, 'embeddings'):
        ensure_genai_configured()
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = settings.GEMINI_EMBEDDING_MODEL
        logger.info(f"Generating embeddings for {len(texts)} texts with model={model}")
        try:
            resp = genai.embeddings.create(model=model, input=texts)
            # response.data is list with embedding
            embeddings = [r['embedding'] for r in resp.data]
            return embeddings
        except Exception as e:
            logger.exception("Failed to generate embeddings with google.generativeai")

    # Fallback: use local sentence-transformers if available
    if SentenceTransformer is not None:
        try:
            logger.info(f"Falling back to sentence-transformers model={settings.SENTENCE_TRANSFORMER_MODEL}")
            model = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
            embs = model.encode(texts, show_progress_bar=False)
            # convert to list of lists
            try:
                return [e.tolist() for e in embs]
            except Exception:
                return [list(e) for e in embs]
        except Exception as e:
            logger.exception("Failed to generate embeddings with sentence-transformers")

    # If we reach here, no embedding method is available
    raise RuntimeError("No embedding backend available. Install google-generativeai with a valid API key or sentence-transformers.")


def generate_embedding(text: str) -> List[float]:
    return generate_embeddings([text])[0]
