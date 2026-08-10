"""`astloom quality-audit` CLI entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from astloom_cli import ui
from astloom_cli.commands.quality_audit.collect import build_quality_audit_report
from astloom_cli.commands.quality_audit.render import format_detail_text, print_human
from astloom_cli.commands.quality_audit.words import parse_quality_audit_words


def cmd_quality_audit(args: argparse.Namespace) -> int:
    detail, save_path = parse_quality_audit_words(getattr(args, "words", None))
    # Best-effort: drop live-test fixture rows from docs-sync before scoring coverage.
    try:
        from astloom_cli.docs_registry_hygiene import purge_docs_registry_fixture_noise
        from astloom_cli.followup_task_lifecycle import open_platform_backends
        from astloom_cli.util import require_scope

        tenant, workspace, project_id = require_scope(args, with_defaults=True)

        class _Scope:
            tenant_id = tenant
            workspace_id = workspace
            project_id = project_id

        backends, _core, scope_dict = open_platform_backends(_Scope())
        try:
            hygiene = purge_docs_registry_fixture_noise(
                backends.docs,
                backends.docs_scope(scope_dict),
            )
            n = int(hygiene.get("deleted_count") or 0)
            if n:
                ui.kv("Docs registry hygiene", f"purged {n} fixture symbol(s)")
        finally:
            backends.close()
    except Exception:  # noqa: BLE001 — CLI audit still runs offline
        pass
    report = build_quality_audit_report(args)
    out_path = Path(save_path).expanduser() if save_path else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(format_detail_text(report, top_only=False), encoding="utf-8")
        json_path = out_path.with_suffix(".json")
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print_human(report, detail=detail)
    if out_path is not None:
        ui.kv("Saved", str(out_path.resolve()))
        ui.kv("JSON", str(out_path.with_suffix(".json").resolve()))
        ui.blank()

    # Non-zero when findings exist so CI/scripts can gate on quality debt.
    return 1 if int((report.get("summary") or {}).get("findings_total") or 0) > 0 else 0
