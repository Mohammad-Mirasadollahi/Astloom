---
doc_id: as.doc.gap.governance-operations-gaps
title: Governance and Operations Gaps
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This document captures governance, operational, compliance, and process gaps that
  should be resolved before production adoption.
tags:
- gap
- gap
phase: 10-gap-analysis
canonical_path: docs/10-gap-analysis/04-governance-operations-gaps.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Governance and Operations Gaps

## Purpose

This document captures governance, operational, compliance, and process gaps that should be resolved before production adoption.

## GAP-G01 - Compliance Requirements by Customer Segment

Different customers may have different compliance requirements.

Questions:

- Is the target customer startup, enterprise, regulated enterprise, or internal team?
- Are SOC 2, GDPR, HIPAA, ISO 27001, or data residency requirements needed?
- Which audit evidence must be retained?

Resolution output:

- Compliance requirements matrix.
- Retention and audit evidence policy per segment.

## GAP-G02 - Data Deletion and Right-to-Erasure

The platform stores memory, logs, graph nodes, artifacts, and prompts. Deletion requirements need more detail.

Questions:

- How is customer data deleted from memory?
- How is deletion propagated to graph embeddings?
- How are audit retention requirements balanced with privacy deletion?

Resolution output:

- Data deletion workflow.
- Privacy and audit conflict policy.

## GAP-G03 - Human Approval Ownership

Escalation exists, but ownership rules need operational detail.

Questions:

- Who approves security changes?
- Who approves billing changes?
- Who approves production automation?
- What happens when approver is unavailable?

Resolution output:

- Approval ownership matrix.
- Escalation fallback chain.

## GAP-G04 - Incident Severity Model

Incident response exists, but severity definitions should be tailored to Astloom.

Questions:

- What makes an Astloom incident critical?
- Is wrong context injection a Sev1, Sev2, or Sev3?
- How is agent-caused production risk classified?

Resolution output:

- Incident severity definitions.
- Response time expectations.

## GAP-G05 - Operational Cost Governance

The platform can call LLMs, embeddings, graph indexing, and storage systems. Cost governance needs more detail.

Questions:

- Who owns LLM budget?
- Are there per-tenant quotas?
- How are expensive workflows rate-limited?
- What alerts trigger cost review?

Resolution output:

- Cost budget policy.
- Quota and rate-limit model.
- Cost dashboard requirements.

## GAP-G06 - Adapter Certification

External adapters can be risky because they connect to tools and may act on behalf of agents.

Questions:

- How is an adapter certified?
- What tests must it pass?
- Who can install an adapter?
- How is a compromised adapter disabled?

Resolution output:

- Adapter certification policy.
- Adapter kill switch procedure.

## GAP-G07 - Documentation Ownership

The documentation tree is large and must have owners.

Questions:

- Who owns each documentation section?
- How are docs reviewed when architecture changes?
- How are stale docs detected outside code symbols?

Resolution output:

- Documentation ownership matrix.
- Architecture review process.

## GAP-G08 - Production Readiness Checklist

The plan has many components, but a release readiness checklist should be created.

Questions:

- What must be true before the first production deployment?
- Which runbooks are mandatory?
- Which dashboards and alerts are mandatory?
- Which failure modes must be tested?

Resolution output:

- Production readiness checklist.
- Go/no-go review template.
