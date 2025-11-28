import os
import requests
from PIL import Image, ImageTk, ImageDraw

class IconManager:
    """
    Manages APRS Icons using High-Res (128px) Spritesheets from hessu.
    
    Mapping Logic (APRS 1.2 Spec):
      - '/' -> Primary Table (Sheet 0)
      - '\' -> Secondary Table (Sheet 1)
      - [0-9, A-Z] -> Overlays. These use the Secondary Table (Sheet 1) symbols,
                      usually with an overlay character. We map them to Sheet 1.
    """
    def __init__(self):
        self.cache = {} 
        self.sheets = {} 
        
        # URLs to High-Res Sheets
        self.sheet_config = {
            '0': "https://raw.githubusercontent.com/hessu/aprs-symbols/master/png/aprs-symbols-128-0.png",
            '1': "https://raw.githubusercontent.com/hessu/aprs-symbols/master/png/aprs-symbols-128-1.png",
            '2': "https://raw.githubusercontent.com/hessu/aprs-symbols/master/png/aprs-symbols-128-2.png"
        }
        
        # Local storage path
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.local_dir = os.path.join(base_path, "storage")
        
        if not os.path.exists(self.local_dir):
            try: os.makedirs(self.local_dir)
            except: pass

        # Load sheets on init
        self._load_sheets()

    def _load_sheets(self):
        headers = {'User-Agent': 'Mozilla/5.0'}
        for idx, url in self.sheet_config.items():
            filename = f"aprs-symbols-128-{idx}.png"
            path = os.path.join(self.local_dir, filename)
            
            # Download if missing
            if not os.path.exists(path):
                try:
                    # print(f"[ICON] Downloading Sheet {idx}...")
                    r = requests.get(url, headers=headers, timeout=15)
                    if r.status_code == 200:
                        with open(path, 'wb') as f:
                            f.write(r.content)
                except Exception: pass

            # Load into Memory
            if os.path.exists(path):
                try:
                    self.sheets[idx] = Image.open(path).convert("RGBA")
                except Exception: pass

    def create_fallback_icon(self, color):
        """Creates a generic radar dot"""
        size = 32
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([2, 2, size-2, size-2], outline=color, width=2)
        draw.ellipse([8, 8, size-8, size-8], fill=color)
        return ImageTk.PhotoImage(image)

    def get_icon(self, table, code, fallback_color):
        # Cache Key
        key = f"{table}{code}"
        if key in self.cache: return self.cache[key]
        
        # --- SHEET SELECTION LOGIC ---
        sheet_id = '0' # Default: Primary (/)
        
        if table == '/':
            sheet_id = '0' # Primary
        elif table == '\\':
            sheet_id = '1' # Secondary
        elif table.isalnum(): 
            # APRS Spec: Digits/Letters as table ID mean "Overlay".
            # The base symbol comes from the Alternate/Secondary table (Sheet 1).
            sheet_id = '1'
            
        sheet = self.sheets.get(sheet_id)
        
        # Fallback if sheet failed to load
        if not sheet:
            tk_img = self.create_fallback_icon(fallback_color)
            self.cache[key] = tk_img
            return tk_img

        # --- GRID CALCULATION ---
        # Grid is ASCII based starting at '!' (33)
        # 16 icons per row
        try:
            char_idx = ord(code) - 33
            
            if char_idx < 0 or char_idx > 95:
                # Invalid symbol code
                tk_img = self.create_fallback_icon(fallback_color)
                self.cache[key] = tk_img
                return tk_img
                
            icon_size = 128
            icons_per_row = 16
            
            col = char_idx % icons_per_row
            row = char_idx // icons_per_row
            
            x = col * icon_size
            y = row * icon_size
            
            # --- CROP & RESIZE ---
            icon_crop = sheet.crop((x, y, x + icon_size, y + icon_size))
            icon_final = icon_crop.resize((32, 32), Image.Resampling.LANCZOS)
            
            tk_img = ImageTk.PhotoImage(icon_final)
            
            self.cache[key] = tk_img
            return tk_img
            
        except Exception:
            tk_img = self.create_fallback_icon(fallback_color)
            self.cache[key] = tk_img
            return tk_img