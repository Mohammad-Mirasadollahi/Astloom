"""Filesystem poller for pending-sync watcher sidecar (batched)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

_SCRIPTS = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "services"
    / "code-graph-service"
    / "scripts"
)
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from watch_pending_sync import ChangeBatcher, poll_once, snapshot  # noqa: E402


def test_poll_detects_new_and_changed_files(tmp_path: Path):
    root = tmp_path / "src"
    root.mkdir()
    f = root / "a.py"
    f.write_text("x=1\n", encoding="utf-8")
    prev = snapshot(root, {".py"})
    time.sleep(0.05)
    f.write_text("x=2\n", encoding="utf-8")
    (root / "b.py").write_text("y=1\n", encoding="utf-8")
    _cur, changed = poll_once(root, prev, extensions={".py"})
    assert any(p.endswith("a.py") for p in changed)
    assert any(p.endswith("b.py") for p in changed)


def test_batcher_waits_for_debounce_not_per_change():
    batcher = ChangeBatcher(debounce_s=10.0, max_wait_s=60.0)
    t0 = 1000.0
    batcher.add(["/a.py", "/b.py"], now=t0)
    assert batcher.ready(now=t0 + 1.0) is False
    batcher.add(["/c.py"], now=t0 + 2.0)  # still writing — reset quiet clock
    assert batcher.ready(now=t0 + 5.0) is False
    assert batcher.ready(now=t0 + 2.0 + 10.0) is True
    flushed = batcher.flush()
    assert flushed == ["/a.py", "/b.py", "/c.py"]
    assert batcher.size == 0


def test_batcher_flushes_on_max_wait_during_continuous_edits():
    batcher = ChangeBatcher(debounce_s=30.0, max_wait_s=12.0)
    t0 = 5000.0
    batcher.add(["/a.py"], now=t0)
    # Agent keeps editing every few seconds — debounce never settles
    for i in range(1, 4):
        batcher.add([f"/{i}.py"], now=t0 + i * 3)
        assert batcher.ready(now=t0 + i * 3) is False
    # At t0+12 continuous writing still hits max_wait ceiling
    batcher.add(["/4.py"], now=t0 + 11.0)
    assert batcher.ready(now=t0 + 12.0) is True
    assert len(batcher.flush()) >= 2
