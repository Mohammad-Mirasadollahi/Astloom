# usage_profile package

Load and validate Usage Profile catalogs, resolve effective profiles, and materialize Cursor MCP connection fragments.

```bash
PYTHONPATH=backend/packages .venv/bin/python -c "from usage_profile import load_usage_profile; print(load_usage_profile('programming-cursor-mcp')['title'])"
```

Catalog: `backend/configs/usage-profiles/`  
Design: `docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md`
