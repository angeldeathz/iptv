# IPTV Playlist — Agent Guide

This repo maintains a curated Latin America–oriented channel lineup.

- `datasource/<section>.m3u` holds the channels (file order = lineup order).
- `assets/logos.json` holds one logo per channel name.
- `official.m3u` is **generated** from both by `python3 scripts/iptv.py build`. Never edit it.

Every lineup task (delete, move, reorder, backup, add sources, search, replace URL, logos, IDs) follows the single skill [`iptv`](skills/iptv/SKILL.md). Read it before acting and change files only through `scripts/iptv.py`.

Out of scope unless the user asks explicitly: `pruebas.m3u`, `pluto_tv.m3u` and the structure of `backup.m3u`.
