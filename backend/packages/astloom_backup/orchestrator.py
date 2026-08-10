"""Backup orchestrator: export / validate / restore / dry-run."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from astloom_backup.bundle import pack_directory, unpack_archive
from astloom_backup.job_state import write_job
from astloom_backup.manifest import (
    MANIFEST_NAME,
    build_manifest,
    gate_contract_version,
    load_manifest,
    validate_manifest_shape,
    verify_checksums,
    write_checksums,
)
from astloom_backup.neo4j_store import count_scope_nodes, wipe_neo4j
from astloom_backup.pg import (
    connect,
    count_scope_rows,
    gate_schema_fingerprint,
    schema_table_fingerprint,
    wipe_scope_pg,
)
from astloom_backup.ports import build_ports
from astloom_backup.remap import resolve_target_scope
from astloom_backup.scope import Remap, Scope
from astloom_backup.secrets import assert_no_secrets


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _contract_version() -> str:
    try:
        from astloom_cli.upgrade.versions import CONTRACT_VERSION

        return str(CONTRACT_VERSION)
    except Exception:
        return "1"


def _product_version() -> str:
    try:
        from astloom_cli import __version__

        return str(__version__)
    except Exception:
        return "0.0.0"


def _export_local_project(scope: Scope, repo_root: Path, dest: Path) -> int:
    from astloom_cli import state

    projects_root = state.default_state_root(repo_root)
    data = state.load_project(
        projects_root, scope.tenant_id, scope.workspace_id, scope.project_id
    )
    if data is None:
        return 0
    assert_no_secrets(data, context="local.project")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1


def _import_local_project(
    path: Path,
    *,
    source: Scope,
    target: Scope,
    repo_root: Path,
) -> int:
    from astloom_cli import state
    from astloom_backup.remap import remap_row

    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("local/project.json must be an object")
    data = remap_row(data, source=source, target=target)
    assert_no_secrets(data, context="local.project")
    data["tenant_id"] = target.tenant_id
    data["workspace_id"] = target.workspace_id
    data["project_id"] = target.project_id
    state.save_project(state.default_state_root(repo_root), data)
    return 1


def scope_is_nonempty(scope: Scope) -> bool:
    try:
        with connect() as conn:
            pg_n = count_scope_rows(conn, scope)
    except RuntimeError as exc:
        if "DATABASE_URL" in str(exc):
            return False
        raise
    neo_n = count_scope_nodes(scope)
    return (pg_n + neo_n) > 0


def wipe_scope(scope: Scope, *, repo_root: Path | None = None) -> dict[str, Any]:
    with connect() as conn:
        pg = wipe_scope_pg(conn, scope)
        conn.commit()
    neo = wipe_neo4j(scope)
    local_deleted = False
    if repo_root is not None:
        from astloom_cli import state

        local_deleted = state.delete_project(
            state.default_state_root(repo_root),
            scope.tenant_id,
            scope.workspace_id,
            scope.project_id,
        )
    return {"postgres": pg, "neo4j": neo, "local_project": local_deleted}


def _verify_imported_counts(
    *,
    manifest_stores: dict[str, Any],
    imported: dict[str, int],
) -> dict[str, Any]:
    mismatches: dict[str, dict[str, int]] = {}
    for store_id, meta in sorted(manifest_stores.items()):
        expected = int((meta or {}).get("row_count") or 0)
        got = int(imported.get(store_id) or 0)
        if expected and got < expected:
            mismatches[store_id] = {"expected": expected, "imported": got}
    if mismatches:
        raise RuntimeError(f"post-restore count verification failed: {mismatches}")
    return {"ok": True, "mismatches": {}}


def export_bundle(
    scope: Scope,
    output: Path,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    scope.validate()
    staging = Path(tempfile.mkdtemp(prefix="asbak-export-"))
    try:
        stores_root = staging / "stores"
        stores_root.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}
        with connect() as conn:
            fingerprint = schema_table_fingerprint(conn)
            for port in build_ports():
                n = port.export_scope(conn, scope, stores_root / port.store_id)
                counts[port.store_id] = n
                d = stores_root / port.store_id
                if n == 0 and d.is_dir() and not any(d.rglob("*")):
                    shutil.rmtree(d, ignore_errors=True)
        local_n = _export_local_project(scope, repo_root, staging / "local" / "project.json")
        counts["local"] = local_n
        for store_id in list(counts):
            if counts[store_id] == 0:
                d = stores_root / store_id
                if d.is_dir() and not any(d.rglob("*")):
                    shutil.rmtree(d, ignore_errors=True)
        manifest = build_manifest(
            scope=scope,
            contract_version=_contract_version(),
            product_version=_product_version(),
            store_counts=counts,
            created_at=_now(),
            schema_fingerprint=fingerprint,
        )
        (staging / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_checksums(staging)
        pack_directory(staging, output)
        result = {
            "ok": True,
            "action": "export",
            "output": str(output.resolve()),
            "scope": scope.as_dict(),
            "store_counts": counts,
            "schema_fingerprint": fingerprint,
            "created_at": manifest["created_at"],
        }
        write_job(repo_root, result)
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def validate_bundle(
    input_path: Path,
    *,
    check_contract: bool = True,
    check_schema: bool = True,
) -> dict[str, Any]:
    staging = unpack_archive(input_path)
    try:
        verify_checksums(staging)
        manifest = load_manifest(staging / MANIFEST_NAME)
        validate_manifest_shape(manifest)
        if check_contract:
            gate_contract_version(manifest, expected=_contract_version())
        fp = manifest.get("schema_fingerprint") or {}
        if check_schema and fp:
            try:
                with connect() as conn:
                    host_fp = schema_table_fingerprint(conn)
                gate_schema_fingerprint(fp, host_fp)
            except RuntimeError as exc:
                # Offline validate (no DATABASE_URL): checksum/contract still apply.
                if "DATABASE_URL" not in str(exc):
                    raise
        return {
            "ok": True,
            "action": "validate",
            "input": str(input_path.resolve()),
            "scope": manifest["scope"],
            "stores": manifest["stores"],
            "contract_version": manifest.get("contract_version"),
            "schema_version": manifest.get("schema_version"),
            "schema_fingerprint": manifest.get("schema_fingerprint") or {},
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def dry_run_bundle(
    input_path: Path,
    *,
    repo_root: Path,
    remap: Remap | None = None,
    replace: bool = False,
    check_contract: bool = True,
) -> dict[str, Any]:
    report = validate_bundle(input_path, check_contract=check_contract)
    source = Scope(**report["scope"])
    target = resolve_target_scope(source, remap)
    nonempty = scope_is_nonempty(target)
    would_fail = nonempty and not replace
    result = {
        **report,
        "action": "dry_run",
        "target_scope": target.as_dict(),
        "target_nonempty": nonempty,
        "would_fail_conflict": would_fail,
        "replace": bool(replace),
    }
    write_job(repo_root, result)
    return result


def restore_bundle(
    input_path: Path,
    *,
    repo_root: Path,
    remap: Remap | None = None,
    replace: bool = False,
    yes: bool = False,
    check_contract: bool = True,
) -> dict[str, Any]:
    if replace and not yes:
        raise ValueError("replace requires --yes")
    staging = unpack_archive(input_path)
    try:
        verify_checksums(staging)
        manifest = load_manifest(staging / MANIFEST_NAME)
        validate_manifest_shape(manifest)
        if check_contract:
            gate_contract_version(manifest, expected=_contract_version())
        source = Scope(**manifest["scope"])
        source.validate()
        target = resolve_target_scope(source, remap)
        target.validate()

        with connect() as conn:
            gate_schema_fingerprint(
                manifest.get("schema_fingerprint") or {},
                schema_table_fingerprint(conn),
            )

        if scope_is_nonempty(target):
            if not replace:
                raise ValueError(
                    "target scope is not empty; refuse restore "
                    "(pass --replace --yes to wipe and replace)"
                )
            wipe_scope(target, repo_root=repo_root)

        imported: dict[str, int] = {}
        stores_root = staging / "stores"
        ports = {p.store_id: p for p in build_ports()}
        with connect() as conn:
            for store_id in [p.store_id for p in build_ports()]:
                store_dir = stores_root / store_id
                if not store_dir.is_dir():
                    continue
                try:
                    n = ports[store_id].import_scope(
                        conn,
                        store_dir,
                        source=source,
                        target=target,
                        require_insert=True,
                    )
                    imported[store_id] = n
                    conn.commit()
                except Exception as exc:
                    conn.rollback()
                    raise RuntimeError(f"restore failed at store={store_id}: {exc}") from exc

        local_n = _import_local_project(
            staging / "local" / "project.json",
            source=source,
            target=target,
            repo_root=repo_root,
        )
        if local_n:
            imported["local"] = local_n

        verification = _verify_imported_counts(
            manifest_stores=manifest.get("stores") or {},
            imported=imported,
        )

        result = {
            "ok": True,
            "action": "restore",
            "input": str(input_path.resolve()),
            "source_scope": source.as_dict(),
            "target_scope": target.as_dict(),
            "replaced": bool(replace),
            "imported": imported,
            "verification": verification,
        }
        write_job(repo_root, result)
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)
