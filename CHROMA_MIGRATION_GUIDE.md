# 🚀 Chroma Database Migration Guide

## Current Setup vs. Production Setup

### Current (Local Development)
```
Local File Storage
├── ./chroma_db/
│   ├── chroma.sqlite3
│   └── uuid-folders/
└── Data persisted in files
```

### Production (Real Chroma Server)
```
Chroma Server (Docker)
├── Running on http://localhost:8001 (or remote server)
├── REST API for connections
├── Proper authentication
├── Persistent database (PostgreSQL backend)
└── Scalable, multi-client support
```

---

## Step 1: Choose Your Chroma Setup

### Option A: Local Chroma Server (Recommended for Development/Staging)
- Easy to set up
- Runs locally on port 8001
- No external dependencies
- Good for testing before production

### Option B: Cloud Chroma (Production Ready)
- Hosted by Chroma team
- Fully managed
- Built-in authentication
- Recommended for production

### Option C: Docker Chroma (Recommended for Production)
- Full control
- Can deploy anywhere
- PostgreSQL backend
- Scalable

---

## Implementation: Option A (Local Chroma Server)

### Step 1.1: Install Chroma Server

```bash
# Install chroma with server support
pip install chroma[server] uvicorn

# Or if already installed, ensure it has server support
pip install --upgrade chromadb uvicorn
```

### Step 1.2: Update Configuration

**File:** `.env`

```env
# Old (Local):
# CHROMA_DIR=./chroma_db

# New (Server):
CHROMA_MODE=server
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_API_KEY=your-secure-api-key-here
CHROMA_URL=http://localhost:8001
CHROMA_COLLECTION_NAME=travel_kb
```

### Step 1.3: Update Retriever for Server Mode

See updated `src/retriever.py` below.

### Step 1.4: Start Chroma Server

```bash
# Terminal 1: Start Chroma Server
chroma run --host 0.0.0.0 --port 8001

# Or with Docker (see Step 2)
```

### Step 1.5: Start Your Application

```bash
# Terminal 2: Start FastAPI Backend
cd /Users/himatejagudi/Desktop/WM2
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

---

## Implementation: Option C (Docker Chroma - Production)

### Step 2.1: Create Docker Compose Setup

**File:** `docker-compose.yml` (create in project root)

```yaml
version: '3.8'

services:
  chroma:
    image: chromadb/chroma:latest
    container_name: wandermind-chroma
    ports:
      - "8001:8000"  # Container port 8000 → Host port 8001
    environment:
      - CHROMA_API_IMPL=rest
      - CHROMA_HOST=0.0.0.0
      - CHROMA_PORT=8000
      - CHROMA_PERSISTENT_DIRECTORY=/data
    volumes:
      - chroma-data:/data
    networks:
      - wandermind-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  backend:
    build: .
    container_name: wandermind-backend
    ports:
      - "8000:8000"
    environment:
      - CHROMA_MODE=server
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - CHROMA_URL=http://chroma:8000
      - CHROMA_API_KEY=${CHROMA_API_KEY}
    depends_on:
      chroma:
        condition: service_healthy
    networks:
      - wandermind-network
    restart: unless-stopped
    volumes:
      - ./data:/app/data  # For data ingestion

volumes:
  chroma-data:
    driver: local

networks:
  wandermind-network:
    driver: bridge
```

### Step 2.2: Create Dockerfile

**File:** `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Run FastAPI
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 2.3: Start with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f chroma
docker-compose logs -f backend

# Stop services
docker-compose down
```

---

## Updated Code Files

### File: `src/retriever.py` (Updated for Server Mode)

```python
from loguru import logger
from .config import settings
import chromadb
from chromadb.config import Settings as ChromaSettings
import numpy as np
from typing import List, Dict, Optional


class ChromaStore:
    def __init__(self, collection_name: str = None):
        collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        
        # Determine if we're using server mode or local mode
        if settings.CHROMA_MODE == "server":
            self._init_server_mode(collection_name)
        else:
            self._init_local_mode(collection_name)
    
    def _init_server_mode(self, collection_name: str):
        """Initialize client for Chroma Server (via HTTP)"""
        try:
            logger.info(f"Connecting to Chroma Server at {settings.CHROMA_URL}")
            
            # Connect to Chroma server via HTTP
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                headers={"Authorization": f"Bearer {settings.CHROMA_API_KEY}"}
                if settings.CHROMA_API_KEY else {}
            )
            
            # Verify connection
            version = self.client.get_version()
            logger.info(f"Connected to Chroma Server version: {version}")
            
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Recommended for embeddings
            )
            logger.info(f"Using collection: {collection_name} (Server Mode)")
            
        except Exception as e:
            logger.error(f"Failed to connect to Chroma Server: {e}")
            raise ConnectionError(
                f"Cannot connect to Chroma Server at {settings.CHROMA_URL}. "
                "Ensure the server is running: chroma run --host 0.0.0.0 --port 8001"
            )
    
    def _init_local_mode(self, collection_name: str):
        """Initialize client for local persistent storage (development)"""
        try:
            logger.info(f"Using local ChromaDB at {settings.CHROMA_DIR}")
            
            # Use PersistentClient for local development
            self.client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
            
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Using collection: {collection_name} (Local Mode)")
            
        except Exception as e:
            logger.error(f"Failed to initialize local ChromaDB: {e}")
            raise

    def rebuild(self, documents: List[str], embeddings: List[List[float]], 
                metadatas: List[dict], ids: List[str]):
        """Clear and repopulate the collection"""
        try:
            # Delete existing collection
            self.client.delete_collection(self.collection.name)
            logger.info(f"Deleted existing collection: {self.collection.name}")
        except Exception as e:
            logger.debug(f"Collection didn't exist or couldn't be deleted: {e}")
        
        # Recreate collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Add documents in batches (Chroma has batch limits)
        batch_size = 100
        logger.info(f"Upserting {len(documents)} documents to ChromaDB (batch size: {batch_size})")
        
        for i in range(0, len(documents), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            
            self.collection.add(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metadatas,
                embeddings=batch_embeddings
            )
            logger.debug(f"Upserted batch {i//batch_size + 1}")
        
        # Persist if supported
        try:
            if hasattr(self.client, 'persist'):
                self.client.persist()
                logger.info("Data persisted successfully")
        except Exception as e:
            logger.debug(f"Persistence not available or failed: {e}")

    def query(self, query_embedding: List[float], top_k: int = 6, rerank: bool = False):
        """Query the collection"""
        try:
            resp = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=['metadatas', 'documents', 'distances']
            )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

        results = []
        
        # Handle different response formats from Chroma
        if resp.get('results'):
            entries = resp.get('results', [])[0]
        elif resp.get('documents'):
            entries = {
                'documents': resp.get('documents', [[]])[0],
                'metadatas': resp.get('metadatas', [[]])[0],
                'distances': resp.get('distances', [[]])[0],
                'ids': resp.get('ids', [[]])[0] if resp.get('ids') else []
            }
        else:
            entries = {}

        docs = entries.get('documents', [])
        metadatas = entries.get('metadatas', [])
        distances = entries.get('distances', [])
        ids = entries.get('ids', [])

        for d, m, dist, id_ in zip(docs, metadatas, distances, ids):
            results.append({'id': id_, 'document': d, 'metadata': m, 'distance': dist})

        if rerank:
            stored = self.collection.get(
                ids=[r['id'] for r in results],
                include=['embeddings']
            )
            emb_map = {eid: emb for eid, emb in zip(
                stored.get('ids', []), 
                stored.get('embeddings', [])
            )}
            q = np.array(query_embedding, dtype=float)
            
            for r in results:
                e = np.array(emb_map.get(r['id'], []), dtype=float)
                if e.size == 0:
                    r['score'] = 0.0
                    continue
                cos = float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-12))
                r['score'] = cos
            
            results.sort(key=lambda x: x.get('score', 0.0), reverse=True)

        return results
```

### File: `src/config.py` (Updated)

```python
from dotenv import load_dotenv
import os
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # API keys / models
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    GOOGLE_PROJECT_ID: str | None = os.getenv("GOOGLE_PROJECT_ID")
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "embedding-001")
    GEMINI_LLM_MODEL: str = os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash")
    SENTENCE_TRANSFORMER_MODEL: str = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")

    # Chroma Configuration
    CHROMA_MODE: str = os.getenv("CHROMA_MODE", "local")  # "local" or "server"
    
    # Local mode settings
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./chroma_db")
    
    # Server mode settings
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8001"))
    CHROMA_URL: str = os.getenv("CHROMA_URL", "http://localhost:8001")
    CHROMA_API_KEY: str | None = os.getenv("CHROMA_API_KEY")
    
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

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
```

---

## Updated `.env` File

Create or update your `.env` file:

```env
# Google API
GOOGLE_API_KEY=your-google-api-key
GOOGLE_PROJECT_ID=your-project-id

# Chroma Configuration
CHROMA_MODE=server                    # "local" for development, "server" for production
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_URL=http://localhost:8001
CHROMA_API_KEY=your-secure-api-key-here

# Collection
CHROMA_COLLECTION_NAME=travel_kb

# Chunking
CHUNK_SIZE_CHARS=1200
CHUNK_OVERLAP_CHARS=200
DEFAULT_TOP_K=6

# Server
HOST=0.0.0.0
PORT=8000
```

---

## Quick Start Commands

### Local Server Mode (Development)

```bash
# Terminal 1: Start Chroma Server
chroma run --host 0.0.0.0 --port 8001

# Terminal 2: Start FastAPI Backend
cd /Users/himatejagudi/Desktop/WM2
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Ingest data (in Python shell or script)
from src.rag import ingest
ingest("./data")
```

### Docker Compose (Production)

```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f chroma
docker-compose logs -f backend

# Ingest data
docker-compose exec backend python -c "from src.rag import ingest; ingest('./data')"

# Stop all services
docker-compose down
```

---

## Verification Steps

### 1. Check Chroma Server Health

```bash
curl http://localhost:8001/api/v1/heartbeat
# Should return: {"nanosecond timestamp"}
```

### 2. List Collections

```bash
curl http://localhost:8001/api/v1/collections
# Should return list of collections including "travel_kb"
```

### 3. Test RAG Pipeline

```bash
# In Python
from src.rag import ingest, generate_answer

# Ingest data
result = ingest("./data")
print(f"Inserted {result['inserted']} chunks")

# Query
answer = generate_answer("Tell me about Paris")
print(answer)
```

### 4. Monitor Connection

```bash
# Watch backend logs
tail -f /tmp/fastapi.log | grep -i chroma

# Should see:
# "Connected to Chroma Server version: X.X.X"
# "Using collection: travel_kb (Server Mode)"
```

---

## Troubleshooting

### Issue: "Connection refused" on port 8001

```bash
# Check if Chroma server is running
lsof -i :8001

# Start Chroma if not running
chroma run --host 0.0.0.0 --port 8001
```

### Issue: "Collection not found"

```bash
# Ingest data
python -c "from src.rag import ingest; ingest('./data')"
```

### Issue: "API key unauthorized"

```bash
# Ensure API key matches in .env and server startup
# Update .env with correct key
# Restart services
```

### Issue: Docker connection errors

```bash
# Check Docker is running
docker ps

# Check network
docker network ls

# View logs
docker-compose logs chroma
```

---

## Migration Path

### Phase 1: Development (Week 1)
- [x] Install Chroma server locally
- [x] Update config to use server mode
- [x] Update retriever.py for HttpClient
- [x] Test locally with ingest/query
- [x] Update .env

### Phase 2: Staging (Week 2)
- [ ] Set up Docker Compose
- [ ] Deploy to staging environment
- [ ] Full integration testing
- [ ] Performance benchmarking

### Phase 3: Production (Week 3)
- [ ] Deploy Docker to production
- [ ] Set up monitoring and logging
- [ ] Backup strategy
- [ ] Authentication/security hardening

---

## Security Considerations

### API Key Management
```bash
# Generate secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Network Security
- Keep Chroma on internal network (not exposed to internet)
- Use API keys for all connections
- Enable SSL/TLS if over public network

### Data Backup
```bash
# Backup Docker volume
docker run --rm -v chroma-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/chroma-backup.tar.gz -C /data .
```

---

## Next Steps

1. **Immediate**: Update `.env` with `CHROMA_MODE=server`
2. **Next**: Update `src/retriever.py` with new code
3. **Then**: Update `src/config.py` with new settings
4. **Test**: Run verification steps
5. **Deploy**: Use docker-compose for production

---

**Status:** 📋 Ready for implementation  
**Estimated Time:** 1-2 hours for local dev setup, 4-6 hours for full Docker production setup  
**Support:** See troubleshooting section or check Chroma docs at https://docs.trychroma.com
