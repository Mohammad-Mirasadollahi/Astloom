---
doc_id: as.doc.ckg.third-party-notices
title: Third-Party Notices — Code Intelligence Prior Art
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: MIT attribution for prior-art code-intelligence projects and Apache 2.0 Headroom
  notices; Astloom native context compression required per doc 54 (not IDE toolstack).
tags:
- standard
- ckg
- license
- mit
- apache-2.0
- prior-art
- headroom
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/THIRD_PARTY_NOTICES.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
- security
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.code-intel-prior-art-license
- as.doc.ckg.repomix-prior-art-ideas-and-license
- as.doc.ckg.headroom-native-context-compression
doc_version: 1.4.1
updated_at: 2026-08-10
---

# Third-Party Notices — Code Intelligence Prior Art

## Purpose

This file records **attribution** for open-source projects whose
**ideas** (and, if ever approved by ADR, source) inform Astloom Code-Knowledge
Graph and related agent context features. Astloom’s default policy is clean-room
re-implementation; see
[`21-code-intelligence-prior-art-ideas-and-license.md`](21-code-intelligence-prior-art-ideas-and-license.md),
[`53-repomix-prior-art-ideas-and-license.md`](53-repomix-prior-art-ideas-and-license.md),
and [`54-headroom-native-context-compression.md`](54-headroom-native-context-compression.md).

Verification date for LICENSE files: **2026-07-25** (DeusData, Repomix, and Headroom
re-verified from upstream `LICENSE` / GitHub `main`).

---

## colbymchenry/codegraph

- Repository: https://github.com/colbymchenry/codegraph
- License: MIT
- Copyright: Copyright (c) 2026 Colby Mchenry
- Astloom use: ideas (explore packing, framework routes, MCP UX); no vendored source as of this notice

```text
MIT License

Copyright (c) 2026 Colby Mchenry

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## tirth8205/code-review-graph

- Repository: https://github.com/tirth8205/code-review-graph
- License: MIT
- Copyright: Copyright (c) 2026 Tirth Kanani
- Astloom use: ideas (flows, risk scoring, communities, TESTED_BY, hybrid search); no vendored source as of this notice

```text
MIT License

Copyright (c) 2026 Tirth Kanani

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Graphify-Labs/graphify

- Repository: https://github.com/Graphify-Labs/graphify
- License: MIT
- Copyright: Copyright (c) 2026 Safi Shamsi
- Astloom use: ideas (edge confidence UX, god/surprise nodes, path queries, rationale); no vendored source as of this notice

```text
MIT License

Copyright (c) 2026 Safi Shamsi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## DeusData/codebase-memory-mcp

- Repository: https://github.com/DeusData/codebase-memory-mcp
- Paper: https://arxiv.org/abs/2603.27277
- License: MIT
- Copyright: Copyright (c) 2025 DeusData
- Verified commit: `97ce23f9827177fff3858831156e9795c6832b18` (2026-07-25)
- Astloom use: **ideas only** (structural MCP UX, HTTP_CALLS / escalate hybrid,
  coverage-before-absence, compact payloads). Clean-room on Neo4j per docs `44`–`47`.
  **Do not** vendor the C binary, Hybrid LSP C sources, or tree-sitter grammar tree
  unless a future ADR + SBOM explicitly approve MIT redistribution.

```text
MIT License

Copyright (c) 2025 DeusData

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## yamadashy/repomix

- Repository: https://github.com/yamadashy/repomix
- License: MIT
- Copyright: Copyright 2024 Kazuki Yamada
- Verified commit: `f0968929bc1cfd8aee61b89682b95e684d6e2c27` (2026-07-25)
- Astloom use: **ideas only** (AI-oriented packs, token budget gates, layered ignore,
  Tree-sitter compress patterns, secret-scan-before-export). Clean-room preferred.
  **Do not** vendor the npm CLI/runtime unless ADR + SBOM approve. Do not use hosted
  remote packing for private Astloom trees (no-cloud-exfiltration).

```text
MIT License

Copyright 2024 Kazuki Yamada

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## headroomlabs-ai/headroom

- Repository: https://github.com/headroomlabs-ai/headroom
- License: Apache License 2.0
- Copyright: Copyright 2025 Headroom Contributors
- Verified commit: `a6d4921e82c1e9fe1a5ca8b90ffd16aa84a698d4` (2026-07-25)
- Astloom use: **Native product requirement** — Astloom software must implement a
  local-first context-compression lane inspired by Headroom (see doc `54`). Prefer
  clean-room on LiteLLM + MCP gateway seams. **Do not** treat separate IDE/dev stacks
  (for example `ai-toolstack`) as the Astloom product SoT. If the `headroom-ai`
  package or upstream source is redistributed: ship Apache 2.0 LICENSE + NOTICE and
  mark modifications per Apache 2.0 §§4(a)–(d).

```text
Copyright 2025 Headroom Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

Full Apache License 2.0 text: https://www.apache.org/licenses/LICENSE-2.0

---

## Runtime Python packages (retrieval stack)

These are **dependencies**, not prior-art idea sources. Keep versions pinned in
`pyproject.toml`.

### turbovec

- Package: `turbovec` (optional extra `astloom[turbovec]`)
- Upstream: https://github.com/RyanCodrai/turbovec
- License: confirm on each release pin (see package metadata / upstream LICENSE)
- Role: Optional in-process Stage-2 ANN replica (`IdMapIndex` only) behind
  `VectorIndexPort`. PostgreSQL + pgvector remains durable embedding SoR.
  Enable with `ASTLOOM_RAG_ANN_ACCELERATOR=turbovec` after
  `python -m vector_index.promotion_gate`.

### rank-bm25

- Package: `rank-bm25`
- License: Apache License 2.0
- Role: Optional Okapi BM25 accelerator for larger in-process corpora
  (`domain/hybrid_search.py`). Lucene-style BM25 remains the small-corpus path.

### scikit-network

- Package: `scikit-network` (optional extra `graph-analytics`)
- License: BSD
- Role: Leiden community detection when installed; Louvain fallback otherwise.
  Astloom does not call Neo4j GDS for communities (portability). GDS Community
  Edition can run algorithms without an Enterprise key — see doc `32`.

---

## Maintenance

When adding a vendored dependency or copying substantial upstream source:

1. Update this file with the exact commit/tag and copyright year from upstream.
2. Ensure redistributed artifacts include the MIT notices.
3. Record an ADR acceptance for the vendoring decision.
4. Update SBOM generation inputs used by release pipelines.

## Related Documents

- [`21-code-intelligence-prior-art-ideas-and-license.md`](21-code-intelligence-prior-art-ideas-and-license.md)
- [`53-repomix-prior-art-ideas-and-license.md`](53-repomix-prior-art-ideas-and-license.md)
- [`54-headroom-native-context-compression.md`](54-headroom-native-context-compression.md)
- [`44-codebase-memory-neo4j-hybrid-feature-specification.md`](44-codebase-memory-neo4j-hybrid-feature-specification.md)
