"""Package-manager manifest aliases for IMPORT resolution (GAP-002 / Phase F3).

Reads lightweight maps from pyproject.toml, go.mod, Cargo.toml, package.json,
and tsconfig paths so imports resolve to project file stems / module paths.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def load_package_aliases(root: str | Path) -> dict[str, str]:
    """Return import-prefix → path-stem (or module path) aliases for a repo root."""
    root_path = Path(root)
    aliases: dict[str, str] = {}
    if not root_path.is_dir():
        return aliases
    aliases.update(_from_pyproject(root_path / "pyproject.toml"))
    aliases.update(_from_go_mod(root_path / "go.mod"))
    aliases.update(_from_cargo_toml(root_path / "Cargo.toml"))
    aliases.update(_from_package_json(root_path / "package.json"))
    aliases.update(_from_tsconfig(root_path / "tsconfig.json"))
    # Nested tsconfig common in monorepos — shallow scan only.
    for child in sorted(root_path.glob("*/tsconfig.json"))[:8]:
        aliases.update(_from_tsconfig(child))
    return aliases


def rewrite_import(import_text: str, aliases: dict[str, str]) -> str:
    """Rewrite an import using the longest matching alias prefix."""
    raw = (import_text or "").strip().strip("\"'")
    if not raw or not aliases:
        return raw
    best = ""
    replacement = ""
    for prefix, target in aliases.items():
        if raw == prefix or raw.startswith(prefix + "/") or raw.startswith(prefix + "."):
            if len(prefix) > len(best):
                best = prefix
                replacement = target
    if not best:
        return raw
    rest = raw[len(best) :].lstrip("/.")
    if not rest:
        return replacement
    return f"{replacement}/{rest}".replace("\\", "/")


def _from_pyproject(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    name = _toml_string(text, "name")
    if not name:
        return {}
    pkg = name.replace("-", "_")
    return {name: pkg, pkg: pkg}


def _from_go_mod(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("module "):
            module = line.split(None, 1)[1].strip()
            if module:
                out[module] = module
        # replace example.com/old => ./local/pkg
        if line.startswith("replace "):
            parts = line[len("replace ") :].split("=>")
            if len(parts) == 2:
                left = parts[0].strip().split()[0]
                right = parts[1].strip().split()[0]
                if left and right:
                    # Map old module path to local relative stem when ./...
                    if right.startswith("./") or right.startswith("../"):
                        stem = Path(right).name or right
                        out[left] = stem
                    else:
                        out[left] = right
    return out


def _from_cargo_toml(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    name = _toml_string_in_section(text, "package", "name")
    if name:
        out[name] = name.replace("-", "_")
        out[name.replace("-", "_")] = name.replace("-", "_")
    # path = "crates/foo" dependencies
    for match in re.finditer(
        r'^([A-Za-z0-9_-]+)\s*=\s*\{[^}]*path\s*=\s*"([^"]+)"',
        text,
        re.MULTILINE,
    ):
        dep_name, dep_path = match.group(1), match.group(2)
        stem = Path(dep_path).name or dep_name
        out[dep_name] = stem
        out[dep_name.replace("-", "_")] = stem
    return out


def _from_package_json(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    name = str(data.get("name") or "").strip()
    if name:
        out[name] = name.lstrip("@").replace("/", ".")
    imports = data.get("imports")
    if isinstance(imports, dict):
        for key, value in imports.items():
            if not isinstance(key, str):
                continue
            target = (
                value
                if isinstance(value, str)
                else (value or {}).get("default")
                if isinstance(value, dict)
                else None
            )
            if isinstance(target, str) and target:
                clean_key = key.rstrip("*").rstrip("/")
                clean_target = target.replace("*", "").rstrip("/")
                stem = Path(clean_target).stem or clean_target
                out[clean_key] = stem
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for dep_name, spec in deps.items():
            if not isinstance(dep_name, str) or not isinstance(spec, str):
                continue
            if spec.startswith("file:") or spec.startswith("workspace:"):
                local = spec.split(":", 1)[1].strip()
                stem = Path(local).name or dep_name.lstrip("@").replace("/", ".")
                out[dep_name] = stem
    return out


def _from_tsconfig(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        # Strip // comments common in tsconfig
        raw = path.read_text(encoding="utf-8", errors="replace")
        raw = re.sub(r"//.*?$", "", raw, flags=re.MULTILINE)
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, str] = {}
    paths = (data.get("compilerOptions") or {}).get("paths")
    if not isinstance(paths, dict):
        return out
    for key, value in paths.items():
        if not isinstance(key, str):
            continue
        targets = value if isinstance(value, list) else [value]
        target = next((t for t in targets if isinstance(t, str) and t), None)
        if not target:
            continue
        clean_key = key.rstrip("*").rstrip("/")
        clean_target = target.replace("*", "").rstrip("/")
        # "@app/*" → "src/app" stem preference: last path segment
        stem = clean_target
        if "/" in clean_target:
            # Keep path-ish form for rewrite_import rest joining
            stem = clean_target.lstrip("./")
        out[clean_key] = stem
    return out


def _toml_string(text: str, key: str) -> str | None:
    pattern = re.compile(rf'^{re.escape(key)}\s*=\s*"([^"]+)"', re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _toml_string_in_section(text: str, section: str, key: str) -> str | None:
    section_re = re.compile(
        rf"^\[{re.escape(section)}\]\s*(.*?)(?=^\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = section_re.search(text)
    if not match:
        return _toml_string(text, key)
    return _toml_string(match.group(1), key)
