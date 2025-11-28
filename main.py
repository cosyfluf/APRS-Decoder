import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import pyaudio
import numpy as np
import time
import requests
from PIL import Image, ImageTk, ImageDraw
import io
import tkintermapview 
import traceback
import re
from datetime import datetime

# Importiere Module
from decoder import AFSK1200Demodulator, APRSPacket
from settings import SettingsManager, SettingsWindow # Unser neues Script

class IconManager:
    def __init__(self):
        self.cache = {}
        self.base_url = "https://raw.githubusercontent.com/hessu/aprs-symbols/master/symbols/24x24"
        self.symbol_map = {
            '>': 'car', 'k': 'truck', 'u': 'truck', 'v': 'van', 'b': 'bike', '<': 'motorcycle',
            '[': 'jogger', '-': 'house', '#': 'digi', '*': 'star', 'S': 'shuttle', 
            'O': 'balloon', 'a': 'ambulance', 'f': 'fire', 'y': 'yacht', 's': 'ship',
            'j': 'jeep', 'R': 'recreational', '/': 'red_dot', '0': 'circle', '^': 'plane'
        }

    def create_fallback_icon(self, color):
        size = 32
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([2, 2, size-2, size-2], outline=color, width=2)
        draw.ellipse([10, 10, size-10, size-10], fill=color)
        return ImageTk.PhotoImage(image)

    def get_icon(self, table, code, fallback_color):
        key = f"{table}{code}"
        if key in self.cache: return self.cache[key]
        
        filename = self.symbol_map.get(code)
        tk_image = None
        if filename:
            try:
                url = f"{self.base_url}/{filename}.png"
                response = requests.get(url, timeout=0.5)
                if response.status_code == 200:
                    img_data = response.content
                    image = Image.open(io.BytesIO(img_data)).convert("RGBA")
                    image = image.resize((32, 32), Image.Resampling.LANCZOS)
                    tk_image = ImageTk.PhotoImage(image)
            except: pass

        if tk_image is None:
            tk_image = self.create_fallback_icon(fallback_color)
        
        self.cache[key] = tk_image
        return tk_image

class APRSApp:
    def __init__(self, root):
        self.root = root
        
        # 1. SETTINGS LADEN
        self.settings = SettingsManager()
        self.style_cfg = self.settings.get_style()
        self.txt = self.settings.get_text
        
        self.root.title(self.txt("WINDOW_TITLE"))
        self.root.geometry("1200x900")
        self.root.configure(bg=self.style_cfg["bg"])
        
        # 2. THEME ANWENDEN
        self.apply_theme()
        
        self.demod = AFSK1200Demodulator()
        self.icon_mgr = IconManager()
        self.p = pyaudio.PyAudio()
        self.is_running = False
        self.audio_queue = queue.Queue()
        
        self.markers = {}
        self.paths = {}
        self.station_history = {}
        
        self.my_lat = tk.DoubleVar(value=50.11)
        self.my_lon = tk.DoubleVar(value=8.68)
        self.status_var = tk.StringVar(value=self.txt("STATUS_READY"))
        
        self.setup_ui()
        self.update_devices()
        
    def apply_theme(self):
        """Konfiguriert ttk Styles basierend auf settings.py"""
        s = ttk.Style()
        try:
            s.theme_use(self.style_cfg["ttk_theme"])
        except:
            s.theme_use('clam') # Fallback

        cfg = self.style_cfg
        
        s.configure(".", background=cfg["bg"], foreground=cfg["fg"], font=cfg["font"], borderwidth=1)
        s.configure("TFrame", background=cfg["bg"])
        s.configure("TLabelframe", background=cfg["bg"], bordercolor=cfg["accent"])
        s.configure("TLabelframe.Label", background=cfg["bg"], foreground=cfg["accent"], font=cfg["font_bold"])
        
        s.configure("TButton", background=cfg["panel"], foreground=cfg["fg"], borderwidth=1)
        s.map("TButton", background=[('active', cfg["accent"])], foreground=[('active', 'white')])
        
        s.configure("TCombobox", fieldbackground=cfg["panel"], background=cfg["panel"], foreground=cfg["fg"])
        
        s.configure("Treeview", background=cfg["panel"], fieldbackground=cfg["panel"], foreground=cfg["fg"], borderwidth=0, font=cfg["font"])
        s.configure("Treeview.Heading", background=cfg["grid"], foreground=cfg["fg"], font=cfg["font_bold"])
        s.map("Treeview", background=[('selected', cfg["accent"])], foreground=[('selected', 'white')])
        
        s.configure("Vertical.TScrollbar", background=cfg["panel"], troughcolor=cfg["bg"])

    def setup_ui(self):
        cfg = self.style_cfg
        
        # --- Toolbar (Oben) ---
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # Settings Button
        btn_sett = ttk.Button(toolbar, text=self.txt("BTN_SETTINGS"), command=self.open_settings)
        btn_sett.pack(side=tk.RIGHT)

        # --- SCOPE ---
        scope_frame = ttk.LabelFrame(self.root, text=self.txt("SCOPE_TITLE"), padding=2)
        scope_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.scope_canvas = tk.Canvas(scope_frame, bg=cfg["scope_bg"], height=150, highlightthickness=0)
        self.scope_canvas.pack(fill=tk.BOTH, expand=True)
        self.draw_grid()

        # --- PANEL ---
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # --- LINKS ---
        left_panel = ttk.Frame(paned, width=400)
        paned.add(left_panel, weight=1)
        
        ctrl_group = ttk.LabelFrame(left_panel, text=self.txt("AUDIO_INPUT"), padding=10)
        ctrl_group.pack(fill=tk.X, pady=(0, 10))
        
        self.device_combo = ttk.Combobox(ctrl_group)
        self.device_combo.pack(fill=tk.X, pady=5)
        
        self.btn_start = ttk.Button(ctrl_group, text=self.txt("START"), command=self.toggle_receiving)
        self.btn_start.pack(fill=tk.X, pady=5)
        
        log_group = ttk.LabelFrame(left_panel, text=self.txt("LOG_TITLE"), padding=2)
        log_group.pack(fill=tk.BOTH, expand=True)
        
        cols = ("Time", "Call", "Sym", "Data")
        self.tree = ttk.Treeview(log_group, columns=cols, show='headings', selectmode='browse')
        
        self.tree.heading("Time", text=self.txt("COL_TIME"))
        self.tree.column("Time", width=70, anchor="center")
        self.tree.heading("Call", text=self.txt("COL_CALL"))
        self.tree.column("Call", width=90, anchor="w")
        self.tree.heading("Sym", text=self.txt("COL_SYM"))
        self.tree.column("Sym", width=50, anchor="center")
        self.tree.heading("Data", text=self.txt("COL_MSG"))
        
        self.tree.tag_configure('matrix', foreground=cfg["fg"], background=cfg["panel"])
        
        scrl = ttk.Scrollbar(log_group, command=self.tree.yview)
        self.tree.configure(yscroll=scrl.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrl.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind('<<TreeviewSelect>>', self.on_list_select)
        
        self.lbl_status = tk.Label(left_panel, textvariable=self.status_var, 
                                 bg=cfg["scope_bg"], fg=cfg["scope_fg"], font=cfg["font_bold"], 
                                 bd=2, relief=tk.SUNKEN, anchor=tk.W, padx=5)
        self.lbl_status.pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        # --- RECHTS ---
        map_container = ttk.LabelFrame(paned, text=self.txt("MAP_TITLE"))
        paned.add(map_container, weight=3)
        
        self.map_widget = tkintermapview.TkinterMapView(map_container, corner_radius=0)
        self.map_widget.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Karte basierend auf Theme
        if "Windows" in self.settings.config["theme"]:
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png") # Hell
        else:
            self.map_widget.set_tile_server("https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png") # Dunkel
            
        self.map_widget.set_position(51.16, 10.45)
        self.map_widget.set_zoom(6)

    def open_settings(self):
        SettingsWindow(self.root, self.settings)

    def draw_grid(self):
        w = 1200 
        h = 150
        cfg = self.style_cfg
        self.scope_canvas.create_line(0, h/4, 2000, h/4, fill=cfg["grid"], dash=(2, 4))
        self.scope_canvas.create_line(0, h/2, 2000, h/2, fill=cfg["scope_line"], width=1)
        self.scope_canvas.create_line(0, 3*h/4, 2000, 3*h/4, fill=cfg["grid"], dash=(2, 4))

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
                if not self.device_combo.get(): return
                idx = int(self.device_combo.get().split(':')[0])
                self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=22050,
                                        input=True, input_device_index=idx,
                                        frames_per_buffer=4096, stream_callback=self.audio_callback)
                self.is_running = True
                self.btn_start.config(text=self.txt("STOP"))
                self.status_var.set(self.txt("STATUS_LISTENING"))
                t = threading.Thread(target=self.processing_loop)
                t.daemon = True
                t.start()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        else:
            self.is_running = False
            if hasattr(self, 'stream'):
                self.stream.stop_stream()
                self.stream.close()
            self.btn_start.config(text=self.txt("START"))
            self.status_var.set(self.txt("STATUS_READY"))

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
        self.scope_canvas.delete("wave")
        
        cfg = self.style_cfg
        step = max(1, len(audio) // w)
        mid1 = h / 4
        mid2 = (h / 4) * 3
        
        pts1 = []
        for i in range(0, len(audio), step):
            x = (i / len(audio)) * w
            y = mid1 - (audio[i] / 30000.0) * (h/4)
            pts1.extend([x, y])
        if len(pts1) > 4: 
            self.scope_canvas.create_line(pts1, fill=cfg["scope_fg"], tags="wave", width=1)
        
        pts2 = []
        scale = np.max(np.abs(demod)) or 1
        for i in range(0, len(demod), step):
            x = (i / len(demod)) * w
            y = mid2 - (demod[i] / scale) * (h/4)
            pts2.extend([x, y])
        if len(pts2) > 4: 
            self.scope_canvas.create_line(pts2, fill=cfg["warn"], tags="wave", width=2)

    def is_valid_callsign(self, call):
        if not call: return False
        return bool(re.match(r'^[A-Z0-9]+(?:-[0-9]{1,2})?$', call))

    def handle_packet(self, raw_bytes):
        try:
            pkt = APRSPacket(raw_bytes)
            if not pkt.callsign_src: return
            if not self.is_valid_callsign(pkt.callsign_src): return
            
            info = pkt.comment or pkt.payload
            info = info[:40] + "..." if len(info) > 40 else info
            
            self.tree.insert('', 0, values=(
                pkt.timestamp.strftime('%H:%M:%S'), 
                pkt.callsign_src, 
                pkt.symbol_code,
                info
            ), tags=('matrix',))
            
            if pkt.latitude and pkt.longitude:
                call = pkt.callsign_src
                if call not in self.station_history: self.station_history[call] = []
                self.station_history[call].append((pkt.latitude, pkt.longitude))
                if len(self.station_history[call]) > 50: self.station_history[call].pop(0)
                
                icon_img = self.icon_mgr.get_icon(pkt.symbol_table, pkt.symbol_code, self.style_cfg["accent"])
                marker_text = f"{call}\n{info}"
                
                if call in self.markers:
                    self.markers[call].set_position(pkt.latitude, pkt.longitude)
                    self.markers[call].set_text(marker_text)
                    if icon_img: self.markers[call].set_icon(icon_img)
                else:
                    if icon_img:
                        m = self.map_widget.set_marker(pkt.latitude, pkt.longitude, text=marker_text, icon=icon_img, text_color=self.style_cfg["fg"])
                    else:
                        m = self.map_widget.set_marker(pkt.latitude, pkt.longitude, text=marker_text, text_color=self.style_cfg["fg"])
                    self.markers[call] = m
                
                if len(self.station_history[call]) > 1:
                    if call in self.paths:
                        self.paths[call].set_position_list(self.station_history[call])
                    else:
                        self.paths[call] = self.map_widget.set_path(self.station_history[call], color=self.style_cfg["accent"], width=2)
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = APRSApp(root)
    root.mainloop()