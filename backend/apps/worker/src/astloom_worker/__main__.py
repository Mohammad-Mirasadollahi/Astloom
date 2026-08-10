from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_PACKAGES = Path(__file__).resolve().parents[4] / "packages"
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

from outbox_relay import OutboxRelay, load_relay_config  # noqa: E402
from outbox_relay.wiring import build_default_handlers  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Astloom transactional outbox relay worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Poll once and exit (default: poll forever)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print batch results as JSON lines",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_relay_config()
    handlers = build_default_handlers(database_url=config.database_url, config=config)
    relay = OutboxRelay.from_config(config, handlers)
    try:
        while True:
            result = relay.run_once()
            if args.json:
                print(
                    json.dumps(
                        {
                            "polled": result.polled,
                            "published": result.published,
                            "errors": result.errors,
                            "handler_results": result.handler_results,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
            elif result.polled or result.errors:
                print(
                    f"outbox-relay polled={result.polled} published={result.published} "
                    f"errors={len(result.errors)}",
                    flush=True,
                )
                for err in result.errors:
                    print(f"error: {err}", file=sys.stderr, flush=True)
            if args.once:
                return 1 if result.errors else 0
            time.sleep(config.poll_interval_seconds)
    finally:
        relay.close()


if __name__ == "__main__":
    raise SystemExit(main())
