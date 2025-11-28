import os
import requests
import threading
from PIL import Image, ImageTk, ImageDraw

class IconManager:
    """
    Manages APRS Icons with local caching and auto-download.
    """
    def __init__(self):
        self.cache = {} # Memory cache (Tkinter Images)
        self.base_url = "https://raw.githubusercontent.com/hessu/aprs-symbols/master/symbols/24x24"
        self.local_dir = "icon" # Local folder name
        
        # Ensure the directory exists
        if not os.path.exists(self.local_dir):
            os.makedirs(self.local_dir)
        
        # --- PRIMARY TABLE ('/') ---
        self.primary_table = {
            '!': 'police', '"': 'reserved', '#': 'digi', '$': 'phone', '%': 'dxcluster',
            '&': 'hf-gateway', "'": 'plane-small', '(': 'mobile-sat', ')': 'wheelchair',
            '*': 'snowmobile', '+': 'red-cross', ',': 'boy-scout', '-': 'house',
            '.': 'x', '/': 'red_dot', '0': 'circle', '1': 'event', '2': 'tornado',
            '3': 'cloud', '4': 'fog', '5': 'rain', '6': 'snow', '7': 'thunder',
            '8': 'hurricane', '9': 'cloud-sun', ':': 'fire', ';': 'campground',
            '<': 'motorcycle', '=': 'train', '>': 'car', '?': 'server', '@': 'hurricane',
            'A': 'aid', 'B': 'bbs', 'C': 'canoe', 'D': 'None', 'E': 'eyeball',
            'F': 'tractor', 'G': 'grid', 'H': 'hotel', 'I': 'tcpip', 'J': 'school',
            'K': 'pc', 'L': 'log', 'M': 'mac', 'N': 'nts', 'O': 'balloon',
            'P': 'police', 'Q': 'recreational', 'R': 'recreational', 'S': 'shuttle',
            'T': 'sstv', 'U': 'bus', 'V': 'atv', 'W': 'wx-service', 'X': 'helicopter',
            'Y': 'yacht', 'Z': 'shelter', '[': 'jogger', '\\': 'triangle', ']': 'mail',
            '^': 'plane', '_': 'wx-station', '`': 'dish', 'a': 'ambulance', 'b': 'bike',
            'c': 'ic', 'd': 'firestation', 'e': 'horse', 'f': 'fire-truck', 'g': 'glider',
            'h': 'hospital', 'i': 'island', 'j': 'jeep', 'k': 'truck', 'l': 'laptop',
            'm': 'mic-e', 'n': 'node', 'o': 'eoc', 'p': 'rover', 'q': 'grid',
            'r': 'repeater', 's': 'ship', 't': 'truck-stop', 'u': 'truck', 'v': 'van',
            'w': 'water', 'x': 'x', 'y': 'yagi', 'z': 'shelter'
        }
        
        # --- SECONDARY / ALTERNATE TABLE ('\') ---
        self.secondary_table = {
            '!': 'emergency', '#': 'digi_green', '$': 'bank', '&': 'hf-gateway-diamond',
            "'": 'crash', '(': 'cloud', ')': 'cloud-sun', '*': 'snow', '+': 'church',
            ',': 'girl-scout', '-': 'house-banned', '.': 'unknown', '/': 'waypoint',
            '0': 'circle', '8': '802.11', ':': 'fire', ';': 'park', '<': 'motorcycle',
            '>': 'car', '?': 'info', '@': 'hurricane', 'A': 'box', 'B': 'bbs',
            'C': 'coastguard', 'D': 'depot', 'E': 'smoke', 'F': 'tractor', 'H': 'hotel',
            'I': 'tcpip', 'J': 'school', 'K': 'pc', 'L': 'log', 'M': 'mac',
            'N': 'nts', 'O': 'balloon', 'P': 'parking', 'Q': 'recreational', 'R': 'recreational',
            'S': 'shuttle', 'T': 'sstv', 'U': 'bus', 'V': 'atv', 'W': 'wx-service',
            'X': 'helicopter', 'Y': 'yacht', 'Z': 'shelter', '[': 'wall', '\\': 'triangle',
            ']': 'mail', '^': 'plane-large', '_': 'wx-station', '`': 'dish', 'a': 'ambulance',
            'b': 'bike', 'c': 'ic', 'd': 'firestation', 'e': 'horse', 'f': 'fire-truck',
            'g': 'glider', 'h': 'hospital', 'i': 'island', 'j': 'jeep', 'k': 'truck',
            'l': 'laptop', 'm': 'mic-e', 'n': 'node', 'o': 'eoc', 'p': 'rover',
            'q': 'grid', 'r': 'repeater', 's': 'ship', 't': 'truck-stop', 'u': 'truck',
            'v': 'van', 'w': 'water', 'x': 'x', 'y': 'yagi', 'z': 'shelter'
        }

        # Start background check/download on initialization
        self.start_background_sync()

    def start_background_sync(self):
        """Starts a thread to check and download missing icons."""
        t = threading.Thread(target=self._sync_worker, daemon=True)
        t.start()

    def _sync_worker(self):
        """Worker thread: Iterates all known symbols and downloads if missing."""
        # Collect all unique filenames from both tables
        all_files = set(list(self.primary_table.values()) + list(self.secondary_table.values()))
        
        for filename in all_files:
            if filename == 'None' or filename == 'unknown':
                continue
                
            local_path = os.path.join(self.local_dir, f"{filename}.png")
            
            # Check if file exists locally
            if not os.path.exists(local_path):
                # Download if missing
                try:
                    url = f"{self.base_url}/{filename}.png"
                    response = requests.get(url, timeout=5) # 5s timeout per file
                    if response.status_code == 200:
                        with open(local_path, 'wb') as f:
                            f.write(response.content)
                        # Optional: Print to console for debugging
                        # print(f"Downloaded: {filename}.png")
                except Exception as e:
                    # Ignore connection errors (offline mode)
                    pass

    def create_fallback_icon(self, color):
        """Creates a generic radar dot in memory."""
        size = 32
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([2, 2, size-2, size-2], outline=color, width=2)
        draw.ellipse([10, 10, size-10, size-10], fill=color)
        return ImageTk.PhotoImage(image)

    def get_icon(self, table, code, fallback_color):
        """
        Returns a Tkinter Image.
        1. Checks Memory Cache.
        2. Checks Local Disk.
        3. If missing on disk, tries immediate download (and save).
        4. Fallback to generated dot.
        """
        key = f"{table}{code}"
        if key in self.cache: return self.cache[key]
        
        # Determine Filename
        filename = None
        if table == '/':
            filename = self.primary_table.get(code)
        elif table == '\\':
            filename = self.secondary_table.get(code)
        elif table.isalnum():
             filename = self.primary_table.get(code)
        
        if not filename:
             filename = self.primary_table.get(code)

        tk_image = None
        
        if filename and filename != 'None':
            local_path = os.path.join(self.local_dir, f"{filename}.png")
            
            # 1. Try Loading from Disk
            if os.path.exists(local_path):
                try:
                    image = Image.open(local_path).convert("RGBA")
                    image = image.resize((32, 32), Image.Resampling.LANCZOS)
                    tk_image = ImageTk.PhotoImage(image)
                except:
                    pass # File corrupted?
            
            # 2. If not on disk, try immediate download (fallback logic)
            if tk_image is None:
                try:
                    url = f"{self.base_url}/{filename}.png"
                    response = requests.get(url, timeout=1)
                    if response.status_code == 200:
                        # Save to disk
                        with open(local_path, 'wb') as f:
                            f.write(response.content)
                        # Load to memory
                        image = Image.open(local_path).convert("RGBA")
                        image = image.resize((32, 32), Image.Resampling.LANCZOS)
                        tk_image = ImageTk.PhotoImage(image)
                except:
                    pass

        # 3. Fallback Generation
        if tk_image is None:
            tk_image = self.create_fallback_icon(fallback_color)
        
        # Cache in memory
        self.cache[key] = tk_image
        return tk_image