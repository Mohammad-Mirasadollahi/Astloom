"""Cross-language symbol and import resolution for polyglot repositories."""

from __future__ import annotations

from dataclasses import dataclass, field

from .confidence_policy import clamp_confidence
from .enums import CallConfidence, SymbolKind
from .languages import detect_language_from_path
from .models import GraphSymbol
from .parsing import resolve_call_target as resolve_same_language_call


def normalize_symbol_key(name: str) -> str:
    """Normalize qualified / path-like names across language separators."""
    cleaned = (name or "").strip().replace("\\", "/")
    cleaned = cleaned.replace("::", ".")
    cleaned = cleaned.replace("/", ".")
    while ".." in cleaned:
        cleaned = cleaned.replace("..", ".")
    return cleaned.strip(".")


def file_stem(path: str) -> str:
    normalized = path.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in normalized:
        return normalized.rsplit(".", 1)[0]
    return normalized


@dataclass
class SymbolIndexes:
    by_qualified: dict[str, str] = field(default_factory=dict)
    short_names: dict[str, list[str]] = field(default_factory=dict)
    by_normalized: dict[str, list[str]] = field(default_factory=dict)
    by_file_stem: dict[str, list[str]] = field(default_factory=dict)
    symbol_language: dict[str, str] = field(default_factory=dict)
    symbols_by_id: dict[str, GraphSymbol] = field(default_factory=dict)


def build_symbol_indexes(symbols: list[GraphSymbol]) -> SymbolIndexes:
    indexes = SymbolIndexes()
    for symbol in symbols:
        indexes.symbols_by_id[symbol.id] = symbol
        language = detect_language_from_path(symbol.file_path) or "unknown"
        indexes.symbol_language[symbol.id] = language

        if symbol.kind == SymbolKind.FILE:
            stem = file_stem(symbol.file_path)
            if stem:
                indexes.by_file_stem.setdefault(stem, []).append(symbol.id)
                indexes.by_file_stem.setdefault(normalize_symbol_key(stem), []).append(symbol.id)
            continue

        if symbol.kind == SymbolKind.DOCUMENTATION:
            continue

        if symbol.kind == SymbolKind.UNRESOLVED:
            # Placeholder endpoints for Neo4j edges — not resolution targets.
            continue

        if symbol.kind == SymbolKind.EXTERNAL:
            continue

        if symbol.kind == SymbolKind.IMPORT:
            # Import nodes are edges of naming, not resolution targets.
            continue

        indexes.by_qualified[symbol.qualified_name] = symbol.id
        normalized = normalize_symbol_key(symbol.qualified_name)
        indexes.by_normalized.setdefault(normalized, []).append(symbol.id)
        indexes.by_normalized.setdefault(normalize_symbol_key(symbol.name), []).append(symbol.id)

        indexes.short_names.setdefault(symbol.name, []).append(symbol.id)
        tail = normalize_symbol_key(symbol.qualified_name).rsplit(".", 1)[-1]
        if tail and tail != symbol.name:
            indexes.short_names.setdefault(tail, []).append(symbol.id)
    return indexes


def resolve_import_target(
    import_text: str,
    indexes: SymbolIndexes,
    *,
    source_language: str,
    package_aliases: dict[str, str] | None = None,
) -> tuple[str | None, CallConfidence, dict[str, object]]:
    """Resolve an import path/name to a project symbol or file across languages."""
    from .package_manifests import rewrite_import

    raw = (import_text or "").strip().strip("\"'")
    if not raw:
        return None, CallConfidence.UNRESOLVED, {}

    candidates_raw = [raw]
    rewritten = rewrite_import(raw, package_aliases or {})
    if rewritten != raw:
        candidates_raw.append(rewritten)

    for attempt in candidates_raw:
        hit = _resolve_one_import(attempt, indexes, source_language=source_language)
        if hit[0] is not None or hit[1] == CallConfidence.AMBIGUOUS:
            meta = dict(hit[2])
            via = str(meta.get("resolved_via") or "")
            if rewritten != raw and attempt == rewritten:
                via = via or "package_manifest"
                meta["resolved_via"] = via
                meta["import_rewritten_from"] = raw
            conf = clamp_confidence(
                hit[1],
                source_language=source_language,
                target_language=str(meta.get("target_language") or ""),
                via=via,
            )
            return hit[0], conf, meta
    return None, CallConfidence.UNRESOLVED, {}


def _resolve_one_import(
    raw: str,
    indexes: SymbolIndexes,
    *,
    source_language: str,
) -> tuple[str | None, CallConfidence, dict[str, object]]:
    if raw in indexes.by_qualified:
        target_id = indexes.by_qualified[raw]
        return target_id, CallConfidence.EXACT, _cross_meta(source_language, indexes, target_id)

    normalized = normalize_symbol_key(raw)
    matches = list(dict.fromkeys(indexes.by_normalized.get(normalized, [])))
    if len(matches) == 1:
        return matches[0], CallConfidence.PROBABLE, _cross_meta(source_language, indexes, matches[0])
    if len(matches) > 1:
        return None, CallConfidence.AMBIGUOUS, {"candidates": matches, "cross_language": True}

    stem = raw.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    stem = stem.lstrip("./")
    stem_candidates = [stem]
    # Named ESM imports may appear as "./helpers.helper" — also try the module path stem.
    if "." in stem:
        stem_candidates.append(stem.rsplit(".", 1)[0])
    if "/" in raw or raw.startswith("."):
        module_path = raw.rsplit("/", 1)[-1]
        module_path = module_path.split(".", 1)[0].lstrip("./")
        if module_path:
            stem_candidates.append(module_path)

    file_matches: list[str] = []
    for candidate in stem_candidates:
        file_matches.extend(indexes.by_file_stem.get(candidate, []))
        file_matches.extend(indexes.by_file_stem.get(normalize_symbol_key(candidate), []))
    file_matches = list(dict.fromkeys(file_matches))
    if len(file_matches) == 1:
        return (
            file_matches[0],
            CallConfidence.PROBABLE,
            _cross_meta(source_language, indexes, file_matches[0]) | {"resolved_via": "file_stem"},
        )
    if len(file_matches) > 1:
        return None, CallConfidence.AMBIGUOUS, {"candidates": file_matches, "cross_language": True}

    short: list[str] = []
    for candidate in stem_candidates:
        short.extend(indexes.short_names.get(candidate, []))
    short = list(dict.fromkeys(short))
    if len(short) == 1:
        return short[0], CallConfidence.PROBABLE, _cross_meta(source_language, indexes, short[0])
    if len(short) > 1:
        return None, CallConfidence.AMBIGUOUS, {"candidates": short, "cross_language": True}

    return None, CallConfidence.UNRESOLVED, {}


def resolve_call_target_polyglot(
    call: str,
    *,
    indexes: SymbolIndexes,
    import_aliases: dict[str, str],
    module_prefix: str,
    source_language: str,
) -> tuple[list[str], CallConfidence, dict[str, object]]:
    """Resolve a call within language first, then across the project graph."""
    targets, confidence = resolve_same_language_call(
        call,
        by_qualified=indexes.by_qualified,
        short_names=indexes.short_names,
        import_aliases=import_aliases,
        module_prefix=module_prefix,
        source_language=source_language,
    )
    if confidence == CallConfidence.EXTERNAL:
        return [], confidence, {}
    if targets and confidence != CallConfidence.UNRESOLVED:
        meta: dict[str, object] = {}
        if len(targets) == 1:
            meta = _cross_meta(source_language, indexes, targets[0])
            confidence = clamp_confidence(
                confidence,
                source_language=source_language,
                target_language=str(meta.get("target_language") or ""),
            )
        return targets, confidence, meta

    normalized_call = normalize_symbol_key(call)
    candidates = list(dict.fromkeys(indexes.by_normalized.get(normalized_call, [])))
    if not candidates:
        short = normalized_call.rsplit(".", 1)[-1]
        candidates = list(dict.fromkeys(indexes.short_names.get(short, [])))
    if not candidates and call in import_aliases:
        expanded = normalize_symbol_key(import_aliases[call])
        candidates = list(dict.fromkeys(indexes.by_normalized.get(expanded, [])))
        if not candidates:
            candidates = list(
                dict.fromkeys(indexes.short_names.get(expanded.rsplit(".", 1)[-1], []))
            )

    if not candidates:
        return [], CallConfidence.UNRESOLVED, {}
    if len(candidates) == 1:
        meta = _cross_meta(source_language, indexes, candidates[0])
        confidence = clamp_confidence(
            CallConfidence.EXACT,
            source_language=source_language,
            target_language=str(meta.get("target_language") or ""),
        )
        return candidates, confidence, meta
    return candidates, CallConfidence.AMBIGUOUS, {"cross_language": True, "candidates": candidates}


def _cross_meta(
    source_language: str,
    indexes: SymbolIndexes,
    target_id: str,
) -> dict[str, object]:
    target_language = indexes.symbol_language.get(target_id, "unknown")
    cross = bool(source_language and target_language and source_language != target_language)
    return {
        "cross_language": cross,
        "source_language": source_language,
        "target_language": target_language,
    }
