"""Unit tests for port_profile bind probe."""

from __future__ import annotations

import socket

from port_profile.loader import check_port_available


def test_check_port_available_sets_reuseaddr(monkeypatch):
    created: list[socket.socket] = []
    real_socket = socket.socket

    class _Spy(socket.socket):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.opts: list[tuple] = []
            created.append(self)

        def setsockopt(self, level, optname, value):  # noqa: ANN001
            self.opts.append((level, optname, value))
            return super().setsockopt(level, optname, value)

    monkeypatch.setattr(socket, "socket", _Spy)
    assert check_port_available(0, host="127.0.0.1") is True
    assert created
    assert any(
        level == socket.SOL_SOCKET and opt == socket.SO_REUSEADDR and int(val) == 1
        for level, opt, val in created[0].opts
    )
    # Restore not required — monkeypatch tears down.
    _ = real_socket
