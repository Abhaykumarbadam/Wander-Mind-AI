// ========================= IMPORTS & CONFIG ===========================
import { auth } from "../firebase-init.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

const API_BASE = "http://127.0.0.1:8000/api/trips";
const TRAVEL_API_BASE = "http://127.0.0.1:8000";
const TRAVEL_SEARCH_URL = `${TRAVEL_API_BASE}/travel/search`;

const CITY_TO_IATA = {
    "hyderabad": "HYD",
    "kathmandu": "KTM",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "bombay": "BOM",
    "bengaluru": "BLR",
    "bangalore": "BLR",
    "chennai": "MAA",
    "kolkata": "CCU",
    "calcutta": "CCU",
    "goa": "GOI",
    "panaji": "GOI",
    "jaipur": "JAI",
    "ahmedabad": "AMD",
    "pune": "PNQ",
    "kochi": "COK",
    "cochin": "COK",
    "singapore": "SIN",
    "bangkok": "BKK",
    "dubai": "DXB",
    "paris": "CDG",
    "london": "LHR",
    "new york": "JFK",
    "tokyo": "NRT",
    "osaka": "KIX",
    "bali": "DPS",
    "denpasar": "DPS",
    "sydney": "SYD",
    "melbourne": "MEL",
    "rome": "FCO",
    "milan": "MXP"
};

// ========================= GLOBAL STATE ===========================
let currentUser = null;
let map = null;
let markersLayer = null;
let currentTrip = null;

// ========================= AUTH ===========================
onAuthStateChanged(auth, (user) => {
    if (user) {
        currentUser = user;
        console.log("User authenticated:", user.uid);

        // Ensure DOM is ready before initializing the itinerary
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => initItinerary());
        } else {
            initItinerary();
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

function guessIataCode(value, fallback = null) {
    if (!value || typeof value !== 'string') return fallback;
    const trimmed = value.trim();
    const parenMatch = trimmed.match(/\(([A-Z]{3})\)/i);
    if (parenMatch) return parenMatch[1].toUpperCase();
    if (/^[A-Z]{3}$/i.test(trimmed)) return trimmed.toUpperCase();
    const standaloneMatch = trimmed.match(/\b([A-Z]{3})\b/);
    if (standaloneMatch) return standaloneMatch[1].toUpperCase();
    const normalized = trimmed.toLowerCase();
    if (CITY_TO_IATA[normalized]) return CITY_TO_IATA[normalized];
    if (normalized.includes(',')) {
        const first = normalized.split(',')[0].trim();
        if (CITY_TO_IATA[first]) return CITY_TO_IATA[first];
    }
    return fallback;
}

// ========================= MAIN INIT ===========================
async function initItinerary() {
    try {
        showLoading(true);

        const tripId = getTripIdFromUrl();
        const trip = await fetchTripData(tripId);

        currentTrip = trip;

        await renderHeader(trip);
        renderChips(trip);
        renderDays(trip);
        
        // Extract all locations from activities across all days
        const allLocations = extractLocationsFromTrip(trip);
        console.log(`📍 Extracted ${allLocations.length} locations from trip:`, allLocations);
        console.log(`   - With coordinates: ${allLocations.filter(l => !l.needsGeocoding).length}`);
        console.log(`   - Need geocoding: ${allLocations.filter(l => l.needsGeocoding).length}`);
        
        await setupMap(allLocations, trip);
        
        // Auto-fetch transport & stay options
        await autoFetchTransportAndStay(trip);
        
        // Generate booking links
        await initBookingLinks(trip);

        showLoading(false);

    } catch (error) {
        console.error("Itinerary init failed:", error);
        showError("Could not load your itinerary. Please try again.");
        showLoading(false);
    }
}

// ========================= DATA FETCHING ===========================
function getTripIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("trip_id");
}

async function fetchTripData(tripId) {
    const token = await getAuthToken();

    // If trip_id is provided, fetch that specific trip
    // Otherwise, fetch the latest trip
    const url = tripId
        ? `${API_BASE}/${tripId}`
        : `${API_BASE}/latest/user`;

    console.log("Fetching trip from:", url);

    const response = await fetch(url, {
        headers: {
            "Authorization": `Bearer ${token}`
        }
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Failed to fetch trip: ${error}`);
    }

    const trip = await response.json();
    console.log("Trip data loaded:", trip);
    return trip;
}

// ========================= RENDER HEADER ===========================
// Derive a reliable destination from trip data (avoids corrupted values like 'you' or month names)
function deriveDestination(trip) {
    if (!trip || typeof trip !== 'object') return '';
    const invalid = new Set(['you','your','trip','journey','travel','december','november','october','september','august','july','june','may','april','march','february','january','unknown','']);
    const candidates = [];

    // Direct fields
    if (trip.destination) candidates.push(trip.destination);
    if (trip.location) candidates.push(trip.location);

    // Locations arrays
    ['locations','inner_locations'].forEach(key => {
        if (Array.isArray(trip[key])) {
            trip[key].forEach(entry => {
                if (!entry) return;
                if (typeof entry === 'string') candidates.push(entry);
                else if (typeof entry === 'object') {
                    if (entry.name) candidates.push(entry.name);
                    if (entry.city) candidates.push(entry.city);
                    if (entry.location) candidates.push(entry.location);
                }
            });
        }
    });

    // Days & activities
    if (Array.isArray(trip.days)) {
        trip.days.forEach(day => {
            if (!day) return;
            if (day.city) candidates.push(day.city);
            if (day.location) candidates.push(day.location);
            if (Array.isArray(day.activities)) {
                day.activities.forEach(act => {
                    if (!act) return;
                    if (act.city) candidates.push(act.city);
                    if (act.location) candidates.push(act.location);
                    if (act.name) {
                        // Extract 'in XYZ' pattern
                        const m = act.name.match(/in\s+([A-Za-z ]{3,})/i);
                        if (m) candidates.push(m[1]);
                    }
                });
            }
        });
    }

    // Notes heuristic (search for known city tokens)
    if (trip.notes && typeof trip.notes === 'string') {
        const note = trip.notes.toLowerCase();
        const knownCities = ['delhi','new delhi','hyderabad','mumbai','goa','ooty','manali','agra','jaipur','bangalore','bengaluru','chennai','kolkata','kerala','kashmir','pondicherry','leh','ladakh'];
        knownCities.forEach(c => { if (note.includes(c)) candidates.push(c); });
    }

    // Normalize & filter
    const cleaned = candidates
        .map(c => (typeof c === 'string' ? c.trim() : ''))
        .filter(c => c && !invalid.has(c.toLowerCase()) && c.length > 2);

    // Prioritize direct destination field, then location field, then others
    let chosen = '';
    if (trip.destination && typeof trip.destination === 'string' && trip.destination.trim().length > 2) {
        chosen = trip.destination.trim();
    } else if (trip.location && typeof trip.location === 'string' && trip.location.trim().length > 2) {
        chosen = trip.location.trim();
    } else {
        // Fallback: prefer shortest city name (main cities are usually short like "Manali", not "Vashisht Village")
        cleaned.sort((a,b) => a.length - b.length);
        chosen = cleaned[0] || '';
    }

    // Normalize common airport names to city names
    const airportToCity = [
        { pattern: /indira gandhi international/i, city: 'Delhi' },
        { pattern: /chhatrapati shivaji/i, city: 'Mumbai' },
        { pattern: /kempegowda/i, city: 'Bengaluru' },
        { pattern: /rajiv gandhi international/i, city: 'Hyderabad' },
        { pattern: /netaji subhash/i, city: 'Kolkata' },
        { pattern: /sardar vallabhbhai patel/i, city: 'Ahmedabad' },
        { pattern: /cochin international/i, city: 'Kochi' },
        { pattern: /dabolim/i, city: 'Goa' },
        { pattern: /veera.*savar/i, city: 'Surat' }
    ];
    const lowerChosen = chosen.toLowerCase();
    for (const mapEntry of airportToCity) {
        if (mapEntry.pattern.test(lowerChosen)) {
            chosen = mapEntry.city;
            break;
        }
    }
    // Strip generic suffixes
    chosen = chosen.replace(/\b(international(\s+airport|\s+air)?)\b/gi,'').replace(/\bairport\b/gi,'').trim();
    // If still multiple words and contains 'air', clean it
    chosen = chosen.replace(/\bair\b/gi,'').trim();

    // Title case output
    return chosen.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
}

// Derive origin (user departure/home city) distinct from destination
async function deriveOrigin(trip, destination) {
    if (!trip || typeof trip !== 'object') return '';
    const invalid = new Set(['you','your','trip','journey','travel','unknown','']);
    const keys = ['departure_location','origin','source','from','departure','home_city','home','user_location','base_city','base_location','start_city','start_location','starting_point'];
    const candidates = [];
    
    // Check departure_location first (might be coordinates)
    if (trip.departure_location) {
        const parsed = await parseLocationField(trip.departure_location);
        if (parsed) candidates.push(parsed);
    }
    
    keys.forEach(k => { if (trip[k] && k !== 'departure_location') candidates.push(trip[k]); });
    if (trip.metadata && typeof trip.metadata === 'object') {
        keys.forEach(k => { if (trip.metadata[k]) candidates.push(trip.metadata[k]); });
    }
    // Days may have a different first city (e.g., arrival city before destination touring region)
    if (Array.isArray(trip.days)) {
        trip.days.forEach(day => {
            if (!day) return;
            if (day.departure_city) candidates.push(day.departure_city);
            if (day.start_city) candidates.push(day.start_city);
            if (day.city) candidates.push(day.city);
        });
    }
    // Normalize & filter
    const cleaned = candidates
        .map(c => (typeof c === 'string' ? c.trim() : ''))
        .filter(c => c && !invalid.has(c.toLowerCase()) && c.length > 2);
    // Remove any exact match to destination (case-insensitive)
    const destLower = (destination || '').toLowerCase();
    const distinct = cleaned.filter(c => c.toLowerCase() !== destLower);
    // Prefer earliest distinct candidate; fallback empty
    const chosen = distinct[0] || '';
    return chosen.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
}

async function renderHeader(trip) {
    const resolvedDestination = deriveDestination(trip) || 'Unknown Destination';
    console.log('🧭 Resolved destination for header:', resolvedDestination);
    // Destination tag
    const destTag = document.getElementById("heroDestination");
    if (destTag) {
        destTag.querySelector("span").textContent = resolvedDestination;
    }

    // Title
    const title = document.getElementById("heroTitle");
    if (title) {
        title.textContent = `Trip to ${resolvedDestination}`;
    }

    // Dates
    const dates = document.getElementById("heroDates");
    if (dates) {
        let start = trip.start_date || trip.check_in || trip.metadata?.start_date || null;
        let end = trip.end_date || trip.check_out || trip.metadata?.end_date || null;
        // Derive from days if inconsistent or missing
        if (Array.isArray(trip.days) && trip.days.length > 0) {
            const dayDates = trip.days.map(d => d.date).filter(Boolean).map(d => new Date(d));
            if (dayDates.length > 0) {
                const earliest = new Date(Math.min(...dayDates));
                const latest = new Date(Math.max(...dayDates));
                if (!start || earliest < new Date(start)) start = earliest.toISOString().split('T')[0];
                if (!end || latest > new Date(end)) end = latest.toISOString().split('T')[0];
            }
        }
        if (start && end) {
            dates.textContent = `${formatDate(start)} – ${formatDate(end)}`;
        }
    }

    // Travelers
    const travelers = document.getElementById("heroTravelers");
    if (travelers) {
        const count = trip.travelers || 1;
        travelers.textContent = `${count} ${count === 1 ? 'Traveler' : 'Travelers'}`;
    }

    // Budget
    const budget = document.getElementById("heroBudget");
    if (budget) {
        const rawBudget = trip.budget_in_inr || trip.budget || trip.estimated_budget_in_inr || trip.metadata?.budget_in_inr || null;
        if (rawBudget) {
            budget.textContent = `₹${formatNumber(rawBudget)}`;
        }
    }

    console.log('📊 Header values -> Destination:', resolvedDestination, 'Dates:', dates?.textContent, 'Budget:', budget?.textContent);
}

// ========================= RENDER CHIPS ===========================
function renderChips(trip) {
    // Diet
    const diet = document.getElementById("statDiet");
    if (diet) {
        diet.textContent = trip.diet || "No preference";
    }

    // Pace
    const pace = document.getElementById("statPace");
    if (pace) {
        pace.textContent = trip.pace || "Balanced";
    }

    // Transport
    const transport = document.getElementById("statTransport");
    if (transport) {
        transport.textContent = trip.transport_preference || "Mixed";
    }

    // Interests
    const interests = document.getElementById("statInterests");
    if (interests) {
        const interestsList = trip.interests || [];
        interests.textContent = interestsList.length > 0
            ? interestsList.join(", ")
            : "General";
    }
}

// ========================= RENDER DAYS ===========================
function renderDays(trip) {
    const container = document.getElementById("timelineContainer");
    if (!container) {
        console.error("Days timeline container not found");
        return;
    }

    container.innerHTML = "";

    const days = trip.days || [];

    if (days.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-calendar-xmark"></i>
                <p>No daily activities found for this trip.</p>
            </div>
        `;
        return;
    }

    days.forEach(day => {
        const dayCard = createDayCard(day);
        container.appendChild(dayCard);
    });

    // Attach event listeners for "View on Map" buttons
    attachMapButtonListeners();
}

function createDayCard(day) {
    const section = document.createElement("section");
    section.className = "day-card";

    const activities = day.activities || [];

    section.innerHTML = `
        <header class="day-header">
            <div class="day-number-badge">Day ${day.day_number}</div>
            <div class="day-header-content">
                <h3 class="day-title">${escapeHtml(day.title || `Day ${day.day_number}`)}</h3>
                ${day.date ? `<p class="day-date"><i class="far fa-calendar"></i> ${formatDate(day.date)}</p>` : ""}
            </div>
        </header>
        
        <div class="activities-list">
            ${activities.length > 0
            ? activities.map(activity => createActivityCard(activity)).join("")
            : '<p class="no-activities">No activities planned for this day.</p>'
        }
        </div>
    `;

    return section;
}

function createActivityCard(activity) {
    const hasLocation = activity.lat != null && activity.lng != null;

    return `
        <article class="activity-card">
            <div class="activity-time-badge">${escapeHtml(activity.time || "Anytime")}</div>
            <div class="activity-content">
                <h4 class="activity-title">${escapeHtml(activity.title || "Activity")}</h4>
                <p class="activity-description">${escapeHtml(activity.description || "")}</p>
                ${activity.location_name
            ? `<p class="activity-location"><i class="fas fa-map-marker-alt"></i> ${escapeHtml(activity.location_name)}</p>`
            : ""
        }
            </div>
            ${hasLocation
            ? `<button class="activity-map-btn" data-lat="${activity.lat}" data-lng="${activity.lng}" data-name="${escapeHtml(activity.location_name || activity.title)}">
                    <i class="fas fa-map-marked-alt"></i>
                    <span>View on Map</span>
                   </button>`
            : ""
        }
        </article>
    `;
}

// ========================= GEOCODING HELPER ===========================
async function geocodeLocation(locationName, destination) {
    try {
        // Build query with destination context for better accuracy
        const query = destination ? `${locationName}, ${destination}` : locationName;
        const geocodeUrl = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
        
        const response = await fetch(geocodeUrl, {
            headers: {
                'Accept-Language': 'en-US',
                'User-Agent': 'WanderMind/1.0'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Geocoding API returned ${response.status}`);
        }
        
        const results = await response.json();
        
        if (results && results.length > 0) {
            return {
                lat: parseFloat(results[0].lat),
                lng: parseFloat(results[0].lon)
            };
        }
        
        return null;
    } catch (error) {
        console.error(`Geocoding error for ${locationName}:`, error);
        return null;
    }
}

// ========================= LOCATION EXTRACTION ===========================
function extractLocationsFromTrip(trip) {
    const locations = [];
    const seenCoords = new Set(); // Avoid duplicate coordinates
    const seenNames = new Set(); // Track unique location names
    
    if (!trip.days || trip.days.length === 0) {
        console.warn("⚠️ No days found in trip");
        return locations;
    }
    
    console.log(`🔍 Scanning ${trip.days.length} days for locations...`);
    
    // Extract locations from all activities
    trip.days.forEach((day, dayIndex) => {
        if (!day.activities || day.activities.length === 0) {
            console.log(`   Day ${day.day_number}: No activities`);
            return;
        }
        
        console.log(`   Day ${day.day_number}: ${day.activities.length} activities`);
        
        day.activities.forEach((activity, actIndex) => {
            const locationName = activity.location_name || activity.title;
            
            if (activity.lat != null && activity.lng != null) {
                let lat = activity.lat;
                let lng = activity.lng;
                const coordKey = `${lat},${lng}`;
                
                // If we've seen this exact coordinate, add a small random offset (0.0001-0.0005 degrees = ~10-50 meters)
                if (seenCoords.has(coordKey)) {
                    const offsetAmount = 0.0001 + (Math.random() * 0.0004);
                    const offsetDirection = Math.random() < 0.5 ? 1 : -1;
                    lat += offsetAmount * offsetDirection;
                    lng += offsetAmount * (Math.random() < 0.5 ? 1 : -1);
                    console.log(`      ⚠️ Duplicate coords detected for ${locationName}, applying offset: [${lat.toFixed(6)}, ${lng.toFixed(6)}]`);
                }
                
                seenCoords.add(coordKey);
                if (locationName) seenNames.add(locationName.toLowerCase());
                
                locations.push({
                    lat: lat,
                    lng: lng,
                    name: locationName || `Day ${day.day_number} Activity`,
                    day: day.day_number,
                    activityTitle: activity.title
                });
                console.log(`      ✓ ${locationName} [${lat}, ${lng}]`);
            } else if (locationName && !seenNames.has(locationName.toLowerCase())) {
                // Location without coordinates - mark for geocoding
                seenNames.add(locationName.toLowerCase());
                locations.push({
                    lat: null,
                    lng: null,
                    name: locationName,
                    day: day.day_number,
                    activityTitle: activity.title,
                    needsGeocoding: true
                });
                console.log(`      ○ ${locationName} (needs geocoding)`);
            } else {
                console.log(`      • Skipped: ${locationName || '(no name)'}`);
            }
        });
    });
    
    const withCoords = locations.filter(l => !l.needsGeocoding).length;
    const needsGeocode = locations.filter(l => l.needsGeocoding).length;
    console.log(`\n📊 Summary: ${locations.length} total locations (${withCoords} with coords, ${needsGeocode} need geocoding)`);
    return locations;
}

// ========================= MAP SETUP ===========================
async function setupMap(locations, trip) {
    const mapContainer = document.getElementById("map");
    if (!mapContainer) {
        console.error("Map container not found");
        return;
    }

    // Initialize map
    map = L.map("map").setView([20, 0], 2);

    // Add tile layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Create markers layer
    markersLayer = L.layerGroup().addTo(map);

    // Geocode locations that need it (with rate limiting)
    const locationsToGeocode = locations.filter(loc => loc.needsGeocoding);
    if (locationsToGeocode.length > 0) {
        console.log(`\n🌍 Starting geocoding for ${locationsToGeocode.length} locations...`);
        let successCount = 0;
        
        for (let i = 0; i < locationsToGeocode.length; i++) {
            const loc = locationsToGeocode[i];
            try {
                console.log(`   [${i + 1}/${locationsToGeocode.length}] Geocoding "${loc.name}"...`);
                const coords = await geocodeLocation(loc.name, trip.destination);
                if (coords) {
                    loc.lat = coords.lat;
                    loc.lng = coords.lng;
                    loc.needsGeocoding = false;
                    successCount++;
                    console.log(`   ✓ Success: [${coords.lat}, ${coords.lng}]`);
                } else {
                    console.log(`   ✗ No results found`);
                }
                // Respect Nominatim rate limit (1 req/sec)
                if (i < locationsToGeocode.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 1100));
                }
            } catch (error) {
                console.error(`   ✗ Error:`, error.message);
            }
        }
        console.log(`\n📍 Geocoding complete: ${successCount}/${locationsToGeocode.length} successful\n`);
    }

    // Add markers with numbers and colors
    const bounds = [];
    const colors = ['#667eea', '#f56565', '#48bb78', '#ed8936', '#9f7aea', '#38b2ac', '#e53e3e', '#d69e2e'];

    locations.forEach((loc, index) => {
        if (loc.lat == null || loc.lng == null) {
            console.warn("Location still missing coordinates after geocoding:", loc.name);
            return;
        }

        // Create custom numbered icon
        const color = colors[index % colors.length];
        const markerHtml = `
            <div style="
                background-color: ${color};
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border: 3px solid white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            ">${index + 1}</div>
        `;

        const customIcon = L.divIcon({
            html: markerHtml,
            className: 'custom-marker-icon',
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16]
        });

        const marker = L.marker([loc.lat, loc.lng], { icon: customIcon }).addTo(markersLayer);
        marker.bindPopup(`<strong>${index + 1}. ${escapeHtml(loc.name || "Location")}</strong>`);

        bounds.push([loc.lat, loc.lng]);
        console.log(`Added marker ${index + 1} for ${loc.name} at [${loc.lat}, ${loc.lng}]`);
    });

    // If no explicit coordinates were available, attempt a lightweight geocode for the trip destination
    if (bounds.length === 0 && trip && trip.destination) {
        try {
            const q = encodeURIComponent(trip.destination);
            const geocodeUrl = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${q}`;
            const resp = await fetch(geocodeUrl, {
                headers: { 'Accept-Language': 'en-US', 'User-Agent': 'WanderMind/1.0 (contact@yourdomain.com)'}
            });
            if (resp.ok) {
                const results = await resp.json();
                if (results && results.length > 0) {
                    const lat = parseFloat(results[0].lat);
                    const lng = parseFloat(results[0].lon);
                    const marker = L.marker([lat, lng]).addTo(markersLayer);
                    marker.bindPopup(`<strong>${escapeHtml(trip.destination)}</strong>`);
                    bounds.push([lat, lng]);
                    console.log('Geocoded destination and added marker for', trip.destination);
                }
            }
        } catch (e) {
            console.warn('Geocoding fallback failed:', e);
        }
    }

    // Fit map to bounds if we have markers
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }

    console.log(`Map initialized with ${bounds.length} markers`);
}

function flyToLocation(lat, lng, name) {
    if (!map) {
        console.error("Map not initialized");
        return;
    }

    map.flyTo([lat, lng], 15, { duration: 1 });

    // Find and open the popup for this location
    markersLayer.eachLayer(layer => {
        if (layer instanceof L.Marker) {
            const pos = layer.getLatLng();
            if (Math.abs(pos.lat - lat) < 0.0001 && Math.abs(pos.lng - lng) < 0.0001) {
                layer.openPopup();
            }
        }
    });
}

// ========================= EVENT LISTENERS ===========================
function attachMapButtonListeners() {
    document.querySelectorAll(".activity-map-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const lat = parseFloat(btn.dataset.lat);
            const lng = parseFloat(btn.dataset.lng);
            const name = btn.dataset.name;

            flyToLocation(lat, lng, name);

            // Scroll map into view on mobile
            const mapContainer = document.getElementById("map");
            if (mapContainer && window.innerWidth < 768) {
                mapContainer.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
    });
}

// Back button
document.getElementById("backBtn")?.addEventListener("click", () => {
    window.location.href = "/Land/chat/index.html";
});

// Mobile map toggle
document.getElementById("mobileMapToggle")?.addEventListener("click", () => {
    const mapPanel = document.querySelector(".map-panel");
    if (mapPanel) {
        mapPanel.classList.toggle("active");
    }
});

// Export PDF button
document.getElementById("exportBtn")?.addEventListener("click", async () => {
    try {
        const btn = document.getElementById("exportBtn");
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
        btn.disabled = true;

        const content = document.getElementById("itineraryContent");
        if (!content) {
            throw new Error("Content not found");
        }

        // Get trip title for filename
        const tripTitle = document.getElementById("heroTitle")?.textContent || "Itinerary";
        const filename = `${tripTitle.replace(/[^a-z0-9]/gi, '_')}.pdf`;

        // Hide map buttons and navigation for PDF
        const elementsToHide = [
            ...document.querySelectorAll('.activity-map-btn'),
            document.querySelector('.mobile-map-toggle'),
            document.querySelector('.nav-header')
        ];

        // Store original display values and hide elements
        const originalStyles = elementsToHide.map(el => {
            if (!el) return null;
            const display = el.style.display;
            el.style.display = 'none';
            return { element: el, display };
        });

        // PDF options
        const opt = {
            margin: [10, 10],
            filename: filename,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { 
                scale: 2,
                useCORS: true,
                logging: false,
                scrollY: 0,
                scrollX: 0
            },
            jsPDF: { 
                unit: 'mm', 
                format: 'a4', 
                orientation: 'portrait',
                compress: true
            },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
        };

        // Generate PDF
        await html2pdf().set(opt).from(content).save();

        // Restore original display values
        originalStyles.forEach(style => {
            if (style && style.element) {
                style.element.style.display = style.display || '';
            }
        });

        // Reset button
        btn.innerHTML = originalText;
        btn.disabled = false;

        // Show success message
        showToast("PDF downloaded successfully!", "success");

        // Optional: Show share option after PDF is generated (Web Share API - FREE)
        if (navigator.share) {
            setTimeout(() => {
                if (confirm("PDF downloaded! Would you like to share it?")) {
                    shareItinerary();
                }
            }, 1000);
        }

    } catch (error) {
        console.error("PDF export failed:", error);
        const btn = document.getElementById("exportBtn");
        btn.innerHTML = '<i class="fas fa-download"></i> Export PDF';
        btn.disabled = false;
        showToast("Failed to generate PDF. Please try again.", "error");
    }
});

// Web Share API (FREE - built into modern browsers)
async function shareItinerary() {
    if (!navigator.share) {
        showToast("Sharing not supported on this device", "info");
        return;
    }

    try {
        const tripTitle = document.getElementById("heroTitle")?.textContent || "My Trip";
        const destination = document.getElementById("heroDestination")?.querySelector("span")?.textContent || "destination";
        const url = window.location.href;

        await navigator.share({
            title: tripTitle,
            text: `Check out my ${destination} itinerary planned with WanderMind!`,
            url: url
        });

        showToast("Shared successfully!", "success");
    } catch (error) {
        // User cancelled or error occurred
        if (error.name !== 'AbortError') {
            console.error("Share failed:", error);
        }
    }
}

// Toast notification helper
function showToast(message, type = "info") {
    // Remove existing toast
    const existingToast = document.querySelector(".toast-notification");
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast
    const toast = document.createElement("div");
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${escapeHtml(message)}</span>
    `;

    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add("show"), 10);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==================== BOOKING WIDGET ====================

function initializeBookingWidget(tripData) {
    const originInput = document.getElementById('originInput');
    const destinationInput = document.getElementById('destinationInput');
    const travelDateInput = document.getElementById('travelDateInput');
    const passengersInput = document.getElementById('passengersInput');
    const bookingButtons = document.querySelectorAll('.booking-btn');
    const resultsContainer = document.getElementById('bookingResultsContainer');

    // Pre-fill data from the trip
    if (tripData.destination) {
        destinationInput.value = tripData.destination.split(',')[0]; // Use the primary city
    }
    if (tripData.start_date) {
        travelDateInput.value = tripData.start_date;
    }
    if (tripData.travelers) {
        passengersInput.value = tripData.travelers;
    }

    bookingButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const type = button.dataset.type;
            const origin = originInput.value;
            const destination = destinationInput.value;
            const date = travelDateInput.value;
            const passengers = passengersInput.value;

            if ((type === 'flight' && !origin) || !destination || !date) {
                alert('Please fill in Origin, Destination, and Date.');
                return;
            }

            resultsContainer.innerHTML = '<div class="loader"></div>';

            try {
                const token = await getAuthToken();
                const response = await fetch(TRAVEL_SEARCH_URL, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ 
                        type, 
                        origin, 
                        destination, 
                        date,
                        start_date: date,
                        end_date: date,
                        passengers: passengers || 1 
                    })
                });

                if (!response.ok) {
                    throw new Error(`Network response was not ok: ${response.statusText}`);
                }

                const data = await response.json();
                renderBookingResults(data, type);

            } catch (error) {
                console.error('Error fetching booking data:', error);
                resultsContainer.innerHTML = '<div class="results-placeholder"><p>Could not fetch results. Please try again.</p></div>';
            }
        });
    });
}

function renderBookingResults(data, type) {
    const resultsContainer = document.getElementById('bookingResultsContainer');
    resultsContainer.innerHTML = '';

    if (type === 'flight') {
        if (data.flights && data.flights.length > 0) {
            data.flights.forEach(flight => {
                const card = document.createElement('div');
                card.className = 'flight-card';
                card.innerHTML = `
                    <div class="flight-header">
                        <span class="flight-airline">${flight.airline}</span>
                        <span class="flight-number">${flight.flight_number}</span>
                    </div>
                    <div class="flight-details">
                        <span>${flight.departure_airport} &rarr; ${flight.arrival_airport}</span>
                        <span>Status: ${flight.status}</span>
                    </div>
                `;
                resultsContainer.appendChild(card);
            });
        } else {
            resultsContainer.innerHTML = '<div class="results-placeholder"><p>No flights found for the selected criteria.</p></div>';
        }
    } else { // Hotels, Trains, Buses from Groq
        const results = data[type + 's']; // e.g., data.hotels, data.trains
        if (results && results.length > 0) {
            results.forEach(item => {
                const card = document.createElement('div');
                card.className = 'suggestion-card';
                card.innerHTML = `
                    <div class="suggestion-header">
                        <span class="suggestion-name">${item.name}</span>
                        <span class="suggestion-price">${item.price || ''}</span>
                    </div>
                    <p class="suggestion-details">${item.details || item.reason || ''}</p>
                    ${item.tip ? `<p class="suggestion-reason"><strong>Tip:</strong> ${item.tip}</p>` : ''}
                `;
                resultsContainer.appendChild(card);
            });
        } else {
            resultsContainer.innerHTML = `<div class="results-placeholder"><p>No ${type} suggestions found.</p></div>`;
        }
    }
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    // DOM is ready. If the user is already authenticated, initialize.
    const loadingState = document.getElementById('loadingState');
    const itineraryContent = document.getElementById('itineraryContent');

    // Ensure loading UI is visible while waiting for auth/init
    loadingState?.classList.remove('hidden');
    itineraryContent?.classList.add('hidden');

    if (currentUser) {
        // If auth already happened earlier, initialize now.
        initItinerary();
    } else {
        console.log('DOM loaded, waiting for authentication to initialize the itinerary');
    }
});

// ========================= UI HELPERS ===========================
function showLoading(show) {
    const loading = document.getElementById("loadingState");
    const content = document.getElementById("itineraryContent");

    if (loading) {
        loading.style.display = show ? "flex" : "none";
    }
    if (content) {
        content.classList.toggle("hidden", show);
    }
}

function showError(message) {
    const content = document.getElementById("itineraryContent");
    if (content) {
        content.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Oops!</h3>
                <p>${escapeHtml(message)}</p>
                <button onclick="location.reload()" class="retry-btn">Try Again</button>
            </div>
        `;
        content.classList.remove("hidden");
    }
}

// ========================= AUTO-FETCH TRANSPORT & STAY ===========================
async function autoFetchTransportAndStay(trip) {
    if (!trip || !trip.destination || !trip.start_date) {
        console.warn('⚠️ Missing trip data for transport search');
        return;
    }

    try {
        console.log('🎬 Auto-fetching transport & stay for trip:', trip);

        const token = await getAuthToken();
        const origin = trip.departure_location || 'HYD'; // Use trip departure or default
        const destination = trip.destination;
        const date = trip.start_date;
        const passengers = trip.travelers || 1;
        
        const originCode = guessIataCode(origin, origin?.slice(0, 3).toUpperCase() || 'HYD');
        const destCode = guessIataCode(destination, destination?.slice(0, 3).toUpperCase() || 'DEL');

        // Pre-fill the form
        const originInput = document.getElementById('originInput');
        const destInput = document.getElementById('destinationInput');
        const dateInput = document.getElementById('travelDateInput');
        const passInput = document.getElementById('passengersInput');

        if (originInput) originInput.value = originCode;
        if (destInput) destInput.value = destCode;
        if (dateInput) dateInput.value = date;
        if (passInput) passInput.value = passengers;

        console.log('🚀 Calling transport API:', { 
            origin: originCode, 
            destination: destCode, 
            start_date: date,
            end_date: trip.end_date || date,
            passengers 
        });

        const response = await fetch(TRAVEL_SEARCH_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                type: 'flight',
                origin: originCode,
                destination: destCode,
                start_date: date,
                end_date: trip.end_date || date,
                passengers: passengers
            })
        });

        if (!response.ok) {
            throw new Error(`Transport API failed: ${response.status}`);
        }

        const data = await response.json();
        console.log('✅ Transport data received:', data);
        console.log('  ✈️ Flights:', data.flights?.length || 0, data.flights);
        console.log('  🚄 Trains:', data.trains?.length || 0, data.trains);
        console.log('  🚌 Buses:', data.buses?.length || 0, data.buses);
        console.log('  🏨 Hotels:', data.hotels?.length || 0, data.hotels);
        
        // Log first hotel if exists to see structure
        if (data.hotels && data.hotels.length > 0) {
            console.log('  🏨 Sample hotel data:', JSON.stringify(data.hotels[0], null, 2));
        }
        
        // Log metadata if present
        if (data.metadata) {
            console.log('  📊 Metadata:', data.metadata);
        }
        if (data.fallback_used) {
            console.log('  ⚠️ Fallback data was used!');
        }

        // Store trip data for booking URL generation
        window.currentTrip = trip;
        
        // Display results
        displayTransportResults(data, destination);

    } catch (error) {
        console.error('❌ Failed to auto-fetch transport:', error);
        // Don't show error to user, just log it
    }
}

function generateBookingURL(type, option, tripData, destination, metadata = {}) {
    const fallbackStart = new Date().toISOString().split('T')[0];
    const fallbackEnd = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const checkIn = metadata.start_date || tripData?.start_date || fallbackStart;
    const checkOut = metadata.end_date || tripData?.end_date || fallbackEnd;
    const adults = metadata.passengers || tripData?.travelers || 2;

    if (type === 'flight') {
        if (option.booking_link) return option.booking_link;

        const rawOrigin = option.departure_airport || option.origin || metadata.origin || tripData?.departure_location;
        const rawDestination = option.arrival_airport || option.destination || metadata.destination || destination;
        const originCode =
            guessIataCode(rawOrigin, metadata.origin_code) ||
            (tripData?.departure_location ? tripData.departure_location.slice(0, 3).toUpperCase() : null) ||
            'DEL';
        const destCode =
            guessIataCode(rawDestination, metadata.destination_code) ||
            (destination ? destination.slice(0, 3).toUpperCase() : null) ||
            'BOM';

        const formatMMTDate = (dateStr) => {
            const d = new Date(dateStr);
            const day = String(d.getDate()).padStart(2, '0');
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const year = d.getFullYear();
            return `${day}/${month}/${year}`;
        };

        const departDate = formatMMTDate(checkIn);
        const returnDate = formatMMTDate(checkOut);
        const itinerary = `${originCode}-${destCode}-${departDate}_${destCode}-${originCode}-${returnDate}`;
        return `https://www.makemytrip.com/flight/search?itinerary=${itinerary}&tripType=R&paxType=A-${adults}_C-0_I-0&intl=true&cabinClass=E&lang=eng`;
    } else if (type === 'hotel') {
        if (option.booking_link) return option.booking_link;
        const destName = encodeURIComponent(destination || metadata.destination || '');
        return `https://www.booking.com/searchresults.html?ss=${destName}&checkin=${checkIn}&checkout=${checkOut}&group_adults=${adults}&no_rooms=1&selected_currency=INR`;
    } else if (type === 'train' || type === 'bus') {
        if (option.booking_link) return option.booking_link;
        const originCity = tripData?.departure_location || metadata.origin || 'Hyderabad';
        return `https://www.redbus.in/bus-tickets/${encodeURIComponent(originCity)}-to-${encodeURIComponent(destination)}`;
    }

    return option.booking_link || '#';
}

function displayTransportResults(data, destination) {
    const resultsContainer = document.getElementById('bookingResultsContainer');
    if (!resultsContainer) return;
    
    // Get current trip data for generating booking URLs
    const tripData = window.currentTrip || {};
    const metadata = data.metadata || {};
    const airportGuidance = metadata.airport_guidance || null;

    let html = '';

    if (airportGuidance && airportGuidance.nearest_airport) {
        const nearest = airportGuidance.nearest_airport;
        html += '<div class="results-section guidance-section">';
        html += '<h3>✈️ Nearest Airport</h3>';
        html += '<div class="guidance-card">';
        html += `<p><strong>${escapeHtml(nearest.name || 'Nearest airport')}</strong> (${escapeHtml(nearest.code || '')})</p>`;
        if (nearest.distance_km) {
            html += `<p>Approx. distance: ${escapeHtml(String(nearest.distance_km))}</p>`;
        }
        if (nearest.notes) {
            html += `<p>${escapeHtml(nearest.notes)}</p>`;
        }
        html += '</div>';

        if (airportGuidance.alternate_airports && airportGuidance.alternate_airports.length > 0) {
            html += '<div class="guidance-subsection"><h4>Alternate Airports</h4><ul>';
            airportGuidance.alternate_airports.forEach((alt) => {
                html += `<li><strong>${escapeHtml(alt.name || '')}</strong>${alt.code ? ` (${escapeHtml(alt.code)})` : ''}${alt.notes ? ` – ${escapeHtml(alt.notes)}` : ''}</li>`;
            });
            html += '</ul></div>';
        }

        if (airportGuidance.railway_access && airportGuidance.railway_access.length > 0) {
            html += '<div class="guidance-subsection"><h4>🚆 Railway Access</h4><ul>';
            airportGuidance.railway_access.forEach((rail) => {
                html += `<li><strong>${escapeHtml(rail.name || '')}</strong>${rail.notes ? ` – ${escapeHtml(rail.notes)}` : ''}</li>`;
            });
            html += '</ul></div>';
        }

        if (airportGuidance.ground_transport && airportGuidance.ground_transport.length > 0) {
            html += '<div class="guidance-subsection"><h4>🚐 Ground Transfer</h4><ul>';
            airportGuidance.ground_transport.forEach((mode) => {
                html += `<li><strong>${escapeHtml(mode.option || '')}</strong>${mode.notes ? ` – ${escapeHtml(mode.notes)}` : ''}</li>`;
            });
            html += '</ul></div>';
        }

        html += '</div>';
    }

    // Combine all transport options
    const allTransport = [];

    if (data.flights && data.flights.length > 0) {
        data.flights.forEach(flight => {
            const link = flight.booking_link || generateBookingURL('flight', flight, tripData, destination, metadata);
            allTransport.push({
                type: 'flight',
                icon: '✈️',
                title: flight.airline || flight.flight_number || 'Flight',
                details: `${flight.departure_airport || ''} → ${flight.arrival_airport || ''}`,
                price: flight.price || 'Check availability',
                link,
                status: flight.status,
                rawData: flight
            });
        });
    }

    if (data.trains && data.trains.length > 0) {
        data.trains.forEach(train => {
            const link = train.booking_link || generateBookingURL('train', train, tripData, destination, metadata);
            allTransport.push({
                type: 'train',
                icon: '🚄',
                title: train.name || 'Train',
                details: train.duration || '',
                price: train.price || 'Check availability',
                link
            });
        });
    }

    if (data.buses && data.buses.length > 0) {
        data.buses.forEach(bus => {
            const link = bus.booking_link || generateBookingURL('bus', bus, tripData, destination, metadata);
            allTransport.push({
                type: 'bus',
                icon: '🚌',
                title: bus.name || 'Bus',
                details: bus.duration || '',
                price: bus.price || 'Check availability',
                link
            });
        });
    }

    // Transport Section
    if (allTransport.length > 0) {
        html += '<div class=\"results-section\"><h3>🚗 Transportation Options</h3><div class=\"results-grid\">';
        allTransport.slice(0, 6).forEach(option => {
            html += `
                <div class=\"result-card\" data-type=\"${option.type}\">
                    <div class=\"card-header\">
                        <span class=\"card-icon\">${option.icon}</span>
                        <h4>${escapeHtml(option.title)}</h4>
                    </div>
                    <p class="card-details">${escapeHtml(option.details)}</p>
                    ${option.status ? `<span class="status-badge">${escapeHtml(option.status)}</span>` : ''}
                    <p class="card-price">${escapeHtml(option.price)}</p>
                    <a href="${escapeHtml(option.link)}" target="_blank" class="card-button">${option.type === 'flight' ? 'Check Availability' : 'Book Now'} →</a>
                </div>
            `;
        });
        html += '</div></div>';
    }

    // Hotels Section - COMMENTED OUT
    /*
    if (data.hotels && data.hotels.length > 0) {
        html += '<div class=\"results-section\"><h3>🏨 Accommodation Options</h3><div class=\"results-grid\">';
        data.hotels.slice(0, 4).forEach(hotel => {
            const bookingUrl = hotel.booking_link || generateBookingURL('hotel', hotel, tripData, destination, metadata);
            const location = hotel.location || destination;
            const duration = hotel.duration || 'Stay duration';
            const price = hotel.price || 'Check availability';
            
            html += `
                <div class=\"result-card\" data-type=\"hotel\">
                    <div class=\"card-header\">
                        <span class=\"card-icon\">🏨</span>
                        <h4>${escapeHtml(hotel.name || 'Hotel')}</h4>
                    </div>
                    <p class=\"card-details\">📍 ${escapeHtml(location)}</p>
                    <p class=\"card-details\">🗓️ ${escapeHtml(duration)}</p>
                    <p class="card-price">${escapeHtml(price)}</p>
                    <a href="${escapeHtml(bookingUrl)}" target="_blank" class="card-button">Book Now →</a>
                </div>
            `;
        });
        html += '</div></div>';
    }
    */

    // Fallback options if no data - COMMENTED OUT (Using booking links feature instead)
    /*
    if (allTransport.length === 0 && (!data.hotels || data.hotels.length === 0)) {
        html = `
            <div class=\"results-placeholder\">
                <p>🔍 No results found. Try searching on popular booking platforms:</p>
                <div class=\"fallback-links\">
                    <a href=\"https://www.booking.com/searchresults.html?ss=${encodeURIComponent(destination)}\" target=\"_blank\" class=\"fallback-btn\">🏨 Booking.com</a>
                    <a href=\"https://www.airbnb.com/s/${encodeURIComponent(destination)}\" target=\"_blank\" class=\"fallback-btn\">🏡 Airbnb</a>
                    <a href=\"https://www.makemytrip.com/\" target=\"_blank\" class=\"fallback-btn\">✈️ MakeMyTrip</a>
                </div>
            </div>
        `;
    }
    */

    resultsContainer.innerHTML = html;
}

// ========================= UTILITY FUNCTIONS ===========================
function formatDate(dateString) {
    if (!dateString) return "";

    try {
        const date = new Date(dateString);
        return date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric"
        });
    } catch (e) {
        return dateString;
    }
}

function formatNumber(num) {
    if (!num) return "0";
    return num.toLocaleString("en-IN");
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ========================= BOOKING LINKS FEATURE ===========================
// Generates direct Booking.com links for hotels and flights

async function generateBookingLinksFromBackend(tripData) {
    /**
     * Call the new backend endpoint to generate Booking.com links
     * 
     * @param {Object} tripData - Trip data with origin, destination, dates, passengers
     * @returns {Promise<Object>} - { hotel_url, flight_url, origin_airport, dest_airport }
     */
    try {
        const token = await getAuthToken();
        
        // Log the full trip data to understand structure
        console.log("📦 Full trip data received:", tripData);
        console.log("🔍 Checking destination field:", tripData.destination);
        console.log("🔍 Checking days array:", tripData.days);
        // Use shared deriveDestination logic for consistency with header
        let destination = deriveDestination(tripData);
        const invalidTokens = new Set(['you','your','trip','journey','travel','destination','place','city','december','november','october','september','august','july','june','may','april','march','february','january','unknown','']);
        const sanitizePlace = (raw) => {
            if (!raw || typeof raw !== 'string') return '';
            const cleaned = raw.trim();
            if (invalidTokens.has(cleaned.toLowerCase())) return '';
            // Remove leading generic words (e.g., "Visit", "Explore")
            return cleaned.replace(/^Visit\s+/i, '').replace(/^Explore\s+/i, '');
        };
        destination = sanitizePlace(destination);

        if (!destination) {
            // Fallback: attempt simpler extraction if deriveDestination failed
            destination = sanitizePlace(
                tripData.destination || 
                tripData.to || 
                tripData.metadata?.destination || 
                ''
            );
        }

        // Extract and sanitize origin
        let origin = sanitizePlace(await deriveOrigin(tripData, destination));
        if (!origin) {
            origin = sanitizePlace(
                tripData.origin || tripData.departure || tripData.from || tripData.source ||
                tripData.metadata?.origin || tripData.metadata?.departure || ''
            );
        }
        // If still identical to destination, leave blank so backend can request user input / skip flight URL
        if (origin && destination && origin.toLowerCase() === destination.toLowerCase()) {
            console.log('⚠️ Origin equals destination; sending blank origin to avoid duplicate flight route');
            origin = '';
        }
        console.log("🎯 Final extracted (sanitized) - Origin:", origin || '(none)', "Destination:", destination);
        
        // Extract dates - check multiple formats
        const startDate = tripData.start_date || 
                         tripData.startDate || 
                         tripData.check_in ||
                         tripData.checkin ||
                         tripData.metadata?.start_date || 
                         "";
                         
        const endDate = tripData.end_date || 
                       tripData.endDate || 
                       tripData.check_out ||
                       tripData.checkout ||
                       tripData.metadata?.end_date || 
                       "";
        
        // Extract passengers/travelers
        const passengers = tripData.passengers || 
                          tripData.travelers || 
                          tripData.adults ||
                          tripData.metadata?.passengers || 
                          2;
        
        const requestBody = {
            origin: origin,
            destination: destination,
            start_date: startDate,
            end_date: endDate,
            passengers: passengers,
            rooms: tripData.rooms || 1,
            trip_type: "ROUNDTRIP"
        };

        console.log("🔗 Generating booking links with extracted data:", requestBody);

        const response = await fetch(`${TRAVEL_API_BASE}/travel/booking-links`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`Failed to generate booking links: ${response.status}`);
        }

        const data = await response.json();
        console.log("✅ Booking links generated:", data);
        return data;

    } catch (error) {
        console.error("❌ Error generating booking links:", error);
        return null;
    }
}

function displayBookingLinks(linksData, containerElement) {
    /**
     * Display booking links as two consolidated large buttons
     * 
     * @param {Object} linksData - { hotel_url, flight_url, origin_airport, dest_airport }
     * @param {HTMLElement} containerElement - Element to render links into
     */
    if (!linksData || !containerElement) return;

    // LOG BOOKING LINKS FOR VERIFICATION
    console.log('═══════════════════════════════════════════════════════');
    console.log('🔗 BOOKING LINKS GENERATED:');
    console.log('═══════════════════════════════════════════════════════');
    console.log('✈️  FLIGHT LINK:', linksData.flight_url);
    console.log('🏨 HOTEL LINK:', linksData.hotel_url);
    console.log('📍 Route:', linksData.origin_airport?.code, '→', linksData.dest_airport?.code);
    console.log('═══════════════════════════════════════════════════════');

    const safeFlightUrl = (typeof linksData.flight_url === 'string' && linksData.flight_url.startsWith('http')) ? linksData.flight_url : '';
    const flightBtn = safeFlightUrl
        ? `<a href="${safeFlightUrl}" target="_blank" class="booking-btn-large booking-btn-flights" rel="noopener noreferrer">
                <div class="booking-btn-icon">✈️</div>
                <div class="booking-btn-content">
                    <h3>Book All Flights</h3>
                    <p>${linksData.origin_airport?.code || ''} → ${linksData.dest_airport?.code || ''}</p>
                </div>
                <div class="booking-btn-arrow">→</div>
           </a>`
        : `<div class="booking-btn-large booking-btn-flights booking-btn-disabled" title="Add your origin city to enable flights">
                <div class="booking-btn-icon">✈️</div>
                <div class="booking-btn-content">
                    <h3>Book All Flights</h3>
                    <p>${linksData.origin_airport?.code || ''} → ${linksData.dest_airport?.code || ''}</p>
                </div>
                <div class="booking-btn-arrow">→</div>
           </div>`;

    const html = `
        <div class="booking-links-section">
            <h2>🔗 Book Your Trip</h2>
            <div class="booking-buttons-container">
                ${flightBtn}
                <a href="${linksData.hotel_url}" target="_blank" class="booking-btn-large booking-btn-hotels">
                    <div class="booking-btn-icon">🏨</div>
                    <div class="booking-btn-content">
                        <h3>Book All Hotels</h3>
                        <p>Find accommodations at your destination</p>
                    </div>
                    <div class="booking-btn-arrow">→</div>
                </a>
            </div>
            ${!safeFlightUrl ? `
            <div class="booking-origin-helper">
                <label for="bookingOriginInput">Your origin city</label>
                <div class="origin-input-row">
                    <input id="bookingOriginInput" type="text" placeholder="e.g., Hyderabad" />
                    <button id="bookingOriginApplyBtn" type="button">Update Flights</button>
                </div>
                <p class="origin-hint">Enter your start city to enable flight search.</p>
            </div>
            ` : ''}
        </div>
    `;

    containerElement.innerHTML = html + containerElement.innerHTML;

    // Attach handler to origin input to regenerate links
    if (!safeFlightUrl) {
        const input = containerElement.querySelector('#bookingOriginInput');
        const btn = containerElement.querySelector('#bookingOriginApplyBtn');
        if (input && btn) {
            btn.addEventListener('click', async () => {
                const originCity = input.value.trim();
                if (!originCity) {
                    showToast('Please enter your origin city', 'info');
                    return;
                }
                // Merge origin into current trip and regenerate
                const trip = window.currentTrip || {};
                const enriched = { ...trip, origin: originCity, metadata: { ...(trip.metadata || {}), origin: originCity } };
                const links = await generateBookingLinksFromBackend(enriched);
                if (links) {
                    // Replace section content with fresh buttons
                    containerElement.innerHTML = '';
                    displayBookingLinks(links, containerElement);
                    showToast('Flights link updated', 'success');
                } else {
                    showToast('Could not generate flights link. Try another city.', 'error');
                }
            });
        }
    }
}

// Auto-generate booking links when trip data is loaded
async function initBookingLinks(tripData) {
    /**
     * Initialize booking links feature - call this after loading trip data
     */
    const linksData = await generateBookingLinksFromBackend(tripData);
    
    if (linksData) {
        const resultsContainer = document.getElementById('bookingResultsContainer');
        if (resultsContainer) {
            displayBookingLinks(linksData, resultsContainer);
        }
    }
}

// Export for use in other parts of the code
window.generateBookingLinks = generateBookingLinksFromBackend;
window.displayBookingLinks = displayBookingLinks;
window.initBookingLinks = initBookingLinks;

console.log("Itinerary script loaded");
