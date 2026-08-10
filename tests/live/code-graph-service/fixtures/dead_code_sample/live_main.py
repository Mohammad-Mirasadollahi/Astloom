"""Tiny live fixture for unused_candidates MCP HTTP probe."""


def main() -> int:
    return helper_used()


def helper_used() -> int:
    return 42


def old_helper_orphan() -> int:
    """Intentionally unused — should score as unused_symbol."""
    return 0
