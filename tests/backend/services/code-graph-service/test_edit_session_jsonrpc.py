"""Feature 49 polish: JSON-RPC Content-Length client + WorkspaceEdit apply."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from code_graph_service.domain.edit_session.jsonrpc import JsonRpcLspClient
from code_graph_service.domain.edit_session.workspace_edit import (
    apply_workspace_edit,
    resolve_under_root,
)
from code_graph_service.domain.errors import ValidationError
import pytest


_FAKE_LS = textwrap.dedent(
    r"""
    import json
    import sys
    from pathlib import Path

    ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    DEMO = (ROOT / "demo.py").resolve()

    def read_message():
        headers = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line or line in (b"\r\n", b"\n"):
                break
            key, _, value = line.decode("ascii").partition(":")
            headers[key.strip().lower()] = value.strip()
        length = int(headers.get("content-length", "0"))
        body = sys.stdin.buffer.read(length)
        return json.loads(body.decode("utf-8"))

    def write_message(payload):
        raw = json.dumps(payload).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()

    while True:
        msg = read_message()
        method = msg.get("method")
        msg_id = msg.get("id")
        if method == "initialize" and msg_id is not None:
            write_message({"jsonrpc": "2.0", "id": msg_id, "result": {"capabilities": {}}})
        elif method == "initialized":
            continue
        elif method == "textDocument/didOpen":
            continue
        elif method == "textDocument/references" and msg_id is not None:
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": [
                        {
                            "uri": DEMO.as_uri(),
                            "range": {
                                "start": {"line": 0, "character": 4},
                                "end": {"line": 0, "character": 9},
                            },
                        }
                    ],
                }
            )
        elif method == "textDocument/definition" and msg_id is not None:
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "uri": DEMO.as_uri(),
                        "range": {
                            "start": {"line": 0, "character": 4},
                            "end": {"line": 0, "character": 9},
                        },
                    },
                }
            )
        elif method == "textDocument/rename" and msg_id is not None:
            new_name = (msg.get("params") or {}).get("newName") or "greet"
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "changes": {
                            DEMO.as_uri(): [
                                {
                                    "range": {
                                        "start": {"line": 0, "character": 4},
                                        "end": {"line": 0, "character": 9},
                                    },
                                    "newText": new_name,
                                }
                            ]
                        }
                    },
                }
            )
        elif method == "exit":
            break
        elif msg_id is not None:
            write_message({"jsonrpc": "2.0", "id": msg_id, "result": None})
    """
)


def test_jsonrpc_content_length_roundtrip(tmp_path: Path):
    script = tmp_path / "fake_ls.py"
    script.write_text(_FAKE_LS, encoding="utf-8")
    (tmp_path / "demo.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    client = JsonRpcLspClient(
        [sys.executable, str(script), str(tmp_path)],
        cwd=str(tmp_path),
        timeout_s=5.0,
    )
    try:
        caps = client.request("initialize", {"capabilities": {}})
        assert isinstance(caps, dict)
        client.notify("initialized", {})
        refs = client.request(
            "textDocument/references",
            {
                "textDocument": {"uri": (tmp_path / "demo.py").resolve().as_uri()},
                "position": {"line": 0, "character": 4},
                "context": {"includeDeclaration": True},
            },
        )
        assert isinstance(refs, list)
        assert refs[0]["range"]["start"]["line"] == 0
    finally:
        client.close()


def test_lsp_edit_session_over_fake_server(tmp_path: Path):
    from code_graph_service.domain.edit_session.jsonrpc import JsonRpcLspClient
    from code_graph_service.domain.edit_session.lsp_session import LspEditSession
    from code_graph_service.domain.parsing_authority import SESSION_EDGE_REFERENCE_KIND

    script = tmp_path / "fake_ls.py"
    script.write_text(_FAKE_LS, encoding="utf-8")
    (tmp_path / "demo.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    client = JsonRpcLspClient(
        [sys.executable, str(script), str(tmp_path)],
        cwd=str(tmp_path),
        timeout_s=5.0,
    )
    client.request("initialize", {"capabilities": {}, "rootUri": tmp_path.resolve().as_uri()})
    client.notify("initialized", {})
    session = LspEditSession(client, language="python", root=tmp_path.resolve())
    try:
        refs = session.find_references(
            root_path=str(tmp_path),
            file_path="demo.py",
            line=0,
            character=4,
            language="python",
        )
        assert refs.available is True
        assert refs.reference_kind == SESSION_EDGE_REFERENCE_KIND
        assert len(refs.locations) >= 1
        renamed = session.rename_symbol(
            root_path=str(tmp_path),
            file_path="demo.py",
            line=0,
            character=4,
            new_name="greet",
            language="python",
            apply=True,
        )
        assert renamed.applied is True
        assert "demo.py" in renamed.changed_files
        assert "def greet()" in (tmp_path / "demo.py").read_text(encoding="utf-8")
    finally:
        session.close()


def test_apply_workspace_edit_and_escape(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    target = root / "a.py"
    target.write_text("def hello():\n    return 1\n", encoding="utf-8")
    uri = target.resolve().as_uri()
    changed = apply_workspace_edit(
        str(root),
        {
            "changes": {
                uri: [
                    {
                        "range": {
                            "start": {"line": 0, "character": 4},
                            "end": {"line": 0, "character": 9},
                        },
                        "newText": "greet",
                    }
                ]
            }
        },
    )
    assert changed == ["a.py"]
    assert "def greet()" in target.read_text(encoding="utf-8")

    with pytest.raises(ValidationError, match="escapes"):
        resolve_under_root(str(root), "../secret.py")
