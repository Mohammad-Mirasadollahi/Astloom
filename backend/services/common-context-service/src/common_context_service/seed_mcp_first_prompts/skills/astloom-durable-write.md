---
name: astloom-durable-write
description: Write memory, task, activity, or decision records via Astloom MCP.
---

# Astloom durable write

## When

- Persisting a decision, activity, memory, or task the project should retain.

## How

1. `astloom_write` with `resource` in `memory` | `task` | `activity` | `decision`.
2. Fill required fields for that resource (`title` / `body` / `instructions` / `summary` as applicable).
3. Confirm result ids when useful.

## Do not

- Fake success on tool failure — surface the error and ask how to proceed.
