import numpy as np
import datetime
from scipy.signal import butter, lfilter

class AFSK1200Demodulator:
    def __init__(self, sample_rate=22050):
        self.fs = sample_rate
        self.baud = 1200.0
        
        # --- ROBUSTER FILTER ENTWORF ---
        # Statt extrem enger Filter nehmen wir einen breiten Bandpass.
        # Das toleriert Frequenzabweichungen (z.B. wenn das Funkgerät nicht exakt auf Frequenz ist).
        
        # 1. Bandpass: 900Hz - 2500Hz
        # Alles darunter (Brummen) und darüber (Rauschen) kommt weg.
        self.b_bp, self.a_bp = butter(4, [900, 2500], btype='band', fs=self.fs)
        
        # 2. Tiefpass: 1200Hz (Glättung nach der Demodulation)
        self.b_lp, self.a_lp = butter(4, 1200, btype='low', fs=self.fs)
        
        # Filter Status (für nahtloses Audio)
        self.zi_bp = np.zeros((max(len(self.a_bp), len(self.b_bp)) - 1, ))
        self.zi_lp = np.zeros((max(len(self.a_lp), len(self.b_lp)) - 1, ))

        # PLL State
        self.pll_phase = 0.0
        self.pll_step = self.baud / self.fs
        self.last_phase = 0
        
        # Packet Buffer
        self.packet_buffer = bytearray()
        self.ones_in_row = 0
        self.collecting = False
        self.bit_buffer = 0
        self.bit_count = 0
        
    def process_chunk(self, audio_chunk):
        """
        Nimmt Audio entgegen, filtert, demoduliert und gibt Pakete zurück.
        """
        # Sicherheitscheck: Leere Daten?
        if len(audio_chunk) == 0: 
            return [], np.zeros(100)

        # 1. Normalisieren (verhindert Übersteuerung)
        # Wir konvertieren zu Float (-1.0 bis 1.0)
        max_val = np.max(np.abs(audio_chunk))
        if max_val == 0: 
            return [], np.zeros(100)
            
        signal = audio_chunk / 32768.0
        
        # 2. BANDPASS FILTER (Lärmschutz)
        signal_filtered, self.zi_bp = lfilter(self.b_bp, self.a_bp, signal, zi=self.zi_bp)
        
        # 3. HARD LIMITER (Der wichtigste Teil!)
        # Egal wie leise oder laut: Wir machen daraus ein perfektes Rechtecksignal (+1/-1).
        # Das hilft extrem bei schwachen Signalen.
        signal_limited = np.sign(signal_filtered)
        
        # 4. DISKRIMINATOR (Verzögerungsmultiplikation)
        # Das ist der klassische FM-Demodulator. Er funktioniert, solange der
        # Phasenunterschied zwischen 1200Hz und 2200Hz erkennbar ist.
        delayed = np.roll(signal_limited, 1)
        delayed[0] = 0 
        mixed = signal_limited * delayed
        
        # 5. TIEFPASS FILTER (Glättung)
        demodulated, self.zi_lp = lfilter(self.b_lp, self.a_lp, mixed, zi=self.zi_lp)
        
        # 6. BIT SLICING (Entscheidung: 0 oder 1?)
        # Wir nehmen den Durchschnitt als Nullpunkt (DC Offset Removal)
        threshold = np.mean(demodulated)
        bits_digital = (demodulated > threshold).astype(int)
        
        # 7. CLOCK RECOVERY & HDLC (Daten extrahieren)
        packets = []
        for i in range(1, len(bits_digital)):
            self.pll_phase += self.pll_step
            
            # Wenn sich der Bit-Wert ändert, synchronisieren wir unsere Uhr (PLL)
            if bits_digital[i] != bits_digital[i-1]:
                # Sanftes Nachjustieren (Nudging)
                if self.pll_phase < 0.5: self.pll_phase += 0.05
                else: self.pll_phase -= 0.05
            
            # Ist es Zeit, das Bit zu lesen?
            if self.pll_phase >= 1.0:
                self.pll_phase -= 1.0
                sampled_bit = bits_digital[i]
                
                # NRZI Decoding: 
                # Wenn sich das Signal ändert -> 0
                # Wenn es gleich bleibt -> 1
                current_bit = 1 if sampled_bit == self.last_phase else 0
                self.last_phase = sampled_bit
                
                pkt_bytes = self._hdlc_process(current_bit)
                if pkt_bytes: packets.append(pkt_bytes)
        
        return packets, demodulated

    def _hdlc_process(self, bit):
        # Erkennt den Start eines Pakets (01111110)
        if bit == 0 and self.ones_in_row == 6: 
            result = None
            if len(self.packet_buffer) > 14: # Mindestlänge für ein gültiges Paket
                # Die letzten 2 Bytes sind CRC (Prüfsumme), die schneiden wir ab
                result = bytes(self.packet_buffer[:-2]) 
            self.packet_buffer = bytearray()
            self.bit_buffer = 0
            self.bit_count = 0
            self.ones_in_row = 0
            self.collecting = True
            return result
            
        # Bit Stuffing entfernen (eine 0 nach fünf 1en wird ignoriert)
        if bit == 0 and self.ones_in_row == 5:
            self.ones_in_row = 0
            return None
            
        if bit == 1:
            self.ones_in_row += 1
            if self.ones_in_row > 6: # Fehler: Mehr als sechs 1en gibt es bei APRS nicht
                self.packet_buffer = bytearray()
                self.collecting = False
                self.ones_in_row = 0
                return None
        else:
            self.ones_in_row = 0
            
        if self.collecting:
            self.bit_buffer |= (bit << (self.bit_count))
            self.bit_count += 1
            if self.bit_count == 8: # Ein ganzes Byte voll
                self.packet_buffer.append(self.bit_buffer)
                self.bit_buffer = 0
                self.bit_count = 0
                # Sicherheits-Reset bei zu langen Datenmüll-Paketen
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
        self.symbol_table = "/" 
        self.symbol_code = ">"  
        self.comment = ""
        self.timestamp = datetime.datetime.now()
        
        if raw_bytes:
            self.parse_ax25(raw_bytes)

    def parse_ax25(self, data):
        try:
            # AX.25 Header muss mindestens 14 Bytes sein (2 Adressen)
            if len(data) < 14: return
            
            self.callsign_dst = self._decode_call(data[0:7])
            self.callsign_src = self._decode_call(data[7:14])
            
            try:
                # Suche nach dem Start der APRS-Daten (0x03 0xF0)
                # Das ist das "Control Field" und "Protocol ID"
                idx = data.index(b'\x03\xf0') 
                self.payload = data[idx+2:].decode('latin-1', errors='replace')
                self._parse_aprs_data(self.payload)
            except ValueError:
                # Manchmal fehlen die Control Fields im Raw Mode (selten)
                pass
        except Exception:
            pass

    def _decode_call(self, data):
        # Rufzeichen decodieren (Bit-Shifted ASCII)
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
        # Extrahiert Koordinaten und Symbole
        # Unterstützt verschiedene APRS Formate (!, =, /, @)
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