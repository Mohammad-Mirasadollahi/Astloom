"""Login service that depends on auth helpers."""

from auth import verify_password


def login(username: str, password: str, stored_hash: str) -> bool:
    """Authenticate a user by verifying the password hash."""
    if not username.strip():
        return False
    return verify_password(password, stored_hash)


def require_login(username: str, password: str, stored_hash: str) -> str:
    """Return a session token when login succeeds."""
    if not login(username, password, stored_hash):
        raise PermissionError("invalid credentials")
    return f"session:{username}"
