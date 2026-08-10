---
name: astloom-memory
description: Retrieve or persist project memory through Astloom MCP.
---

# Astloom memory

## When

- Need durable project facts, decisions, or conventions.
- User asks to remember or recall something.

## How

1. Retrieve: `astloom_memory_retrieve` (`query`, optional `include_history`).
2. Persist: `astloom_write` `resource=memory` (`title`, `body`, optional `tags`, `confidence`).
3. Cite what Astloom returned; do not invent memory.

## Do not

- Keep durable facts chat-only when write/retrieve tools are available.
