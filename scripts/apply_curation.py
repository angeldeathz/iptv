#!/usr/bin/env python3
"""Apply one-off curation rules to official.m3u before running clean_m3u.py."""
import re
import sys
from typing import Optional

from clean_m3u import parse_extinf

TARGET = "/home/angeldeathz/iptv/official.m3u"

DELETE_IDS = {
    5, 13, 14, 15, 21,
    41, 43, 44, 45, 46, 48, 50, 52, 53, 55, 56, 57, 58, 59, 60,
    63, 65, 67, 68, 70, 77, 78,
    99, 100, 101, 102, 103,
    122, 128, 130, 131, 135, 136, 137, 138,
    146, 147,
    153, 155, 157, 158,
    160, 161, 170, 172, 174, 175, 176, 178, 179,
    181, 182, 183, 184, 185, 186, 187, 188,
}

RENAME_BY_ID = {
    80: "Film&Arts",
    104: "FMH Movies",
    114: "Disney Jr",
    115: "Disney Jr",
}

MOVE_GROUP_BY_ID = {
    118: "Musica",
    119: "Musica",
    189: "Nacionales",
    197: "Peliculas",
    198: "Peliculas",
    199: "Peliculas",
    206: "Peliculas",
    208: "Peliculas",
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
