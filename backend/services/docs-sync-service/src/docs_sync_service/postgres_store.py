"""PostgreSQL Docs Sync Store with bounded connection pool.

Role: persist docs-sync symbols/documents/anchors/findings/drafts/outbox.
Source of truth: ``docs_sync.*`` tables; writers borrow from a sized ``psycopg``
pool (connections are not shareable across threads while checked out).
Allowed: concurrent Phase-2 writers; pool size auto from Postgres capacity
(or ``ASTLOOM_PG_POOL_MAX``); idempotent schema ensure on construct; close
all on ``close()``.
Forbidden: sharing one cursor/connection across threads; retaining one idle
client per worker thread (exhausts Postgres ``max_connections``); global
document IDs that can overwrite another project; duplicate document-symbol anchors.
"""

from __future__ import annotations

from typing import Any

from .enums import DocumentState, DraftState, DriftState, DriftType, Severity
from .errors import ConflictError, NotFoundError
from .models import (
    CodeSymbol,
    DocAnchor,
    Document,
    DocumentationDraft,
    DriftFinding,
    Scope,
)
from .pg_thread_local import ThreadLocalPsycopg, resolve_pg_pool_max
from .util import digest


def _timestamp(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


class PostgresStore:
    """PostgreSQL adapter for the Docs Sync Store port (thread-safe writers)."""

    def __init__(self, database_url: str, *, max_connections: int | None = None) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Docs Sync database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        self._json = Jsonb
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        pool_max = (
            max(1, int(max_connections))
            if max_connections is not None
            else resolve_pg_pool_max(database_url=database_url)
        )
        self._pool = ThreadLocalPsycopg(
            lambda: psycopg.connect(database_url, autocommit=True, row_factory=dict_row),
            max_size=pool_max,
        )
        # Fail fast on bad URL / schema; seed then return the bootstrap client.
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Apply service-owned idempotent migrations."""
        from pathlib import Path

        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        with self._connection.cursor() as cursor:
            for name in (
                "0001_docs_sync.sql",
                "0002_outbox_published.sql",
                "0003_document_scope_primary_key.sql",
                "0004_anchor_natural_key.sql",
            ):
                path = migrations_dir / name
                if path.is_file():
                    cursor.execute(path.read_text(encoding="utf-8"))

    @property
    def _connection(self) -> Any:
        return self._pool.get()

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    def _symbol(self, row: dict[str, Any], scope: Scope) -> CodeSymbol:
        return CodeSymbol(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["repo"], row["file_path"],
            row["symbol_path"], row["kind"], row["signature_hash"], row["body_hash"], row["doc_required"],
            row["tags"], _timestamp(row["created_at"]), _timestamp(row["updated_at"]), row["version"],
        )

    def _document(self, row: dict[str, Any], scope: Scope) -> Document:
        return Document(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["path"], row["title"], row["owner"],
            DocumentState(row["state"]), row["schema_version"], row["linked_symbols"], row["decision_refs"],
            row["frontmatter"], row["body"], _timestamp(row["created_at"]), _timestamp(row["updated_at"]), row["version"],
        )

    def _anchor(self, row: dict[str, Any], scope: Scope) -> DocAnchor:
        return DocAnchor(
            row["id"], scope, row["doc_id"], row["symbol_id"], row["recorded_hash"], row["status"],
            _timestamp(row["created_at"]), _timestamp(row["updated_at"]), row["version"],
        )

    def _finding(self, row: dict[str, Any], scope: Scope) -> DriftFinding:
        return DriftFinding(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["symbol_id"], row["doc_id"],
            DriftType(row["drift_type"]), row["old_hash"], row["new_hash"], Severity(row["severity"]),
            DriftState(row["status"]), row["issue_ref"], row["task_ref"], row["evidence_refs"],
            _timestamp(row["created_at"]), _timestamp(row["updated_at"]), row["version"],
        )

    def _draft(self, row: dict[str, Any], scope: Scope) -> DocumentationDraft:
        return DocumentationDraft(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["symbol_id"], row["finding_id"],
            row["title"], row["body"], DraftState(row["state"]), _timestamp(row["created_at"]),
            _timestamp(row["updated_at"]), row["version"],
        )

    def get_symbol(self, symbol_id: str, scope: Scope) -> CodeSymbol:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.symbols WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (symbol_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("symbol not found in project scope")
        return self._symbol(row, scope)

    def find_symbol(self, scope: Scope, repo: str, file_path: str, symbol_path: str) -> CodeSymbol | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.symbols WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   AND repo=%s AND file_path=%s AND symbol_path=%s""",
                (scope.tenant_id, scope.workspace_id, scope.project_id, repo, file_path, symbol_path),
            )
            row = cursor.fetchone()
        return self._symbol(row, scope) if row else None

    def put_symbol(self, symbol: CodeSymbol) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO docs_sync.symbols
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,repo,file_path,
                    symbol_path,kind,signature_hash,body_hash,doc_required,tags,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET body_hash=EXCLUDED.body_hash,signature_hash=EXCLUDED.signature_hash,
                   doc_required=EXCLUDED.doc_required,tags=EXCLUDED.tags,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (symbol.id, symbol.scope.tenant_id, symbol.scope.workspace_id, symbol.scope.project_id,
                 symbol.scope.project_group_id, symbol.actor_id, symbol.correlation_id, symbol.repo, symbol.file_path,
                 symbol.symbol_path, symbol.kind, symbol.signature_hash, symbol.body_hash, symbol.doc_required,
                 self._json(symbol.tags), symbol.version, symbol.created_at, symbol.updated_at),
            )

    def delete_symbol(self, symbol_id: str, scope: Scope) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """DELETE FROM docs_sync.anchors WHERE symbol_id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (symbol_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            cursor.execute(
                """DELETE FROM docs_sync.symbols WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (symbol_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )

    def list_symbols(self, scope: Scope) -> list[CodeSymbol]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.symbols WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._symbol(row, scope) for row in cursor.fetchall()]

    def get_document(self, document_id: str, scope: Scope) -> Document:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.documents WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (document_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("document not found in project scope")
        return self._document(row, scope)

    def put_document(self, document: Document) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO docs_sync.documents
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,path,title,owner,
                    state,schema_version,linked_symbols,decision_refs,frontmatter,body,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id,tenant_id,workspace_id,project_id)
                   DO UPDATE SET title=EXCLUDED.title,owner=EXCLUDED.owner,state=EXCLUDED.state,
                   linked_symbols=EXCLUDED.linked_symbols,decision_refs=EXCLUDED.decision_refs,
                   frontmatter=EXCLUDED.frontmatter,body=EXCLUDED.body,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (document.id, document.scope.tenant_id, document.scope.workspace_id, document.scope.project_id,
                 document.scope.project_group_id, document.actor_id, document.correlation_id, document.path,
                 document.title, document.owner, document.state.value, document.schema_version,
                 self._json(document.linked_symbols), self._json(document.decision_refs),
                 self._json(document.frontmatter), document.body, document.version, document.created_at, document.updated_at),
            )

    def list_documents(self, scope: Scope) -> list[Document]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.documents WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._document(row, scope) for row in cursor.fetchall()]

    def get_anchor(self, anchor_id: str, scope: Scope) -> DocAnchor:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.anchors WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (anchor_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("anchor not found in project scope")
        return self._anchor(row, scope)

    def put_anchor(self, anchor: DocAnchor) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO docs_sync.anchors
                   (id,tenant_id,workspace_id,project_id,project_group_id,doc_id,symbol_id,recorded_hash,status,
                    version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET recorded_hash=EXCLUDED.recorded_hash,status=EXCLUDED.status,
                   version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (anchor.id, anchor.scope.tenant_id, anchor.scope.workspace_id, anchor.scope.project_id,
                 anchor.scope.project_group_id, anchor.doc_id, anchor.symbol_id, anchor.recorded_hash,
                 anchor.status, anchor.version, anchor.created_at, anchor.updated_at),
            )

    def delete_anchor(self, anchor_id: str, scope: Scope) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """DELETE FROM docs_sync.anchors WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (anchor_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )

    def list_anchors(self, scope: Scope, symbol_id: str | None = None) -> list[DocAnchor]:
        with self._connection.cursor() as cursor:
            if symbol_id is None:
                cursor.execute(
                    """SELECT * FROM docs_sync.anchors WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                       ORDER BY created_at,id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id),
                )
            else:
                cursor.execute(
                    """SELECT * FROM docs_sync.anchors WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                       AND symbol_id=%s ORDER BY created_at,id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id, symbol_id),
                )
            return [self._anchor(row, scope) for row in cursor.fetchall()]

    def get_finding(self, finding_id: str, scope: Scope) -> DriftFinding:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.drift_findings WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (finding_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("drift finding not found in project scope")
        return self._finding(row, scope)

    def put_finding(self, finding: DriftFinding) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO docs_sync.drift_findings
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,symbol_id,doc_id,
                    drift_type,old_hash,new_hash,severity,status,issue_ref,task_ref,evidence_refs,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status,severity=EXCLUDED.severity,
                   issue_ref=EXCLUDED.issue_ref,task_ref=EXCLUDED.task_ref,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (finding.id, finding.scope.tenant_id, finding.scope.workspace_id, finding.scope.project_id,
                 finding.scope.project_group_id, finding.actor_id, finding.correlation_id, finding.symbol_id,
                 finding.doc_id, finding.drift_type.value, finding.old_hash, finding.new_hash, finding.severity.value,
                 finding.status.value, finding.issue_ref, finding.task_ref, self._json(finding.evidence_refs),
                 finding.version, finding.created_at, finding.updated_at),
            )

    def list_findings(self, scope: Scope) -> list[DriftFinding]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.drift_findings WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._finding(row, scope) for row in cursor.fetchall()]

    def get_draft(self, draft_id: str, scope: Scope) -> DocumentationDraft:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.drafts WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (draft_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("documentation draft not found in project scope")
        return self._draft(row, scope)

    def put_draft(self, draft: DocumentationDraft) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO docs_sync.drafts
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,symbol_id,finding_id,
                    title,body,state,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title,body=EXCLUDED.body,state=EXCLUDED.state,
                   version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (draft.id, draft.scope.tenant_id, draft.scope.workspace_id, draft.scope.project_id,
                 draft.scope.project_group_id, draft.actor_id, draft.correlation_id, draft.symbol_id, draft.finding_id,
                 draft.title, draft.body, draft.state.value, draft.version, draft.created_at, draft.updated_at),
            )

    def list_drafts(self, scope: Scope) -> list[DocumentationDraft]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM docs_sync.drafts WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._draft(row, scope) for row in cursor.fetchall()]

    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT fingerprint,record_id FROM docs_sync.idempotency
                   WHERE scope_key=%s AND command=%s AND idempotency_key=%s""",
                (self._scope_key(scope), command, key),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        if row["fingerprint"] != digest(payload):
            raise ConflictError("idempotency key was reused with a different payload")
        return row["record_id"]

    def remember(self, scope: Scope, command: str, key: str, payload: dict[str, Any], record_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO docs_sync.idempotency
                   (scope_key,command,idempotency_key,fingerprint,record_id) VALUES (%s,%s,%s,%s,%s)""",
                (self._scope_key(scope), command, key, digest(payload), record_id),
            )

    def event(self, payload: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO docs_sync.outbox (event_id,event_type,payload,occurred_at) VALUES (%s,%s,%s,%s)",
                (payload["event_id"], payload["event_type"], self._json(payload), payload["occurred_at"]),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM docs_sync.outbox ORDER BY occurred_at,event_id")
            return [row["payload"] for row in cursor.fetchall()]

    def reset_connections(self) -> None:
        """Drop worker connections after Postgres restart / AdminShutdown."""
        self.close()

    def close(self) -> None:
        self._pool.close_all()
