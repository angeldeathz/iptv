#!/usr/bin/env python3
"""Copy tvg-logo URLs from official.m3u into assets/logos.json by global channel ID."""
from __future__ import annotations

import argparse
import json
import sys

from fix_logos import OFFICIAL, parse_entries
from logo_assets import load_assets, record_asset


def sync_channel_ids(ids: list[int], dry_run: bool = False) -> dict:
    with open(OFFICIAL, encoding="utf-8") as f:
        entries = parse_entries(f.readlines())

    id_map = {entry["global_id"]: entry for entry in entries if entry["global_id"] is not None}
    missing = sorted(set(ids) - set(id_map))
    if missing:
        return {
            "error": f"IDs no encontrados en official.m3u: {', '.join(map(str, missing))}",
            "missing_ids": missing,
        }

    bases: list[str] = []
    id_results = []
    for channel_id in ids:
        entry = id_map[channel_id]
        base = entry["base_name"]
        if base.lower() not in {name.lower() for name in bases}:
            bases.append(base)
        id_results.append(
            {
                "id": channel_id,
                "tvg_name": entry["attrs"].get("tvg-name", entry["display_name"]),
                "channel": base,
            }
        )

    assets_before = load_assets()
    results = []
    for base_name in bases:
        group = [entry for entry in entries if entry["base_name"].lower() == base_name.lower()]
        logo_url = ""
        for entry in group:
            logo = entry["attrs"].get("tvg-logo", "")
            if logo:
                logo_url = logo
                break

        if not logo_url:
            results.append(
                {
                    "channel": base_name,
                    "status": "skipped",
                    "reason": "sin tvg-logo en official.m3u",
                    "url": "",
                }
            )
            continue

        key = base_name.lower().strip()
        old_entry = assets_before.get(key)
        old_url = old_entry.get("url", "") if isinstance(old_entry, dict) else ""

        if old_url == logo_url:
            status = "unchanged"
        elif old_url:
            status = "updated"
        else:
            status = "added"

        if not dry_run:
            record_asset(base_name, logo_url, "official_m3u")

        results.append(
            {
                "channel": base_name,
                "status": status,
                "old_url": old_url,
                "url": logo_url,
            }
        )

    return {
        "requested_ids": ids,
        "channels": id_results,
        "results": results,
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy tvg-logo URLs from official.m3u into assets/logos.json."
    )
    parser.add_argument(
        "ids",
        nargs="+",
        type=int,
        help="Global channel IDs (first number in tvg-name, e.g. 4 for '4 TVN 1').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing assets/logos.json.",
    )
    args = parser.parse_args()

    summary = sync_channel_ids(args.ids, dry_run=args.dry_run)

    if "error" in summary:
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(summary["error"], file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for item in summary["results"]:
            if item["status"] == "skipped":
                print(f"SKIP {item['channel']}: {item['reason']}", file=sys.stderr)
            elif item["status"] == "added":
                print(f"ADD  {item['channel']}: {item['url']}")
            elif item["status"] == "updated":
                print(f"UPD  {item['channel']}: {item['old_url']} -> {item['url']}")
            else:
                print(f"OK   {item['channel']}: {item['url']}")

    if any(item["status"] == "skipped" for item in summary["results"]):
        sys.exit(2)


if __name__ == "__main__":
    main()
