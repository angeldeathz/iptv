#!/usr/bin/env python3
"""Remove channels from official.m3u by global ID and recalculate lineup IDs."""
from __future__ import annotations

import argparse
import sys

from channel_ops import apply_operations
from m3u_channel_utils import parse_expectations


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove channels from official.m3u by global ID."
    )
    parser.add_argument(
        "ids",
        nargs="+",
        type=int,
        help="Global channel IDs from official.m3u (first number in tvg-name).",
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        metavar="ID:NAME",
        help=(
            "Verify that ID resolves to a channel whose tvg-name contains NAME "
            "before deleting it."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the resolved plan without modifying files.",
    )
    args = parser.parse_args()

    try:
        expectations = parse_expectations(args.expect)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    sys.exit(
        apply_operations(
            remove_ids=set(args.ids),
            backup_ids=set(),
            expectations=expectations,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
