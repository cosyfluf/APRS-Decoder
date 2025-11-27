import tkinter as tk
from tkinter import ttk
import webbrowser
import os
import json
from datetime import datetime

class MapManager:
    def __init__(self):
        self.stations = {}
        self.map_file = "aprs_map.html"
        self.create_map_template()
        
    def create_map_template(self):
        """Erstellt die HTML-Kartendatei mit Leaflet"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>APRS Live Karte</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
    <style>
        body { margin: 0; padding: 0; }
        #map { height: 100vh; width: 100%; }
        .station-marker { 
            background: rgba(0, 100, 255, 0.8); 
            color: white; 
            padding: 4px 8px; 
            border-radius: 4px; 
            border: 2px solid white;
            font-weight: bold;
            font-size: 11px;
            text-shadow: 1px 1px 1px rgba(0,0,0,0.5);
            white-space: nowrap;
        }
        .info-panel {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            max-width: 300px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .station-item {
            margin: 5px 0;
            padding: 5px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
        }
        .station-item:hover {
            background: #f0f0f0;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        <h3 style="margin-top: 0;">APRS Stations</h3>
        <div><strong>Gesamt: </strong><span id="station-count">0</span></div>
        <div id="station-list" style="margin-top: 10px;"></div>
        <button onclick="clearAllStations()" style="margin-top: 10px; width: 100%;">Alle löschen</button>
    </div>
    
    <script>
        // Karte initialisieren
        var map = L.map('map').setView([50.1109, 8.6821], 6);  // Zentriert auf Deutschland
        
        // OpenStreetMap Layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
        
        // Marker Cluster
        var markers = L.markerClusterGroup({
            chunkedLoading: true,
            maxClusterRadius: 50
        });
        map.addLayer(markers);
        
        var stations = {};
        
        // APRS Symbole definieren
        var aprsSymbols = {
            '/[': {icon: '🚗', name: 'Auto', color: '#0066cc'},
            '/>': {icon: '🚙', name: 'SUV', color: '#0066cc'},
            '/\\\\': {icon: '🏠', name: 'Haus', color: '#cc0000'},
            '/]': {icon: '🏢', name: 'Gebäude', color: '#cc0000'},
            '/^': {icon: '✈️', name: 'Flugzeug', color: '#00cc00'},
            '/v': {icon: '🚤', name: 'Boot', color: '#0066cc'},
            '/-': {icon: '🚶', name: 'Fußgänger', color: '#cc00cc'},
            '/#': {icon: '📡', name: 'Digipeater', color: '#ff6600'},
            '/*': {icon: '⭐', name: 'Stern', color: '#ffcc00'},
            '/@': {icon: '🌀', name: 'Zyklon', color: '#00cccc'},
            'default': {icon: '📍', name: 'Position', color: '#666666'}
        };
        
        function getSymbolIcon(symbol) {
            return aprsSymbols[symbol] || aprsSymbols['default'];
        }
        
        function updateStation(callsign, lat, lng, symbol, timestamp, comment) {
            var symbolInfo = getSymbolIcon(symbol);
            
            // Alten Marker entfernen falls vorhanden
            if (stations[callsign]) {
                markers.removeLayer(stations[callsign]);
            }
            
            var icon = L.divIcon({
                className: 'station-marker',
                html: '<div style="display: flex; align-items: center; gap: 3px; background: ' + symbolInfo.color + ';">' + 
                      '<span style="font-size: 12px;">' + symbolInfo.icon + '</span>' +
                      '<span>' + callsign + '</span>' +
                      '</div>',
                iconSize: [80, 25],
                iconAnchor: [40, 12]
            });
            
            // Neuen Marker hinzufügen
            var marker = L.marker([lat, lng], {icon: icon})
                .bindPopup(createPopupContent(callsign, lat, lng, symbolInfo, timestamp, comment));
            
            markers.addLayer(marker);
            stations[callsign] = marker;
            
            // Stationsliste aktualisieren
            updateStationList();
        }
        
        function createPopupContent(callsign, lat, lng, symbolInfo, timestamp, comment) {
            var timeStr = timestamp ? new Date(timestamp).toLocaleString() : 'Unbekannt';
            return `
                <div style="min-width: 200px;">
                    <h3 style="margin: 0 0 10px 0;">${callsign}</h3>
                    <p><strong>Position:</strong><br>${lat.toFixed(4)}° N<br>${lng.toFixed(4)}° E</p>
                    <p><strong>Symbol:</strong> ${symbolInfo.icon} ${symbolInfo.name}</p>
                    <p><strong>Letztes Update:</strong><br>${timeStr}</p>
                    ${comment ? '<p><strong>Kommentar:</strong><br>' + comment + '</p>' : ''}
                    <div style="margin-top: 10px;">
                        <button onclick="zoomToStation('${callsign}')" style="margin-right: 5px;">Zentrieren</button>
                        <button onclick="removeStation('${callsign}')">Entfernen</button>
                    </div>
                </div>
            `;
        }
        
        function updateStationList() {
            var stationList = document.getElementById('station-list');
            var stationCount = document.getElementById('station-count');
            var html = '';
            var count = 0;
            
            for (var callsign in stations) {
                count++;
                var latlng = stations[callsign].getLatLng();
                html += `<div class="station-item" onclick="zoomToStation('${callsign}')">
                    <strong>${callsign}</strong><br>
                    <small>${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}</small>
                </div>`;
            }
            
            stationList.innerHTML = html || '<p>Keine Stationen</p>';
            stationCount.textContent = count;
        }
        
        function zoomToStation(callsign) {
            if (stations[callsign]) {
                var marker = stations[callsign];
                map.setView(marker.getLatLng(), 10);
                marker.openPopup();
            }
        }
        
        function removeStation(callsign) {
            if (stations[callsign]) {
                markers.removeLayer(stations[callsign]);
                delete stations[callsign];
                updateStationList();
            }
        }
        
        function clearAllStations() {
            markers.clearLayers();
            stations = {};
            updateStationList();
        }
        
        // Karte nach Laden anpassen
        setTimeout(function() {
            map.invalidateSize();
        }, 100);
    </script>
</body>
</html>
        """
        
        with open(self.map_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def get_map_widget(self, parent):
        """Erstellt ein Frame mit Web-Browser für die Karte"""
        try:
            from tkinterweb import HtmlFrame
            self.html_frame = HtmlFrame(parent, messages_enabled=False)
            self.html_frame.load_file(self.map_file)
            return self.html_frame
        except ImportError:
            # Fallback: Simple Frame mit Browser-Button
            frame = ttk.Frame(parent)
            label = ttk.Label(frame, text="tkinterweb nicht installiert. Karte kann im Browser geöffnet werden.")
            label.pack(pady=20)
            btn = ttk.Button(frame, text="Karte im Browser öffnen", command=self.open_in_browser)
            btn.pack(pady=10)
            return frame
    
    def open_in_browser(self):
        """Öffnet die Karte im Standard-Browser"""
        webbrowser.open('file://' + os.path.abspath(self.map_file))
    
    def add_station(self, callsign, latitude, longitude, symbol=None, comment=""):
        """Fügt eine Station zur Karte hinzu"""
        self.stations[callsign] = {
            'latitude': latitude,
            'longitude': longitude,
            'symbol': symbol or '/[',
            'timestamp': datetime.now().isoformat(),
            'comment': comment
        }
        
        # Update die Karte via JavaScript
        if hasattr(self, 'html_frame'):
            # Escape single quotes in comment for JavaScript
            escaped_comment = comment.replace("'", "\\'")
            js_code = f"""
            updateStation(
                '{callsign}', 
                {latitude}, 
                {longitude}, 
                '{symbol or "/["}', 
                '{datetime.now().isoformat()}', 
                '{escaped_comment}'
            );
            """
            try:
                self.html_frame.execute_script(js_code)
            except Exception as e:
                print(f"JavaScript error: {e}")
    
    def update_station(self, callsign, latitude, longitude, symbol=None, comment=""):
        """Aktualisiert eine bestehende Station"""
        self.add_station(callsign, latitude, longitude, symbol, comment)
    
    def remove_station(self, callsign):
        """Entfernt eine Station von der Karte"""
        if callsign in self.stations:
            del self.stations[callsign]
            
        if hasattr(self, 'html_frame'):
            js_code = f"removeStation('{callsign}');"
            try:
                self.html_frame.execute_script(js_code)
            except:
                pass
    
    def clear_all_stations(self):
        """Entfernt alle Stationen von der Karte"""
        self.stations.clear()
        
        if hasattr(self, 'html_frame'):
            js_code = "clearAllStations();"
            try:
                self.html_frame.execute_script(js_code)
            except:
                pass
    
    def get_station_count(self):
        """Gibt die Anzahl der aktuellen Stationen zurück"""
        return len(self.stations)
    
    def save_stations(self, filename="aprs_stations.json"):
        """Speichert die Stationen in eine JSON-Datei"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.stations, f, indent=2, ensure_ascii=False)
    
    def load_stations(self, filename="aprs_stations.json"):
        """Lädt Stationen aus einer JSON-Datei"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                stations = json.load(f)
                for callsign, data in stations.items():
                    self.add_station(
                        callsign,
                        data['latitude'],
                        data['longitude'],
                        data.get('symbol'),
                        data.get('comment', '')
                    )
        except FileNotFoundError:
            pass

# Testfunktion
if __name__ == "__main__":
    root = tk.Tk()
    root.title("APRS Map Test")
    root.geometry("800x600")
    
    map_manager = MapManager()
    map_frame = map_manager.get_map_widget(root)
    map_frame.pack(fill=tk.BOTH, expand=True)
    
    # Test-Stationen
    test_btn = tk.Button(root, text="Test-Stationen hinzufügen", 
                        command=lambda: map_manager.add_station("DL1TEST", 48.1351, 11.5820, "/[", "Test Station"))
    test_btn.pack(pady=5)
    
    root.mainloop()