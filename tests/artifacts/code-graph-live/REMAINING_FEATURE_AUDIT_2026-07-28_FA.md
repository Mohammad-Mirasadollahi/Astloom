# گزارش Audit تکمیلی قابلیت‌های Astloom

تاریخ: ۲۰۲۶-۰۷-۲۸  
نوع بررسی: فقط Audit، بدون تغییر کد، تنظیمات، migration یا restart سرویس

## نتیجه اجرایی

نرم‌افزار در سطح تست‌های کوچک و سناریوهای ایزوله پوشش گسترده‌ای دارد، اما در وضعیت
فعلی نمی‌توان ادعا کرد «همه قابلیت‌ها بدون باگ و دقیقاً مطابق مستندات کار می‌کنند».
چهار مانع اصلی برای چنین تأییدی وجود دارد:

1. مسیر HTTP سرویس MCP با یک درخواست CPU-bound قفل شده و health endpoint نیز پاسخ
   نمی‌دهد.
2. CALLS graph در داده واقعی monorepo، edgeهای اشتباه با confidence بالا تولید
   می‌کند و همین خطا وارد impact، call path، community و generation context می‌شود.
3. تنها ۱۳۰ مورد از ۲۷۵۴ symbol واجد شرایط embedding دارند؛ در نتیجه semantic
   retrieval طبیعی، به‌خصوص query فارسی، کیفیت ضعیفی دارد.
4. freshness مقدار `pending_count=0` گزارش می‌کند، در حالی که inventory همان لحظه
   ۳۲ فایل کد ویرایش‌شده را تشخیص می‌دهد.

بنابراین verdict نهایی این Audit: **پوشش تست زیاد است، ولی correctness و availability
در چند مسیر اصلی هنوز قابل قبول نیست.**

## دامنه و روش

- معیار پذیرش از مستندات جاری `docs/07-code-knowledge-graph`، README سرویس‌های
  code-graph، docs-sync و MCP استخراج شد.
- ۷۹۰ test ID جمع‌آوری شد:
  - code graph: ۳۹۳
  - docs sync: ۱۲
  - MCP gateway: ۳۷
  - CLI و packageها: ۳۴۸
- ۶۸۹ تست non-live اجرا شد.
- از ۱۰۱ تست live-named، تعداد ۹۹ مورد اجرا شد.
- رفتارهای اصلی روی PostgreSQL، Neo4j، local BGE، CLI و MCP واقعی یا in-process
  بررسی شد.
- هیچ سرویس، داده اصلی، فایل governance یا کد محصول به قصد Audit تغییر داده نشد.

## پوشش تست

| سطح | نتیجه | زمان | Peak RSS |
|---|---:|---:|---:|
| کل non-live | ۶۸۸ pass، ۱ failure وابسته به محیط، ۱۰۱ deselect | ۳۱.۹ ثانیه | حدود ۴۱۲ MB |
| همان تست failing به‌تنهایی | ۳ بار pass | — | — |
| کل فایل تست مربوط به failure | ۴۳/۴۳ pass | — | — |
| retrieval اصلی + challenge + fuzzer | ۱۰۹/۱۰۹ pass | ۵۴.۶۲ ثانیه | حدود ۱۳۰ MB |
| Docker persistence + parity + repair + tenant isolation | ۱۹/۱۹ pass | ۲۸.۹۶ ثانیه | حدود ۱۴۶ MB |
| parallel/RPM sync | ۱۲/۱۲ pass | ۶۷.۶۷ ثانیه | حدود ۱.۶۷ GiB |
| MCP docs drift/generation، read-only | ۴ pass، ۱ safety deselect | ۵۱.۸۲ ثانیه | حدود ۴۰۶ MB |
| CLI docs-link + progress | ۲/۲ pass | ۱۳.۹۴ ثانیه | حدود ۲۷۷ MB |

در مجموع ۷۸۸ شناسه از ۷۹۰ شناسه واقعاً اجرا شدند. هر ۷۸۸ مورد حداقل یک بار pass
شدند، اما اجرای aggregate به علت یک ایراد isolation در test suite کاملاً سبز نبود.

### دو تست Live اجرا‌نشده

1. تست unknown-symbol در docs drift، روی project scope اصلی symbol و finding جدید
   می‌نویسد.
2. تست approval/weight فایل
   `.astloom/weight-profile-governance.json` را به‌شکل سراسری حذف و بازنویسی
   می‌کند.

اجرا نکردن این دو مورد تصمیم ایمنی در Audit read-only است. رفتارهای زیرین با unit
test پوشش دارند، ولی مسیر Live آن‌ها در وضعیت فعلی ایزوله نیست؛ این خود یک شکاف
تست محسوب می‌شود.

## یافته‌های محصول

### AC-AUDIT-01 — Critical — قفل شدن کامل مسیر HTTP سرویس MCP

وضعیت نهایی process:

- PID: `2768453`
- state: `Rsl`
- elapsed: بیش از ۵۶ دقیقه
- CPU: حدود ۹۴.۹٪
- RSS: حدود ۲٬۲۱۱٬۴۰۸ KiB
- thread count: ۳
- port: `32500` با `Recv-Q=59`
- `GET /health`: timeout بعد از ۵ ثانیه، بدون دریافت حتی یک byte

در همان زمان، ping/profile/guidance با همان gateway در حالت in-process و memory در
حدود ۱۴ میلی‌ثانیه تمام شدند. بنابراین مشکل به خود قرارداد ابزارها محدود نیست؛ مسیر
HTTP قادر نیست کار سنگین synchronous را از event loop جدا کند.

در `http_app.py` endpoint به‌صورت async تعریف شده، ولی در خطوط ۹۴ و ۱۰۸
`handle_message` مستقیماً و synchronous اجرا می‌شود. یک tool CPU-bound تمام event
loop، batchهای بعدی و حتی health را متوقف می‌کند. این رفتار با ادعای README درباره
پشتیبانی از concurrent agents سازگار نیست.

سرویس restart نشد، چون دامنه این درخواست Audit-only بود.

### AC-AUDIT-02 — High — CALLS اشتباه با confidence=`exact`

نمونه واقعی:

`DocsSyncService.detect_drift` به
`shared_kernel.time.FakeClock.set` با confidence=`exact` متصل شده است.

منبع call در واقع builtin پایتون، یعنی `set(symbol_ids)` است. resolver ابتدا نام
کوتاه `set` را در symbolهای پروژه پیدا می‌کند و وقتی فقط یک match دارد آن را exact
اعلام می‌کند؛ تشخیص builtin/external فقط بعد از شکست resolution پروژه اجرا می‌شود.

پیامد مشاهده‌شده:

- خروجی impact با فیلتر exact/probable شامل `FakeClock.set` اشتباه بود.
- call path حدود ۳۰ node برگرداند که بخش عمده آن‌ها به‌خاطر نام‌های عمومی مشترک
  مانند `idempotent`، `remember`، `list_symbols` و `now` نامرتبط بودند.
- generation context و AST neighbors نیز symbolهای نامرتبط از سرویس‌های دیگر را
  وارد context کردند.
- community مربوط به symbol مورد بررسی ۴۱۴ عضو داشت و بسیار کم‌تمرکز بود.

این یافته با هدف مستند ۱۵، یعنی جلوگیری از آلوده شدن blast radius توسط CALLS
اشتباه با confidence بالا، ناسازگار است. accuracy corpus فعلی چهار فایل کوچک دارد
و collisionهای یک monorepo واقعی یا builtin shadowing را پوشش نمی‌دهد.

### AC-AUDIT-03 — High — semantic index فقط ۴.۷٪ کامل است

inventory واقعی:

- eligible symbols: ۲۷۵۴
- indexed embeddings: ۱۳۰
- missing embeddings: ۲۶۲۴
- coverage: ۴.۷٪

در همان inventory، code sync برابر ۹۲.۲٪ و docs sync برابر ۹۴.۲٪ گزارش می‌شود.
در نتیجه درصدهای کلی می‌توانند تصور نادرستی از آمادگی semantic retrieval بدهند.

کیفیت واقعی:

- query انگلیسی طبیعی درباره validation frontmatter و drift در ۱۶.۴۴ ثانیه پاسخ
  داد، ولی methodهای اصلی docs-sync در پنج نتیجه اول نبودند.
- query فارسی معادل در ۱۷.۷۴ ثانیه پاسخ داد و نتیجه پنجم
  `PostgresStore.put_draft` بود؛ methodهای مورد انتظار در پنج نتیجه اول نبودند.
- query دقیق شامل نام service و method خوب عمل کرد:
  `validate_frontmatter` رتبه ۱ و `detect_drift` رتبه ۳.

پس exact/lexical lookup سالم است، اما کیفیت semantic و query فارسی در داده واقعی
با انتظار یک knowledge graph کامل هم‌سطح نیست.

### AC-AUDIT-04 — High — freshness به‌شکل نادرست وضعیت clean نشان می‌دهد

در یک snapshot واحد:

- inventory: تعداد ۳۲ فایل کد edited
- graph freshness: `pending_count=0`
- stale banner/footer: `null`
- structural impact/call-path/community: freshness=`ok`

freshness فعلی عمدتاً به mark/clearهای in-process وابسته است و تغییرات واقعی workspace
را با inventory تطبیق نمی‌دهد. در نتیجه ابزار structural ممکن است روی graph قدیمی
کار کند، ولی نبود stale state را القا کند.

### AC-AUDIT-05 — High — quality debt واقعی و پنهان‌شده زیر درصدهای کلی

اجرای quality audit:

- زمان: ۱۴.۶۳ ثانیه
- exit code: ۱، مطابق قرارداد وجود finding
- ۲۳۲ finding با severity=`high`
  - ۲۰۰ مورد `code.missing_embeddings`؛ لیست در سقف نمایش ۲۰۰ محدود شده است.
  - ۳۲ مورد `code.stale_edited`

این Audit طبق درخواست کاربر هیچ remediation یا task durable ایجاد نکرد.

## شکاف‌های Test/QA

### AC-AUDIT-06 — Medium — تست launch به محیط واقعی وابسته است

`test_start_mcp_http_refuses_when_port_still_busy` در اجرای aggregate failure داد،
ولی:

- سه بار به‌تنهایی pass شد.
- کل فایل آن ۴۳/۴۳ pass شد.

علت: تست `subprocess.Popen` را global monkeypatch می‌کند. وقتی port واقعی ۳۲۵۰۰
قابل دسترس است، probe داخلی `ss` برای کشف PID نیز از همان mock عبور می‌کند و به
اشتباه launch سرویس شمرده می‌شود. در sandbox که port دیده نمی‌شود این branch اجرا
نمی‌شود. این failure مشکل isolation تست است، نه اثبات شکست رفتار launch محصول.

### AC-AUDIT-07 — Medium — دو تست Live ایزوله و read-only نیستند

تست‌های docs drift unknown و approval/weight به main/global state می‌نویسند. این
موضوع مانع اجرای کامل safe audit می‌شود و باید با tenant/project/temp config مستقل
بازطراحی شود.

### AC-AUDIT-08 — Low — ناسازگاری متن سند زبان‌ها

جدول سند language support شش زبان را فهرست می‌کند، ولی متن acceptance همان سند از
«پنج زبان بالا» صحبت می‌کند. unit testهای parser/cross-language برای زبان‌های
مستندشده وجود دارند، اما معیار پذیرش متنی باید یکدست شود.

## قابلیت‌هایی که مطابق مستندات عمل کردند

### Context compression

- حجم JSON اولیه: ۱۱٬۰۶۰ character
- حجم compressed: ۲٬۰۳۴ character
- صرفه‌جویی: ۹٬۰۲۶ character، معادل ۸۱.۶۱٪
- mode: lossy با ثبت `list_truncated`
- retrieve با handle: round-trip دقیقاً برابر ورودی
- stats و process-local isolation صحیح

### Repo Pack

دو فایل واقعی با مجموع ۳۳٬۴۹۵ character بررسی شد:

- estimated tokens: ۸٬۳۷۴
- بودجه ۲۰٬۰۰۰: pass، exit 0
- بودجه ۱۰: fail-closed، exit 2 و
  `token_budget_exceeded:8374>10`
- hotspotها درست گزارش شدند.
- secret finding برای این دو فایل صفر بود.

### LSP optional fallback

هیچ‌کدام از `pyright-langserver`، `pylsp`,
`typescript-language-server`، `gopls` یا `rust-analyzer` روی host در دسترس نبود.
ابزارهای definition/references مطابق سند، به‌جای خروجی خالی مبهم، پاسخ structured
با `available=false`، detail واضح و locations خالی دادند.

مسیر موفق LSP واقعی به‌دلیل نبود language server قابل Audit Live نبود؛ mock
JSON-RPC، rename و reconcile در unit testها pass شدند. rename واقعی اجرا نشد چون
write است.

### Documentation standards و catalog

- standards: ۳۱۱/۳۱۱ conforming
- nonconforming: صفر
- revision debt: صفر
- زمان: ۲.۴۶ ثانیه
- docs catalog با query `structural-isolation` سند ۵۵ را دقیقاً پیدا کرد.

### Generation context

برای `DocsSyncService.detect_drift` موارد زیر درست بودند:

- full repository استفاده نشد.
- لایه‌های human، living، rationale و AST حاضر بودند.
- human layer ترجیح داده شد.
- gap گزارش نشد.
- edge اختراع‌شده گزارش نشد.
- polyglot summary حاضر بود.

ضعف این قابلیت نه در قرارداد context، بلکه در AST neighborهای آلوده به CALLS
اشتباه است.

### Structural residuals

شرط صریح سند ۵۵ درباره حذف نویز `testing.py` و `__init__` از hotspotهای برتر pass
شد. با این حال hubهای عمومی و sample `main` با degree بالا نشان می‌دهند کیفیت کلی
structural graph هنوز تحت تأثیر collision نام‌هاست.

## عملکرد

| عملیات واقعی | زمان | Peak RSS / مشاهده |
|---|---:|---:|
| inventory | ۱۲.۵ ثانیه | حدود ۳۳۹ MB |
| quality audit | ۱۴.۶۳ ثانیه | حدود ۳۳۹ MB |
| semantic query انگلیسی | ۱۶.۴۴ ثانیه | حدود ۱.۶۳ GiB |
| semantic query فارسی | ۱۷.۷۴ ثانیه | حدود ۱.۶۴ GiB |
| exact-symbol query | ۱۷.۴ ثانیه | حدود ۱.۶۴ GiB |
| impact | ۹.۱ ثانیه | — |
| call path | ۸.۹۳ ثانیه | — |
| community | ۱۱.۳۳ ثانیه | — |
| architecture overview | ۱۰.۳۳ ثانیه | — |
| detect changes | ۱۶.۶۵ ثانیه | — |
| parallel/RPM live suite | ۶۷.۶۷ ثانیه | حدود ۱.۶۷ GiB |

مصرف ۱.۶ تا ۱.۷ GiB در مسیر local BGE و زمان cold query حدود ۱۷ ثانیه برای
interactive coding سنگین است. صحت اجرای cache/concurrency در تست‌ها تأیید شد، ولی
SLO صریح برای latency و memory در مستندات وجود ندارد؛ بنابراین این مورد به‌عنوان
ریسک عملکرد ثبت می‌شود، نه failure قطعی acceptance.

## موارد خارج از دامنه قابلیت جاری

مواردی که خود مستندات lifecycle آن‌ها را future/deferred اعلام کرده‌اند، به‌عنوان
شکست محصول جاری حساب نشدند:

- Repository Code Wiki، اسناد ۱۴ تا ۱۸ و ۲۰
- wiki + graph، سند ۴۳
- client watcher UI، سند ۵۱

همچنین موفقیت واقعی LSP بدون نصب language server اختیاری قابل سنجش نبود.

## وضعیت عدم تغییر

- پیش از این Audit، workspace از دور قبلی دارای تغییرات tracked/untracked بود.
- در این Audit هیچ فایل source، test source، config یا migration ویرایش نشد.
- اجرای evaluationها پنج فایل `tests/artifacts/code-graph-eval/*-latest*` را طبق
  رفتار خود تست به‌روزرسانی و artifactهای timestamped تولید کرد.
- این فایل گزارش تنها artifact دستی جدید این دور است.
- probe تشخیصی موقت حذف شد و در پایان وجود نداشت.
- سرویس MCP restart یا terminate نشد و در همان حالت مشاهده‌شده باقی ماند.

## جمع‌بندی اولویت

1. رفع starvation مسیر HTTP MCP و افزودن test واقعی concurrent health/tool.
2. جلوگیری از resolve شدن builtinها و نام‌های کوتاه عمومی به edge exact.
3. rebuild کامل embeddingها و افزودن معیار retrieval برای query طبیعی و فارسی.
4. اتصال freshness به واقعیت workspace/inventory یا نمایش صریح «وضعیت نامعلوم».
5. ایزوله کردن سه test ناسالم: port/Popen، docs unknown write و global governance.

تا پیش از رفع و retest این پنج محور، اعلام «نبود باگ» یا «انطباق کامل خروجی با
مستندات» از نظر این Audit قابل دفاع نیست.
