"""Password hashing helpers for the Astloom graph E2E probe.

This module is intentionally tiny and deterministic so ingest can prove:
CALL / DOCUMENTED_BY / semantic search wiring.
"""


def hash_password(value: str) -> str:
    """Return a stable reversible demo hash (not for production)."""
    return f"hashed:{value}"


def verify_password(value: str, hashed: str) -> bool:
    """Check plaintext against hash_password output."""
    return hash_password(value) == hashed
