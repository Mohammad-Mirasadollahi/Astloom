"""Language parser registry — dispatches ingest to language-specific adapters."""

from __future__ import annotations

from collections.abc import Callable

from ..errors import ValidationError
from ..languages import assert_language_supported
from ..models import ParseResult
from ..parsing import parse_python_source
from .go_lang import parse_go_source
from .java_lang import parse_java_source
from .javascript import parse_javascript_source
from .rust_lang import parse_rust_source
from .typescript import parse_typescript_source

ParserFn = Callable[[str, str], ParseResult]

_PARSERS: dict[str, ParserFn] = {
    "python": parse_python_source,
    "javascript": parse_javascript_source,
    "typescript": parse_typescript_source,
    "go": parse_go_source,
    "rust": parse_rust_source,
    "java": parse_java_source,
}


def parse_source(language: str, file_path: str, source: str) -> ParseResult:
    """Parse source into the common symbol schema for a supported language."""
    normalized = assert_language_supported(language)
    parser = _PARSERS.get(normalized)
    if parser is None:
        raise ValidationError(f"no parser registered for language: {normalized}")
    try:
        return parser(file_path, source)
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ValidationError(f"failed to parse {normalized} source: {exc}") from exc


def registered_parsers() -> list[str]:
    return sorted(_PARSERS)
