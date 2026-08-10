# Remote / one-command client

Full operator guide (SSH + HTTP, examples):  
[41-one-command-cross-platform-agent-onboarding.md](../../docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md)

SSH-only detail:  
[40-remote-dev-client-mcp-wiring.md](../../docs/08-software-engineering-architecture/40-remote-dev-client-mcp-wiring.md)

## Quick start

```bash
# Dev host — interactive SSH wizard (cwd = that project for MCP + sync)
cd /opt/MyApp && astloom connect

# Several apps at once (comma-separated); each gets MCP + sync pin
astloom connect /opt/App1,/opt/App2,/opt/App3

# Re-auth / replace Astloom pubkey
astloom connect edit

# Advanced: template + hand-edit <checkout>/.astloom/connect.yaml
astloom connect init
```

```bash
# Astloom server — HTTP mode only
export ASTLOOM_MCP_TOKEN_SECRET='long-random-secret'
export ASTLOOM_MCP_HTTP_PUBLIC_URL='http://astloom.example.internal:32500'
astloom mcp serve-http --port 32500
```
