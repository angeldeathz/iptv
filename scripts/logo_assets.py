#!/usr/bin/env python3
"""Shared logo URL checks, candidate discovery, and assets/logos.json I/O."""
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
ASSETS_PATH = os.path.join(REPO_ROOT, "assets", "logos.json")

USER_AGENT = "Mozilla/5.0 (compatible; iptv-logo-check/1.0)"
MIN_IMAGE_BYTES = 400
IMAGE_CONTENT_TYPES = ("image/",)


def load_assets() -> dict:
    if not os.path.exists(ASSETS_PATH):
        return {}
    with open(ASSETS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_assets(data: dict) -> None:
    os.makedirs(os.path.dirname(ASSETS_PATH), exist_ok=True)
    with open(ASSETS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def assets_url_map() -> dict[str, str]:
    """Map lowercase channel base name -> working logo URL."""
    result = {}
    for key, entry in load_assets().items():
        if isinstance(entry, dict) and entry.get("url"):
            result[key.lower()] = entry["url"]
    return result


def slug_variants(clean_name: str) -> list[str]:
    base = clean_name.lower().strip()
    compact = re.sub(r"[^a-z0-9]", "", base)
    hyphen = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    slugs = []
    for value in (compact, hyphen):
        if value and value not in slugs:
            slugs.append(value)
    parts = base.split()
    if parts:
        first = re.sub(r"[^a-z0-9]", "", parts[0])
        if first and first not in slugs:
            slugs.append(first)
    return slugs


def build_candidates(clean_name: str) -> list[tuple[str, str]]:
    """Return (source_label, url) pairs to probe, best-first."""
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    def add(source: str, url: str) -> None:
        if url not in seen_urls:
            seen_urls.add(url)
            candidates.append((source, url))

    for slug in slug_variants(clean_name):
        add("docdog_latino", f"https://docdog.top/logo/countries/latino/{slug}.png")
        add("docdog_argentina", f"https://docdog.top/logo/countries/argentina/{slug}.png")
        add("docdog_argentina_ar", f"https://docdog.top/logo/countries/argentina/{slug}-ar.png")
        add(
            "tv_logos_us",
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/{slug}-us.png",
        )
        add(
            "tv_logos_uk",
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-kingdom/{slug}-uk.png",
        )
        add(
            "tv_logos_international",
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/international/{slug}-int.png",
        )

    return candidates


def check_url(url: str, timeout: float = 12.0) -> tuple[bool, int | None, str]:
    """Verify a logo URL returns a real image (GET, not HEAD — Wikipedia blocks HEAD)."""
    if not url or not url.startswith(("http://", "https://")):
        return False, None, ""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=timeout, context=ctx) as response:
            status = getattr(response, "status", response.getcode())
            content_type = (response.headers.get("Content-Type") or "").lower()
            body = response.read(MIN_IMAGE_BYTES + 1)
            size = len(body)
    except urllib.error.HTTPError as exc:
        return False, exc.code, ""
    except Exception:
        return False, None, ""

    if status != 200:
        return False, status, content_type
    if size < MIN_IMAGE_BYTES:
        return False, status, content_type
    if content_type and not any(content_type.startswith(t) for t in IMAGE_CONTENT_TYPES):
        # Some hosts omit Content-Type; accept if we got enough bytes and status 200.
        if content_type.startswith("text/"):
            return False, status, content_type
    return True, status, content_type


def find_working_logo(
    clean_name: str,
    current_url: str = "",
    extra_candidates: list[tuple[str, str]] | None = None,
) -> tuple[str | None, str | None]:
    """
    Find a working logo URL for a channel base name.
    Returns (url, source_label) or (None, None).
    """
    base_key = clean_name.lower().strip()
    assets = load_assets()

    probes: list[tuple[str, str]] = []

    asset_entry = assets.get(base_key)
    if isinstance(asset_entry, dict) and asset_entry.get("url"):
        probes.append(("assets", asset_entry["url"]))

    if current_url:
        probes.append(("current", current_url))

    if extra_candidates:
        probes.extend(extra_candidates)

    probes.extend(build_candidates(clean_name))

    seen: set[str] = set()
    for source, url in probes:
        if url in seen:
            continue
        seen.add(url)
        ok, _, _ = check_url(url)
        if ok:
            return url, source

    return None, None


def record_asset(channel: str, url: str, source: str) -> None:
    data = load_assets()
    key = channel.lower().strip()
    data[key] = {
        "channel": channel,
        "url": url,
        "source": source,
        "verified_at": date.today().isoformat(),
    }
    save_assets(data)
