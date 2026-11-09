# IPTV Playlist — Agent Guide

This repo maintains a curated Latin America–oriented channel lineup.

- `datasource/<section>.m3u` holds the channels (file order = lineup order).
- `assets/logos.json` holds one logo per channel name.
- `assets/stream_audio.json` holds, per Astra source, whether the audio is Spanish, English or both, and whether the stored URL must be bare MPEG-TS or `index.m3u8`. `python3 scripts/iptv.py audio` refreshes it. `add` and `set-url` obey it.
- `official.m3u` is **generated** from both by `python3 scripts/iptv.py build`. Never edit it.

Every lineup task (delete, move, reorder, backup, add sources, search, replace URL, logos, IDs) follows the single skill [`iptv`](skills/iptv/SKILL.md). Read it before acting and change files only through `scripts/iptv.py`.

Out of scope unless the user asks explicitly: `pluto_tv.m3u` and the structure of `backup.m3u`. For `pruebas.m3u`, use the skill workflow *search channels into pruebas.m3u* (origin `search`, top 3 per channel — never copy from `official.m3u`).
