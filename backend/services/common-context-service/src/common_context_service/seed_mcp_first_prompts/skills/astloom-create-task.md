---
name: astloom-create-task
description: Create a durable Astloom Task for follow-up engineering work.
---

# Astloom create task

## When

- User or plan needs a durable follow-up Task in Astloom.

## How

1. Prefer `astloom_create_task` (`title`, optional `instructions`).
2. Or `astloom_write` `resource=task` when that path is required.
3. Return the created task identity from the tool result.

## Do not

- Substitute chat checklists for durable Tasks when the user asked to track work in Astloom.
