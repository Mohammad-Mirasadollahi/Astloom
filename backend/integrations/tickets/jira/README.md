# Jira

Path: `backend/integrations/tickets/jira`

## Purpose

Jira tracker adapter boundary for ExternalTicket remote create/dispatch.

## Implementation

- Module: `backend/integrations/tickets/jira/adapter.py` (`JiraTrackerAdapter`)
- Registry: `adapter_service.trackers.build_tracker_registry` when `ASTLOOM_JIRA_BASE_URL`, `ASTLOOM_JIRA_EMAIL`, `ASTLOOM_JIRA_API_TOKEN`, and `ASTLOOM_JIRA_PROJECT_KEY` are set
- Opt-in live: `tests/live/adapter-service/test_external_ticketing_vendor_sandbox.py`

## Status

Implemented. Mandatory CI does not require Jira credentials.
