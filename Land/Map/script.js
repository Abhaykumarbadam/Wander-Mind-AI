import { auth } from "../firebase-init.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

const API_BASE = "http://localhost:8000";
let map = null;
let currentTrip = null;
let markers = [];

// Initialize Map
function initMap() {
    map = L.map('fullScreenMap', {
        zoomControl: false // We use custom controls
    }).setView([20, 0], 2);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);
}

// Fetch Trip Data
async function loadTripData(tripId) {
    if (!auth.currentUser) return;
    const token = await auth.currentUser.getIdToken();

    // In a real app, we'd fetch specific trip by ID. 
    // Here we reuse the itinerary endpoint and filter.
    try {
        const response = await fetch(`${API_BASE}/trips/itinerary`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        const allTrips = [...(data.trips.upcoming || []), ...(data.trips.ongoing || []), ...(data.trips.completed || [])];

        // Find trip by ID or fallback to latest
        currentTrip = allTrips.find(t => t._id === tripId) || allTrips[0];

        if (currentTrip) {
            renderTripOnMap(currentTrip);
            document.getElementById('tripTitleBadge').textContent = currentTrip.location || "Your Trip";
        }
    } catch (e) {
        console.error("Error loading trip:", e);
    }
}

function renderTripOnMap(trip) {
    // Clear existing
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    const bounds = L.latLngBounds();

    // Main Location
    if (trip.coordinates) {
        const mainMarker = L.marker([trip.coordinates.lat, trip.coordinates.lng]).addTo(map);
        bounds.extend(mainMarker.getLatLng());
        markers.push(mainMarker);
    }

    // Inner Locations
    if (trip.inner_locations && trip.inner_locations.length > 0) {
        trip.inner_locations.forEach(loc => {
            // If we have coords (requires geocoding on backend or client)
            // For now, we simulate or skip if no coords.
            // Assuming backend provides coords in future update.
        });
    }

    if (!bounds.isValid()) {
        map.setView([20, 0], 2);
    } else {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    initMap();

    onAuthStateChanged(auth, (user) => {
        if (user) {
            const params = new URLSearchParams(window.location.search);
            const tripId = params.get('id');
            loadTripData(tripId);
        } else {
            window.location.href = "/Land/loginPage/login.html";
        }
    });

    document.getElementById('backBtn').addEventListener('click', () => {
        window.history.back();
    });

    document.getElementById('zoomInBtn').addEventListener('click', () => map.zoomIn());
    document.getElementById('zoomOutBtn').addEventListener('click', () => map.zoomOut());

    // Bottom Sheet Logic
    const sheet = document.getElementById('locationBottomSheet');
    const handle = document.querySelector('.sheet-handle');

    handle.addEventListener('click', () => {
        sheet.classList.toggle('expanded');
    });
});
