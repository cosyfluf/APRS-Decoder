import numpy as np
import datetime
import math

class AFSK1200Demodulator:
    def __init__(self, sample_rate=22050):
        self.fs = sample_rate
        self.baud = 1200
        self.samples_per_bit = self.fs / self.baud
        
        # State
        self.pll_phase = 0
        self.pll_step = self.baud / self.fs
        self.last_phase = 0
        
        self.bit_buffer = 0
        self.bit_count = 0
        self.packet_buffer = bytearray()
        self.ones_in_row = 0
        self.collecting = False
        
    def process_chunk(self, audio_chunk):
        """
        Numpy-basierte Demodulation (Diskriminator + PLL)
        """
        if np.max(np.abs(audio_chunk)) == 0:
            return []
            
        # Normalisieren
        signal = audio_chunk / 32768.0
        
        # 1. Delay-Line Diskriminator (FM Demodulation)
        delayed = np.roll(signal, 1)
        delayed[0] = 0
        prod = signal * delayed
        
        # Tiefpassfilter (Moving Average)
        window_size = int(self.samples_per_bit * 0.8)
        lp_filter = np.ones(window_size) / window_size
        demodulated = np.convolve(prod, lp_filter, mode='same')
        
        # Bit Slicing (Analog zu Digital)
        threshold = np.mean(demodulated)
        bits_raw = (demodulated > threshold).astype(int)
        
        # 2. Clock Recovery (PLL) & HDLC
        packets = []
        for i in range(1, len(bits_raw)):
            self.pll_phase += self.pll_step
            
            # Synchronisation bei Flankenwechsel
            if bits_raw[i] != bits_raw[i-1]:
                if self.pll_phase < 0.5: self.pll_phase += 0.1
                else: self.pll_phase -= 0.1
            
            if self.pll_phase >= 1.0:
                self.pll_phase -= 1.0
                # NRZI Decode
                sampled_bit = bits_raw[i]
                decoded_bit = 1 if sampled_bit == self.last_phase else 0
                self.last_phase = sampled_bit
                
                packet = self._hdlc_process(decoded_bit)
                if packet: packets.append(packet)
                    
        return packets

    def _hdlc_process(self, bit):
        # Flag Detection (01111110)
        if bit == 0 and self.ones_in_row == 6:
            result = None
            if len(self.packet_buffer) > 10:
                # Hier könnte man noch CRC prüfen
                result = bytes(self.packet_buffer[:-2]) 
            self.packet_buffer = bytearray()
            self.bit_buffer = 0
            self.bit_count = 0
            self.ones_in_row = 0
            self.collecting = True
            return result
            
        if bit == 0 and self.ones_in_row == 5: # Bit Stuffing
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
        return None

class APRSPacket:
    def __init__(self, raw_bytes=None):
        self.callsign_src = ""
        self.callsign_dst = ""
        self.payload = ""
        self.latitude = 0.0
        self.longitude = 0.0
        self.symbol = ""
        self.comment = ""
        self.timestamp = datetime.datetime.now()
        
        if raw_bytes:
            self.parse_ax25(raw_bytes)

    def parse_ax25(self, data):
        try:
            if len(data) < 16: return
            self.callsign_dst = self._decode_call(data[0:7])
            self.callsign_src = self._decode_call(data[7:14])
            
            try:
                # Suche nach Control Field 0x03 0xF0
                idx = data.index(b'\x03\xf0')
                self.payload = data[idx+2:].decode('latin-1', errors='ignore')
                self._parse_aprs_data(self.payload)
            except ValueError:
                pass
        except Exception as e:
            print(f"Parse Error: {e}")

    def _decode_call(self, data):
        call = ""
        ssid = (data[-1] >> 1) & 0x0F
        for b in data[:-1]:
            char = (b >> 1)
            if char != 0x20: call += chr(char)
        if ssid > 0: call += f"-{ssid}"
        return call.strip()

    def _parse_aprs_data(self, info):
        import re
        # Pattern für Koordinaten
        pattern = re.compile(r'[\!=\/@](\d{4}\.\d{2})([NS]).(\d{5}\.\d{2})([EW])(.)')
        match = pattern.search(info)
        
        if match:
            lat_str, lat_dir, lon_str, lon_dir, sym = match.groups()
            
            lat = float(lat_str[:2]) + float(lat_str[2:])/60
            if lat_dir == 'S': lat *= -1
            self.latitude = lat
            
            lon = float(lon_str[:3]) + float(lon_str[3:])/60
            if lon_dir == 'W': lon *= -1
            self.longitude = lon
            
            self.symbol = info[match.end()-1]
            parts = info.split(sym, 1)
            if len(parts) > 1: self.comment = parts[1].strip()