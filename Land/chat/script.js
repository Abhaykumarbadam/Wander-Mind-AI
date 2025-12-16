// Import Firebase auth from firebase-init.js
import { auth } from "../firebase-init.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

// ==================== GLOBAL STATE ====================
let currentUser = null;
// Always start with null session for new landing page loads
let currentSessionId = null;
let currentChatId = null;
const API_BASE = "http://localhost:8000";
const PENDING_MESSAGE_KEY = "pendingMessage";
const PENDING_SESSION_KEY = "pendingSessionId";
const SESSION_STORAGE_KEY = "aura_session_id";

// ==================== DOM ELEMENTS ====================
const landingView = document.getElementById("landingView");
const chatInterface = document.getElementById("chatInterface");
const videoBackground = document.getElementById("videoBackground");
const landingInput = document.getElementById("landingInput");
const landingSendBtn = document.getElementById("landingSendBtn");
const chatInput = document.getElementById("chatInput");
const sendMessageBtn = document.getElementById("sendMessageBtn");
const chatMessages = document.getElementById("chatMessages");
const chatHistory = document.getElementById("chatHistory");
const newChatBtn = document.getElementById("newChatBtn");
const mapPanel = document.getElementById("mapPanel");
const closeMapBtn = document.getElementById("closeMapBtn");
const chatMain = document.getElementById("chatMain");
const loadingOverlay = document.getElementById("loadingOverlay");

// ==================== AUTH ====================
onAuthStateChanged(auth, (user) => {
    if (user) {
        currentUser = user;
        console.log("User authenticated:", user.uid);
        loadChatHistory();

        // Check for session_id in URL
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');
        if (sessionId) {
            console.log("Loading session from URL:", sessionId);
            loadChatById(null, sessionId);
        }
    } else {
        console.log("No user authenticated, redirecting to login");
        window.location.href = "/Land/loginPage/login.html";
    }
});

async function getAuthToken() {
    if (!currentUser) {
        throw new Error("No authenticated user");
    }
    return await currentUser.getIdToken();
}

// ==================== DEBUG TOOLS (added) ====================
window.debugItinerary = {
    logSessionState: () => {
        console.log("📊 Session State:");
        console.log("  currentSessionId:", currentSessionId);
        console.log("  localStorage session:", localStorage.getItem(SESSION_STORAGE_KEY));
        console.log("  sessionStorage pending:", sessionStorage.getItem(PENDING_SESSION_KEY));
        console.log("  currentUser:", currentUser?.uid);
    },
    testExtraction: (response) => {
        console.log("🧪 Testing extraction...");
        const result = extractTripFromResponse(response, window.currentProfile);
        console.log("Result:", result);
        return result;
    },
    testSync: async (sessionId) => {
        console.log("🧪 Testing sync for session:", sessionId);
        try {
            const token = await getAuthToken();
            const response = await fetch(`${API_BASE}/trips/sync-itinerary-to-trip?session_id=${sessionId}`, {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });
            const data = await response.json();
            console.log("✅ Sync result:", data);
            return data;
        } catch (error) {
            console.error("❌ Sync failed:", error);
        }
    }
};

console.log("🐛 Debug tools available: window.debugItinerary");

// ==================== API CALLS ====================
async function sendMessage(message, sessionId = null) {
    try {
        const token = await getAuthToken();
        const response = await fetch(`${API_BASE}/message`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                user_message: message,
                session_id: sessionId || currentSessionId || null
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error sending message:", error);
        throw error;
    }
}

async function generateItinerary(sessionId) {
    try {
        console.log("🚀 Calling /plan to generate itinerary...");
        // Show full-screen loading overlay
        if (loadingOverlay) loadingOverlay.classList.remove('hidden');

        const token = await getAuthToken();
        const response = await fetch(`${API_BASE}/plan`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });

        // Hide loading overlay
        if (loadingOverlay) loadingOverlay.classList.add('hidden');

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.message || "Failed to generate plan");
        }

        const data = await response.json();
        console.log("✅ Plan generated:", data);

        if (data.type === "ask_split") {
            addMessage('assistant', data.assistant_message);
        } else if (data.itinerary) {
            // Display the itinerary
            addMessage('assistant', data.itinerary);

            // Extract trip_id from response
            const tripId = data.trip_id || data._id;

            // Show notification with trip_id
            if (tripId) {
                showItineraryNotification(data.destination || "Your Trip", tripId);
            }

            // Update chat title with destination after plan is generated
            if (data.destination && sessionId) {
                await updateChatTitleWithDestination(sessionId, data.destination);
            }

            // Sync/Save it
            await checkAndCreateTripFromItinerary(data.itinerary, sessionId);
        }

        return data;
    } catch (error) {
        console.error("Error generating itinerary:", error);
        document.getElementById('loadingMessage')?.remove();
        addMessage('assistant', "I encountered an error while generating your itinerary. Please try again.");
        throw error;
    }
}

async function requestUserLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject("Geolocation is not supported by your browser");
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                resolve({
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                });
            },
            (error) => {
                reject(error.message);
            }
        );
    });
}

async function handleLocationRequest() {
    try {
        showLoadingMessage();
        const coords = await requestUserLocation();

        // Send location as a system/user message context
        const message = `My current location is: ${coords.lat}, ${coords.lng}`;
        addMessage('user', "📍 Shared current location");

        const response = await sendMessage(message, currentSessionId);
        hideLoadingMessage();
        addMessage('assistant', getAssistantReply(response));

    } catch (error) {
        hideLoadingMessage();
        addMessage('assistant', "I couldn't access your location. Please check your browser settings.");
        console.error("Location error:", error);
    }
}

async function loadChatHistory() {
    try {
        const token = await getAuthToken();
        const response = await fetch(`${API_BASE}/chats`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const chats = await response.json();
        renderChatHistory(chats);
    } catch (error) {
        console.error("Error loading chat history:", error);
        chatHistory.innerHTML = '<div class="history-loading"><p>Failed to load chats</p></div>';
    }
}

async function loadChatById(chatId, sessionId) {
    try {
        const token = await getAuthToken();
        const response = await fetch(`${API_BASE}/chat/${sessionId}`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const chatData = await response.json();

        // Switch to this session
        currentSessionId = sessionId;
        currentChatId = chatId;
        persistSession(sessionId);

        // Show chat interface if not already visible
        if (!chatMain || chatMain.classList.contains('hidden')) {
            // Transition from landing to chat with existing conversation
            landingView.classList.add('fade-out');
            videoBackground.classList.add('blurred');
            document.body.classList.add('chat-active');

            setTimeout(() => {
                landingView.classList.add('hidden');
                if (chatMain) chatMain.classList.remove('hidden');
                renderMessages(chatData.messages || []);

                // Store profile globally for itinerary extraction
                window.currentProfile = chatData.profile || {};
            }, 500);
        } else {
            renderMessages(chatData.messages || []);
            // Store profile globally for itinerary extraction
            window.currentProfile = chatData.profile || {};
        }
    } catch (error) {
        console.error("Error loading chat:", error);
    }
}

async function generateChatTitle(sessionId, firstMessage) {
    try {
        const token = await getAuthToken();
        const response = await fetch(`${API_BASE}/chat/title`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                session_id: sessionId,
                first_message: firstMessage
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data.title;
    } catch (error) {
        console.error("Error generating title:", error);
        return "New Chat";
    }
}

async function updateChatTitleWithDestination(sessionId, destination) {
    try {
        console.log("📝 Updating chat title with destination:", destination);
        const token = await getAuthToken();
        const newTitle = `Trip to ${destination}`;
        
        const response = await fetch(`${API_BASE}/chat/update-title`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                session_id: sessionId,
                title: newTitle
            })
        });

        if (response.ok) {
            console.log("✅ Chat title updated successfully");
            // Refresh chat history to show updated title
            await loadChatHistory();
        }
    } catch (error) {
        console.error("❌ Error updating chat title:", error);
        // Non-critical, don't show error to user
    }
}

// ==================== UI RENDERING ====================
function renderChatHistory(chats) {
    if (!chats || chats.length === 0) {
        chatHistory.innerHTML = '<div class="history-loading"><p>No previous chats</p></div>';
        return;
    }

    chatHistory.innerHTML = chats.map(chat => {
        // Get a meaningful title (not just "Travel Planning chat")
        const chatTitle = chat.title && chat.title !== 'Travel Planning chat' && chat.title !== 'New Chat'
            ? escapeHtml(chat.title)
            : escapeHtml(chat.title || 'Untitled Chat');

        // Format date nicely
        const dateText = formatDate(chat.updated_at || chat.created_at);

        // Check if this is the currently active session
        const isActive = chat.session_id === currentSessionId;

        return `
            <div class="history-item ${isActive ? 'active' : ''}" 
                 data-chat-id="${chat._id}" 
                 data-session-id="${chat.session_id}">
                <div class="history-item-content">
                    <div class="history-item-header">
                        <div class="history-item-title">${chatTitle}</div>
                        <button class="delete-chat-btn" 
                                data-chat-id="${chat._id}" 
                                data-session-id="${chat.session_id}"
                                title="Delete chat"
                                aria-label="Delete this chat"
                                onclick="event.stopPropagation()">
                            <svg viewBox="0 0 24 24" width="16" height="16">
                                <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>
                            </svg>
                        </button>
                    </div>
                    <div class="history-date">${dateText}</div>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers for chat items
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            const chatId = item.dataset.chatId;
            const sessionId = item.dataset.sessionId;
            loadChatById(chatId, sessionId);

            // Update active state
            document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');

            // Close sidebar on mobile after selection
            if (window.innerWidth <= 968) {
                chatSidebar.classList.remove('open');
            }
        });
    });

    // Add click handlers for delete buttons
    document.querySelectorAll('.delete-chat-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const chatId = btn.dataset.chatId;
            const sessionId = btn.dataset.sessionId;

            // Confirm deletion
            if (confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
                await deleteChat(sessionId);
            }
        });
    });
}

// Function to delete a chat
async function deleteChat(sessionId) {
    // Remove from UI immediately
    const chatItems = document.querySelectorAll('.history-item');
    chatItems.forEach(item => {
        if (item.dataset.sessionId === sessionId) {
            item.style.opacity = '0';
            item.style.transform = 'translateX(-20px)';
            setTimeout(() => item.remove(), 300);
        }
    });

    // If deleted chat was current, start new chat
    if (sessionId === currentSessionId) {
        setTimeout(() => {
            startNewChat();
        }, 300);
    }

    // Try to delete from backend (fail silently)
    try {
        const token = await getAuthToken();
        await fetch(`${API_BASE}/chat/${sessionId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        console.log('Chat deleted from backend successfully');
    } catch (error) {
        console.error('Backend delete failed (UI already updated):', error);
        // Don't show error to user since UI is already updated
    }
}

function renderMessages(messages) {
    chatMessages.innerHTML = '';

    messages.forEach(msg => {
        const messageEl = createMessageElement(msg.role, msg.content);
        chatMessages.appendChild(messageEl);
    });

    scrollToBottom();
}

function createMessageElement(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Support basic markdown-style formatting
    let formattedContent = content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold
        .replace(/\n/g, '<br>'); // Line breaks

    contentDiv.innerHTML = formattedContent;

    messageDiv.appendChild(contentDiv);

    return messageDiv;
}

function addMessage(role, content) {
    const messageEl = createMessageElement(role, content);
    chatMessages.appendChild(messageEl);
    scrollToBottom();
}

function showLoadingMessage() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant';
    loadingDiv.id = 'loadingMessage';

    const loadingContent = document.createElement('div');
    loadingContent.className = 'message-loading';
    loadingContent.innerHTML = `
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
    `;

    loadingDiv.appendChild(loadingContent);
    chatMessages.appendChild(loadingDiv);
    scrollToBottom();
}

function hideLoadingMessage() {
    const loadingMsg = document.getElementById('loadingMessage');
    if (loadingMsg) {
        loadingMsg.remove();
    }
}

function displayWelcomeMessage() {
    const welcomeText = "👋 Hello! I'm Aura, your AI travel companion. I'm here to help you plan the perfect trip! Tell me about your travel dreams, and I'll create a personalized itinerary just for you. ✈️🌍";
    addMessage('assistant', welcomeText);
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    if (diffMins < 10080) return `${Math.floor(diffMins / 1440)}d ago`;

    return date.toLocaleDateString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function persistSession(sessionId) {
    if (sessionId && sessionId !== "null") {
        currentSessionId = sessionId;
        localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    } else {
        currentSessionId = null;
        localStorage.removeItem(SESSION_STORAGE_KEY);
    }
}

// ==================== SESSION MANAGEMENT ====================
function startNewChat() {
    // Clear current session
    currentSessionId = null;
    currentChatId = null;
    localStorage.removeItem(SESSION_STORAGE_KEY);

    // Clear chat messages
    chatMessages.innerHTML = '';

    // Reset to landing view
    if (chatMain) chatMain.classList.add('hidden');
    landingView.classList.remove('hidden', 'fade-out');

    // Reset blur effects
    document.body.classList.remove('chat-active');
    videoBackground.classList.remove('blurred');

    // Clear inputs
    landingInput.value = '';
    chatInput.value = '';

    // Update active state in history
    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));

    console.log('Started new chat session');
}

function createNewSession() {
    // This will be called when sending the first message
    // The backend will create a new session automatically when session_id is null
    currentSessionId = null;
    return null;
}

function getAssistantReply(payload = {}) {
    return payload.response ?? payload.message ?? payload.assistant_message ?? "I'm here to help!";
}

/**
 * CHECK + SYNC: Auto-detect itinerary in LLM response and sync to trips
 *
 * Called AFTER LLM response is received.
 * Responsibilities:
 *  - Detect itinerary patterns
 *  - Ensure session_id persisted (MUST be persisted before calling this)
 *  - Extract trip info robustly
 *  - Call /trips/sync-itinerary-to-trip (idempotent)
 *  - Add lightweight UI notification
 */
async function checkAndCreateTripFromItinerary(assistantResponse, sessionId) {
    try {
        console.log("🔍 Checking for itinerary in response...");
        console.log("Session ID:", sessionId);

        if (!assistantResponse || assistantResponse.trim().length < 20) {
            console.log("ℹ️ Assistant response too short, skipping itinerary check.");
            return;
        }

        // Look for itinerary patterns (flexible)
        const itineraryPatterns = [
            /###\s+.+Trip[:\s]/i,
            /#\s+.+Itinerary/i,
            /Day\s+\d+[:\s]/i,
            /\bItinerary\b/i,
            /\bDay \d+\b/i
        ];

        const hasItinerary = itineraryPatterns.some(pattern => pattern.test(assistantResponse));

        if (!hasItinerary) {
            console.log("ℹ️ No itinerary detected in response");
            return;
        }

        console.log("✅ Itinerary detected!");

        // Ensure session ID exists (critical)
        if (!sessionId) {
            // Try fallback to persisted session
            sessionId = localStorage.getItem(SESSION_STORAGE_KEY) || null;
            if (!sessionId) {
                console.error("❌ Cannot save itinerary: No session ID available (both param and persisted are null)");
                return;
            } else {
                console.log("⚠️ Using persisted sessionId fallback:", sessionId);
            }
        }

        // Extract trip information
        const tripInfo = extractTripFromResponse(assistantResponse, window.currentProfile || {});

        if (!tripInfo) {
            console.warn("⚠️ Could not extract trip information from itinerary text");
            return;
        }

        // Create or sync trip (idempotent)
        try {
            const syncResult = await createTripFromItinerary(tripInfo, sessionId);
            console.log("✅ createTripFromItinerary result:", syncResult);
            // Refresh UI: load chat history and optionally map
            await loadChatHistory();
            showItineraryNotification(tripInfo.location);
        } catch (syncErr) {
            console.error("❌ Sync failed:", syncErr);
        }

    } catch (error) {
        console.error("❌ Error processing itinerary:", error);
        // background task — don't break user flow
    }
}

/**
 * Extract trip information from LLM itinerary response
 *
 * Returns object:
 * {
 *   location: "string",
 *   start_date: "YYYY-MM-DD",
 *   end_date: "YYYY-MM-DD",
 *   cities: ["city1", "city2"],
 *   notes: "string",
 *   accommodation: "string or null",
 *   itinerary_text: "full response"
 * }
 */
function extractTripFromResponse(response, profile = {}) {
    try {
        console.log("🔍 Extracting trip from response...");
        response = typeof response === 'string' ? response : JSON.stringify(response || '');

        let structuredData = null;
        // Try to extract JSON block
        const jsonMatch = response.match(/```json\s*(\{[\s\S]*?\})\s*```/);
        if (jsonMatch) {
            try {
                structuredData = JSON.parse(jsonMatch[1]);
                console.log("✅ Found structured JSON in response");
            } catch (e) {
                console.warn("⚠️ Failed to parse JSON block:", e);
            }
        }

        // ... (keep existing regex fallback for basic fields if JSON fails or is partial) ...

        // Destination extraction patterns
        const destinationPatterns = [
            /###\s*(.+?)\s+Trip[:\s]/i,
            /#\s*(.+?)\s+Itinerary/i,
            /trip to\s+([A-Z][a-zA-Z\s-]{2,50})/i,
            /itinerary for\s+([A-Z][a-zA-Z\s-]{2,50})/i,
            /visiting\s+([A-Z][a-zA-Z\s-]{2,50})/i,
            /travel to\s+([A-Z][a-zA-Z\s-]{2,50})/i
        ];

        let destination = structuredData?.location || null;
        if (!destination) {
            for (const p of destinationPatterns) {
                const m = response.match(p);
                if (m && m[1]) {
                    destination = m[1].trim().replace(/[\*\_]+/g, '').split(/,|\(|\//)[0].trim();
                    break;
                }
            }
        }

        // ... (rest of regex fallback) ...

        if (!destination) {
            // As a fallback try to get a capitalized first word sequence after "to"
            const fallback = response.match(/to\s+([A-Z][a-zA-Z\s]{2,40})/);
            if (fallback) destination = fallback[1].trim();
        }

        if (!destination) {
            console.warn("❌ No destination found in response");
            return null;
        }

        // Cities
        const cities = structuredData?.cities || [destination];

        // Dates
        let startDate = structuredData?.start_date || null;
        let endDate = structuredData?.end_date || null;

        if (!startDate || !endDate) {
            // Date extraction: try multiple patterns
            let m = response.match(/(\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})/);
            if (m) {
                startDate = m[1];
                endDate = m[2];
            } else {
                // Try profile
                if (profile && profile.start_date && profile.end_date) {
                    startDate = profile.start_date;
                    endDate = profile.end_date;
                }
            }
        }

        // Default dates if still missing
        if (!startDate || !endDate) {
            const today = new Date();
            const s = new Date(today);
            s.setDate(s.getDate() + 7);
            const e = new Date(s);
            e.setDate(e.getDate() + 6);
            const toIso = d => d.toISOString().split('T')[0];
            startDate = startDate || toIso(s);
            endDate = endDate || toIso(e);
        }
        // Fallback extraction for inner locations if JSON missing
        let innerLocations = structuredData?.inner_locations || [];
        if (innerLocations.length === 0) {
            // Extract capitalized words after "Visit", "Explore", "at"
            const locRegex = /(?:visit|explore|at|to)\s+([A-Z][a-zA-Z\s]{2,30})/g;
            let match;
            const seen = new Set();
            while ((match = locRegex.exec(response)) !== null) {
                const loc = match[1].trim();
                if (loc && !seen.has(loc) && loc !== destination && !['Morning', 'Afternoon', 'Evening', 'The', 'A'].includes(loc)) {
                    seen.add(loc);
                    innerLocations.push({ name: loc });
                }
            }
        }

        // Fallback extraction for days if JSON missing
        let days = structuredData?.days || [];
        if (days.length === 0) {
            const lines = response.split('\n');
            let currentDay = null;
            lines.forEach(line => {
                const dayMatch = line.match(/^(?:\*\*|#+\s*)?Day\s+(\d+)(?::|\s|[-–])*(.*)/i);
                if (dayMatch) {
                    if (currentDay) days.push(currentDay);
                    currentDay = {
                        day: parseInt(dayMatch[1]),
                        title: dayMatch[2].replace(/\*\*/g, '').trim() || 'Explore',
                        activities: []
                    };
                } else if (currentDay) {
                    const trimmed = line.trim();
                    if (trimmed && trimmed.match(/^[\s-]*[\*\-]\s+/)) {
                        currentDay.activities.push({
                            description: trimmed.replace(/^[\s-]*[\*\-]\s+/, '').replace(/\*\*/g, ''),
                            place: 'Activity',
                            time: 'Anytime'
                        });
                    }
                }
            });
            if (currentDay) days.push(currentDay);
        }

        const tripInfo = {
            location: destination,
            start_date: startDate,
            end_date: endDate,
            notes: response, // Store full response as notes/itinerary_text
            accommodation: structuredData?.accommodation || null,
            itinerary_text: response,
            cities: cities,
            // New structured fields
            days: structuredData?.days || [],
            inner_locations: innerLocations,
            budget_inr: structuredData?.budget_inr || null,
            duration: structuredData?.duration || null
        };

        console.log("✅ Trip info extracted successfully:", tripInfo);
        return tripInfo;
    } catch (error) {
        console.error("❌ Error extracting trip info:", error);
        return null;
    }
}

/**
 * createTripFromItinerary
 *
 *  - Ensures sessionId present
 *  - Calls /trips/sync-itinerary-to-trip (idempotent)
 *  - Handles auth + errors
 */
async function createTripFromItinerary(tripInfo, sessionId) {
    try {
        console.log("💾 Creating trip from itinerary...");
        console.log("Session ID:", sessionId);
        console.log("Trip payload preview:", {
            location: tripInfo.location,
            start_date: tripInfo.start_date,
            end_date: tripInfo.end_date,
            cities: tripInfo.cities
        });

        if (!tripInfo.location || !tripInfo.start_date || !tripInfo.end_date) {
            throw new Error("Missing required trip fields (location/start_date/end_date)");
        }

        // ensure sessionId
        if (!sessionId) {
            sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
            if (!sessionId) throw new Error("Session ID missing - cannot sync itinerary");
            console.log("Using persisted sessionId in createTripFromItinerary:", sessionId);
        }

        const token = await getAuthToken();

        // Prepare complete payload with ALL structured fields
        const body = {
            session_id: sessionId,
            itinerary_text: tripInfo.itinerary_text,
            cities: tripInfo.cities,
            start_date: tripInfo.start_date,
            end_date: tripInfo.end_date,
            location: tripInfo.location,
            notes: tripInfo.notes,
            accommodation: tripInfo.accommodation,
            // NEW: Include structured fields
            days: tripInfo.days || [],
            inner_locations: tripInfo.inner_locations || [],
            budget_inr: tripInfo.budget_inr || null,
            duration: tripInfo.duration || null
        };

        console.log("📤 Saving complete itinerary with structured data:", {
            location: body.location,
            days_count: body.days.length,
            inner_locations_count: body.inner_locations.length,
            budget: body.budget_inr
        });

        // 1. Save Itinerary First (Explicit Save)
        const saveUrl = `${API_BASE}/trips/itinerary/save`;
        const saveResp = await fetch(saveUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(body)
        });

        if (!saveResp.ok) {
            const errText = await saveResp.text();
            console.warn("⚠️ Itinerary save failed, but trying sync anyway...", errText);
        } else {
            console.log("✅ Itinerary saved successfully");
        }

        // 2. Sync Trip (Idempotent) - Send same complete payload
        const syncUrl = `${API_BASE}/trips/sync-itinerary-to-trip?session_id=${encodeURIComponent(sessionId)}`;
        console.log("📡 POST", syncUrl);

        const resp = await fetch(syncUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(body)
        });

        if (!resp.ok) {
            const txt = await resp.text();
            console.error("❌ Server returned error:", resp.status, txt);
            throw new Error(`Sync failed: ${resp.status} ${txt}`);
        }

        const data = await resp.json();
        console.log("✅ Trip sync response:", data);
        return data;
    } catch (error) {
        console.error("❌ Error creating trip from itinerary:", error);
        // Don't throw further in background tasks; bubble up for debugging
        throw error;
    }
}

function showItineraryNotification(destination, tripId) {
    // Create a subtle notification
    const notification = document.createElement('div');
    notification.className = 'itinerary-notification';
    notification.innerHTML = `
        <div class="notification-content">
            <div class="notification-icon">🎯</div>
            <div class="notification-text">
                <strong>Trip Added!</strong>
                <span>${escapeHtml(destination)} has been added to your travel itinerary</span>
            </div>
            <button class="view-itinerary-btn" id="viewItineraryBtn">View Journey</button>
        </div>
    `;

    document.body.appendChild(notification);

    document.getElementById("viewItineraryBtn")?.addEventListener("click", () => {
        // Navigate with trip_id parameter
        const url = tripId
            ? `/Land/itinerary/index.html?trip_id=${encodeURIComponent(tripId)}`
            : '/Land/itinerary/index.html';
        window.open(url, '_blank');
    });

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                notification.parentNode.removeChild(notification);
            }, 300);
        }
    }, 5000);
}

// ==================== MAIN CHAT HANDLER ====================

async function handleSendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    // Check for location keyword
    if (message.toLowerCase().includes("share my location") || message.toLowerCase().includes("use my current location")) {
        chatInput.value = '';
        handleLocationRequest();
        return;
    }

    // Clear input
    chatInput.value = '';

    // Display user message
    addMessage('user', message);

    // Show loading animation
    showLoadingMessage();

    try {
        // Send message
        const response = await sendMessage(message, currentSessionId);

        // Hide loading animation
        hideLoadingMessage();

        // CRITICAL: Persist session FIRST, before anything else
        if (response?.session_id) {
            console.log("📌 Persisting session_id FIRST:", response.session_id);
            persistSession(response.session_id);
            console.log("✓ Session persisted. currentSessionId is now:", currentSessionId);
        } else {
            console.warn("⚠️ Response did not include session_id!");
        }

        // Display assistant response
        addMessage('assistant', getAssistantReply(response));

        // Check for explicit action from Aura V2
        if (response.action === "generate_itinerary") {
            console.log("🚀 Action: generate_itinerary detected!");
            await generateItinerary(response.session_id || currentSessionId);
        }

        // NOW check for itinerary and create trip (session is guaranteed to be persisted)
        console.log("🔍 Checking for itinerary in response...");
        await checkAndCreateTripFromItinerary(getAssistantReply(response), response?.session_id || currentSessionId);

        // Update chat history
        await loadChatHistory();

        // Check if we should show map
        checkForMapTrigger(getAssistantReply(response));

    } catch (error) {
        console.error("Error:", error);
        hideLoadingMessage();
        addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
    }
}

// ==================== EVENT HANDLERS (session timing fixes applied) ====================
console.log("Setting up event listeners...");
console.log("landingSendBtn:", landingSendBtn);
console.log("landingInput:", landingInput);

landingSendBtn.addEventListener('click', async () => {
    console.log("Landing send button clicked!");
    const message = landingInput.value.trim();
    console.log("Message:", message);
    if (!message) {
        console.log("No message, returning");
        return;
    }

    // Transition to chat interface with blur effect
    landingView.classList.add('fade-out');
    videoBackground.classList.add('blurred');

    // Add blur to body for better focus on chat
    document.body.classList.add('chat-active');

    // Clear landing input
    landingInput.value = '';

    setTimeout(async () => {
        landingView.classList.add('hidden');
        if (chatMain) chatMain.classList.remove('hidden');

        // Display user message after interface is visible
        addMessage('user', message);

        // Show loading animation
        showLoadingMessage();

        try {
            // Send message and create or continue session
            const response = await sendMessage(message, currentSessionId);

            // Hide loading animation
            hideLoadingMessage();

            // CRITICAL: Persist session FIRST, before anything else
            if (response?.session_id) {
                console.log("📌 Persisting session_id FIRST (landing):", response.session_id);
                persistSession(response.session_id);
                console.log("✓ Session persisted. currentSessionId is now:", currentSessionId);
            } else {
                console.warn("⚠️ Response did not include session_id!");
            }

            // Display assistant response
            addMessage('assistant', getAssistantReply(response));

            // Check for explicit action from Aura V2
            if (response.action === "generate_itinerary") {
                console.log("🚀 Action: generate_itinerary detected (landing)!");
                await generateItinerary(response.session_id || currentSessionId);
            }

            // NOW check if response contains an itinerary and auto-create trip
            console.log("🔍 Checking for itinerary in response (landing)...");
            await checkAndCreateTripFromItinerary(getAssistantReply(response), response?.session_id || currentSessionId);

            // Generate and save chat title
            if (currentSessionId) {
                await generateChatTitle(currentSessionId, message);
                currentChatId = `${currentUser.uid}_${currentSessionId}`;
            }

            // Reload chat history
            await loadChatHistory();

            // Check if we should show map
            // Check if we should show map
            checkForMapTrigger(getAssistantReply(response));
        } catch (error) {
            console.error("Error:", error);
            hideLoadingMessage();
            addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        }
    }, 500);
});

sendMessageBtn.addEventListener('click', async () => {
    await handleSendMessage();
});

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
    }
});

// Location button listener
const shareLocationBtn = document.getElementById('shareLocationBtn');
if (shareLocationBtn) {
    shareLocationBtn.addEventListener('click', handleLocationRequest);
}


// Sidebar toggle functionality
const hamburgerBtn = document.getElementById("hamburgerBtn");
const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
const floatingHistoryBtn = document.getElementById("floatingHistoryBtn");
const chatSidebar = document.getElementById("chatSidebar");

// Function to toggle sidebar
function toggleSidebar() {
    chatSidebar.classList.toggle('open');
}

// Hamburger button in header
if (hamburgerBtn) {
    hamburgerBtn.addEventListener('click', toggleSidebar);
}

// Toggle button inside sidebar
if (sidebarToggleBtn) {
    sidebarToggleBtn.addEventListener('click', () => {
        chatSidebar.classList.remove('open');
    });
}

// Floating history button
if (floatingHistoryBtn) {
    floatingHistoryBtn.addEventListener('click', toggleSidebar);
}

// Close sidebar when clicking outside (optional)
document.addEventListener('click', (e) => {
    if (chatSidebar.classList.contains('open') && 
        !chatSidebar.contains(e.target) && 
        !hamburgerBtn.contains(e.target) && 
        !floatingHistoryBtn.contains(e.target)) {
        chatSidebar.classList.remove('open');
    }
});

newChatBtn.addEventListener('click', () => {
    startNewChat();
});

// Itinerary button
const itineraryBtn = document.getElementById("itineraryBtn");
if (itineraryBtn) {
    itineraryBtn.addEventListener('click', () => {
        window.location.href = '/Land/itinerary/index.html';
    });
}

closeMapBtn.addEventListener('click', () => {
    mapPanel.classList.add('hidden');
    chatInterface.classList.remove('with-map');
});

// Suggestion buttons
document.querySelectorAll('.suggestion-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const prompt = btn.dataset.prompt;
        landingInput.value = prompt;
        landingInput.focus();
    });
});

// Auto-resize textareas
[landingInput, chatInput].forEach(textarea => {
    textarea.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
});

// Enter key to send message (Shift+Enter for new line)
landingInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        landingSendBtn.click();
    }
});

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessageBtn.click();
    }
});

// ==================== MAP TRIGGER ====================
function checkForMapTrigger(message) {
    const mapTriggers = [
        'would you like to see the itinerary',
        'visualize the maps',
        'see the map',
        'view on map'
    ];

    const itineraryTriggers = [
        'show my travel itinerary',
        'see my trips',
        'view my itinerary',
        'travel journey',
        'my travel plans',
        'planned trips',
        'trip history'
    ];

    const lowerMessage = (message || '').toLowerCase();
    const shouldShowMap = mapTriggers.some(trigger => lowerMessage.includes(trigger));
    const shouldShowItinerary = itineraryTriggers.some(trigger => lowerMessage.includes(trigger));

    if (shouldShowItinerary) {
        // Navigate to itinerary page
        window.location.href = '/Land/itinerary/index.html';
        return;
    }

    if (shouldShowMap) {
        // Show map panel
        mapPanel.classList.remove('hidden');
        chatInterface.classList.add('with-map');

        // TODO: Initialize map with itinerary data
        console.log('Map panel triggered');
    }
}

// ==================== INITIALIZATION ====================
// Check for pending session/message from Main dashboard redirect
const pendingSessionIdRaw = sessionStorage.getItem(PENDING_SESSION_KEY);
if (pendingSessionIdRaw !== null) {
    sessionStorage.removeItem(PENDING_SESSION_KEY);
    const sanitizedSession = pendingSessionIdRaw && pendingSessionIdRaw !== "null"
        ? pendingSessionIdRaw
        : null;
    if (sanitizedSession) {
        // Only restore session if there's also a pending message
        const pendingMessage = sessionStorage.getItem(PENDING_MESSAGE_KEY);
        if (pendingMessage) {
            persistSession(sanitizedSession);
        }
    }
}

const pendingMessage = sessionStorage.getItem(PENDING_MESSAGE_KEY);
if (pendingMessage) {
    sessionStorage.removeItem(PENDING_MESSAGE_KEY);
    // Wait for auth to complete, then auto-send the message
    const checkAuth = setInterval(() => {
        if (currentUser) {
            clearInterval(checkAuth);
            // Auto-populate and send the message
            setTimeout(() => {
                landingInput.value = pendingMessage;
                landingSendBtn.click();
            }, 500);
        }
    }, 100);
} else {
    // Always start with a fresh session when opening chat page
    // This ensures each visit creates a new conversation
    startNewChat();

    // Load chat history in the background for sidebar
    const checkAuth = setInterval(async () => {
        if (currentUser) {
            clearInterval(checkAuth);
            await loadChatHistory();
        }
    }, 100);
}

console.log("Chat interface initialized");
