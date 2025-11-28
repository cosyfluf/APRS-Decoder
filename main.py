import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import pyaudio
import numpy as np
import time
import math
import os
from datetime import datetime

# Importiere unsere Module
from decoder import AFSK1200Demodulator, APRSPacket
from map import MapServer

class LogManager:
    """Verwaltet CSV und ADIF Logs"""
    def __init__(self):
        date_str = datetime.now().strftime('%Y%m%d')
        self.csv_file = f"aprs_log_{date_str}.csv"
        self.adif_file = f"aprs_log_{date_str}.adi"
        
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w') as f:
                f.write("Date,Time,Callsign,Lat,Lon,Distance_km,Comment\n")
        
        if not os.path.exists(self.adif_file):
            with open(self.adif_file, 'w') as f:
                f.write("APRS Live Log ADIF Export\n<EOH>\n")

    def log(self, packet, my_lat, my_lon):
        if not packet.callsign_src: return 0.0
        
        # Distanz berechnen
        dist_km = 0.0
        if my_lat and my_lon and packet.latitude:
            R = 6371
            dlat = math.radians(packet.latitude - my_lat)
            dlon = math.radians(packet.longitude - my_lon)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(my_lat)) * \
                math.cos(math.radians(packet.latitude)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            dist_km = R * c

        # CSV schreiben
        with open(self.csv_file, 'a') as f:
            f.write(f"{packet.timestamp.date()},{packet.timestamp.strftime('%H:%M:%S')},"
                    f"{packet.callsign_src},{packet.latitude:.4f},{packet.longitude:.4f},"
                    f"{dist_km:.1f},\"{packet.comment}\"\n")
        
        # ADIF schreiben
        with open(self.adif_file, 'a') as f:
            call = packet.callsign_src
            date_s = packet.timestamp.strftime('%Y%m%d')
            time_s = packet.timestamp.strftime('%H%M')
            record = (f"<CALL:{len(call)}>{call} <QSO_DATE:{len(date_s)}>{date_s} "
                      f"<TIME_ON:{len(time_s)}>{time_s} <MODE:3>PKT <BAND:2>2m "
                      f"<COMMENT:{len(packet.comment)}>{packet.comment} <EOR>\n")
            f.write(record)
            
        return dist_km

class APRSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python APRS Decoder (Real DSP)")
        self.root.geometry("900x600")
        
        # Backend-Objekte
        self.demod = AFSK1200Demodulator()
        self.map_server = MapServer()
        self.logger = LogManager()
        
        # Server starten
        self.map_server.start()
        
        # Audio Variablen
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.p = pyaudio.PyAudio()
        
        # GUI Setup
        self.setup_ui()
        self.update_devices()

    def setup_ui(self):
        # 1. Kopfzeile (Steuerung)
        ctrl_frame = ttk.Frame(self.root, padding=5)
        ctrl_frame.pack(fill=tk.X)
        
        ttk.Label(ctrl_frame, text="Audio Input:").pack(side=tk.LEFT)
        self.device_combo = ttk.Combobox(ctrl_frame, width=40)
        self.device_combo.pack(side=tk.LEFT, padx=5)
        
        self.btn_start = ttk.Button(ctrl_frame, text="Start Empfang", command=self.toggle_receiving)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(ctrl_frame, text="Karte öffnen", command=self.map_server.open_browser).pack(side=tk.LEFT, padx=5)
        
        # 2. QTH Einstellungen (für Distanz)
        qth_frame = ttk.LabelFrame(self.root, text="Mein Standort (für QRB Berechnung)", padding=5)
        qth_frame.pack(fill=tk.X, padx=5)
        
        self.my_lat = tk.DoubleVar(value=50.11)
        self.my_lon = tk.DoubleVar(value=8.68)
        
        ttk.Label(qth_frame, text="Lat:").pack(side=tk.LEFT)
        ttk.Entry(qth_frame, textvariable=self.my_lat, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(qth_frame, text="Lon:").pack(side=tk.LEFT)
        ttk.Entry(qth_frame, textvariable=self.my_lon, width=10).pack(side=tk.LEFT, padx=5)
        
        # 3. Tabelle
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        cols = ("Zeit", "Rufzeichen", "QRB (km)", "Kommentar / Info")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        
        self.tree.heading("Zeit", text="Zeit")
        self.tree.column("Zeit", width=80)
        self.tree.heading("Rufzeichen", text="Rufzeichen")
        self.tree.column("Rufzeichen", width=100)
        self.tree.heading("QRB (km)", text="QRB (km)")
        self.tree.column("QRB (km)", width=80)
        self.tree.heading("Kommentar / Info", text="Kommentar / Info")
        self.tree.column("Kommentar / Info", width=400)
        
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scroll.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 4. Raw Log (unten)
        self.raw_text = tk.Text(self.root, height=5, bg='black', fg='#00ff00', font=('Consolas', 9))
        self.raw_text.pack(fill=tk.X, padx=5, pady=5)

    def update_devices(self):
        devices = []
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                devices.append(f"{i}: {dev['name']}")
        self.device_combo['values'] = devices
        if devices: self.device_combo.current(0)

    def toggle_receiving(self):
        if not self.is_running:
            try:
                dev_index = int(self.device_combo.get().split(':')[0])
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=22050,
                    input=True,
                    input_device_index=dev_index,
                    frames_per_buffer=2048,
                    stream_callback=self.audio_callback
                )
                self.is_running = True
                self.btn_start.config(text="Stop Empfang")
                
                # Processing Thread starten
                self.proc_thread = threading.Thread(target=self.processing_loop)
                self.proc_thread.daemon = True
                self.proc_thread.start()
                
            except Exception as e:
                messagebox.showerror("Fehler", str(e))
        else:
            self.is_running = False
            self.stream.stop_stream()
            self.stream.close()
            self.btn_start.config(text="Start Empfang")

    def audio_callback(self, in_data, frame_count, time_info, status):
        if self.is_running:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def processing_loop(self):
        while self.is_running:
            try:
                if not self.audio_queue.empty():
                    raw_data = self.audio_queue.get()
                    audio_chunk = np.frombuffer(raw_data, dtype=np.int16)
                    
                    # Demodulieren
                    packets = self.demod.process_chunk(audio_chunk)
                    
                    for pkt_bytes in packets:
                        # UI Update muss im Main Thread passieren
                        self.root.after(0, self.handle_packet, pkt_bytes)
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(e)

    def handle_packet(self, raw_bytes):
        # Raw Anzeige
        try:
            self.raw_text.insert(tk.END, f"{raw_bytes}\n")
            self.raw_text.see(tk.END)
        except: pass
        
        # Decodieren
        packet = APRSPacket(raw_bytes)
        
        if packet.callsign_src:
            # Logging & Distanz
            dist = self.logger.log(packet, self.my_lat.get(), self.my_lon.get())
            
            # Map Update
            self.map_server.update_station(packet)
            
            # Tabelle Update
            self.tree.insert('', 0, values=(
                packet.timestamp.strftime('%H:%M:%S'),
                packet.callsign_src,
                f"{dist:.1f}",
                packet.comment
            ))

if __name__ == "__main__":
    root = tk.Tk()
    app = APRSApp(root)
    root.mainloop()