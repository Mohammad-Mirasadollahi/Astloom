"""At-rest registry for minted access tokens.

Never persists the raw token — only its SHA-256 hex digest plus scope metadata.
``expires_at=None`` means non-expiring (matches mint ``ttl_seconds=0``).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


def hash_access_token(raw: str) -> str:
    """SHA-256 hex digest of the raw token. Callers must never log ``raw``."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AccessTokenRecord:
    jti: str
    token_hash: str
    tenant_id: str
    workspace_id: str
    project_id: str
    expires_at: datetime | None
    revoked_at: datetime | None = None


class AccessTokenRegistry(Protocol):
    def register(
        self,
        *,
        jti: str,
        token_hash: str,
        tenant_id: str,
        workspace_id: str,
        project_id: str,
        expires_at: datetime | None,
    ) -> None: ...

    def assert_active(self, jti: str, token_hash: str) -> None:
        """Raise ``ValueError`` if the token is missing, hash-mismatched, revoked, or expired."""
        ...

    def get(self, jti: str) -> AccessTokenRecord | None: ...

    def revoke(self, jti: str) -> None: ...


@dataclass
class _Record:
    token_hash: str
    tenant_id: str
    workspace_id: str
    project_id: str
    expires_at: datetime | None
    revoked_at: datetime | None = None


class InMemoryAccessTokenRegistry:
    """Test double. Stores only the token hash, never the raw token."""

    def __init__(self) -> None:
        self._records: dict[str, _Record] = {}

    def register(
        self,
        *,
        jti: str,
        token_hash: str,
        tenant_id: str,
        workspace_id: str,
        project_id: str,
        expires_at: datetime | None,
    ) -> None:
        self._records[jti] = _Record(token_hash, tenant_id, workspace_id, project_id, expires_at)

    def get(self, jti: str) -> AccessTokenRecord | None:
        record = self._records.get(jti)
        if record is None:
            return None
        return AccessTokenRecord(
            jti=jti,
            token_hash=record.token_hash,
            tenant_id=record.tenant_id,
            workspace_id=record.workspace_id,
            project_id=record.project_id,
            expires_at=record.expires_at,
            revoked_at=record.revoked_at,
        )

    def assert_active(self, jti: str, token_hash: str) -> None:
        record = self._records.get(jti)
        if record is None:
            raise ValueError("access token not found")
        if record.revoked_at is not None:
            raise ValueError("access token revoked")
        if record.token_hash != token_hash:
            raise ValueError("access token hash mismatch")
        if record.expires_at is not None and datetime.now(UTC) > record.expires_at:
            raise ValueError("access token expired")

    def revoke(self, jti: str) -> None:
        record = self._records.get(jti)
        if record is None:
            raise ValueError("access token not found")
        record.revoked_at = datetime.now(UTC)


class PostgresAccessTokenRegistry:
    """PostgreSQL adapter (psycopg, sibling pattern to ``PostgresStore``).

    Persists only the SHA-256 hash of each access token — never the raw value.
    """

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("access token registry database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        normalized_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._connection = psycopg.connect(normalized_url, autocommit=True, row_factory=dict_row)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS project_profile")
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS project_profile.access_tokens (
                    jti text PRIMARY KEY,
                    token_hash text NOT NULL,
                    tenant_id text NOT NULL,
                    workspace_id text NOT NULL,
                    project_id text NOT NULL,
                    expires_at timestamptz,
                    revoked_at timestamptz,
                    created_at timestamptz NOT NULL DEFAULT now())"""
            )
            # Existing installs created expires_at NOT NULL before non-expiring tokens.
            cursor.execute(
                """ALTER TABLE project_profile.access_tokens
                   ALTER COLUMN expires_at DROP NOT NULL"""
            )

    def register(
        self,
        *,
        jti: str,
        token_hash: str,
        tenant_id: str,
        workspace_id: str,
        project_id: str,
        expires_at: datetime | None,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO project_profile.access_tokens
                   (jti, token_hash, tenant_id, workspace_id, project_id, expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (jti) DO UPDATE SET
                     token_hash=EXCLUDED.token_hash,
                     expires_at=EXCLUDED.expires_at,
                     revoked_at=NULL""",
                (jti, token_hash, tenant_id, workspace_id, project_id, expires_at),
            )

    def get(self, jti: str) -> AccessTokenRecord | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT jti, token_hash, tenant_id, workspace_id, project_id,
                          expires_at, revoked_at
                   FROM project_profile.access_tokens WHERE jti=%s""",
                (jti,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return AccessTokenRecord(
            jti=str(row["jti"]),
            token_hash=str(row["token_hash"]),
            tenant_id=str(row["tenant_id"]),
            workspace_id=str(row["workspace_id"]),
            project_id=str(row["project_id"]),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )

    def assert_active(self, jti: str, token_hash: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT token_hash, revoked_at, expires_at FROM project_profile.access_tokens WHERE jti=%s",
                (jti,),
            )
            row = cursor.fetchone()
        if row is None:
            raise ValueError("access token not found")
        if row["revoked_at"] is not None:
            raise ValueError("access token revoked")
        if row["token_hash"] != token_hash:
            raise ValueError("access token hash mismatch")
        expires_at = row["expires_at"]
        if expires_at is not None and datetime.now(UTC) > expires_at:
            raise ValueError("access token expired")

    def revoke(self, jti: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE project_profile.access_tokens SET revoked_at=now() WHERE jti=%s",
                (jti,),
            )
            if cursor.rowcount == 0:
                raise ValueError("access token not found")

    def close(self) -> None:
        self._connection.close()
