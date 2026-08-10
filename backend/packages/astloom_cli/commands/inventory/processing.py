"""Active docs/embed model context for inventory."""

from __future__ import annotations

from typing import Any


def processing_context(svc: Any) -> dict[str, Any]:
    """Configured / active models used for docs + embeddings."""
    docs_models: list[str] = []
    embed_route_models: list[str] = []
    try:
        cfg = svc.llm_config() if hasattr(svc, "llm_config") else {}
    except Exception:  # noqa: BLE001 — inventory must not crash
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    docs_llm_enabled = bool(cfg.get("docs_enabled"))
    route_docs = cfg.get("route_docs") if isinstance(cfg.get("route_docs"), dict) else {}
    route_embed = cfg.get("route_embed") if isinstance(cfg.get("route_embed"), dict) else {}
    primary = str(route_docs.get("primary_model") or "").strip()
    if primary:
        docs_models.append(primary)
    for item in route_docs.get("fallback_models") or []:
        text = str(item or "").strip()
        if text and text not in docs_models:
            docs_models.append(text)
    embed_primary = str(route_embed.get("primary_model") or "").strip()
    if embed_primary:
        embed_route_models.append(embed_primary)
    for item in route_embed.get("fallback_models") or []:
        text = str(item or "").strip()
        if text and text not in embed_route_models:
            embed_route_models.append(text)

    embedder = getattr(svc, "embeddings", None)
    active_embed = str(getattr(embedder, "model", "") or "").strip()
    if not active_embed and embedder is not None:
        describe = getattr(embedder, "describe", None)
        if callable(describe):
            try:
                active_embed = str(describe() or "").strip()
            except Exception:  # noqa: BLE001
                active_embed = ""

    docs_label = docs_models[0] if docs_models and docs_llm_enabled else "heuristic"
    return {
        "docs_llm_enabled": docs_llm_enabled,
        "docs_models": docs_models,
        "docs_model_label": docs_label,
        "embed_route_models": embed_route_models,
        "active_embed_model": active_embed or (embed_route_models[0] if embed_route_models else "unknown"),
    }


def embed_models_by_symbol(svc: Any, scope: Any) -> dict[str, str]:
    index = getattr(svc, "embedding_index", None)
    if index is None:
        return {}
    lister = getattr(index, "list_symbol_models", None)
    if not callable(lister):
        return {}
    try:
        raw = lister(scope) or {}
    except Exception:  # noqa: BLE001
        return {}
    return {str(k): str(v) for k, v in dict(raw).items() if str(k).strip() and str(v).strip()}
