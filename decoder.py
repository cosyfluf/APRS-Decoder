import numpy as np
import datetime
from scipy.signal import butter, lfilter

class AFSK1200Demodulator:
    def __init__(self, sample_rate=22050):
        self.fs = sample_rate
        self.baud = 1200.0
        
        # --- ROBUST FILTER DESIGN ---
        # Instead of narrow mark/space filters, we use a wide bandpass.
        # This handles frequency drift better (e.g., poor radio calibration).
        
        # 1. Bandpass: 900Hz - 2500Hz
        # Removes low hum and high frequency noise.
        self.b_bp, self.a_bp = butter(4, [900, 2500], btype='band', fs=self.fs)
        
        # 2. Lowpass: 1200Hz
        # Post-detection filter to smooth the discriminator output.
        self.b_lp, self.a_lp = butter(4, 1200, btype='low', fs=self.fs)
        
        # Filter States (to maintain continuity between audio chunks)
        self.zi_bp = np.zeros((max(len(self.a_bp), len(self.b_bp)) - 1, ))
        self.zi_lp = np.zeros((max(len(self.a_lp), len(self.b_lp)) - 1, ))

        # PLL (Clock Recovery) State
        self.pll_phase = 0.0
        self.pll_step = self.baud / self.fs
        self.last_phase = 0
        
        # HDLC (Packet Assembly) State
        self.packet_buffer = bytearray()
        self.ones_in_row = 0
        self.collecting = False
        self.bit_buffer = 0
        self.bit_count = 0
        
    def process_chunk(self, audio_chunk):
        """
        Process audio chunk, demodulate and return parsed packets.
        Returns: (List_of_Packet_Bytes, Demodulated_Signal_For_UI)
        """
        # Safety check for empty data
        if len(audio_chunk) == 0: 
            return [], np.zeros(100)

        # 1. Normalize (prevent clipping, convert to float -1.0 to 1.0)
        max_val = np.max(np.abs(audio_chunk))
        if max_val == 0: 
            return [], np.zeros(100)
            
        signal = audio_chunk / 32768.0
        
        # 2. BANDPASS FILTER
        signal_filtered, self.zi_bp = lfilter(self.b_bp, self.a_bp, signal, zi=self.zi_bp)
        
        # 3. HARD LIMITER (Crucial!)
        # Converts everything to a square wave (+1/-1).
        # Makes the decoder immune to volume fluctuations.
        signal_limited = np.sign(signal_filtered)
        
        # 4. DISCRIMINATOR (Delay-Line)
        # Classic FM Demodulation by multiplying signal with delayed version.
        delayed = np.roll(signal_limited, 1)
        delayed[0] = 0 
        mixed = signal_limited * delayed
        
        # 5. LOWPASS FILTER (Smoothing)
        demodulated, self.zi_lp = lfilter(self.b_lp, self.a_lp, mixed, zi=self.zi_lp)
        
        # 6. BIT SLICING
        # Use mean as threshold (DC Offset Removal)
        threshold = np.mean(demodulated)
        bits_digital = (demodulated > threshold).astype(int)
        
        # 7. CLOCK RECOVERY & HDLC
        packets = []
        for i in range(1, len(bits_digital)):
            self.pll_phase += self.pll_step
            
            # Sync PLL on edge detection
            if bits_digital[i] != bits_digital[i-1]:
                # Nudge PLL
                if self.pll_phase < 0.5: self.pll_phase += 0.05
                else: self.pll_phase -= 0.05
            
            # Sampling point
            if self.pll_phase >= 1.0:
                self.pll_phase -= 1.0
                sampled_bit = bits_digital[i]
                
                # NRZI Decoding: Change = 0, No Change = 1
                current_bit = 1 if sampled_bit == self.last_phase else 0
                self.last_phase = sampled_bit
                
                pkt_bytes = self._hdlc_process(current_bit)
                if pkt_bytes: packets.append(pkt_bytes)
        
        return packets, demodulated

    def _hdlc_process(self, bit):
        # Detect Flag (01111110)
        if bit == 0 and self.ones_in_row == 6: 
            result = None
            if len(self.packet_buffer) > 14: # Min length for APRS
                # Strip CRC (last 2 bytes)
                result = bytes(self.packet_buffer[:-2]) 
            self.packet_buffer = bytearray()
            self.bit_buffer = 0
            self.bit_count = 0
            self.ones_in_row = 0
            self.collecting = True
            return result
            
        # Remove Bit Stuffing (0 after five 1s)
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
            if self.bit_count == 8: # Byte full
                self.packet_buffer.append(self.bit_buffer)
                self.bit_buffer = 0
                self.bit_count = 0
                # Sanity check for max length
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
        # Use UTC Time
        self.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        if raw_bytes:
            self.parse_ax25(raw_bytes)

    def parse_ax25(self, data):
        try:
            if len(data) < 14: return
            
            self.callsign_dst = self._decode_call(data[0:7])
            self.callsign_src = self._decode_call(data[7:14])
            
            try:
                # Find Control Field (0x03) and Protocol ID (0xF0)
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
        import re
        # Regex for Coordinates and Symbols
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