"""Unit tests for scripts/get-astloom.sh helpers and fetch paths."""

from __future__ import annotations

import os
import stat
import subprocess
import tarfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "get-astloom.sh"


def _source_helpers(snippet: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full = f"""
set -euo pipefail
GET_ASTLOOM_LIB_ONLY=1
# shellcheck disable=SC1091
source {SCRIPT.as_posix()!r}
{snippet}
"""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        ["bash", "-c", full],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_script_is_executable() -> None:
    assert SCRIPT.is_file()
    mode = SCRIPT.stat().st_mode
    assert mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_normalize_channel() -> None:
    proc = _source_helpers(
        "normalize_channel release; echo; "
        "normalize_channel stable; echo; "
        "normalize_channel main; echo; "
        "normalize_channel tip; echo; "
        "normalize_channel weird || echo bad"
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[:4] == ["release", "release", "main", "main"]
    assert "bad" in lines


def test_prompt_root_uses_default_without_tty_prompt() -> None:
    proc = _source_helpers(
        "prompt_root; echo; "
        "ASTLOOM_ROOT=/custom/ac prompt_root"
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[0] == "/opt/Astloom"
    assert lines[1] == "/custom/ac"


def test_preserve_paths_list() -> None:
    proc = _source_helpers("preserve_paths")
    assert proc.returncode == 0, proc.stderr
    text = proc.stdout
    assert ".astloom" in text
    assert ".env" in text
    assert "backend/deployments/compose/.env.local" in text


def test_sync_tree_preserving(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    root = tmp_path / "root"
    staging.mkdir()
    root.mkdir()
    (staging / "install.sh").write_text("#!/bin/bash\necho new\n", encoding="utf-8")
    (staging / "README.md").write_text("new tree\n", encoding="utf-8")
    (root / ".env").write_text("KEEP=1\n", encoding="utf-8")
    (root / ".astloom").mkdir()
    (root / ".astloom" / "install-state.env").write_text("role=server\n", encoding="utf-8")
    compose = root / "backend" / "deployments" / "compose"
    compose.mkdir(parents=True)
    (compose / ".env.local").write_text("SECRET=old\n", encoding="utf-8")
    (root / "old.txt").write_text("gone\n", encoding="utf-8")

    proc = _source_helpers(
        f'sync_tree_preserving {staging.as_posix()!r} {root.as_posix()!r}'
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert (root / "install.sh").is_file()
    assert (root / "README.md").read_text(encoding="utf-8") == "new tree\n"
    assert (root / ".env").read_text(encoding="utf-8") == "KEEP=1\n"
    assert (root / ".astloom" / "install-state.env").read_text(encoding="utf-8") == "role=server\n"
    assert (compose / ".env.local").read_text(encoding="utf-8") == "SECRET=old\n"
    assert not (root / "old.txt").exists()


def test_latest_release_tag_falls_back_to_git_tag(tmp_path: Path) -> None:
    fake_curl = tmp_path / "fake-curl"
    fake_curl.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            url=""
            for a in "$@"; do
              case "$a" in
                http*) url="$a" ;;
              esac
            done
            if [[ "$url" == *"/releases/latest"* ]]; then
              echo '{"message":"Not Found"}'
              exit 0
            fi
            if [[ "$url" == *"/tags"* ]]; then
              echo '[{"name":"v0.9.0"}]'
              exit 0
            fi
            echo '{}'
            """
        ),
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    proc = _source_helpers(
        "latest_release_tag",
        env={"ASTLOOM_CURL": str(fake_curl)},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "v0.9.0"


def test_latest_release_tag_parses_json(tmp_path: Path) -> None:
    fake_curl = tmp_path / "fake-curl"
    fake_curl.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            # Ignore args; emit fixture JSON for releases/latest
            echo '{"tag_name":"v9.9.9","name":"Astloom v9.9.9"}'
            """
        ),
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    proc = _source_helpers(
        "latest_release_tag",
        env={"ASTLOOM_CURL": str(fake_curl)},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "v9.9.9"


def test_fetch_release_into_with_stubbed_curl(tmp_path: Path) -> None:
    root = tmp_path / "opt" / "Astloom"
    root.mkdir(parents=True)
    (root / ".env").write_text("KEEP=yes\n", encoding="utf-8")
    (root / ".astloom").mkdir()
    (root / ".astloom" / "install-state.env").write_text("role=client\n", encoding="utf-8")

    # Build a tarball that looks like GitHub's repo-root/tag prefix folder.
    payload = tmp_path / "payload"
    inner = payload / "Mohammad-Mirasadollahi-Astloom-abc1234"
    inner.mkdir(parents=True)
    (inner / "install.sh").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
    (inner / "VERSION").write_text("from-release\n", encoding="utf-8")
    tar_path = tmp_path / "release.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(inner, arcname=inner.name)

    fake_curl = tmp_path / "fake-curl"
    fake_curl.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            out=""
            while [[ $# -gt 0 ]]; do
              case "$1" in
                -o)
                  out="$2"
                  shift 2
                  ;;
                *)
                  shift
                  ;;
              esac
            done
            if [[ -n "${{out}}" ]]; then
              cp {tar_path.as_posix()!r} "${{out}}"
            else
              echo '{{"tag_name":"v1.2.3"}}'
            fi
            """
        ),
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    proc = _source_helpers(
        f"fetch_release_into {root.as_posix()!r}",
        env={"ASTLOOM_CURL": str(fake_curl)},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert (root / "install.sh").is_file()
    assert (root / "VERSION").read_text(encoding="utf-8") == "from-release\n"
    assert (root / ".env").read_text(encoding="utf-8") == "KEEP=yes\n"
    assert (root / ".astloom" / "install-state.env").read_text(encoding="utf-8") == "role=client\n"
    assert (root / ".astloom" / "fetched-release-tag").read_text(encoding="utf-8").strip() == "v1.2.3"


def test_parse_and_run_passes_install_args(tmp_path: Path) -> None:
    """End-to-end dry: stub release fetch via pre-seeded root + skip install marker."""
    root = tmp_path / "Astloom"
    root.mkdir()
    (root / "install.sh").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'INSTALL_ARGS:%s\\n' "$*"
            """
        ),
        encoding="utf-8",
    )
    (root / "install.sh").chmod(0o755)

    # Patch fetch_release_into to no-op so we only test install argv pass-through.
    snippet = f"""
fetch_release_into() {{
  info "stub fetch_release_into $1"
}}
prompt_channel() {{ printf '%s\\n' release; }}
prompt_root() {{ printf '%s\\n' {root.as_posix()!r}; }}
parse_and_run --channel release --root {root.as_posix()!r} --yes --role server --runtime venv
"""
    proc = subprocess.run(
        ["bash", "-c", f"set -euo pipefail; GET_ASTLOOM_LIB_ONLY=1; source {SCRIPT.as_posix()!r}; {snippet}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "ASTLOOM_SKIP_INSTALL": "0"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    # --role implies --non-interactive; --yes kept (explicit) or added for unattended.
    assert "INSTALL_ARGS:--non-interactive --yes --role server --runtime venv" in proc.stdout


def test_run_install_interactive_does_not_force_yes(tmp_path: Path) -> None:
    """TTY bootstrap must still show install.sh 'type yes' confirmation."""
    root = tmp_path / "Astloom"
    root.mkdir()
    (root / "install.sh").write_text(
        "#!/usr/bin/env bash\nprintf 'INSTALL_ARGS:%s\\n' \"$*\"\n",
        encoding="utf-8",
    )
    (root / "install.sh").chmod(0o755)
    proc = _source_helpers(
        f"run_install {root.as_posix()!r}",
        env={"ASTLOOM_SKIP_INSTALL": "0"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "INSTALL_ARGS:" in proc.stdout
    assert "INSTALL_ARGS:--yes" not in proc.stdout
    # Empty argv after INSTALL_ARGS:
    assert proc.stdout.strip().endswith("INSTALL_ARGS:") or "INSTALL_ARGS:\n" in proc.stdout


def test_run_install_role_implies_noninteractive(tmp_path: Path) -> None:
    root = tmp_path / "Astloom"
    root.mkdir()
    (root / "install.sh").write_text(
        "#!/usr/bin/env bash\nprintf 'INSTALL_ARGS:%s\\n' \"$*\"\n",
        encoding="utf-8",
    )
    (root / "install.sh").chmod(0o755)
    proc = _source_helpers(
        f"run_install {root.as_posix()!r} --role client",
        env={"ASTLOOM_SKIP_INSTALL": "0"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "INSTALL_ARGS:--yes --non-interactive --role client" in proc.stdout


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def test_discard_generated_checkout_dirt_removes_egg_info(tmp_path: Path) -> None:
    """Untracked editable-install egg-info must be removed before channel sync."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("ok\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    egg = repo / "backend" / "packages" / "astloom.egg-info"
    egg.mkdir(parents=True)
    (egg / "PKG-INFO").write_text("Name: astloom\nVersion: dirty\n", encoding="utf-8")
    dirty = _git(repo, "status", "--porcelain", "-u")
    assert "egg-info" in dirty.stdout

    proc = _source_helpers(f"discard_generated_checkout_dirt {repo.as_posix()!r}")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert not egg.exists()
    clean = _git(repo, "status", "--porcelain", "-u")
    assert clean.stdout.strip() == ""


def test_sync_git_checkout_to_origin_discards_tracked_dirt(tmp_path: Path) -> None:
    """Main-channel update must converge despite dirty tracked docs (not only egg-info)."""
    upstream = tmp_path / "upstream.git"
    subprocess.run(["git", "init", "--bare", str(upstream)], check=True, capture_output=True)

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init")
    _git(seed, "config", "user.email", "t@example.com")
    _git(seed, "config", "user.name", "t")
    (seed / "docs").mkdir()
    (seed / "docs" / "note.md").write_text("v1\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "v1")
    _git(seed, "branch", "-M", "main")
    _git(seed, "remote", "add", "origin", str(upstream))
    _git(seed, "push", "-u", "origin", "main")

    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(upstream), str(work)],
        check=True,
        capture_output=True,
    )
    assert (work / "docs" / "note.md").is_file()
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    (work / ".env").write_text("KEEP=1\n", encoding="utf-8")
    (work / "docs" / "note.md").write_text("local dirt\n", encoding="utf-8")

    (seed / "docs" / "note.md").write_text("v2\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "v2")
    _git(seed, "push", "origin", "main")

    proc = _source_helpers(f"sync_git_checkout_to_origin {work.as_posix()!r} main")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert (work / "docs" / "note.md").read_text(encoding="utf-8") == "v2\n"
    assert (work / ".env").read_text(encoding="utf-8") == "KEEP=1\n"
    tip = _git(work, "rev-parse", "origin/main").stdout.strip()
    head = _git(work, "rev-parse", "HEAD").stdout.strip()
    assert head == tip
    assert "Discarding local tracked changes" in proc.stderr


def test_noninteractive_requires_channel() -> None:
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--root",
            "/tmp/astloom-should-not-exist-xyz",
            "--skip-install",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "ASTLOOM_CHANNEL": "",
            "ASTLOOM_NONINTERACTIVE": "1",
        },
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode != 0
    assert "non-interactive" in (proc.stderr + proc.stdout).lower() or "channel" in (
        proc.stderr + proc.stdout
    ).lower()


def test_can_prompt_respects_noninteractive_flag() -> None:
    proc = _source_helpers(
        "can_prompt && echo yes || echo no",
        env={"ASTLOOM_NONINTERACTIVE": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "no"
