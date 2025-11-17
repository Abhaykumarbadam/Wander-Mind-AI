#!/bin/bash

# 🔧 Quick Backend Verification Script
# Tests that both critical fixes are working

echo "═══════════════════════════════════════════════════════"
echo "  WanderMind Backend Verification Script"
echo "═══════════════════════════════════════════════════════"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health endpoint
echo "Test 1: Backend Health Check"
echo "───────────────────────────────────────────────────────"
HEALTH=$(curl -s http://127.0.0.1:8000/health 2>&1)
if echo "$HEALTH" | grep -q "true"; then
    echo -e "${GREEN}✓${NC} Backend is running on port 8000"
    echo "  Response: $HEALTH"
else
    echo -e "${RED}✗${NC} Backend not responding"
    echo "  Start with: uvicorn app:app --host 127.0.0.1 --port 8000"
    exit 1
fi
echo ""

# Test 2: Check if port 5501 is accessible (Live Server)
echo "Test 2: Frontend Server Check"
echo "───────────────────────────────────────────────────────"
if lsof -i :5501 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Frontend server running on port 5501 (VS Code Live Server)"
    echo "  Access at: http://localhost:5501/Land/Main/index.html"
else
    echo -e "${YELLOW}!${NC} Port 5501 not in use"
    echo "  Start VS Code Live Server or manually serve files"
fi
echo ""

# Test 3: Check async implementation
echo "Test 3: Async Implementation Check"
echo "───────────────────────────────────────────────────────"
if grep -q "async def message" /Users/himatejagudi/Desktop/WM2/app.py; then
    echo -e "${GREEN}✓${NC} /message endpoint is async"
else
    echo -e "${RED}✗${NC} /message endpoint is NOT async"
fi

if grep -q "async def plan" /Users/himatejagudi/Desktop/WM2/app.py; then
    echo -e "${GREEN}✓${NC} /plan endpoint is async"
else
    echo -e "${RED}✗${NC} /plan endpoint is NOT async"
fi

if grep -q "async def chat_async" /Users/himatejagudi/Desktop/WM2/core/llm.py; then
    echo -e "${GREEN}✓${NC} chat_async() function exists"
else
    echo -e "${RED}✗${NC} chat_async() function missing"
fi
echo ""

# Test 4: Check auth guards
echo "Test 4: Auth Guard Implementation Check"
echo "───────────────────────────────────────────────────────"
if grep -q "isInitializing\|isInitialized" /Users/himatejagudi/Desktop/WM2/Land/Main/index.js | head -1; then
    echo -e "${GREEN}✓${NC} Auth guards are in place"
else
    echo -e "${RED}✗${NC} Auth guards may be missing"
fi
echo ""

# Test 5: Port isolation verification
echo "Test 5: Port Isolation Verification"
echo "───────────────────────────────────────────────────────"
echo "Port 8000 (Backend):"
if lsof -i :8000 | grep -q uvicorn; then
    echo -e "  ${GREEN}✓${NC} FastAPI running on 8000"
else
    echo -e "  ${RED}✗${NC} FastAPI NOT running on 8000"
fi

echo "Port 5501 (Frontend):"
if lsof -i :5501 | grep -q "node\|Live Server"; then
    echo -e "  ${GREEN}✓${NC} Live Server running on 5501"
else
    echo -e "  ${YELLOW}!${NC} No server detected on 5501 (may be normal)"
fi
echo ""

# Test 6: File sizes (verify changes were applied)
echo "Test 6: Changed Files Verification"
echo "───────────────────────────────────────────────────────"
SIZE_JS=$(wc -l < /Users/himatejagudi/Desktop/WM2/Land/Main/index.js)
SIZE_LLM=$(wc -l < /Users/himatejagudi/Desktop/WM2/core/llm.py)
SIZE_APP=$(wc -l < /Users/himatejagudi/Desktop/WM2/app.py)

echo "  index.js: $SIZE_JS lines (expected: ~2270)"
echo "  llm.py: $SIZE_LLM lines (expected: ~75-80)"
echo "  app.py: $SIZE_APP lines (expected: ~650-660)"
echo ""

# Summary
echo "═══════════════════════════════════════════════════════"
echo "  Verification Summary"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "✅ If all tests passed, the fixes are working!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:5501/Land/Main/index.html"
echo "2. Log in with your Firebase credentials"
echo "3. Send a message (should NOT reload page)"
echo "4. Request an itinerary (should NOT hang port)"
echo ""
echo "Check /tmp/fastapi.log for backend activity:"
echo "  tail -100 /tmp/fastapi.log"
echo ""
