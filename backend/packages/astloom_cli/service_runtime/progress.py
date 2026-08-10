"""Progress lines and wall-clock helpers."""

from __future__ import annotations

import os
import time
from datetime import datetime


def progress(message: str) -> None:
    """Human progress line for long start/stop/restart steps (always flushed)."""
    from astloom_cli import ui

    print(f"   {ui.accent('→')}  {message}", flush=True)


def wall_clock_now() -> str:
    """Local wall clock to the second: ``YYYY-MM-DD HH:MM:SS``."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_wall_clock(stamp: str) -> datetime | None:
    """Parse ``YYYY-MM-DD HH:MM:SS`` local wall clock; ``None`` if invalid."""
    text = (stamp or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def uptime_seconds_since(stamp: str, *, now: datetime | None = None) -> int | None:
    """Seconds from ``stamp`` to ``now`` (local). ``None`` if stamp is invalid."""
    started = parse_wall_clock(stamp)
    if started is None:
        return None
    current = now or datetime.now()
    return max(0, int((current - started).total_seconds()))


def format_docker_started_at(raw: str) -> str:
    """Convert Docker ``State.StartedAt`` to local ``YYYY-MM-DD HH:MM:SS``."""
    text = (raw or "").strip()
    if not text or text.startswith("0001-"):
        return wall_clock_now()
    # Docker may emit nanoseconds; fromisoformat accepts up to microseconds.
    if "." in text:
        head, frac_and_tz = text.split(".", 1)
        digits = ""
        tz = ""
        for ch in frac_and_tz:
            if ch.isdigit():
                digits += ch
            else:
                tz = frac_and_tz[len(digits) :]
                break
        text = f"{head}.{digits[:6].ljust(6, '0')}{tz}"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return wall_clock_now()
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def format_process_started_at(pid: int) -> str | None:
    """Local wall clock when ``pid`` started (Linux ``/proc``); ``None`` if unknown."""
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            raw = handle.read()
        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime_sec = float(handle.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    rparen = raw.rfind(")")
    if rparen < 0:
        return None
    fields = raw[rparen + 2 :].split()
    if len(fields) < 20:
        return None
    try:
        start_ticks = int(fields[19])
        ticks = int(os.sysconf("SC_CLK_TCK"))
    except (ValueError, OSError):
        return None
    if ticks <= 0:
        return None
    boot = time.time() - uptime_sec
    started = datetime.fromtimestamp(boot + (start_ticks / ticks))
    return started.strftime("%Y-%m-%d %H:%M:%S")


def stack_restarted_at(*stamps: str | None) -> str | None:
    """Latest start among running pieces = when the stack last became fully current."""
    parsed = [(parse_wall_clock(s), s) for s in stamps if s]
    valid = [(dt, s) for dt, s in parsed if dt is not None]
    if not valid:
        return None
    return max(valid, key=lambda item: item[0])[1]