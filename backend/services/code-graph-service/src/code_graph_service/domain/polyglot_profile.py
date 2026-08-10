"""Polyglot project profiling — detect related languages in one repository."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from .enums import SymbolKind
from .languages import detect_language_from_path
from .models import GraphEdge, GraphSymbol


@dataclass(frozen=True)
class LanguageLink:
    source_language: str
    target_language: str
    edge_count: int
    relation_types: tuple[str, ...]
    sample_edge_ids: tuple[str, ...]


@dataclass
class PolyglotProjectProfile:
    is_polyglot: bool
    languages: list[str]
    file_counts_by_language: dict[str, int]
    symbol_counts_by_language: dict[str, int]
    language_links: list[LanguageLink]
    related_language_groups: list[list[str]]
    relatedness: str
    cross_language_edge_count: int
    summary: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["language_links"] = [
            {
                "source_language": link.source_language,
                "target_language": link.target_language,
                "edge_count": link.edge_count,
                "relation_types": list(link.relation_types),
                "sample_edge_ids": list(link.sample_edge_ids),
            }
            for link in self.language_links
        ]
        return payload


def build_polyglot_profile(
    symbols: list[GraphSymbol],
    edges: list[GraphEdge],
) -> PolyglotProjectProfile:
    """Derive whether a project uses multiple related languages and how they connect."""
    file_counts: dict[str, int] = defaultdict(int)
    symbol_counts: dict[str, int] = defaultdict(int)
    symbol_language: dict[str, str] = {}

    for symbol in symbols:
        language = detect_language_from_path(symbol.file_path) or "unknown"
        symbol_language[symbol.id] = language
        if symbol.kind == SymbolKind.FILE:
            file_counts[language] += 1
        elif symbol.kind not in {SymbolKind.DOCUMENTATION, SymbolKind.IMPORT}:
            symbol_counts[language] += 1

    languages = sorted(
        {
            language
            for language in set(file_counts) | set(symbol_counts)
            if language != "unknown"
        }
    )
    is_polyglot = len(languages) >= 2

    link_buckets: dict[tuple[str, str], dict[str, object]] = {}
    adjacency: dict[str, set[str]] = defaultdict(set)
    cross_edge_count = 0

    for edge in edges:
        if edge.rel_type not in {"CALLS", "IMPORTS", "INHERITS_FROM"}:
            continue
        meta = edge.metadata or {}
        source_language = str(
            meta.get("source_language")
            or symbol_language.get(edge.source_id)
            or detect_language_from_path(str(meta.get("file_path") or ""))
            or "unknown"
        )
        target_language = str(
            meta.get("target_language")
            or symbol_language.get(edge.target_id)
            or "unknown"
        )
        if source_language in {"", "unknown"} or target_language in {"", "unknown"}:
            continue
        if source_language == target_language:
            continue
        if str(edge.target_id).startswith(("unresolved:", "ext:")):
            continue

        cross_edge_count += 1
        left, right = sorted((source_language, target_language))
        key = (left, right)
        bucket = link_buckets.setdefault(
            key,
            {"edge_count": 0, "relation_types": set(), "sample_edge_ids": []},
        )
        bucket["edge_count"] = int(bucket["edge_count"]) + 1
        relation_types = bucket["relation_types"]
        assert isinstance(relation_types, set)
        relation_types.add(edge.rel_type)
        samples = bucket["sample_edge_ids"]
        assert isinstance(samples, list)
        if len(samples) < 5:
            samples.append(edge.id)
        adjacency[source_language].add(target_language)
        adjacency[target_language].add(source_language)

    language_links = [
        LanguageLink(
            source_language=left,
            target_language=right,
            edge_count=int(bucket["edge_count"]),
            relation_types=tuple(sorted(bucket["relation_types"])),  # type: ignore[arg-type]
            sample_edge_ids=tuple(bucket["sample_edge_ids"]),  # type: ignore[arg-type]
        )
        for (left, right), bucket in sorted(link_buckets.items())
    ]

    groups = _connected_language_groups(languages, adjacency)
    relatedness = _relatedness_label(languages, groups, cross_edge_count)
    summary = _summary(is_polyglot, languages, groups, language_links, relatedness)

    return PolyglotProjectProfile(
        is_polyglot=is_polyglot,
        languages=languages,
        file_counts_by_language={language: file_counts.get(language, 0) for language in languages},
        symbol_counts_by_language={language: symbol_counts.get(language, 0) for language in languages},
        language_links=language_links,
        related_language_groups=groups,
        relatedness=relatedness,
        cross_language_edge_count=cross_edge_count,
        summary=summary,
    )


def _connected_language_groups(
    languages: list[str],
    adjacency: dict[str, set[str]],
) -> list[list[str]]:
    remaining = set(languages)
    groups: list[list[str]] = []
    while remaining:
        seed = sorted(remaining)[0]
        stack = [seed]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen or current not in remaining:
                continue
            seen.add(current)
            stack.extend(sorted(adjacency.get(current, set()) & remaining))
        groups.append(sorted(seen))
        remaining -= seen
    return sorted(groups, key=lambda group: (-len(group), group))


def _relatedness_label(
    languages: list[str],
    groups: list[list[str]],
    cross_edge_count: int,
) -> str:
    if len(languages) <= 1:
        return "monolingual"
    if cross_edge_count == 0:
        return "polyglot_isolated"
    multi = [group for group in groups if len(group) > 1]
    if len(multi) == 1 and len(multi[0]) == len(languages):
        return "polyglot_fully_related"
    if multi:
        return "polyglot_partially_related"
    return "polyglot_isolated"


def _summary(
    is_polyglot: bool,
    languages: list[str],
    groups: list[list[str]],
    links: list[LanguageLink],
    relatedness: str,
) -> str:
    if not is_polyglot:
        language = languages[0] if languages else "unknown"
        return f"Monolingual project ({language})."
    link_bits = [
        f"{link.source_language}↔{link.target_language}({link.edge_count})"
        for link in links[:6]
    ]
    related = [group for group in groups if len(group) > 1]
    if relatedness == "polyglot_fully_related":
        return (
            f"Polyglot related project with languages {', '.join(languages)}. "
            f"All languages are connected via cross-language edges"
            + (f": {', '.join(link_bits)}." if link_bits else ".")
        )
    if relatedness == "polyglot_partially_related":
        clusters = "; ".join("+".join(group) for group in related)
        return (
            f"Polyglot project with partially related languages {', '.join(languages)}. "
            f"Related clusters: {clusters}."
        )
    return (
        f"Polyglot project with isolated languages {', '.join(languages)} "
        "(no resolved cross-language CALLS/IMPORTS yet)."
    )
