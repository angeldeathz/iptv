#!/usr/bin/env python3
"""Probe every stream URL in official.m3u; print JSON with dead channels only in the list."""
from __future__ import annotations

import argparse
import concurrent.futures
import http.client
import json
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from streams import (  # noqa: E402
    MPEGTS_SYNC_BYTE,
    PROBE_TIMEOUT_SECONDS,
    USER_AGENT,
    canonical_url,
)

EXTINF_ATTR_RE = re.compile(r'([\w\-]+)\s*=\s*"([^"]*)"')
# High parallelism starves home/Astra hosts and yields false timeouts on back-to-back runs.
DEFAULT_WORKERS = 8
VERIFY_ATTEMPTS = 3
# Reasons that often mean congestion, not a dead stream — must pass a slow sequential recheck.
AMBIGUOUS_REASONS = frozenset({"timeout", "connection_error", "no_stream"})
CLEAR_EOL = "\033[K"


class Progress:
    def __init__(self, total: int, entry_count: int) -> None:
        self.total = total
        self.entry_count = entry_count
        self.done = 0
        self.in_flight: list[tuple[str, str]] = []
        self._lock = threading.Lock()
        self._phase = "sondeo"

    def set_phase(self, phase: str, total: int | None = None) -> None:
        with self._lock:
            self._phase = phase
            if total is not None:
                self.total = total
                self.done = 0

    def start(self, key: str, label: str) -> None:
        with self._lock:
            self.in_flight.append((key, label))
            self._render_locked()

    def finish(self, key: str, reason: str | None, label: str) -> None:
        with self._lock:
            self.in_flight = [(k, name) for k, name in self.in_flight if k != key]
            self.done += 1
            self._render_locked(reason, label)

    def tick(self, reason: str | None, label: str) -> None:
        with self._lock:
            self.done += 1
            self._render_locked(reason, label)

    def _render_locked(self, last_reason: str | None = None, last_label: str = "") -> None:
        pct = (100 * self.done // self.total) if self.total else 100
        if self.in_flight:
            showing = self.in_flight[-1][1]
            extra = len(self.in_flight) - 1
            tail = f" (+{extra} en paralelo)" if extra > 0 else ""
            canal = f"comprobando: {showing}{tail}"
        elif self.done < self.total:
            canal = "comprobando: …"
        else:
            canal = "listo"
        status = ""
        if last_reason is not None and last_label:
            mark = "MUERTO" if last_reason else "OK"
            status = f" · {last_label}: {mark}"
        line = (
            f"\r{CLEAR_EOL}[{pct:3d}%] {self.done}/{self.total} "
            f"({self._phase}) · {canal}{status}"
        )
        sys.stderr.write(line)
        sys.stderr.flush()

    def close(self) -> None:
        with self._lock:
            sys.stderr.write(f"\r{CLEAR_EOL}\n")
            sys.stderr.flush()


def parse_official(path: Path) -> list[dict]:
    entries: list[dict] = []
    extinf: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            extinf = line
            continue
        if not line or line.startswith("#") or extinf is None:
            continue
        attrs = dict(EXTINF_ATTR_RE.findall(extinf))
        display = extinf.rsplit(",", 1)[-1].strip()
        label = attrs.get("tvg-name") or display
        match = re.match(r"^(\d+)\s", label)
        channel_id = int(match.group(1)) if match else 0
        entries.append(
            {
                "id": channel_id,
                "name": display,
                "group": attrs.get("group-title", ""),
                "url": line,
            }
        )
        extinf = None
    return entries


def probe_url(url: str, timeout: float) -> str | None:
    """None if the URL serves HLS or MPEG-TS; otherwise a short reason code."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=ssl.create_default_context()
        ) as response:
            chunk = response.read(512)
            content_type = (response.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        return f"http_{exc.code}"
    except urllib.error.URLError as exc:
        reason = str(exc.reason).lower()
        if "timed out" in reason or isinstance(exc.reason, TimeoutError):
            return "timeout"
        return "connection_error"
    except (OSError, http.client.HTTPException):
        return "timeout"
    if not chunk:
        return "empty"
    if chunk.startswith(b"#EXTM3U") or "mpegurl" in content_type:
        return None
    if not chunk.startswith(b"#") and MPEGTS_SYNC_BYTE in chunk[:400]:
        return None
    return "no_stream"


def probe_one(
    key: str, url: str, label: str, timeout: float, progress: Progress | None
) -> tuple[str, str | None]:
    if progress:
        progress.start(key, label)
    reason = probe_url(url, timeout)
    if progress:
        progress.finish(key, reason, label)
    return key, reason


def confirm_ambiguous(
    unique_urls: dict[str, str],
    reasons: dict[str, str | None],
    labels: dict[str, str],
    timeout: float,
    progress: Progress | None,
) -> None:
    suspects = [key for key, reason in reasons.items() if reason in AMBIGUOUS_REASONS]
    if not suspects:
        return

    verify_timeout = min(timeout * 1.5, 18.0)
    if progress:
        progress.set_phase("verificación", len(suspects))
        sys.stderr.write(
            f"\nRevisando {len(suspects)} URL con timeout/sospecha, una a una…\n"
        )
        sys.stderr.flush()

    for key in suspects:
        url = unique_urls[key]
        label = labels[key]
        final: str | None = reasons[key]
        for _ in range(VERIFY_ATTEMPTS):
            reason = probe_url(url, verify_timeout)
            if reason is None:
                final = None
                break
            if reason not in AMBIGUOUS_REASONS:
                final = reason
                break
            final = reason
            time.sleep(0.35)
        reasons[key] = final
        if progress:
            progress.tick(final, label)


def probe_dead(
    entries: list[dict], workers: int, timeout: float, progress: Progress | None
) -> list[dict]:
    unique_urls: dict[str, str] = {}
    labels: dict[str, str] = {}
    for entry in entries:
        key = canonical_url(entry["url"])
        unique_urls.setdefault(key, entry["url"])
        labels.setdefault(key, entry["name"])

    reasons: dict[str, str | None] = {}

    if progress:
        progress.set_phase("sondeo", len(unique_urls))

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(probe_one, key, url, labels[key], timeout, progress)
                for key, url in unique_urls.items()
            ]
            for future in concurrent.futures.as_completed(futures):
                key, reason = future.result()
                reasons[key] = reason

        confirm_ambiguous(unique_urls, reasons, labels, timeout, progress)
    finally:
        if progress:
            progress.close()

    dead: list[dict] = []
    for entry in entries:
        key = canonical_url(entry["url"])
        reason = reasons.get(key)
        if reason is not None:
            dead.append({**entry, "reason": reason})
    dead.sort(key=lambda row: row["id"])
    return dead


def resolve_progress_flag(args: argparse.Namespace) -> bool:
    if args.no_progress:
        return False
    if args.progress:
        return True
    return sys.stderr.isatty()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "playlist",
        nargs="?",
        type=Path,
        default=ROOT / "official.m3u",
        help="M3U playlist to probe (default: official.m3u)",
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=float, default=PROBE_TIMEOUT_SECONDS)
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show % and current channel on stderr (default: on when stderr is a TTY)",
    )
    parser.add_argument("--no-progress", action="store_true", help="No status on stderr")
    args = parser.parse_args()

    if not args.playlist.is_file():
        print(json.dumps({"error": f"playlist not found: {args.playlist}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    entries = parse_official(args.playlist)
    show_progress = resolve_progress_flag(args)
    unique = len({canonical_url(e["url"]) for e in entries})
    progress = Progress(unique, len(entries)) if show_progress else None
    dead = probe_dead(
        entries,
        workers=max(1, args.workers),
        timeout=args.timeout,
        progress=progress,
    )
    print(json.dumps({"dead": dead}, ensure_ascii=False))
    return 1 if dead else 0


if __name__ == "__main__":
    raise SystemExit(main())