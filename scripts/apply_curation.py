#!/usr/bin/env python3
"""Apply one-off curation rules to official.m3u before running clean_m3u.py."""
import re
import sys
from typing import Optional

from clean_m3u import parse_extinf

import os

script_dir = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(script_dir, "..", "official.m3u")

DELETE_IDS = {
    28, 33, 35, 39, 61, 76, 81, 106, 109, 110, 113, 119, 128, 129,
    153, 154, 156, 159, 160, 165, 173, 177, 178, 181, 185, 186, 187,
    188, 189, 190, 191, 192, 193, 194, 195, 196, 198, 199,
}

RENAME_BY_ID = {}

MOVE_GROUP_BY_ID = {
    127: "Peliculas",
    169: "Noticias",
    180: "Noticias",
}


def extract_global_id(extinf_line: str) -> Optional[int]:
    _, attrs, display_name = parse_extinf(extinf_line)
    tvg_name = attrs.get("tvg-name", display_name)
    match = re.match(r"^(\d+)\s+", tvg_name.strip())
    if match:
        return int(match.group(1))
    match = re.match(r"^(\d+)\s+", display_name.strip())
    return int(match.group(1)) if match else None


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


def apply_rename(extinf_line: str, new_clean_name: str) -> str:
    duration, attrs, _ = parse_extinf(extinf_line)
    attrs_str = "".join(f' {k}="{v}"' for k, v in attrs.items())
    placeholder = f"0 {new_clean_name} 1"
    return f"#EXTINF:{duration}{attrs_str},{placeholder}"


def apply_group(extinf_line: str, group: str) -> str:
    duration, attrs, display_name = parse_extinf(extinf_line)
    attrs["group-title"] = group
    attrs_str = "".join(f' {k}="{v}"' for k, v in attrs.items())
    return f"#EXTINF:{duration}{attrs_str},{display_name}"


def add_editorial_group(extinf_line: str, group: str) -> str:
    duration, attrs, display_name = parse_extinf(extinf_line)
    attrs["editorial-group"] = group
    attrs_str = "".join(f' {k}="{v}"' for k, v in attrs.items())
    return f"#EXTINF:{duration}{attrs_str},{display_name}"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(target, encoding="utf-8") as f:
        raw_lines = f.readlines()

    entries = parse_entries(raw_lines)
    kept = []
    removed = 0
    renamed = 0
    moved = 0

    for entry in entries:
        channel_id = extract_global_id(entry["extinf"])
        if channel_id is None:
            kept.append(entry)
            continue

        if channel_id in DELETE_IDS:
            removed += 1
            continue

        if channel_id in RENAME_BY_ID:
            entry["extinf"] = apply_rename(entry["extinf"], RENAME_BY_ID[channel_id])
            renamed += 1

        if channel_id in MOVE_GROUP_BY_ID:
            entry["extinf"] = apply_group(entry["extinf"], MOVE_GROUP_BY_ID[channel_id])
            entry["extinf"] = add_editorial_group(entry["extinf"], MOVE_GROUP_BY_ID[channel_id])
            moved += 1

        kept.append(entry)

    with open(target, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for entry in kept:
            f.write(f"{entry['extinf']}\n")
            for option in entry["options"]:
                f.write(f"{option}\n")
            f.write(f"{entry['url']}\n\n")

    print(
        f"Applied curation to {target}: "
        f"removed {removed}, renamed {renamed}, moved {moved}, kept {len(kept)}."
    )


if __name__ == "__main__":
    main()
