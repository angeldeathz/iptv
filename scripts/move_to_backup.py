#!/usr/bin/env python3
"""Move channels from official.m3u to backup.m3u by global ID."""
import argparse
import os
import re
import subprocess
import sys

from clean_m3u import GROUP_ORDER, parse_extinf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
OFFICIAL = os.path.join(REPO_ROOT, "official.m3u")
BACKUP = os.path.join(REPO_ROOT, "backup.m3u")

BACKUP_HEADER = (
    "#EXTM3U\n\n"
    "# Respaldo de canales cuando la señal principal en official.m3u deja de funcionar.\n"
)


def extract_global_id(extinf_line: str) -> int | None:
    attrs, display_name = parse_extinf(extinf_line)
    tvg_name = attrs.get("tvg-name", display_name)
    for candidate in (tvg_name, display_name):
        match = re.match(r"^(\d+)\s+", candidate.strip())
        if match:
            return int(match.group(1))
    return None


def strip_global_id(name: str) -> str:
    match = re.match(r"^\d+\s+(.+)$", name.strip())
    return match.group(1).strip() if match else name.strip()


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


def normalize_for_backup(entry: dict) -> dict:
    attrs, display_name = parse_extinf(entry["extinf"])
    backup_name = strip_global_id(attrs.get("tvg-name", display_name))
    backup_display = strip_global_id(display_name)

    duration_match = re.match(r"#EXTINF:([^,]+)", entry["extinf"])
    duration = duration_match.group(1) if duration_match else "-1"

    attrs.pop("tvg-id", None)
    attrs["tvg-name"] = backup_name
    attrs_str = "".join(f' {k}="{v}"' for k, v in attrs.items())
    extinf = f"#EXTINF:{duration}{attrs_str},{backup_display}"

    return {
        "extinf": extinf,
        "options": entry["options"],
        "url": entry["url"],
        "group": attrs.get("group-title", "Variedades"),
    }


def parse_backup_entries(raw_lines):
    entries = []
    for entry in parse_entries(raw_lines):
        attrs, _ = parse_extinf(entry["extinf"])
        entries.append(
            {
                **entry,
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
        description="Move channels from official.m3u to backup.m3u by global ID."
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
    moved = []

    for entry in official_entries:
        channel_id = extract_global_id(entry["extinf"])
        if channel_id in requested_ids:
            found_ids.add(channel_id)
            moved.append(normalize_for_backup(entry))
        else:
            kept.append(entry)

    missing = sorted(requested_ids - found_ids)
    if missing:
        print(f"IDs no encontrados en official.m3u: {', '.join(map(str, missing))}", file=sys.stderr)
        sys.exit(1)

    write_official(kept)

    backup_entries = []
    if os.path.exists(BACKUP):
        with open(BACKUP, encoding="utf-8") as f:
            backup_entries = parse_backup_entries(f.readlines())

    existing_urls = {e["url"] for e in backup_entries}
    for entry in moved:
        if entry["url"] not in existing_urls:
            backup_entries.append(entry)
            existing_urls.add(entry["url"])

    write_backup(backup_entries)
    run_clean_m3u()


if __name__ == "__main__":
    main()
