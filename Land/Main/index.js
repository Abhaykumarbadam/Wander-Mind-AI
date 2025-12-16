// =============================
// ✨ WanderMind AI - Enhanced Chat System
// =============================

import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";
import { auth } from "../firebase-init.js";

// =============================
// AUTHENTICATION & INITIALIZATION
// =============================

// Prevent multiple initializations
let isInitializing = false;
let isInitialized = false;

// Watchdog to detect hangs
let watchdogTimer = null;
function startWatchdog() {
  if (watchdogTimer) clearInterval(watchdogTimer);
  watchdogTimer = setInterval(() => {
    if (isInitializing && !isInitialized) {
      const elapsed = Date.now() - (window.initStartTime || Date.now());
      if (elapsed > 15000) { // 15 seconds
        console.error("WATCHDOG: Initialization taking too long, forcing completion");
        isInitializing = false;
        isInitialized = true;
        clearInterval(watchdogTimer);
        alert("Page initialization is taking too long. Some features may not work. Please refresh if issues persist.");
      }
    }
  }, 1000);
}

// Auth gate: if not signed in, bounce to login
// Add timeout to prevent hangs
let initTimeout = null;
let appInitTimeout = null;

onAuthStateChanged(auth, (user) => {
  // Clear any existing timeouts
  if (initTimeout) clearTimeout(initTimeout);
  if (appInitTimeout) clearTimeout(appInitTimeout);

  if (!user) {
    // Don't redirect during initialization or if already on login page
    if (!isInitialized && window.location.href.includes("loginPage")) {
      return; // Already on login page, don't redirect again
    }
    if (isInitializing) {
      return; // Don't redirect while initializing
    }
    // Only redirect if we're on a different page
    if (!window.location.href.includes("loginPage")) {
      window.location.href = "/Land/loginPage/login.html";
    }
    return;
  }

  // Prevent duplicate initialization
  if (isInitializing || isInitialized) {
    console.log("Already initialized, skipping...");
    return;
  }

  localStorage.setItem("firebase_uid", user.uid);

  // Initialize app after auth confirmed (only once)
  isInitializing = true;
  window.initStartTime = Date.now();
  startWatchdog();

  // Add timeout to prevent hanging (8 seconds - more aggressive)
  appInitTimeout = setTimeout(() => {
    if (isInitializing) {
      console.error("App initialization timed out!");
      isInitializing = false;
      isInitialized = true; // Force completion
      if (watchdogTimer) clearInterval(watchdogTimer);
      alert("Page is taking too long to load. Some features may not work. Please refresh.");
    }
  }, 8000);

  // Use requestIdleCallback if available, otherwise setTimeout
  const initFn = () => {
    initApp().then(() => {
      if (appInitTimeout) clearTimeout(appInitTimeout);
      if (watchdogTimer) clearInterval(watchdogTimer);
      isInitialized = true;
      isInitializing = false;
    }).catch((err) => {
      if (appInitTimeout) clearTimeout(appInitTimeout);
      if (watchdogTimer) clearInterval(watchdogTimer);
      console.error("Error initializing app:", err);
      isInitializing = false;
      isInitialized = true; // Mark as done even on error
      // Show error but don't crash
      alert("Error loading page. Some features may not work. Please refresh.");
    });
  };

  if (window.requestIdleCallback) {
    requestIdleCallback(initFn, { timeout: 1000 });
  } else {
    setTimeout(initFn, 100);
  }
});

// Fallback timeout: if auth state doesn't fire within 5 seconds, try to initialize anyway
initTimeout = setTimeout(() => {
  if (!isInitialized && !isInitializing && auth.currentUser) {
    console.warn("Auth state change timeout - forcing initialization");
    isInitializing = true;
    initApp().then(() => {
      isInitialized = true;
      isInitializing = false;
    }).catch((err) => {
      console.error("Error in timeout init:", err);
      isInitializing = false;
    });
  }
}, 5000);

// =============================
// STATE MANAGEMENT
// =============================

// Persistent chat session and message history
const storedSessionId = localStorage.getItem("aura_session_id");
let sessionId = storedSessionId && storedSessionId !== "null" ? storedSessionId : null;
let chatHistory = readJSONFromStorage("aura_chat_history", []);
let chatSessions = readJSONFromStorage("aura_chat_sessions", []);
let currentChatId = localStorage.getItem("aura_current_chat_id") || null;
let isSending = false;
function cloneFallback(value) {
  if (Array.isArray(value)) return [...value];
  if (value && typeof value === "object") return { ...value };
  return value;
}

function readJSONFromStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return cloneFallback(fallback);
    return JSON.parse(raw);
  } catch (err) {
    console.warn(`Invalid JSON for ${key}. Clearing corrupted value.`, err);
    localStorage.removeItem(key);
    return cloneFallback(fallback);
  }
}

// =============================
// DOM ELEMENTS
// =============================

const chatMessagesEl = document.getElementById("chatMessages");
const chatInputEl = document.getElementById("chatInput");
const sendBtnEl = document.getElementById("sendBtn");
const sendIconEl = sendBtnEl?.querySelector(".send-icon");
const sendSpinnerEl = sendBtnEl?.querySelector(".send-spinner");
const profileNameEl = document.getElementById("profileName");
const profileInitialEl = document.getElementById("profileInitial");
const editPreferencesBtn = document.getElementById("editPreferencesBtn");
const profileChipEl = document.getElementById("profileChip");

const DAY_ICON_SET = ["✈️", "🌅", "⛱️", "🍽️", "🏙️", "🚶", "🏞️", "🎉", "🛥️", "🕌"];
let latestItineraryRaw = "";
let latestItineraryHtml = "";
let latestItineraryMeta = { cities: [], startDate: null, endDate: null };
let latestTransportData = { flights: [], trains: [], buses: [], hotels: [] };
let copyToastEl = null;

// Sidebar toggle state
let sidebarCollapsed = localStorage.getItem("aura_sidebar_collapsed") === "true";

// =============================
// HELPER FUNCTIONS
// =============================

/**
 * Initialize sidebar collapsed state from localStorage
 */
function initSidebarState() {
  const sidebar = document.getElementById("chatSidebar");
  if (sidebar && sidebarCollapsed) {
    sidebar.classList.add("collapsed");
  }
}

/**
 * Get fresh Firebase ID token for API calls
 */
async function getIdToken() {
  const u = auth.currentUser;
  if (!u) {
    console.error("Not signed in - redirecting to login");
    window.location.href = "/Land/loginPage/login.html";
    throw new Error("Not signed in");
  }
  try {
    const token = await u.getIdToken(true);
    return token;
  } catch (err) {
    console.error("Error getting ID token:", err);
    // Force refresh of token
    try {
      const freshToken = await u.getIdToken(true);
      return freshToken;
    } catch (retryErr) {
      console.error("Failed to refresh token:", retryErr);
      window.location.href = "/Land/loginPage/login.html";
      throw new Error("Token refresh failed");
    }
  }
}

/**
 * Load dashboard statistics from backend with error handling
 */
async function loadDashboardStats() {
  const statTripsEl = document.getElementById("statTrips");
  const statDaysEl = document.getElementById("statDays");
  const statUpcomingEl = document.getElementById("statUpcoming");

  try {
    // Show loading state
    if (statTripsEl) statTripsEl.textContent = "...";
    if (statDaysEl) statDaysEl.textContent = "...";
    if (statUpcomingEl) statUpcomingEl.textContent = "...";

    const token = await getIdToken();

    // Fetch actual stats from new endpoint
    const statsResponse = await fetch(`${API_BASE_URL}/dashboard/stats`, {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!statsResponse.ok) {
      throw new Error(`Stats API returned ${statsResponse.status}`);
    }

    const stats = await statsResponse.json();
    const totalTrips = stats.total_trips || 0;
    const totalDays = stats.total_days || 0;
    const upcoming = stats.upcoming || 0;

    // Update UI with actual values
    if (statTripsEl) statTripsEl.textContent = totalTrips;
    if (statDaysEl) statDaysEl.textContent = totalDays;
    if (statUpcomingEl) statUpcomingEl.textContent = upcoming;

    console.log('✅ Dashboard stats loaded:', { totalTrips, totalDays, upcoming });
  } catch (err) {
    console.error("Error loading dashboard stats:", err);

    // Show error state
    if (statTripsEl) statTripsEl.textContent = "0";
    if (statDaysEl) statDaysEl.textContent = "0";
    if (statUpcomingEl) statUpcomingEl.textContent = "0";
  }
}

/**
 * Save chat history to localStorage for persistence
 */
function saveChatHistory() {
  localStorage.setItem("aura_chat_history", JSON.stringify(chatHistory));
  if (sessionId) {
    localStorage.setItem("aura_session_id", sessionId);
  }
  if (currentChatId) {
    localStorage.setItem("aura_current_chat_id", currentChatId);
  }
}

/**
 * Update or create chat session
 */
function updateChatSession() {
  if (!currentChatId) {
    currentChatId = `chat_${Date.now()}`;
    chatSessions.push({
      id: currentChatId,
      title: chatHistory.length > 0 ? chatHistory[0].content.substring(0, 50) : "New Chat",
      lastMessage: chatHistory[chatHistory.length - 1]?.content?.substring(0, 100) || "",
      timestamp: Date.now(),
      messageCount: chatHistory.length
    });
  } else {
    const session = chatSessions.find(s => s.id === currentChatId);
    if (session) {
      session.lastMessage = chatHistory[chatHistory.length - 1]?.content?.substring(0, 100) || "";
      session.timestamp = Date.now();
      session.messageCount = chatHistory.length;
      if (chatHistory.length > 0 && !session.title) {
        session.title = chatHistory[0].content.substring(0, 50);
      }
    }
  }
  localStorage.setItem("aura_chat_sessions", JSON.stringify(chatSessions));
  renderChatList();
}

/**
 * Reset itinerary view to placeholder state
 */
function resetItineraryView() {
  const loadingEl = document.getElementById("itineraryLoading");
  const placeholderEl = document.getElementById("itineraryPlaceholder");
  const contentEl = document.getElementById("itineraryContent");
  if (loadingEl) loadingEl.style.display = "none";
  if (placeholderEl) placeholderEl.style.display = "block";
  if (contentEl) {
    contentEl.style.display = "none";
    contentEl.innerHTML = "";
  }
  latestItineraryRaw = "";
  latestItineraryHtml = "";
  latestItineraryMeta = { cities: [], startDate: null, endDate: null };
}

/**
 * Make backend request to start a fresh trip session
 */
async function requestTripReset(options = {}) {
  const { resetPreferences = false } = options || {};
  try {
    const token = await getIdToken();
    const response = await fetch("http://127.0.0.1:8000/new_trip", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ reset_preferences: resetPreferences })
    });
    if (!response.ok) {
      const txt = await response.text().catch(() => "Unable to reset trip");
      throw new Error(txt || "Unable to reset trip profile");
    }
    const raw = await response.text();
    if (!raw) return {};
    try {
      return JSON.parse(raw);
    } catch (parseErr) {
      console.warn("Unexpected response while resetting trip:", parseErr);
      return {};
    }
  } catch (err) {
    console.warn("Trip reset request failed:", err);
    throw err;
  }
}

/**
 * Start a new chat conversation
 */
async function startNewChat(options = {}) {
  const { resetPreferences = false, assistantIntro = null } = options || {};

  // Save current chat if it has messages (defer to prevent blocking)
  if (chatHistory.length > 0) {
    setTimeout(() => updateChatSession(), 50);
  }

  try {
    await requestTripReset({ resetPreferences });
  } catch (err) {
    if (resetPreferences) {
      showToast("Couldn't refresh your profile. Try again in a moment.");
    } else {
      console.warn("Continuing without backend reset due to error.");
    }
  }

  // Reset for new chat
  sessionId = null;
  chatHistory = [];
  currentChatId = `chat_${Date.now()}`;

  // Clear UI
  if (chatMessagesEl) {
    chatMessagesEl.innerHTML = "";
  }

  resetItineraryView();

  const defaultIntro = "Hello! I'm Aura, your personal travel concierge. Tell me about your next adventure and I'll craft the perfect plan. ✈️";
  addMessageToUI("assistant", assistantIntro || defaultIntro);

  // Save state (defer to prevent blocking)
  setTimeout(() => {
    saveChatHistory();
    updateChatSession();
  }, 100);
}

/**
 * Load a chat session
 */
function loadChatSession(chatId) {
  // Save current chat first
  if (chatHistory.length > 0) {
    updateChatSession();
  }

  // Find and load the session
  const session = chatSessions.find(s => s.id === chatId);
  if (!session) return;

  currentChatId = chatId;

  // Load chat history from backend if sessionId exists
  // For now, we'll load from localStorage
  // TODO: Load from backend using session ID

  // Clear and reload UI
  if (chatMessagesEl) {
    chatMessagesEl.innerHTML = "";
  }

  // Reload messages (this would come from backend in production)
  // For now, show placeholder
  addMessageToUI("assistant", "Loading chat history...");

  saveChatHistory();
  renderChatList();
}

/**
 * Render chat list in sidebar - optimized to prevent hangs
 */
function renderChatList() {
  const chatListEl = document.getElementById("chatList");
  if (!chatListEl) return;

  try {
    // Limit sessions to prevent DOM overload
    const sorted = [...chatSessions].sort((a, b) => b.timestamp - a.timestamp).slice(0, 20);

    if (sorted.length === 0) {
      chatListEl.innerHTML = '<div class="chat-list-empty">No previous chats</div>';
      return;
    }

    // Use document fragment for better performance
    const fragment = document.createDocumentFragment();

    sorted.forEach(session => {
      const item = document.createElement("div");
      item.className = `chat-list-item ${session.id === currentChatId ? "active" : ""}`;
      item.onclick = () => loadChatSession(session.id);

      const date = new Date(session.timestamp);
      item.innerHTML = `
        <div class="chat-list-item-title">${session.title || "New Chat"}</div>
        <div class="chat-list-item-date">${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
      `;

      fragment.appendChild(item);
    });

    chatListEl.innerHTML = "";
    chatListEl.appendChild(fragment);
  } catch (err) {
    console.error("Error rendering chat list:", err);
    chatListEl.innerHTML = '<div class="chat-list-empty">Error loading chats</div>';
  }
}

/**
 * Scroll chat container to bottom smoothly
 */
function scrollChatToBottom() {
  const container = document.getElementById("chatMessagesContainer");
  if (container) {
    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth"
    });
  }
}

function ensureToastElement() {
  if (!copyToastEl) {
    copyToastEl = document.createElement("div");
    copyToastEl.className = "copy-success-toast";
    document.body.appendChild(copyToastEl);
  }
}

function showToast(message) {
  if (!message) return;
  ensureToastElement();
  if (!copyToastEl) return;
  copyToastEl.textContent = message;
  copyToastEl.classList.add("show");
  clearTimeout(copyToastEl._hideTimer);
  copyToastEl._hideTimer = setTimeout(() => {
    copyToastEl?.classList.remove("show");
  }, 2200);
}

function setupProfileChipDetails() {
  try {
    const user = auth.currentUser;
    let name = user?.displayName || user?.email?.split("@")[0] || "Traveler";
    if (typeof name === "string") {
      name = name.trim() || "Traveler";
    } else {
      name = "Traveler";
    }
    if (profileNameEl) profileNameEl.textContent = name;
    if (profileInitialEl) profileInitialEl.textContent = (name.charAt(0) || "T").toUpperCase();
    if (profileChipEl) profileChipEl.setAttribute("title", `Signed in as ${name}`);
  } catch (err) {
    console.warn("Error preparing profile chip:", err);
  }

  if (editPreferencesBtn && !editPreferencesBtn.dataset.bound) {
    editPreferencesBtn.dataset.bound = "true";
    editPreferencesBtn.addEventListener("click", async () => {
      if (editPreferencesBtn.disabled) return;
      const originalLabel = editPreferencesBtn.textContent;
      editPreferencesBtn.disabled = true;
      editPreferencesBtn.textContent = "Refreshing...";
      try {
        await startNewChat({
          resetPreferences: true,
          assistantIntro: "Let's refresh your travel preferences from the ground up. Tell me what you're imagining for this new trip!"
        });
        showToast("Preferences reset—share your updated trip details!");
      } catch (err) {
        console.error("Error resetting preferences:", err);
        showToast("Couldn't refresh preferences. Try again.");
      } finally {
        editPreferencesBtn.textContent = originalLabel;
        editPreferencesBtn.disabled = false;
      }
    });
  }

  // Setup sidebar toggle
  const toggleSidebarBtn = document.getElementById("toggleSidebar");
  if (toggleSidebarBtn && !toggleSidebarBtn.dataset.bound) {
    toggleSidebarBtn.dataset.bound = "true";
    toggleSidebarBtn.addEventListener("click", () => {
      const sidebar = document.getElementById("chatSidebar");
      if (sidebar) {
        sidebarCollapsed = !sidebarCollapsed;
        sidebar.classList.toggle("collapsed", sidebarCollapsed);
        localStorage.setItem("aura_sidebar_collapsed", sidebarCollapsed);
      }
    });
  }

  // Setup new chat button
  const newChatBtn = document.getElementById("newChatBtn");
  if (newChatBtn && !newChatBtn.dataset.bound) {
    newChatBtn.dataset.bound = "true";
    newChatBtn.addEventListener("click", async () => {
      await startNewChat();
    });
  }
  // Setup AI Chat Nav button
  const navChatBtn = document.getElementById("navChatBtn");
  if (navChatBtn && !navChatBtn.dataset.bound) {
    navChatBtn.dataset.bound = "true";
    navChatBtn.addEventListener("click", (e) => {
      e.preventDefault();
      // Check if we have an active session
      if (sessionId) {
        // Resume existing session
        window.location.href = `../chat/index.html?session_id=${sessionId}`;
      } else {
        // Start new session
        window.location.href = "../chat/index.html";
      }
    });
  }

  // Setup Itinerary Nav button (redirects to chat interface)
  const navItineraryBtn = document.getElementById("navItineraryBtn");
  if (navItineraryBtn && !navItineraryBtn.dataset.bound) {
    navItineraryBtn.dataset.bound = "true";
    navItineraryBtn.addEventListener("click", (e) => {
      e.preventDefault();
      // Check if we have an active session
      if (sessionId) {
        // Resume existing session
        window.location.href = `../chat/index.html?session_id=${sessionId}`;
      } else {
        // Start new session
        window.location.href = "../chat/index.html";
      }
    });
  }
}

/**
 * Convert markdown to HTML while preserving structure
 */
function formatMarkdown(text) {
  if (!text) return "";

  try {
    // Ensure text is a string
    if (typeof text !== 'string') {
      text = String(text || "");
    }

    // Escape HTML first
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Convert markdown to HTML with error handling
    try {
      // Headers
      html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
      html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
      html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

      // Bold
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

      // Lists - handle bullet points
      html = html.replace(/^[\s]*[•\-\*]\s+(.+)$/gm, '<li>$1</li>');
      // Wrap consecutive list items in ul
      html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

      // Code blocks
      html = html.replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>');
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

      // Blockquotes
      html = html.replace(/^>\s+(.+)$/gm, '<blockquote>$1</blockquote>');

      // Paragraphs (double line breaks)
      html = html.replace(/\n\n/g, '</p><p>');
      html = '<p>' + html + '</p>';

      // Clean up empty paragraphs
      html = html.replace(/<p><\/p>/g, '');
      html = html.replace(/<p>(<[^>]+>)/g, '$1');
      html = html.replace(/(<\/[^>]+>)<\/p>/g, '$1');

      // Preserve single line breaks
      html = html.replace(/\n/g, '<br>');
    } catch (markdownError) {
      console.warn("Error in markdown conversion:", markdownError);
      // Fallback: just escape and preserve line breaks
      html = html.replace(/\n/g, '<br>');
    }

    return html;
  } catch (err) {
    console.error("Error in formatMarkdown:", err);
    // Return safe fallback
    return String(text || "").replace(/\n/g, '<br>');
  }
}

/**
 * Add message to chat UI with smooth animation and markdown formatting
 * Optimized to prevent hangs
 */
function addMessageToUI(role, content, isTyping = false) {
  if (!chatMessagesEl) return;

  const messageEl = document.createElement("div");
  messageEl.className = `chat-message ${role}${isTyping ? " typing" : ""}`;

  if (isTyping) {
    messageEl.innerHTML = `
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    `;
  } else {
    // Format markdown for assistant messages, plain text for user
    // Use requestAnimationFrame to defer heavy markdown processing
    if (role === "assistant") {
      // Defer markdown formatting to prevent blocking
      requestAnimationFrame(() => {
        try {
          messageEl.innerHTML = formatMarkdown(content);
        } catch (err) {
          console.error("Error formatting markdown:", err);
          messageEl.textContent = content; // Fallback to plain text
        }
      });
      // Show plain text immediately, then update with formatted version
      messageEl.textContent = content;
    } else {
      messageEl.textContent = content;
    }
  }

  chatMessagesEl.appendChild(messageEl);

  // Auto-scroll to bottom after message is added (defer to prevent blocking)
  requestAnimationFrame(() => {
    scrollChatToBottom();
  });

  // Store in history (only non-typing messages)
  if (!isTyping) {
    chatHistory.push({ role, content, timestamp: Date.now() });

    // Limit history size to prevent memory issues
    if (chatHistory.length > 100) {
      chatHistory = chatHistory.slice(-100); // Keep only last 100 messages
    }

    // Defer saving to prevent blocking
    setTimeout(() => {
      saveChatHistory();
      updateChatSession();
    }, 50);
  }

  return messageEl;
}

/**
 * Update existing message (for replacing typing indicator)
 */
function updateMessage(messageEl, content) {
  if (!messageEl) return;
  messageEl.classList.remove("typing");
  messageEl.innerHTML = "";
  messageEl.textContent = content;
  scrollChatToBottom();
}

/**
 * Remove typing indicator
 */
function removeTypingIndicator() {
  const typingEl = chatMessagesEl?.querySelector(".chat-message.typing");
  if (typingEl) {
    typingEl.remove();
  }
  // Ensure scroll after removing typing indicator
  setTimeout(() => scrollChatToBottom(), 50);
}

/**
 * Set send button loading state
 */
function setSendButtonLoading(loading) {
  if (!sendBtnEl || !sendIconEl || !sendSpinnerEl) return;
  isSending = loading;
  sendBtnEl.disabled = loading;
  if (loading) {
    sendIconEl.style.display = "none";
    sendSpinnerEl.style.display = "block";
  } else {
    sendIconEl.style.display = "block";
    sendSpinnerEl.style.display = "none";
  }
}

// =============================
// CHAT API INTEGRATION
// =============================

/**
 * Send message to Aura backend with full conversation history
 */
async function sendToAura(userMessage) {
  if (isSending) return;

  // ALWAYS redirect to chat interface from Main dashboard
  // Store the message + session context and redirect to dedicated chat page
  sessionStorage.setItem("pendingMessage", userMessage);
  sessionStorage.setItem(
    "pendingSessionId",
    sessionId || localStorage.getItem("aura_session_id") || ""
  );
  window.location.href = "../chat/index.html";
  return;

  // Add user message to UI immediately
  addMessageToUI("user", userMessage);

  // Show typing indicator
  const typingEl = addMessageToUI("assistant", "", true);

  setSendButtonLoading(true);

  try {
    const token = await getIdToken();

    // Build payload with session and message
    const payload = {
      user_message: userMessage,
      session_id: sessionId || null
    };

    // Call backend API
    const response = await fetch("http://127.0.0.1:8000/message", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error: ${response.status} - ${errorText}`);
    }

    const data = await response.json();

    // Update session ID if provided
    if (!sessionId && data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem("aura_session_id", sessionId);
    }

    // Handle different response types
    if (data.type === "ready_for_plan") {
      // User wants itinerary - auto-trigger plan generation
      removeTypingIndicator();
      addMessageToUI("assistant", data.message || "Creating your itinerary...");
      await generateItinerary();
      return;
    }

    // Get assistant response
    const assistantMessage = data.assistant_message || data.message || "I'm here to help!";

    // Replace typing indicator with actual response
    removeTypingIndicator();
    addMessageToUI("assistant", assistantMessage);

  } catch (err) {
    console.error("Aura API error:", err);
    removeTypingIndicator();
    addMessageToUI("assistant", `Error: ${err.message}. Make sure the backend is running on http://127.0.0.1:8000`);
  } finally {
    setSendButtonLoading(false);
  }
}

/**
 * Generate itinerary by calling /plan endpoint
 */
async function generateItinerary() {
  if (!sessionId) {
    console.error("No session ID available");
    addMessageToUI("assistant", "I need to start a conversation first. Please send me a message about your trip!");
    return;
  }

  try {
    const token = await getIdToken();

    // Show loading in itinerary section
    const loadingEl = document.getElementById("itineraryLoading");
    const placeholderEl = document.getElementById("itineraryPlaceholder");
    const contentEl = document.getElementById("itineraryContent");

    if (loadingEl) loadingEl.style.display = "block";
    if (placeholderEl) placeholderEl.style.display = "none";
    if (contentEl) {
      contentEl.style.display = "none";
      contentEl.innerHTML = ""; // Clear previous content
    }

    // Scroll to itinerary section
    try {
      const itinerarySection = document.getElementById("itinerary");
      if (itinerarySection) {
        itinerarySection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (scrollError) {
      console.warn("Error scrolling to itinerary:", scrollError);
    }

    // Call /plan endpoint
    const response = await fetch("http://127.0.0.1:8000/plan", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        session_id: sessionId,
        extra_notes: ""
      })
    });

    if (!response.ok) {
      let errorText = "Unknown error";
      try {
        errorText = await response.text();
      } catch (e) {
        console.warn("Could not read error response:", e);
      }
      throw new Error(`Plan generation error: ${response.status} - ${errorText}`);
    }

    let data;
    try {
      data = await response.json();
    } catch (jsonError) {
      console.error("Error parsing JSON response:", jsonError);
      throw new Error("Invalid response from server. Please try again.");
    }

    if (data.type === "itinerary" && data.itinerary) {
      // Display the itinerary with error handling
      try {
        displayItinerary(
          data.itinerary || "",
          data.cities || [],
          data.start_date || null,
          data.end_date || null
        );
      } catch (displayError) {
        console.error("Error displaying itinerary:", displayError);
        addMessageToUI("assistant", "I generated your itinerary, but there was an error displaying it. Please check the Itinerary section or try refreshing the page.");
      }
    } else if (data.type === "ask_split") {
      // Need city split - show message
      addMessageToUI("assistant", data.assistant_message || "I need to know how many days you want to spend in each city.");
    } else {
      // Unknown response type
      console.warn("Unknown response type:", data);
      addMessageToUI("assistant", "I received an unexpected response. Please try generating the itinerary again.");
    }

  } catch (err) {
    console.error("Itinerary generation error:", err);
    const errorMessage = err.message || "An unknown error occurred";
    addMessageToUI("assistant", `Error generating itinerary: ${errorMessage}. Please make sure the backend is running and try again.`);

    // Show error in itinerary section too
    const contentEl = document.getElementById("itineraryContent");
    if (contentEl) {
      contentEl.innerHTML = `
        <div class="itinerary-header">
          <div class="itinerary-title">Error</div>
        </div>
        <details class="itinerary-day-card" open>
          <summary class="itinerary-day-summary">
            <span class="day-icon">⚠️</span>
            <div class="day-title">
              <span class="day-title-main">Unable to generate itinerary</span>
              <span class="day-title-meta">Please try again or contact support</span>
            </div>
            <span class="itinerary-day-toggle">⌄</span>
          </summary>
          <div class="itinerary-day-content">
            <div class="itinerary-time-block">
              <div class="itinerary-activity-detail">
                <strong>Error:</strong> ${errorMessage}
                <br><br>
                Please try again or contact support if the issue persists.
              </div>
            </div>
          </div>
        </details>
      `;
      contentEl.style.display = "block";
    }
  } finally {
    // Always hide loading indicator
    try {
      const loadingEl = document.getElementById("itineraryLoading");
      if (loadingEl) loadingEl.style.display = "none";
    } catch (e) {
      console.warn("Error hiding loading indicator:", e);
    }
  }
}

/**
 * Display formatted itinerary in the UI - optimized to prevent hangs
 */
function displayItinerary(itineraryText, cities, startDate, endDate) {
  const placeholderEl = document.getElementById("itineraryPlaceholder");
  const contentEl = document.getElementById("itineraryContent");
  if (!contentEl) {
    console.error("Itinerary content element not found");
    return;
  }

  try {
    if (placeholderEl) placeholderEl.style.display = "none";
    contentEl.style.display = "block";
    contentEl.innerHTML = '<div class="itinerary-header"><div class="itinerary-title">Loading itinerary...</div></div>';

    const render = () => {
      try {
        const maxLength = 50000;
        const textToFormat = itineraryText && itineraryText.length > maxLength
          ? itineraryText.substring(0, maxLength) + "\n\n[... content truncated for performance ...]"
          : itineraryText || "";

        let formatted = "";
        try {
          formatted = formatItineraryText(textToFormat, cities || [], startDate, endDate);
        } catch (formatError) {
          console.error("Error formatting itinerary:", formatError);
          formatted = `
            <div class="itinerary-header">
              <div class="itinerary-title">Your Travel Plan</div>
              <div class="itinerary-meta">
                ${cities && cities.length ? `<div class="itinerary-meta-item"><strong>📍 Cities:</strong> ${cities.join(", ")}</div>` : ""}
                ${startDate ? `<div class="itinerary-meta-item"><strong>📅 Start:</strong> ${new Date(startDate).toLocaleDateString()}</div>` : ""}
                ${endDate ? `<div class="itinerary-meta-item"><strong>📅 End:</strong> ${new Date(endDate).toLocaleDateString()}</div>` : ""}
              </div>
            </div>
            <details class="itinerary-day-card" open>
              <summary class="itinerary-day-summary">
                <span class="day-icon">🧭</span>
                <div class="day-title">
                  <span class="day-title-main">Your Itinerary</span>
                  <span class="day-title-meta">Detailed plan overview</span>
                </div>
                <span class="itinerary-day-toggle">⌄</span>
              </summary>
              <div class="itinerary-day-content">
                <div class="itinerary-time-block">
                  <div class="itinerary-activity">
                    ${(itineraryText || "No itinerary content available.").replace(/\n/g, "<br>")}
                  </div>
                </div>
              </div>
            </details>
          `;
        }

        latestItineraryRaw = itineraryText || "";
        latestItineraryHtml = formatted;
        latestItineraryMeta = {
          cities: Array.isArray(cities) ? cities : [],
          startDate: startDate || null,
          endDate: endDate || null
        };

        contentEl.innerHTML = "";
        const controls = document.createElement("div");
        controls.className = "itinerary-controls";
        controls.innerHTML = `
          <button type="button" class="itinerary-control-btn" id="copyItineraryBtn">📋 Copy Plan</button>
          <button type="button" class="itinerary-control-btn" id="downloadItineraryBtn">⬇️ Download PDF</button>
        `;
        contentEl.appendChild(controls);
        contentEl.insertAdjacentHTML("beforeend", formatted);

        const copyBtn = contentEl.querySelector("#copyItineraryBtn");
        const downloadBtn = contentEl.querySelector("#downloadItineraryBtn");
        copyBtn?.addEventListener("click", handleCopyItinerary);
        downloadBtn?.addEventListener("click", handleDownloadItinerary);

        // Automatically fetch transport and stay options when itinerary is displayed
        const itineraryData = {
          destination: cities && cities.length > 0 ? cities[0] : null,
          departure_location: 'HYD', // Default, could be extracted from profile
          start_date: startDate,
          travelers: 1,
          cities: cities
        };
        
        console.log('🎯 Itinerary displayed, triggering transport search with:', itineraryData);
        
        if (itineraryData.destination && itineraryData.start_date) {
          // Trigger transport search automatically with slight delay to ensure DOM is ready
          setTimeout(() => {
            displayTransportOptions(itineraryData).catch(err => {
              console.error('❌ Failed to auto-fetch transport options:', err);
            });
          }, 500);
        } else {
          console.warn('⚠️ Missing destination or start_date for transport search:', itineraryData);
        }

        requestAnimationFrame(() => {
          const itinerarySection = document.getElementById("itinerary");
          itinerarySection?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      } catch (err) {
        console.error("Error rendering itinerary:", err);
        contentEl.innerHTML = `
          <div class="itinerary-header">
            <div class="itinerary-title">Error Loading Itinerary</div>
          </div>
          <details class="itinerary-day-card" open>
            <summary class="itinerary-day-summary">
              <span class="day-icon">⚠️</span>
              <div class="day-title">
                <span class="day-title-main">Unable to show itinerary</span>
                <span class="day-title-meta">Please regenerate or refresh</span>
              </div>
              <span class="itinerary-day-toggle">⌄</span>
            </summary>
            <div class="itinerary-day-content">
              <div class="itinerary-time-block">
                <div class="itinerary-activity-detail">
                  There was an error displaying your itinerary. Please try again.
                </div>
              </div>
            </div>
          </details>
        `;
      }
    };

    if (window.requestIdleCallback) {
      requestIdleCallback(render, { timeout: 2000 });
    } else {
      setTimeout(render, 80);
    }
  } catch (err) {
    console.error("Error displaying itinerary:", err);
    contentEl.innerHTML = `
      <div class="itinerary-header">
        <div class="itinerary-title">Error Loading Itinerary</div>
      </div>
      <details class="itinerary-day-card" open>
        <summary class="itinerary-day-summary">
          <span class="day-icon">⚠️</span>
          <div class="day-title">
            <span class="day-title-main">Something went wrong</span>
            <span class="day-title-meta">Try generating again</span>
          </div>
          <span class="itinerary-day-toggle">⌄</span>
        </summary>
        <div class="itinerary-day-content">
          <div class="itinerary-time-block">
            <div class="itinerary-activity-detail">
              ${err.message || "Unknown error"}
            </div>
          </div>
        </div>
      </details>
    `;
    contentEl.style.display = "block";
    if (placeholderEl) placeholderEl.style.display = "none";
  }
}

async function handleCopyItinerary() {
  if (!latestItineraryRaw) {
    showToast("Generate an itinerary first.");
    return;
  }
  try {
    await navigator.clipboard.writeText(latestItineraryRaw.trim());
    showToast("Itinerary copied to clipboard!");
  } catch (err) {
    console.warn("Clipboard copy failed:", err);
    showToast("Copy failed. Try manually copying.");
  }
}

// Helper functions for generating booking URLs in PDF
function generateFlightBookingURL(flight, itineraryMeta) {
  const origin = flight.departure_airport?.match(/\(([A-Z]{3})\)/)?.[1] || 'HYD';
  const dest = flight.arrival_airport?.match(/\(([A-Z]{3})\)/)?.[1] || 'DPS';
  const startDate = itineraryMeta.start_date || new Date().toISOString().split('T')[0];
  const endDate = itineraryMeta.end_date || new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0];
  const adults = itineraryMeta.travelers || 2;
  
  const formatMMTDate = (dateStr) => {
    const d = new Date(dateStr);
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
  };
  
  const itinerary = `${origin}-${dest}-${formatMMTDate(startDate)}_${dest}-${origin}-${formatMMTDate(endDate)}`;
  return `https://www.makemytrip.com/flight/search?itinerary=${itinerary}&tripType=R&paxType=A-${adults}_C-0_I-0&intl=true&cabinClass=E&lang=eng`;
}

function generateHotelBookingURL(itineraryMeta) {
  const destination = encodeURIComponent(itineraryMeta.cities?.[0] || 'Destination');
  const checkIn = itineraryMeta.start_date || new Date().toISOString().split('T')[0];
  const checkOut = itineraryMeta.end_date || new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0];
  const adults = itineraryMeta.travelers || 2;
  return `https://www.booking.com/searchresults.html?ss=${destination}&checkin=${checkIn}&checkout=${checkOut}&group_adults=${adults}&no_rooms=1&selected_currency=INR`;
}

function generateTrainBookingURL(itineraryMeta) {
  const origin = encodeURIComponent(itineraryMeta.departure_location || 'Hyderabad');
  const destination = encodeURIComponent(itineraryMeta.cities?.[0] || 'Destination');
  return `https://www.irctc.co.in/nget/train-search`;
}

function generateBusBookingURL(itineraryMeta) {
  const origin = encodeURIComponent(itineraryMeta.departure_location || 'Hyderabad');
  const destination = encodeURIComponent(itineraryMeta.cities?.[0] || 'Destination');
  return `https://www.redbus.in/bus-tickets/${origin}-to-${destination}`;
}

function handleDownloadItinerary() {
  if (!latestItineraryHtml) {
    showToast("Generate an itinerary first.");
    return;
  }
  const printableHtml = latestItineraryHtml.replace(/<details/g, "<details open");
  const title = latestItineraryMeta.cities && latestItineraryMeta.cities.length
    ? `WanderMind Itinerary – ${latestItineraryMeta.cities.join(" • ")}`
    : "WanderMind Travel Itinerary";

  // Generate transport and stay sections for PDF
  let transportSection = '';
  let staySection = '';

  // Check if we have transport data
  const hasTransport = latestTransportData.flights.length > 0 || 
                       latestTransportData.trains.length > 0 || 
                       latestTransportData.buses.length > 0;
  
  if (hasTransport) {
    transportSection = `
      <div class="pdf-section">
        <h2 class="pdf-section-title">🚀 Transport Options</h2>
        <div class="pdf-options-grid">
    `;

    // Add flights
    if (latestTransportData.flights.length > 0) {
      latestTransportData.flights.slice(0, 4).forEach((flight, idx) => {
        // Generate booking URL if not present
        const bookingUrl = flight.booking_link || generateFlightBookingURL(flight, latestItineraryMeta);
        
        transportSection += `
          <div class="pdf-option-card">
            <div class="pdf-option-header">
              <span class="pdf-option-icon">✈️</span>
              <div>
                <h3>${flight.airline || flight.flight_number || 'Flight Option ' + (idx + 1)}</h3>
                <p class="pdf-flight-route">${flight.departure_airport || 'Origin'} → ${flight.arrival_airport || 'Destination'}</p>
              </div>
            </div>
            ${flight.departure_time ? `<p class="pdf-option-detail"><strong>Departure:</strong> ${new Date(flight.departure_time).toLocaleString('en-US', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})}</p>` : ''}
            ${flight.arrival_time ? `<p class="pdf-option-detail"><strong>Arrival:</strong> ${new Date(flight.arrival_time).toLocaleString('en-US', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})}</p>` : ''}
            ${flight.flight_date ? `<p class="pdf-option-detail"><strong>Date:</strong> ${new Date(flight.flight_date).toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'})}</p>` : ''}
            ${flight.status ? `<span class="pdf-option-status">${flight.status.toUpperCase()}</span>` : ''}
            <p class="pdf-option-price">${flight.price || 'Price on request'}</p>
            <div class="pdf-booking-link">
              <strong>🔗 Book Now:</strong><br>
              <a href="${bookingUrl}" target="_blank" style="color: #667eea; word-break: break-all; text-decoration: underline;">${bookingUrl}</a>
            </div>
          </div>
        `;
      });
    }

    // Add trains
    if (latestTransportData.trains.length > 0) {
      latestTransportData.trains.slice(0, 3).forEach((train, idx) => {
        const bookingUrl = train.booking_link || generateTrainBookingURL(latestItineraryMeta);
        
        transportSection += `
          <div class="pdf-option-card">
            <div class="pdf-option-header">
              <span class="pdf-option-icon">🚄</span>
              <h3>${train.name || 'Train Option ' + (idx + 1)}</h3>
            </div>
            ${train.duration ? `<p class="pdf-option-detail"><strong>Duration:</strong> ${train.duration}</p>` : ''}
            ${train.departure ? `<p class="pdf-option-detail"><strong>Departure:</strong> ${train.departure}</p>` : ''}
            <p class="pdf-option-price">${train.price || 'Price on request'}</p>
            <div class="pdf-booking-link">
              <strong>🔗 Book Train:</strong><br>
              <a href="${bookingUrl}" target="_blank" style="color: #667eea; word-break: break-all; text-decoration: underline;">${bookingUrl}</a>
            </div>
          </div>
        `;
      });
    }

    // Add buses
    if (latestTransportData.buses.length > 0) {
      latestTransportData.buses.slice(0, 3).forEach((bus, idx) => {
        const bookingUrl = bus.booking_link || generateBusBookingURL(latestItineraryMeta);
        
        transportSection += `
          <div class="pdf-option-card">
            <div class="pdf-option-header">
              <span class="pdf-option-icon">🚌</span>
              <h3>${bus.name || 'Bus Option ' + (idx + 1)}</h3>
            </div>
            ${bus.duration ? `<p class="pdf-option-detail"><strong>Duration:</strong> ${bus.duration}</p>` : ''}
            ${bus.departure ? `<p class="pdf-option-detail"><strong>Departure:</strong> ${bus.departure}</p>` : ''}
            <p class="pdf-option-price">${bus.price || 'Price on request'}</p>
            <div class="pdf-booking-link">
              <strong>🔗 Book Bus:</strong><br>
              <a href="${bookingUrl}" target="_blank" style="color: #667eea; word-break: break-all; text-decoration: underline;">${bookingUrl}</a>
            </div>
          </div>
        `;
      });
    }

    transportSection += `
        </div>
      </div>
    `;
  }

  // Add hotel section
  if (latestTransportData.hotels.length > 0) {
    staySection = `
      <div class="pdf-section">
        <h2 class="pdf-section-title">🏨 Accommodation Options</h2>
        <div class="pdf-options-grid">
    `;

    latestTransportData.hotels.slice(0, 4).forEach((hotel, idx) => {
      const bookingUrl = hotel.booking_link || generateHotelBookingURL(latestItineraryMeta);
      
      staySection += `
        <div class="pdf-option-card">
          <div class="pdf-option-header">
            <span class="pdf-option-icon">🏨</span>
            <div>
              <h3>${hotel.name || 'Hotel Option ' + (idx + 1)}</h3>
              ${hotel.location ? `<p class="pdf-hotel-location">📍 ${hotel.location}</p>` : ''}
            </div>
          </div>
          ${hotel.duration ? `<p class="pdf-option-detail"><strong>Stay Duration:</strong> ${hotel.duration}</p>` : ''}
          ${hotel.rating ? `<p class="pdf-option-detail"><strong>Rating:</strong> ${'⭐'.repeat(Math.floor(hotel.rating))}</p>` : ''}
          ${hotel.amenities ? `<p class="pdf-option-detail"><strong>Amenities:</strong> ${hotel.amenities}</p>` : ''}
          <p class="pdf-option-price">${hotel.price || 'Price on request'}</p>
          <div class="pdf-booking-link">
            <strong>🔗 Book Hotel:</strong><br>
            <a href="${bookingUrl}" target="_blank" style="color: #667eea; word-break: break-all; text-decoration: underline;">${bookingUrl}</a>
          </div>
        </div>
      `;
    });

    staySection += `
        </div>
      </div>
    `;
  }
  const printable = `
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>${title}</title>
      <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { 
          font-family: 'Inter', system-ui, -apple-system, Segoe UI, sans-serif; 
          margin:40px; 
          color:#0f172a;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
        }
        .itinerary-container-print { 
          max-width:1000px; 
          margin:0 auto; 
          background: white;
          border-radius: 24px;
          padding: 48px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 { 
          color:#111827; 
          font-size: 36px;
          margin-bottom: 32px;
          text-align: center;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }
        h2 { color:#111827; margin-top: 32px; margin-bottom: 16px; }
        h3 { color:#1e293b; font-size: 16px; margin: 0; }
        details { 
          border:1px solid #e0e7ff; 
          border-radius:16px; 
          margin-bottom:16px; 
          padding:0 20px 12px;
          background: linear-gradient(135deg, #faf5ff 0%, #f5f3ff 100%);
        }
        summary { 
          font-weight:600; 
          font-size:18px; 
          padding:16px 0; 
          list-style:none;
          cursor: pointer;
        }
        summary::-webkit-details-marker { display:none; }
        .time-block { 
          border:1px solid #e2e8f0; 
          border-radius:12px; 
          padding:16px; 
          margin-bottom:12px;
          background: white;
        }
        .time-block strong { color:#5b21b6; }
        .itinerary-day-toggle { display:none; }
        
        /* Transport & Stay Sections */
        .pdf-section {
          margin-top: 48px;
          page-break-inside: avoid;
        }
        .pdf-section-title {
          font-size: 28px;
          color: #111827;
          margin-bottom: 24px;
          padding-bottom: 12px;
          border-bottom: 3px solid #667eea;
        }
        .pdf-options-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
          gap: 20px;
          margin-bottom: 24px;
        }
        .pdf-option-card {
          background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
          border: 2px solid #e2e8f0;
          border-radius: 16px;
          padding: 20px;
          transition: all 0.3s ease;
          page-break-inside: avoid;
        }
        .pdf-option-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
          border-color: #667eea;
        }
        .pdf-option-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 12px;
        }
        .pdf-option-icon {
          font-size: 28px;
          line-height: 1;
        }
        .pdf-option-detail {
          color: #475569;
          font-size: 14px;
          margin: 8px 0;
          line-height: 1.5;
        }
        .pdf-option-status {
          display: inline-block;
          padding: 4px 12px;
          background: #dbeafe;
          color: #1e40af;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 600;
          margin: 8px 0;
        }
        .pdf-option-price {
          color: #059669;
          font-weight: 700;
          font-size: 18px;
          margin: 12px 0 8px;
        }
        .pdf-option-link {
          color: #667eea;
          font-size: 12px;
          word-break: break-all;
          margin-top: 8px;
          font-weight: 500;
        }
        .pdf-booking-link {
          margin-top: 12px;
          padding: 12px;
          background: #f8fafc;
          border: 2px dashed #cbd5e1;
          border-radius: 8px;
          font-size: 12px;
        }
        .pdf-booking-link strong {
          color: #334155;
          font-size: 13px;
          margin-bottom: 6px;
          display: block;
        }
        .pdf-booking-link a {
          color: #667eea !important;
          text-decoration: underline !important;
          word-break: break-all;
          font-size: 11px;
          line-height: 1.6;
        }
        .pdf-flight-route {
          color: #64748b;
          font-size: 13px;
          font-weight: 500;
          margin-top: 4px;
        }
        .pdf-hotel-location {
          color: #64748b;
          font-size: 12px;
          margin-top: 4px;
        }
        
        @media print {
          body { background: white; }
          .itinerary-container-print { box-shadow: none; }
        }
      </style>
    </head>
    <body>
      <div class="itinerary-container-print">
        <h1>${title}</h1>
        ${printableHtml}
        ${transportSection}
        ${staySection}
      </div>
    </body>
    </html>
  `;

  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) {
    showToast("Allow pop-ups to download the itinerary.");
    return;
  }
  win.document.open();
  win.document.write(printable);
  win.document.close();
  win.focus();
  setTimeout(() => {
    try {
      win.print();
    } catch (err) {
      console.warn("Print dialog failed:", err);
    }
  }, 400);
}

/**
 * Format itinerary text into beautiful HTML - robust parser for actual LLM output
 */
function parseItinerarySections(rawText) {
  const dayRegex = /\*\*Day\s*(\d+)[\s:.-]*([^\*]*)\*\*/gi;
  const days = [];
  let intro = "";
  let currentIndex = 0;
  let match;

  while ((match = dayRegex.exec(rawText)) !== null) {
    const dayNumber = parseInt(match[1], 10);
    const title = (match[2] || "").trim();
    const headerStart = match.index;
    const headerEnd = dayRegex.lastIndex;

    if (days.length === 0) {
      intro = rawText.slice(0, headerStart).trim();
    } else {
      const prevDay = days[days.length - 1];
      prevDay.content = rawText.slice(currentIndex, headerStart).trim();
    }

    days.push({ dayNum: dayNumber, title, content: "" });
    currentIndex = headerEnd;
  }

  if (days.length > 0) {
    const lastDay = days[days.length - 1];
    lastDay.content = rawText.slice(currentIndex).trim();
  } else {
    intro = rawText.trim();
  }

  return { intro, days };
}

function extractDayPreview(content) {
  if (!content) return "";
  const locationMatch = content.match(/\*\*([^*]{2,80})\*\*/i);
  if (locationMatch) return locationMatch[1].trim();
  const bulletMatch = content.match(/•\s*([^\n]+)/);
  if (bulletMatch) return bulletMatch[1].trim();
  const line = content.split("\n").find((ln) => ln.trim());
  return line ? line.trim().slice(0, 80) : "";
}

function formatItineraryText(text, cities, startDate, endDate) {
  if (!text || typeof text !== "string") {
    console.warn("Invalid text input to formatItineraryText:", text);
    return "";
  }

  try {
    const header = `
      <div class="itinerary-header">
        <div class="itinerary-title">Your Perfect Travel Plan</div>
        <div class="itinerary-meta">
          ${cities && Array.isArray(cities) && cities.length > 0 ? `<div class="itinerary-meta-item"><strong>📍 Cities:</strong> ${cities.join(", ")}</div>` : ""}
          ${startDate ? `<div class="itinerary-meta-item"><strong>📅 Start:</strong> ${new Date(startDate).toLocaleDateString()}</div>` : ""}
          ${endDate ? `<div class="itinerary-meta-item"><strong>📅 End:</strong> ${new Date(endDate).toLocaleDateString()}</div>` : ""}
        </div>
      </div>
    `;

    const { intro, days } = parseItinerarySections(text);
    let body = "";

    if (intro) {
      body += `<div class="itinerary-intro">${formatItineraryContent(intro)}</div>`;
    }

    if (!days.length) {
      body += `
        <details class="itinerary-day-card" open>
          <summary class="itinerary-day-summary">
            <span class="day-icon">🧭</span>
            <div class="day-title">
              <span class="day-title-main">Full Itinerary</span>
              <span class="day-title-meta">Expand for details</span>
            </div>
            <span class="itinerary-day-toggle">⌄</span>
          </summary>
          <div class="itinerary-day-content">
            <div class="itinerary-time-block">
              <div class="itinerary-activity">
                ${formatItineraryContent(text)}
              </div>
            </div>
          </div>
        </details>
      `;
      return header + body;
    }

    days.forEach((day, index) => {
      body += createDayBlock(day.dayNum, day.content, day.title, {
        iconIndex: index,
        open: index === 0
      });
    });

    return header + body;
  } catch (err) {
    console.error("Critical error in formatItineraryText:", err);
    return `
      <div class="itinerary-header">
        <div class="itinerary-title">Your Travel Plan</div>
      </div>
      <details class="itinerary-day-card" open>
        <summary class="itinerary-day-summary">
          <span class="day-icon">🧭</span>
          <div class="day-title">
            <span class="day-title-main">Your Itinerary</span>
          </div>
          <span class="itinerary-day-toggle">⌄</span>
        </summary>
        <div class="itinerary-day-content">
          <div class="itinerary-time-block">
            <div class="itinerary-activity">
              ${formatMarkdown(text || "No itinerary content available.")}
            </div>
          </div>
        </div>
      </details>
    `;
  }
}

/**
 * Create a formatted day block - handles actual LLM output format
 */
function createDayBlock(dayNum, content, dayTitle = "", options = {}) {
  try {
    if (!content || typeof content !== 'string') {
      content = String(content || "");
    }

    const displayTitle = (dayTitle || "").replace(/\*\*/g, "").trim() || "";

    const iconIndex = options.iconIndex || 0;
    const icon = DAY_ICON_SET[iconIndex % DAY_ICON_SET.length];
    const preview = extractDayPreview(content);
    const openAttr = options.open ? " open" : "";

    let dayInnerHtml = "";

    // Split content by time sections - handle **Morning:** **Location** pattern
    const timeSections = [];
    try {
      const timeSectionRegex = /\*\*(Morning|Afternoon|Evening|Lunch|Dinner)[:\-]?\s*([^*]+)?\*\*/gi;
      let lastIndex = 0;
      let match;

      // Reset regex
      timeSectionRegex.lastIndex = 0;

      while ((match = timeSectionRegex.exec(content)) !== null) {
        if (match.index > lastIndex) {
          const beforeText = content.substring(lastIndex, match.index).trim();
          if (beforeText) {
            timeSections.push({ type: 'text', content: beforeText });
          }
        }

        // Find end of this time section (next time section or end)
        const sectionStart = match.index;
        timeSectionRegex.lastIndex = match.index + match[0].length;
        const nextMatch = timeSectionRegex.exec(content);
        timeSectionRegex.lastIndex = 0; // Reset for next iteration

        const sectionEnd = nextMatch ? nextMatch.index : content.length;
        const sectionContent = content.substring(sectionStart, sectionEnd).trim();

        timeSections.push({
          type: 'time',
          label: match[1],
          content: sectionContent,
          startIndex: sectionStart
        });

        lastIndex = sectionEnd;
      }

      // Add remaining content
      if (lastIndex < content.length) {
        const remaining = content.substring(lastIndex).trim();
        if (remaining) {
          timeSections.push({ type: 'text', content: remaining });
        }
      }
    } catch (regexError) {
      console.warn("Error in time section regex:", regexError);
      // Fallback: treat as single text block
      timeSections.push({ type: 'text', content: content });
    }

    // If no time sections found, try simpler pattern
    if (timeSections.length === 0) {
      try {
        const simpleTimePattern = /(Morning|Afternoon|Evening|Lunch|Dinner)[:\-]/gi;
        const simpleMatches = [...content.matchAll(simpleTimePattern)];

        if (simpleMatches.length > 0) {
          for (let i = 0; i < simpleMatches.length; i++) {
            const startIdx = simpleMatches[i].index;
            const endIdx = i < simpleMatches.length - 1 ? simpleMatches[i + 1].index : content.length;
            const sectionText = content.substring(startIdx, endIdx).trim();
            timeSections.push({
              type: 'time',
              label: simpleMatches[i][1],
              content: sectionText
            });
          }
        } else {
          // No time sections at all - format entire content
          timeSections.push({ type: 'text', content: content });
        }
      } catch (simpleError) {
        console.warn("Error in simple time pattern:", simpleError);
        timeSections.push({ type: 'text', content: content });
      }
    }

    // Process time sections with error handling
    for (const section of timeSections) {
      try {
        if (section.type === 'time') {
          // Extract location name from **Location** pattern
          const locationMatch = section.content.match(/\*\*([^*]+)\*\*/);
          const locationName = locationMatch ? locationMatch[1] : "";

          // Extract time if present
          const timeMatch = section.content.match(/\(([^)]+)\)/);
          const timeStr = timeMatch ? timeMatch[1] : "";

          // Remove time section header and location from content
          let sectionContent = section.content
            .replace(/\*\*(Morning|Afternoon|Evening|Lunch|Dinner)[:\-]?\s*[^*]*\*\*/gi, "")
            .replace(/\*\*([^*]+)\*\*/g, "")
            .trim();

          dayInnerHtml += createTimeBlock(section.label, sectionContent, timeStr, locationName);
        } else {
          // Regular text content
          dayInnerHtml += `<div class="itinerary-time-block">${formatItineraryContent(section.content || "")}</div>`;
        }
      } catch (sectionError) {
        console.warn("Error processing time section:", sectionError);
        // Fallback: add as plain text
        dayInnerHtml += `<div class="itinerary-time-block">${formatItineraryContent(String(section.content || ""))}</div>`;
      }
    }

    if (!dayInnerHtml.trim()) {
      dayInnerHtml = `<div class="itinerary-time-block"><div class="itinerary-activity">${formatItineraryContent(content)}</div></div>`;
    }

    return `
      <details class="itinerary-day-card"${openAttr}>
        <summary class="itinerary-day-summary">
          <span class="day-icon">${icon}</span>
          <div class="day-title">
            <span class="day-title-main">Day ${dayNum || "?"}${displayTitle ? `: ${displayTitle}` : ""}</span>
            ${preview ? `<span class="day-title-meta">${preview}</span>` : ""}
          </div>
          <span class="itinerary-day-toggle">⌄</span>
        </summary>
        <div class="itinerary-day-content">
          ${dayInnerHtml}
        </div>
      </details>
    `;
  } catch (err) {
    console.error("Critical error in createDayBlock:", err);
    // Return minimal safe HTML
    return `
      <details class="itinerary-day-card" open>
        <summary class="itinerary-day-summary">
          <span class="day-icon">🧭</span>
          <div class="day-title">
            <span class="day-title-main">Day ${dayNum || "?"}</span>
          </div>
          <span class="itinerary-day-toggle">⌄</span>
        </summary>
        <div class="itinerary-day-content">
          <div class="itinerary-time-block">
            <div class="itinerary-activity">
              ${formatItineraryContent(String(content || ""))}
            </div>
          </div>
        </div>
      </details>
    `;
  }
}

/**
 * Create a formatted time block
 */
function createTimeBlock(label, content, time = "", activityTitle = "") {
  const emojiMap = {
    MORNING: "🌅",
    AFTERNOON: "🌆",
    EVENING: "🌃",
    LUNCH: "🍽️",
    DINNER: "🍽️",
    WALK: "🚶",
    TRANSIT: "🚶",
    ACCOMMODATION: "💤"
  };

  const emoji = emojiMap[label.toUpperCase()] || "📍";
  const displayLabel = label.charAt(0) + label.slice(1).toLowerCase();

  let timeLabelHtml = `${emoji} <strong>${displayLabel}</strong>`;
  if (time) {
    timeLabelHtml += ` <span class="itinerary-time">(${time})</span>`;
  }
  if (activityTitle) {
    timeLabelHtml += `: <span class="itinerary-activity-name">${activityTitle}</span>`;
  }

  return `
    <div class="itinerary-time-block">
      <div class="itinerary-time-label">${timeLabelHtml}</div>
      <div class="itinerary-activity">${formatItineraryContent(content)}</div>
    </div>
  `;
}

/**
 * Format itinerary content with proper styling - SIMPLIFIED and more robust
 */
function formatItineraryContent(text) {
  if (!text) return "";

  try {
    // Ensure text is a string
    if (typeof text !== 'string') {
      text = String(text || "");
    }

    // Escape HTML first
    let safe = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Process line by line for better control
    const lines = safe.split('\n');
    let result = "";

    for (let i = 0; i < lines.length; i++) {
      try {
        let line = lines[i]?.trim() || "";
        if (!line) {
          // Empty line - add spacing
          if (i < lines.length - 1 && lines[i + 1] && lines[i + 1].trim()) {
            result += '<div style="height:8px;"></div>';
          }
          continue;
        }

        // Check for bullet points (•, -, *)
        if (/^[\s]*[•\-\*]\s+/.test(line)) {
          const content = line.replace(/^[\s]*[•\-\*]\s+/, "");
          // Convert bold in bullet content
          const withBold = content.replace(/\*\*([^*]+)\*\*/g, '<span class="itinerary-highlight">$1</span>');
          result += `<div class="itinerary-activity-detail">${withBold}</div>`;
          continue;
        }

        // Check for numbered lists
        if (/^[\s]*\d+[\.\)]\s+/.test(line)) {
          const content = line.replace(/^[\s]*\d+[\.\)]\s+/, "");
          const withBold = content.replace(/\*\*([^*]+)\*\*/g, '<span class="itinerary-highlight">$1</span>');
          result += `<div class="itinerary-activity-detail">${withBold}</div>`;
          continue;
        }

        // Check if line starts with ** (bold text - likely a heading or location)
        if (/^\*\*/.test(line)) {
          // Remove ** and highlight
          const content = line.replace(/\*\*/g, "");
          result += `<div class="itinerary-activity-title" style="margin-top:16px; margin-bottom:8px;"><span class="itinerary-highlight">${content}</span></div>`;
          continue;
        }

        // Regular text line - convert bold and wrap
        let processed = line.replace(/\*\*([^*]+)\*\*/g, '<span class="itinerary-highlight">$1</span>');
        processed = processed.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Check if it's a time section header
        if (/^(Morning|Afternoon|Evening|Lunch|Dinner)[:\-]/.test(processed)) {
          result += `<div class="itinerary-time-section"><strong>${processed}</strong></div>`;
        } else {
          result += `<div class="itinerary-activity-detail">${processed}</div>`;
        }
      } catch (lineError) {
        console.warn("Error processing line:", lineError, lines[i]);
        // Continue with next line
        result += `<div class="itinerary-activity-detail">${lines[i] || ""}</div>`;
      }
    }

    return result || `<div class="itinerary-activity-detail">${safe.replace(/\n/g, "<br>")}</div>`;
  } catch (err) {
    console.error("Error in formatItineraryContent:", err);
    // Return safe fallback
    return `<div class="itinerary-activity-detail">${String(text || "").replace(/\n/g, "<br>")}</div>`;
  }
}

// =============================
// CHAT INPUT HANDLERS
// =============================

/**
 * Auto-resize textarea as user types
 */
function autoResizeTextarea() {
  if (!chatInputEl) return;
  chatInputEl.style.height = 'auto';
  const newHeight = Math.min(chatInputEl.scrollHeight, 120);
  chatInputEl.style.height = newHeight + 'px';
}

/**
 * Handle send button click
 */
function handleSend() {
  if (!chatInputEl) return;
  const msg = chatInputEl.value.trim();
  if (!msg || isSending) return;

  chatInputEl.value = "";
  autoResizeTextarea(); // Reset height
  sendToAura(msg);
}

// Attach event listeners
if (sendBtnEl) {
  sendBtnEl.addEventListener("click", handleSend);
}

if (chatInputEl) {
  // Send on Enter key (Shift+Enter for newline)
  chatInputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Auto-resize on input
  chatInputEl.addEventListener("input", autoResizeTextarea);

  // Focus input on load
  chatInputEl.focus();
}

// =============================
// LOAD PERSISTENT CHAT HISTORY
// =============================

/**
 * Load chat history from backend (if session exists) or localStorage
 */
async function loadChatHistory() {
  if (!chatMessagesEl) return;

  // Try to load from backend if we have a session
  if (sessionId) {
    try {
      const token = await getIdToken();
      const response = await fetch(`http://127.0.0.1:8000/chat/history?session_id=${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
          // Limit messages to prevent memory issues
          const messages = data.messages.slice(-100); // Only keep last 100 messages
          chatHistory = messages.map(m => ({
            role: m.role || "user",
            content: m.content || "",
            timestamp: m.ts ? new Date(m.ts).getTime() : Date.now()
          }));
          // Defer saving to prevent blocking
          setTimeout(() => saveChatHistory(), 100);
        }
      }
    } catch (err) {
      console.warn("Could not load history from backend:", err);
      // Fall back to localStorage
    }
  }

  // Restore messages from history - BATCHED to prevent hangs
  if (chatHistory.length === 0) {
    // Show welcome message if no history
    addMessageToUI("assistant", "Hey! I'm Aura, your travel planning assistant. What adventure are we planning today? ✨");
    scrollChatToBottom();
  } else {
    // Limit messages to prevent hangs (only show last 50 messages)
    const messagesToShow = chatHistory.slice(-50);
    console.log(`Loading ${messagesToShow.length} messages (limited from ${chatHistory.length})`);

    // Batch render messages to prevent blocking
    let index = 0;
    const batchSize = 5; // Render 5 messages at a time

    function renderBatch() {
      const end = Math.min(index + batchSize, messagesToShow.length);

      // Use document fragment for better performance
      const fragment = document.createDocumentFragment();

      for (let i = index; i < end; i++) {
        const msg = messagesToShow[i];
        try {
          const messageEl = document.createElement("div");
          messageEl.className = `chat-message ${msg.role}`;

          // Skip markdown formatting for old messages to speed up rendering
          // Only format if it's a recent message (last 10) or assistant message
          if (msg.role === "assistant" && i >= messagesToShow.length - 10) {
            messageEl.innerHTML = formatMarkdown(msg.content);
          } else {
            // Plain text for older messages (much faster)
            messageEl.textContent = msg.content;
          }

          fragment.appendChild(messageEl);
        } catch (err) {
          console.warn("Error rendering message:", err);
        }
      }

      if (chatMessagesEl) {
        chatMessagesEl.appendChild(fragment);
      }

      index = end;

      if (index < messagesToShow.length) {
        // Continue rendering next batch
        setTimeout(renderBatch, 10); // Small delay to prevent blocking
      } else {
        // All messages rendered
        scrollChatToBottom();
      }
    }

    // Clear existing messages first
    if (chatMessagesEl) {
      chatMessagesEl.innerHTML = "";
    }

    // Start rendering
    renderBatch();
  }
}

// =============================
// SOCIAL MEDIA & JOURNALING
// =============================

/**
 * Load social media posts from backend
 */
async function loadSocialPosts() {
  const socialGrid = document.getElementById("socialGrid");
  if (!socialGrid) return;

  try {
    const token = await getIdToken();
    const response = await fetch("http://127.0.0.1:8000/social/posts", {
      headers: { Authorization: `Bearer ${token}` }
    });

    let posts = [];
    if (response.ok) {
      const data = await response.json();
      posts = data.posts || [];
    }

    // Fallback to localStorage if backend returns empty
    if (posts.length === 0) {
      posts = readJSONFromStorage("aura_social_posts", []);
    }

    if (posts.length === 0) {
      socialGrid.innerHTML = `<div class="placeholder">No posts yet. Share your travel experiences!</div>`;
      return;
    }

    socialGrid.innerHTML = ""; // Clear existing
    posts.forEach(post => {
      const postEl = document.createElement("div");
      postEl.className = "social-post";
      postEl.innerHTML = `
        <div class="social-post-header">
          <div class="social-post-avatar">${(post.author || "User")[0].toUpperCase()}</div>
          <div>
            <strong>${post.author || "User"}</strong>
            <div style="font-size:12px; color:var(--muted); opacity:0.7">${new Date(post.timestamp || Date.now()).toLocaleDateString()}</div>
          </div>
        </div>
        <div class="social-post-content">${post.content || ""}</div>
        <div class="social-post-footer">
          <span>❤️ ${post.likes || 0}</span>
          <span>💬 ${post.comments || 0}</span>
        </div>
      `;
      socialGrid.appendChild(postEl);
    });
  } catch (err) {
    console.error("Error loading social posts:", err);
    socialGrid.innerHTML = `<div class="placeholder">Could not load posts. Please try again later.</div>`;
  }
}

/**
 * Load travel journal entries from backend
 */
async function loadJournalEntries() {
  const journalEntries = document.getElementById("journalEntries");
  if (!journalEntries) return;

  try {
    const token = await getIdToken();
    const response = await fetch("http://127.0.0.1:8000/journal/entries", {
      headers: { Authorization: `Bearer ${token}` }
    });

    let entries = [];
    if (response.ok) {
      const data = await response.json();
      entries = data.entries || [];
    }

    // Fallback to localStorage if backend returns empty
    if (entries.length === 0) {
      entries = readJSONFromStorage("aura_journal_entries", []);
    }

    if (entries.length === 0) {
      journalEntries.innerHTML = `<div class="placeholder">Your travel memories will appear here after your trips!</div>`;
      return;
    }

    journalEntries.innerHTML = ""; // Clear existing
    entries.forEach(entry => {
      const entryEl = document.createElement("div");
      entryEl.className = "journal-entry";
      entryEl.innerHTML = `
        <div class="journal-entry-date">${new Date(entry.date || entry.timestamp || Date.now()).toLocaleDateString()}</div>
        <div class="journal-entry-content">${entry.content || ""}</div>
      `;
      journalEntries.appendChild(entryEl);
    });
  } catch (err) {
    console.error("Error loading journal entries:", err);
    journalEntries.innerHTML = `<div class="placeholder">Could not load journal entries. Please try again later.</div>`;
  }
}

// =============================
// NAVIGATION HANDLERS
// =============================

/**
 * Handle navigation to different sections
 */
function setupNavigation() {
  document.querySelectorAll(".nav-item").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const href = a.getAttribute("href");
      if (!href || !href.startsWith("#")) return;

      const el = document.querySelector(href);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });

        // Show/hide sections based on navigation
        if (href === "#social") {
          document.getElementById("social")?.style.setProperty("display", "block");
          loadSocialPosts();
        } else if (href === "#journal") {
          document.getElementById("journal")?.style.setProperty("display", "block");
          loadJournalEntries();
        }
      }
    });
  });
}

// =============================
// ANIMATIONS & UI POLISH
// =============================

/**
 * Initialize scroll animations - with safety checks
 */
let scrollObserver = null;

function initScrollAnimations() {
  // DISABLED: Scroll animations can cause hangs with heavy DOM operations
  // Just make content visible immediately
  try {
    // Make all content visible immediately (lightweight)
    const animateElements = document.querySelectorAll(".animate-in");
    if (animateElements.length > 0) {
      // Use requestAnimationFrame to batch DOM updates
      requestAnimationFrame(() => {
        animateElements.forEach((el) => {
          if (el) {
            el.classList.add("in-view");
            el.style.opacity = "1";
            el.style.transform = "none";
          }
        });
      });
    }
  } catch (err) {
    console.error("Error making content visible:", err);
  }

  /* OLD CODE - DISABLED
  // Prevent multiple observers
  if (scrollObserver) {
    console.warn("Scroll observer already initialized, skipping...");
    return;
  }
  
  try {
    // Make all content visible immediately (fallback)
    document.querySelectorAll(".animate-in").forEach((el) => {
      if (el) {
        el.classList.add("in-view"); // Make visible immediately
        el.style.opacity = "1"; // Force visibility
        el.style.transform = "none";
      }
    });
    
    scrollObserver = new IntersectionObserver(
    (entries) => {
        try {
      entries.forEach((entry) => {
            try {
        const el = entry.target;
              if (!el || !el.parentElement) return;
              
        if (entry.isIntersecting) {
          el.classList.add("in-view");
                el.style.opacity = "1"; // Ensure visible
                el.style.transform = "none";
          const icon = el.querySelector(".fw-icon");
          if (icon) icon.style.transform = "translateY(-6px) scale(1.02)";
        } else {
                // Don't hide on scroll out - keep content visible
          const icon = el.querySelector(".fw-icon");
          if (icon) icon.style.transform = "none";
              }
            } catch (entryError) {
              console.warn("Error processing intersection entry:", entryError);
        }
      });
        } catch (observerError) {
          console.error("Error in intersection observer:", observerError);
        }
    },
    { threshold: 0.15 }
  );
    
    // Observe elements with error handling
    try {
      document.querySelectorAll(".animate-in").forEach((n) => {
        if (n) {
          scrollObserver.observe(n);
          // Ensure it's visible even if observer hasn't fired yet
          n.style.opacity = "1";
          n.style.transform = "none";
        }
      });
    } catch (err) {
      console.warn("Error observing animate-in elements:", err);
    }
    
    try {
      document.querySelectorAll(".feature-card").forEach((n) => {
        if (n) scrollObserver.observe(n);
      });
    } catch (err) {
      console.warn("Error observing feature cards:", err);
    }
  } catch (err) {
    console.error("Error initializing scroll animations:", err);
    // Fallback: make everything visible
    document.querySelectorAll(".animate-in").forEach((el) => {
      if (el) {
        el.style.opacity = "1";
        el.style.transform = "none";
      }
    });
  }
  */
}

// =============================
// TYPING ANIMATION
// =============================

/**
 * Typing animation for welcome message - DISABLED to prevent hangs
 * Just show text immediately
 */
let typingAnimationTimeout = null;
let isTypingAnimationRunning = false;

function initTypingAnimation() {
  const el = document.getElementById("typed");
  if (!el) return;

  if (isTypingAnimationRunning) return;

  try {
    const userName = auth.currentUser?.displayName || "Traveler";
    const full = `Welcome back, ${userName}! Plan your next adventure with AI.`;

    let i = 0;
    let isDeleting = false;
    isTypingAnimationRunning = true;

    function tick() {
      try {
        if (!el || !el.parentElement) {
          isTypingAnimationRunning = false;
          return;
        }

        if (!isDeleting) {
          // Typing forward
          i++;
          el.textContent = full.slice(0, i);

          if (i >= full.length) {
            // Finished typing, pause then start deleting
            typingAnimationTimeout = setTimeout(() => {
              isDeleting = true;
              tick();
            }, 2000); // Pause for 2 seconds
            return;
          }
          typingAnimationTimeout = setTimeout(tick, 80);
        } else {
          // Deleting backward
          i--;
          el.textContent = full.slice(0, i);

          if (i <= 0) {
            // Finished deleting, start typing again
            isDeleting = false;
            typingAnimationTimeout = setTimeout(tick, 500);
            return;
          }
          typingAnimationTimeout = setTimeout(tick, 40);
        }
      } catch (err) {
        console.error("Error in typing animation:", err);
        el.textContent = full;
        isTypingAnimationRunning = false;
      }
    }
    tick();
  } catch (err) {
    console.error("Error setting welcome text:", err);
    const userName = auth.currentUser?.displayName || "Traveler";
    el.textContent = `Welcome back, ${userName}! Plan your next adventure with AI.`;
    isTypingAnimationRunning = false;
  }

  /* OLD CODE - DISABLED
  // Prevent multiple animations
  if (isTypingAnimationRunning) {
    console.warn("Typing animation already running, skipping...");
    // Show full text immediately as fallback
    const userName = auth.currentUser?.displayName || "Traveler";
    el.textContent = `Welcome back, ${userName}! Plan your next adventure with AI.`;
    return;
  }
  
  try {
    const userName = auth.currentUser?.displayName || "Traveler";
    const full = `Welcome back, ${userName}! Plan your next adventure with AI.`;
    
    // Show full text immediately (fallback)
    el.textContent = full;
    
    let i = 0;
    let forward = true;
    let pauseAfter = 1400;
    isTypingAnimationRunning = true;
    let animationCount = 0;
    const maxAnimations = 3; // Limit to prevent infinite loops
    
    function tick() {
      try {
        // Safety check: make sure element still exists
        if (!el || !el.parentElement) {
          isTypingAnimationRunning = false;
          return;
        }
        
        // Limit animation cycles to prevent infinite loops
        if (animationCount > maxAnimations) {
          el.textContent = full;
          isTypingAnimationRunning = false;
          return;
        }
        
        if (forward) {
          i++;
          el.textContent = full.slice(0, i);
         
          if (i >= full.length) {
            forward = false;
            animationCount++;
            typingAnimationTimeout = setTimeout(() => {
              if (animationCount < maxAnimations) {
                i = 0;
                forward = true;
                tick();
              } else {
                el.textContent = full;
                isTypingAnimationRunning = false;
              }
            }, pauseAfter);
            return;
          }
        } else {
          i = 0;
        }
        typingAnimationTimeout = setTimeout(tick, 80);
      } catch (err) {
        console.error("Error in typing animation:", err);
        el.textContent = full; // Show full text on error
        isTypingAnimationRunning = false;
      }
    }
    tick();
  } catch (err) {
    console.error("Error initializing typing animation:", err);
    // Show full text on error
    const userName = auth.currentUser?.displayName || "Traveler";
    el.textContent = `Welcome back, ${userName}! Plan your next adventure with AI.`;
    isTypingAnimationRunning = false;
  }
  */
}

// =============================
// MARQUEE ANIMATION
// =============================

/**
 * Initialize marquee scroll animation - DISABLED to prevent hangs
 *If needed, use CSS animations instead of JavaScript
 */
let marqueeAnimationId = null;
let isMarqueeRunning = false;

function initMarquee() {
  const track = document.getElementById("marqueeTrack");
  if (!track) return;

  if (isMarqueeRunning) return;

  try {
    const nodes = Array.from(track.children);
    if (nodes.length === 0) return;

    // Clone images for seamless loop
    nodes.forEach((node) => track.appendChild(node.cloneNode(true)));

    let px = 0;
    const speed = 1.2;
    isMarqueeRunning = true;

    function step() {
      try {
        if (!track || !track.parentElement) {
          isMarqueeRunning = false;
          if (marqueeAnimationId) cancelAnimationFrame(marqueeAnimationId);
          return;
        }

        px += speed;
        const half = track.scrollWidth / 2;
        if (half > 0) {
          if (px >= half) px = 0;
          track.style.transform = `translateX(${-px}px)`;
        }
        marqueeAnimationId = requestAnimationFrame(step);
      } catch (err) {
        console.error("Error in marquee animation:", err);
        isMarqueeRunning = false;
        if (marqueeAnimationId) cancelAnimationFrame(marqueeAnimationId);
      }
    }

    track.style.willChange = "transform";
    marqueeAnimationId = requestAnimationFrame(step);
  } catch (err) {
    console.error("Error initializing marquee:", err);
    isMarqueeRunning = false;
  }

  /* OLD CODE - DISABLED
  const track = document.getElementById("marqueeTrack");
  if (!track) return;
  
  // Prevent multiple marquee initializations
  if (isMarqueeRunning) {
    console.warn("Marquee already running, skipping...");
    return;
  }
  
  try {
    const nodes = Array.from(track.children);
    if (nodes.length === 0) return;
    
    nodes.forEach((node) => track.appendChild(node.cloneNode(true)));
    
    let px = 0;
    const speed = 0.6;
    isMarqueeRunning = true;
    let frameCount = 0;
    const maxFrames = 100000; // Safety limit
    
    function step() {
      try {
        frameCount++;
        
        // Safety check: make sure track still exists
        if (!track || !track.parentElement) {
          isMarqueeRunning = false;
          if (marqueeAnimationId) cancelAnimationFrame(marqueeAnimationId);
          return;
        }
        
        // Safety limit to prevent infinite loops
        if (frameCount > maxFrames) {
          console.warn("Marquee animation limit reached, stopping");
          isMarqueeRunning = false;
          return;
        }
        
        px += speed;
        const half = track.scrollWidth / 2;
        if (half === 0) {
          // Track not ready yet, try again (but limit retries)
          if (frameCount < 100) {
            marqueeAnimationId = requestAnimationFrame(step);
          } else {
            isMarqueeRunning = false;
          }
          return;
        }
        if (px >= half) px = 0;
        track.style.transform = `translateX(${-px}px)`;
        marqueeAnimationId = requestAnimationFrame(step);
      } catch (err) {
        console.error("Error in marquee animation:", err);
        isMarqueeRunning = false;
        if (marqueeAnimationId) cancelAnimationFrame(marqueeAnimationId);
      }
    }
    
    track.style.willChange = "transform";
    marqueeAnimationId = requestAnimationFrame(step);
  } catch (err) {
    console.error("Error initializing marquee:", err);
    isMarqueeRunning = false;
  }
  */
}

// =============================
// LOGOUT HANDLER
// =============================

/**
 * Handle logout - clear local storage and redirect
 */
function setupLogout() {
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem("username");
      localStorage.removeItem("token");
      localStorage.removeItem("email");
      localStorage.removeItem("aura_session_id");
      localStorage.removeItem("aura_chat_history");
      sessionId = null;
      chatHistory = [];
      window.location.href = "../loginPage/login.html";
    });
  }
}

// =============================
// INITIALIZATION
// =============================

/**
 * Load itinerary from backend on page load
 */
async function loadItinerary() {
  if (!sessionId) return;

  try {
    const token = await getIdToken();
    const response = await fetch(`http://127.0.0.1:8000/itinerary?session_id=${sessionId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (response.ok) {
      const data = await response.json();
      if (data.itinerary) {
        // Defer itinerary rendering to prevent blocking
        // Use requestIdleCallback or setTimeout to process in background
        const renderFn = () => {
          try {
            displayItinerary(data.itinerary, data.cities, data.start_date, data.end_date);
          } catch (err) {
            console.error("Error displaying itinerary:", err);
          }
        };

        if (window.requestIdleCallback) {
          requestIdleCallback(renderFn, { timeout: 2000 });
        } else {
          setTimeout(renderFn, 100);
        }
      }
    }
  } catch (err) {
    console.warn("Could not load itinerary:", err);
  }
}

/**
 * Initialize entire application
 */
async function initApp() {
  try {
    console.log("🚀 Initializing WanderMind AI...");

    // Set footer year
    const yearEl = document.getElementById("year");
    if (yearEl) yearEl.textContent = new Date().getFullYear();

    // Initialize sidebar state from localStorage
    initSidebarState();

    // Setup profile chip and buttons
    setupProfileChipDetails();

    // Load dashboard statistics
    setTimeout(async () => {
      try {
        await loadDashboardStats();
      } catch (err) {
        console.warn("Error loading dashboard stats:", err);
      }
    }, 100);

    // Render chat list (show past sessions)
    renderChatList();

    // Start new chat on login (if no current chat) - defer to prevent blocking
    setTimeout(async () => {
      try {
        if (!currentChatId || chatHistory.length === 0) {
          await startNewChat();
        } else {
          // Load existing chat history
          await loadChatHistory();
        }
      } catch (err) {
        console.error("Error loading chat:", err);
        // Fallback: start new chat
        await startNewChat();
      }
    }, 200);

    // Load itinerary if available - defer to prevent blocking
    setTimeout(async () => {
      try {
        await loadItinerary();
      } catch (err) {
        console.warn("Error loading itinerary:", err);
      }
    }, 300);

    // Initialize map - defer to prevent blocking
    setTimeout(() => {
      try {
        initializeMap();
        loadTripLocations();
      } catch (err) {
        console.warn("Error initializing map:", err);
      }
    }, 400);

    // Load transport recommendations - defer to prevent blocking
    setTimeout(async () => {
      try {
        await loadTransportRecommendations();
      } catch (err) {
        console.warn("Error loading transport recommendations:", err);
      }
    }, 500);

    // Setup navigation
    try {
      setupNavigation();
    } catch (err) {
      console.error("Error setting up navigation:", err);
    }

    // DISABLED: Scroll animations can cause hangs
    // Initialize animations (with error handling)
    try {
      initScrollAnimations();
    } catch (err) {
      console.error("Error initializing scroll animations:", err);
    }

    // Simplified typing animation - just show text immediately
    try {
      const typedEl = document.getElementById("typed");
      if (typedEl) {
        const userName = auth.currentUser?.displayName || "Traveler";
        typedEl.textContent = `Welcome back, ${userName}! Plan your next adventure with AI.`;
      }
      // Disable animation to prevent hangs
      initTypingAnimation();
    } catch (err) {
      console.error("Error setting up welcome text:", err);
    }

    // Disable marquee animation to prevent hangs
    try {
      initMarquee();
    } catch (err) {
      console.error("Error initializing marquee:", err);
    }

    // Setup logout
    try {
      setupLogout();
    } catch (err) {
      console.error("Error setting up logout:", err);
    }

    console.log("✨ WanderMind AI initialized successfully");
  } catch (err) {
    console.error("Critical error in initApp:", err);
    // Show error to user but don't crash
    alert("Error initializing application. Some features may not work. Please refresh the page.");
  }
}

// Global error handler to prevent crashes
window.addEventListener('error', (event) => {
  console.error('Global error caught:', event.error);
  // Don't let errors crash the page
  event.preventDefault();

  // Show user-friendly error message
  if (chatMessagesEl) {
    const errorMsg = document.createElement("div");
    errorMsg.className = "chat-message assistant";
    errorMsg.innerHTML = `<div class="itinerary-activity-detail">
      <strong>⚠️ An error occurred:</strong> ${event.error?.message || "Unknown error"}
      <br><br>
      The page is still working. Please try your action again or refresh the page if issues persist.
    </div>`;
    chatMessagesEl.appendChild(errorMsg);
    scrollChatToBottom();
  }

  return true; // Prevent default error handling
});

// =============================
// MAP VISUALIZATION
// =============================
let map = null;
let markers = [];

function initializeMap() {
  try {
    const mapEl = document.getElementById('map');
    if (!mapEl || map) return;

    // Initialize map centered on world view
    map = L.map('map').setView([20, 0], 2);

    // Add tile layer (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);

    console.log('Map initialized successfully');
  } catch (err) {
    console.error('Error initializing map:', err);
  }
}

async function loadTripLocations() {
  try {
    if (!map) return;

    const token = await getIdToken();
    const response = await fetch(`${API_BASE_URL}/chats`, {
      headers: { "Authorization": `Bearer ${token}` }
    });

    if (!response.ok) return;

    const chats = await response.json();

    // Clear existing markers
    markers.forEach(marker => marker.remove());
    markers = [];

    // For each chat, try to get itinerary and extract cities
    for (const chat of chats.slice(0, 5)) { // Limit to 5 most recent
      try {
        const itinResponse = await fetch(`${API_BASE_URL}/itinerary?session_id=${chat.session_id}`, {
          headers: { "Authorization": `Bearer ${token}` }
        });

        if (itinResponse.ok) {
          const itinData = await itinResponse.json();
          if (itinData.cities && itinData.cities.length > 0) {
            // Add markers for cities (would need geocoding API for real coordinates)
            // For now, show the data is available
            updateMapInfo(`🗺️ ${itinData.cities.length} destination(s) from your trips`);
          }
        }
      } catch (err) {
        console.error('Error loading itinerary for chat:', err);
      }
    }
  } catch (err) {
    console.error('Error loading trip locations:', err);
  }
}

function updateMapInfo(message) {
  const mapInfo = document.getElementById('mapInfo');
  if (mapInfo) {
    mapInfo.innerHTML = `<p class="map-hint">${message}</p>`;
  }
}

// =============================
// TRANSPORT & STAY RECOMMENDATIONS
// =============================
async function loadTransportRecommendations() {
  const transportPlaceholder = document.getElementById('transportPlaceholder');
  const transportContent = document.getElementById('transportContent');
  const transportLoading = document.getElementById('transportLoading');

  try {
    // Show loading
    if (transportPlaceholder) transportPlaceholder.classList.add('hidden');
    if (transportLoading) transportLoading.classList.remove('hidden');

    const token = await getIdToken();

    // Get user's recent itineraries
    const response = await fetch(`${API_BASE_URL}/chats`, {
      headers: { "Authorization": `Bearer ${token}` }
    });

    if (!response.ok) throw new Error('Failed to fetch chats');

    const chats = await response.json();

    if (chats.length === 0) {
      // No trips yet
      if (transportLoading) transportLoading.classList.add('hidden');
      if (transportPlaceholder) transportPlaceholder.classList.remove('hidden');
      return;
    }

    // Get itinerary for most recent chat
    const mostRecent = chats[0];
    const itinResponse = await fetch(`${API_BASE_URL}/itinerary?session_id=${mostRecent.session_id}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });

    if (itinResponse.ok) {
      const itinData = await itinResponse.json();
      displayTransportOptions(itinData);
      if (transportLoading) transportLoading.classList.add('hidden');
      if (transportContent) transportContent.classList.remove('hidden');
    } else {
      // No itinerary available
      if (transportLoading) transportLoading.classList.add('hidden');
      if (transportPlaceholder) transportPlaceholder.classList.remove('hidden');
    }
  } catch (err) {
    console.error('Error loading transport recommendations:', err);
    if (transportLoading) transportLoading.classList.add('hidden');
    if (transportPlaceholder) transportPlaceholder.classList.remove('hidden');
  }
}

async function displayTransportOptions(itineraryData) {
  console.log('🎬 displayTransportOptions called with:', itineraryData);
  
  const transportOptions = document.getElementById('transportOptions');
  const stayOptions = document.getElementById('stayOptions');
  const transportPlaceholder = document.getElementById('transportPlaceholder');
  const transportContent = document.getElementById('transportContent');
  const transportLoading = document.getElementById('transportLoading');

  console.log('📦 DOM elements found:', {
    transportOptions: !!transportOptions,
    stayOptions: !!stayOptions,
    transportPlaceholder: !!transportPlaceholder,
    transportContent: !!transportContent,
    transportLoading: !!transportLoading
  });

  if (!transportOptions || !stayOptions) {
    console.error('❌ Required DOM elements not found!');
    return;
  }

  // Extract trip details from itinerary data
  const destination = itineraryData?.destination || itineraryData?.cities?.[0];
  const departure = itineraryData?.departure_location || 'HYD';
  const startDate = itineraryData?.start_date || itineraryData?.startDate;

  console.log('📍 Extracted travel details:', { destination, departure, startDate });

  if (!destination || !startDate) {
    console.warn('⚠️ Missing destination or start date for transport search');
    return;
  }

  // Show loading state
  if (transportPlaceholder) transportPlaceholder.classList.add('hidden');
  if (transportContent) transportContent.classList.add('hidden');
  if (transportLoading) transportLoading.classList.remove('hidden');

  try {
    const token = await getIdToken();

    // Trigger n8n workflow for transport search
    console.log('🚀 Triggering transport search:', { departure, destination, startDate });
    
    const transportResponse = await fetch(`${API_BASE_URL}/travel/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        type: 'flight',
        origin: departure,
        destination: destination,
        date: startDate,
        passengers: itineraryData?.travelers || 1
      })
    });

    if (!transportResponse.ok) {
      throw new Error(`Transport search failed: ${transportResponse.status}`);
    }

    const transportData = await transportResponse.json();
    console.log('✅ Transport API response:', transportData);
    console.log('  ✈️ Flights:', transportData.flights?.length || 0);
    console.log('  🚄 Trains:', transportData.trains?.length || 0);
    console.log('  🚌 Buses:', transportData.buses?.length || 0);
    console.log('  🏨 Hotels:', transportData.hotels?.length || 0);

    // Store transport data for PDF generation
    latestTransportData = {
      flights: transportData.flights || [],
      trains: transportData.trains || [],
      buses: transportData.buses || [],
      hotels: transportData.hotels || []
    };
    
    console.log('💾 Stored transport data:', latestTransportData);

    // Hide loading, show content
    if (transportLoading) transportLoading.classList.add('hidden');
    if (transportContent) transportContent.classList.remove('hidden');

    // Combine all transport options from workflow (flights, trains, buses)
    const allTransportOptions = [];
    
    // Add flights
    if (transportData.flights && transportData.flights.length > 0) {
      transportData.flights.forEach(flight => {
        allTransportOptions.push({
          type: 'flight',
          title: flight.airline || flight.flight_number || '✈️ Flight',
          details: `${flight.departure_airport || ''} → ${flight.arrival_airport || ''}`,
          price: flight.price || 'Check availability',
          link: flight.booking_link,
          status: flight.status
        });
      });
    }
    
    // Add trains
    if (transportData.trains && transportData.trains.length > 0) {
      transportData.trains.forEach(train => {
        allTransportOptions.push({
          type: 'train',
          title: train.name || '🚄 Train',
          details: train.duration || '',
          price: train.price || 'Check availability',
          link: train.booking_link
        });
      });
    }
    
    // Add buses
    if (transportData.buses && transportData.buses.length > 0) {
      transportData.buses.forEach(bus => {
        allTransportOptions.push({
          type: 'bus',
          title: bus.name || '🚌 Bus',
          details: bus.duration || '',
          price: bus.price || 'Check availability',
          link: bus.booking_link
        });
      });
    }

    // Render transport options with creative styling
    if (allTransportOptions.length > 0) {
      transportOptions.innerHTML = allTransportOptions.slice(0, 6).map(option => {
        // Determine icon based on type
        let icon = '✈️';
        if (option.type === 'train') icon = '🚄';
        if (option.type === 'bus') icon = '🚌';
        
        return `
          <div class="option-card" data-type="${option.type}">
            <h4 class="option-title">${icon} ${option.title}</h4>
            <p class="option-details">${option.details}</p>
            ${option.status ? `<span class="status-badge">${option.status}</span>` : ''}
            <p class="option-price">${option.price}</p>
            ${option.link ? `<a href="${option.link}" target="_blank" class="booking-link">Book Now →</a>` : '<button class="booking-link" onclick="alert(\'Booking link not available\')">Check Availability</button>'}
          </div>
        `;
      }).join('');
    } else {
      transportOptions.innerHTML = '<div class="no-results">🔍 No transport options found. We\'re working on getting the best deals for you!</div>';
    }

    // Render hotel options from workflow results with creative styling
    if (transportData.hotels && transportData.hotels.length > 0) {
      const hotelCards = transportData.hotels.slice(0, 4).map(hotel => `
        <div class="option-card" data-type="hotel">
          <h4 class="option-title">🏨 ${hotel.name || 'Hotel'}</h4>
          <p class="option-details">${hotel.duration || 'Comfortable accommodation'}</p>
          <p class="option-price">${hotel.price || 'Check availability'}</p>
          ${hotel.booking_link ? `<a href="${hotel.booking_link}" target="_blank" class="booking-link">Book Now →</a>` : '<button class="booking-link" onclick="alert(\'Booking link not available\')">Check Availability</button>'}
        </div>
      `).join('');
      
      stayOptions.innerHTML = hotelCards + `
        <div class="option-card" data-type="search" style="background:linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);">
          <h4 class="option-title">🔍 More Options</h4>
          <p class="option-details">Explore additional accommodations</p>
          <p class="option-price" style="background:linear-gradient(135deg, #059669 0%, #10b981 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Best deals await</p>
          <button onclick="window.open('https://www.booking.com/searchresults.html?ss=${encodeURIComponent(destination)}&checkin=${startDate}', '_blank')" class="booking-link">Booking.com →</button>
        </div>
      `;
    } else {
      // Fallback to search links if no hotels from workflow - make it attractive
      stayOptions.innerHTML = `
        <div class="option-card" data-type="search" style="background:linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);">
          <h4 class="option-title">🏨 Hotels in ${destination}</h4>
          <p class="option-details">Discover comfortable stays for your journey</p>
          <p class="option-price" style="background:linear-gradient(135deg, #d97706 0%, #f59e0b 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Best Price Guarantee</p>
          <button onclick="window.open('https://www.booking.com/searchresults.html?ss=${encodeURIComponent(destination)}&checkin=${startDate}', '_blank')" class="booking-link" style="background:linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">Search Booking.com →</button>
        </div>
        <div class="option-card" data-type="search" style="background:linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);">
          <h4 class="option-title">🏡 Airbnb Rentals</h4>
          <p class="option-details">Find unique homes and experiences</p>
          <p class="option-price" style="background:linear-gradient(135deg, #dc2626 0%, #ef4444 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Local & Authentic</p>
          <button onclick="window.open('https://www.airbnb.com/s/${encodeURIComponent(destination)}', '_blank')" class="booking-link" style="background:linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">Search Airbnb →</button>
        </div>
        <div class="option-card" data-type="search" style="background:linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);">
          <h4 class="option-title">🏢 More Platforms</h4>
          <p class="option-details">Compare prices across multiple booking sites</p>
          <p class="option-price" style="background:linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Save up to 30%</p>
          <button onclick="window.open('https://www.kayak.com/hotels/' + encodeURIComponent('${destination}'), '_blank')" class="booking-link" style="background:linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);">Compare Prices →</button>
        </div>
      `;
    }

  } catch (error) {
    console.error('Error fetching transport options:', error);
    
    // Show error state
    if (transportLoading) transportLoading.classList.add('hidden');
    if (transportPlaceholder) {
      transportPlaceholder.classList.remove('hidden');
      transportPlaceholder.innerHTML = `
        <div class="placeholder-icon">⚠️</div>
        <p>Unable to load transport options</p>
        <p class="placeholder-hint">${error.message || 'Please check your connection and try again'}</p>
      `;
    }
  }
}

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  event.preventDefault();

  // Show user-friendly error message
  const errorNotification = document.createElement('div');
  errorNotification.className = 'error-notification';
  errorNotification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #ff4444;
    color: white;
    padding: 16px 24px;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    z-index: 10000;
    animation: slideIn 0.3s ease;
  `;
  errorNotification.innerHTML = `
    <strong>⚠️ Error:</strong> ${event.reason?.message || "Something went wrong"}
  `;
  document.body.appendChild(errorNotification);

  // Remove after 5 seconds
  setTimeout(() => {
    errorNotification.remove();
  }, 5000);
});

// =============================
// TRAVEL SEARCH INTEGRATION
// =============================
window.searchTravel = async function () {
  const user = auth.currentUser;
  if (!user) {
    console.error("User not signed in");
    return;
  }
  const token = await user.getIdToken();

  const body = {
    type: "flight",
    origin: "DEL",
    destination: "BOM",
    date: "2025-02-11",
    passengers: 1
  };

  try {
    const response = await fetch("http://127.0.0.1:8000/travel/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(body)
    });

    const data = await response.json();
    console.log("Travel Search Results:", data);
    if (window.renderTravelResults) {
      window.renderTravelResults(data.results);
    } else {
      console.warn("renderTravelResults function not found. Results:", data.results);
    }
  } catch (error) {
    console.error("Travel search failed:", error);
  }
}

// =============================
// ACCOMMODATION SEARCH INTEGRATION
// =============================
window.searchAccommodations = async function (location, checkinDate, checkoutDate, adults = 2, rooms = 1) {
  const user = auth.currentUser;
  if (!user) {
    console.error("User not signed in");
    return null;
  }

  try {
    const token = await user.getIdToken();

    const body = {
      location: location,
      checkin_date: checkinDate,
      checkout_date: checkoutDate,
      adults: adults,
      children: 0,
      room_qty: rooms,
      units: "metric",
      currency: "USD",
      locale: "en-us"
    };

    const response = await fetch("http://127.0.0.1:8000/accommodations/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      throw new Error(`Search failed: ${response.statusText}`);
    }

    const data = await response.json();
    console.log("Accommodation Search Results:", data);
    return data.results;
  } catch (error) {
    console.error("Accommodation search failed:", error);
    return null;
  }
}

window.getPopularAccommodations = async function (location) {
  const user = auth.currentUser;
  if (!user) {
    console.error("User not signed in");
    return null;
  }

  try {
    const token = await user.getIdToken();

    const response = await fetch(`http://127.0.0.1:8000/accommodations/popular/${encodeURIComponent(location)}`, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to get popular accommodations: ${response.statusText}`);
    }

    const data = await response.json();
    console.log("Popular Accommodations:", data);
    return data.results;
  } catch (error) {
    console.error("Failed to get popular accommodations:", error);
    return null;
  }
}