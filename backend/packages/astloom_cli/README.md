# astloom CLI

Command-line interface for Usage Profiles, local project state, Cursor MCP export, and the MCP gateway.

Installed as console script `astloom` via editable install (`pip install -e .` from repo root).

Layout: `main.py` (dispatch) · `parser/` (argparse by domain) · `util.py` · `state.py` · `commands/` (handlers).

```bash
bash scripts/ensure-venv.sh
astloom doctor
astloom profile list
astloom project register --tenant t --workspace w --project p --name Demo --usage-profile programming-cursor-mcp
astloom project activate --tenant t --workspace w --project p --usage-profile programming-cursor-mcp
astloom cursor export --tenant t --workspace w --project p --out /tmp/astloom-mcp.json
astloom mcp tools --usage-profile programming-cursor-mcp
```

Design: `docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md`  
CLI docs: `docs/08-software-engineering-architecture/36-astloom-cli.md`
