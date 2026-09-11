#!/usr/bin/env python3
"""Comprueba la disponibilidad de los canales en una lista M3U."""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from clean_m3u import parse_extinf

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class Channel:
    channel_id: int
    name: str
    url: str
    user_agent: str
    group: str


@dataclass
class CheckResult:
    channel: Channel
    available: bool
    detail: str


def parse_user_agent(option_line: str) -> Optional[str]:
    match = re.search(r"http-user-agent=(.+)$", option_line, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_channel_id(tvg_name: str, display_name: str) -> Optional[int]:
    for candidate in (tvg_name, display_name):
        match = re.match(r"^(\d+)\s+", candidate.strip())
        if match:
            return int(match.group(1))
    return None


def parse_m3u(file_path: str) -> list[Channel]:
    channels: list[Channel] = []
    current_extinf: Optional[str] = None
    current_user_agent = DEFAULT_USER_AGENT

    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line_str = line.strip()
            if not line_str or line_str.startswith("#EXTM3U"):
                continue

            if line_str.startswith("#EXTINF:"):
                current_extinf = line_str
                current_user_agent = DEFAULT_USER_AGENT
                continue

            if line_str.startswith("#EXTVLCOPT:"):
                user_agent = parse_user_agent(line_str)
                if user_agent:
                    current_user_agent = user_agent
                continue

            if line_str.startswith("#"):
                continue

            if not current_extinf:
                continue

            attrs, display_name = parse_extinf(current_extinf)
            tvg_name = attrs.get("tvg-name", display_name)
            channel_id = extract_channel_id(tvg_name, display_name)
            if channel_id is None:
                current_extinf = None
                continue

            channels.append(
                Channel(
                    channel_id=channel_id,
                    name=tvg_name.strip() or display_name.strip(),
                    url=line_str,
                    user_agent=current_user_agent,
                    group=attrs.get("group-title", ""),
                )
            )
            current_extinf = None

    return channels


def check_url(url: str, timeout: float, user_agent: str) -> tuple[bool, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "*/*",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            if status >= 400:
                return False, f"HTTP {status}"

            chunk = response.read(4096)
            if not chunk:
                return False, "Respuesta vacia"

            return True, "OK"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = exc.reason
        return False, str(reason) if reason else "Error de red"
    except TimeoutError:
        return False, "Timeout"
    except Exception as exc:  # noqa: BLE001 - report any unexpected failure
        return False, str(exc)


def check_channel(channel: Channel, timeout: float) -> CheckResult:
    available, detail = check_url(channel.url, timeout, channel.user_agent)
    return CheckResult(channel=channel, available=available, detail=detail)


def print_results(results: list[CheckResult], show_all: bool) -> None:
    down = [result for result in results if not result.available]
    up = [result for result in results if result.available]

    if show_all:
        print(f"Verificados: {len(results)} | OK: {len(up)} | Caidos: {len(down)}\n")
        for result in sorted(results, key=lambda item: item.channel.channel_id):
            status = "OK" if result.available else "CAIDO"
            print(
                f"[{status}] ID {result.channel.channel_id:>3}  "
                f"{result.channel.name}  ({result.detail})"
            )
        print()
        return

    if not down:
        print(f"Todos los canales respondieron correctamente ({len(results)} verificados).")
        return

    print(f"Canales caidos ({len(down)} de {len(results)}):\n")
    for result in sorted(down, key=lambda item: item.channel.channel_id):
        print(
            f"  ID {result.channel.channel_id:>3}  "
            f"{result.channel.name}  — {result.detail}"
        )


def print_json(results: list[CheckResult]) -> None:
    payload = {
        "total": len(results),
        "available": sum(1 for result in results if result.available),
        "down": sum(1 for result in results if not result.available),
        "channels_down": [
            {
                "id": result.channel.channel_id,
                "name": result.channel.name,
                "group": result.channel.group,
                "url": result.channel.url,
                "error": result.detail,
            }
            for result in sorted(results, key=lambda item: item.channel.channel_id)
            if not result.available
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_playlist = os.path.join(script_dir, "..", "official.m3u")

    parser = argparse.ArgumentParser(
        description="Revisa que canales de una lista M3U no estan disponibles."
    )
    parser.add_argument(
        "playlist",
        nargs="?",
        default=default_playlist,
        help="Ruta al archivo M3U (por defecto: official.m3u)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Segundos de espera por canal (por defecto: 10)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=15,
        help="Revisiones en paralelo (por defecto: 15)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Mostrar todos los canales, no solo los caidos",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en JSON",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Revisar solo los primeros N canales (util para pruebas)",
    )
    args = parser.parse_args()

    playlist = os.path.abspath(args.playlist)
    if not os.path.exists(playlist):
        print(f"Error: no existe el archivo {playlist}", file=sys.stderr)
        return 2

    channels = parse_m3u(playlist)
    if args.limit > 0:
        channels = channels[: args.limit]

    if not channels:
        print("No se encontraron canales en la lista.", file=sys.stderr)
        return 2

    workers = max(1, args.workers)
    results: list[CheckResult] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(check_channel, channel, args.timeout)
            for channel in channels
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    if args.json:
        print_json(results)
    else:
        print_results(results, show_all=args.all)

    down_count = sum(1 for result in results if not result.available)
    return 1 if down_count else 0


if __name__ == "__main__":
    sys.exit(main())
