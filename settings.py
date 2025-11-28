import json
import os
import tkinter as tk
from tkinter import ttk

CONFIG_FILE = "config.json"

# --- LANGUAGE PACKS ---
LANGUAGES = {
    "English": {
        "WINDOW_TITLE": "APRS DECODER - U96 EDITION",
        "AUDIO_INPUT": "Audio Input Device",
        "START": "Start Receiver",
        "STOP": "Stop Receiver",
        "STATUS_READY": "System Ready - Standby",
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
        "SETTINGS_TITLE": "Configuration",
        "LBL_THEME": "Visual Theme:",
        "LBL_LANG": "Language:",
        "BTN_SAVE": "Apply & Close"
    },
    "Deutsch": {
        "WINDOW_TITLE": "APRS DECODER - U96 EDITION",
        "AUDIO_INPUT": "Audio Eingabegerät",
        "START": "Empfänger Starten",
        "STOP": "Empfänger Stoppen",
        "STATUS_READY": "System Bereit",
        "STATUS_LISTENING": "Empfange auf 144.800 MHz (UTC)",
        "SCOPE_TITLE": "Signal Analyse",
        "MAP_TITLE": "Taktische Karte",
        "LOG_TITLE": "Stations-Logbuch",
        "COL_TIME": "Zeit (UTC)",
        "COL_CALL": "Rufzeichen",
        "COL_SYM": "Symbol",
        "COL_MSG": "Nachricht",
        "BTN_SETTINGS": "Einstellungen",
        "BTN_SAVE_LOG": "Log Speichern (CSV)",
        "SETTINGS_TITLE": "Konfiguration",
        "LBL_THEME": "Design Thema:",
        "LBL_LANG": "Sprache:",
        "BTN_SAVE": "Übernehmen & Schließen"
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
        default = {"theme": "Windows (Default)", "language": "English"}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                return default
        return default

    def save_config(self, theme, lang):
        self.config["theme"] = theme
        self.config["language"] = lang
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f)

    def get_text(self, key):
        lang = self.config.get("language", "English")
        return LANGUAGES[lang].get(key, key)

    def get_style(self):
        theme_name = self.config.get("theme", "Windows (Default)")
        return THEMES.get(theme_name, THEMES["Windows (Default)"])

class SettingsWindow:
    def __init__(self, parent, manager, apply_callback):
        self.window = tk.Toplevel(parent)
        self.manager = manager
        self.apply_callback = apply_callback # Funktion zum Live-Update
        self.txt = manager.get_text
        
        # Fenster Konfiguration (Modal/Transient)
        self.window.title(self.txt("SETTINGS_TITLE"))
        self.window.geometry("400x300")
        self.window.resizable(False, False)
        
        # Zentrieren relativ zum Hauptfenster
        x = parent.winfo_x() + 50
        y = parent.winfo_y() + 50
        self.window.geometry(f"+{x}+{y}")
        
        # Macht das Fenster zu einem Teil des Hauptfensters (kein eigener Taskbar Eintrag)
        self.window.transient(parent)
        # Fokus festhalten (Modal)
        self.window.grab_set()
        
        style = manager.get_style()
        self.window.configure(bg=style["bg"])
        
        frame = tk.Frame(self.window, bg=style["bg"], padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Language
        lbl_lang = tk.Label(frame, text=self.txt("LBL_LANG"), bg=style["bg"], fg=style["fg"], font=style["font_bold"])
        lbl_lang.pack(anchor=tk.W, pady=(0, 5))
        
        self.var_lang = tk.StringVar(value=manager.config["language"])
        cb_lang = ttk.Combobox(frame, textvariable=self.var_lang, values=list(LANGUAGES.keys()), state="readonly")
        cb_lang.pack(fill=tk.X, pady=(0, 15))
        
        # Theme
        lbl_theme = tk.Label(frame, text=self.txt("LBL_THEME"), bg=style["bg"], fg=style["fg"], font=style["font_bold"])
        lbl_theme.pack(anchor=tk.W, pady=(0, 5))
        
        self.var_theme = tk.StringVar(value=manager.config["theme"])
        cb_theme = ttk.Combobox(frame, textvariable=self.var_theme, values=list(THEMES.keys()), state="readonly")
        cb_theme.pack(fill=tk.X, pady=(0, 20))
        
        # Save Button
        btn_save = tk.Button(frame, text=self.txt("BTN_SAVE"), command=self.save, 
                           bg=style["panel"], fg=style["fg"])
        btn_save.pack(pady=10)
        
    def save(self):
        # Speichern
        self.manager.save_config(self.var_theme.get(), self.var_lang.get())
        # Callback aufrufen (Live Update in main.py)
        self.apply_callback()
        # Fenster schließen
        self.window.destroy()