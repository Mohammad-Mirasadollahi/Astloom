"""Heuristic secret scan before export packs (RM-06). Clean-room; not Secretlint."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretFinding:
    rule_id: str
    message: str
    line: int


_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "private_key",
        "PEM private key block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "aws_access_key",
        "AWS access key id pattern",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "generic_api_key_assign",
        "High-entropy secret assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\b\s*[=:]\s*['\"][^'\"]{12,}"
        ),
    ),
    (
        "slack_token",
        "Slack token pattern",
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    ),
    (
        "github_pat",
        "GitHub personal access token",
        re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    ),
)


def scan_text_for_secrets(text: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for rule_id, message, pattern in _RULES:
            if pattern.search(line):
                findings.append(SecretFinding(rule_id=rule_id, message=message, line=i))
    return findings
