import os
import requests
import threading
from PIL import Image, ImageTk, ImageDraw
import io

class IconManager:
    """
    Manages APRS Icons with local caching and auto-download.
    Ref: http://www.aprs.org/symbols.html
    """
    def __init__(self):
        self.cache = {} 
        self.base_url = "https://raw.githubusercontent.com/hessu/aprs-symbols/master/symbols/24x24"
        
        # Determine absolute path to ensure folder is found
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.local_dir = os.path.join(base_path, "storage")
        
        if not os.path.exists(self.local_dir):
            os.makedirs(self.local_dir)
        
        # Manual Override for specific symbols that are often wrong
        self.overrides = {
            '/#': 'digi',      # Primary Digi (Green Star)
            r'\#': 'digi',     # Alt Digi
            '/r': 'repeater',  # Repeater
            r'\r': 'repeater', 
            '/>': 'car',
            '/>': 'car',
            '/[': 'jogger',
            '/-': 'house',
            r'\-': 'house',
        }

        # Start background sync
        self.start_background_sync()

    def start_background_sync(self):
        t = threading.Thread(target=self._sync_worker, daemon=True)
        t.start()

    def _sync_worker(self):
        """Downloads common icons in background"""
        common_files = [
            'car', 'digi', 'green_star', 'repeater', 'house', 'jogger', 'truck', 
            'van', 'bike', 'motorcycle', 'yacht', 'ship', 'jeep', 'ambulance',
            'police', 'fire', 'balloon', 'plane', 'helicopter', 'shuttle',
            'phone', 'dxcluster', 'bbs', 'cloud', 'rain', 'snow'
        ]
        
        for filename in common_files:
            self._download_file(filename)

    def _download_file(self, filename):
        local_path = os.path.join(self.local_dir, f"{filename}.png")
        if not os.path.exists(local_path):
            try:
                url = f"{self.base_url}/{filename}.png"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
            except: pass

    def create_fallback_icon(self, color):
        """Creates a vector circle as fallback"""
        size = 32
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        # Outer ring
        draw.ellipse([2, 2, size-2, size-2], outline=color, width=3)
        # Inner dot
        draw.ellipse([10, 10, size-10, size-10], fill=color)
        return ImageTk.PhotoImage(image)

    def get_icon(self, table, code, fallback_color):
        key = f"{table}{code}"
        if key in self.cache: return self.cache[key]
        
        # 1. Check Overrides first (Manual Fixes)
        filename = self.overrides.get(key)
        
        # 2. General Mapping (Simplified for robustness)
        if not filename:
            if code == '>': filename = 'car'
            elif code == 'k': filename = 'truck'
            elif code == 'u': filename = 'truck'
            elif code == 'v': filename = 'van'
            elif code == '[': filename = 'jogger'
            elif code == '-': filename = 'house'
            elif code == '#': filename = 'digi'
            elif code == '*': filename = 'star'
            elif code == 'r': filename = 'repeater'
            elif code == 'a': filename = 'ambulance'
            elif code == 'y': filename = 'yacht'
            elif code == 's': filename = 'ship'
            elif code == 'j': filename = 'jeep'
            elif code == '_': filename = 'wx-station'
            elif code == 'p': filename = 'rover'
            
        # Default fallback name
        if not filename:
            filename = 'unknown'

        tk_image = None
        
        if filename:
            local_path = os.path.join(self.local_dir, f"{filename}.png")
            
            # Try to load from disk
            if os.path.exists(local_path):
                try:
                    image = Image.open(local_path).convert("RGBA")
                    image = image.resize((32, 32), Image.Resampling.LANCZOS)
                    tk_image = ImageTk.PhotoImage(image)
                except: pass
            else:
                # Not on disk? Try downloading NOW
                try:
                    self._download_file(filename)
                    if os.path.exists(local_path):
                        image = Image.open(local_path).convert("RGBA")
                        image = image.resize((32, 32), Image.Resampling.LANCZOS)
                        tk_image = ImageTk.PhotoImage(image)
                except: pass

        if tk_image is None:
            tk_image = self.create_fallback_icon(fallback_color)
        
        self.cache[key] = tk_image
        return tk_image