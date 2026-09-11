# IPTV Playlist Curation — Agent Guide

This repo maintains a curated Latin America–oriented channel list in `official.m3u`, with retired sources in `backup.m3u`. Agents should treat `official.m3u` as an editorial TV lineup, not a raw link dump.

**After any edit to `official.m3u`**, run the cleanup script (idempotent — safe to run every time):

```bash
python3 scripts/clean_m3u.py
```

---

## Skills index

Read the full `SKILL.md` before running a workflow. Skills live under `.agents/skills/`. Pick **one** skill per request — use the disambiguation column when intents overlap.

| Skill | Purpose | Triggers | Not this skill if… |
|-------|---------|----------|-------------------|
| [`m3u-source-update`](skills/m3u-source-update/SKILL.md) | Find streams on Astra servers; add up to 6 ranked URLs to `official.m3u` | buscar fuentes, agregar canal, nuevas variantes, URL caída, origin servers | user gives IDs to delete/backup, or only wants logos/reorder |
| [`m3u-lineup`](skills/m3u-lineup/SKILL.md) | Editorial order — LATAM first, 1080p, provider-style blocks | ordenar, curar parrilla/grilla, Movistar/DIRECTV/Claro, categorías | adding streams, delete, backup, or logo fixes |
| [`m3u-fix-logos`](skills/m3u-fix-logos/SKILL.md) | Repair `tvg-logo` URLs via `fix_logos.py` (**needs IDs**) | iconos, logos, tvg-logo 404, no se ven en TV | stream doesn't play, delete, backup, or search sources |
| [`m3u-remove-channels`](skills/m3u-remove-channels/SKILL.md) | **Permanent** delete from `official.m3u` (**needs IDs**) | eliminar, borrar, quitar, delete for good | user says backup/respaldo — use `m3u-to-backup` |
| [`m3u-to-backup`](skills/m3u-to-backup/SKILL.md) | Move `official.m3u` → `backup.m3u`, keep source (**needs IDs**) | backup, respaldo, mover a backup, quitar pero guardar | user wants permanent delete — use `m3u-remove-channels` |

**ID-based skills** (`m3u-fix-logos`, `m3u-remove-channels`, `m3u-to-backup`): never run without explicit global IDs (the number at the start of `tvg-name`, e.g. `88` in `88 Star Channel 1`). Ask first; do not grep-and-guess.

**Typical flow**: `m3u-source-update` (find streams) → user tests on TV → `m3u-remove-channels` or `m3u-to-backup` (drop failures). `m3u-lineup` is for editorial reorder only. After any `official.m3u` edit, run `clean_m3u.py`.

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
