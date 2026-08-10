# Connect flow package

Owns `astloom connect` orchestration: reachability, API/HTTP MCP wiring, remote sync/ingest, and post-connect summary UI. HTTPS is the only remote transport — SSH has been removed from the Astloom product.

Client remote sync uses **content-push** (`client_push.py` → remote `ingest-push`). `source_path.py` only resolves `source.server_path` for local (`--local`) connect; it does not stage checkouts.
