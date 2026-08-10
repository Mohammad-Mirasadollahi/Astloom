# Common Context Profiles

Path: `backend/configs/common-context-profiles`

## Purpose

Stores future configuration profiles that control how reusable common context is proposed, scored, reviewed, injected, suppressed, and reported.

## Expected Settings

- score weights for frequency, recency, confidence, user pinning, task similarity, and effectiveness.
- maximum common-context token budget per workflow type.
- approval thresholds for project, project-group, and organization scopes.
- feature toggles for automatic proposal, automatic suppression, conflict warnings, and reporting.
- isolation policies that prevent unrelated projects from sharing common items.

## Rule

Profiles must be data-driven. Do not hard-code common-context behavior into service code, prompts, launchers, or agent wrappers.
