# Travel Knowledge Base — RAG Pipeline

This project implements a Retrieval-Augmented Generation (RAG) pipeline over a JSON knowledge base of country travel information.

Features
- FastAPI service with endpoints to embed the dataset and answer questions
- Chunking, embedding (Google Gemini embeddings), and storage in ChromaDB (local persistent)
- Gemini 2.0 Flash LLM for grounded answers
- Prompt template that prevents hallucinations and forces facts-only answers
- Debug logging with loguru

Important: This repo expects you to supply a Google API key for Gemini models (set `GOOGLE_API_KEY` in `.env`).

Project structure
```
.
├─ data/                      # JSON knowledge base (country files)
├─ src/
│  ├─ main.py                 # FastAPI app
│  ├─ loader.py               # JSON loader and normalizer
│  ├─ chunking.py             # chunking logic
│  ├─ embedder.py             # embedding wrapper (Gemini)
│  ├─ retriever.py            # Chroma persistence + retrieval
│  ├─ llm.py                  # LLM wrapper for Gemini
│  ├─ prompt.py               # Prompt templates
│  └─ config.py               # Config (.env)
├─ scripts/
│  └─ query_test.py           # Example queries
├─ requirements.txt
└─ README.md
```

Setup (local)
1. Create a Python virtual environment (venv or poetry). Example using venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create `.env` (see `.env.example`) and set `GOOGLE_API_KEY`.

3. Build embeddings and start server:

```bash
# Build embeddings from data/ (this writes to ChromaDB persistent folder)
curl -X POST http://localhost:8000/embed_data -H 'Content-Type: application/json' -d '{"data_dir": "./data"}'

# Start server
uvicorn src.main:app --reload
```

Ask a question (example):

```bash
curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' -d '{"question": "When is the best time to visit Tokyo?"}'
```

Docker
1. Build image: docker build -t travel-rag:latest .
2. Run container with environment variables (ensure GOOGLE_API_KEY passed).

Notes
- The project uses `google-generativeai` package to call Gemini models. Make sure your Google account and project have access to Gemini.
- If you prefer other embedding/LLM providers, adapt `src/embedder.py` and `src/llm.py`.
# Travel Knowledge Base

A structured JSON database of top tourist points of interest (POIs) worldwide, with focus on India and famous global destinations.

## 📁 Structure

```
travel_knowledge_base/
│
├── data/
│   ├── india/
│   │   ├── kerala.json
│   │   ├── telangana.json
│   │   ├── rajasthan.json
│   │   ├── delhi.json
│   │   ├── goa.json
│   │   ├── maharashtra.json
│   │   ├── himachal_pradesh.json
│   │   ├── tamil_nadu.json
│   │   ├── uttar_pradesh.json
│   │   └── west_bengal.json
│   │
│   ├── france/
│   │   ├── paris.json
│   │   └── nice.json
│   │
│   ├── japan/
│   │   ├── tokyo.json
│   │   ├── kyoto.json
│   │   └── osaka.json
│   │
│   ├── united_kingdom/
│   │   ├── london.json
│   │   └── edinburgh.json
│   │
│   ├── italy/
│   │   ├── rome.json
│   │   ├── venice.json
│   │   └── florence.json
│   │
│   ├── united_states/
│   │   ├── new_york.json
│   │   ├── los_angeles.json
│   │   └── san_francisco.json
│   │
│   ├── australia/
│   │   ├── sydney.json
│   │   └── melbourne.json
│   │
│   ├── uae/
│   │   ├── dubai.json
│   │   └── abu_dhabi.json
│   │
│   ├── thailand/
│   │   ├── bangkok.json
│   │   └── phuket.json
│   │
│   ├── singapore/
│   │   └── singapore.json
│   │
│   ├── switzerland/
│   │   ├── zurich.json
│   │   ├── lucerne.json
│   │   └── interlaken.json
│   │
│   ├── spain/
│   │   ├── barcelona.json
│   │   └── madrid.json
│   │
│   └── greece/
│       ├── athens.json
│       └── santorini.json
│
└── README.md
```

## 📊 Schema

Each POI follows this JSON schema:

```json
{
    "id": "unique_string_identifier",
    "poi_type": "cafe | restaurant | viewpoint | shopping | museum | park | monument | other",
    "name": "Name of the POI",
    "city": "City where the POI is located",
    "state": "State or region (if applicable)",
    "country": "Country where the POI is located",
    "description": "Concise description (1-2 sentences)",
    "tags": ["list", "of", "relevant", "tags"],
    "duration_hours": 2.5,
    "best_time": ["morning", "afternoon", "evening", "sunset", "night"],
    "category": "food | viewpoint | shopping | cultural | historical | nature | other",
    "lat": 12.3456,
    "lon": 78.9012,
    "price_band": 1-5,
    "source": ["wikidata:QID", "wikipedia:Page_name"]
}
```

## 🗺️ Coverage

### India (10 States/Regions)
- **Kerala**: Munnar, Alleppey, Fort Kochi, Varkala, Athirappilly
- **Telangana**: Hyderabad (Charminar, Golconda Fort, Ramoji Film City)
- **Rajasthan**: Jaipur, Udaipur, Jaisalmer
- **Delhi**: Red Fort, India Gate, Qutub Minar, Humayun's Tomb
- **Goa**: Beaches, Basilica, Flea Market, Dudhsagar Falls
- **Maharashtra**: Mumbai (Gateway of India, Marine Drive, Elephanta Caves)
- **Himachal Pradesh**: Manali, Shimla, Dharamshala, Kasol
- **Tamil Nadu**: Madurai, Chennai, Ooty, Mahabalipuram
- **Uttar Pradesh**: Taj Mahal, Varanasi, Agra Fort, Fatehpur Sikri
- **West Bengal**: Kolkata, Darjeeling, Sundarbans

### International Destinations (12 Countries)
- **France**: Paris, Nice
- **Japan**: Tokyo, Kyoto, Osaka
- **United Kingdom**: London, Edinburgh
- **Italy**: Rome, Venice, Florence
- **United States**: New York, Los Angeles, San Francisco
- **Australia**: Sydney, Melbourne
- **UAE**: Dubai, Abu Dhabi
- **Thailand**: Bangkok, Phuket
- **Singapore**: Singapore
- **Switzerland**: Zurich, Lucerne, Interlaken
- **Spain**: Barcelona, Madrid
- **Greece**: Athens, Santorini

## 🏷️ Categories

- **Food**: Cafes, restaurants, food markets
- **Viewpoint**: Scenic locations, observation decks
- **Shopping**: Markets, malls, shopping streets
- **Cultural**: Museums, galleries, cultural centers
- **Historical**: Monuments, forts, ancient sites
- **Nature**: Parks, beaches, mountains, lakes
- **Other**: Theme parks, entertainment venues

## 💰 Price Bands

- **1**: Budget-friendly (Free or very cheap)
- **2**: Moderate (₹500-1000 or $10-30)
- **3**: Mid-range (₹1000-2500 or $30-75)
- **4**: Expensive (₹2500-5000 or $75-150)
- **5**: Luxury (₹5000+ or $150+)

## 📍 Data Quality

- All POIs include verified coordinates (latitude/longitude)
- Sources from Wikidata and Wikipedia for verification
- Realistic visit durations based on typical tourist behavior
- Factual descriptions without invented information

## 🔍 Usage

Load JSON files programmatically to:
- Build travel recommendation systems
- Create itinerary planning tools
- Power AI travel assistants
- Generate interactive maps
- Filter by category, location, price, or time

## 📝 Notes

- All coordinates use decimal degrees format
- Duration in hours (float values)
- Best time includes both time of day and seasonal recommendations where applicable
- Tags are lowercase with underscores for multi-word tags
- IDs are unique across the entire dataset

## 🌟 Total Coverage

- **Countries**: 13
- **Cities/Regions**: 50+
- **POIs**: 200+
- **Categories**: 7
- **Verified Sources**: Wikidata & Wikipedia

---

**Last Updated**: November 2025
**Format**: JSON
**License**: Data compiled from public sources (Wikidata, Wikipedia)
