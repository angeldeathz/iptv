#!/usr/bin/env python3
"""SS IPTV dual-audio fix for Astra HTTP Play streams.

SS IPTV on Smart TVs only shows the language menu for MPEG-TS
(`/play/<id>`), not for HLS (`/play/<id>/index.m3u8`). Spanish is forced
as the default track with audio-track="spa,eng".
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from typing import Optional

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
SSIPTV_AUDIO_TRACK = "spa,eng"
ASTRA_PLAY_RE = re.compile(
    r"^(https?://[^/\s]+(?::\d+)?)/play/([^/?#]+)",
    re.IGNORECASE,
)
CTX = ssl.create_default_context()


def is_astra_play_url(url: str) -> bool:
    return ASTRA_PLAY_RE.match(url.strip()) is not None


def astra_mpegts_url(url: str) -> str:
    """MPEG-TS form: http://host:port/play/<id>"""
    match = ASTRA_PLAY_RE.match(url.strip())
    if not match:
        return url.strip()
    return f"{match.group(1)}/play/{match.group(2)}"


def astra_hls_url(url: str) -> str:
    """HLS form: http://host:port/play/<id>/index.m3u8"""
    mpegts = astra_mpegts_url(url)
    if mpegts == url.strip() and not is_astra_play_url(url):
        return url.strip()
    return f"{mpegts}/index.m3u8"


def canonical_stream_url(url: str) -> str:
    """Same identity for HLS and MPEG-TS variants of one Astra play id."""
    stripped = url.strip()
    if is_astra_play_url(stripped):
        return astra_mpegts_url(stripped)
    path = stripped.split("?", 1)[0]
    return re.sub(r"(\.m3u8)+$", ".m3u8", path, flags=re.IGNORECASE)


def ensure_ssiptv_audio_track(attrs: dict) -> dict:
    attrs["audio-track"] = SSIPTV_AUDIO_TRACK
    return attrs


def probe_mpegts_url(url: str, timeout: float = 12.0) -> bool:
    """True when the MPEG-TS URL returns a transport stream, not HLS/404."""
    mpegts = astra_mpegts_url(url)
    request = urllib.request.Request(
        mpegts,
        headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=CTX) as response:
            chunk = response.read(512)
            content_type = (response.headers.get("Content-Type") or "").lower()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False

    if not chunk:
        return False
    if chunk.startswith(b"#") or b"#EXTM3U" in chunk[:64]:
        return False
    if "mpegurl" in content_type:
        return False
    return b"\x47" in chunk[:400]


def resolve_astra_play_url(url: str, timeout: float = 12.0) -> str:
    """Prefer MPEG-TS; keep HLS when the server does not expose MPEG-TS."""
    stripped = url.strip()
    if not is_astra_play_url(stripped):
        return stripped
    path = stripped.split("?", 1)[0]
    already_mpegts = not path.lower().endswith(".m3u8")
    if probe_mpegts_url(stripped, timeout=timeout):
        return astra_mpegts_url(stripped)
    if already_mpegts:
        return astra_mpegts_url(stripped)
    return path


def _rewrite_extinf_audio_track(extinf: str) -> str:
    if re.search(r'\baudio-track\s*=\s*"', extinf, re.IGNORECASE):
        return re.sub(
            r'\baudio-track\s*=\s*"[^"]*"',
            f'audio-track="{SSIPTV_AUDIO_TRACK}"',
            extinf,
            count=1,
            flags=re.IGNORECASE,
        )

    comma_idx = -1
    in_quotes = False
    for idx, char in enumerate(extinf):
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            comma_idx = idx
            break
    if comma_idx == -1:
        return f'{extinf} audio-track="{SSIPTV_AUDIO_TRACK}"'
    return (
        extinf[:comma_idx]
        + f' audio-track="{SSIPTV_AUDIO_TRACK}"'
        + extinf[comma_idx:]
    )


def apply_ssiptv_fix(
    file_path: str,
    timeout: float = 12.0,
    workers: int = 8,
) -> dict:
    """Rewrite Astra entries in an M3U: MPEG-TS when available, audio-track always."""
    with open(file_path, encoding="utf-8") as handle:
        lines = handle.readlines()

    url_indexes: list[tuple[int, str, str]] = []
    pending_extinf: Optional[int] = None
    pending_name = "?"

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#EXTINF:"):
            pending_extinf = idx
            match = re.search(r'tvg-name="([^"]+)"', stripped)
            pending_name = match.group(1) if match else "?"
            continue
        if stripped.startswith("#") or not stripped:
            continue
        if pending_extinf is None:
            continue
        url_indexes.append((idx, stripped, pending_name))
        pending_extinf = None

    astra_items = [
        (idx, url, name)
        for idx, url, name in url_indexes
        if is_astra_play_url(url)
    ]

    resolved: dict[int, str] = {}
    mpegts_ok = 0
    hls_kept = 0

    def resolve_one(item: tuple[int, str, str]) -> tuple[int, str, bool]:
        idx, url, _name = item
        new_url = resolve_astra_play_url(url, timeout=timeout)
        return idx, new_url, new_url == astra_mpegts_url(url) and not new_url.lower().endswith(".m3u8")

    if astra_items:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(workers, len(astra_items)))
        ) as executor:
            for idx, new_url, used_mpegts in executor.map(resolve_one, astra_items):
                resolved[idx] = new_url
                if used_mpegts:
                    mpegts_ok += 1
                else:
                    hls_kept += 1

    audio_track_set = 0
    pending_extinf = None
    out_lines: list[str] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#EXTINF:"):
            pending_extinf = len(out_lines)
            out_lines.append(line)
            continue
        if pending_extinf is not None and stripped and not stripped.startswith("#"):
            url = resolved.get(idx, stripped)
            if is_astra_play_url(url):
                extinf_line = out_lines[pending_extinf]
                newline = "\n" if extinf_line.endswith("\n") else ""
                out_lines[pending_extinf] = _rewrite_extinf_audio_track(
                    extinf_line.rstrip("\n")
                ) + newline
                audio_track_set += 1
            out_lines.append(url + ("\n" if line.endswith("\n") else ""))
            pending_extinf = None
            continue
        out_lines.append(line)

    with open(file_path, "w", encoding="utf-8") as handle:
        handle.writelines(out_lines)

    return {
        "path": file_path,
        "astra": len(astra_items),
        "mpegts": mpegts_ok,
        "hls_fallback": hls_kept,
        "audio_track": audio_track_set,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aplica MPEG-TS + audio-track=spa,eng a canales Astra de una lista M3U "
            "(requerido para cambiar idioma en SS IPTV)."
        )
    )
    parser.add_argument(
        "playlist",
        nargs="?",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "official.m3u"),
        help="Lista M3U a corregir (default: official.m3u)",
    )
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    playlist = os.path.abspath(args.playlist)
    if not os.path.exists(playlist):
        print(f"Error: no existe {playlist}", file=sys.stderr)
        return 2

    stats = apply_ssiptv_fix(playlist, timeout=args.timeout, workers=args.workers)
    print(
        f"SS IPTV audio fix: {stats['astra']} Astra, "
        f"{stats['mpegts']} MPEG-TS, "
        f"{stats['hls_fallback']} HLS fallback, "
        f"{stats['audio_track']} audio-track."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
