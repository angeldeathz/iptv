#!/usr/bin/env python3
"""Set real tvg-logo URLs in official.m3u for channels identified by global ID."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

from clean_m3u import (
    LOGO_LIBRARY,
    clean_channel_name,
    get_channel_base,
    parse_extinf,
)
from search_sources import SOURCE_PLAYLISTS, fetch_playlist

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
OFFICIAL = os.path.join(REPO_ROOT, "official.m3u")


@dataclass
class ChannelTarget:
    channel_id: int
    clean_name: str
    base_name: str
    display_name: str


@dataclass
class LogoResult:
    base_name: str
    logo: Optional[str]
    source: str
    channel_ids: list[int]


def extract_global_id(extinf_line: str) -> int | None:
    attrs, display_name = parse_extinf(extinf_line)
    tvg_name = attrs.get("tvg-name", display_name)
    for candidate in (tvg_name, display_name):
        match = re.match(r"^(\d+)\s+", candidate.strip())
        if match:
            return int(match.group(1))
    return None


def parse_entries(raw_lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    current_extinf: str | None = None
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


def parse_id_tokens(tokens: list[str]) -> list[int]:
    ids: list[int] = []
    for token in tokens:
        if "-" in token:
            parts = token.split("-", 1)
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                raise ValueError(f"Rango invalido: {token}")
            start, end = int(parts[0]), int(parts[1])
            if start > end:
                raise ValueError(f"Rango invalido: {token}")
            ids.extend(range(start, end + 1))
        elif token.isdigit():
            ids.append(int(token))
        else:
            raise ValueError(f"ID invalido: {token}")
    return sorted(set(ids))


def score_logo(url: str) -> int:
    url_lower = url.lower()
    score = 0
    if "upload.wikimedia.org" in url_lower:
        score += 100
    if "cdn.m3u.cl" in url_lower:
        score += 90
    if "logopedia" in url_lower or "wikia.nocookie.net" in url_lower:
        score += 40
    if url_lower.startswith("https://"):
        score += 10
    if "imgur.com" in url_lower:
        score += 20
    if url_lower.endswith(".svg") or ".svg." in url_lower:
        score += 5
    if url_lower.startswith("http://"):
        score -= 5
    return score


def lookup_logo_library(base_name: str) -> Optional[str]:
    base_lower = base_name.lower()
    clean_lower = base_lower

    if clean_lower in LOGO_LIBRARY:
        return LOGO_LIBRARY[clean_lower]
    if base_lower in LOGO_LIBRARY:
        return LOGO_LIBRARY[base_lower]

    for key, logo in LOGO_LIBRARY.items():
        if key in clean_lower or clean_lower in key:
            return logo
    return None


def names_match(target_base: str, candidate_name: str) -> bool:
    candidate_clean = clean_channel_name(candidate_name)
    candidate_base = get_channel_base(candidate_clean)
    return candidate_base.casefold() == target_base.casefold()


def collect_source_logos(timeout: float) -> dict[str, list[str]]:
    logos_by_base: dict[str, list[str]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(fetch_playlist, source, source_url, timeout)
            for source, source_url in SOURCE_PLAYLISTS
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result.error:
                continue
            for entry in result.entries:
                attrs, _ = parse_extinf(entry.extinf)
                logo = attrs.get("tvg-logo", "").strip()
                if not logo:
                    continue
                clean = clean_channel_name(entry.display_name or entry.tvg_name)
                base = get_channel_base(clean)
                logos_by_base.setdefault(base.casefold(), []).append(logo)

    return logos_by_base


def pick_best_logo(candidates: list[str]) -> Optional[str]:
    unique = sorted(set(candidates), key=lambda url: (-score_logo(url), url))
    return unique[0] if unique else None


def resolve_logo(
    base_name: str,
    source_logos: dict[str, list[str]],
    manual_logo: Optional[str] = None,
) -> tuple[Optional[str], str]:
    if manual_logo:
        return manual_logo, "manual"

    library_logo = lookup_logo_library(base_name)
    if library_logo:
        return library_logo, "logo_library"

    source_candidates = source_logos.get(base_name.casefold(), [])
    source_logo = pick_best_logo(source_candidates)
    if source_logo:
        return source_logo, "source_playlists"

    return None, "not_found"


def set_extinf_logo(extinf_line: str, logo_url: str) -> str:
    attrs, display_name = parse_extinf(extinf_line)
    attrs["tvg-logo"] = logo_url

    duration_match = re.match(r"#EXTINF:([^,]+)", extinf_line)
    duration = duration_match.group(1) if duration_match else "-1"

    attrs_str = "".join(f' {key}="{value}"' for key, value in attrs.items())
    return f"#EXTINF:{duration}{attrs_str},{display_name}"


def build_targets(entries: list[dict], requested_ids: set[int]) -> tuple[list[ChannelTarget], list[int]]:
    targets: list[ChannelTarget] = []
    found_ids: set[int] = set()

    for entry in entries:
        channel_id = extract_global_id(entry["extinf"])
        if channel_id is None or channel_id not in requested_ids:
            continue

        _, display_name = parse_extinf(entry["extinf"])
        clean_name = clean_channel_name(display_name)
        base_name = get_channel_base(clean_name)
        targets.append(
            ChannelTarget(
                channel_id=channel_id,
                clean_name=clean_name,
                base_name=base_name,
                display_name=display_name,
            )
        )
        found_ids.add(channel_id)

    missing = sorted(requested_ids - found_ids)
    return targets, missing


def write_official(entries: list[dict]) -> None:
    with open(OFFICIAL, "w", encoding="utf-8") as handle:
        handle.write("#EXTM3U\n\n")
        for entry in entries:
            handle.write(f"{entry['extinf']}\n")
            for option in entry["options"]:
                handle.write(f"{option}\n")
            handle.write(f"{entry['url']}\n\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set real tvg-logo URLs in official.m3u by global channel ID."
    )
    parser.add_argument(
        "ids",
        nargs="+",
        help="Global channel IDs (supports ranges like 88-92).",
    )
    parser.add_argument(
        "--logo",
        help="Force a specific logo URL for all requested channel bases.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Timeout in seconds when fetching source playlists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve logos without writing official.m3u.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable results.",
    )
    args = parser.parse_args()

    try:
        requested_ids = set(parse_id_tokens(args.ids))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    with open(OFFICIAL, encoding="utf-8") as handle:
        entries = parse_entries(handle.readlines())

    targets, missing = build_targets(entries, requested_ids)
    if missing:
        print(
            f"IDs no encontrados en official.m3u: {', '.join(map(str, missing))}",
            file=sys.stderr,
        )
        sys.exit(1)

    bases: dict[str, list[int]] = {}
    for target in targets:
        bases.setdefault(target.base_name, []).append(target.channel_id)

    source_logos = collect_source_logos(args.timeout)

    results: list[LogoResult] = []
    updates_by_base: dict[str, str] = {}

    for base_name, channel_ids in sorted(bases.items(), key=lambda item: min(item[1])):
        logo, source = resolve_logo(base_name, source_logos, args.logo)
        results.append(
            LogoResult(
                base_name=base_name,
                logo=logo,
                source=source,
                channel_ids=sorted(channel_ids),
            )
        )
        if logo:
            updates_by_base[base_name.casefold()] = logo

    updated_entries = 0
    for entry in entries:
        _, display_name = parse_extinf(entry["extinf"])
        clean_name = clean_channel_name(display_name)
        base_name = get_channel_base(clean_name)
        logo = updates_by_base.get(base_name.casefold())
        if not logo:
            continue
        new_extinf = set_extinf_logo(entry["extinf"], logo)
        if new_extinf != entry["extinf"]:
            entry["extinf"] = new_extinf
            updated_entries += 1

    if not args.dry_run and updates_by_base:
        write_official(entries)

    if args.json:
        payload = {
            "requested_ids": sorted(requested_ids),
            "updated_entries": updated_entries,
            "results": [
                {
                    "base_name": result.base_name,
                    "channel_ids": result.channel_ids,
                    "logo": result.logo,
                    "source": result.source,
                }
                for result in results
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if any(result.logo is None for result in results):
            sys.exit(2)
        return

    for result in results:
        if result.logo:
            print(
                f"[{result.source}] {result.base_name} "
                f"(IDs {', '.join(map(str, result.channel_ids))}): {result.logo}"
            )
        else:
            print(
                f"[not_found] {result.base_name} "
                f"(IDs {', '.join(map(str, result.channel_ids))}): sin logo"
            )

    if updated_entries:
        action = "Simulacion:" if args.dry_run else "Actualizado:"
        print(f"{action} {updated_entries} entrada(s) en official.m3u")
    elif args.dry_run:
        print("Simulacion: no hubo cambios en official.m3u")

    if any(result.logo is None for result in results):
        sys.exit(2)


if __name__ == "__main__":
    main()
