"""Stream URL helpers (Astra MPEG-TS vs HLS) and search over Astra origin playlists."""
from __future__ import annotations

import concurrent.futures
import http.client
import re
import ssl
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
PROBE_TIMEOUT_SECONDS = 12.0
SEARCH_TIMEOUT_SECONDS = 15.0
SEARCH_WORKERS = 12
MPEGTS_SYNC_BYTE = b"\x47"
ASTRA_PLAY_RE = re.compile(r"^(https?://[^/\s]+)/play/([^/?#\s]+)", re.IGNORECASE)
EXTINF_ATTR_RE = re.compile(r'([\w\-]+)\s*=\s*"([^"]*)"')

# Astra servers that publish their full catalog at /playlist.m3u (verified October 2026).
SOURCE_PLAYLISTS = (
    "170.244.209.30:8000",
    "186.33.1.71:8000",
    "181.78.8.199:8000",
    "45.173.231.22:8000",
    "38.44.109.41:8003",
    "157.100.9.51:8000",
    "45.167.1.137:8000",
    "45.167.1.138:8000",
    "190.60.40.165:1010",
    "72.1.184.5:8089",
    "45.186.254.75:8000",
    "38.224.48.4:8000",
    "45.5.118.152:8000",
    "190.108.83.69:8000",
    "209.14.98.47:8000",
    "38.226.49.253:8000",
    "181.224.255.210:8001",
    "45.5.116.228:8000",
    "190.61.43.117:45000",
    "187.102.211.240:9001",
    "190.61.42.218:9000",
    "190.14.10.19:16000",
    "170.247.204.9:8000",
    "181.78.20.119:58002",
    "205.235.6.29:8000",
    "177.74.205.189:8000",
    "45.232.210.1:18000",
    "181.224.200.5:2277",
    "190.108.90.142:8000",
    "38.225.116.4:22000",
)


def is_astra_play_url(url: str) -> bool:
    return ASTRA_PLAY_RE.match(url.strip()) is not None


def astra_mpegts_url(url: str) -> str:
    match = ASTRA_PLAY_RE.match(url.strip())
    if not match:
        return url.strip()
    return f"{match.group(1)}/play/{match.group(2)}"


def canonical_url(url: str) -> str:
    """Identity used to detect duplicates: HLS and MPEG-TS forms of one Astra id are the same stream."""
    if is_astra_play_url(url):
        return astra_mpegts_url(url)
    return url.strip().split("?", 1)[0]


def resolve_stream_url(url: str) -> str:
    """SS IPTV only shows the audio language menu for MPEG-TS, so prefer it and fall back to HLS."""
    stripped = url.strip()
    if not is_astra_play_url(stripped):
        return stripped
    mpegts = astra_mpegts_url(stripped)
    if serves_mpegts(mpegts):
        return mpegts
    return f"{mpegts}/index.m3u8"


def search_sources(matches_query, hosts: tuple[str, ...] = SOURCE_PLAYLISTS) -> dict:
    """Fetch every origin playlist and return entries accepted by `matches_query(name, group, url)`."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        fetched = list(executor.map(fetch_source_playlist, hosts))

    matches = []
    failed_sources = []
    for host, entries, error in fetched:
        if error:
            failed_sources.append({"source": host, "error": error})
            continue
        for entry in entries:
            if matches_query(entry["name"], entry["group"], entry["url"]):
                matches.append({"source": host, **entry})
    return {"matches": matches, "failed_sources": failed_sources}


def serves_mpegts(url: str) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(
            request, timeout=PROBE_TIMEOUT_SECONDS, context=ssl.create_default_context()
        ) as response:
            chunk = response.read(512)
            content_type = (response.headers.get("Content-Type") or "").lower()
    except (OSError, http.client.HTTPException):
        return False
    if not chunk or chunk.startswith(b"#") or "mpegurl" in content_type:
        return False
    return MPEGTS_SYNC_BYTE in chunk[:400]


def fetch_source_playlist(host: str) -> tuple[str, list, str]:
    request = urllib.request.Request(
        f"http://{host}/playlist.m3u", headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    try:
        with urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        return host, [], f"HTTP {exc.code}"
    except (OSError, http.client.HTTPException) as exc:
        return host, [], str(getattr(exc, "reason", exc))
    if not text.strip():
        return host, [], "empty playlist"
    return host, parse_source_playlist(text), ""


def parse_source_playlist(text: str) -> list:
    entries = []
    extinf = None
    options: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            extinf = line
            options = []
        elif line.startswith("#EXTVLCOPT:"):
            options.append(line)
        elif not line.startswith("#") and extinf:
            attrs, name = parse_extinf(extinf)
            entries.append(
                {
                    "name": name,
                    "group": attrs.get("group-title", ""),
                    "logo": attrs.get("tvg-logo", ""),
                    "url": astra_mpegts_url(line) if is_astra_play_url(line) else line,
                    "vlc_options": options,
                }
            )
            extinf = None
            options = []
    return entries


def parse_extinf(extinf: str) -> tuple[dict, str]:
    in_quotes = False
    for index, char in enumerate(extinf):
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            return dict(EXTINF_ATTR_RE.findall(extinf[:index])), extinf[index + 1 :].strip()
    return dict(EXTINF_ATTR_RE.findall(extinf)), ""
