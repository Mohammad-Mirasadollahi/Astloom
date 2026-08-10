"""Tests for client post-install / post-upgrade Usage Profile next steps."""

from __future__ import annotations

from astloom_cli.client_next_steps import (
    CLIENT_USAGE_PROFILE_NEXT_STEPS,
    print_client_connect_next_steps,
)


def test_client_next_steps_cover_interactive_and_noninteractive():
    text = CLIENT_USAGE_PROFILE_NEXT_STEPS
    assert "astloom-client profile list" in text
    assert "astloom-client connect" in text
    assert "--usage-profile" in text
    assert "--local" in text
    assert "--server" in text
    assert "connect.yaml" in text


def test_print_client_connect_next_steps(capsys):
    print_client_connect_next_steps()
    out = capsys.readouterr().out
    assert "Usage Profile" in out
    assert "--usage-profile" in out
    assert "astloom-client connect" in out
