#!/usr/bin/env python3
"""Fix broken tvg-logo URLs in official.m3u by channel global ID."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

from clean_m3u import LOGO_LIBRARY, clean_channel_name, get_channel_base, parse_extinf
from logo_assets import check_url, find_working_logo, record_asset

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
OFFICIAL = os.path.join(REPO_ROOT, "official.m3u")


def extract_global_id(extinf_line: str) -> int | None:
    attrs, display_name = parse_extinf(extinf_line)
    tvg_name = attrs.get("tvg-name", display_name)
    for candidate in (tvg_name, display_name):
        match = re.match(r"^(\d+)\s+", candidate.strip())
        if match:
            return int(match.group(1))
    return None


def parse_entries(raw_lines: list[str]) -> list[dict]:
    entries = []
    current_extinf = None
    current_options: list[str] = []

    for line in raw_lines:
        line_str = line.strip()
        if not line_str or line_str.startswith("#EXTM3U"):
            continue
        if line_str.startswith("#EXTINF:"):
            current_extinf = line_str
            current_options = []
        elif line_str.startswith("#EXTVLCOPT:"):
            current_options.append(line_str)
        elif line_str.startswith("#"):
            continue
        elif current_extinf:
            attrs, display_name = parse_extinf(current_extinf)
            clean = clean_channel_name(display_name)
            entries.append(
                {
                    "extinf": current_extinf,
                    "options": current_options,
                    "url": line_str,
                    "attrs": attrs,
                    "display_name": display_name,
                    "clean_name": clean,
                    "base_name": get_channel_base(clean),
                    "global_id": extract_global_id(current_extinf),
                }
            )
            current_extinf = None
            current_options = []

    return entries


def set_extinf_logo(extinf: str, logo_url: str) -> str:
    if 'tvg-logo="' in extinf:
        return re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo_url}"', extinf, count=1)
    return extinf.replace("#EXTINF:-1 ", f'#EXTINF:-1 tvg-logo="{logo_url}" ', 1)


def sync_logo_library(base_key: str, logo_url: str) -> bool:
    """Update LOGO_LIBRARY entry in clean_m3u.py when we find a verified URL."""
    clean_path = os.path.join(SCRIPT_DIR, "clean_m3u.py")
    with open(clean_path, encoding="utf-8") as f:
        content = f.read()

    pattern = rf'(\s+"{re.escape(base_key)}": )"[^"]*"'
    if not re.search(pattern, content):
        return False

    new_content = re.sub(pattern, rf'\1"{logo_url}"', content, count=1)
    if new_content == content:
        return False

    with open(clean_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def write_official(entries: list[dict]) -> None:
    with open(OFFICIAL, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for entry in entries:
            f.write(f"{entry['extinf']}\n")
            for option in entry["options"]:
                f.write(f"{option}\n")
            f.write(f"{entry['url']}\n\n")


def run_clean_m3u() -> None:
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "clean_m3u.py")],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def fix_channel_base(entries: list[dict], base_name: str, dry_run: bool = False) -> dict:
    base_key = base_name.lower()
    group = [e for e in entries if e["base_name"].lower() == base_key]
    if not group:
        return {
            "channel": base_name,
            "status": "not_found",
            "old_url": "",
            "new_url": "",
            "source": "",
            "updated_variants": 0,
        }

    current_url = ""
    for entry in group:
        logo = entry["attrs"].get("tvg-logo", "")
        if logo:
            current_url = logo
            break

    library_url = LOGO_LIBRARY.get(base_key) or LOGO_LIBRARY.get(base_name.lower())
    extra = []
    if library_url and library_url != current_url:
        extra.append(("logo_library", library_url))

    ok, _, _ = check_url(current_url) if current_url else (False, None, "")
    if ok:
        if not dry_run:
            record_asset(base_name, current_url, "current")
            sync_logo_library(base_key, current_url)
        return {
            "channel": base_name,
            "status": "ok",
            "old_url": current_url,
            "new_url": current_url,
            "source": "current",
            "updated_variants": 0,
        }

    new_url, source = find_working_logo(base_name, current_url, extra)
    if not new_url:
        return {
            "channel": base_name,
            "status": "failed",
            "old_url": current_url,
            "new_url": "",
            "source": "",
            "updated_variants": 0,
        }

    updated = 0
    for entry in group:
        entry["extinf"] = set_extinf_logo(entry["extinf"], new_url)
        entry["attrs"]["tvg-logo"] = new_url
        updated += 1

    if not dry_run:
        record_asset(base_name, new_url, source or "unknown")
        sync_logo_library(base_key, new_url)

    return {
        "channel": base_name,
        "status": "fixed",
        "old_url": current_url,
        "new_url": new_url,
        "source": source,
        "updated_variants": updated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix broken tvg-logo URLs in official.m3u by global channel ID."
    )
    parser.add_argument(
        "ids",
        nargs="+",
        type=int,
        help="Global channel IDs (first number in tvg-name, e.g. 202 for '202 TLC 1').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Probe URLs and report changes without writing files.",
    )
    args = parser.parse_args()

    with open(OFFICIAL, encoding="utf-8") as f:
        entries = parse_entries(f.readlines())

    id_map = {e["global_id"]: e for e in entries if e["global_id"] is not None}
    missing = sorted(set(args.ids) - set(id_map))
    if missing:
        msg = f"IDs no encontrados en official.m3u: {', '.join(map(str, missing))}"
        if args.json:
            print(json.dumps({"error": msg, "missing_ids": missing}, ensure_ascii=False))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)

    bases: list[str] = []
    id_results = []
    for channel_id in args.ids:
        entry = id_map[channel_id]
        base = entry["base_name"]
        if base.lower() not in {b.lower() for b in bases}:
            bases.append(base)
        id_results.append(
            {
                "id": channel_id,
                "tvg_name": entry["attrs"].get("tvg-name", entry["display_name"]),
                "channel": base,
            }
        )

    outcomes = []
    for base_name in bases:
        outcomes.append(fix_channel_base(entries, base_name, dry_run=args.dry_run))

    if not args.dry_run:
        write_official(entries)
        run_clean_m3u()

    summary = {
        "requested_ids": args.ids,
        "channels": id_results,
        "results": outcomes,
        "dry_run": args.dry_run,
    }

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for item in outcomes:
            if item["status"] == "ok":
                print(f"OK  {item['channel']}: {item['new_url']}")
            elif item["status"] == "fixed":
                print(
                    f"FIX {item['channel']}: {item['old_url'] or '(sin logo)'} "
                    f"-> {item['new_url']} [{item['source']}] "
                    f"({item['updated_variants']} variantes)"
                )
            elif item["status"] == "failed":
                print(f"FAIL {item['channel']}: no se encontró logo alternativo", file=sys.stderr)
            else:
                print(f"??  {item['channel']}: {item['status']}")

    if any(r["status"] == "failed" for r in outcomes):
        sys.exit(2)
    if any(r["status"] == "fixed" for r in outcomes) and args.dry_run:
        print("\n(dry-run: no se escribieron cambios)", file=sys.stderr)


if __name__ == "__main__":
    main()
