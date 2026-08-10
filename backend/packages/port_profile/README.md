# port_profile

Phase 8 shared helper for Astloom development port profiles and GAP-T07 preflight.

- Profile file: `backend/configs/port-profiles/astloom-dev.json`
- Loads overrideable `ASTLOOM_*_PORT` values
- Rejects common default ports
- Bind check via `check_port_available`
- Owning-process detection via Linux `ss` / `lsof` (`find_port_owner`)
- Alternate free port suggestion in the project range (`suggest_alternate_port`)
- Full preflight report + `.astloom/run/port-map.json` artifact (`run_preflight` / `write_port_map`)
- CLI: `astloom ports show|check [--write-map] [--allow-ours]`
