"""Shared helpers for ID-based channel operations on official.m3u."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set

from clean_m3u import GROUP_ORDER, parse_extinf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
OFFICIAL = os.path.join(REPO_ROOT, "official.m3u")
BACKUP = os.path.join(REPO_ROOT, "backup.m3u")

GROUP_ALIASES = {
    "infantiles": "Infantiles",
    "kids": "Infantiles",
    "peliculas": "Peliculas",
    "películas": "Peliculas",
    "cine": "Peliculas",
    "series": "Series",
    "deportes": "Deportes",
    "sports": "Deportes",
    "noticias": "Noticias",
    "news": "Noticias",
    "musica": "Musica",
    "música": "Musica",
    "documentales": "Documentales",
    "nacionales": "Nacionales",
    "regionales": "Regionales",
    "variedades": "Variedades",
    "internacionales": "Internacionales",
    "pluto tv": "Pluto TV",
    "pluto": "Pluto TV",
    "24/7 - experimentales": "24/7 - Experimentales",
    "24/7 experimentales": "24/7 - Experimentales",
    "experimentales": "24/7 - Experimentales",
}


@dataclass(frozen=True)
class ChannelEntry:
    extinf: str
    options: List[str]
    url: str

    @property
    def channel_id(self) -> Optional[int]:
        return extract_global_id(self.extinf)

    @property
    def label(self) -> str:
        attrs, display_name = parse_extinf(self.extinf)
        return attrs.get("tvg-name", display_name).strip() or display_name.strip()


def extract_global_id(extinf_line: str) -> Optional[int]:
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


def parse_entries(raw_lines: Iterable[str]) -> List[ChannelEntry]:
    entries: List[ChannelEntry] = []
    current_extinf: Optional[str] = None
    current_options: List[str] = []

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
                ChannelEntry(
                    extinf=current_extinf,
                    options=current_options,
                    url=line_str,
                )
            )
            current_extinf = None
            current_options = []

    return entries


def load_official_entries(path: str = OFFICIAL) -> List[ChannelEntry]:
    with open(path, encoding="utf-8") as f:
        return parse_entries(f.readlines())


def index_entries_by_id(entries: Sequence[ChannelEntry]) -> Dict[int, ChannelEntry]:
    indexed: Dict[int, ChannelEntry] = {}
    for entry in entries:
        channel_id = entry.channel_id
        if channel_id is None:
            continue
        indexed[channel_id] = entry
    return indexed


def normalize_group_name(raw: str) -> Optional[str]:
    stripped = raw.strip()
    if stripped in GROUP_ORDER:
        return stripped
    return GROUP_ALIASES.get(stripped.casefold())


def apply_group_to_entry(entry: ChannelEntry, group: str) -> ChannelEntry:
    duration_match = re.match(r"#EXTINF:([^,]+)", entry.extinf)
    duration = duration_match.group(1) if duration_match else "-1"
    attrs, display_name = parse_extinf(entry.extinf)
    attrs["group-title"] = group
    attrs["editorial-group"] = group
    attrs_str = "".join(f' {k}="{v}"' for k, v in attrs.items())
    return ChannelEntry(
        extinf=f"#EXTINF:{duration}{attrs_str},{display_name}",
        options=entry.options,
        url=entry.url,
    )


def parse_recategorizations(values: Sequence[str]) -> Dict[int, str]:
    moves: Dict[int, str] = {}
    for raw in values:
        if ":" not in raw:
            raise ValueError(
                f"Invalid --recategorize value '{raw}'. Use ID:GROUP, e.g. 188:Infantiles"
            )
        id_part, group_part = raw.split(":", 1)
        channel_id = int(id_part.strip())
        group = normalize_group_name(group_part)
        if group is None:
            known = ", ".join(GROUP_ORDER)
            raise ValueError(
                f"Unknown group '{group_part.strip()}'. Valid groups: {known}"
            )
        moves[channel_id] = group
    return moves


def write_official_entries(entries: Sequence[ChannelEntry], path: str = OFFICIAL) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for entry in entries:
            f.write(f"{entry.extinf}\n")
            for option in entry.options:
                f.write(f"{option}\n")
            f.write(f"{entry.url}\n\n")


def run_clean_m3u() -> None:
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "clean_m3u.py")],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def parse_expectations(values: Sequence[str]) -> Dict[int, str]:
    expectations: Dict[int, str] = {}
    for raw in values:
        if ":" not in raw:
            raise ValueError(
                f"Invalid --expect value '{raw}'. Use ID:NAME, e.g. 82:UNIVERSAL PREMIERE"
            )
        id_part, name_part = raw.split(":", 1)
        channel_id = int(id_part.strip())
        fragment = name_part.strip()
        if not fragment:
            raise ValueError(f"Invalid --expect value '{raw}': name fragment is empty")
        expectations[channel_id] = fragment
    return expectations


def matches_expectation(label: str, expected_fragment: str) -> bool:
    return expected_fragment.casefold() in label.casefold()


def verify_expectations(
    indexed: Dict[int, ChannelEntry],
    expectations: Dict[int, str],
) -> List[str]:
    errors: List[str] = []
    for channel_id, fragment in sorted(expectations.items()):
        entry = indexed.get(channel_id)
        if entry is None:
            errors.append(f"ID {channel_id}: not found in official.m3u")
            continue
        if not matches_expectation(entry.label, fragment):
            errors.append(
                f"ID {channel_id}: expected name containing '{fragment}', "
                f"found '{entry.label}'"
            )
    return errors


def find_missing_ids(requested: Set[int], found: Set[int]) -> List[int]:
    return sorted(requested - found)


def format_action_plan(
    remove_ids: Set[int],
    backup_ids: Set[int],
    indexed: Dict[int, ChannelEntry],
    recategorize_map: Optional[Dict[int, str]] = None,
) -> str:
    lines: List[str] = []
    recategorize_map = recategorize_map or {}
    recategorize_ids = set(recategorize_map)
    overlap = sorted((remove_ids & backup_ids) | (remove_ids & recategorize_ids) | (backup_ids & recategorize_ids))
    if overlap:
        lines.append("ERROR: same ID requested for multiple actions:")
        for channel_id in overlap:
            lines.append(f"  {channel_id} = {indexed[channel_id].label}")
        return "\n".join(lines)

    if recategorize_map:
        lines.append("RECATEGORIZE:")
        for channel_id in sorted(recategorize_map):
            entry = indexed[channel_id]
            target_group = recategorize_map[channel_id]
            lines.append(f"  {channel_id} = {entry.label} -> {target_group}")
            lines.append(f"    {entry.url}")

    if backup_ids:
        lines.append("BACKUP:")
        for channel_id in sorted(backup_ids):
            entry = indexed[channel_id]
            lines.append(f"  {channel_id} = {entry.label}")
            lines.append(f"    {entry.url}")

    if remove_ids:
        lines.append("REMOVE:")
        for channel_id in sorted(remove_ids):
            entry = indexed[channel_id]
            lines.append(f"  {channel_id} = {entry.label}")
            lines.append(f"    {entry.url}")

    if not lines:
        lines.append("No channel operations requested.")
    return "\n".join(lines)
