# Live: project-scoped backup / restore

Requires Compose Postgres (and Neo4j when graph store is neo4j).

```bash
cd /opt/Astloom
.venv/bin/python -m pytest tests/backend/live/astloom_backup -m live -q
```
