# GitHub Issues

Path: `backend/integrations/tickets/github-issues`

## Purpose

GitHub Issues tracker adapter boundary for ExternalTicket remote create/dispatch.

## Implementation

- Module: `backend/integrations/tickets/github-issues/adapter.py` (`GitHubIssuesTrackerAdapter`)
- Registry: `adapter_service.trackers.build_tracker_registry` when `ASTLOOM_GITHUB_TOKEN`, `ASTLOOM_GITHUB_OWNER`, and `ASTLOOM_GITHUB_REPO` are set
- Opt-in live: `tests/live/adapter-service/test_external_ticketing_vendor_sandbox.py`

## Status

Implemented. Mandatory CI does not require GitHub credentials.
