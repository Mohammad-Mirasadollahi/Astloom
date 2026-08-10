"""Thin Astloom client CLI entry (install role=client)."""

from __future__ import annotations

from astloom_cli.util import ensure_service_import_paths

ensure_service_import_paths()

from astloom_client.dispatch import dispatch
from astloom_client.parser import build_parser


def main(argv: list[str] | None = None) -> int:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        return dispatch(args, parser)
    except KeyboardInterrupt:
        print("\nInterrupted — remote sync stop uses Ctrl+C during sync", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
