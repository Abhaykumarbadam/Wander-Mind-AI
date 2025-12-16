<div align="center">

# 🌍 WanderMind AI

### Intelligent AI-Powered Travel Planning & Itinerary Generation Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.4-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vite](https://img.shields.io/badge/Vite-7.2.2-646CFF?style=for-the-badge&logo=vite)](https://vitejs.dev/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.8.0-47A248?style=for-the-badge&logo=mongodb)](https://www.mongodb.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-FF6B6B?style=for-the-badge)](https://www.trychroma.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3.75-121212?style=for-the-badge)](https://www.langchain.com/)

[Features](#-features) • [Architecture](#-architecture) • [Getting Started](#-getting-started) • [API Documentation](#-api-documentation) 

</div>

---

## 📖 Overview

**WanderMind AI** is an advanced, full-stack travel planning platform that leverages cutting-edge AI technology to create personalized travel itineraries. Combining **Retrieval-Augmented Generation (RAG)** with large language models (OpenAI GPT-4, Google Gemini), WanderMind transforms natural conversations into comprehensive travel plans.

### 🎯 What Makes WanderMind Special?

- 💬 **Conversational AI Interface** - Chat naturally about your travel preferences
- 🗺️ **Smart Itinerary Generation** - AI-powered day-by-day travel plans with real locations
- 📍 **Intelligent Geocoding** - Automatic location detection and reverse geocoding
- 🔍 **RAG-Powered Recommendations** - Context-aware suggestions from a vast knowledge base
- 🔐 **Firebase Authentication** - Secure user management and session handling
- 🎨 **Modern Responsive UI** - Beautiful, mobile-friendly interface built with Vite
- 🔗 **Booking Integration** - Direct links to flights, hotels, and transportation
- 💾 **Session Management** - Save, revisit, and modify your travel plans

---

## ✨ Features

### 🤖 AI-Powered Conversation Engine
- Natural language understanding for travel planning
- Multi-turn conversational flow with context retention
- Intelligent profile extraction from user messages
- Smart fallback handling for ambiguous inputs

### 🗺️ Intelligent Itinerary Generation
- **Day-by-day scheduling** with activities, dining, and exploration
- **Automatic geocoding** for all locations using OpenStreetMap Nominatim
- **Budget-aware planning** with cost considerations
- **Pace customization** (relaxed, moderate, fast-paced)
- **Dietary preferences** and interest-based recommendations

### 📊 Knowledge Base & RAG System
- **16+ countries** with detailed POI data (India, Japan, France, UAE, etc.)
- **Vector database** (ChromaDB) for semantic search
- **Chunked embeddings** for efficient retrieval
- **Grounded answers** preventing AI hallucinations

### 🔗 Travel Service Integration
- **Flight search** via Aviation Stack API
- **Hotel recommendations** through LLM-powered search
- **Transportation options** (flights, trains, buses, car rentals)
- **Direct booking links** for MakeMyTrip, Booking.com, etc.

### 👤 User Management
- Firebase Authentication (email/password, Google OAuth)
- Session-based chat history
- Profile persistence across sessions
- Multiple trip management per user

### 🎨 Frontend Features
- **Landing page** with feature showcase
- **Interactive chat interface** with typing indicators
- **Itinerary visualization** with maps and timelines
- **Trip history** and session management
- **Responsive design** for mobile and desktop

---

## 🏗️ Architecture

### Tech Stack

#### Backend
- **Framework**: FastAPI 0.115.4 (Python 3.9+)
- **Database**: MongoDB 4.8.0 (sessions, profiles, trips)
- **Vector DB**: ChromaDB (embeddings, RAG retrieval)
- **LLM Integration**: 
  - LangChain Core 0.3.75
  - OpenAI GPT-4o-mini (primary)
  - Google Gemini 2.0 Flash (legacy support)
- **Authentication**: Firebase Admin SDK
- **HTTP Client**: httpx (async support)

#### Frontend
- **Build Tool**: Vite 7.2.2
- **Framework**: Vanilla JavaScript (modular ES6+)
- **Styling**: Custom CSS with responsive design
- **Firebase**: Client SDK for auth

#### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Reverse Geocoding**: Nominatim OpenStreetMap API
- **Environment**: dotenv for configuration management

### 📂 Project Structure

```
WanderMind/
│
├── 🚀 Backend (FastAPI)
│   ├── app.py                          # Main FastAPI application & endpoints
│   ├── core/                           # Core business logic
│   │   ├── llm.py                      # LLM interface (OpenAI/Gemini)
│   │   ├── extract.py                  # Profile & data extraction logic
│   │   ├── prompts.py                  # System prompts & templates
│   │   └── prompts/                    # Detailed prompt templates
│   │       ├── asker.txt               # Question generation prompts
│   │       ├── itinerary.txt           # Itinerary generation prompts
│   │       └── system_aura.txt         # Base system personality
│   ├── db/                             # Database layer
│   │   └── mongo.py                    # MongoDB connection & operations
│   ├── routes/                         # API route modules
│   │   ├── travel.py                   # Travel search & recommendations
│   │   ├── booking.py                  # Booking links & flight info
│   │   ├── trips.py                    # Trip CRUD operations
│   │   ├── trips_api.py                # Trip API endpoints
│   │   └── accommodations.py           # Hotel & accommodation search
│   ├── src/                            # RAG system (legacy Gemini)
│   │   ├── main.py                     # RAG FastAPI app
│   │   ├── rag.py                      # RAG orchestration
│   │   ├── embedder.py                 # Embedding generation
│   │   ├── retriever.py                # ChromaDB retrieval
│   │   ├── llm.py                      # LLM wrapper (Gemini)
│   │   ├── loader.py                   # JSON data loader
│   │   ├── chunking.py                 # Text chunking strategies
│   │   └── config.py                   # Configuration management
│   ├── utils/                          # Utility functions
│   │   ├── geocoding.py                # Location geocoding helpers
│   │   ├── helpers.py                  # General helper functions
│   │   └── location_extractor.py       # Extract locations from data
│   ├── auth/                           # Firebase authentication
│   │   └── firebase_admin_init.py      # Firebase initialization
│   ├── data/                           # Travel knowledge base (JSON)
│   │   ├── india/ (10 states)
│   │   ├── japan/ (Tokyo, Kyoto, Osaka)
│   │   ├── france/ (Paris, Nice)
│   │   ├── united_states/
│   │   ├── uae/
│   │   ├── thailand/
│   │   ├── singapore/
│   │   ├── spain/
│   │   └── ... (16+ countries)
│   └── chroma_db/                      # ChromaDB persistent storage
│
├── 🎨 Frontend (Vite + Vanilla JS)
│   ├── Land/                           # Main frontend directory
│   │   ├── landingpage.html            # Marketing landing page
│   │   ├── style.css                   # Global styles
│   │   ├── firebase-init.js            # Firebase client config
│   │   ├── Main/                       # Main app container
│   │   │   ├── main.html               # Main app layout
│   │   │   └── script.js               # App initialization
│   │   ├── loginPage/                  # Authentication UI
│   │   │   ├── login.html              # Login/signup page
│   │   │   ├── style.css
│   │   │   └── script.js               # Auth logic
│   │   ├── chat/                       # Conversational interface
│   │   │   ├── chat.html               # Chat UI
│   │   │   ├── style.css               # Chat styling
│   │   │   └── script.js               # Chat logic & API calls
│   │   ├── itinerary/                  # Trip visualization
│   │   │   ├── itinerary.html          # Itinerary display
│   │   │   ├── style.css               # Itinerary styling
│   │   │   └── script.js               # Itinerary logic & booking links
│   │   ├── Map/                        # Map integration
│   │   ├── features/                   # Feature showcase
│   │   ├── about/                      # About section
│   │   ├── js/                         # Shared JavaScript modules
│   │   └── img/                        # Static images
│   ├── vite.config.js                  # Vite configuration
│   ├── package.json                    # NPM dependencies
│   └── index.html                      # Entry point
│
├── 🐳 DevOps & Configuration
│   ├── docker-compose.yml              # Multi-container orchestration
│   ├── Dockerfile                      # Backend container image
│   ├── requirements.txt                # Python dependencies
│   ├── .env                            # Environment variables (gitignored)
│   └── wandermindauth.json             # Firebase service account
│
├── 🧪 Scripts & Utilities
│   ├── check_*.py                      # Diagnostic scripts (DB, workflows, etc.)
│   ├── test_*.py                       # Testing scripts
│   ├── sync_itineraries.py             # Data synchronization
│   ├── verify_*.py                     # Verification utilities
│   └── scripts/
│       ├── ingest_data.py              # Ingest knowledge base into ChromaDB
│       └── query_test.py               # Test RAG queries
│
└── 📚 Documentation
    ├── README.md                       # This file
    ├── PROJECT_DOCUMENTATION.md        # Detailed project docs
    ├── PROJECT_ARCHITECTURE.md         # System architecture
    ├── FIX_N8N_WORKFLOW_GUIDE.md      # N8N integration guide
    └── BOOKING_LINKS_IMPLEMENTATION.md # Booking feature docs
```

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface (Vite)                    │
│  Landing → Login → Chat Interface → Itinerary Display → Maps   │
└────────────────┬────────────────────────────────────────────────┘
                 │ Firebase Auth JWT
                 │ REST API Calls
┌────────────────▼────────────────────────────────────────────────┐
│                    FastAPI Backend (app.py)                      │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │   /message   │    /plan     │  /chats      │   /travel    │ │
│  │ (chat flow)  │ (itinerary)  │ (sessions)   │  (search)    │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
└─────┬────────┬────────┬────────┬────────────────────────────────┘
      │        │        │        │
      │        │        │        └─────► Nominatim API (geocoding)
      │        │        └──────────────► MongoDB (sessions/profiles)
      │        └───────────────────────► ChromaDB (vector search)
      └────────────────────────────────► OpenAI/Gemini (LLM)
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+** (Backend)
- **Node.js 16+** & **npm** (Frontend)
- **MongoDB** instance (local or Atlas)
- **Firebase Project** with Authentication enabled
- **OpenAI API Key** or **Google Gemini API Key**
- **Docker & Docker Compose** (optional, for containerized deployment)

### Installation

#### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yourusername/wandermind-ai.git
cd wandermind-ai
```

#### 2️⃣ Backend Setup

```bash
# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3️⃣ Frontend Setup

```bash
# Install Node dependencies
npm install
```

#### 4️⃣ Environment Configuration

Create a `.env` file in the project root:

```env
# ===== MongoDB Configuration =====
MONGODB_URI=mongodb://localhost:27017/
MONGO_DBNAME=wander_ai

# ===== LLM Configuration (Choose one) =====
# OpenAI (Primary)
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Google Gemini (Alternative)
# GOOGLE_API_KEY=your-google-api-key-here
# GEMINI_MODEL=gemini-2.0-flash

# ===== Firebase Configuration =====
GOOGLE_PROJECT_ID=your-firebase-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=./wandermindauth.json

# ===== ChromaDB Configuration =====
CHROMA_MODE=local
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_URL=http://localhost:8001
CHROMA_PERSISTENT_DIRECTORY=./chroma_db

# ===== External APIs (Optional) =====
AVIATIONSTACK_API_KEY=your-aviationstack-api-key
```

#### 5️⃣ Firebase Configuration

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable **Authentication** → **Email/Password** and **Google** sign-in
3. Download service account JSON from **Project Settings** → **Service Accounts**
4. Save as `wandermindauth.json` in the project root
5. Update `Land/firebase-init.js` with your Firebase client config:

```javascript
// Land/firebase-init.js
const firebaseConfig = {
  apiKey: "your-api-key",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "123456789",
  appId: "your-app-id"
};
```

#### 6️⃣ Initialize ChromaDB Knowledge Base

```bash
# Ingest travel data into ChromaDB vector database
python scripts/ingest_data.py
```

### Running the Application

#### Option A: Development Mode (Separate Servers)

**Terminal 1 - Backend:**
```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 - Frontend:**
```bash
npm run dev
# Starts Vite dev server on http://127.0.0.1:5173
```

**Terminal 3 - ChromaDB (if not using Docker):**
```bash
chroma run --path ./chroma_db --port 8001
```

#### Option B: Docker Compose (Recommended for Production)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

Services:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **ChromaDB**: http://localhost:8001

---

## 📚 API Documentation

### Core Endpoints

#### 🔐 Authentication
All endpoints (except `/health`) require Firebase JWT token in `Authorization` header:
```
Authorization: Bearer <firebase-jwt-token>
```

#### 💬 Chat & Message Flow

**POST `/message`**
```json
{
  "session_id": "uuid-v4",
  "message": "I want to travel to Bali in December",
  "user_id": "firebase-uid"
}
```
Response:
```json
{
  "reply": "Great! Let me help you plan...",
  "action": "ask_questions",
  "profile_updates": {...},
  "session_id": "uuid-v4"
}
```

#### 🗺️ Itinerary Generation

**POST `/plan`**
```json
{
  "user_id": "firebase-uid",
  "session_id": "uuid-v4"
}
```
Response: Complete itinerary with day-by-day activities, locations, dining, budget breakdown.

#### 📋 Session Management

- **GET `/chats`** - List all user chat sessions
- **GET `/chat/{session_id}`** - Get specific chat history
- **POST `/chat/title`** - Generate chat title
- **POST `/chat/update-title`** - Update chat title
- **DELETE `/chat/{session_id}`** - Delete chat session

#### 🎫 Travel Services

**POST `/travel/search`**
```json
{
  "origin": "New Delhi",
  "destination": "Goa",
  "start_date": "2025-12-20",
  "travelers": 2
}
```

**POST `/travel/booking-links`**
```json
{
  "origin": "New Delhi",
  "destination": "Manali",
  "departure_date": "2025-04-15",
  "return_date": "2025-04-20",
  "travelers": 3
}
```
Returns: MakeMyTrip, Booking.com, Goibibo, ClearTrip links

#### 🏨 Accommodations

**POST `/accommodations/search`** - Hotel recommendations via LLM

#### 🧳 Trip Management

- **GET `/api/trips/latest/user`** - Get user's latest trip
- **GET `/api/trips/{trip_id}`** - Get specific trip
- **POST `/trips/itinerary/save`** - Save itinerary to database
- **POST `/trips/sync-itinerary-to-trip`** - Sync session itinerary to trip

### Interactive API Documentation

Visit **http://localhost:8000/docs** for complete Swagger UI documentation with:
- All endpoint schemas
- Request/response examples
- Try-it-out functionality
- Authentication testing

---

## 🗄️ Database Schema

### MongoDB Collections

#### **users**
```javascript
{
  _id: "firebase-uid",
  display_name: "John Doe",
  email: "john@example.com",
  created_at: ISODate("2025-01-01T00:00:00Z"),
  // Travel preferences
  destination: "Bali",
  start_date: "2025-12-20",
  end_date: "2025-12-25",
  budget_in_inr: 150000,
  travelers: 2,
  departure_location: "Hyderabad",
  pace: "relaxed",
  interests: ["beaches", "culture", "food"],
  diet: "vegetarian",
  transport_preference: "flight",
  accommodation_level: "mid-range"
}
```

#### **sessions**
```javascript
{
  _id: "user-id_session-uuid",
  user_id: "firebase-uid",
  session_id: "uuid-v4",
  title: "Trip to Manali",
  created_at: ISODate("2025-04-10T10:30:00Z"),
  updated_at: ISODate("2025-04-10T11:45:00Z"),
  messages: [
    {
      role: "user",
      content: "I want to go to Manali",
      timestamp: ISODate("2025-04-10T10:30:00Z")
    },
    {
      role: "assistant",
      content: "Great! When would you like to travel?",
      timestamp: ISODate("2025-04-10T10:30:05Z")
    }
  ],
  mode: "trip_planning",
  metadata: {...}
}
```

#### **trips**
```javascript
{
  _id: "trip-uuid",
  user_id: "firebase-uid",
  session_id: "session-uuid",
  destination: "Manali",
  start_date: "2025-04-15",
  end_date: "2025-04-20",
  travelers: 3,
  budget_in_inr: 30000,
  itinerary: [
    {
      day: 1,
      date: "2025-04-15",
      activities: [
        {
          time: "10:00 AM",
          activity: "Arrival and Hotel Check-in",
          location: "Mall Road, Manali",
          lat: 32.2444268,
          lon: 77.1895578,
          description: "...",
          estimated_cost: 0
        }
      ]
    }
  ],
  total_estimated_cost: 90000,
  created_at: ISODate("2025-04-10T12:00:00Z")
}
```

#### **itineraries**
```javascript
{
  _id: ObjectId("..."),
  user_id: "firebase-uid",
  session_id: "session-uuid",
  trip_id: "trip-uuid",
  itinerary_data: [...], // Same structure as trips.itinerary
  created_at: ISODate("2025-04-10T12:00:00Z"),
  updated_at: ISODate("2025-04-10T12:00:00Z")
}
```

### ChromaDB Collections

#### **travel_knowledge**
- **Documents**: Chunked POI descriptions from `data/` directory
- **Embeddings**: Generated via OpenAI/Gemini embedding models
- **Metadata**: `{country, city, category, source_file, chunk_index}`

---

## 🧩 Module Deep Dive

### Core Modules

#### `core/llm.py` - LLM Interface
- **Purpose**: Unified interface for OpenAI and Gemini models
- **Functions**:
  - `chat(messages, temperature, max_tokens)` - Synchronous LLM call
  - `chat_async(messages)` - Async LLM call
- **Features**: Timeout handling, retry logic, graceful error messages

#### `core/extract.py` - Data Extraction
- **Purpose**: Parse LLM responses and extract structured data
- **Functions**:
  - `extract_profile(text)` - Extract travel preferences
  - `extract_deltas(text)` - Parse incremental updates
  - `structure_itinerary_data(raw_itinerary)` - Format itinerary JSON

#### `core/prompts.py` - Prompt Engineering
- **System Prompts**:
  - `BASE_SYSTEM_AURA` - Friendly AI travel assistant personality
  - `ASKER_SYSTEM` - Question generation for missing information
  - `ITINERARY_SYSTEM_PROMPT` - Detailed itinerary generation instructions
  - `DATA_STRUCTURING_SYSTEM` - JSON formatting guidelines

#### `db/mongo.py` - Database Operations
- **Connection Management**: MongoDB client initialization
- **CRUD Operations**:
  - Profile management (`get_or_create_profile`, `save_profile`)
  - Session handling (`get_or_create_session`, `append_message`)
  - Trip operations (`save_trip`, `get_itinerary`)
- **Constants**: `REQUIRED_SLOTS`, `TRIP_FIELDS`, `PREFERENCE_FIELDS`

### Route Modules

#### `routes/travel.py` - Travel Search
- **Endpoints**:
  - `POST /travel/search` - Flight/train/bus search
  - `POST /travel/booking-links` - Generate booking URLs
- **Integrations**: N8N workflow (legacy), direct LLM search (active)

#### `routes/booking.py` - Flight & Hotel Booking
- **Endpoints**:
  - `GET /booking/flights` - Aviation Stack API integration
  - `POST /booking/hotels` - LLM-powered hotel suggestions
- **APIs**: Aviationstack for live flight data

#### `routes/trips.py` & `routes/trips_api.py` - Trip Management
- **CRUD Operations**: Create, read, update, delete trips
- **Itinerary Management**: Save, sync, and retrieve itineraries
- **User Trips**: List all trips for a user

### Utility Modules

#### `utils/geocoding.py` - Location Services
- **Functions**:
  - `geocode_location(place_name)` - Nominatim forward geocoding
  - `reverse_geocode(lat, lon)` - Coordinates to city name
  - `is_coordinates(value)` - Detect coordinate patterns
- **API**: OpenStreetMap Nominatim (rate-limited: 1 req/sec)

#### `utils/helpers.py` - Helper Functions
- **Profile Management**:
  - `missing_slots(profile)` - Check incomplete profile fields
  - `merge_soft(profile, updates)` - Non-destructive profile updates
- **Data Parsing**:
  - `parse_destinations(dest_string)` - Extract cities from text
  - `trip_total_days(start, end)` - Calculate trip duration
  - `normalize_transport_preference(value)` - Standardize transport types

#### `utils/location_extractor.py` - Location Extraction
- Extract locations from itinerary for geocoding and mapping

### RAG System (src/)

#### `src/rag.py` - RAG Orchestration
- **Workflow**: Query → Embedding → ChromaDB retrieval → Context + LLM
- **Function**: `generate_answer(question, top_k=5)`

#### `src/embedder.py` - Embedding Generation
- Generate embeddings for queries and documents using Gemini

#### `src/retriever.py` - Vector Search
- ChromaDB persistence and similarity search

#### `src/chunking.py` - Text Chunking
- Semantic chunking for large POI descriptions

---

## 🎨 Frontend Architecture

### Page Components

#### Landing Page (`Land/landingpage.html`)
- Hero section with CTA
- Feature showcase
- About section
- Footer with links

#### Login Page (`Land/loginPage/`)
- Email/password authentication
- Google OAuth integration
- Firebase error handling
- Auto-redirect on successful login

#### Chat Interface (`Land/chat/`)
- **Features**:
  - Message history with timestamps
  - Typing indicators
  - Auto-scroll to latest message
  - Session management (new chat, chat history sidebar)
  - "Generate Itinerary" button
  - "My Journey" button (redirect to latest trip)
- **API Integration**: `/message`, `/chats`, `/chat/{id}`

#### Itinerary Display (`Land/itinerary/`)
- **Features**:
  - Day-by-day timeline view
  - Activity cards with time, location, description
  - Booking links (flights, hotels, buses)
  - Budget breakdown
  - Reverse geocoding for coordinates → city names
  - Responsive design for mobile
- **API Integration**: `/api/trips/{id}`, `/travel/booking-links`

### JavaScript Modules

#### `Land/chat/script.js`
- **Functions**:
  - `sendMessage()` - POST to `/message` endpoint
  - `loadChatHistory()` - Fetch and display messages
  - `createNewChat()` - Initialize new session
  - `loadChatSessions()` - Populate sidebar with user chats
  - `generateItinerary()` - Trigger `/plan` endpoint

#### `Land/itinerary/script.js`
- **Functions**:
  - `fetchTripData(tripId)` - Load trip from API
  - `renderItinerary(trip)` - Display day-by-day schedule
  - `deriveDestination(trip)` - Smart destination extraction
  - `deriveOrigin(trip)` - Reverse geocode departure location
  - `reverseGeocode(lat, lon)` - Nominatim API call
  - `generateBookingLinks()` - Create MakeMyTrip, Booking.com URLs

---

## 🔧 Configuration & Deployment

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_URI` | ✅ | MongoDB connection string |
| `MONGO_DBNAME` | ✅ | Database name (default: `wander_ai`) |
| `OPENAI_API_KEY` | ⚠️* | OpenAI API key (primary LLM) |
| `OPENAI_MODEL` | ⚠️* | Model name (e.g., `gpt-4o-mini`) |
| `GOOGLE_API_KEY` | ⚠️* | Google Gemini API key (alternative LLM) |
| `GEMINI_MODEL` | ⚠️* | Gemini model (e.g., `gemini-2.0-flash`) |
| `GOOGLE_PROJECT_ID` | ✅ | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | ✅ | Path to Firebase service account JSON |

\* Either OpenAI or Gemini credentials required


---

## 🧪 Testing

### Run Backend Tests

```bash
# Test itinerary generation
python test_booking_links.py

# Test Groq/Gemini models
python test_groq_direct.py

# Check database connections
python check_db_structure.py

# Test RAG queries
python scripts/query_test.py

# Verify geocoding
python -c "from utils.geocoding import geocode_location; print(geocode_location('Tokyo'))"
```


## 🗺️ Roadmap

### Current Version (v1.0)
- ✅ Conversational travel planning
- ✅ AI-powered itinerary generation
- ✅ RAG-based recommendations
- ✅ Booking link integration
- ✅ Session management

### Upcoming Features (v1.1)
- 🗓️ **Calendar Integration** (Google Calendar, Outlook)
- 🗺️ **Interactive Maps** (Mapbox, Google Maps)
- 📱 **Mobile App** (React Native)
- 🌐 **Multi-language Support** (i18n)
- 💳 **Payment Integration** (Stripe, Razorpay)

### Future Vision (v2.0)
- 🤖 **Voice Assistant** (speech-to-text, text-to-speech)
- 📊 **Analytics Dashboard** (user insights, popular destinations)
- 🏆 **Gamification** (travel badges, achievements)
- 👥 **Social Features** (share itineraries, collaborative planning)
- 🌤️ **Real-time Weather** integration
- 🚨 **Travel Alerts** (safety, visa requirements)

---

<div align="center">

**Built with ❤️ by the WanderMind AI Team**

[⭐ Star this repo](https://github.com/yourusername/wandermind-ai) | [🐛 Report Bug](https://github.com/yourusername/wandermind-ai/issues) | [✨ Request Feature](https://github.com/yourusername/wandermind-ai/issues)

</div>


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

