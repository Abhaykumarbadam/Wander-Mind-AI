// Map initialization and trip management
let map;
let markers = {};
let tripData = null;
const API_BASE = 'http://127.0.0.1:8000';

// Initialize Firebase (config loaded from firebase-init.js)
let currentUser = null;

// Wait for Firebase to initialize
firebase.auth().onAuthStateChanged((user) => {
    if (user) {
        currentUser = user;
        initMap();
        loadTrips();
    } else {
        // Redirect to login if not authenticated
        window.location.href = '../loginPage/login.html';
    }
});

// Initialize map
function initMap() {
    map = L.map('map').setView([20, 0], 2);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
    }).addTo(map);
}

// Get Firebase ID token
async function getAuthToken() {
    if (!currentUser) {
        throw new Error('User not authenticated');
    }
    return await currentUser.getIdToken();
}

// Load trips from API
async function loadTrips() {
    showLoading(true);
    
    try {
        const token = await getAuthToken();
        
        const response = await fetch(`${API_BASE}/trips/map-data`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load trips');
        }
        
        const data = await response.json();
        tripData = data.map_data;
        
        // Clear existing markers
        Object.values(markers).forEach(marker => map.removeLayer(marker));
        markers = {};
        
        // Add markers for each status
        addMarkersForStatus('completed', tripData.completed, '#10b981');
        addMarkersForStatus('ongoing', tripData.ongoing, '#f59e0b');
        addMarkersForStatus('upcoming', tripData.upcoming, '#3b82f6');
        
        // Update stats
        updateStats(tripData);
        
        // Update trips list
        updateTripsList(tripData);
        
        // Fit map to show all markers
        if (Object.keys(markers).length > 0) {
            const group = L.featureGroup(Object.values(markers));
            map.fitBounds(group.getBounds().pad(0.1));
        }
        
    } catch (error) {
        console.error('Error loading trips:', error);
        alert('Failed to load trips. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Add markers for a specific status
function addMarkersForStatus(status, trips, color) {
    trips.forEach(trip => {
        if (trip.coordinates && trip.coordinates.lat && trip.coordinates.lng) {
            const marker = L.circleMarker(
                [trip.coordinates.lat, trip.coordinates.lng],
                {
                    radius: 10,
                    fillColor: color,
                    color: 'white',
                    weight: 3,
                    opacity: 1,
                    fillOpacity: 0.8
                }
            );
            
            // Create popup content
            const popupContent = `
                <div class="popup-title">${trip.location}</div>
                <div class="popup-info">📅 ${formatDate(trip.start_date)} - ${formatDate(trip.end_date)}</div>
                ${trip.city ? `<div class="popup-info">📍 ${trip.city}, ${trip.country}</div>` : ''}
                ${trip.accommodation ? `<div class="popup-info">🏨 ${trip.accommodation}</div>` : ''}
                ${trip.notes ? `<div class="popup-info">📝 ${trip.notes}</div>` : ''}
                <div class="popup-info" style="margin-top:0.5rem"><strong>Status:</strong> ${capitalizeFirst(status)}</div>
            `;
            
            marker.bindPopup(popupContent);
            marker.addTo(map);
            
            markers[trip.id] = marker;
        }
    });
}

// Update statistics
function updateStats(data) {
    const completedCount = data.completed.length;
    const ongoingCount = data.ongoing.length;
    const upcomingCount = data.upcoming.length;
    
    // Count unique countries
    const countries = new Set();
    [...data.completed, ...data.ongoing, ...data.upcoming].forEach(trip => {
        if (trip.country) countries.add(trip.country);
    });
    
    document.getElementById('completedCount').textContent = completedCount;
    document.getElementById('ongoingCount').textContent = ongoingCount;
    document.getElementById('upcomingCount').textContent = upcomingCount;
    document.getElementById('countriesCount').textContent = countries.size;
}

// Update trips list panel
function updateTripsList(data) {
    const tripsList = document.getElementById('tripsList');
    tripsList.innerHTML = '';
    
    // Combine and sort all trips by date
    const allTrips = [
        ...data.completed.map(t => ({...t, status: 'completed'})),
        ...data.ongoing.map(t => ({...t, status: 'ongoing'})),
        ...data.upcoming.map(t => ({...t, status: 'upcoming'}))
    ].sort((a, b) => new Date(b.start_date) - new Date(a.start_date));
    
    if (allTrips.length === 0) {
        tripsList.innerHTML = '<p style="text-align:center;color:#999;padding:2rem;">No trips yet. Add your first trip!</p>';
        return;
    }
    
    allTrips.forEach(trip => {
        const card = document.createElement('div');
        card.className = `trip-card ${trip.status}`;
        card.innerHTML = `
            <div class="trip-card-header">
                <div class="trip-location">${trip.location}</div>
                <div class="trip-status ${trip.status}">${trip.status}</div>
            </div>
            <div class="trip-dates">
                ${formatDate(trip.start_date)} - ${formatDate(trip.end_date)}
            </div>
            ${trip.accommodation ? `<div class="trip-notes">🏨 ${trip.accommodation}</div>` : ''}
            ${trip.notes ? `<div class="trip-notes">${trip.notes}</div>` : ''}
        `;
        
        // Click to focus on map
        card.addEventListener('click', () => {
            if (markers[trip.id]) {
                map.setView(
                    [trip.coordinates.lat, trip.coordinates.lng],
                    12
                );
                markers[trip.id].openPopup();
            }
        });
        
        tripsList.appendChild(card);
    });
}

// Add new trip
async function addTrip(formData) {
    showLoading(true);
    
    try {
        const token = await getAuthToken();
        
        const response = await fetch(`${API_BASE}/trips/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add trip');
        }
        
        const result = await response.json();
        
        // Reload trips
        await loadTrips();
        
        // Close modal
        closeModal();
        
        // Show success message
        alert('Trip added successfully!');
        
    } catch (error) {
        console.error('Error adding trip:', error);
        alert(`Failed to add trip: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

// Format date
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Capitalize first letter
function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Show/hide loading overlay
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('show');
    } else {
        overlay.classList.remove('show');
    }
}

// Modal management
function openModal() {
    document.getElementById('addTripModal').classList.add('open');
}

function closeModal() {
    document.getElementById('addTripModal').classList.remove('open');
    document.getElementById('addTripForm').reset();
}

// Toggle trips panel
function toggleTripsPanel() {
    const panel = document.getElementById('tripsPanel');
    panel.classList.toggle('open');
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Add Trip button
    document.getElementById('addTripBtn').addEventListener('click', openModal);
    
    // Close modal buttons
    document.getElementById('closeModalBtn').addEventListener('click', closeModal);
    document.getElementById('cancelBtn').addEventListener('click', closeModal);
    
    // Close panel
    document.getElementById('closePanelBtn').addEventListener('click', () => {
        document.getElementById('tripsPanel').classList.remove('open');
    });
    
    // Back button
    document.getElementById('backBtn').addEventListener('click', () => {
        window.location.href = '../Main/index.html';
    });
    
    // Form submission
    document.getElementById('addTripForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = {
            location: document.getElementById('location').value,
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value,
            status: document.getElementById('status').value,
            accommodation: document.getElementById('accommodation').value || null,
            notes: document.getElementById('notes').value || null
        };
        
        await addTrip(formData);
    });
    
    // Click stats to open trips panel
    document.querySelectorAll('.stat-card').forEach(card => {
        card.addEventListener('click', toggleTripsPanel);
    });
    
    // Set min date for start date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('startDate').min = today;
    
    // Update end date min when start date changes
    document.getElementById('startDate').addEventListener('change', (e) => {
        document.getElementById('endDate').min = e.target.value;
    });
});
