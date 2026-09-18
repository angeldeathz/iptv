#!/usr/bin/env python3
"""Move channels to another section in official.m3u by global ID."""
from __future__ import annotations

import argparse
import sys

from channel_ops import apply_operations
from m3u_channel_utils import parse_expectations, parse_recategorizations


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recategorize channels in official.m3u by global ID. "
            "Sets group-title and editorial-group so clean_m3u.py keeps the target section."
        )
    )
    parser.add_argument(
        "moves",
        nargs="+",
        metavar="ID:GROUP",
        help="Move spec, e.g. 188:Infantiles 189:Infantiles",
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        metavar="ID:NAME",
        help=(
            "Verify that ID resolves to a channel whose tvg-name contains NAME "
            "before recategorizing it."
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
        recategorize_map = parse_recategorizations(args.moves)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    sys.exit(
        apply_operations(
            remove_ids=set(),
            backup_ids=set(),
            expectations=expectations,
            dry_run=args.dry_run,
            recategorize_map=recategorize_map,
        )
    )


if __name__ == "__main__":
    main()
