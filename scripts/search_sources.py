#!/usr/bin/env python3
"""Busca canales por nombre en todas las listas M3U de origen."""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from clean_m3u import parse_extinf

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Servidores verificados que publican catálogo completo en /playlist.m3u
SOURCE_PLAYLISTS = [
    ("38.44.109.41:8003", "http://38.44.109.41:8003/playlist.m3u"),
    ("190.60.40.165:1010", "http://190.60.40.165:1010/playlist.m3u"),
    ("38.226.49.253:8000", "http://38.226.49.253:8000/playlist.m3u"),
    ("190.61.42.218:9000", "http://190.61.42.218:9000/playlist.m3u"),
    ("187.102.211.240:9001", "http://187.102.211.240:9001/playlist.m3u"),
    ("177.74.205.189:8000", "http://177.74.205.189:8000/playlist.m3u"),
    ("181.224.200.5:2277", "http://181.224.200.5:2277/playlist.m3u"),
]


@dataclass
class SourceEntry:
    source: str
    source_url: str
    extinf: str
    display_name: str
    tvg_name: str
    group: str
    url: str
    user_agent: Optional[str] = None
    vlc_options: list[str] = field(default_factory=list)


@dataclass
class OfficialMatch:
    channel_id: int
    name: str
    url: str


@dataclass
class FetchResult:
    source: str
    source_url: str
    entries: list[SourceEntry]
    error: Optional[str] = None


def parse_user_agent(option_line: str) -> Optional[str]:
    match = re.search(r"http-user-agent=(.+)$", option_line, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def parse_playlist_text(source: str, source_url: str, text: str) -> list[SourceEntry]:
    entries: list[SourceEntry] = []
    current_extinf: Optional[str] = None
    current_user_agent: Optional[str] = None
    current_vlc_options: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF:"):
            current_extinf = line
            current_user_agent = None
            current_vlc_options = []
            continue

        if line.startswith("#EXTVLCOPT:"):
            current_vlc_options.append(line)
            user_agent = parse_user_agent(line)
            if user_agent:
                current_user_agent = user_agent
            continue

        if line.startswith("#"):
            continue

        if not current_extinf:
            continue

        attrs, display_name = parse_extinf(current_extinf)
        entries.append(
            SourceEntry(
                source=source,
                source_url=source_url,
                extinf=current_extinf,
                display_name=display_name.strip(),
                tvg_name=attrs.get("tvg-name", display_name).strip(),
                group=attrs.get("group-title", "").strip(),
                url=line,
                user_agent=current_user_agent,
                vlc_options=list(current_vlc_options),
            )
        )
        current_extinf = None
        current_user_agent = None
        current_vlc_options = []

    return entries


def fetch_playlist(source: str, source_url: str, timeout: float) -> FetchResult:
    request = urllib.request.Request(
        source_url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        return FetchResult(source, source_url, [], f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        reason = exc.reason
        return FetchResult(source, source_url, [], str(reason) if reason else "Error de red")
    except TimeoutError:
        return FetchResult(source, source_url, [], "Timeout")
    except Exception as exc:  # noqa: BLE001
        return FetchResult(source, source_url, [], str(exc))

    if not text.strip():
        return FetchResult(source, source_url, [], "Lista vacia")

    return FetchResult(source, source_url, parse_playlist_text(source, source_url, text))


def load_official_urls(official_path: str) -> tuple[set[str], dict[str, OfficialMatch]]:
    urls: set[str] = set()
    by_url: dict[str, OfficialMatch] = {}
    current_extinf: Optional[str] = None

    with open(official_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line.startswith("#EXTINF:"):
                current_extinf = line
                continue
            if not line or line.startswith("#"):
                continue
            if not current_extinf:
                continue

            attrs, display_name = parse_extinf(current_extinf)
            tvg_name = attrs.get("tvg-name", display_name).strip()
            channel_id = None
            for candidate in (tvg_name, display_name):
                match = re.match(r"^(\d+)\s+", candidate)
                if match:
                    channel_id = int(match.group(1))
                    break

            urls.add(line)
            if channel_id is not None:
                by_url[line] = OfficialMatch(
                    channel_id=channel_id,
                    name=tvg_name or display_name,
                    url=line,
                )
            current_extinf = None

    return urls, by_url


def build_matcher(query: str, use_regex: bool):
    if use_regex:
        pattern = re.compile(query, re.IGNORECASE)

        def matches(entry: SourceEntry) -> bool:
            haystack = " ".join(
                part for part in (entry.display_name, entry.tvg_name, entry.group, entry.url) if part
            )
            return pattern.search(haystack) is not None

        return matches

    needle = query.casefold()

    def matches(entry: SourceEntry) -> bool:
        for part in (entry.display_name, entry.tvg_name, entry.group, entry.url):
            if needle in part.casefold():
                return True
        return False

    return matches


def filter_sources(selected: Optional[list[str]]) -> list[tuple[str, str]]:
    if not selected:
        return SOURCE_PLAYLISTS

    wanted = {item.casefold() for item in selected}
    filtered = [
        (source, url)
        for source, url in SOURCE_PLAYLISTS
        if source.casefold() in wanted or any(part in source.casefold() for part in wanted)
    ]
    return filtered


def format_entry_block(
    entry: SourceEntry,
    index: int,
    official_by_url: dict[str, OfficialMatch],
) -> list[str]:
    lines = [f"  {index}. {entry.display_name or entry.tvg_name}"]
    if entry.group:
        lines[-1] += f"  [{entry.group}]"
    if entry.tvg_name and entry.tvg_name != entry.display_name:
        lines.append(f"     tvg-name: {entry.tvg_name}")

    official = official_by_url.get(entry.url)
    if official:
        lines.append(f"     EN LISTA -> ID {official.channel_id}  {official.name}")
    else:
        lines.append("     (nueva fuente)")

    lines.append(f"     {entry.url}")
    if entry.vlc_options:
        for option in entry.vlc_options:
            lines.append(f"     {option}")
    return lines


def print_results(
    query: str,
    fetch_results: list[FetchResult],
    official_by_url: dict[str, OfficialMatch],
    matcher,
) -> int:
    total_matches = 0
    sources_with_matches = 0
    failed_sources: list[FetchResult] = []

    print(f'Buscando: "{query}"\n')

    for result in fetch_results:
        if result.error:
            failed_sources.append(result)
            continue

        matches = [entry for entry in result.entries if matcher(entry)]
        if not matches:
            continue

        sources_with_matches += 1
        total_matches += len(matches)
        print(f"=== {result.source} ({len(matches)} coincidencia{'s' if len(matches) != 1 else ''}) ===")
        for index, entry in enumerate(matches, start=1):
            for line in format_entry_block(entry, index, official_by_url):
                print(line)
            print()

    if failed_sources:
        print("--- Fuentes no disponibles ---")
        for result in failed_sources:
            print(f"  {result.source}: {result.error}")
        print()

    if total_matches == 0:
        print("No se encontraron coincidencias.")
    else:
        print(
            f"Total: {total_matches} coincidencia{'s' if total_matches != 1 else ''} "
            f"en {sources_with_matches} fuente{'s' if sources_with_matches != 1 else ''}"
        )

    return total_matches


def print_json(
    query: str,
    fetch_results: list[FetchResult],
    official_by_url: dict[str, OfficialMatch],
    matcher,
) -> int:
    payload = {
        "query": query,
        "sources": [],
        "total_matches": 0,
        "failed_sources": [],
    }

    for result in fetch_results:
        if result.error:
            payload["failed_sources"].append(
                {"source": result.source, "url": result.source_url, "error": result.error}
            )
            continue

        matches = []
        for entry in result.entries:
            if not matcher(entry):
                continue

            official = official_by_url.get(entry.url)
            matches.append(
                {
                    "display_name": entry.display_name,
                    "tvg_name": entry.tvg_name,
                    "group": entry.group,
                    "url": entry.url,
                    "extinf": entry.extinf,
                    "vlc_options": entry.vlc_options,
                    "in_official": official is not None,
                    "official_id": official.channel_id if official else None,
                    "official_name": official.name if official else None,
                }
            )

        if matches:
            payload["sources"].append(
                {
                    "source": result.source,
                    "url": result.source_url,
                    "matches": matches,
                }
            )
            payload["total_matches"] += len(matches)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload["total_matches"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Busca un canal en todas las listas M3U de origen verificadas."
    )
    parser.add_argument(
        "query",
        help='Texto a buscar (ej: "star channel", "mega", "espn 2")',
    )
    parser.add_argument(
        "--regex",
        action="store_true",
        help="Interpretar la consulta como expresion regular",
    )
    parser.add_argument(
        "--source",
        action="append",
        metavar="HOST",
        help="Limitar la busqueda a una fuente (puede repetirse). Ej: 38.44.109.41:8003",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Segundos de espera por fuente (por defecto: 15)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=7,
        help="Descargas en paralelo (por defecto: 7)",
    )
    parser.add_argument(
        "--official",
        default=os.path.join(os.path.dirname(__file__), "..", "official.m3u"),
        help="Ruta a official.m3u para marcar fuentes ya usadas",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en JSON",
    )
    args = parser.parse_args()

    if not args.query.strip():
        print("Error: la consulta no puede estar vacia.", file=sys.stderr)
        return 2

    sources = filter_sources(args.source)
    if not sources:
        print("Error: ninguna fuente coincide con --source.", file=sys.stderr)
        return 2

    official_path = os.path.abspath(args.official)
    if not os.path.exists(official_path):
        print(f"Error: no existe {official_path}", file=sys.stderr)
        return 2

    _, official_by_url = load_official_urls(official_path)
    matcher = build_matcher(args.query, args.regex)

    fetch_results: list[FetchResult] = []
    workers = max(1, min(args.workers, len(sources)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(fetch_playlist, source, url, args.timeout)
            for source, url in sources
        ]
        for future in concurrent.futures.as_completed(futures):
            fetch_results.append(future.result())

    fetch_results.sort(key=lambda item: item.source)

    if args.json:
        total = print_json(args.query, fetch_results, official_by_url, matcher)
    else:
        total = print_results(args.query, fetch_results, official_by_url, matcher)

    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
