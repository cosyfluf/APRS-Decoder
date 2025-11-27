import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import pyaudio
import numpy as np
from decoder import APRSParser, AFSKDemodulator
from map import MapManager

class APRSDecoderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("APRS Live Decoder")
        self.root.geometry("1000x700")
        
        # Komponenten initialisieren
        self.map_manager = MapManager()
        self.parser = APRSParser()
        self.demodulator = AFSKDemodulator()
        
        # Audio Variablen
        self.audio = None
        self.stream = None
        self.is_recording = False
        self.audio_queue = queue.Queue()
        
        self.setup_ui()
        self.setup_audio_devices()
        
    def setup_ui(self):
        # Haupt-Layout
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Linke Seite: Einstellungen und Log
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Rechte Seite: Karte
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Einstellungen Frame
        settings_frame = ttk.LabelFrame(left_frame, text="Audio Einstellungen", padding=10)
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Audio Device Auswahl
        ttk.Label(settings_frame, text="Eingabegerät:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(settings_frame, textvariable=self.device_var, width=40)
        self.device_combo.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))
        
        # Sample Rate
        ttk.Label(settings_frame, text="Sample Rate:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.rate_var = tk.StringVar(value="22050")
        rate_combo = ttk.Combobox(settings_frame, textvariable=self.rate_var, 
                                 values=["8000", "11025", "22050", "44100"])
        rate_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 10))
        
        # Control Buttons
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.start_btn = ttk.Button(button_frame, text="Start", command=self.start_decoding)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="Stop", command=self.stop_decoding, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Status Anzeige
        status_frame = ttk.Frame(settings_frame)
        status_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW)
        
        self.status_var = tk.StringVar(value="Bereit")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        self.station_count_var = tk.StringVar(value="Stationen: 0")
        ttk.Label(status_frame, textvariable=self.station_count_var).pack(side=tk.RIGHT)
        
        # Log Frame
        log_frame = ttk.LabelFrame(left_frame, text="APRS Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # Log Text mit Scrollbar
        log_text_frame = ttk.Frame(log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_text_frame, height=15, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_text_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Karte Frame
        map_frame = ttk.LabelFrame(right_frame, text="APRS Karte", padding=10)
        map_frame.pack(fill=tk.BOTH, expand=True)
        
        self.map_widget = self.map_manager.get_map_widget(map_frame)
        self.map_widget.pack(fill=tk.BOTH, expand=True)
        
        # Map Control Buttons
        map_control_frame = ttk.Frame(map_frame)
        map_control_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(map_control_frame, text="Karte zurücksetzen", 
                  command=self.map_manager.clear_all_stations).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(map_control_frame, text="Karte im Browser öffnen", 
                  command=self.map_manager.open_in_browser).pack(side=tk.LEFT)
        
    def setup_audio_devices(self):
        """Audio Eingabegeräte ermitteln"""
        try:
            self.audio = pyaudio.PyAudio()
            devices = []
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    devices.append(f"{i}: {device_info['name']}")
            
            self.device_combo['values'] = devices
            if devices:
                self.device_combo.current(0)
        except Exception as e:
            self.log(f"Fehler bei Audio-Initialisierung: {e}")
            
    def start_decoding(self):
        """Startet die APRS Decodierung"""
        if not self.device_var.get():
            messagebox.showerror("Fehler", "Bitte ein Audio-Eingabegerät auswählen!")
            return
            
        try:
            device_index = int(self.device_var.get().split(':')[0])
            sample_rate = int(self.rate_var.get())
            
            self.is_recording = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_var.set("Empfange...")
            
            # Audio Stream starten
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024,
                stream_callback=self.audio_callback
            )
            
            self.stream.start_stream()
            
            # Processing Thread starten
            self.processing_thread = threading.Thread(target=self.process_audio_data)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            
            self.log("APRS Decodierung gestartet")
            
        except Exception as e:
            self.log(f"Fehler beim Start: {e}")
            self.stop_decoding()
            
    def stop_decoding(self):
        """Stoppt die APRS Decodierung"""
        self.is_recording = False
        self.status_var.set("Gestoppt")
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("APRS Decodierung gestoppt")
        
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Audio Callback für PyAudio"""
        if self.is_recording:
            self.audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)
    
    def process_audio_data(self):
        """Verarbeitet Audio-Daten im separaten Thread"""
        while self.is_recording:
            try:
                if not self.audio_queue.empty():
                    audio_data = self.audio_queue.get()
                    
                    # Audio-Daten zu numpy array konvertieren
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    
                    # AFSK Demodulation (vereinfacht)
                    decoded_data = self.demodulator.process_audio(audio_array)
                    
                    if decoded_data:
                        # APRS Paket parsen
                        packet = self.parser.parse_packet(decoded_data)
                        
                        if packet and packet.callsign:
                            # UI updaten im Haupt-Thread
                            self.root.after(0, self.update_ui, packet)
                            
            except Exception as e:
                self.root.after(0, self.log, f"Verarbeitungsfehler: {e}")
                
    def update_ui(self, packet):
        """Aktualisiert die UI mit neuen Paket-Daten"""
        try:
            # Log Eintrag
            log_entry = f"{packet.callsign}"
            if packet.latitude and packet.longitude:
                log_entry += f" @ {packet.latitude:.4f}, {packet.longitude:.4f}"
            if packet.comment:
                log_entry += f" - {packet.comment}"
                
            self.log(log_entry)
            
            # Auf Karte anzeigen
            if packet.latitude and packet.longitude:
                self.map_manager.add_station(
                    packet.callsign,
                    packet.latitude,
                    packet.longitude,
                    packet.symbol,
                    packet.comment or ""
                )
                
                # Stationszähler aktualisieren
                count = self.map_manager.get_station_count()
                self.station_count_var.set(f"Stationen: {count}")
                
        except Exception as e:
            self.log(f"UI Update Fehler: {e}")
            
    def log(self, message):
        """Fügt einen Eintrag zum Log hinzu"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.update()
        
    def on_closing(self):
        """Wird aufgerufen wenn das Fenster geschlossen wird"""
        self.stop_decoding()
        if self.audio:
            self.audio.terminate()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = APRSDecoderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
    root.mainloop()