from dotenv import load_dotenv
import os
# ...existing code..
from pydantic_settings import BaseSettings
# ...existing code...
load_dotenv()


class Settings(BaseSettings):
    # API keys / models
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    GOOGLE_PROJECT_ID: str | None = os.getenv("GOOGLE_PROJECT_ID")
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "embedding-001")
    GEMINI_LLM_MODEL: str = os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash")
    # Local sentence-transformers fallback (used if Gemini embeddings not available)
    SENTENCE_TRANSFORMER_MODEL: str = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")

    # Chroma Configuration
    CHROMA_MODE: str = os.getenv("CHROMA_MODE", "local")  # "local", "server", or "cloud"
    
    # Local mode settings
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./chroma_db")
    
    # Server mode settings
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8001"))
    CHROMA_URL: str = os.getenv("CHROMA_URL", "http://localhost:8001")
    
    # Cloud mode settings
    CHROMA_API_KEY: str | None = os.getenv("CHROMA_API_KEY")
    CHROMA_TENANT: str | None = os.getenv("CHROMA_TENANT")
    CHROMA_DATABASE: str | None = os.getenv("CHROMA_DATABASE")
    
    # Collection settings
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "travel_kb")

    # Chunking
    CHUNK_SIZE_CHARS: int = int(os.getenv("CHUNK_SIZE_CHARS", "1200"))
    CHUNK_OVERLAP_CHARS: int = int(os.getenv("CHUNK_OVERLAP_CHARS", "200"))

    # Retrieval
    DEFAULT_TOP_K: int = int(os.getenv("DEFAULT_TOP_K", "6"))

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # For pydantic v2 / pydantic-settings: allow extra env vars (ignore unknowns)
    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
