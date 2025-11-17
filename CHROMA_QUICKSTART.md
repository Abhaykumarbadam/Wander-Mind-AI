# 🚀 Chroma Setup - Quick Start

## Fastest Way to Get Started

### Option 1: Local Chroma Server (Recommended for First-Time)

```bash
# 1. Run the setup script
chmod +x setup_chroma.sh
./setup_chroma.sh

# 2. Choose option 1 (Local Server Mode)
# Script will automatically update your .env file
```

Then in two separate terminals:

```bash
# Terminal 1: Start Chroma Server
chroma run --host 0.0.0.0 --port 8001

# Terminal 2: Start FastAPI Backend
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### Option 2: Docker Compose (Recommended for Production)

```bash
# 1. Run the setup script
chmod +x setup_chroma.sh
./setup_chroma.sh

# 2. Choose option 2 (Docker Compose)
# Script will automatically:
# - Update .env with secure API key
# - Build Docker images
# - Start all services

# 3. That's it! Everything is running in Docker
```

---

## Manual Setup (If You Prefer)

### Step 1: Install Chroma Server

```bash
pip install "chromadb[server]" uvicorn
```

### Step 2: Update `.env`

```env
CHROMA_MODE=server
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_URL=http://localhost:8001
CHROMA_API_KEY=your-secure-key-here
```

### Step 3: Update Code

Files already updated:
- ✅ `src/retriever.py` - Now supports server mode
- ✅ `src/config.py` - New Chroma configuration settings
- ✅ `docker-compose.yml` - Docker setup
- ✅ `Dockerfile` - Container setup

### Step 4: Start Services

```bash
# Terminal 1
chroma run --host 0.0.0.0 --port 8001

# Terminal 2
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

---

## Verification

### Check Chroma is Running

```bash
curl http://localhost:8001/api/v1/heartbeat
```

Should return a timestamp like: `{"nanosecond timestamp": 1234567890}`

### Check Backend is Running

```bash
curl http://127.0.0.1:8000/health
```

Should return: `{"ok": true}`

### Check Collections

```bash
curl http://localhost:8001/api/v1/collections
```

---

## Ingest Data

```bash
# Python shell
python3
>>> from src.rag import ingest
>>> result = ingest("./data")
>>> print(f"Inserted {result['inserted']} chunks")
```

Or use the setup script:
```bash
./setup_chroma.sh
# Choose option 5 (Ingest Data)
```

---

## Common Issues

### Port 8001 Already in Use

```bash
# Find what's using it
lsof -i :8001

# Kill it
kill -9 <PID>
```

### Connection Refused

```bash
# Make sure Chroma server is running
chroma run --host 0.0.0.0 --port 8001

# Check logs
tail -f /tmp/chroma.log
```

### Docker Issues

```bash
# Start fresh
docker-compose down -v  # Remove all data
docker-compose build --no-cache
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Your Application                       │
│                  (FastAPI on 8000)                      │
└─────────────────────┬───────────────────────────────────┘
                      │
                      │ HTTP REST API
                      │
        ┌─────────────▼──────────────┐
        │  Chroma Server (8001)      │
        │  ├── Collections           │
        │  ├── Embeddings            │
        │  └── Search Capabilities   │
        └────────────────────────────┘
                      │
                      │ DuckDB + Parquet
                      │
        ┌─────────────▼──────────────┐
        │   Persistent Storage       │
        │   (chroma-data/ volume)    │
        └────────────────────────────┘
```

---

## Next Steps

1. ✅ Run setup script: `./setup_chroma.sh`
2. ✅ Start services
3. ✅ Ingest data
4. ✅ Test RAG queries
5. ✅ Deploy to production with Docker Compose

---

## File Changes Summary

**Modified Files:**
- `src/retriever.py` - Added server mode support
- `src/config.py` - New Chroma settings
- `.env` - New Chroma configuration

**New Files:**
- `docker-compose.yml` - Docker orchestration
- `Dockerfile` - Container definition
- `setup_chroma.sh` - Setup automation
- `CHROMA_MIGRATION_GUIDE.md` - Complete guide

**Backward Compatible:**
- Existing local mode still works with `CHROMA_MODE=local`
- No changes to other modules
- All existing functionality preserved

---

## Documentation

See `CHROMA_MIGRATION_GUIDE.md` for complete technical details.

---

**Status:** ✅ Ready to Deploy  
**Time to Setup:** 5-10 minutes (local) or 15-20 minutes (Docker)  
**Support:** See troubleshooting or check https://docs.trychroma.com
