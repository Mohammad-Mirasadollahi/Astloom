"""Minimal Content-Length JSON-RPC LSP client over stdio subprocess."""

from __future__ import annotations

import json
import subprocess
import threading
from typing import Any

from ..errors import ValidationError


class JsonRpcLspClient:
    """Synchronous LSP client (initialize + request/notify). Local process only."""

    def __init__(self, argv: list[str], *, cwd: str | None = None, timeout_s: float = 30.0) -> None:
        if not argv:
            raise ValidationError("language server argv is empty")
        self._timeout_s = timeout_s
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=False,
        )
        self._next_id = 1
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._pending: dict[int, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._closed = False
        self._cv = threading.Condition(self._lock)
        self._reader.start()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._proc.terminate()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=2)
        self._reader.join(timeout=2)
        for stream in (self._proc.stdout, self._proc.stderr):
            if stream is not None:
                stream.close()

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            msg_id = self._next_id
            self._next_id += 1
            self._pending[msg_id] = {}
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
        self._write(payload)
        import time

        end = time.monotonic() + self._timeout_s
        with self._cv:
            while msg_id in self._pending and "result" not in self._pending[msg_id] and "error" not in self._pending[msg_id]:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    self._pending.pop(msg_id, None)
                    raise ValidationError(f"LSP timeout waiting for {method}")
                self._cv.wait(timeout=remaining)
            slot = self._pending.pop(msg_id, {})
        if "error" in slot:
            err = slot["error"]
            raise ValidationError(f"LSP error for {method}: {err}")
        return slot.get("result")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _write(self, message: dict[str, Any]) -> None:
        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        stdin = self._proc.stdin
        if stdin is None:
            raise ValidationError("LSP stdin closed")
        with self._lock:
            stdin.write(header + body)
            stdin.flush()

    def _read_loop(self) -> None:
        stdout = self._proc.stdout
        if stdout is None:
            return
        buffer = b""
        while not self._closed:
            chunk = stdout.read(1)
            if not chunk:
                break
            buffer += chunk
            while b"\r\n\r\n" in buffer:
                header, rest = buffer.split(b"\r\n\r\n", 1)
                length = None
                for line in header.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        try:
                            length = int(line.split(b":", 1)[1].strip())
                        except ValueError:
                            length = None
                if length is None:
                    buffer = rest
                    continue
                while len(rest) < length:
                    more = stdout.read(length - len(rest))
                    if not more:
                        return
                    rest += more
                body, buffer = rest[:length], rest[length:]
                try:
                    message = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                self._handle_message(message)

    def _handle_message(self, message: dict[str, Any]) -> None:
        with self._cv:
            if "id" in message and ("result" in message or "error" in message):
                msg_id = int(message["id"])
                if msg_id in self._pending:
                    if "error" in message:
                        self._pending[msg_id]["error"] = message["error"]
                    else:
                        self._pending[msg_id]["result"] = message.get("result")
                    self._cv.notify_all()
            else:
                self._events.append(message)
