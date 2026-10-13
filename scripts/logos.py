"""assets/logos.json: the single source of channel logos, keyed by exact channel name."""
from __future__ import annotations

import http.client
import json
import os
import re
import ssl
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOGOS_PATH = os.path.join(REPO_ROOT, "assets", "logos.json")
USER_AGENT = "Mozilla/5.0 (compatible; iptv-logo-check/1.0)"
CHECK_TIMEOUT_SECONDS = 12.0
MIN_IMAGE_BYTES = 400


def load_logos() -> dict:
    if not os.path.exists(LOGOS_PATH):
        return {}
    with open(LOGOS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def save_logos(logo_by_channel: dict) -> None:
    ordered = dict(sorted(logo_by_channel.items(), key=lambda item: item[0].casefold()))
    with open(LOGOS_PATH, "w", encoding="utf-8") as handle:
        json.dump(ordered, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def is_working_logo(url: str) -> bool:
    """GET instead of HEAD because Wikipedia and other hosts reject HEAD requests."""
    if not url.startswith(("http://", "https://")):
        return False
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=CHECK_TIMEOUT_SECONDS, context=ssl.create_default_context()
        ) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            body = response.read(MIN_IMAGE_BYTES + 1)
    except (OSError, http.client.HTTPException):
        return False
    return len(body) > MIN_IMAGE_BYTES and not content_type.startswith("text/")


def find_working_logo(channel_name: str, rejected_url: str = "") -> str:
    for url in build_candidate_urls(channel_name):
        if url != rejected_url and is_working_logo(url):
            return url
    return ""


def build_candidate_urls(channel_name: str) -> list[str]:
    candidates: list[str] = []
    for slug in build_slugs(channel_name):
        candidates += [
            f"https://docdog.top/logo/countries/latino/{slug}.png",
            f"https://docdog.top/logo/countries/argentina/{slug}.png",
            f"https://docdog.top/logo/countries/argentina/{slug}-ar.png",
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/{slug}-us.png",
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-kingdom/{slug}-uk.png",
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/international/{slug}-int.png",
        ]
    return candidates


def build_slugs(channel_name: str) -> list[str]:
    lowered = channel_name.lower().strip()
    first_word = lowered.split()[0] if lowered.split() else ""
    slugs: list[str] = []
    for slug in (
        re.sub(r"[^a-z0-9]", "", lowered),
        re.sub(r"[^a-z0-9]+", "-", lowered).strip("-"),
        re.sub(r"[^a-z0-9]", "", first_word),
    ):
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs
