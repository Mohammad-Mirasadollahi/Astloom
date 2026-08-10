"""Argon2id hashing for bootstrap secrets."""

from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    type=Type.ID,
)


def hash_secret(raw: str) -> str:
    return _HASHER.hash(raw)


def verify_secret(raw: str, encoded: str) -> bool:
    try:
        return _HASHER.verify(encoded, raw)
    except (VerificationError, InvalidHashError, ValueError):
        return False
