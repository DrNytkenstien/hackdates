import hashlib
import json
import time
from typing import Any, Dict, List

class BlackBoxBlock:
    def __init__(self, step_id: int, step_name: str, payload: Dict[str, Any], prev_hash: str = ""):
        self.timestamp = time.time()
        self.step_id = step_id
        self.step_name = step_name
        self.payload = payload
        self.prev_hash = prev_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        # Serializes block content predictably for exact byte-for-byte SHA-256 calculation
        block_content = {
            "prev_hash": self.prev_hash,
            "step_id": self.step_id,
            "step_name": self.step_name,
            "payload": self.payload
        }
        serialized = json.dumps(block_content, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "timestamp": self.timestamp
        }

class BlackBoxRecorder:
    """Manages the lifetime of a single event's cryptographic chain."""
    def __init__(self):
        self.chain: List[BlackBoxBlock] = []

    def record_step(self, step_name: str, payload: Dict[str, Any]) -> BlackBoxBlock:
        prev_hash = self.chain[-1].hash if self.chain else "0" * 64
        step_id = len(self.chain) + 1
        
        block = BlackBoxBlock(step_id=step_id, step_name=step_name, payload=payload, prev_hash=prev_hash)
        self.chain.append(block)
        return block

    def verify_chain(self) -> bool:
        """Verifies that no block in the sequence has been modified."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            
            # Check 1: Does the current block point to the correct previous hash?
            if current.prev_hash != previous.hash:
                return False
            # Check 2: Has the current block's payload been altered?
            if current.hash != current.calculate_hash():
                return False
        return True

    def export_chain(self) -> List[Dict[str, Any]]:
        return [block.to_dict() for block in self.chain]