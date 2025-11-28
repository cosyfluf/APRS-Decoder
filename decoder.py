import numpy as np
import datetime
from scipy.signal import butter, lfilter

class AFSK1200Demodulator:
    def __init__(self, sample_rate=22050):
        self.fs = sample_rate
        self.baud = 1200.0
        
        # --- NEUE STRATEGIE: MARK/SPACE FILTER (Besser bei Rauschen) ---
        # Anstatt Frequenzänderung zu messen, filtern wir gezielt
        # nach 1200 Hz und 2200 Hz und vergleichen die Lautstärke.
        
        # Filter für "Mark" (1200 Hz) - Sehr schmalbandig
        self.b_mark, self.a_mark = butter(2, [1100, 1300], btype='band', fs=self.fs)
        
        # Filter für "Space" (2200 Hz) - Sehr schmalbandig
        self.b_space, self.a_space = butter(2, [2100, 2300], btype='band', fs=self.fs)
        
        # Tiefpass für das Datensignal (Post-Detection)
        self.b_lp, self.a_lp = butter(2, 600, btype='low', fs=self.fs)
        
        # Filter Status-Speicher
        self.zi_mark = np.zeros((max(len(self.a_mark), len(self.b_mark)) - 1, ))
        self.zi_space = np.zeros((max(len(self.a_space), len(self.b_space)) - 1, ))
        self.zi_lp = np.zeros((max(len(self.a_lp), len(self.b_lp)) - 1, ))

        # PLL State
        self.pll_phase = 0.0
        self.pll_step = self.baud / self.fs
        self.last_phase = 0
        
        # HDLC State
        self.packet_buffer = bytearray()
        self.ones_in_row = 0
        self.collecting = False
        self.bit_buffer = 0
        self.bit_count = 0
        
    def process_chunk(self, audio_chunk):
        if len(audio_chunk) == 0: return [], np.zeros(100)

        # 1. Audio Normalisieren
        max_val = np.max(np.abs(audio_chunk))
        if max_val == 0: return [], np.zeros(100)
        signal = audio_chunk / 32768.0
        
        # 2. MARK / SPACE FILTERUNG
        # Wir schicken das Signal durch ZWEI Filter parallel
        mark_sig, self.zi_mark = lfilter(self.b_mark, self.a_mark, signal, zi=self.zi_mark)
        space_sig, self.zi_space = lfilter(self.b_space, self.a_space, signal, zi=self.zi_space)
        
        # 3. ENVELOPE DETECTION (Betrag bilden)
        # Wir wollen wissen: Wo ist mehr Energie?
        mark_env = np.abs(mark_sig)
        space_env = np.abs(space_sig)
        
        # 4. SUBTRAKTION
        # Mark - Space. 
        # Positiv = 1200Hz (Bit 1), Negativ = 2200Hz (Bit 0)
        raw_bits = mark_env - space_env
        
        # 5. TIEFPASS (Glättung)
        demodulated, self.zi_lp = lfilter(self.b_lp, self.a_lp, raw_bits, zi=self.zi_lp)
        
        # 6. BIT SLICING (Digitalisierung)
        # Hysterese: Signal muss deutlich positiv/negativ sein
        bits_digital = (demodulated > 0.0).astype(int)
        
        # 7. CLOCK RECOVERY & HDLC
        packets = []
        for i in range(1, len(bits_digital)):
            self.pll_phase += self.pll_step
            
            # Synchronisation an Flanken
            if bits_digital[i] != bits_digital[i-1]:
                if self.pll_phase < 0.5: self.pll_phase += 0.05
                else: self.pll_phase -= 0.05
            
            if self.pll_phase >= 1.0:
                self.pll_phase -= 1.0
                sampled_bit = bits_digital[i]
                
                # NRZI Decoding
                current_bit = 1 if sampled_bit == self.last_phase else 0
                self.last_phase = sampled_bit
                
                pkt_bytes = self._hdlc_process(current_bit)
                if pkt_bytes: packets.append(pkt_bytes)
        
        return packets, demodulated

    def _hdlc_process(self, bit):
        if bit == 0 and self.ones_in_row == 6: # Flag
            result = None
            if len(self.packet_buffer) > 14: 
                result = bytes(self.packet_buffer[:-2]) 
            self.packet_buffer = bytearray()
            self.bit_buffer = 0
            self.bit_count = 0
            self.ones_in_row = 0
            self.collecting = True
            return result
            
        if bit == 0 and self.ones_in_row == 5: # Stuffing
            self.ones_in_row = 0
            return None
            
        if bit == 1:
            self.ones_in_row += 1
            if self.ones_in_row > 6: # Error
                self.packet_buffer = bytearray()
                self.collecting = False
                self.ones_in_row = 0
                return None
        else:
            self.ones_in_row = 0
            
        if self.collecting:
            self.bit_buffer |= (bit << (self.bit_count))
            self.bit_count += 1
            if self.bit_count == 8:
                self.packet_buffer.append(self.bit_buffer)
                self.bit_buffer = 0
                self.bit_count = 0
                if len(self.packet_buffer) > 300: 
                    self.collecting = False
                    self.packet_buffer = bytearray()
        return None

class APRSPacket:
    def __init__(self, raw_bytes=None):
        self.callsign_src = ""
        self.callsign_dst = ""
        self.payload = ""
        self.latitude = 0.0
        self.longitude = 0.0
        self.symbol_table = "/" # Default Primary
        self.symbol_code = ">"  # Default Car
        self.comment = ""
        self.timestamp = datetime.datetime.now()
        
        if raw_bytes:
            self.parse_ax25(raw_bytes)

    def parse_ax25(self, data):
        try:
            if len(data) < 14: return
            self.callsign_dst = self._decode_call(data[0:7])
            self.callsign_src = self._decode_call(data[7:14])
            try:
                idx = data.index(b'\x03\xf0') 
                self.payload = data[idx+2:].decode('latin-1', errors='replace')
                self._parse_aprs_data(self.payload)
            except: pass
        except: pass

    def _decode_call(self, data):
        call = ""
        try:
            ssid = (data[-1] >> 1) & 0x0F
            for b in data[:-1]:
                char = (b >> 1)
                if char != 0x20: call += chr(char)
            if ssid > 0: call += f"-{ssid}"
        except: return "UNKNOWN"
        return call.strip()

    def _parse_aprs_data(self, info):
        import re
        # Extrahiert Position UND Symbole
        pattern = re.compile(r'[\!=\/@](\d{4}\.\d{2})([NS])(.)(\d{5}\.\d{2})([EW])(.)')
        match = pattern.search(info)
        if match:
            try:
                lat_str, lat_dir, sym_table, lon_str, lon_dir, sym_code = match.groups()
                
                self.latitude = float(lat_str[:2]) + float(lat_str[2:])/60
                if lat_dir == 'S': self.latitude *= -1
                
                self.longitude = float(lon_str[:3]) + float(lon_str[3:])/60
                if lon_dir == 'W': self.longitude *= -1
                
                self.symbol_table = sym_table
                self.symbol_code = sym_code
                
                parts = info.split(sym_code, 1)
                if len(parts) > 1: self.comment = parts[1].strip()
            except: pass