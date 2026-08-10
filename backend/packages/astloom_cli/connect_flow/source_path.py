"""``source.server_path`` resolution for connect (local dogfood only).

Module contract:
- Role: resolve ``source.server_path`` for local (``--local``) connect only.
- SoT / invariants: never invent Astloom identity pins; never rsync-stage a
  durable checkout (client remote sync uses content-push instead).
- Failures: never prompt on TTY.

Remote (SSH) on-server-tree discovery has been removed (API-only HTTPS
migration). Non-local connect leaves ``source.server_path`` empty unless the
operator sets it explicitly in ``connect.yaml``; client sync always
content-pushes over HTTPS.
"""

from __future__ import annotations

from pathlib import Path


def source_path_for_connect(*, local: bool, work: Path, configured: str = "") -> str:
    """Ingest path: same-host cwd is fine; remote connect leaves it to the operator (or empty).

    ``source.server_path`` must exist on the Astloom host when set (NFS/clone),
    not a blind copy of the laptop checkout path. Only dogfood ``--local`` may
    default to cwd. Client remote sync does not require this — it content-pushes.
    """
    text = (configured or "").strip()
    if text:
        return text
    if local:
        return str(work)
    return ""


# Compat alias.
_source_path_for_connect = source_path_for_connect
