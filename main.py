import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import pyaudio
import numpy as np
import time
import requests
from PIL import Image, ImageTk
import io
import tkintermapview 
from datetime import datetime

# Import der Logik
from decoder import AFSK1200Demodulator, APRSPacket

# --- THEMA KONFIGURATION (DAS BOOT STYLE) ---
COLOR_BG = "#121212"        # Rumpf Grau/Schwarz
COLOR_PANEL = "#1e1e1e"     # Panel Hintergrund
COLOR_TEXT = "#33ff33"      # Phosphor Grün
COLOR_WARN = "#ff3333"      # Alarm Rot
COLOR_ACCENT = "#00cc00"    # Dunkleres Grün
COLOR_GRID = "#004400"      # Oszilloskop Gitter
FONT_MAIN = ("Consolas", 10)
FONT_BOLD = ("Consolas", 10, "bold")
FONT_LCD = ("Consolas", 12, "bold")

class IconManager:
    def __init__(self):
        self.cache = {}
        self.base_url = "https://raw.githubusercontent.com/hessu/aprs-symbols/master/symbols/24x24"
        self.symbol_map = {
            '>': 'car', '[': 'jogger', '-': 'house', 'k': 'truck', 'v': 'van', 
            'b': 'bike', 'u': 'truck', 's': 'ship', 'j': 'jeep', '<': 'motorcycle', 
            'R': 'recreational', '#': 'digi', '*': 'star', 'S': 'shuttle', 
            'O': 'balloon', 'a': 'ambulance', 'f': 'fire', 'y': 'yacht', '/': 'red_dot'
        }

    def get_icon(self, table, code):
        key = code
        filename = self.symbol_map.get(key, 'unknown')
        if table == '/' and code == '>': filename = 'car'
        
        if key in self.cache: return self.cache[key]
        if filename == 'unknown': return None
            
        try:
            url = f"{self.base_url}/{filename}.png"
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                img_data = response.content
                image = Image.open(io.BytesIO(img_data))
                # Etwas größer skalieren für bessere Sichtbarkeit auf dunkler Karte
                image = image.resize((32, 32), Image.Resampling.LANCZOS)
                tk_image = ImageTk.PhotoImage(image)
                self.cache[key] = tk_image
                return tk_image
        except: pass
        return None

class APRSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("U96 SONAR DECODER - SYSTEM ACTIVE")
        self.root.geometry("1200x900")
        self.root.configure(bg=COLOR_BG)
        
        # Styles anwenden
        self.setup_styles()
        
        self.demod = AFSK1200Demodulator()
        self.icon_mgr = IconManager()
        self.p = pyaudio.PyAudio()
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.markers = {}
        
        self.my_lat = tk.DoubleVar(value=50.11)
        self.my_lon = tk.DoubleVar(value=8.68)
        self.status_var = tk.StringVar(value="SYSTEM BEREIT - WARTE AUF SIGNAL")
        
        self.setup_ui()
        self.update_devices()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam') # Clam erlaubt die meisten Customizations
        
        # Allgemeine Farben
        style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=FONT_MAIN, borderwidth=1)
        
        # Frames
        style.configure("TFrame", background=COLOR_BG)
        style.configure("TLabelframe", background=COLOR_BG, bordercolor=COLOR_ACCENT)
        style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_ACCENT, font=FONT_BOLD)
        
        # Buttons (Wie Hardware-Tasten)
        style.configure("TButton", background=COLOR_PANEL, foreground=COLOR_TEXT, borderwidth=2, bordercolor=COLOR_ACCENT)
        style.map("TButton", 
                  background=[('active', COLOR_ACCENT)], 
                  foreground=[('active', 'black')])
        
        # Combobox
        style.configure("TCombobox", fieldbackground=COLOR_PANEL, background=COLOR_PANEL, foreground=COLOR_TEXT, arrowcolor=COLOR_TEXT)
        
        # Treeview (Tabelle)
        style.configure("Treeview", 
                        background=COLOR_PANEL, 
                        fieldbackground=COLOR_PANEL, 
                        foreground=COLOR_TEXT, 
                        borderwidth=0,
                        font=FONT_MAIN)
        style.configure("Treeview.Heading", 
                        background="#002200", 
                        foreground=COLOR_TEXT, 
                        font=FONT_BOLD)
        style.map("Treeview", background=[('selected', COLOR_ACCENT)], foreground=[('selected', 'black')])
        
        # Scrollbar
        style.configure("Vertical.TScrollbar", background=COLOR_PANEL, troughcolor=COLOR_BG, arrowcolor=COLOR_TEXT)

    def setup_ui(self):
        # --- SONAR SCOPE (Oben) ---
        # Rahmen sieht aus wie ein Rack-Einschub
        scope_frame = ttk.LabelFrame(self.root, text="/// HYDROPHONE SIGNAL ANALYSIS ///", padding=2)
        scope_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.scope_canvas = tk.Canvas(scope_frame, bg="black", height=150, highlightthickness=0)
        self.scope_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Grid zeichnen (statischer Hintergrund)
        self.draw_grid()

        # --- HAUPT PANEL ---
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # --- LINKES STEUERDECK ---
        left_panel = ttk.Frame(paned, width=400)
        paned.add(left_panel, weight=1)
        
        # 1. Input Sektion
        ctrl_group = ttk.LabelFrame(left_panel, text="[ COMMUNICATION INPUT ]", padding=10)
        ctrl_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ctrl_group, text="AUDIO DEVICE:").pack(anchor=tk.W)
        self.device_combo = ttk.Combobox(ctrl_group)
        self.device_combo.pack(fill=tk.X, pady=5)
        
        self.btn_start = ttk.Button(ctrl_group, text="ACTIVATE RECEIVER", command=self.toggle_receiving)
        self.btn_start.pack(fill=tk.X, pady=5)
        
        # 2. Logbuch
        log_group = ttk.LabelFrame(left_panel, text="[ DECODED TELEMETRY ]", padding=2)
        log_group.pack(fill=tk.BOTH, expand=True)
        
        cols = ("Time", "Call", "Sym", "Data")
        self.tree = ttk.Treeview(log_group, columns=cols, show='headings', selectmode='browse')
        
        self.tree.heading("Time", text="UTC")
        self.tree.column("Time", width=70, anchor="center")
        self.tree.heading("Call", text="STATION")
        self.tree.column("Call", width=90, anchor="w")
        self.tree.heading("Sym", text="TYPE")
        self.tree.column("Sym", width=50, anchor="center")
        self.tree.heading("Data", text="PAYLOAD")
        
        # Scrollbar im Industrial Look
        scrl = ttk.Scrollbar(log_group, command=self.tree.yview)
        self.tree.configure(yscroll=scrl.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrl.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind('<<TreeviewSelect>>', self.on_list_select)
        
        # Status Anzeige (LCD Look)
        self.lbl_status = tk.Label(left_panel, textvariable=self.status_var, 
                                 bg="black", fg=COLOR_TEXT, font=FONT_LCD, 
                                 bd=2, relief=tk.SUNKEN, anchor=tk.W, padx=5)
        self.lbl_status.pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        # --- RECHTES KARTENDECK ---
        map_container = ttk.LabelFrame(paned, text="[ TACTICAL MAP DISPLAY ]")
        paned.add(map_container, weight=3)
        
        self.map_widget = tkintermapview.TkinterMapView(map_container, corner_radius=0)
        self.map_widget.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # U-Boot Modus: Dunkle Karte!
        # Wir nutzen CartoDB Dark Matter Tiles für den echten "War Room" Look
        self.map_widget.set_tile_server("https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png")
        self.map_widget.set_position(51.16, 10.45)
        self.map_widget.set_zoom(6)

    def draw_grid(self):
        """Zeichnet ein cooles Sonar-Gitter"""
        w = 1200 # Annahme, wird resize überschrieben aber ok für init
        h = 150
        # Horizontale Linien
        self.scope_canvas.create_line(0, h/4, 2000, h/4, fill=COLOR_GRID, dash=(2, 4))
        self.scope_canvas.create_line(0, h/2, 2000, h/2, fill=COLOR_ACCENT, width=1) # Center
        self.scope_canvas.create_line(0, 3*h/4, 2000, 3*h/4, fill=COLOR_GRID, dash=(2, 4))
        # Text Overlay
        self.scope_canvas.create_text(10, 10, text="AUDIO INPUT GAIN", fill=COLOR_TEXT, anchor="nw", font=("Consolas", 8))
        self.scope_canvas.create_text(10, 80, text="MARK/SPACE CORRELATOR DELTA", fill=COLOR_WARN, anchor="nw", font=("Consolas", 8))

    def update_devices(self):
        devs = []
        try:
            for i in range(self.p.get_device_count()):
                d = self.p.get_device_info_by_index(i)
                if d['maxInputChannels'] > 0: devs.append(f"{i}: {d['name']}")
        except: pass
        self.device_combo['values'] = devs
        if devs: self.device_combo.current(0)

    def on_list_select(self, event):
        sel = self.tree.selection()
        if sel:
            call = self.tree.item(sel[0])['values'][1]
            if call in self.markers:
                m = self.markers[call]
                self.map_widget.set_position(m.position[0], m.position[1])

    def toggle_receiving(self):
        if not self.is_running:
            try:
                idx = int(self.device_combo.get().split(':')[0])
                self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=22050,
                                        input=True, input_device_index=idx,
                                        frames_per_buffer=4096, stream_callback=self.audio_callback)
                self.is_running = True
                self.btn_start.config(text="TERMINATE RECEIVER")
                self.status_var.set(">>> LISTENING ON 144.800 MHZ <<<")
                t = threading.Thread(target=self.processing_loop)
                t.daemon = True
                t.start()
            except Exception as e:
                messagebox.showerror("SYSTEM FAILURE", str(e))
        else:
            self.is_running = False
            self.stream.stop_stream()
            self.stream.close()
            self.btn_start.config(text="ACTIVATE RECEIVER")
            self.status_var.set("SYSTEM STANDBY")

    def audio_callback(self, in_data, frame_count, time_info, status):
        if self.is_running: self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def processing_loop(self):
        while self.is_running:
            try:
                if not self.audio_queue.empty():
                    raw = self.audio_queue.get()
                    chunk = np.frombuffer(raw, dtype=np.int16)
                    packets_bytes, viz_data = self.demod.process_chunk(chunk)
                    
                    if np.max(np.abs(chunk)) > 800:
                        self.root.after(0, self.draw_scope, chunk, viz_data)
                    
                    for pkt_bytes in packets_bytes:
                        self.root.after(0, self.handle_packet, pkt_bytes)
                else:
                    time.sleep(0.01)
            except: pass

    def draw_scope(self, audio, demod):
        w = self.scope_canvas.winfo_width()
        h = self.scope_canvas.winfo_height()
        if w < 10: return
        
        # WICHTIG: Wir löschen nur die Kurven, nicht das Gitter!
        self.scope_canvas.delete("wave")
        
        step = max(1, len(audio) // w)
        mid1 = h / 4
        mid2 = (h / 4) * 3
        
        # Audio Waveform (Phosphor Grün)
        pts1 = []
        for i in range(0, len(audio), step):
            x = (i / len(audio)) * w
            y = mid1 - (audio[i] / 30000.0) * (h/4)
            pts1.extend([x, y])
        if len(pts1) > 4: 
            self.scope_canvas.create_line(pts1, fill=COLOR_TEXT, tags="wave", width=1)
        
        # Demodulator Output (Alarm Rot für Kontrast)
        pts2 = []
        scale = np.max(np.abs(demod)) or 1
        for i in range(0, len(demod), step):
            x = (i / len(demod)) * w
            y = mid2 - (demod[i] / scale) * (h/4)
            pts2.extend([x, y])
        if len(pts2) > 4: 
            self.scope_canvas.create_line(pts2, fill=COLOR_WARN, tags="wave", width=2)

    def handle_packet(self, raw_bytes):
        pkt = APRSPacket(raw_bytes)
        if not pkt.callsign_src: return
        
        self.status_var.set(f"CONTACT DETECTED: {pkt.callsign_src}")
        
        icon_img = self.icon_mgr.get_icon(pkt.symbol_table, pkt.symbol_code)
        
        info = pkt.comment or pkt.payload
        if len(info) > 40: info = info[:40] + "..."
        
        # Einfügen in Log (immer oben)
        self.tree.insert('', 0, values=(
            pkt.timestamp.strftime('%H:%M:%S'), 
            pkt.callsign_src, 
            pkt.symbol_code,
            info
        ))
        
        # Map Marker Logic
        if pkt.latitude and pkt.longitude:
            call = pkt.callsign_src
            if call in self.markers:
                self.markers[call].set_position(pkt.latitude, pkt.longitude)
                if icon_img: self.markers[call].set_icon(icon_img)
            else:
                if icon_img:
                    m = self.map_widget.set_marker(pkt.latitude, pkt.longitude, text=call, icon=icon_img)
                else:
                    m = self.map_widget.set_marker(pkt.latitude, pkt.longitude, text=call)
                self.markers[call] = m

if __name__ == "__main__":
    root = tk.Tk()
    app = APRSApp(root)
    root.mainloop()