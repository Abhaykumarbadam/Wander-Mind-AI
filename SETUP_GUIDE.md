# 🚀 Quick Setup for Developers

## Prerequisites
- Python 3.8+
- Node.js 14+ (for frontend)
- Git

## Setup (5 minutes)

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/wandermind.git
cd wandermind
```

### 2. Set up environment variables
```bash
# Copy the template
cp .env.example .env

# Edit with your actual credentials
# Required: GOOGLE_API_KEY, MONGODB_URI, CHROMA_API_KEY, etc.
nano .env
```

### 3. Set up Firebase configuration
```bash
# Copy the template
cp Land/firebase-init.example.js Land/firebase-init.js

# Edit with your Firebase credentials
nano Land/firebase-init.js
```

You'll need:
- `apiKey`: From Firebase Console
- `authDomain`: Your Firebase domain
- `projectId`: Your Firebase project ID
- `storageBucket`, `messagingSenderId`, `appId`: From Firebase Console

See [SECURITY_SETUP.md](./SECURITY_SETUP.md) for detailed instructions.

### 4. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the backend
```bash
# Start Chroma database (if using server mode)
chroma run --host 0.0.0.0 --port 8001 &

# Or use Docker Compose for production
docker-compose up -d

# Start FastAPI backend
python3 app.py
```

The backend will be available at `http://localhost:8000`

### 6. Open the frontend
- Open `Land/landingpage.html` in your browser, or
- Use VS Code Live Server: right-click `landingpage.html` → "Open with Live Server"
- Frontend will be at `http://127.0.0.1:5501` (or similar)

## 🔐 Security Notes

**IMPORTANT:** Never commit your credentials!

- `.env` - Contains all API keys (in `.gitignore`)
- `Land/firebase-init.js` - Contains Firebase config (in `.gitignore`)
- `wandermindauth.json` - Contains Firebase service account (in `.gitignore`)

See [SECURITY_SETUP.md](./SECURITY_SETUP.md) for more information.

## 📚 Documentation

- [SECURITY_SETUP.md](./SECURITY_SETUP.md) - Complete security guide
- [SECURITY_SUMMARY.md](./SECURITY_SUMMARY.md) - Quick reference
- [CHROMA_MIGRATION_GUIDE.md](./CHROMA_MIGRATION_GUIDE.md) - Database setup
- [CHAT_UI_TESTING_GUIDE.md](./CHAT_UI_TESTING_GUIDE.md) - Testing guide

## ✅ Verification

Once everything is set up:

```bash
# Test backend
curl http://localhost:8000/health

# Test Chroma (if running)
curl http://localhost:8001/api/v1/heartbeat

# Test frontend
# Open in browser and try logging in
```

All should work! ✨
