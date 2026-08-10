"""Local documentation generation (deterministic, no cloud model calls)."""

from __future__ import annotations

from .models import GraphSymbol


class HeuristicDocGenerator:
    """Local deterministic documentation — no cloud model calls."""

    def generate(self, symbol: GraphSymbol, neighbors: list[str]) -> str:
        neighbor_text = ", ".join(neighbors[:8]) if neighbors else "none"
        return (
            f"{symbol.kind.value.title()} `{symbol.qualified_name}`\n"
            f"Signature: {symbol.signature or symbol.name}\n"
            f"File: {symbol.file_path}\n"
            f"Related symbols: {neighbor_text}\n"
            f"Summary: Owns behavior for `{symbol.name}` in project graph context."
        )
