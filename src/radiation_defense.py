# src/radiation_defense.py
import hmac
import hashlib
import json
import random
from typing import Tuple, Dict, Any, List

SECRET_GROUND_KEY = b"ZERO_TRUST_SATELLITE_SECRET_2026"

class GroundStationCache:
    """Caches pre-verified, signed telecommands on Earth.
    
    If space radiation corrupts a packet in transit, Ground Station re-uplinks 
    directly from this cache without wasting LLM compute.
    """
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def store(self, packet_id: str, payload_json: str):
        self._cache[packet_id] = payload_json

    def retrieve(self, packet_id: str) -> str:
        return self._cache.get(packet_id, "")


class TMRMemoryController:
    """Simulates onboard Triple Modular Redundancy (TMR) hardware memory.
    
    Mirrors data across Bank A, Bank B, and Bank C. Uses 2-out-of-3 majority voting 
    to repair single-event upsets (SEUs) on the fly.
    """
    def __init__(self, data: Any):
        # Mirror payload across 3 physically separate memory banks
        self.bank_a = json.dumps(data)
        self.bank_b = json.dumps(data)
        self.bank_c = json.dumps(data)

    def inject_random_seu_bit_flip(self) -> str:
        """Simulates a heavy ion hitting a RANDOM memory bank (A, B, or C) at a RANDOM bit address."""
        corrupted_bank = random.choice(['A', 'B', 'C'])
        bank_attr = f"bank_{corrupted_bank.lower()}"
        
        data_str = getattr(self, bank_attr)
        bytes_data = bytearray(data_str.encode('utf-8'))
        
        if len(bytes_data) > 0:
            byte_idx = random.randint(0, len(bytes_data) - 1)
            bit_mask = 1 << random.randint(0, 7)
            bytes_data[byte_idx] ^= bit_mask
            setattr(self, bank_attr, bytes_data.decode('utf-8', errors='ignore'))
            
        return corrupted_bank

    def evaluate_tmr_voting_gate(self) -> Tuple[bool, str]:
        """Performs 2-out-of-3 hardware majority voting and auto-scrubs corrupted bank."""
        if self.bank_a == self.bank_b == self.bank_c:
            return True, "All 3 memory banks aligned. Zero SEU detected."

        # Majority Vote Logic
        if self.bank_a == self.bank_b:
            corrected_data = self.bank_a
            self.bank_c = corrected_data  # Scrub Bank C
            corrupted_bank = "Bank C"
        elif self.bank_a == self.bank_c:
            corrected_data = self.bank_a
            self.bank_b = corrected_data  # Scrub Bank B
            corrupted_bank = "Bank B"
        elif self.bank_b == self.bank_c:
            corrected_data = self.bank_b
            self.bank_a = corrected_data  # Scrub Bank A
            corrupted_bank = "Bank A"
        else:
            return False, "CRITICAL MEMORY FAILURE: Unrecoverable multi-bank SEU."

        return True, f"SEU detected in {corrupted_bank}. TMR Majority Vote (2/3) restored truth and auto-scrubbed memory."


def compute_hmac_signature(payload_str: str) -> str:
    """Generates an HMAC-SHA256 signature over the telecommand payload."""
    return hmac.new(SECRET_GROUND_KEY, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()


def inject_transit_seu_bit_flip(payload_str: str) -> str:
    """Simulates cosmic ray striking RF signal during space link transmission."""
    payload_bytes = bytearray(payload_str.encode('utf-8'))
    idx = random.randint(0, len(payload_bytes) - 1)
    payload_bytes[idx] ^= (1 << random.randint(0, 7))  # Flip random bit
    return payload_bytes.decode('utf-8', errors='ignore')


def verify_onboard_hmac(received_payload: str, expected_signature: str) -> bool:
    """Onboard FPGA Receiver: Recomputes HMAC to verify packet integrity."""
    computed = compute_hmac_signature(received_payload)
    return hmac.compare_digest(computed, expected_signature)