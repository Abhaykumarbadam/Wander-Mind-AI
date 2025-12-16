# WanderMind AI - Complete Project Architecture & Workflow

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Technology Stack](#technology-stack)
4. [Backend Architecture](#backend-architecture)
5. [Frontend Architecture](#frontend-architecture)
6. [Database Schema](#database-schema)
7. [Core Workflows](#core-workflows)
8. [API Documentation](#api-documentation)
9. [Authentication Flow](#authentication-flow)
10. [RAG System](#rag-system)
11. [Deployment](#deployment)

---

## 🎯 Project Overview

**WanderMind AI** is an intelligent travel planning assistant that uses Google's Gemini AI to help users plan personalized trips through conversational interactions. The system collects user preferences, generates custom itineraries, and provides travel recommendations using RAG (Retrieval Augmented Generation).

### Key Features
- 🤖 AI-powered conversational trip planning
- 🗺️ Multi-destination itinerary generation
- ✈️ Travel search integration (flights, accommodations)
- 📱 Real-time chat interface
- 🔐 Firebase authentication
- 💾 MongoDB for persistent storage
- 🧠 RAG-based travel recommendations

---

## 🏗️ Architecture Diagram

```
┌───────────────────────────────────────────────────────────────── ┐
│                         FRONTEND (Vite + Vanilla JS)             │
├───────────────────────────────────────────────────────────────── ┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  Landing     │  │  Chat        │  │  Itinerary   │            │
│  │  Page        │  │  Interface   │  │  View        │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│         │                  │                  │                  │
│         └──────────────────┴──────────────────┘                  │
│                            │                                     │
│                   Firebase Auth (JWT)                            │
│                            │                                     │
└────────────────────────────┼─────────────────────────────────────┘
                             │
                    HTTP/REST API
                             │
┌────────────────────────────┼─────────────────────────────────────┐
│                    BACKEND (FastAPI)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      app.py (Main)                       │  │
│  │  - /message (chat endpoint)                              │  │
│  │  - /plan (itinerary generation)                          │  │
│  │  - /rag (travel recommendations)                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                   │
│  ┌────────────┬────────────┼────────────┬──────────────┐       │
│  │            │            │            │              │       │
│  ▼            ▼            ▼            ▼              ▼       │
│ ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────┐           │
│ │Travel│  │Trips │  │Booking│  │Accom │  │Trips API │          │
│ │Routes│  │Routes│  │Routes │  │Routes│  │          │          │
│ └──────┘  └──────┘  └──────┘  └──────┘  └──────────┘           │
│                                                                │
└─────────────────┬───────────────────┬───────────────────────────┘
                  │                   │
         ┌────────┴────────┐  ┌───────┴────────┐
         │                 │  │                │
         ▼                 ▼  ▼                ▼
    ┌─────────┐      ┌──────────┐      ┌──────────┐
    │ MongoDB │      │  Gemini  │      │  ChromaDB│
    │         │      │   AI     │      │   (RAG)  │
    │ Users   │      │          │      │          │
    │ Sessions│      │ LangChain│      │ Vectors  │
    │ Trips   │      └──────────┘      └──────────┘
    └─────────┘
```

---

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.9+)
- **AI/LLM**: Google Gemini 2.0 Flash (via LangChain)
- **Database**: MongoDB
- **Vector DB**: ChromaDB (for RAG)
- **Authentication**: Firebase Admin SDK
- **Key Libraries**:
  - `langchain-google-genai` - LLM integration
  - `pymongo` - MongoDB driver
  - `chromadb` - Vector database
  - `python-dotenv` - Environment management
  - `httpx` - Async HTTP client

### Frontend
- **Build Tool**: Vite 7.2.2
- **Framework**: Vanilla JavaScript (ES6 modules)
- **Authentication**: Firebase Auth (Web SDK 11.0.1)
- **Styling**: Custom CSS with CSS variables
- **Libraries**:
  - Marked.js - Markdown rendering
  - Highlight.js - Code highlighting
  - Leaflet - Map visualization

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Proxy/Gateway**: (Optional) Nginx
- **Environment**: `.env` for configuration

---

## 🔧 Backend Architecture

### Main Application (`app.py`)

The core FastAPI application that orchestrates all services.

#### Key Components:

**1. Initialization**
```python
app = FastAPI(title="Aura Travel — LC + OpenAI + Mongo", version="3.0.0")
# CORS middleware for frontend communication
# Firebase authentication setup
# Router inclusion (travel, trips, booking, etc.)
```

**2. Main Endpoints**

##### `/message` - Conversational Chat
- **Purpose**: Handle user messages and maintain conversation flow
- **Logic**:
  1. Authenticate user via Firebase JWT token
  2. Retrieve/create user profile from MongoDB
  3. Get or create chat session
  4. Use **Aura V2 System Prompt** (single-shot conversation)
  5. Call Gemini AI with conversation history + user profile
  6. Parse JSON response with profile updates and assistant reply
  7. Update user profile in database
  8. Save messages to session history
  9. Return clean text response to frontend

**Workflow**:
```
User Message → Firebase Auth → Get Profile → Build Context
     ↓
Gemini AI (Aura V2 Prompt) → JSON Response
     ↓
{
  "profile_updates": {...},
  "assistant_response": "...",
  "action": "ask|plan|complete"
}
     ↓
Save Profile Updates → Save Messages → Return Response
```

##### `/plan` - Itinerary Generation
- **Purpose**: Generate detailed day-by-day itinerary
- **Logic**:
  1. Validate required fields (destination, dates)
  2. Parse destinations (multi-city support)
  3. Calculate total trip days
  4. Normalize city day split
  5. Build itinerary prompt with all preferences
  6. Call Gemini AI to generate detailed plan
  7. Structure and save itinerary
  8. Return formatted itinerary to frontend

**Workflow**:
```
Plan Request → Validate Profile → Parse Destinations
     ↓
Calculate Days → Split Days per City
     ↓
Build Itinerary Prompt → Gemini AI
     ↓
Generate Detailed Itinerary → Save → Return
```

##### `/rag` - RAG-based Recommendations
- **Purpose**: Retrieve travel information using vector search
- **Logic**:
  1. Generate embedding for user question
  2. Query ChromaDB for similar content
  3. Build context from retrieved chunks
  4. Use Gemini AI to synthesize answer
  5. Return answer with source citations

### Core Modules

#### `core/llm.py` - LLM Interface
```python
# Synchronous chat
chat(messages, temperature, max_tokens) -> str

# Async chat with timeout and retry logic
chat_async(messages, temperature, max_tokens, timeout_sec) -> str
```

**Features**:
- LangChain Google GenAI integration
- Automatic retry on rate limits (3 attempts)
- System message handling for Gemini
- Timeout support for production use

#### `core/prompts.py` - System Prompts

**AURA_V2_SYSTEM**: The main AI personality prompt
- Defines Aura's conversational style
- JSON response structure
- Profile extraction rules
- Question sequencing logic

**ITINERARY_SYSTEM_PROMPT**: Itinerary generation
- Day-by-day planning guidelines
- Activity suggestions
- Timing and logistics
- Budget considerations

#### `core/extract.py` - Data Extraction
```python
extract_profile(text) -> Dict  # Extract user preferences
extract_deltas(text) -> Dict   # Extract profile updates
structure_itinerary_data(text) -> Dict  # Parse itinerary
```

#### `db/mongo.py` - Database Operations

**Collections**:
- `users` - User profiles and preferences
- `sessions` - Chat sessions and messages
- `trips` - Generated itineraries
- `travel_searches` - Flight/hotel searches

**Key Functions**:
```python
# Profile Management
get_or_create_profile(user_id) -> Dict
save_profile(user_id, profile) -> None

# Session Management
get_or_create_session(session_id, user_id) -> str
append_message(session_id, role, content, user_id) -> None
get_recent_messages(session_id, k=10) -> List[Dict]

# Trip Management
save_itinerary(session_id, itinerary) -> None
get_itinerary(session_id) -> Dict
save_trip(user_id, trip_data) -> str

# Chat History
save_chat(user_id, session_id) -> None
get_user_chats(user_id) -> List[Dict]
```

### Routes

#### `routes/travel.py` - Travel Search
- Flight search (commented out - N8N integration)
- Accommodation search
- Transport recommendations
- Fallback mock data for development

#### `routes/trips.py` & `routes/trips_api.py`
- Trip CRUD operations
- Itinerary sync
- Trip listing and filtering
- Session to trip conversion

#### `routes/booking.py`
- Booking link generation
- Affiliate link management
- Flight/hotel booking URLs

---

## 🎨 Frontend Architecture

### Structure
```
Land/
├── landingpage.html          # Home page
├── loginPage/                # Authentication UI
│   ├── login.html
│   └── signup.html
├── Main/                     # Dashboard
│   ├── index.html
│   ├── index.js
│   └── style.css
├── chat/                     # AI Chat Interface
│   ├── index.html
│   ├── script.js
│   └── style.css
├── itinerary/                # Trip view
│   ├── index.html
│   └── script.js
├── Map/                      # Map visualization
└── firebase-init.js          # Firebase config
```

### Chat Interface (`Land/chat/`)

#### `script.js` - Core Logic

**Global State**:
```javascript
let currentUser = null;           // Firebase user
let currentSessionId = null;      // Active chat session
let currentChatId = null;         // Chat ID for history
const API_BASE = "http://localhost:8000";
```

**Key Functions**:

```javascript
// Authentication
onAuthStateChanged(auth, (user) => {
  if (user) {
    loadChatHistory();
    checkURLSession();
  } else {
    redirectToLogin();
  }
});

// Send Message
async function sendMessage(message, sessionId) {
  const token = await getAuthToken();
  const response = await fetch(`${API_BASE}/message`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      user_message: message,
      session_id: sessionId
    })
  });
  return response.json();
}

// Display Message
function displayMessage(role, content) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${role}`;
  messageDiv.innerHTML = formatMarkdown(content);
  chatMessages.appendChild(messageDiv);
  scrollToBottom();
}

// Load Chat History
async function loadChatHistory() {
  const token = await getAuthToken();
  const response = await fetch(`${API_BASE}/chats`, {
    headers: { "Authorization": `Bearer ${token}` }
  });
  const chats = await response.json();
  renderChatHistory(chats);
}

// Start New Chat
async function startNewChat() {
  currentSessionId = null;
  clearChatMessages();
  transitionToChat();
}
```

**Chat Flow**:
```
User Types Message → landingInput/chatInput
     ↓
Click Send → sendMessage(message, sessionId)
     ↓
API Call → /message with Bearer token
     ↓
Response → displayMessage(assistant, response)
     ↓
Update UI → Save to history
```

#### `style.css` - UI Styling

**Key Features**:
- Video background with blur effect
- Collapsible sidebar (hover or click)
- Floating "Chat History" button
- Markdown rendering styles
- Mobile responsive design

**CSS Variables**:
```css
:root {
  --primary-color: #6366f1;
  --text-light: #ffffff;
  --bg-overlay: rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.15);
  --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

**Sidebar Behavior**:
- Default: Hidden (collapsed)
- Hover: Temporarily appears
- Click "Chat History": Toggles open/closed
- Content shifts when sidebar is open (no overlap)

---

## 💾 Database Schema

### MongoDB Collections

#### `users` Collection
```javascript
{
  _id: "firebase_uid",
  profile: {
    display_name: "John Doe",
    destination: "Paris, France",
    start_date: "2025-06-15",
    end_date: "2025-06-22",
    budget_in_inr: 150000,
    travelers: 2,
    pace: "Balanced",
    interests: ["History", "Food", "Art"],
    diet: "Non-Veg",
    transport_preference: "Public Transport",
    accommodation_level: "Hotel",
    departure_location: "Mumbai"
  },
  created_at: "2025-01-15T10:30:00Z",
  updated_at: "2025-01-15T11:45:00Z"
}
```

#### `sessions` Collection
```javascript
{
  _id: "uuid-session-id",
  user_id: "firebase_uid",
  messages: [
    {
      role: "user",
      content: "I want to plan a trip to Paris",
      timestamp: "2025-01-15T10:30:00Z"
    },
    {
      role: "assistant",
      content: "Great choice! When are you planning...",
      timestamp: "2025-01-15T10:30:05Z"
    }
  ],
  mode: "collecting",  // collecting|planning|complete
  metadata: {
    preferences_prompted: false,
    preferences_confirmed: false,
    profile_snapshot: {...},
    confirmed_preferences: []
  },
  created_at: "2025-01-15T10:30:00Z"
}
```

#### `trips` Collection
```javascript
{
  _id: "trip_id",
  user_id: "firebase_uid",
  session_id: "session_id",
  title: "7-Day Paris Adventure",
  destination: "Paris, France",
  start_date: "2025-06-15",
  end_date: "2025-06-22",
  itinerary: {
    days: [
      {
        day: 1,
        date: "2025-06-15",
        activities: [
          {
            time: "09:00",
            title: "Eiffel Tower Visit",
            description: "Start with iconic landmark...",
            location: "Eiffel Tower",
            cost: 1500
          }
        ]
      }
    ]
  },
  budget_breakdown: {...},
  created_at: "2025-01-15T11:45:00Z"
}
```

---

## 🔄 Core Workflows

### 1. User Onboarding & Profile Collection

```mermaid
sequenceDiagram
    User->>Frontend: Visit landing page
    Frontend->>Firebase: Check auth status
    Firebase-->>Frontend: User authenticated
    Frontend->>Backend: POST /message (initial message)
    Backend->>MongoDB: Get/Create profile
    Backend->>Gemini: Aura V2 prompt
    Gemini-->>Backend: JSON response
    Backend->>MongoDB: Save profile updates
    Backend-->>Frontend: Assistant response
    Frontend->>User: Display message
```

**Profile Collection Sequence**:
1. Name → Destination → Dates
2. Interests → Pace → Accommodation
3. Budget → Diet → Transport
4. Departure Location

### 2. Itinerary Generation

```mermaid
sequenceDiagram
    User->>Frontend: Request itinerary
    Frontend->>Backend: POST /plan
    Backend->>MongoDB: Validate profile
    Backend->>Gemini: Generate itinerary
    Gemini-->>Backend: Detailed day plan
    Backend->>MongoDB: Save itinerary
    Backend-->>Frontend: Itinerary JSON
    Frontend->>User: Display itinerary
```

### 3. RAG Query Flow

```mermaid
sequenceDiagram
    User->>Frontend: Ask travel question
    Frontend->>Backend: POST /rag
    Backend->>ChromaDB: Query vectors
    ChromaDB-->>Backend: Relevant chunks
    Backend->>Gemini: Synthesize answer
    Gemini-->>Backend: Answer with context
    Backend-->>Frontend: Response + sources
    Frontend->>User: Display answer
```

---

## 📡 API Documentation

### Authentication
All API endpoints require Firebase JWT token in Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

### Endpoints

#### `POST /message`
**Request**:
```json
{
  "user_message": "I want to visit Japan in April",
  "session_id": "uuid-or-null"
}
```

**Response**:
```json
{
  "type": "ask",
  "session_id": "generated-uuid",
  "response": "Great! Japan in April is cherry blossom season...",
  "assistant_message": "Great! Japan in April is...",
  "action": "ask"
}
```

#### `POST /plan`
**Request**:
```json
{
  "session_id": "uuid",
  "city_day_split": [
    {"city": "Tokyo", "days": 4},
    {"city": "Kyoto", "days": 3}
  ],
  "extra_notes": "Want to see Mt. Fuji"
}
```

**Response**:
```json
{
  "type": "itinerary",
  "session_id": "uuid",
  "itinerary": {
    "days": [...]
  }
}
```

#### `POST /rag`
**Request**:
```json
{
  "question": "Best temples to visit in Kyoto",
  "top_k": 5,
  "mode": "answer"
}
```

**Response**:
```json
{
  "answer": "Based on travel data, the top temples...",
  "sources": ["japan/kyoto/temples.md"],
  "chunks_used": ["chunk_001", "chunk_002"]
}
```

#### `GET /chats`
**Headers**: `Authorization: Bearer <token>`

**Response**:
```json
[
  {
    "session_id": "uuid",
    "title": "Trip to Japan",
    "created_at": "2025-01-15T10:30:00Z",
    "message_count": 15
  }
]
```

---

## 🔐 Authentication Flow

### Firebase Authentication

```javascript
// Frontend: firebase-init.js
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "...",
  authDomain: "...",
  projectId: "wandermind-ai"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

### Token Flow
```
1. User logs in → Firebase Auth
2. Get ID token → auth.currentUser.getIdToken()
3. Send to backend → Authorization: Bearer <token>
4. Backend verifies → firebase_admin.auth.verify_id_token()
5. Extract user_id → decoded['uid']
6. Use for database queries
```

---

## 🧠 RAG System

### Architecture

```
Data Files (data/) → Loader → Chunker → Embedder → ChromaDB
                                                         ↓
User Query → Embedding → Vector Search → Top-K Chunks → LLM → Answer
```

### Components

#### `src/loader.py`
- Reads markdown files from `data/` directory
- Extracts metadata (country, category)
- Returns flattened entries

#### `src/chunking.py`
- Splits text into overlapping chunks
- Default: 1000 chars with 200 overlap
- Preserves context

#### `src/embedder.py`
- Uses Google Generative AI embeddings
- Model: `models/embedding-001`
- Dimension: 768

#### `src/retriever.py`
- ChromaDB integration
- Vector similarity search
- Optional reranking

#### `src/rag.py`
- Orchestrates RAG pipeline
- Ingest: `ingest(data_dir)`
- Query: `generate_answer(question, top_k)`

### Data Structure

```
data/
├── japan/
│   ├── tokyo/
│   │   ├── attractions.md
│   │   └── food.md
│   └── kyoto/
│       └── temples.md
├── france/
└── india/
```

**Metadata Extraction**:
```
data/japan/tokyo/attractions.md
     ↓
country: japan
category: attractions
city: tokyo
```

---

## 🚀 Deployment

### Docker Compose Setup

```yaml
services:
  chroma:
    image: chromadb/chroma:latest
    ports: ["8001:8000"]
    volumes: [chroma-data:/data]
    
  backend:
    build: .
    ports: ["8000:8000"]
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - MONGODB_URI=${MONGODB_URI}
      - FIREBASE_SERVICE_ACCOUNT=./wandermindauth.json
    depends_on: [chroma]
    
  frontend:
    image: nginx:alpine
    ports: ["5173:80"]
    volumes:
      - ./Land:/usr/share/nginx/html
```

### Environment Variables

```bash
# .env file
GOOGLE_API_KEY=your_gemini_api_key
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net
MONGO_DBNAME=wander_ai
GEMINI_MODEL=gemini-2.0-flash
FIREBASE_SERVICE_ACCOUNT=./wandermindauth.json
CHROMA_MODE=server
CHROMA_HOST=chroma
CHROMA_PORT=8000
```

### Running Locally

**Backend**:
```bash
cd WM2
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**:
```bash
npm install
npm run dev
```

**ChromaDB**:
```bash
docker-compose up chroma
```

---

## 🎯 Key Design Decisions

### 1. Single-Shot Aura V2 Prompt
- Simplified from multi-step extraction
- LLM returns JSON with updates + response
- Reduces API calls and latency
- Easier to maintain and debug

### 2. Profile-First Approach
- User profile is central data structure
- All preferences stored in MongoDB
- Session snapshots for tracking changes
- Enables personalization across sessions

### 3. Async/Await for LLM Calls
- Non-blocking I/O for better performance
- Timeout support for reliability
- Retry logic for rate limits
- Scales better under load

### 4. RAG for Travel Knowledge
- ChromaDB for fast vector search
- Country/category metadata filtering
- Source attribution for transparency
- Offline knowledge base (no API limits)

### 5. Firebase for Auth
- Industry-standard security
- Social login support
- JWT token verification
- Easy frontend integration

---

## 📊 Data Flow Summary

```
User Input (Frontend)
    ↓ (Firebase Auth Token)
Backend API (/message)
    ↓ (Get/Update Profile)
MongoDB (users, sessions)
    ↓ (Build Context)
Gemini AI (Aura V2)
    ↓ (JSON Response)
Parse & Save Updates
    ↓ (Return Response)
Frontend Display
    ↓ (User Interaction)
Repeat or Generate Itinerary (/plan)
```

---

## 🔍 Troubleshooting

### Common Issues

**1. Firebase Token Verification Failed**
- Check `wandermindauth.json` exists
- Verify Firebase project ID matches
- Clock skew: Added 10s tolerance

**2. MongoDB Connection Error**
- Verify `MONGODB_URI` in `.env`
- Check network/firewall rules
- MongoDB Atlas: Whitelist IP

**3. Gemini API Rate Limit**
- Retry logic: 3 attempts with backoff
- Consider quota upgrade
- Use async calls with timeout

**4. ChromaDB Not Found**
- Run `docker-compose up chroma`
- Check `CHROMA_HOST` and `CHROMA_PORT`
- Verify network connectivity

---

## 📚 Code Reference

### Important Files to Read

1. **app.py** (Lines 1-900): Main application logic
2. **core/llm.py**: LLM wrapper with retry logic
3. **db/mongo.py**: Database operations
4. **Land/chat/script.js**: Frontend chat logic
5. **src/rag.py**: RAG implementation
6. **core/prompts.py**: System prompts

### Key Constants

```python
# Required profile fields
REQUIRED_SLOTS = [
    "display_name", "destination", "start_date", "end_date",
    "budget_in_inr", "travelers", "pace", "interests", "diet",
    "transport_preference", "accommodation_level", "departure_location"
]

# Session modes
MODES = ["collecting", "planning", "complete"]

# Transport options
SLOT_OPTIONS = {
    "transport_preference": ["Public Transport", "Taxi/Cab", "Rental Car", "Walking"]
}
```

---

## 🎓 Learning Path

To understand this project completely:

1. **Start Here**: `app.py` → `/message` endpoint
2. **Understand Auth**: `get_uid_from_token()` function
3. **Study Prompts**: `core/prompts.py` → `AURA_V2_SYSTEM`
4. **Database Flow**: `db/mongo.py` → profile/session functions
5. **Frontend Integration**: `Land/chat/script.js` → `sendMessage()`
6. **Itinerary Logic**: `app.py` → `/plan` endpoint
7. **RAG System**: `src/rag.py` → `generate_answer()`

---

## 📝 Future Enhancements

- [ ] N8N workflow integration for flight/hotel search
- [ ] Real-time collaboration on trip planning
- [ ] Mobile app (React Native)
- [ ] Payment integration for bookings
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Image generation for destinations
- [ ] Social sharing of itineraries

---

**Last Updated**: December 12, 2025  
**Version**: 3.0.0  
**Maintainer**: WanderMind AI Team
