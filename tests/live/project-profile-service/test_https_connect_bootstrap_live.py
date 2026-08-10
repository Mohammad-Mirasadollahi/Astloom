"""Live HTTPS connect bootstrap + Bearer status (real TLS + Postgres).

Requires:
- Astloom Postgres on 127.0.0.1:32232 (compose)
- Env secrets set by the test harness (or caller)

Marked ``live`` so default unit runs skip it.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.live

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("ASTLOOM_LIVE_TLS_DATA", "/tmp/astloom-live-https-qa"))
# Use hostname "localhost" so the auto-generated leaf SAN matches (not bare 127.0.0.1).
HOST = "localhost"
BIND = "127.0.0.1"
PORT = int(os.environ.get("ASTLOOM_LIVE_PROFILE_PORT", "32194"))
DSN = os.environ.get(
    "ASTLOOM_PROJECT_PROFILE_DATABASE_URL",
    "postgresql://astloom:astloom-local-dev-secret@127.0.0.1:32232/astloom",
)
BOOTSTRAP_SECRET = "live-bootstrap-secret-32chars!!"
TOKEN_SECRET = "live-mcp-token-secret-32chars!!!!"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _postgres_reachable() -> bool:
    try:
        import psycopg

        with psycopg.connect(DSN, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def https_profile_server():
    if not _postgres_reachable():
        pytest.skip("Astloom Postgres not reachable for live HTTPS probe")

    DATA.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / "backend" / "packages"))
    from astloom_cli.tls_certs import ensure_tls_material

    material = ensure_tls_material(data_root=DATA, hostname="localhost")
    assert material.cert_path.is_file()
    assert material.key_path.is_file()
    assert material.ca_pem_path.is_file()

    env = os.environ.copy()
    env.update(
        {
            "ASTLOOM_PROJECT_PROFILE_DATABASE_URL": DSN,
            "ASTLOOM_PROJECT_PROFILE_PORT": str(PORT),
            "ASTLOOM_MCP_TOKEN_SECRET": TOKEN_SECRET,
            "ASTLOOM_CONNECT_BOOTSTRAP_SECRET": BOOTSTRAP_SECRET,
            "ASTLOOM_DATA_ROOT": str(DATA),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(REPO / "backend" / "packages"),
                    str(REPO / "backend" / "services" / "project-profile-service" / "src"),
                    env.get("PYTHONPATH", ""),
                ]
            ),
        }
    )

    # Avoid clobbering an unrelated listener.
    if _port_open(BIND, PORT):
        pytest.skip(f"port {PORT} already in use; refuse to hijack for live probe")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "project_profile_service.api:app",
            "--factory",
            "--host",
            BIND,
            "--port",
            str(PORT),
            "--ssl-certfile",
            str(material.cert_path),
            "--ssl-keyfile",
            str(material.key_path),
        ],
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + 30
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            pytest.fail(f"uvicorn exited early: {out[-2000:]}")
        if _port_open(BIND, PORT):
            ready = True
            break
        time.sleep(0.25)
    if not ready:
        proc.kill()
        out = proc.stdout.read() if proc.stdout else ""
        pytest.fail(f"uvicorn did not open {PORT}: {out[-2000:]}")

    yield {
        "base": f"https://{HOST}:{PORT}",
        "ca": material.ca_pem_path,
        "cert_generated": material.generated,
    }

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_live_https_auto_cert_bootstrap_and_bearer_status(https_profile_server):
    base = https_profile_server["base"]
    ca = https_profile_server["ca"]
    project = f"live-https-{uuid.uuid4().hex[:8]}"
    headers = {
        "X-Tenant-Id": "live",
        "X-Workspace-Id": "qa",
        "X-Actor-Id": "live-qa",
        "Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }

    import ssl

    ctx = ssl.create_default_context(cafile=str(ca))
    with httpx.Client(verify=ctx, timeout=30.0) as client:
        # Wrong bootstrap secret → 401
        bad = client.post(
            f"{base}/api/v1/projects/{project}/connect/bootstrap",
            headers=headers,
            json={"bootstrap_secret": "wrong", "usage_profile": "programming-cursor-mcp", "name": project},
        )
        assert bad.status_code == 401, bad.text

        # Bootstrap with real secret over HTTPS + trusted CA
        boot = client.post(
            f"{base}/api/v1/projects/{project}/connect/bootstrap",
            headers=headers,
            json={
                "bootstrap_secret": BOOTSTRAP_SECRET,
                "usage_profile": "programming-cursor-mcp",
                "name": project,
            },
        )
        assert boot.status_code == 200, boot.text
        body = boot.json()
        access = str(body.get("access_token") or "")
        assert access.startswith("as1."), body
        assert int(body.get("expires_in") or 0) >= 86400
        assert "refresh_token" not in body

        # Status without Bearer → 401
        no_auth = client.get(
            f"{base}/api/v1/projects/{project}/connect/status",
            headers={k: v for k, v in headers.items() if k != "Idempotency-Key"},
        )
        assert no_auth.status_code == 401, no_auth.text

        # Status with access token → 200
        ok = client.get(
            f"{base}/api/v1/projects/{project}/connect/status",
            headers={
                **{k: v for k, v in headers.items() if k != "Idempotency-Key"},
                "Authorization": f"Bearer {access}",
            },
        )
        assert ok.status_code == 200, ok.text
        status_body = ok.json()
        assert isinstance(status_body, dict)

        # Hash-at-rest: DB has SHA-256 digest only (never plaintext bearer)
        sys.path.insert(0, str(REPO / "backend" / "packages"))
        from astloom_auth.token_registry import hash_access_token
        from usage_profile.mcp_tokens import verify_connect_token

        claims = verify_connect_token(access, secret=TOKEN_SECRET)
        jti = claims.get("jti")
        assert jti, claims
        expected_hash = hash_access_token(access)

        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DSN, connect_timeout=5, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT jti, token_hash, tenant_id, workspace_id, project_id,
                           revoked_at, expires_at
                    FROM project_profile.access_tokens
                    WHERE jti = %s
                    """,
                    (jti,),
                )
                row = cur.fetchone()
                assert row is not None, "minted token must be registered in Postgres"
                assert row["token_hash"] == expected_hash
                assert access not in row["token_hash"]
                assert access not in (row["jti"] or "")
                assert row["tenant_id"] == "live"
                assert row["workspace_id"] == "qa"
                assert row["project_id"] == project
                assert row["revoked_at"] is None

                # Revoke → subsequent Bearer must fail closed
                cur.execute(
                    "UPDATE project_profile.access_tokens SET revoked_at = now() WHERE jti = %s",
                    (jti,),
                )
                conn.commit()

        revoked = client.get(
            f"{base}/api/v1/projects/{project}/connect/status",
            headers={
                **{k: v for k, v in headers.items() if k != "Idempotency-Key"},
                "Authorization": f"Bearer {access}",
            },
        )
        assert revoked.status_code == 401, revoked.text
