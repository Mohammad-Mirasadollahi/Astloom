"""Framework DI / injection binding extraction (GAP-002).

Detects Depends / constructor-injection / Spring / Wire patterns and returns
consumer→provider bindings for ingest to emit CALLS edges with
``provenance=di_injection``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# FastAPI / Starlette: Depends(provider) or Annotated[..., Depends(provider)]
_PY_DEPENDS = re.compile(
    r"Depends\(\s*(?P<provider>[A-Za-z_][\w.]*)\s*\)",
    re.MULTILINE,
)

# NestJS / TS: constructor(private readonly foo: FooService)
_TS_CTOR_PARAM = re.compile(
    r"constructor\s*\((?P<body>[^)]*)\)",
    re.MULTILINE | re.DOTALL,
)
_TS_PARAM_TYPE = re.compile(
    r"(?:private|public|protected|readonly|\s)+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[A-Za-z_][\w.]*)",
)

# Nest @Inject(TOKEN) on a parameter — capture token identifier
_TS_INJECT = re.compile(
    r"@Inject\(\s*[\"']?(?P<token>[A-Za-z_][\w.]*)[\"']?\s*\)",
    re.MULTILINE,
)

# Nearest preceding def/class for Python Depends sites
_PY_DEF_OR_CLASS = re.compile(
    r"^(?:async\s+)?(?:def|class)\s+(?P<name>[A-Za-z_]\w*)\s*[\(:]",
    re.MULTILINE,
)

# Spring: @Autowired field/ctor/method; javax/jakarta @Inject
_JAVA_AUTOWIRED_FIELD = re.compile(
    r"@Autowired\b(?:\([^)]*\))?\s*"
    r"(?:private|protected|public)?\s*(?:final\s+)?"
    r"(?P<type>[A-Za-z_][\w.]*)\s+(?P<field>[A-Za-z_]\w*)\s*[;=]",
    re.MULTILINE,
)
_JAVA_CTOR = re.compile(
    r"(?:public|protected|private)\s+(?P<class>[A-Za-z_]\w*)\s*\((?P<body>[^)]*)\)\s*\{",
    re.MULTILINE | re.DOTALL,
)
_JAVA_CTOR_DI_ANNOTATION = re.compile(r"@(?:Autowired|Inject)\b")
_JAVA_PARAM = re.compile(
    r"(?:final\s+)?(?P<type>[A-Za-z_][\w.]*)\s+(?P<name>[A-Za-z_]\w*)\s*(?:,|$)",
)
_JAVA_INJECT = re.compile(
    r"@(?:javax\.inject\.|jakarta\.inject\.)?Inject\b(?:\([^)]*\))?\s*"
    r"(?:private|protected|public)?\s*(?:final\s+)?"
    r"(?P<type>[A-Za-z_][\w.]*)\s+(?P<field>[A-Za-z_]\w*)\s*[;=]",
    re.MULTILINE,
)

# Google Wire: wire.Build(NewFoo, NewBar) / wire.NewSet(...)
_GO_WIRE_BUILD = re.compile(
    r"wire\.(?:Build|NewSet)\s*\((?P<body>[^)]*)\)",
    re.MULTILINE | re.DOTALL,
)
_GO_IDENT = re.compile(r"\b([A-Za-z_][\w.]*)\b")


@dataclass(frozen=True)
class ExtractedInjection:
    consumer_name: str
    provider_name: str
    framework: str
    pattern: str
    line_hint: int = 0


def extract_injections(
    source: str, *, language: str, file_path: str = ""
) -> list[ExtractedInjection]:
    """Extract DI bindings from a source file (deterministic, no LLM)."""
    _ = file_path
    lang = (language or "").lower().strip()
    if lang in {"python", "py"}:
        return _extract_python(source)
    if lang in {"javascript", "js", "typescript", "ts", "tsx", "jsx"}:
        return _extract_typescript(source)
    if lang in {"java"}:
        return _extract_java(source)
    if lang in {"go"}:
        return _extract_go_wire(source)
    return []


def _extract_python(source: str) -> list[ExtractedInjection]:
    out: list[ExtractedInjection] = []
    for match in _PY_DEPENDS.finditer(source):
        provider = match.group("provider").split(".")[-1]
        consumer = _nearest_def_or_class(source, match.start()) or "__module__"
        line_hint = source[: match.start()].count("\n") + 1
        out.append(
            ExtractedInjection(
                consumer_name=consumer,
                provider_name=provider,
                framework="fastapi",
                pattern="Depends",
                line_hint=line_hint,
            )
        )
    return out


def _extract_typescript(source: str) -> list[ExtractedInjection]:
    out: list[ExtractedInjection] = []
    class_names = [
        m.group("name")
        for m in re.finditer(r"class\s+(?P<name>[A-Za-z_]\w*)", source)
    ]
    default_consumer = class_names[-1] if class_names else "__module__"

    for match in _TS_CTOR_PARAM.finditer(source):
        body = match.group("body")
        consumer = _nearest_class_before(source, match.start()) or default_consumer
        line_hint = source[: match.start()].count("\n") + 1
        for param in _TS_PARAM_TYPE.finditer(body):
            provider = param.group("type").split(".")[-1]
            out.append(
                ExtractedInjection(
                    consumer_name=consumer,
                    provider_name=provider,
                    framework="nestjs_or_ts",
                    pattern="constructor_type",
                    line_hint=line_hint,
                )
            )

    for match in _TS_INJECT.finditer(source):
        token = match.group("token").split(".")[-1]
        consumer = _nearest_class_before(source, match.start()) or default_consumer
        line_hint = source[: match.start()].count("\n") + 1
        out.append(
            ExtractedInjection(
                consumer_name=consumer,
                provider_name=token,
                framework="nestjs",
                pattern="Inject",
                line_hint=line_hint,
            )
        )
    return out


def _extract_java(source: str) -> list[ExtractedInjection]:
    out: list[ExtractedInjection] = []
    for match in _JAVA_AUTOWIRED_FIELD.finditer(source):
        provider = match.group("type").split(".")[-1]
        consumer = _nearest_java_type(source, match.start()) or "__module__"
        out.append(
            ExtractedInjection(
                consumer_name=consumer,
                provider_name=provider,
                framework="spring",
                pattern="Autowired",
                line_hint=source[: match.start()].count("\n") + 1,
            )
        )
    for match in _JAVA_INJECT.finditer(source):
        provider = match.group("type").split(".")[-1]
        consumer = _nearest_java_type(source, match.start()) or "__module__"
        out.append(
            ExtractedInjection(
                consumer_name=consumer,
                provider_name=provider,
                framework="spring",
                pattern="Inject",
                line_hint=source[: match.start()].count("\n") + 1,
            )
        )
    for match in _JAVA_CTOR.finditer(source):
        consumer = match.group("class")
        # Skip if this looks like a method (return type present before name) — ctor name == class.
        if not _is_likely_java_type(source, consumer):
            continue
        # Require @Autowired/@Inject on the constructor to avoid plain POJO false positives.
        prefix = source[max(0, match.start() - 120) : match.start()]
        if not _JAVA_CTOR_DI_ANNOTATION.search(prefix):
            continue
        line_hint = source[: match.start()].count("\n") + 1
        for param in _JAVA_PARAM.finditer(match.group("body")):
            provider = param.group("type").split(".")[-1]
            if provider in {"String", "int", "long", "boolean", "Integer", "Long", "Boolean"}:
                continue
            out.append(
                ExtractedInjection(
                    consumer_name=consumer,
                    provider_name=provider,
                    framework="spring",
                    pattern="constructor_injection",
                    line_hint=line_hint,
                )
            )
    return out


def _extract_go_wire(source: str) -> list[ExtractedInjection]:
    out: list[ExtractedInjection] = []
    if "wire." not in source:
        return out
    for match in _GO_WIRE_BUILD.finditer(source):
        body = match.group("body")
        line_hint = source[: match.start()].count("\n") + 1
        providers = [
            m.group(1).split(".")[-1]
            for m in _GO_IDENT.finditer(body)
            if m.group(1) not in {"wire", "Build", "NewSet"}
        ]
        consumer = _nearest_go_func(source, match.start()) or "__module__"
        for provider in providers:
            out.append(
                ExtractedInjection(
                    consumer_name=consumer,
                    provider_name=provider,
                    framework="wire",
                    pattern="wire_build",
                    line_hint=line_hint,
                )
            )
    return out


def _nearest_def_or_class(source: str, pos: int) -> str | None:
    best: str | None = None
    best_start = -1
    for match in _PY_DEF_OR_CLASS.finditer(source):
        if match.start() <= pos and match.start() >= best_start:
            best = match.group("name")
            best_start = match.start()
    return best


def _nearest_class_before(source: str, pos: int) -> str | None:
    best: str | None = None
    best_start = -1
    for match in re.finditer(r"class\s+(?P<name>[A-Za-z_]\w*)", source):
        if match.start() <= pos and match.start() >= best_start:
            best = match.group("name")
            best_start = match.start()
    return best


def _nearest_java_type(source: str, pos: int) -> str | None:
    best: str | None = None
    best_start = -1
    for match in re.finditer(
        r"(?:class|interface|enum|record)\s+(?P<name>[A-Za-z_]\w*)",
        source,
    ):
        if match.start() <= pos and match.start() >= best_start:
            best = match.group("name")
            best_start = match.start()
    return best


def _is_likely_java_type(source: str, name: str) -> bool:
    return bool(
        re.search(
            rf"(?:class|interface|enum|record)\s+{re.escape(name)}\b",
            source,
        )
    )


def _nearest_go_func(source: str, pos: int) -> str | None:
    best: str | None = None
    best_start = -1
    for match in re.finditer(r"func\s+(?:\([^)]+\)\s+)?(?P<name>[A-Za-z_]\w*)\s*\(", source):
        if match.start() <= pos and match.start() >= best_start:
            best = match.group("name")
            best_start = match.start()
    return best
