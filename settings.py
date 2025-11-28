import json
import os
import tkinter as tk
from tkinter import ttk

CONFIG_FILE = "config.json"

# --- SPRACHPAKETE ---
LANGUAGES = {
    "English": {
        "WINDOW_TITLE": "APRS DECODER",
        "AUDIO_INPUT": "Audio Input Device",
        "START": "Start Receiver",
        "STOP": "Stop Receiver",
        "STATUS_READY": "System Ready",
        "STATUS_LISTENING": "Listening on 144.800 MHz",
        "SCOPE_TITLE": "Signal Analysis",
        "MAP_TITLE": "Tactical Map",
        "LOG_TITLE": "Station Log",
        "COL_TIME": "Time",
        "COL_CALL": "Callsign",
        "COL_SYM": "Icon",
        "COL_MSG": "Message",
        "BTN_SETTINGS": "Settings",
        "SETTINGS_TITLE": "Configuration",
        "LBL_THEME": "Visual Theme:",
        "LBL_LANG": "Language:",
        "BTN_SAVE": "Save & Restart",
        "RESTART_MSG": "Please restart the application to apply changes."
    },
    "Deutsch": {
        "WINDOW_TITLE": "APRS DECODER",
        "AUDIO_INPUT": "Audio Eingabegerät",
        "START": "Empfänger Starten",
        "STOP": "Empfänger Stoppen",
        "STATUS_READY": "System Bereit",
        "STATUS_LISTENING": "Empfange auf 144.800 MHz",
        "SCOPE_TITLE": "Signal Analyse",
        "MAP_TITLE": "Taktische Karte",
        "LOG_TITLE": "Stations-Logbuch",
        "COL_TIME": "Zeit",
        "COL_CALL": "Rufzeichen",
        "COL_SYM": "Symbol",
        "COL_MSG": "Nachricht",
        "BTN_SETTINGS": "Einstellungen",
        "SETTINGS_TITLE": "Konfiguration",
        "LBL_THEME": "Design Thema:",
        "LBL_LANG": "Sprache:",
        "BTN_SAVE": "Speichern & Neustart",
        "RESTART_MSG": "Bitte starten Sie das Programm neu, um die Änderungen anzuwenden."
    }
}

# --- THEMES ---
THEMES = {
    "Windows (Default)": {
        "bg": "#f0f0f0", "fg": "black", "panel": "#e0e0e0", 
        "accent": "#0078d7", "warn": "red", "grid": "#cccccc",
        "font": ("Segoe UI", 9), "font_bold": ("Segoe UI", 9, "bold"),
        "ttk_theme": "vista" if os.name == 'nt' else 'clam',
        "scope_bg": "white", "scope_fg": "blue", "scope_line": "black"
    },
    "U96 - Das Boot": {
        "bg": "#121212", "fg": "#33ff33", "panel": "#1e1e1e",
        "accent": "#00cc00", "warn": "#ff3333", "grid": "#004400",
        "font": ("Consolas", 10), "font_bold": ("Consolas", 10, "bold"),
        "ttk_theme": "clam",
        "scope_bg": "black", "scope_fg": "#33ff33", "scope_line": "#00cc00"
    },
    "80s Synthwave": {
        "bg": "#2b213a", "fg": "#05ffa1", "panel": "#241b31", # Lila/Cyan
        "accent": "#ff00c1", "warn": "#ff71ce", "grid": "#4d266e", # Pink/Neon
        "font": ("Courier New", 10), "font_bold": ("Courier New", 10, "bold"),
        "ttk_theme": "clam",
        "scope_bg": "#120a1f", "scope_fg": "#05ffa1", "scope_line": "#ff00c1"
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
    def __init__(self, parent, manager):
        self.window = tk.Toplevel(parent)
        self.manager = manager
        self.txt = manager.get_text
        
        self.window.title(self.txt("SETTINGS_TITLE"))
        self.window.geometry("400x300")
        
        # Style für das Settings Fenster selbst laden (Basis)
        style = manager.get_style()
        self.window.configure(bg=style["bg"])
        
        # UI Elemente
        frame = tk.Frame(self.window, bg=style["bg"], padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Sprache
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
        self.manager.save_config(self.var_theme.get(), self.var_lang.get())
        tk.messagebox.showinfo("Restart", self.manager.get_text("RESTART_MSG"))
        self.window.destroy()