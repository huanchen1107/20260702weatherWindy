// Taiwan CWA Weather Broadcast Visualization Logic

// State management
let mapInstance = null;      // Leaflet map instance (either standard Leaflet or from Windy)
let windyStore = null;        // Windy API store
let cwaMarkerGroup = null;    // Layer group for circle markers
let cwaLabelGroup = null;     // Layer group for numeric temperature text labels
let rawStations = [];         // Raw CWA station data list
let uniqueCounties = new Set();
let autoRefreshTimer = null;
let isWindyMode = false;

// Color scale by Temperature (matching design.md)
function getColorByTemperature(temp) {
    if (temp === null || temp === undefined) return "#94a3b8"; // Gray for missing
    if (temp < 10) return "#2b6cb0";
    if (temp < 15) return "#3182ce";
    if (temp < 20) return "#38a169";
    if (temp < 25) return "#ecc94b";
    if (temp < 30) return "#ed8936";
    if (temp < 35) return "#e53e3e";
    return "#9b2c2c";
}

// Format DateTime nicely
function formatDateTime(isoString) {
    if (!isoString) return "N/A";
    try {
        const dt = new Date(isoString);
        return dt.toLocaleString('zh-TW', { hour12: false });
    } catch (e) {
        return isoString;
    }
}

// Dynamic display length calculator for Asian characters
function padText(text, width) {
    return text || "";
}

// 1. Initial configuration fetch
async function initApp() {
    try {
        const response = await fetch("/api/config");
        const config = await response.json();
        
        if (config.windy_api_key && config.windy_api_key.trim() !== "") {
            console.log("Windy API key found. Attempting to initialize Windy...");
            loadWindyMap(config.windy_api_key);
        } else {
            console.log("No Windy API key configured. Booting fallback standard Leaflet map.");
            initFallbackMap();
        }
    } catch (e) {
        console.error("Failed to load app config. Booting fallback map: ", e);
        initFallbackMap();
    }
    
    // Load initial weather data
    await fetchWeatherData();
    
    // Setup event listeners
    setupEventListeners();
    
    // Start auto-refresh
    toggleAutoRefresh(document.getElementById("toggle-auto-refresh").checked);
}

// 2. Load Windy Map API
function loadWindyMap(apiKey) {
    // Dynamically inject Windy's bootloader script
    const script = document.createElement("script");
    script.src = "https://api.windy.com/assets/map-forecast/libBoot.js";
    script.async = true;
    
    script.onload = () => {
        const options = {
            key: apiKey,
            lat: 23.7,
            lon: 121.0,
            zoom: 8,
            overlay: "wind",
            verbose: false
        };
        
        try {
            windyInit(options, (windyAPI) => {
                const { map, store, broadcast } = windyAPI;
                mapInstance = map;
                windyStore = store;
                isWindyMode = true;
                
                console.log("Windy Map successfully initialized!");
                
                // Initialize CWA overlays on the Windy Leaflet instance
                initMapOverlays();
                
                // Sync UI controls with Windy status
                syncWindyLayerUI(store.get("overlay"));
                
                // Listen to Windy map updates to control label visibility based on zoom
                mapInstance.on("zoomend", handleZoomChange);
                
                // Listen to redraw finish events
                broadcast.on("redrawFinished", () => {
                    console.log("Windy background redraw finished");
                });
            });
        } catch (err) {
            console.error("Error during windyInit. Falling back to Leaflet.", err);
            initFallbackMap();
        }
    };
    
    script.onerror = () => {
        console.error("Failed to load Windy libBoot.js script. Falling back to Leaflet.");
        initFallbackMap();
    };
    
    document.head.appendChild(script);
}

// 3. Fallback Standard Leaflet Map Initialization
function initFallbackMap() {
    isWindyMode = false;
    
    // Toggle containers visibility
    document.getElementById("windy").classList.add("hidden");
    document.getElementById("fallback-map").classList.remove("hidden");
    
    // Update Badge status
    const badge = document.getElementById("map-mode-badge");
    badge.textContent = "Standard Mode";
    badge.className = "badge badge-fallback";
    
    // Update Sidebar Layer controls
    document.getElementById("windy-layers-selector").classList.add("hidden");
    document.getElementById("fallback-layers-selector").classList.remove("hidden");
    
    // Create standard Leaflet map
    mapInstance = L.map("fallback-map").setView([23.7, 121.0], 8);
    
    // Load CartoDB Dark Matter tiles (looks beautiful and dark, matches glassmorphism)
    const darkTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(mapInstance);
    
    // Save map tile layer reference on mapInstance to easily swap later
    mapInstance._tileLayers = {
        "carto-dark": darkTiles,
        "osm": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        })
    };
    
    initMapOverlays();
    
    // Monitor zoom changes
    mapInstance.on("zoomend", handleZoomChange);
}

// 4. Initialize Overlay Layer Groups
function initMapOverlays() {
    if (!mapInstance) return;
    
    cwaMarkerGroup = L.layerGroup().addTo(mapInstance);
    cwaLabelGroup = L.layerGroup().addTo(mapInstance);
}

// 5. Fetch weather data from backend API
async function fetchWeatherData() {
    try {
        const res = await fetch("/api/temperature/latest");
        const data = await res.json();
        
        rawStations = data.stations || [];
        
        // Update updated_at timestamp UI
        document.getElementById("last-update-time").textContent = formatDateTime(data.updated_at);
        
        // Extract unique counties for filter dropdown
        uniqueCounties.clear();
        rawStations.forEach(s => {
            if (s.county) uniqueCounties.add(s.county);
        });
        
        populateCountySelector();
        calculateAndDisplayStats();
        
        // Render layers
        renderWeatherLayers();
        
    } catch (e) {
        console.error("Error fetching CWA weather data: ", e);
        document.getElementById("last-update-time").textContent = "Sync Error";
    }
}

// 6. Populate county select options
function populateCountySelector() {
    const selector = document.getElementById("filter-county");
    const currentVal = selector.value;
    
    // Clear except first option
    selector.innerHTML = '<option value="">All Counties (Taiwan)</option>';
    
    // Sort counties alphabetically/regionally
    const sortedCounties = Array.from(uniqueCounties).sort();
    sortedCounties.forEach(county => {
        const opt = document.createElement("option");
        opt.value = county;
        opt.textContent = county;
        selector.appendChild(opt);
    });
    
    // Restore previous selection if valid
    if (uniqueCounties.has(currentVal)) {
        selector.value = currentVal;
    }
}

// 7. Calculate and render floating Statistics Box
function calculateAndDisplayStats() {
    if (rawStations.length === 0) return;
    
    let totalTemp = 0;
    let validTempCount = 0;
    let hottestTemp = -999;
    let hottestName = "N/A";
    
    rawStations.forEach(s => {
        if (s.temperature_c !== null && s.temperature_c !== undefined) {
            totalTemp += s.temperature_c;
            validTempCount++;
            
            if (s.temperature_c > hottestTemp) {
                hottestTemp = s.temperature_c;
                hottestName = s.station_name;
            }
        }
    });
    
    const avgTemp = validTempCount > 0 ? (totalTemp / validTempCount).toFixed(1) : "-.-";
    
    document.getElementById("stat-total-stations").textContent = rawStations.length;
    document.getElementById("stat-avg-temp").textContent = `${avgTemp}°C`;
    document.getElementById("stat-hottest-temp").textContent = hottestTemp > -999 ? `${hottestTemp.toFixed(1)}°C` : "-.-°C";
    document.getElementById("stat-hottest-name").textContent = hottestName;
    document.getElementById("stat-hottest-name").title = hottestName;
}

// 8. Draw station markers & text labels on the map
function renderWeatherLayers() {
    if (!mapInstance || !cwaMarkerGroup || !cwaLabelGroup) return;
    
    // Clear previous layers
    cwaMarkerGroup.clearLayers();
    cwaLabelGroup.clearLayers();
    
    // Read current filter settings
    const selectedCounty = document.getElementById("filter-county").value;
    const minTemp = parseFloat(document.getElementById("filter-temp-min").value);
    const searchQuery = document.getElementById("search-station").value.toLowerCase().trim();
    
    const showMarkersToggle = document.getElementById("toggle-cwa-layer").checked;
    const showLabelsToggle = document.getElementById("toggle-temp-labels").checked;
    const currentZoom = mapInstance.getZoom();
    
    // Filter stations
    const filteredStations = rawStations.filter(s => {
        // County filter
        if (selectedCounty && s.county !== selectedCounty) return false;
        
        // Min temperature filter
        if (s.temperature_c === null || s.temperature_c === undefined || s.temperature_c < minTemp) return false;
        
        // Search query (Station name or ID)
        if (searchQuery) {
            const nameMatch = s.station_name && s.station_name.toLowerCase().includes(searchQuery);
            const idMatch = s.station_id && s.station_id.toLowerCase().includes(searchQuery);
            if (!nameMatch && !idMatch) return false;
        }
        
        return true;
    });
    
    // Draw each station
    filteredStations.forEach(s => {
        const latLng = [s.lat, s.lon];
        
        // 8.1 Circle Marker
        if (showMarkersToggle) {
            const marker = L.circleMarker(latLng, {
                radius: 8,
                fillColor: getColorByTemperature(s.temperature_c),
                fillOpacity: 0.85,
                color: "#ffffff",
                weight: 1.5,
                title: s.station_name
            });
            
            // Build modern details popup layout
            const popupContent = `
                <div class="popup-header">
                    <div class="popup-title">${s.station_name}</div>
                    <div class="popup-subtitle">ID: ${s.station_id} | ${s.county || ""} ${s.town || ""}</div>
                </div>
                <div class="popup-details">
                    <div class="popup-detail-box">
                        <span class="lbl">Temperature</span>
                        <span class="val" style="color: ${getColorByTemperature(s.temperature_c)}">${s.temperature_c.toFixed(1)}°C</span>
                    </div>
                    <div class="popup-detail-box">
                        <span class="lbl">Humidity</span>
                        <span class="val">${s.humidity_percent !== null ? s.humidity_percent + '%' : 'N/A'}</span>
                    </div>
                    <div class="popup-detail-box">
                        <span class="lbl">Wind</span>
                        <span class="val">${s.wind_speed_mps !== null ? s.wind_speed_mps.toFixed(1) + ' m/s' : 'N/A'}</span>
                    </div>
                    <div class="popup-detail-box">
                        <span class="lbl">Rain</span>
                        <span class="val">${s.precipitation_mm !== null ? s.precipitation_mm.toFixed(1) + ' mm' : 'N/A'}</span>
                    </div>
                </div>
                <div class="popup-extremes">
                    <div class="popup-extreme-box high">
                        <i class="fa-solid fa-temperature-arrow-up"></i>
                        <span>High: ${s.daily_high_temperature !== null ? s.daily_high_temperature.toFixed(1) + '°C' : 'N/A'}</span>
                    </div>
                    <div class="popup-extreme-box low">
                        <i class="fa-solid fa-temperature-arrow-down"></i>
                        <span>Low: ${s.daily_low_temperature !== null ? s.daily_low_temperature.toFixed(1) + '°C' : 'N/A'}</span>
                    </div>
                </div>
                <div class="popup-footer">Observed: ${new Date(s.observed_at).toLocaleTimeString('zh-TW', {hour: '2-digit', minute:'2-digit'})}</div>
            `;
            
            marker.bindPopup(popupContent, {
                maxWidth: 260,
                className: "custom-leaflet-popup"
            });
            
            marker.addTo(cwaMarkerGroup);
        }
        
        // 8.2 Numeric Text Bubble Label (shown when zoom level >= 9 and toggle is active)
        if (showLabelsToggle && currentZoom >= 9) {
            const tempLabelIcon = L.divIcon({
                className: 'leaflet-station-label',
                html: `<div class="station-temp-bubble" style="border-color: ${getColorByTemperature(s.temperature_c)}">${s.temperature_c.toFixed(1)}°</div>`,
                iconSize: [0, 0]
            });
            
            const labelMarker = L.marker(latLng, { icon: tempLabelIcon });
            labelMarker.addTo(cwaLabelGroup);
        }
    });
}

// 9. Show/Hide text labels depending on Zoom level
function handleZoomChange() {
    if (!mapInstance || !cwaLabelGroup) return;
    
    const showLabelsToggle = document.getElementById("toggle-temp-labels").checked;
    const currentZoom = mapInstance.getZoom();
    
    if (showLabelsToggle && currentZoom >= 9) {
        // Redraw layers to render labels
        renderWeatherLayers();
    } else {
        // Clear labels if zoom is too low or toggle is off
        cwaLabelGroup.clearLayers();
    }
}

// 10. Wire up all UI Control listeners
function setupEventListeners() {
    // CWA Overlays triggers
    document.getElementById("toggle-cwa-layer").addEventListener("change", renderWeatherLayers);
    document.getElementById("toggle-temp-labels").addEventListener("change", renderWeatherLayers);
    
    // Filters triggers
    document.getElementById("filter-county").addEventListener("change", renderWeatherLayers);
    
    const tempSlider = document.getElementById("filter-temp-min");
    const tempSliderVal = document.getElementById("temp-range-val");
    tempSlider.addEventListener("input", (e) => {
        tempSliderVal.textContent = `${e.target.value}°C`;
        renderWeatherLayers();
    });
    
    document.getElementById("search-station").addEventListener("input", renderWeatherLayers);
    
    // Auto refresh trigger
    document.getElementById("toggle-auto-refresh").addEventListener("change", (e) => {
        toggleAutoRefresh(e.target.checked);
    });
    
    // Sync Button
    document.getElementById("btn-refresh").addEventListener("click", async () => {
        const btn = document.getElementById("btn-refresh");
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Syncing Data...';
        
        try {
            const response = await fetch("/api/temperature/refresh", { method: "POST" });
            const result = await response.json();
            console.log("Manual Cache Refresh completed:", result);
            await fetchWeatherData();
        } catch (e) {
            console.error("Manual refresh call failed:", e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Sync Observation Data';
        }
    });
    
    // Windy Overlay Selector Buttons
    const layerButtons = document.querySelectorAll("#windy-layers-selector .btn-layer");
    layerButtons.forEach(btn => {
        btn.addEventListener("click", (e) => {
            layerButtons.forEach(b => b.classList.remove("active"));
            const targetBtn = e.currentTarget;
            targetBtn.classList.add("active");
            
            const targetLayer = targetBtn.getAttribute("data-layer");
            if (isWindyMode && windyStore) {
                windyStore.set("overlay", targetLayer);
            }
        });
    });
    
    // Fallback standard Leaflet Base Map Selector Buttons
    const fallbackTileButtons = document.querySelectorAll("#fallback-layers-selector .btn-layer");
    fallbackTileButtons.forEach(btn => {
        btn.addEventListener("click", (e) => {
            fallbackTileButtons.forEach(b => b.classList.remove("active"));
            const targetBtn = e.currentTarget;
            targetBtn.classList.add("active");
            
            const targetTileKey = targetBtn.getAttribute("data-tile");
            if (mapInstance && mapInstance._tileLayers) {
                // Remove all tile layers
                Object.values(mapInstance._tileLayers).forEach(layer => {
                    mapInstance.removeLayer(layer);
                });
                // Add the selected tile layer
                mapInstance._tileLayers[targetTileKey].addTo(mapInstance);
            }
        });
    });
}

// 11. Sync active buttons with Windy store
function syncWindyLayerUI(activeLayer) {
    const layerButtons = document.querySelectorAll("#windy-layers-selector .btn-layer");
    layerButtons.forEach(btn => {
        if (btn.getAttribute("data-layer") === activeLayer) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });
}

// 12. Turn Auto Refresh on/off
function toggleAutoRefresh(enable) {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
    
    if (enable) {
        console.log("Auto-refresh enabled. Sync interval: 5 minutes.");
        autoRefreshTimer = setInterval(async () => {
            console.log("Auto-refresh trigger: fetching CWA weather data...");
            await fetchWeatherData();
        }, 300000); // 5 minutes
    } else {
        console.log("Auto-refresh disabled.");
    }
}

// Kickstart the app on load
window.addEventListener("DOMContentLoaded", initApp);
