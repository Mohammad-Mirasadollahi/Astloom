---
name: astloom-source-contracts
description: >-
  Selective hard-module contract docstrings (standard 49) and package/folder README maps
  (standard 50) — apply on edit and fix-on-read of hard modules only (default-deny).
---

# Astloom source contracts

## When

- Editing a module that **passes** the Hard Module Test in standard 49 (SoT vs wake, queue/worker,
  fail-open/closed, state machine, trust boundary, exclusivity).
- **Fix-on-read:** opened a **hard** module with missing/wrong file-top contract.
- Agents already mis-edit SoT / crash policy on that file, or a package/folder seam is confusing.
- Adding or splitting a service/shared package root (README map — standard 50).

## How

1. **Hard Module Test first** (default **no**): if unsure or none of the 49 questions are a clear
   yes → **MUST NOT** write a module contract docstring. Normative:
   `docs/08-software-engineering-architecture/49-module-contract-docstrings-standard.md`.
2. **Module contract (49)** — hard modules only: English file-top docstring, 3–6 lines: role;
   SoT/invariants; allowed vs forbidden failures (fail-open vs fail-closed). Optional wake/rebuild.
3. Read an existing contract before changing durability, retries, or crash handling.
4. Update or delete the header in the **same** change when the contract changes — never leave a lying header.
5. **Fix-on-read:** missing/wrong hard-module header → add/fix **same turn** before other work.
   Still skip helpers/DTOs/re-exports.
6. **Package README (50):** Purpose, Boundaries (may/must-not), Start-here list of 2–5 files.
   Soft ≤ ~40 lines. Normative: `docs/08-software-engineering-architecture/50-package-folder-readme-standard.md`.
7. After edits: prefer graph sync/ingest so `MODULE_CONTRACT` / package README nodes stay retrievable.

## Do not

- Contract helpers, DTOs, `__init__` re-exports, thin HTTP/MCP/CLI wiring, fixtures, or “just in case.”
- Skip fix-on-read for a hard module you already opened.
- Write a per-file encyclopedia in folder READMEs.
- Put SoT / fail-open policy only in the README — it belongs in the hard-module docstring.
- Persian in committed source or README maps.
