import numpy as np
import datetime
import re
from scipy.signal import butter, lfilter

class AFSK1200Demodulator:
    def __init__(self, sample_rate=22050):
        self.fs = sample_rate
        self.baud = 1200.0
        
        # --- ROBUST FILTER DESIGN ---
        # 1. Bandpass: 900Hz - 2500Hz
        # Filters out low hum and high frequency noise
        self.b_bp, self.a_bp = butter(4, [900, 2500], btype='band', fs=self.fs)
        
        # 2. Lowpass: 1200Hz
        # Smoothing filter after demodulation
        self.b_lp, self.a_lp = butter(4, 1200, btype='low', fs=self.fs)
        
        # Filter states (for continuous stream processing)
        self.zi_bp = np.zeros((max(len(self.a_bp), len(self.b_bp)) - 1, ))
        self.zi_lp = np.zeros((max(len(self.a_lp), len(self.b_lp)) - 1, ))

        # PLL (Phase Locked Loop) State
        self.pll_phase = 0.0
        self.pll_step = self.baud / self.fs
        self.last_phase = 0
        
        # HDLC (High-Level Data Link Control) State
        self.packet_buffer = bytearray()
        self.ones_in_row = 0
        self.collecting = False
        self.bit_buffer = 0
        self.bit_count = 0
        
    def process_chunk(self, audio_chunk):
        """
        Demodulates audio chunk and extracts AX.25 packets.
        """
        if len(audio_chunk) == 0: return [], np.zeros(100)

        max_val = np.max(np.abs(audio_chunk))
        if max_val == 0: return [], np.zeros(100)
            
        # Normalize audio to -1.0 ... 1.0
        signal = audio_chunk / 32768.0
        
        # 1. Bandpass Filter
        signal_filtered, self.zi_bp = lfilter(self.b_bp, self.a_bp, signal, zi=self.zi_bp)
        
        # 2. Hard Limiter (Amplifies weak signals to square wave)
        signal_limited = np.sign(signal_filtered)
        
        # 3. Delay-Line Discriminator (FM Demodulation)
        delayed = np.roll(signal_limited, 1)
        delayed[0] = 0 
        mixed = signal_limited * delayed
        
        # 4. Lowpass Filter
        demodulated, self.zi_lp = lfilter(self.b_lp, self.a_lp, mixed, zi=self.zi_lp)
        
        # 5. Bit Slicing (Decision: 0 or 1)
        threshold = np.mean(demodulated)
        bits_digital = (demodulated > threshold).astype(int)
        
        # 6. Clock Recovery & HDLC Decoding
        packets = []
        for i in range(1, len(bits_digital)):
            self.pll_phase += self.pll_step
            
            # Sync PLL on edge
            if bits_digital[i] != bits_digital[i-1]:
                if self.pll_phase < 0.5: self.pll_phase += 0.05
                else: self.pll_phase -= 0.05
            
            # Sample bit
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
        # Flag Detection (01111110)
        if bit == 0 and self.ones_in_row == 6: 
            result = None
            if len(self.packet_buffer) > 14: 
                # Strip CRC (last 2 bytes)
                result = bytes(self.packet_buffer[:-2]) 
            self.packet_buffer = bytearray()
            self.bit_buffer = 0
            self.bit_count = 0
            self.ones_in_row = 0
            self.collecting = True
            return result
            
        # Bit Stuffing Removal
        if bit == 0 and self.ones_in_row == 5:
            self.ones_in_row = 0
            return None
            
        if bit == 1:
            self.ones_in_row += 1
            if self.ones_in_row > 6: # Error / Abort
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
                if len(self.packet_buffer) > 500: 
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
        # Store timestamp in UTC
        self.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        if raw_bytes:
            self.parse_ax25(raw_bytes)

    def parse_ax25(self, data):
        try:
            if len(data) < 14: return
            
            self.callsign_dst = self._decode_call(data[0:7])
            self.callsign_src = self._decode_call(data[7:14])
            
            try:
                # Find Control Field (0x03)
                idx = data.index(b'\x03\xf0') 
                self.payload = data[idx+2:].decode('latin-1', errors='replace')
                self._parse_aprs_data(self.payload)
            except ValueError:
                pass
        except Exception:
            pass

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
        # Universal Regex for Position extraction
        # (\d{4}\.\d{2}) -> Lat
        # ([NS])         -> Dir
        # (.)            -> Symbol Table ID
        # (\d{5}\.\d{2}) -> Lon
        # ([EW])         -> Dir
        # (.)            -> Symbol Code
        regex = r'(\d{4}\.\d{2})([NS])(.)(\d{5}\.\d{2})([EW])(.)'
        match = re.search(regex, info)
        
        if match:
            try:
                lat_str, lat_dir, sym_table, lon_str, lon_dir, sym_code = match.groups()
                
                # Convert Lat to Decimal
                lat_deg = float(lat_str[:2])
                lat_min = float(lat_str[2:])
                self.latitude = lat_deg + (lat_min / 60.0)
                if lat_dir == 'S': self.latitude *= -1
                
                # Convert Lon to Decimal
                lon_deg = float(lon_str[:3])
                lon_min = float(lon_str[3:])
                self.longitude = lon_deg + (lon_min / 60.0)
                if lon_dir == 'W': self.longitude *= -1
                
                self.symbol_table = sym_table
                self.symbol_code = sym_code
                
                # Extract comment (everything after the symbol)
                end_pos = match.end()
                if end_pos < len(info):
                    self.comment = info[end_pos:].strip()
                else:
                    self.comment = info.strip()
            except: pass