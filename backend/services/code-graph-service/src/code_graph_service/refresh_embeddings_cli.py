"""CLI entry for scoped code-graph embedding refresh (GAP-T03).

Role: operator CLI for one-scope SoR re-embed (pending|running|failed|complete).
SoT: CodeGraphService.refresh_embeddings + refresh-policy.json; TurboVec never SoR.
Allowed: --force / --dry-run. Forbidden: cross-tenant args; treating ANN as durable.
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh code-graph embedding SoR for one scope")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from code_graph_service.bootstrap import build_container
    from code_graph_service.domain.models import Scope

    container = build_container()
    try:
        scope = Scope(args.tenant, args.workspace, args.project)
        result = container.service.refresh_embeddings(
            scope,
            force=bool(args.force),
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result.public(), indent=2, sort_keys=True))
        return 0 if result.state == "complete" else 1
    finally:
        closer = getattr(container, "close", None)
        if callable(closer):
            closer()


if __name__ == "__main__":
    sys.exit(main())
