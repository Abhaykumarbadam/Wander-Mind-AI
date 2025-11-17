# Chat UI Testing Guide

## Pre-Testing Setup

### 1. Start the Backend
```bash
cd /Users/himatejagudi/Desktop/WM2
python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Expected output:
```
INFO:     Started server process [XXXXX]
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 2. Open in Browser
```
http://127.0.0.1:8000/Land/Main/index.html
```

**Note:** You must be logged in via Firebase auth first. If redirected to login, authenticate and return.

### 3. Open Developer Console
```
Chrome/Edge: F12 or Cmd+Opt+I
Firefox: F12 or Cmd+Opt+I
Safari: Cmd+Opt+I (must enable in preferences)
```

Watch for any errors or warnings during testing.

---

## Test Cases

### Test 1: UI Renders Correctly ✅

**Steps:**
1. Load page at http://127.0.0.1:8000/Land/Main/index.html
2. Wait 2 seconds for full load

**Expected Results:**
- [ ] Navbar visible with logo and nav items
- [ ] Social and Journal tabs are GONE (removed)
- [ ] Chat section visible with:
  - [ ] Chat header with "AI Travel Concierge" title
  - [ ] Profile chip showing user name/emoji
  - [ ] "Edit Details" button
  - [ ] "New Chat" button with gradient
- [ ] Chat sidebar on left side with "Chat History" header
- [ ] Sidebar toggle button (≡) visible
- [ ] Chat messages container visible (white background)
- [ ] Text input at bottom with "Ask your AI travel assistant..." placeholder
- [ ] Send button (➤) to right of input
- [ ] Input hint text below input: "Press Enter to send, Shift+Enter for new line"
- [ ] No console errors (check F12)

**Browser Console Check:**
```javascript
// Paste in console and verify no errors
[
  document.getElementById("chatSidebar"),
  document.getElementById("chatMessages"),
  document.getElementById("chatInput"),
  document.getElementById("sendBtn"),
  document.getElementById("newChatBtn")
].every(el => el !== null) // Should print: true
```

---

### Test 2: Profile Chip Displays User Info ✅

**Steps:**
1. Check the profile chip in chat header
2. Look at the avatar emoji and name

**Expected Results:**
- [ ] Avatar shows user's initial or emoji (e.g., "H", "😊")
- [ ] Name displays (e.g., "Himmatej", "User", or email prefix)
- [ ] Profile chip has gradient background
- [ ] "Edit Details" button is visible and clickable
- [ ] Hovering over button shows color change

**Optional - In Console:**
```javascript
console.log({
  avatar: document.getElementById("profileInitial").textContent,
  name: document.getElementById("profileName").textContent
});
```

---

### Test 3: New Chat Button Creates Fresh Conversation ✅

**Steps:**
1. Click "New Chat" button
2. Observe the changes

**Expected Results:**
- [ ] Chat messages clear
- [ ] Welcome message appears: "Hello! I'm Aura, your personal travel concierge..."
- [ ] Chat input becomes focused (blue border)
- [ ] New session created in sidebar
- [ ] Current chat marked as active in sidebar
- [ ] No console errors

**Verify in Console:**
```javascript
// Check current chat ID changed
console.log("Current Chat ID:", localStorage.getItem("aura_current_chat_id"));
// Check chat history cleared/reset
console.log("Chat History:", JSON.parse(localStorage.getItem("aura_chat_history")));
```

---

### Test 4: Sidebar Session List Works ✅

**Steps:**
1. Complete at least 3 separate conversations (can be short)
2. Each time: type message, click send
3. Click "New Chat" button to start fresh
4. Observe sidebar updates

**Expected Results:**
- [ ] After first chat: sidebar shows 1 session
- [ ] After second chat: sidebar shows 2 sessions
- [ ] After third chat: sidebar shows 3 sessions
- [ ] Each session shows:
  - [ ] Title (first user message, truncated)
  - [ ] Timestamp (date and time)
- [ ] Sessions sorted by newest first
- [ ] Current session is highlighted/active
- [ ] Clicking past session loads it
- [ ] Messages from that session reappear

**Verify localStorage:**
```javascript
// Should show array of sessions
console.log(JSON.parse(localStorage.getItem("aura_chat_sessions")));
```

**Example Output:**
```javascript
[
  {
    id: "chat_1731871234567",
    title: "Tell me about Paris",
    lastMessage: "Paris is a beautiful city...",
    timestamp: 1731871234567,
    messageCount: 2
  },
  {
    id: "chat_1731871200000",
    title: "Suggest a 5-day Italy trip",
    lastMessage: "I'd love to help with your Italy trip!",
    timestamp: 1731871200000,
    messageCount: 4
  }
]
```

---

### Test 5: Sidebar Toggle/Collapse ✅

**Steps:**
1. Click the toggle button (≡) in sidebar header
2. Observe sidebar behavior

**Expected Results:**
- [ ] Sidebar slides out smoothly (0.3s animation)
- [ ] Sidebar width becomes 0
- [ ] Chat area expands to fill space
- [ ] Toggle button remains visible (transforms)
- [ ] Click toggle again to expand sidebar
- [ ] Sidebar slides back in smoothly
- [ ] State persists on page refresh

**Verify Persistence:**
```javascript
// Before reload - toggle sidebar
// Refresh page (Cmd+R or F5)
// After reload - sidebar should be in same state
console.log("Sidebar collapsed:", localStorage.getItem("aura_sidebar_collapsed"));
```

---

### Test 6: Chat Input and Message Sending ✅

**Steps:**
1. Click chat input
2. Type: "Tell me about the Eiffel Tower"
3. Press Enter

**Expected Results:**
- [ ] Input gains blue focus border
- [ ] Text appears in textarea as you type
- [ ] Pressing Enter sends message (doesn't create newline)
- [ ] User message appears on right with purple gradient
- [ ] Input clears after send
- [ ] Send button shows loading spinner (⏳)
- [ ] Typing indicator appears (⊙ ⊙ ⊙)
- [ ] Assistant response appears after ~2-3 seconds
- [ ] Messages auto-scroll to bottom
- [ ] No console errors

**In Console During Send:**
```javascript
// Message should be added to history
console.log("Chat history length:", JSON.parse(localStorage.getItem("aura_chat_history")).length);
```

---

### Test 7: Multi-line Input (Shift+Enter) ✅

**Steps:**
1. Click chat input
2. Type: "Line 1"
3. Press Shift+Enter
4. Type: "Line 2"
5. Press Enter to send

**Expected Results:**
- [ ] Shift+Enter creates newline in textarea
- [ ] Text shows as two lines in input
- [ ] Textarea auto-resizes if needed (max 120px)
- [ ] Enter (without Shift) sends the whole message
- [ ] Message displays with proper formatting:
  ```
  Line 1
  Line 2
  ```
- [ ] No console errors

---

### Test 8: Textarea Auto-Resize ✅

**Steps:**
1. Click chat input
2. Type multiple lines (10+ lines of text)
3. Watch the textarea height

**Expected Results:**
- [ ] Textarea grows as you type (smooth animation)
- [ ] Max height is ~120px (not taller)
- [ ] Scrollbar appears when at max height
- [ ] When text is deleted, textarea shrinks back
- [ ] Min height is ~44px (comfortable to click)

**Expected Behavior:**
```
Initial: 44px
After 3 lines: ~60px
After 6 lines: ~90px
After 10 lines: ~120px (max, scrollbar appears)
```

---

### Test 9: Message Formatting and Markdown ✅

**Steps:**
1. Send message: "Testing **bold** and *italic*"
2. Send message: "# Header\n## Subheader\n- List item 1\n- List item 2"
3. Send message: "> This is a quote"
4. Send message: "Use `backticks` for inline code"

**Expected Results:**
- [ ] Bold text (**text**) appears in strong/bold
- [ ] Italic text (*text*) appears slanted
- [ ] Headers (# ## ###) render with proper sizing and hierarchy
- [ ] List items (- or •) appear as bullet points
- [ ] Blockquotes (> text) have left border and italic styling
- [ ] Inline code (`code`) has gray background
- [ ] All formatting is left-aligned assistant messages
- [ ] No HTML tags visible (properly rendered)

---

### Test 10: Message Animation ✅

**Steps:**
1. Send a message
2. Watch the message appear

**Expected Results:**
- [ ] Message fades in smoothly (0.32s)
- [ ] Message slides up slightly as it fades in
- [ ] Multiple messages have staggered animations
- [ ] Animations are smooth (no jank/stuttering)
- [ ] Once visible, messages stay visible (no flashing)

---

### Test 11: Data Persistence on Refresh ✅

**Steps:**
1. Send 2-3 messages in a conversation
2. Press F5 or Cmd+R to refresh
3. Wait for page to load

**Expected Results:**
- [ ] Same chat session loads (not new chat)
- [ ] All previous messages reappear in same order
- [ ] Session still marked as active in sidebar
- [ ] Can continue conversation where left off
- [ ] Profile chip still shows user info
- [ ] Chat input is focused and ready

**Verify in Console (Before Refresh):**
```javascript
const history = JSON.parse(localStorage.getItem("aura_chat_history"));
const chatId = localStorage.getItem("aura_current_chat_id");
console.log("Messages before refresh:", history.length);
console.log("Chat ID:", chatId);

// Store these values
window.preRefreshState = { historyCount: history.length, chatId };
```

**Verify in Console (After Refresh):**
```javascript
const history = JSON.parse(localStorage.getItem("aura_chat_history"));
const chatId = localStorage.getItem("aura_current_chat_id");
console.log("Messages after refresh:", history.length);
console.log("Chat ID:", chatId);
console.log("Same chat ID?", chatId === window.preRefreshState?.chatId);
console.log("Same message count?", history.length === window.preRefreshState?.historyCount);
```

---

### Test 12: Switch Between Sessions ✅

**Steps:**
1. Complete conversation A: "Plan a 3-day trip to Paris" (2-3 messages)
2. Click "New Chat"
3. Complete conversation B: "Suggest restaurants in Tokyo" (2-3 messages)
4. In sidebar, click on Session A (first conversation)
5. Observe

**Expected Results:**
- [ ] Paris messages reappear
- [ ] Tokyo messages disappear
- [ ] Session A is highlighted in sidebar
- [ ] Can send new messages to Session A
- [ ] Click Session B again - Tokyo messages return
- [ ] Both sessions maintain independent histories
- [ ] Titles accurately reflect content

---

### Test 13: Social and Journal Removed ✅

**Steps:**
1. Look at navbar
2. Scroll down through all sections
3. Open browser DevTools (F12)

**Expected Results:**
- [ ] "Social" link is NOT in navbar
- [ ] "Journal" link is NOT in navbar
- [ ] No #social section exists in DOM
- [ ] No #journal section exists in DOM
- [ ] No console errors about missing elements
- [ ] No network requests to /social or /journal endpoints

**Verify in Console:**
```javascript
// Should return null
console.log("Social section:", document.getElementById("social"));
console.log("Journal section:", document.getElementById("journal"));

// Check navbar items
const navItems = document.querySelectorAll(".nav-item span");
const navTexts = Array.from(navItems).map(el => el.textContent);
console.log("Nav items:", navTexts);
// Should NOT contain "Social" or "Journal"
```

---

### Test 14: Responsive Design (Mobile) ✅

**Steps:**
1. Open DevTools (F12)
2. Toggle device toolbar (Cmd+Shift+M on Mac, Ctrl+Shift+M on Windows)
3. Select iPhone 12 or similar (390px width)
4. Test all functionality

**Expected Results:**
- [ ] Sidebar collapses by default
- [ ] Chat messages are full-width and readable
- [ ] Input is full-width and usable
- [ ] Buttons are large enough to tap
- [ ] Profile chip displays properly
- [ ] Messages still animate and scroll
- [ ] Can toggle sidebar on/off
- [ ] Click to expand sidebar works
- [ ] No horizontal scrolling needed
- [ ] Text is readable at default zoom

**Test on Different Sizes:**
- [ ] 390px (iPhone 12)
- [ ] 768px (iPad)
- [ ] 1024px (Desktop/Tablet hybrid)
- [ ] 1440px (Large desktop)

---

### Test 15: Browser Compatibility ✅

**Test in Each Browser:**

**Chrome/Chromium:**
- [ ] All features work
- [ ] Animations are smooth
- [ ] localStorage persists
- [ ] No console errors

**Firefox:**
- [ ] All features work
- [ ] CSS backdrop-filter works (glassmorphism visible)
- [ ] Animations smooth
- [ ] localStorage persists

**Safari:**
- [ ] All features work
- [ ] Glassmorphism visible
- [ ] Textarea input works properly
- [ ] localStorage persists

**Edge:**
- [ ] All features work
- [ ] Same as Chrome (Chromium-based)
- [ ] Animations smooth

---

### Test 16: Error Handling ✅

**Steps:**
1. Disconnect internet (or use DevTools to disable network)
2. Try to send a message
3. Observe error handling

**Expected Results:**
- [ ] Send button shows loading spinner
- [ ] After timeout (~5s), shows error message
- [ ] Error message is user-friendly (not technical)
- [ ] Can still interact with UI
- [ ] Can retry sending
- [ ] localStorage still works offline

**With Network Restored:**
- [ ] Retry works and message sends
- [ ] Normal conversation resumes
- [ ] No data loss

---

### Test 17: Performance Check ✅

**Steps:**
1. Open DevTools Performance tab
2. Send 20+ messages in a conversation
3. Record performance trace
4. Check for hangs or slowdowns

**Expected Results:**
- [ ] Page remains responsive with 20+ messages
- [ ] Smooth scrolling in messages area
- [ ] Message animations don't stutter
- [ ] No frame drops (should maintain 60fps)
- [ ] CPU usage moderate
- [ ] No memory leaks (check memory in DevTools)

**Specific Checks:**
```javascript
// Check message count limit
const history = JSON.parse(localStorage.getItem("aura_chat_history"));
console.log("Total messages:", history.length);
console.log("Should be <= 100 (performance limit)");

// Check sessions count
const sessions = JSON.parse(localStorage.getItem("aura_chat_sessions"));
console.log("Total sessions:", sessions.length);
console.log("Should be <= 50 (to limit sidebar size)");
```

---

### Test 18: Accessibility Check ✅

**Steps:**
1. Tab through UI using keyboard
2. Navigate with arrow keys
3. Use screen reader (Mac: Voice Over, Windows: NVDA/Narrator)

**Expected Results:**
- [ ] All buttons are keyboard accessible
- [ ] Tab order is logical (top to bottom, left to right)
- [ ] Focus indicators visible (blue outline)
- [ ] Can send message with keyboard only:
  - Tab to input
  - Type message
  - Tab to send button
  - Press Enter
- [ ] Chat messages announced by screen reader
- [ ] Button labels clear and descriptive
- [ ] No unlabeled icons

---

## Regression Testing

### Verify Existing Features Still Work

- [ ] Chat messages still send to `/message` endpoint
- [ ] RAG integration still works (messages include KB context)
- [ ] Itinerary generation (`/plan`) still works
- [ ] Profile management still works
- [ ] Firebase auth still redirects non-logged users
- [ ] Logout button works
- [ ] All other sections (Dashboard, Itinerary, Maps, etc.) still work

---

## Test Results Template

```
Date: _______________
Tester: _______________
Browser: _______________
OS: _______________

Test 1 - UI Renders Correctly: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 2 - Profile Chip: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 3 - New Chat Button: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 4 - Sidebar Sessions: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 5 - Sidebar Toggle: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 6 - Chat Input & Send: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 7 - Multi-line Input: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 8 - Textarea Resize: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 9 - Message Formatting: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 10 - Message Animation: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 11 - Data Persistence: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 12 - Session Switching: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 13 - Social/Journal Removed: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 14 - Responsive Design: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 15 - Browser Compatibility: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 16 - Error Handling: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 17 - Performance: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

Test 18 - Accessibility: [ ] PASS [ ] FAIL [ ] PARTIAL
  Issues: _____________________________________

OVERALL RESULT: [ ] PASS [ ] FAIL

Notes: ________________________________________
       ________________________________________
```

---

## Troubleshooting

### Issue: Messages not saving to localStorage
**Solution:** Check browser privacy settings. InCognito/Private mode disables localStorage.

### Issue: Sidebar sessions not showing
**Solution:** 
1. Complete at least one full message (user + assistant response)
2. Check console: `console.log(JSON.parse(localStorage.getItem("aura_chat_sessions")))`
3. Verify session has `id`, `title`, `timestamp`

### Issue: Backend connection errors
**Solution:**
1. Verify backend running: `curl http://127.0.0.1:8000/health`
2. Check network tab in DevTools
3. Ensure you're authenticated (not on login page)

### Issue: Markdown not rendering
**Solution:**
1. Check browser console for marked.js/highlight.js errors
2. Verify CDN links are accessible
3. Try in different browser

### Issue: Animations are stuttering
**Solution:**
1. Close other tabs/apps
2. Clear browser cache (Cmd+Shift+Delete)
3. Try in Incognito mode
4. Check GPU acceleration in browser settings

### Issue: Textarea stuck/not resizing
**Solution:**
1. Refresh page
2. Clear localStorage: `localStorage.clear()`
3. Test in different browser
4. Check for JS errors in console

---

## Success Criteria

✅ **All Tests Pass:**
- [ ] UI renders correctly with all new elements
- [ ] Session persistence works (survives refresh)
- [ ] Sidebar displays sessions and allows switching
- [ ] Messages format with markdown
- [ ] Input handles multi-line text
- [ ] Social/Journal fully removed
- [ ] Responsive on all device sizes
- [ ] No console errors
- [ ] Performance is smooth (60fps)
- [ ] Accessible via keyboard

**Result:** Ready for production deployment! 🚀
