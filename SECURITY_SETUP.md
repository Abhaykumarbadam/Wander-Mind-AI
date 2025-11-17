# 🔐 Security Setup Guide

Your WanderMind project contains sensitive credentials that should **NEVER** be committed to GitHub. Follow this guide to secure your project.

## ⚠️ Important: Credentials Already Exposed

Your Firebase credentials are currently visible in the repository. **Before pushing to GitHub:**

1. ✅ Create `.gitignore` to prevent future commits
2. ✅ Set up environment files for credentials
3. ⚠️ Consider these Firebase credentials **compromised** - regenerate them in Firebase Console

## 📋 What's Protected Now

Files now in `.gitignore` (not committed to GitHub):
- `.env` - All API keys, MongoDB credentials, Chroma API key
- `firebase-init.js` - Firebase API key and project credentials
- `wandermindauth.json` - Firebase service account
- `__pycache__/`, `node_modules/`, etc.

## 🔑 Setting Up Firebase Credentials

### Step 1: Create Your Local Firebase Config

```bash
# Copy the example file
cp Land/firebase-init.example.js Land/firebase-init.js

# Edit it with your credentials
nano Land/firebase-init.js
```

### Step 2: Get Your Firebase Credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project: `wandermindai-6d60f`
3. Click ⚙️ Settings → Project settings
4. Under "Your apps" section, click your web app
5. Copy the config object:

```javascript
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "wandermindai-6d60f.firebaseapp.com",
  projectId: "wandermindai-6d60f",
  storageBucket: "wandermindai-6d60f.firebasestorage.app",
  messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
  appId: "1:YOUR_APP_ID:web:YOUR_WEB_ID",
  measurementId: "G_YOUR_MEASUREMENT_ID"
};
```

### Step 3: Update `.env` File

```bash
# Copy the example
cp .env.example .env

# Edit with your actual credentials
nano .env
```

Fill in:
- `GOOGLE_API_KEY` - From Google Cloud Console
- `MONGODB_URI` - From MongoDB Atlas
- `CHROMA_API_KEY` - From your Chroma setup
- `APP_SECRET_KEY` - Keep it secure (or generate new)

## 🛡️ Environment Variables Your App Uses

### Frontend (JavaScript)
- ✅ **`firebase-init.js`** - Loaded from `Land/firebase-init.js`
  - File is in `.gitignore` ✓
  - Contains Firebase config
  - Only on developer machines

### Backend (Python)
- ✅ **`.env`** - Loaded by Python app
  - File is in `.gitignore` ✓
  - Contains all secrets
  - Only on developer machines

## ✅ How Authentication Still Works

1. **Frontend:** Loads `firebase-init.js` from local file system
   - ✅ File NOT committed to git
   - ✅ Browser has access to it
   - ✅ Works seamlessly

2. **Backend:** Reads `.env` file
   - ✅ File NOT committed to git
   - ✅ Python app loads it with `python-dotenv`
   - ✅ All endpoints work

3. **Firebase Auth Flow:**
   ```
   Frontend (firebase-init.js) → Firebase Auth → Google OAuth
   Backend (.env FIREBASE_SERVICE_ACCOUNT) → Firebase Admin SDK
   ```
   Both sources use credentials from `.env` and `firebase-init.js`

## 🔄 Deploying to Production

### Option 1: Vercel/Netlify (Frontend)

Set environment variables in deployment dashboard:
```
VITE_FIREBASE_API_KEY=xxx
VITE_FIREBASE_AUTH_DOMAIN=xxx
VITE_FIREBASE_PROJECT_ID=xxx
```

### Option 2: Heroku/Railway (Backend)

Set environment variables:
```
GOOGLE_API_KEY=xxx
MONGODB_URI=xxx
CHROMA_API_KEY=xxx
FIREBASE_SERVICE_ACCOUNT=/app/wandermindauth.json
```

### Option 3: Docker

```bash
# .env goes in container at runtime
docker build -t wandermind .
docker run -e GOOGLE_API_KEY="xxx" -e MONGODB_URI="xxx" wandermind
```

## 🚨 If Credentials Were Exposed to GitHub

**Immediate Actions:**

1. **Regenerate Firebase API Key:**
   - Firebase Console → Settings → Web apps
   - Delete old app, create new one
   - Update local `firebase-init.js`

2. **Regenerate MongoDB Password:**
   - MongoDB Atlas → Database Access
   - Reset password for `himatejagudi2_db_user`

3. **Regenerate Google API Key:**
   - Google Cloud Console → APIs & Services → Credentials
   - Delete old key, create new one

4. **Regenerate Chroma API Key:**
   - Update in `.env`

5. **Clear Git History (if needed):**
   ```bash
   # Remove file from git history
   git filter-branch --tree-filter 'rm -f Land/firebase-init.js' HEAD
   git filter-branch --tree-filter 'rm -f .env' HEAD
   ```

## ✨ Checklist Before Pushing to GitHub

- [ ] `.gitignore` exists and contains:
  - [ ] `.env`
  - [ ] `firebase-init.js`
  - [ ] `wandermindauth.json`
- [ ] `Land/firebase-init.js` is NOT staged for commit
- [ ] `.env` file is NOT staged for commit
- [ ] `Land/firebase-init.example.js` exists for documentation
- [ ] `.env.example` exists with placeholder values
- [ ] Run `git status` to verify no secrets are staged

## 📝 Contributing Guidelines

For new developers joining the project:

1. Clone repository
2. Create local `firebase-init.js`:
   ```bash
   cp Land/firebase-init.example.js Land/firebase-init.js
   ```
3. Create local `.env`:
   ```bash
   cp .env.example .env
   ```
4. Ask project lead for actual credential values
5. Fill in `.env` and `firebase-init.js`
6. Never commit these files

## 🔗 Useful Commands

```bash
# Verify nothing sensitive is staged
git status

# Check if credentials are in recent commits
git log --all --oneline -- ".env" "firebase-init.js"

# Remove file from staging (if accidentally added)
git rm --cached .env
git rm --cached Land/firebase-init.js

# See what's in .gitignore
cat .gitignore

# Verify .gitignore is working
git check-ignore -v .env firebase-init.js
```

## 📚 More Info

- [Firebase Security Best Practices](https://firebase.google.com/docs/projects/api/firebase-ml-security)
- [Git .gitignore Documentation](https://git-scm.com/docs/gitignore)
- [Environment Variables in Python](https://pypi.org/project/python-dotenv/)
- [Securing JavaScript in Browsers](https://owasp.org/www-community/Sensitive_Data_Exposure)

---

**Status:** ✅ Your project is now configured to keep credentials safe!
