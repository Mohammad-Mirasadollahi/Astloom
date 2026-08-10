"""Language support matrix and guards.

Python is the mandatory baseline language and must remain supported.
Additional languages use tree-sitter adapters and share the same graph schema.
"""

from __future__ import annotations

from typing import Any

from .errors import ValidationError

LANGUAGE_MATRIX: dict[str, dict[str, Any]] = {
    "python": {
        "status": "supported",
        "required": True,
        "parser": "stdlib_ast",
        "extensions": (".py",),
    },
    "typescript": {
        "status": "supported",
        "required": False,
        "parser": "tree_sitter",
        "extensions": (".ts", ".tsx", ".mts", ".cts"),
    },
    "javascript": {
        "status": "supported",
        "required": False,
        "parser": "tree_sitter",
        "extensions": (".js", ".jsx", ".mjs", ".cjs"),
    },
    "go": {
        "status": "supported",
        "required": False,
        "parser": "tree_sitter",
        "extensions": (".go",),
    },
    "rust": {
        "status": "supported",
        "required": False,
        "parser": "tree_sitter",
        "extensions": (".rs",),
    },
    "java": {
        "status": "supported",
        "required": False,
        "parser": "tree_sitter",
        "extensions": (".java",),
    },
}

REQUIRED_LANGUAGES: frozenset[str] = frozenset(
    name for name, meta in LANGUAGE_MATRIX.items() if meta.get("required") is True
)

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    extension: language
    for language, meta in LANGUAGE_MATRIX.items()
    for extension in meta.get("extensions", ())
}


def language_matrix() -> dict[str, dict[str, Any]]:
    return {name: dict(meta) for name, meta in LANGUAGE_MATRIX.items()}


def supported_languages() -> list[str]:
    return sorted(name for name, meta in LANGUAGE_MATRIX.items() if meta["status"] == "supported")


def required_languages() -> list[str]:
    return sorted(REQUIRED_LANGUAGES)


def detect_language_from_path(file_path: str) -> str | None:
    lowered = file_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for extension, language in sorted(EXTENSION_TO_LANGUAGE.items(), key=lambda item: -len(item[0])):
        if lowered.endswith(extension):
            return language
    return None


def assert_required_languages_supported() -> None:
    """Fail fast if a mandatory language (currently Python) is not supported."""
    missing = [
        name
        for name in REQUIRED_LANGUAGES
        if LANGUAGE_MATRIX.get(name, {}).get("status") != "supported"
    ]
    if missing:
        raise RuntimeError(
            "required code-graph languages must stay supported: " + ", ".join(sorted(missing))
        )


def assert_language_supported(language: str) -> str:
    assert_required_languages_supported()
    normalized = (language or "python").strip().lower() or "python"
    meta = LANGUAGE_MATRIX.get(normalized)
    if meta is None:
        raise ValidationError(f"unsupported language: {normalized}")
    if meta["status"] != "supported":
        raise ValidationError(
            f"language {normalized} is {meta['status']} (parser={meta['parser']}); "
            f"supported: {', '.join(supported_languages())}; "
            f"required: {', '.join(required_languages())}"
        )
    return normalized
