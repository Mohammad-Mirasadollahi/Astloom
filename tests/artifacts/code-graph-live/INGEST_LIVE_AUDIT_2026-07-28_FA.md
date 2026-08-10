# گزارش جامع Audit زنده Ingest و Code Knowledge Graph

تاریخ اجرا: 2026-07-28  
محیط: `/opt/Astloom`، نسخه محصول `0.1.2`، contract `1`  
محدوده اصلی: Ingest، Code Graph، embedding/retrieval، Living/Human Docs، Freshness/Sync و MCP  
نوع فعالیت: فقط Audit؛ هیچ اصلاحی روی کد یا داده عملیاتی محصول انجام نشد.

## نتیجه مدیریتی

**نتیجه نهایی: Conditional Fail برای استفاده production بدون نظارت.**

هسته Ingest و parsing در سناریوهای واقعی خوب عمل می‌کند: پنج زبان پشتیبانی‌شده ingest شدند، symbolها و edgeهای اصلی ساخته شدند، Persian document سالم ماند، retrieval ترکیبی روی Scope سالم نتیجه باکیفیت داد، و authentication/tenant isolation در MCP درست بود.

با این حال چهار نقص برای اعتماد production تعیین‌کننده‌اند:

1. تغییر dimension در `PostgresEmbeddingIndex.ensure_schema()` جدول embedding مشترک را به‌صورت سراسری Drop می‌کند. یکی از تست‌های Live رسمی با `dims=16` همین مسیر را اجرا کرد و embedding تمام Scopeها، از جمله `mir/dev/astloom`، حذف شد.
2. سیستم این حذف را تشخیص نداد: inventory همچنان Code=100% و LLM docs=100% گزارش کرد، Quality Audit اخطار embedding نداد، no-op ingest آن را backfill نکرد، و challenge gate حتی در حالت `bm25` پاس شد.
3. docs-sync دو hash از domain متفاوت را مقایسه می‌کند؛ بنابراین anchorهای تازه همان لحظه `stale` می‌شوند و در incremental sync تکراری جمع می‌شوند.
4. Ingest کاملاً ناموفق، با 1/1 parse failure و صفر فایل ingest‌شده، همچنان exit code صفر و `ok=true` برمی‌گرداند.

امتیاز کل evidence-based: **68/100**. این امتیاز SLA نیست؛ جمع‌بندی وزنی کیفیت عملی مشاهده‌شده در همین Audit است.

## Scorecard

| بخش | امتیاز | وضعیت | دلیل کوتاه |
|---|---:|---|---|
| Bootstrap و dependency health | 82/100 | Pass | Doctor سالم؛ PostgreSQL و Neo4j healthy |
| Discovery و filtering فایل | 86/100 | Pass | include/exclude و invalid-file isolation درست |
| Parsing چندزبانه | 92/100 | Pass | Python، TypeScript، JavaScript، Go و Rust موفق |
| Symbol/edge extraction | 84/100 | Pass با نویز | exact edges درست؛ unresolved/external قابل مشاهده |
| Living documentation | 82/100 | Pass | living docs و rationale تولید و بازیابی شدند |
| Embedding persistence | 42/100 | Fail | مسیر schema می‌تواند تمام tenantها را پاک کند |
| Human docs و anchor/drift | 35/100 | Fail | همه anchorهای Live از لحظه ثبت stale بودند |
| Hybrid retrieval | 76/100 سالم / 45/100 فعلی | Partial | Scope تازه عالی؛ Scope اصلی semantic=0 |
| Graph intelligence | 78/100 | Partial | callers/community/context خوب؛ impact default پرنویز |
| Sync/freshness/idempotency | 72/100 | Partial | no-op درست؛ backfill و observability ضعیف |
| MCP auth و tenant isolation | 90/100 | Pass | 401 درست، scoped token و no-leak درست |
| Performance و progress visibility | 48/100 | Partial | cold start سنگین؛ incremental کندتر از full |
| Test isolation و release gates | 62/100 | Partial | 800 تست مستقل پاس؛ combined state leakage و semantic blind spot |
| Security hygiene | 72/100 | Partial | auth درست؛ bearer artifact با mode 0644 |

## داده Live

Fixture موقت عمداً این تنوع را داشت:

- `src/auth.py`: Python، سه تابع مرتبط با login/password.
- `src/client.ts`: TypeScript.
- `src/http_client.js`: JavaScript.
- `src/token.go`: Go.
- `src/policy.rs`: Rust.
- `docs/login.md`: متن ترکیبی فارسی/انگلیسی با دو `linked_symbols`.
- `negative/broken.py`: Python نامعتبر برای تست failure isolation.

Scope اصلی Fixture:

- tenant: `audit-live`
- workspace: `qa`
- project: `audit-multilang-docs`

Scopeهای جانبی:

- `audit-mixed-failure`
- `audit-failure-isolation`
- `ingest-semantic-fresh`
- `audit-isolation-empty`

## Audit مرحله‌به‌مرحله 0 تا 100

### مرحله 0 — Bootstrap و Runtime

وضعیت:

- `astloom doctor`: سالم.
- نسخه محصول: `0.1.2`.
- contract: `1`.
- PostgreSQL: healthy روی `32232`.
- Neo4j: healthy روی `32287`.
- MCP HTTP: health endpoint روی `32501` پاسخ صحیح داد.

یافته:

- `astloom service status` در visibility واقعی همزمان `Process stopped`، `Reachable yes` و exit code 1 برگرداند. این تناقض lifecycle روی workflow معمول `astloom sync` اثر گذاشت و sync اولیه را متوقف کرد.

### مرحله 1 — Inventory، Scope و Freshness اولیه

Scope فعال محصول:

- Code: `411/411` synced.
- Docs: `603/608` synced.
- LLM docs: `2754/2754` documented.
- Docs باقی‌مانده: 5.

Inventory این وضعیت را سالم نشان می‌دهد، اما embedding Scope اصلی صفر است. بنابراین inventory درباره semantic readiness تصویر کامل نمی‌دهد.

### مرحله 2 — Discovery و Filter

نتیجه:

- پنج source معتبر کشف شدند.
- `negative/broken.py` طبق exclude در sync کامل وارد مسیر اصلی نشد.
- در تست mixed، فایل نامعتبر کنار پنج فایل سالم قرار گرفت؛ پنج فایل سالم ingest شدند و failure همان فایل جدا گزارش شد.

کیفیت: خوب.

### مرحله 3 — Parsing چندزبانه

Full sync:

- 5 فایل source موفق.
- 12 symbol indexed.
- زبان‌ها: Python، TypeScript، JavaScript، Go و Rust.
- شمار فایل هر زبان: 1.
- شمار symbol: Python=4، هر زبان دیگر=1.

Failure isolation:

- mixed input: موفق.
- all-invalid input: parser failure دقیق بود، اما status نهایی اشتباه موفق اعلام شد.

### مرحله 4 — Symbol و Edge Projection

در Scope چندزبانه:

- `DOCUMENTED_BY`: 10
- `CONTAINS`: 7
- `CALLS exact`: 2
- `CALLS unresolved`: 5
- `CALLS external`: 2
- `HTTP_CALLS unresolved`: 1

دو CALLS داخلی اصلی درست resolve شدند:

- `src.auth.login → src.auth.check_password`
- `src.auth.login → src.auth.normalize_user`

نویز unresolved/external در fixture عمدتاً built-in، method call و endpoint حل‌نشده بود؛ وجودش در graph قابل توضیح است، اما نباید بدون confidence floor وارد blast radius پیش‌فرض شود.

### مرحله 5 — Living Docs و Rationale

نتیجه:

- Living docs برای symbolها ساخته و ذخیره شدند.
- Rationale layer فعال بود.
- generation context برای `src.auth.login` شامل این لایه‌ها بود:
  - human: 1
  - living: 2
  - rationale: 1
  - AST neighbors: 2
- preferred layer به‌درستی `human` انتخاب شد.

### مرحله 6 — Embedding

روی Scope تازه `ingest-semantic-fresh`:

- embeddingها با dimension=1024 و مدل `BAAI/bge-large-en-v1.5` ذخیره شدند.
- 9 embedding: documentation=5، function=4.
- hybrid channels: BM25=6، FTS=9، semantic=9.
- mode: `hybrid_rrf_fts_semantic_bm25`.

روی Scope چندزبانه:

- 15 embedding: documentation=8، function=7.
- مدل واقعی BGE و dimension=1024.

روی Scope اصلی `mir/dev/astloom` بعد از suite:

- embedding row count: **0**.
- hybrid query: BM25=10، FTS=10، semantic=0.
- mode: **bm25**.

Root cause:

- تست `test_postgres_embedding_index_live` index را با `dims=16` و `ensure_schema=True` می‌سازد.
- `ensure_schema()` در mismatch، جدول مشترک `code_graph.symbol_embeddings` را Drop و با dimension جدید دوباره ایجاد می‌کند.
- این عملیات scope-aware نیست و تمام tenant/workspace/projectها را حذف می‌کند.
- تست‌های بعدی جدول را به 1024 برگرداندند، اما داده‌های Scope اصلی بازسازی نشدند.

### مرحله 7 — Graph Persistence و Idempotency

Durable Neo4j ingest:

- 2 فایل، 7 symbol، 24 edge.
- 5 symbol مستندشده.

Re-ingest همان Scope:

- 0 symbol جدید.
- 0 edge جدید.
- 2 فایل skipped.
- mode مؤثر: no-op/idempotent.

نقص:

- وقتی graph موجود است ولی embeddingها حذف شده‌اند، no-op ingest embeddingهای مفقود را backfill نمی‌کند.

### مرحله 8 — Human Docs، Link و Anchor

نتیجه مثبت:

- سند فارسی UTF-8 بدون خرابی ذخیره و retrieve شد.
- دو linked symbol resolve شدند.
- `DOCUMENTED_BY` ساخته شد.
- generation context human doc را ترجیح داد.

نقص قطعی:

- `docs_link_sync` مقدار `graph_sym.hash_value` را به‌عنوان `recorded_hash` می‌فرستد.
- docs-sync آن را با `symbol.body_hash` مقایسه می‌کند.
- این دو hash از domain متفاوت‌اند.
- نتیجه Live: همه anchorها از لحظه ایجاد `stale`.
- بعد از incremental edit:
  - 2 symbol distinct
  - 3 anchor
  - 3 recorded hash distinct
  - status همه: `stale`
- anchor قدیمی prune نشد و anchor جدید اضافه شد.

Versioning:

- body سند تغییر کرد، اما document version همچنان `1` ماند.
- upsert، object جدید با version=1 را جایگزین می‌کند.

### مرحله 9 — Full، Incremental و No-op Sync

Full پنج‌فایلی:

- wall: 43.79s
- زمان داخلی گزارش‌شده: 26.0s
- peak RSS: حدود 1.791GB
- workers/embedding slots: 12/12

Incremental یک‌فایلی:

- یک فایل و یک symbol تغییرکرده.
- 4 symbol indexed.
- 13 edge بازنویسی‌شده.
- wall: 60.98s
- زمان داخلی: 43.7s
- peak RSS: حدود 1.754GB

No-op:

- wall: 19.05s
- زمان داخلی: 1.6s
- peak RSS: حدود 356MB

یافته‌ها:

- incremental یک‌فایلی از full پنج‌فایلی کندتر بود.
- progress در full حدود 16s و در incremental حدود 40s روی 0% ماند.
- ETA دقیق نبود.
- preflight اعلام کرد Docs change ندارد، ولی مرحله docs بعداً `changed=1` پیدا کرد.
- RPM session صفر بود، ولی `Tokens≈` نمایش داده شد؛ این تخمین ممکن است با مصرف واقعی cloud اشتباه گرفته شود.

### مرحله 10 — Retrieval

Persian query: `قوانین ورود و رمز عبور`

Scope سالم:

- human Persian doc رتبه اول.
- BM25=0.
- FTS=1.
- semantic=10 در MCP.
- mode کامل hybrid.
- warm persistent MCP: حدود 0.79s.

برداشت:

- semantic retrieval برای فارسی مفید و خروجی باکیفیت بود.
- tokenizer BM25 فارسی contribution نداد؛ بدون embedding کیفیت فارسی به‌شدت افت می‌کند.

Cold CLI:

- حدود 19 تا 22 ثانیه.
- peak RSS حدود 1.65GB.
- هزینه غالب مربوط به load مدل BGE است.

Scope اصلی بعد از حذف embedding:

- semantic=0.
- mode=bm25.
- top results هنوز lexical/FTS معقول بودند، اما semantic capability خاموش و بدون alert بود.

### مرحله 11 — Graph Intelligence

Callers:

- `check_password` یک caller درست داشت: `src.auth.login`.
- latency warm MCP: حدود 0.17s.

Community:

- algorithm: `scikit_network_leiden`.
- community شامل `login`، `check_password` و `normalize_user`.
- label: `check_password-cluster`.

Impact:

- default MCP: 6 نتیجه.
- فقط 2 نتیجه پروژه‌ای معتبر.
- 4 نتیجه noise: external/unresolved.
- با `min_confidence=probable`: دقیقاً همان 2 نتیجه معتبر.

Root cause:

- handler MCP نبود argument را به `None` تبدیل می‌کند.
- domain contract می‌گوید default باید `probable` باشد، اما `None` confidence floor را غیرفعال می‌کند.
- همین رفتار در callers handler نیز وجود دارد و روی graphهای دیگر می‌تواند نویز مشابه ایجاد کند.

Language profile:

- پنج زبان درست تشخیص داده شدند.
- profile: `polyglot_isolated`.
- cross-language edge: صفر، مطابق Fixture که ارتباط بین زبان‌ها نداشت.

Generation context:

- seed درست.
- 8 symbol.
- expansion: `apoc_or_store_expand`.
- human doc به‌درستی preferred.

### مرحله 12 — MCP، Authentication و Isolation

Protocol:

- MCP `2024-11-05`.
- server: `Astloom-Programming 1.3.1`.
- lazy facade فقط دو ابزار context-facing دارد: search و execute.

Authentication:

- request بدون token: 401.
- token منقضی: unauthorized.
- token تازه scope-bound: موفق.

Tenant isolation:

- همان query با token پروژه `audit-isolation-empty`: صفر نتیجه.
- هیچ leak از `audit-multilang-docs` مشاهده نشد.

Lazy discovery:

- query صریح hybrid، ابزار generic search را بالاتر از hybrid search رتبه داد.
- ابزار destructive purge هم در نتایج ظاهر شد.
- purge همچنان `confirm=true` می‌خواهد؛ مسئله اصلی ranking و safety UX است، نه bypass کنترل.

Security hygiene:

- `.astloom/mcp-http.secret`: mode 0600.
- `.astloom/tmp_mcp_bearer.txt`: mode 0644 و شامل token منقضی.
- token منقضی بود، اما artifact secret-like با permission عمومی‌تر از حد لازم است.

### مرحله 13 — Test Gates و Quality Metrics

تست‌های مستقل:

- Code Graph service: 389 passed در 150.48s.
- CLI: 344 passed در 35.96s.
- Docs Sync: 11 passed.
- MCP Gateway: 31 passed.
- MCP Live docs/generation: 5 passed در 52.88s.
- LLM routing/RPM: 20 passed.
- مجموع: **800 تست مستقل پاس**.

Combined run:

- 408 تست اجرا شد.
- 3 failure:
  - یک failure به‌دلیل software path موقت باقی‌مانده در process.
  - دو failure به‌دلیل environment/profile state leakage.
- هر سه تست وقتی مستقل اجرا شدند پاس شدند.

برداشت:

- correctness منفرد خوب است.
- isolation بین suiteها ضعیف است.
- combined order می‌تواند رفتار را تغییر دهد.

Quality metrics:

- call-graph corpus: 4 case، Precision=1.0، Recall=1.0، F1=1.0.
- threshold corpus: 0.7/0.7.
- retrieval nDCG@10: 0.8569؛ threshold=0.5.
- explore co-change F1: 1.0.
- change-risk co-change F1: 1.0.
- community same-rate: 1.0.
- challenge live: 50/50 pass.
- retrieval fuzzer: 50/50 pass.
- production retrieval live: 9 pass.

محدودیت متریک‌ها:

- call-graph corpus فقط 4 case دارد.
- co-change eval فقط 2 pair دارد.
- benefit proxy در sample هیچ صرفه‌جویی نشان نداد:
  - with explore: 1741 chars
  - naive source: 1062 chars
  - ratio: 1.6394
- challenge artifact همین اجرای جدید `hybrid_mode=bm25` داشت و باز هم pass شد؛ semantic availability جزو gate سخت نیست.

Quality Audit:

- قبل از Fixture: 0 finding.
- هنگام وجود Fixture موقت: فقط دو finding مربوط به frontmatter همان Fixture.
- missing embedding در Scope اصلی توسط Quality Audit گزارش نشد.

## یافته‌ها به ترتیب شدت

### Critical

#### C-01 — حذف سراسری embeddingها در mismatch dimension

اثر:

- تمام Scopeها/tenantها ممکن است semantic index خود را از دست بدهند.
- تست رسمی Live این رخداد را در دیتابیس مشترک Audit ایجاد کرد.

شاهد:

- `dims=16` در تست.
- `DROP_SYMBOL_EMBEDDINGS` در `ensure_schema()`.
- Scope اصلی بعد از suite: صفر embedding.

#### C-02 — Semantic degradation بدون alert و بدون self-healing

اثر:

- محصول ظاهراً healthy است ولی hybrid عملاً BM25 است.
- inventory و Quality Audit سبز می‌مانند.
- no-op ingest embedding را برنمی‌گرداند.
- challenge gate نیز در BM25-only پاس می‌شود.

### High

#### H-01 — Anchorها به‌علت hash-domain mismatch همیشه stale

اثر:

- drift signal غیرقابل اعتماد.
- coverage state اشتباه.
- anchorهای تکراری در incremental sync.

#### H-02 — All-invalid ingest موفق گزارش می‌شود

اثر:

- automation نمی‌تواند failure کامل ingest را از موفقیت تشخیص دهد.
- exit code و top-level status برای pipeline قابل اعتماد نیست.

#### H-03 — MCP impact/callers default confidence contract را دور می‌زند

اثر:

- blast radius با external/unresolved آلوده می‌شود.
- review و risk analysis می‌تواند بیش‌برآورد شود.

#### H-04 — Service lifecycle status متناقض

اثر:

- `stopped` و `Reachable yes` همزمان.
- فرمان sync معمول ممکن است به‌اشتباه متوقف شود.

#### H-05 — Test isolation و shared state

اثر:

- ترتیب اجرای suite نتیجه را تغییر می‌دهد.
- تست dimension مشترک داده tenantهای دیگر را حذف می‌کند.
- env/software-path leakage در combined run failure می‌سازد.

### Medium

#### M-01 — Document version روی update افزایش نمی‌یابد

#### M-02 — Incremental sync از full sync کندتر و progress برای مدت طولانی 0%

#### M-03 — Preflight docs inventory با مرحله اجرا ناسازگار

#### M-04 — Cold retrieval حدود 20s و 1.65GB RSS

#### M-05 — BM25 فارسی contribution صفر؛ وابستگی شدید به semantic

#### M-06 — Lazy tool ranking ابزار generic/destructive را نامتناسب بالا می‌آورد

#### M-07 — Bearer token artifact با mode 0644

#### M-08 — Benefit proxy در sample منفی است

#### M-09 — Neo4j driver در تست‌ها warning مربوط به explicit close داشت

### Low

#### L-01 — `Tokens≈` با RPM session=0 می‌تواند با مصرف واقعی اشتباه شود

#### L-02 — Short qualified name در generation-context resolve نمی‌شود

`require_login` شکست خورد، ولی `service.require_login` موفق بود. Contract باید نیاز به نام fully-qualified را روشن‌تر کند یا ambiguity را بهتر گزارش کند.

## رفتارهایی که درست کار کردند

- local/cloud boundary بدون consent fail-closed بود.
- BGE واقعی با backend آشکار استفاده شد.
- parse پنج زبان موفق بود.
- mixed failure isolation درست بود.
- Neo4j persistence و re-ingest idempotency درست بود.
- PostgreSQL pgvector روی Scope تازه semantic hits داشت.
- Persian UTF-8 سالم ماند.
- human documentation رتبه اول retrieval و preferred generation layer شد.
- exact CALLS، callers و community درست بودند.
- tenant isolation در Neo4j/PostgreSQL/MCP درست بود.
- unauthorized MCP request رد شد.
- no-op sync graph را بی‌دلیل بازنویسی نکرد.
- production challenge، fuzzer، retrieval و corpus gates مستقل پاس شدند.

## مواردی که عمداً Live mutation نشدند

به‌دلیل دستور «فقط Audit»:

- هیچ fix یا migration اجرا نشد.
- embedding Scope اصلی backfill نشد.
- purge روی Scope واقعی اجرا نشد.
- IDE rename روی فایل محصول اجرا نشد؛ contract آن فقط توسط تست‌های رسمی پوشش داده شد.
- cloud LLM route فعال نشد، چون consent خروج از private boundary داده نشده بود.
- مشکل anchor/version اصلاح نشد.

قابلیت‌های continuous per-save indexing و Wiki طبق اسناد محصول deferred هستند و به‌عنوان شکست قابلیت shipped محاسبه نشدند.

## معیار پذیرش پیشنهادی برای Production

این Audit توصیه اصلاحی اجرا نمی‌کند، اما برای تغییر verdict به Pass حداقل باید شواهد زیر وجود داشته باشد:

1. هیچ مسیر runtime/test نتواند جدول embedding مشترک را بدون migration کنترل‌شده Drop کند.
2. semantic row coverage به inventory، health و release gate اضافه شود.
3. no-op sync بتواند embedding missing/model-mismatch را detect و backfill کند.
4. anchor hash contract یک domain واحد داشته باشد و stale anchor قدیمی prune شود.
5. all-failed ingest exit non-zero و `ok=false` بدهد.
6. MCP default confidence با domain default یکسان شود.
7. combined suite بدون state/env leakage پاس شود.
8. progress/ETA و incremental latency budget قابل تکرار شود.

## Verdict نهایی

برای استفاده آزمایشی و interactive، subsystem ارزشمند و بخش عمده قابلیت‌ها عملی است. برای ingest production چندtenant و pipelineهای unattended، وضعیت فعلی قابل قبول نیست؛ چون یک مسیر schema/test می‌تواند semantic data همه Scopeها را حذف کند و سیستم هم این افت را نه اعلام می‌کند و نه خودکار بازسازی می‌کند.

## پیوست Remediation — 2026-07-28

پس از مجوز صریح برای Code Fix، موارد قابل‌اقدام این Audit اصلاح و دوباره تست شدند:

- schema mismatch دیگر جدول embedding را Drop نمی‌کند و با خطای operator-actionable متوقف می‌شود.
- no-op ingest، rowهای missing/model-mismatch را با `embedding_refresh` بازسازی و failure را آشکار می‌کند.
- inventory و quality-audit اکنون coverage واقعی embedding را می‌سنجند و مدل را حدس نمی‌زنند.
- invalid/partial ingest در CLI و MCP با `ok=false` و exit غیرصفر گزارش می‌شود.
- docs anchor از `body_hash` واحد استفاده می‌کند، duplicateها prune می‌شوند و version سند/anchor افزایش می‌یابد.
- default confidence در MCP روی `probable` تثبیت شد.
- lifecycle حالت reachable-without-pid را متناقض گزارش نمی‌کند و pid متعلق به همین checkout را recover می‌کند.
- tokenizer BM25 از فارسی و normalization حروف عربی/فارسی پشتیبانی می‌کند.
- lazy tool search ابزار hybrid صریح را بالاتر می‌آورد و purge بدون destructive intent نمایش نمی‌دهد.
- embedding refresh به batch encode مجهز شد.

شواهد بعد از fix:

- `129 passed` در regression suite متمرکز نهایی.
- `5 passed` در PostgreSQL/pgvector live regression.
- Live MCP: invalid ingest=`ok:false`، حذف عمدی یک row و no-op self-heal=`refreshed:1`.
- Live Persian retrieval: `bm25:1`، `semantic:4`، top hit=`good.login`.
- دو ری‌استارت موفق؛ وضعیت نهایی: PostgreSQL/Neo4j healthy و MCP managed/reachable.

داده‌ی قدیمی Scope اصلی که در Audit اولیه حذف شده بود اکنون به‌درستی به‌عنوان high finding دیده می‌شود. اجرای remediation BGE روی کل Scope اصلی آغاز و batch شد، اما به‌علت حجم ۱۵هزار symbol در پنجره تست کامل نشد؛ این یک repair داده‌ی موجود است، نه failure خاموش یا بازگشت bug حذف جدول.
