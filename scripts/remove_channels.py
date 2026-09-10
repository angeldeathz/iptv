#!/usr/bin/env python3
"""Remove channels from official.m3u by global ID and recalculate lineup IDs."""
import argparse
import os
import re
import subprocess
import sys

from clean_m3u import parse_extinf

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


def parse_entries(raw_lines):
    entries = []
    current_extinf = None
    current_options = []

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
            entries.append(
                {
                    "extinf": current_extinf,
                    "options": current_options,
                    "url": line_str,
                }
            )
            current_extinf = None
            current_options = []

    return entries


def write_official(entries):
    with open(OFFICIAL, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for entry in entries:
            f.write(f"{entry['extinf']}\n")
            for option in entry["options"]:
                f.write(f"{option}\n")
            f.write(f"{entry['url']}\n\n")


def run_clean_m3u():
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "clean_m3u.py")],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Remove channels from official.m3u by global ID."
    )
    parser.add_argument(
        "ids",
        nargs="+",
        type=int,
        help="Global channel IDs from official.m3u (first number in tvg-name).",
    )
    args = parser.parse_args()
    requested_ids = set(args.ids)

    with open(OFFICIAL, encoding="utf-8") as f:
        official_entries = parse_entries(f.readlines())

    found_ids = set()
    kept = []

    for entry in official_entries:
        channel_id = extract_global_id(entry["extinf"])
        if channel_id in requested_ids:
            found_ids.add(channel_id)
        else:
            kept.append(entry)

    missing = sorted(requested_ids - found_ids)
    if missing:
        print(
            f"IDs no encontrados en official.m3u: {', '.join(map(str, missing))}",
            file=sys.stderr,
        )
        sys.exit(1)

    write_official(kept)
    run_clean_m3u()


if __name__ == "__main__":
    main()
