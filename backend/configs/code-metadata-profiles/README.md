# Code Metadata Profiles

Path: `backend/configs/code-metadata-profiles`

## Purpose

Stores future configuration profiles for metadata extraction, scoring, freshness, retrieval, and source-read escalation.

## Required Settings

- metadata freshness thresholds by language and repository size.
- ranking weights for symbol relevance, graph proximity, documentation freshness, ownership, call frequency, test coverage, and risk.
- source-read escalation thresholds for low confidence, stale metadata, high-risk changes, security-sensitive code, generated code, and ambiguous call resolution.
- token budget limits for metadata context packs.
- language-specific parser and extractor settings.

## Rule

Do not hard-code metadata scoring or source-read behavior. Profiles must drive weighting and thresholds.

Default profile: `default.json`, loaded by `backend/packages/code-metadata/code_metadata/loader.py`.
