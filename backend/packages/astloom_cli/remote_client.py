"""Local Compose env loading shared by CLI commands that need Postgres/Neo4j DSNs."""

from __future__ import annotations

from pathlib import Path


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE env file (no shell expansion)."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def apply_compose_env_to_os(environ: dict[str, str], repo_root: Path) -> None:
    """Load ``backend/deployments/compose/.env.local`` into *environ* and set MCP store URLs."""
    env_file = repo_root / "backend" / "deployments" / "compose" / ".env.local"
    values = parse_env_file(env_file)
    if not values:
        raise SystemExit(f"error: missing or empty compose env {env_file} (run install.sh on Astloom host)")

    required = (
        "ASTLOOM_POSTGRES_USER",
        "ASTLOOM_POSTGRES_PASSWORD",
        "ASTLOOM_POSTGRES_PORT",
        "ASTLOOM_POSTGRES_DATABASE",
        "ASTLOOM_NEO4J_BOLT_PORT",
        "ASTLOOM_NEO4J_PASSWORD",
    )
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise SystemExit(f"error: compose env missing keys: {', '.join(missing)}")

    # Preserve operator/process overrides for durable paths (tests must not poison dogfood).
    preserve = {"ASTLOOM_DATA_ROOT"}
    for key, value in values.items():
        if key in preserve and str(environ.get(key) or "").strip():
            continue
        environ[key] = value
    pg_user = values["ASTLOOM_POSTGRES_USER"]
    pg_pass = values["ASTLOOM_POSTGRES_PASSWORD"]
    pg_port = values["ASTLOOM_POSTGRES_PORT"]
    pg_db = values["ASTLOOM_POSTGRES_DATABASE"]
    bolt_port = values["ASTLOOM_NEO4J_BOLT_PORT"]
    neo_user = values.get("ASTLOOM_NEO4J_USER", "neo4j")

    database_url = f"postgresql://{pg_user}:{pg_pass}@127.0.0.1:{pg_port}/{pg_db}"
    environ["ASTLOOM_DATABASE_URL"] = database_url
    # Same DSN powers pgvector embeddings + outbox mirror alongside Neo4j.
    environ["ASTLOOM_CODE_GRAPH_DATABASE_URL"] = database_url
    environ["ASTLOOM_MCP_STORE_MODE"] = "postgres"
    environ["ASTLOOM_NEO4J_URI"] = f"bolt://127.0.0.1:{bolt_port}"
    environ["ASTLOOM_NEO4J_USER"] = neo_user
    environ["ASTLOOM_CODE_GRAPH_STORE"] = "neo4j"
    environ["ASTLOOM_MCP_GRAPH_MODE"] = "neo4j"
