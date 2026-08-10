---
doc_id: as.doc.tech.data-contracts-and-events
title: Technical Logic and Verification - Data Contracts and Events
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: Phase 6 does not invent a parallel product schema. It defines the verification evidence
  contract that proves Phase 1 through 5 public contracts behave correctly.
tags:
- contract
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/11-data-contracts-and-events.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Technical Logic and Verification - Data Contracts and Events

## Purpose

Phase 6 does not invent a parallel product schema. It defines the verification evidence contract that proves Phase 1 through 5 public contracts behave correctly.

## Core Entities

- `TechnicalLogicPack(id, phase_ref, domain, invariants, algorithms, failure_modes)`
- `VerificationCheck(id, check_type, subject_ref, command, expected_evidence)`
- `VerificationRun(id, check_id, status, started_at, finished_at, report_ref)`
- `PhaseGateDecision(id, phase_number, status, owner, waiver_ref, decided_at)`
- `RuntimeScenario(id, name, steps, expected_records, expected_events)`

## Check Types

- `contract`
- `state_machine`
- `idempotency`
- `redaction`
- `retrieval`
- `docs_drift`
- `rule_evaluation`
- `broker_delivery`
- `reliability`
- `runtime_e2e`

## Evidence Fields

Every verification report should include:

- `check_id`
- `subject_ref` (service, contract, or scenario)
- `status` (`passed`, `failed`, `skipped`, `waived`)
- `command`
- `correlation_id` when exercising runtime flows
- `evidence_refs` (logs, fixtures, pytest node ids)
- `documentation_ref` (path into `docs/06-technical-logic/` or owning phase doc)

## Events

Phase 6 emits process evidence, typically as CI artifacts rather than broker business events:

- `verification.check_started`
- `verification.check_completed`
- `verification.phase_gate_passed`
- `verification.phase_gate_failed`
- `verification.phase_gate_waived`

If these are published on the platform broker later, they must use the standard event envelope owned by interoperability contracts.

## Contract Rules

- Phase 6 must not fork Phase 1 through 5 entity schemas; it validates them.
- A waiver cannot silently drop a critical security or redaction check.
- Canonical test commands in service READMEs are part of the contract surface for this phase.
