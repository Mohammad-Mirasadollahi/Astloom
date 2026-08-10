"""Deterministic bloom filter for documented symbol ids."""

from __future__ import annotations

from hashlib import sha256


class BloomFilter:
    """Deterministic membership filter for documented symbol ids."""

    def __init__(self, size: int = 2048, hashes: int = 3, version: str = "1"):
        self.size = size
        self.hashes = hashes
        self.version = version
        self._bits = bytearray(size)

    def add(self, value: str) -> None:
        for index in self._indexes(value):
            self._bits[index] = 1

    def might_contain(self, value: str) -> bool:
        return all(self._bits[index] for index in self._indexes(value))

    def _indexes(self, value: str) -> list[int]:
        digest_value = sha256(value.encode()).hexdigest()
        return [int(digest_value[i * 8 : (i + 1) * 8], 16) % self.size for i in range(self.hashes)]
