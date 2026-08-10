# Dependency Injection Primitives

Path: `backend/packages/shared-kernel/dependency-injection`

## Purpose

Defines future shared primitives and conventions for dependency injection, composition roots, provider registration, lifecycle scopes, and test-time dependency replacement.

## Rules

- Domain code must not resolve dependencies from a container.
- Application services should receive dependencies through constructors or explicit factories.
- Infrastructure adapters are wired at the composition root.
- Service locator usage is forbidden outside bootstrap code.
- Runtime dependencies must be replaceable in tests.

## Status

Scaffold only. No implementation code has been added yet.
