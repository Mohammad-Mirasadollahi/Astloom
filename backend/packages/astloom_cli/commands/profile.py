"""profile catalog commands."""

from __future__ import annotations

import argparse

from astloom_cli.util import print_json
from usage_profile import list_profile_ids, load_usage_profile


def cmd_profile_list(_: argparse.Namespace) -> int:
    for profile_id in list_profile_ids():
        profile = load_usage_profile(profile_id)
        print(f"{profile_id}\t{profile.get('title')}\t{profile.get('audience')}")
    return 0


def cmd_profile_show(args: argparse.Namespace) -> int:
    print_json(load_usage_profile(args.profile_id))
    return 0
