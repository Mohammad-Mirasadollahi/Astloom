# Live: project-profile-service

## HTTPS connect bootstrap

```bash
# Requires Astloom compose Postgres on 127.0.0.1:32232
.venv/bin/python -m pytest tests/live/project-profile-service/test_https_connect_bootstrap_live.py -m live -v
```

Proves auto TLS cert generation, HTTPS bootstrap with bootstrap secret, single access token
(no refresh; SHA-256 digest registered at rest in `project_profile.access_tokens`),
Bearer-gated `connect/status`, and fail-closed after DB revoke of the token `jti`.
