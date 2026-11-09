"""assets/stream_audio.json: per Astra source, which languages it carries and which URL form to store.

Keyed by the bare /play/<id> URL. `form` is what add/set-url must write:
- mpegts: no .m3u8, so the TV can offer both languages (Spanish is the first track)
- hls: index.m3u8 (faster). Required when the server 404s without it. Safe when there is only one language.
"""
from __future__ import annotations

import http.client
import json
import os
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import streams

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
AUDIO_PATH = os.path.join(REPO_ROOT, "assets", "stream_audio.json")
SPANISH = frozenset({"spa", "es", "esp"})
ENGLISH = frozenset({"eng", "en"})
AUDIO_TYPES = frozenset({0x03, 0x04, 0x0F, 0x11, 0x81, 0x06, 0x87})


def load_audio() -> dict:
    if not os.path.exists(AUDIO_PATH):
        return {}
    with open(AUDIO_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def save_audio(catalog: dict) -> None:
    ordered = dict(sorted(catalog.items(), key=lambda item: item[0]))
    with open(AUDIO_PATH, "w", encoding="utf-8") as handle:
        json.dump(ordered, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def preferred_astra_url(url: str) -> str:
    """URL form to store. Known sources follow the catalog; a new one is classified once."""
    mpegts = streams.astra_mpegts_url(url)
    hls = streams.astra_hls_url(url)
    record = load_audio().get(mpegts)
    if record and record.get("delivery") != "down":
        return hls if record.get("form") == "hls" else mpegts

    record = classify_source(mpegts)
    if record["delivery"] == "down":
        if "/index.m3u8" in url.lower():
            return hls
        if streams.serves_mpegts(mpegts):
            return mpegts
        if streams.serves_hls(hls):
            return hls
        return mpegts

    catalog = load_audio()
    catalog[mpegts] = record
    save_audio(catalog)
    return hls if record["form"] == "hls" else mpegts


def classify_lineup(entries: list[tuple[str, str]], refresh: bool = False) -> dict:
    """Classify (channel name, url) pairs. Returns the catalog and does not rewrite playlists."""
    previous = load_audio()
    catalog = {} if refresh else previous
    pending = []
    for name, url in entries:
        if not streams.is_astra_play_url(url):
            continue
        key = streams.astra_mpegts_url(url)
        if key in catalog and not refresh:
            catalog[key]["channel"] = name
            continue
        pending.append((key, name))

    found = {}
    with ThreadPoolExecutor(max_workers=streams.SEARCH_WORKERS) as executor:
        futures = {executor.submit(classify_source, key): (key, name) for key, name in pending}
        for future in as_completed(futures):
            key, name = futures[future]
            record = future.result()
            record["channel"] = name
            verified = previous.get(key, {}).get("verified")
            if verified:
                apply_verified(record, verified)
            found[key] = record

    catalog.update(found)
    for name, url in entries:
        if streams.is_astra_play_url(url):
            key = streams.astra_mpegts_url(url)
            if key in catalog:
                catalog[key]["channel"] = name
    save_audio(catalog)
    return catalog


def classify_source(url: str) -> dict:
    mpegts = streams.astra_mpegts_url(url)
    hls = streams.astra_hls_url(url)
    languages, delivery, hls_ok = _languages_and_delivery(mpegts, hls)
    audio = audio_kind(languages)
    form, fix = decide_form(audio, delivery, hls_ok)
    return {
        "audio": audio,
        "languages": languages,
        "delivery": delivery,
        "form": form,
        "fix": fix,
        "checked": date.today().isoformat(),
    }


def apply_verified(record: dict, kind: str) -> dict:
    """The TV language wins over the language tag inside the stream. A refresh keeps it."""
    record["verified"] = kind
    record["audio"] = kind
    hls_ok = record.get("delivery") == "hls-only" or record.get("form") == "hls"
    form, fix = decide_form(kind, record.get("delivery") or "down", hls_ok)
    record["form"] = form
    record["fix"] = fix
    return record


def audio_kind(languages: list[str]) -> str:
    present = {language for language in languages if language != "?"}
    has_spanish = bool(present & SPANISH)
    has_english = bool(present & ENGLISH)
    if has_spanish and has_english:
        return "dual"
    if has_spanish:
        return "spa"
    if has_english:
        return "eng"
    if present:
        return "other"
    return "unknown"


def decide_form(audio: str, delivery: str, hls_ok: bool) -> tuple[str, str]:
    """Return (form, fix). form is mpegts or hls; fix tells a later edit what not to do."""
    if delivery == "hls-only":
        if audio == "dual":
            return "hls", "replace-source"
        return "hls", "keep-hls"
    if delivery != "mpegts":
        return ("hls" if hls_ok else "mpegts"), "unknown"
    if audio == "dual":
        return "mpegts", "use-mpegts"
    if audio in ("spa", "eng") and hls_ok:
        return "hls", "keep-hls"
    return "mpegts", "use-mpegts"


def _languages_and_delivery(mpegts: str, hls: str) -> tuple[list[str], str, bool]:
    ts_payload = _read(mpegts, 250_000)
    if ts_payload and streams.MPEGTS_SYNC_BYTE in ts_payload[:400] and not ts_payload.startswith(b"#"):
        languages = _languages_in_ts(ts_payload)
        if languages or _has_pmt(ts_payload):
            hls_ok = audio_kind(languages) in ("spa", "eng") and streams.serves_hls(hls)
            return languages, "mpegts", hls_ok
    hls_payload = _hls_segment(hls)
    if hls_payload:
        return _languages_in_ts(hls_payload), "hls-only", True
    return [], "down", False


def _read(url: str, size: int) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": streams.USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(
            request, timeout=streams.PROBE_TIMEOUT_SECONDS, context=ssl.create_default_context()
        ) as response:
            return response.read(size)
    except (OSError, http.client.HTTPException):
        return None


def _hls_segment(master_url: str) -> bytes | None:
    master = _read(master_url, 8_000)
    if not master or not master.startswith(b"#EXTM3U"):
        return None
    variant = _first_uri(master.decode("utf-8", "replace"))
    if not variant:
        return None
    if not variant.startswith("http"):
        variant = master_url.rsplit("/", 1)[0] + "/" + variant.rsplit("/", 1)[-1]
    media = _read(variant, 8_000)
    if not media:
        return None
    segment = _first_uri(media.decode("utf-8", "replace"))
    if not segment:
        return None
    if not segment.startswith("http"):
        segment = variant.rsplit("/", 1)[0] + "/" + segment
    return _read(segment, 300_000)


def _first_uri(playlist: str) -> str:
    for line in playlist.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def _has_pmt(data: bytes) -> bool:
    return bool(_pmt_streams(data))


def _languages_in_ts(data: bytes) -> list[str]:
    found: list[str] = []
    for langs in _pmt_streams(data):
        for lang in langs:
            if lang not in found:
                found.append(lang)
    return found


def _pmt_streams(data: bytes) -> list[list[str]]:
    pmt_pid = None
    buffer = b""
    for packet in _packets(data):
        pid = ((packet[1] & 0x1F) << 8) | packet[2]
        payload_start = packet[1] & 0x40
        offset = 4
        if (packet[3] >> 4) & 2:
            offset += 1 + packet[4]
        if offset >= 188:
            continue
        payload = packet[offset:]
        if pid == 0 and payload_start and pmt_pid is None:
            pmt_pid = _program_pid(payload)
        elif pmt_pid is not None and pid == pmt_pid:
            buffer = payload if payload_start else buffer + payload
            streams = _audio_streams(buffer)
            if streams:
                return streams
    return []


def _packets(data: bytes):
    start = data.find(streams.MPEGTS_SYNC_BYTE)
    if start < 0:
        return
    step = 188
    if start + 192 < len(data) and data[start + 188] != 0x47 and data[start + 192] == 0x47:
        step = 192
    index = start
    while index + 188 <= len(data):
        if data[index] != 0x47:
            index += 1
            continue
        yield data[index : index + 188]
        index += step


def _program_pid(payload: bytes) -> int | None:
    if not payload:
        return None
    section = payload[1 + payload[0] :]
    if not section or section[0] != 0x00:
        return None
    length = ((section[1] & 0x0F) << 8) | section[2]
    body = section[3 : 3 + length]
    index, end = 5, len(body) - 4
    while index + 4 <= end:
        program = (body[index] << 8) | body[index + 1]
        pid = ((body[index + 2] & 0x1F) << 8) | body[index + 3]
        if program:
            return pid
        index += 4
    return None


def _audio_streams(payload: bytes) -> list[list[str]]:
    if not payload:
        return []
    section = payload[1 + payload[0] :]
    if len(section) < 12 or section[0] != 0x02:
        return []
    length = ((section[1] & 0x0F) << 8) | section[2]
    body = section[3 : 3 + length]
    if len(body) < 9:
        return []
    index = 9 + (((body[7] & 0x0F) << 8) | body[8])
    end = len(body) - 4
    streams = []
    while index + 5 <= end:
        stream_type = body[index]
        info_length = ((body[index + 3] & 0x0F) << 8) | body[index + 4]
        info = body[index + 5 : index + 5 + info_length]
        languages = _iso639(info)
        if stream_type in AUDIO_TYPES or languages:
            streams.append(languages or ["?"])
        index += 5 + info_length
    return streams


def _iso639(info: bytes) -> list[str]:
    languages = []
    index = 0
    while index + 2 <= len(info):
        tag, size = info[index], info[index + 1]
        descriptor = info[index + 2 : index + 2 + size]
        if tag == 0x0A:
            cursor = 0
            while cursor + 4 <= len(descriptor):
                languages.append(descriptor[cursor : cursor + 3].decode("latin1", "replace").lower())
                cursor += 4
        index += 2 + size
    return languages
