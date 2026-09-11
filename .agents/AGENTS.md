# IPTV Playlist Curation — Agent Guide

This repo maintains a curated Latin America–oriented channel list in `official.m3u`, with retired sources in `backup.m3u`. Agents should treat `official.m3u` as an editorial TV lineup, not a raw link dump.

**After any edit to `official.m3u`**, run the cleanup script (idempotent — safe to run every time):

```bash
python3 scripts/clean_m3u.py
```

---

## Skills index

Read the full `SKILL.md` before running a workflow. Skills live under `.agents/skills/`.

| Skill | Purpose | Use when the user… |
|-------|---------|-------------------|
| [`m3u-source-update`](skills/m3u-source-update/SKILL.md) | Search Astra origin servers and add up to 6 best new stream URLs per channel | asks to find sources, add backups, replace a down channel, or pull from origin servers |
| [`m3u-lineup`](skills/m3u-lineup/SKILL.md) | Editorial curation — LATAM priority, 1080p first, provider-style block order | asks to reorder, curate, or align the grid with Movistar / DIRECTV / Claro style |
| [`m3u-fix-logos`](skills/m3u-fix-logos/SKILL.md) | Verify and replace broken `tvg-logo` URLs by global channel ID | reports missing icons on TV, 404 logos, or asks to fix logos |
| [`m3u-remove-channels`](skills/m3u-remove-channels/SKILL.md) | Permanently delete channels from `official.m3u` and recalculate IDs | asks to remove/delete channels or drop sources that failed on TV (**requires user IDs**) |
| [`m3u-to-backup`](skills/m3u-to-backup/SKILL.md) | Move channels from `official.m3u` to `backup.m3u` and reorder the official list | asks to move sources to backup or keep them off official without deleting (**requires user IDs**) |

**ID-based skills** (`m3u-remove-channels`, `m3u-to-backup`, `m3u-fix-logos`): never run without explicit global IDs from the user (the number at the start of `tvg-name`, e.g. `88` in `88 Star Channel 1`).

**Combining skills**: source updates handle *finding* streams; `m3u-lineup` handles *editorial* ordering. After adding sources, cleanup always runs via `clean_m3u.py` or the skill's final step.

---

## Format rules for `official.m3u`

These rules are enforced by `scripts/clean_m3u.py`. Do not hand-edit IDs, repetition indices, or `group-title` — let the script normalize them.

### Channel naming

Display name and `tvg-name` format:

```text
<global_id> <clean_name> <repetition_index>
```

Examples: `1 Chilevision 1`, `4 Canal 13 2`.

- **Global ID**: incremental across the whole file, starting at `1`. One per channel family (not per quality variant).
- **Repetition index**: `1`, `2`, `3`… for alternate qualities/backups of the same channel. Best quality gets `1`.
- **Clean name**: no country prefixes (`CL:`, `MX:`, `BR:`, `USA:`, …), no country suffixes, no resolution tags (`HD`, `FHD`, `SD`, `HEVC`, `1080p`, `720p`, `[Geo-blocked]`, etc.).

### Attributes

| Attribute | Rule |
|-----------|------|
| `tvg-name` | Required on every `#EXTINF`. Must be unique. Format matches display name. |
| `tvg-id` | **Do not include.** This list is used without EPG. |
| `tvg-logo` | Include when known. Use `m3u-fix-logos` for broken URLs. |
| `group-title` | **PascalCase** only (e.g. `Nacionales`, `Peliculas`). Never ALL CAPS or all lowercase. |
| `#EXTVLCOPT` | Copy from source when required (e.g. `http-user-agent`). |

### Category order

Groups are sorted in this priority (matches `GROUP_ORDER` in `clean_m3u.py`):

1. `Nacionales`
2. `Regionales`
3. `Noticias`
4. `Infantiles`
5. `Peliculas`
6. `Series`
7. `Deportes`
8. `Musica`
9. `Documentales`
10. `Variedades`
11. `Internacionales`

Within each group: channel families stay together; best quality first (HEVC > FHD/1080p > HD/720p > SD/576p/480p).

### Deduplication

- No two channels may share the same stream URL. The cleanup script keeps the best-quality entry (or the earliest on tie) and recalculates IDs.

---

## Editorial policy (summary)

Full workflow: [`m3u-lineup` skill](skills/m3u-lineup/SKILL.md).

- Prioritize Latin American and Spanish-speaking channels.
- Keep Brazil and other non-priority markets at the end unless uniquely needed.
- Order like a TV provider — not alphabetically unless the user asks.
- Prefer stable, high-resolution sources (`1080p` first).
- Preserve valid M3U syntax (`#EXTM3U`, `#EXTINF`, `#EXTVLCOPT`) so players do not break.

---

## Useful scripts

| Script | Purpose |
|--------|---------|
| `scripts/clean_m3u.py` | Normalize names, IDs, groups, dedup URLs (**run after every edit**) |
| `scripts/search_sources.py` | Search origin M3U servers (needs `full_network`) |
| `scripts/check_channels.py` | List channels whose URLs fail (needs `full_network`) |
| `scripts/fix_logos.py` | Repair `tvg-logo` by global ID |
| `scripts/remove_channels.py` | Permanently remove channels by global ID |
| `scripts/move_to_backup.py` | Move channels to `backup.m3u` by global ID |
