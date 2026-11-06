"""Детерминированный ГПСЧ на SHA-256 (counter mode)."""
import hashlib


class HashPRNG:
    """Детерминированный криптографический ГСЧ на SHA-256 в counter mode."""

    def __init__(self, key: bytes, domain: bytes):
        self.key = key
        self.domain = domain
        self.counter = 0
        self.buffer = b""

    def _refill(self):
        msg = self.domain + b"|" + self.counter.to_bytes(8, 'big')
        self.buffer += hashlib.sha256(self.key + b"|" + msg).digest()
        self.counter += 1

    def next_bytes(self, n: int) -> bytes:
        while len(self.buffer) < n:
            self._refill()
        out = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return out

    def next_bit(self) -> int:
        return self.next_bytes(1)[0] & 1

    def next_int(self, N: int) -> int:
        if N <= 1:
            return 0
        bits = (N - 1).bit_length()
        nbytes = (bits + 7) // 8
        mask = (1 << bits) - 1
        while True:
            v = int.from_bytes(self.next_bytes(nbytes), 'big') & mask
            if v < N:
                return v