import json
import threading
import webbrowser
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

class MapServer:
    def __init__(self, port=8000):
        self.stations = {}
        self.port = port
        self.server = None
        self.thread = None
        
    def start(self):
        self.update_json()
        self.create_html()
        
        handler = SimpleHTTPRequestHandler
        try:
            self.server = HTTPServer(('localhost', self.port), handler)
            self.thread = threading.Thread(target=self.server.serve_forever)
            self.thread.daemon = True
            self.thread.start()
            print(f"Map Server läuft: http://localhost:{self.port}/aprs_map.html")
            return True
        except OSError:
            print(f"Port {self.port} ist belegt.")
            return False
            
    def update_station(self, packet):
        if not packet.latitude: return
        
        # Daten für die Web-Karte aufbereiten
        self.stations[packet.callsign_src] = {
            'lat': packet.latitude,
            'lon': packet.longitude,
            'symbol': packet.symbol,
            'comment': packet.comment,
            'time': packet.timestamp.strftime('%H:%M:%S')
        }
        self.update_json()
        
    def update_json(self):
        # Schreibt die Daten in eine Datei, die das JS pollt
        with open('stations.json', 'w') as f:
            json.dump(self.stations, f)
            
    def open_browser(self):
        webbrowser.open(f'http://localhost:{self.port}/aprs_map.html')

    def create_html(self):
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>APRS Live Map</title>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <style>body { margin:0; } #map { height: 100vh; }</style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([51.16, 10.45], 6); // Deutschland zentriert
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OSM contributors'
        }).addTo(map);
        
        var markers = {};
        
        function updateMap() {
            fetch('stations.json?t=' + Date.now())
                .then(response => response.json())
                .then(data => {
                    for (var call in data) {
                        var st = data[call];
                        var content = `<b>${call}</b><br>${st.time}<br>${st.comment}`;
                        
                        if (markers[call]) {
                            markers[call].setLatLng([st.lat, st.lon]).setPopupContent(content);
                        } else {
                            markers[call] = L.marker([st.lat, st.lon])
                                .bindPopup(content)
                                .addTo(map);
                        }
                    }
                });
        }
        setInterval(updateMap, 2000); // Alle 2 Sekunden aktualisieren
        updateMap();
    </script>
</body>
</html>
        """
        with open('aprs_map.html', 'w', encoding='utf-8') as f:
            f.write(html)