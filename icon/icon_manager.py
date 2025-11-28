import os
import requests
from PIL import Image, ImageTk, ImageDraw

class IconManager:
    """
    Manages APRS Icons using High-Res (128px) Spritesheets.
    Includes Debugging and Transparency Checks.
    """
    def __init__(self):
        self.cache = {} 
        self.sheets = {} 
        
        # Hessu High-Res Sheets
        self.sheet_config = {
            '0': "https://raw.githubusercontent.com/hessu/aprs-symbols/master/png/aprs-symbols-128-0.png", # Primary /
            '1': "https://raw.githubusercontent.com/hessu/aprs-symbols/master/png/aprs-symbols-128-1.png", # Secondary \
            '2': "https://raw.githubusercontent.com/hessu/aprs-symbols/master/png/aprs-symbols-128-2.png"  # Overlays
        }
        
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.local_dir = os.path.join(base_path, "storage")
        
        if not os.path.exists(self.local_dir):
            try: os.makedirs(self.local_dir)
            except: pass

        self._load_sheets()

    def _load_sheets(self):
        headers = {'User-Agent': 'Mozilla/5.0'}
        for idx, url in self.sheet_config.items():
            filename = f"aprs-symbols-128-{idx}.png"
            path = os.path.join(self.local_dir, filename)
            
            # Download
            if not os.path.exists(path):
                try:
                    print(f"[ICON INIT] Lade Sheet {idx}...")
                    r = requests.get(url, headers=headers, timeout=20)
                    if r.status_code == 200:
                        with open(path, 'wb') as f:
                            f.write(r.content)
                        print(f"[ICON INIT] Sheet {idx} OK.")
                    else:
                        print(f"[ICON INIT] Fehler HTTP {r.status_code} bei Sheet {idx}")
                except Exception as e:
                    print(f"[ICON INIT] Download Fehler: {e}")

            # Laden
            if os.path.exists(path):
                try:
                    self.sheets[idx] = Image.open(path).convert("RGBA")
                except Exception as e: 
                    print(f"[ICON INIT] Bildfehler Sheet {idx}: {e}")

    def create_fallback_icon(self, color):
        """Erzeugt einen 'Radar-Punkt'"""
        size = 32
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        # Dickerer Rand für bessere Sichtbarkeit
        draw.ellipse([2, 2, size-2, size-2], outline=color, width=3)
        draw.ellipse([10, 10, size-10, size-10], fill=color)
        return ImageTk.PhotoImage(image)

    def is_image_empty(self, img):
        """Prüft, ob ein Bild komplett transparent ist (Alpha-Kanal)"""
        extrema = img.getextrema()
        if len(extrema) == 4: # RGBA
            # extrema[3] ist der Alpha Kanal (min, max). Wenn max 0 ist, ist es unsichtbar.
            if extrema[3][1] == 0:
                return True
        return False

    def get_icon(self, table, code, fallback_color):
        key = f"{table}{code}"
        if key in self.cache: return self.cache[key]
        
        # --- BLATT AUSWAHL ---
        sheet_id = '0' # Primary /
        if table == '\\':
            sheet_id = '1' # Secondary \
        elif table.isalnum():
            sheet_id = '2' # Overlay 0-9, A-Z
            
        sheet = self.sheets.get(sheet_id)
        
        # Fallback wenn Sheet fehlt
        if not sheet:
            print(f"[ICON ERROR] Sheet {sheet_id} fehlt für {key}")
            tk_img = self.create_fallback_icon(fallback_color)
            self.cache[key] = tk_img
            return tk_img

        # --- BERECHNUNG ---
        try:
            char_idx = ord(code) - 33
            if char_idx < 0 or char_idx > 95:
                print(f"[ICON WARN] Ungültiger Code: {code} ({ord(code)})")
                tk_img = self.create_fallback_icon(fallback_color)
                self.cache[key] = tk_img
                return tk_img
                
            icon_size = 128
            icons_per_row = 16
            
            col = char_idx % icons_per_row
            row = char_idx // icons_per_row
            
            x = col * icon_size
            y = row * icon_size
            
            # --- DEBUGGING FÜR DICH ---
            # Das zeigt dir in der Konsole, was er tut. 
            # Wenn du einen Repeater empfängst, schau hier hin!
            # print(f"[ICON DEBUG] '{table}{code}' -> Sheet {sheet_id}, Zeile {row}, Spalte {col}")
            
            # Crop
            icon_crop = sheet.crop((x, y, x + icon_size, y + icon_size))
            
            # --- SICHERHEITSCHECK ---
            # Ist das ausgeschnittene Bild leer?
            if self.is_image_empty(icon_crop):
                print(f"[ICON WARN] Symbol '{table}{code}' ist auf dem Sheet leer/transparent!")
                tk_img = self.create_fallback_icon(fallback_color)
            else:
                # Resize
                icon_final = icon_crop.resize((32, 32), Image.Resampling.LANCZOS)
                tk_img = ImageTk.PhotoImage(icon_final)
            
            self.cache[key] = tk_img
            return tk_img
            
        except Exception as e:
            print(f"[ICON CRASH] {e}")
            tk_img = self.create_fallback_icon(fallback_color)
            self.cache[key] = tk_img
            return tk_img