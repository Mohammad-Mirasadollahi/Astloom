# Linear

Path: `backend/integrations/tickets/linear`

## Purpose

Linear tracker adapter boundary for ExternalTicket remote create/dispatch.

## Implementation

- Module: `backend/integrations/tickets/linear/adapter.py` (`LinearTrackerAdapter`)
- Registry: `adapter_service.trackers.build_tracker_registry` when `ASTLOOM_LINEAR_API_KEY` and `ASTLOOM_LINEAR_TEAM_ID` are set
- Opt-in live: `tests/live/adapter-service/test_external_ticketing_vendor_sandbox.py`

## Status

Implemented. Mandatory CI does not require Linear credentials.
