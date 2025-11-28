import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import pyaudio
import numpy as np
import time
import tkintermapview 
import re
import csv
from datetime import datetime

# Import Logic and Settings
from decoder import AFSK1200Demodulator, APRSPacket
from settings import SettingsManager
from icon.icon_manager import IconManager

class APRSApp:
    def __init__(self, root):
        self.root = root
        
        # 1. Load Managers
        self.settings = SettingsManager()
        self.demod = AFSK1200Demodulator()
        self.icon_mgr = IconManager()
        self.p = pyaudio.PyAudio()
        
        # 2. State
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.markers = {}         
        self.marker_data = {}     
        self.active_marker_call = None
        self.paths = {}           
        self.station_history = {} 
        self.log_data = []        
        
        self.status_var = tk.StringVar()
        
        # 3. Audio Devices
        self.audio_devices = self.get_audio_devices()
        
        # 4. Build UI
        self.setup_ui_structure()
        self.reload_ui()
        
        # Force geometry to prevent collapse
        self.root.geometry("1200x900")
        self.root.update() 

    def get_audio_devices(self):
        devs = []
        try:
            for i in range(self.p.get_device_count()):
                d = self.p.get_device_info_by_index(i)
                if d['maxInputChannels'] > 0: 
                    devs.append(f"{i}: {d['name']}")
        except: pass
        return devs

    def setup_ui_structure(self):
        # --- Toolbar ---
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        self.btn_save = ttk.Button(self.toolbar, command=self.save_log)
        self.btn_save.pack(side=tk.LEFT)
        
        self.btn_sett = ttk.Button(self.toolbar, command=self.toggle_settings_view)
        self.btn_sett.pack(side=tk.RIGHT)

        # --- CONTAINER ---
        self.container = ttk.Frame(self.root)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # === VIEW 1: DASHBOARD ===
        self.view_dashboard = ttk.Frame(self.container)
        self.view_dashboard.pack(fill=tk.BOTH, expand=True)
        
        # Scope
        self.scope_frame = ttk.LabelFrame(self.view_dashboard, padding=2)
        self.scope_frame.pack(fill=tk.X, padx=10, pady=5)
        self.scope_canvas = tk.Canvas(self.scope_frame, height=120, highlightthickness=0)
        self.scope_canvas.pack(fill=tk.BOTH, expand=True)

        # Split Pane
        self.paned = ttk.PanedWindow(self.view_dashboard, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # --- LINKES PANEL ---
        self.left_panel = ttk.Frame(self.paned, width=400)
        self.paned.add(self.left_panel, weight=1)
        
        # 1. Audio Control
        self.ctrl_group = ttk.LabelFrame(self.left_panel, padding=10)
        self.ctrl_group.pack(fill=tk.X, pady=(0, 5))
        
        self.device_combo = ttk.Combobox(self.ctrl_group)
        self.device_combo.pack(fill=tk.X, pady=5)
        
        # 2. START/STOP BUTTON (WICHTIG: tk.Button für Farben!)
        # Platziert direkt zwischen Audio und Log
        self.btn_start = tk.Button(self.left_panel, command=self.toggle_receiving, 
                                 bd=0, relief=tk.FLAT, cursor="hand2")
        self.btn_start.pack(fill=tk.X, pady=10, padx=2)
        
        # 3. Log
        self.log_group = ttk.LabelFrame(self.left_panel, padding=2)
        self.log_group.pack(fill=tk.BOTH, expand=True)
        
        cols = ("Time", "Call", "Sym", "Data")
        self.tree = ttk.Treeview(self.log_group, columns=cols, show='headings', selectmode='browse')
        self.tree.column("Time", width=70, anchor="center")
        self.tree.column("Call", width=90, anchor="w")
        self.tree.column("Sym", width=50, anchor="center")
        self.scrl = ttk.Scrollbar(self.log_group, command=self.tree.yview)
        self.tree.configure(yscroll=self.scrl.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrl.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind('<<TreeviewSelect>>', self.on_list_select)
        
        # Map (Right)
        self.map_container = ttk.LabelFrame(self.paned)
        self.paned.add(self.map_container, weight=3)
        self.map_widget = tkintermapview.TkinterMapView(self.map_container, corner_radius=0)
        self.map_widget.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.map_widget.set_position(51.16, 10.45)
        self.map_widget.set_zoom(6)
        
        # Status
        self.lbl_status = tk.Label(self.view_dashboard, textvariable=self.status_var, bd=2, relief=tk.SUNKEN, anchor=tk.W, padx=5)
        self.lbl_status.pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        # === VIEW 2: SETTINGS (Hidden Overlay) ===
        self.view_settings = ttk.Frame(self.container)
        
        self.sett_box = ttk.Frame(self.view_settings, padding=20)
        self.sett_box.place(relx=0.5, rely=0.5, anchor="center", width=500, height=450)
        
        ttk.Label(self.sett_box, text="SETTINGS", font=("Consolas", 16, "bold")).pack(pady=20)
        
        ttk.Label(self.sett_box, text="Language:").pack(anchor=tk.W)
        self.var_lang = tk.StringVar()
        self.cb_lang = ttk.Combobox(self.sett_box, textvariable=self.var_lang, state="readonly")
        self.cb_lang.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.sett_box, text="Theme:").pack(anchor=tk.W, pady=(10,0))
        self.var_theme = tk.StringVar()
        self.cb_theme = ttk.Combobox(self.sett_box, textvariable=self.var_theme, state="readonly")
        self.cb_theme.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.sett_box, text="Audio Input:").pack(anchor=tk.W, pady=(10,0))
        self.var_audio = tk.StringVar()
        self.cb_audio = ttk.Combobox(self.sett_box, textvariable=self.var_audio, values=self.audio_devices, state="readonly")
        self.cb_audio.pack(fill=tk.X, pady=5)
        
        self.btn_close_sett = ttk.Button(self.sett_box, command=self.save_settings)
        self.btn_close_sett.pack(pady=30, fill=tk.X)

    def reload_ui(self):
        """Refreshes Colors, Texts and States"""
        self.style_cfg = self.settings.get_style()
        self.txt = self.settings.get_text
        cfg = self.style_cfg
        
        self.root.configure(bg=cfg["bg"])
        self.root.title(self.txt("WINDOW_TITLE"))
        self.view_settings.configure(style="TFrame") 
        self.view_dashboard.configure(style="TFrame")
        
        s = ttk.Style()
        try: s.theme_use(cfg["ttk_theme"])
        except: pass
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
        
        self.btn_save.config(text=self.txt("BTN_SAVE_LOG"))
        self.btn_sett.config(text=self.txt("BTN_SETTINGS"))
        self.btn_close_sett.config(text=self.txt("BTN_CLOSE_SETT"))
        
        self.scope_frame.config(text=self.txt("SCOPE_TITLE"))
        self.scope_canvas.config(bg=cfg["scope_bg"])
        self.draw_grid()
        
        self.ctrl_group.config(text=self.txt("AUDIO_INPUT"))
        self.log_group.config(text=self.txt("LOG_TITLE"))
        self.map_container.config(text=self.txt("MAP_TITLE"))
        
        # --- UPDATE BUTTON FARBE & TEXT ---
        # Wir nutzen Config Farben für konsistenten Look
        # START = Grün (accent), STOP = Rot (warn)
        if self.is_running:
            self.btn_start.config(
                text=self.txt("STOP"), 
                bg=cfg["warn"], 
                fg="black" if "U96" in self.settings.config["theme"] else "white",
                font=cfg["font_bold"]
            )
            self.status_var.set(self.txt("STATUS_LISTENING"))
        else:
            self.btn_start.config(
                text=self.txt("START"), 
                bg=cfg["accent"], 
                fg="black" if "U96" in self.settings.config["theme"] else "white",
                font=cfg["font_bold"]
            )
            self.status_var.set(self.txt("STATUS_READY"))
            
        self.tree.heading("Time", text=self.txt("COL_TIME"))
        self.tree.heading("Call", text=self.txt("COL_CALL"))
        self.tree.heading("Sym", text=self.txt("COL_SYM"))
        self.tree.heading("Data", text=self.txt("COL_MSG"))
        self.tree.tag_configure('matrix', foreground=cfg["fg"], background=cfg["panel"])
        
        self.lbl_status.config(bg=cfg["scope_bg"], fg=cfg["scope_fg"], font=cfg["font_bold"])
        self.map_widget.set_tile_server(cfg["map_server"])
        
        # Populate Settings
        from settings import LANGUAGES, THEMES
        self.cb_lang['values'] = list(LANGUAGES.keys())
        self.cb_theme['values'] = list(THEMES.keys())
        
        self.var_lang.set(self.settings.config["language"])
        self.var_theme.set(self.settings.config["theme"])
        
        idx = self.settings.config.get("audio_device_index", 0)
        if idx < len(self.audio_devices):
            self.var_audio.set(self.audio_devices[idx])
        elif self.audio_devices:
            self.var_audio.set(self.audio_devices[0])

    def toggle_settings_view(self):
        if self.view_settings.winfo_ismapped():
            self.view_settings.place_forget()
        else:
            self.view_settings.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.view_settings.lift()

    def save_settings(self):
        sel_audio = self.var_audio.get()
        audio_idx = 0
        if sel_audio:
            try: audio_idx = int(sel_audio.split(':')[0])
            except: pass
            
        self.settings.save_config(self.var_theme.get(), self.var_lang.get(), audio_idx)
        self.reload_ui()
        self.view_settings.place_forget()
        
        if self.is_running:
            self.toggle_receiving() 
            self.root.after(500, self.toggle_receiving)

    def save_log(self):
        if not self.log_data:
            messagebox.showinfo("Info", "Log is empty.")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")],
            initialfile=f"aprs_log_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        )
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["UTC_Time", "Callsign", "Latitude", "Longitude", "Symbol", "Comment"])
                    for entry in self.log_data:
                        writer.writerow(entry)
                messagebox.showinfo("Success", f"Log saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log: {e}")

    def draw_grid(self):
        w = 1200 
        h = 150
        cfg = self.style_cfg
        self.scope_canvas.delete("grid") 
        self.scope_canvas.create_line(0, h/4, 2000, h/4, fill=cfg["grid"], dash=(2, 4), tags="grid")
        self.scope_canvas.create_line(0, h/2, 2000, h/2, fill=cfg["scope_line"], width=1, tags="grid")
        self.scope_canvas.create_line(0, 3*h/4, 2000, 3*h/4, fill=cfg["grid"], dash=(2, 4), tags="grid")

    def on_list_select(self, event):
        sel = self.tree.selection()
        if sel:
            call = self.tree.item(sel[0])['values'][1]
            if call in self.markers:
                m = self.markers[call]
                self.map_widget.set_position(m.position[0], m.position[1])

    def toggle_receiving(self):
        # Config laden für Farben
        cfg = self.style_cfg
        
        if not self.is_running:
            try:
                idx = self.settings.config.get("audio_device_index", 0)
                self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=22050,
                                        input=True, input_device_index=idx,
                                        frames_per_buffer=4096, stream_callback=self.audio_callback)
                self.is_running = True
                
                # --- UPDATE TO STOP (RED) ---
                self.btn_start.config(
                    text=self.txt("STOP"), 
                    bg=cfg["warn"], 
                    fg="black" if "U96" in self.settings.config["theme"] else "white"
                )
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
            
            # --- UPDATE TO START (GREEN) ---
            self.btn_start.config(
                text=self.txt("START"), 
                bg=cfg["accent"], 
                fg="black" if "U96" in self.settings.config["theme"] else "white"
            )
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

    def on_marker_click(self, marker):
        try:
            if self.active_marker_call and self.active_marker_call in self.markers:
                old_marker = self.markers[self.active_marker_call]
                old_marker.set_text(self.active_marker_call)

            clicked_call = None
            for call, m in self.markers.items():
                if m == marker:
                    clicked_call = call
                    break
            
            if clicked_call and clicked_call in self.marker_data:
                full_info = self.marker_data[clicked_call]
                marker.set_text(full_info)
                self.active_marker_call = clicked_call
        except: pass

    def handle_packet(self, raw_bytes):
        try:
            pkt = APRSPacket(raw_bytes)
            if not pkt.callsign_src: return
            if not self.is_valid_callsign(pkt.callsign_src): return
            
            info_full = pkt.comment or pkt.payload
            info_short = info_full[:40] + "..." if len(info_full) > 40 else info_full
            time_str = pkt.timestamp.strftime('%H:%M:%S')
            
            self.log_data.append([
                pkt.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                pkt.callsign_src,
                pkt.latitude,
                pkt.longitude,
                pkt.symbol_code,
                info_full
            ])
            
            self.tree.insert('', 0, values=(
                time_str, 
                pkt.callsign_src, 
                pkt.symbol_code,
                info_short
            ), tags=('matrix',))
            
            if pkt.latitude and pkt.longitude:
                call = pkt.callsign_src
                
                if call not in self.station_history: self.station_history[call] = []
                self.station_history[call].append((pkt.latitude, pkt.longitude))
                if len(self.station_history[call]) > 50: self.station_history[call].pop(0)
                
                full_details = f"{call}\n{info_full}\n{time_str} UTC"
                self.marker_data[call] = full_details

                icon_img = self.icon_mgr.get_icon(pkt.symbol_table, pkt.symbol_code, self.style_cfg["accent"])
                
                if call in self.markers:
                    self.markers[call].set_position(pkt.latitude, pkt.longitude)
                    if self.active_marker_call == call:
                         self.markers[call].set_text(full_details)
                    else:
                         self.markers[call].set_text(call)
                    if icon_img: self.markers[call].set_icon(icon_img)
                else:
                    m = self.map_widget.set_marker(
                        pkt.latitude, pkt.longitude, 
                        text=call, 
                        icon=icon_img, 
                        text_color=self.style_cfg["fg"],
                        command=self.on_marker_click
                    )
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