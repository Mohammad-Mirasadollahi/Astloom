# API Contracts

Path: `backend/packages/contracts/api`

## Purpose

Future home for shared API request, response, error, pagination, filtering, sorting, and idempotency contracts.

## Rules

- API schemas must follow `/root/Astloom/docs/14-api-design-and-naming-standards/`.
- JSON wire fields must use snake_case.
- DTO names must be explicit, such as CreateTaskRequest and CreateTaskResponse.
- Public errors must follow the structured error contract.
- List responses must use the standard pagination shape.
- Retryable commands must define idempotency behavior.

## Status

Scaffold only. No implementation code has been added yet.
