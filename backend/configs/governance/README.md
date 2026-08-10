# Governance catalogs

Phase 9/10 machine-readable governance inputs:

- `risk-open-decisions.json` — risks and open decisions with owners and review dates
- `impact-kpis.json` — required impact KPIs and report fields
- `gap-register.json` — master + technical + architecture gap register
- `bounded-context-map.json` — GAP-A01 entity ownership / forbidden persistence edges
- `sync-async-boundaries.json` — GAP-A02 operation sync/async catalog
- `read-model-catalog.json` — GAP-A03 read model consistency map
- `tenancy-deployment-modes.json` — GAP-A04 tenancy modes
- `agent-trust-policy.json` — GAP-A05 trust lifecycle
- `ide-product-boundary.json` — GAP-A06 action→surface matrix
- `admin-permission-matrix.json` — GAP-A07 admin actions

Loaded by `backend/packages/governance_catalog/` and `backend/packages/architecture_governance/`.
