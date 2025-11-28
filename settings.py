import json
import os

CONFIG_FILE = "config.json"

# --- LANGUAGES ---
LANGUAGES = {
    "English": {
        "WINDOW_TITLE": "APRS DECODER - U96 EDITION",
        "AUDIO_INPUT": "Audio Input Device",
        "START": "Start Receiver",
        "STOP": "Stop Receiver",
        "STATUS_READY": "System Ready",
        "STATUS_LISTENING": "Listening on 144.800 MHz (UTC)",
        "SCOPE_TITLE": "Signal Analysis",
        "MAP_TITLE": "Tactical Map",
        "LOG_TITLE": "Station Log",
        "COL_TIME": "Time (UTC)",
        "COL_CALL": "Callsign",
        "COL_SYM": "Icon",
        "COL_MSG": "Message",
        "BTN_SETTINGS": "Settings",
        "BTN_SAVE_LOG": "Save Log (CSV)",
        "LBL_THEME": "Visual Theme:",
        "LBL_LANG": "Language:",
        "LBL_AUDIO": "Audio Device:",
        "BTN_CLOSE_SETT": "Save & Close"
    },
    "Deutsch": {
        "WINDOW_TITLE": "APRS DECODER - U96 EDITION",
        "AUDIO_INPUT": "Audio Eingabegerät",
        "START": "Starten",
        "STOP": "Stoppen",
        "STATUS_READY": "Bereit",
        "STATUS_LISTENING": "Empfange auf 144.800 MHz (UTC)",
        "SCOPE_TITLE": "Signal Analyse",
        "MAP_TITLE": "Taktische Karte",
        "LOG_TITLE": "Logbuch",
        "COL_TIME": "Zeit (UTC)",
        "COL_CALL": "Rufzeichen",
        "COL_SYM": "Symbol",
        "COL_MSG": "Nachricht",
        "BTN_SETTINGS": "Einstellungen",
        "BTN_SAVE_LOG": "Log Speichern",
        "LBL_THEME": "Design Thema:",
        "LBL_LANG": "Sprache:",
        "LBL_AUDIO": "Audio Gerät:",
        "BTN_CLOSE_SETT": "Speichern & Schließen"
    }
}

# --- THEMES ---
THEMES = {
    "Windows (Default)": {
        "bg": "#f0f0f0", "fg": "black", "panel": "#e0e0e0", 
        "accent": "#0078d7", "warn": "red", "grid": "#cccccc",
        "font": ("Segoe UI", 9), "font_bold": ("Segoe UI", 9, "bold"),
        "ttk_theme": "vista" if os.name == 'nt' else 'clam',
        "scope_bg": "white", "scope_fg": "blue", "scope_line": "black",
        "map_server": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
    },
    "U96 - Das Boot": {
        "bg": "#121212", "fg": "#33ff33", "panel": "#1e1e1e",
        "accent": "#00cc00", "warn": "#ff3333", "grid": "#004400",
        "font": ("Consolas", 10), "font_bold": ("Consolas", 10, "bold"),
        "ttk_theme": "clam",
        "scope_bg": "black", "scope_fg": "#33ff33", "scope_line": "#00cc00",
        "map_server": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
    },
    "80s Synthwave": {
        "bg": "#2b213a", "fg": "#05ffa1", "panel": "#241b31", 
        "accent": "#ff00c1", "warn": "#ff71ce", "grid": "#4d266e", 
        "font": ("Courier New", 10), "font_bold": ("Courier New", 10, "bold"),
        "ttk_theme": "clam",
        "scope_bg": "#120a1f", "scope_fg": "#05ffa1", "scope_line": "#ff00c1",
        "map_server": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
    }
}

class SettingsManager:
    def __init__(self):
        self.config = self.load_config()
        
    def load_config(self):
        default = {
            "theme": "Windows (Default)", 
            "language": "English",
            "audio_device_index": 0
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    # Merge with defaults to prevent errors on new keys
                    default.update(data)
                    return default
            except:
                return default
        return default

    def save_config(self, theme, lang, audio_idx):
        self.config["theme"] = theme
        self.config["language"] = lang
        self.config["audio_device_index"] = audio_idx
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f)

    def get_text(self, key):
        lang = self.config.get("language", "English")
        return LANGUAGES[lang].get(key, key)

    def get_style(self):
        theme_name = self.config.get("theme", "Windows (Default)")
        return THEMES.get(theme_name, THEMES["Windows (Default)"])