"""Dev client wiring (list supported MCP client targets)."""

from __future__ import annotations

import argparse

from astloom_cli.mcp_client_targets import list_mcp_client_targets
from astloom_cli.util import print_json


def cmd_client_list_mcp_clients(_args: argparse.Namespace) -> int:
    print_json(list_mcp_client_targets())
    return 0
