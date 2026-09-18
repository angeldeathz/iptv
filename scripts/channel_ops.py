#!/usr/bin/env python3
"""Atomic remove/backup operations on official.m3u by global ID.

Use this script when the user requests multiple ID-based changes in one message.
IDs are resolved once, then all operations run in a single pass before clean_m3u.py.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Optional

from clean_m3u import GROUP_ORDER, parse_extinf
from m3u_channel_utils import (
    BACKUP,
    ChannelEntry,
    apply_group_to_entry,
    find_missing_ids,
    format_action_plan,
    index_entries_by_id,
    load_official_entries,
    parse_expectations,
    parse_recategorizations,
    run_clean_m3u,
    strip_global_id,
    verify_expectations,
    write_official_entries,
)

BACKUP_HEADER = (
    "#EXTM3U\n\n"
    "# Respaldo de canales cuando la señal principal en official.m3u deja de funcionar.\n"
)


def normalize_for_backup(entry: ChannelEntry) -> dict:
    attrs, display_name = parse_extinf(entry.extinf)
    backup_name = strip_global_id(attrs.get("tvg-name", display_name))
    backup_display = strip_global_id(display_name)

    duration_match = re.match(r"#EXTINF:([^,]+)", entry.extinf)
    duration = duration_match.group(1) if duration_match else "-1"

    attrs.pop("tvg-id", None)
    attrs["tvg-name"] = backup_name
    attrs_str = "".join(f' {k}="{v}"' for k, v in attrs.items())
    extinf = f"#EXTINF:{duration}{attrs_str},{backup_display}"

    return {
        "extinf": extinf,
        "options": entry.options,
        "url": entry.url,
        "group": attrs.get("group-title", "Variedades"),
    }


def parse_backup_entries(raw_lines):
    from m3u_channel_utils import parse_entries

    entries = []
    for entry in parse_entries(raw_lines):
        attrs, _ = parse_extinf(entry.extinf)
        entries.append(
            {
                "extinf": entry.extinf,
                "options": entry.options,
                "url": entry.url,
                "group": attrs.get("group-title", "Variedades"),
            }
        )
    return entries


def group_priority(group_name: str) -> int:
    try:
        return GROUP_ORDER.index(group_name)
    except ValueError:
        return len(GROUP_ORDER)


def write_backup(entries):
    entries.sort(key=lambda e: (group_priority(e["group"]), e["extinf"]))
    lines = [BACKUP_HEADER.rstrip("\n"), ""]
    current_group = None

    for entry in entries:
        if entry["group"] != current_group:
            current_group = entry["group"]
            lines.append(f"# ===== {current_group} =====")
            lines.append("")

        lines.append(entry["extinf"])
        for option in entry["options"]:
            lines.append(option)
        lines.append(entry["url"])
        lines.append("")

    with open(BACKUP, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def list_channels(filter_text: Optional[str] = None) -> int:
    entries = load_official_entries()
    indexed = index_entries_by_id(entries)
    needle = filter_text.casefold() if filter_text else None

    for channel_id in sorted(indexed):
        entry = indexed[channel_id]
        if needle and needle not in entry.label.casefold():
            continue
        print(f"{channel_id:>4}  {entry.label}")
    return 0


def apply_operations(
    remove_ids: set[int],
    backup_ids: set[int],
    expectations: dict[int, str],
    dry_run: bool,
    recategorize_map: dict[int, str] | None = None,
) -> int:
    recategorize_map = recategorize_map or {}
    recategorize_ids = set(recategorize_map)

    if not remove_ids and not backup_ids and not recategorize_ids:
        print("No channel operations requested.", file=sys.stderr)
        return 1

    conflicting_ids = (remove_ids & backup_ids) | (remove_ids & recategorize_ids) | (backup_ids & recategorize_ids)
    if conflicting_ids:
        print(
            "The same ID cannot be removed, backed up, and recategorized in one operation.",
            file=sys.stderr,
        )
        return 1

    official_entries = load_official_entries()
    indexed = index_entries_by_id(official_entries)
    all_requested = remove_ids | backup_ids | recategorize_ids

    missing = find_missing_ids(all_requested, set(indexed))
    if missing:
        print(
            f"IDs not found in official.m3u: {', '.join(map(str, missing))}",
            file=sys.stderr,
        )
        return 1

    expectation_errors = verify_expectations(indexed, expectations)
    if expectation_errors:
        print("Name verification failed:", file=sys.stderr)
        for error in expectation_errors:
            print(f"  - {error}", file=sys.stderr)
        print("\nCurrent playlist entries for requested IDs:", file=sys.stderr)
        for channel_id in sorted(all_requested):
            print(f"  {channel_id} = {indexed[channel_id].label}", file=sys.stderr)
        return 1

    plan = format_action_plan(remove_ids, backup_ids, indexed, recategorize_map)
    print(plan)
    if plan.startswith("ERROR:"):
        return 1

    if dry_run:
        print("\nDry run: no files were modified.")
        return 0

    kept: list[ChannelEntry] = []
    moved: list[ChannelEntry] = []

    for entry in official_entries:
        channel_id = entry.channel_id
        if channel_id in backup_ids:
            moved.append(entry)
        elif channel_id in remove_ids:
            continue
        elif channel_id in recategorize_map:
            kept.append(apply_group_to_entry(entry, recategorize_map[channel_id]))
        else:
            kept.append(entry)

    write_official_entries(kept)

    if moved:
        backup_entries = []
        if os.path.exists(BACKUP):
            with open(BACKUP, encoding="utf-8") as f:
                backup_entries = parse_backup_entries(f.readlines())

        existing_urls = {entry["url"] for entry in backup_entries}
        for entry in moved:
            normalized = normalize_for_backup(entry)
            if normalized["url"] not in existing_urls:
                backup_entries.append(normalized)
                existing_urls.add(normalized["url"])

        write_backup(backup_entries)

    run_clean_m3u()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply remove/backup operations atomically on official.m3u. "
            "Use this when a user request mixes both actions or touches multiple IDs."
        )
    )
    parser.add_argument(
        "--remove",
        dest="remove_ids",
        action="append",
        type=int,
        default=[],
        metavar="ID",
        help="Global ID to permanently delete from official.m3u.",
    )
    parser.add_argument(
        "--backup",
        dest="backup_ids",
        action="append",
        type=int,
        default=[],
        metavar="ID",
        help="Global ID to move from official.m3u to backup.m3u.",
    )
    parser.add_argument(
        "--recategorize",
        action="append",
        default=[],
        metavar="ID:GROUP",
        help=(
            "Move a channel to another section by setting group-title and "
            "editorial-group (e.g. 188:Infantiles). Repeat per channel."
        ),
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        metavar="ID:NAME",
        help=(
            "Verify that ID resolves to a channel whose tvg-name contains NAME "
            "(case-insensitive). Repeat for each ID when names are known."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the resolved plan without modifying files.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List current official.m3u channels as ID + tvg-name.",
    )
    parser.add_argument(
        "--filter",
        help="Case-insensitive filter used with --list.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        sys.exit(list_channels(args.filter))

    try:
        expectations = parse_expectations(args.expect)
        recategorize_map = parse_recategorizations(args.recategorize)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    remove_ids = set(args.remove_ids)
    backup_ids = set(args.backup_ids)
    sys.exit(
        apply_operations(
            remove_ids=remove_ids,
            backup_ids=backup_ids,
            expectations=expectations,
            dry_run=args.dry_run,
            recategorize_map=recategorize_map,
        )
    )


if __name__ == "__main__":
    main()
