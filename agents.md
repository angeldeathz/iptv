# Agent Guide - Maintaining official.m3u

This repository contains a curated television channel list in the `official.m3u` file. To keep the channel lineup clean, consistent, and correctly formatted, you must run the automated cleanup script whenever you make changes or add new channels.

## Format Rules for `official.m3u`

1. **Lineup Order (Categories)**: Channels must be ordered according to standardized thematic groups (highest to lowest priority):
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

2. **`group-title` Attribute**: All `group-title` values must be in **PascalCase** (e.g. `Nacionales`, `Peliculas`, `Series`). Never use ALL CAPS or all lowercase.

3. **No Country Prefixes or Suffixes**: The channel name must not include country codes or geographic affiliation (e.g. `CL: Chilevision FHD` must be `Chilevision FHD`, without prefixes like `CL:`, `MX:`, `BR:`, `USA:`, `US:`, `ES:`, or suffixes like `MX`, `Brazil`, `BR`, `USA`, etc.).

4. **No Resolution Tags**: Resolution and quality tags (`HD`, `FHD`, `SD`, `HEVC`, `1080p`, `720p`, `576p`, `480p`, `[Geo-blocked]`, etc.) must be removed from the clean channel name to group duplicate streams.

5. **Name Identifiers (IDs)**:
   - Each channel must start with an incremental global ID (starting at `1`).
   - Each channel must end with a repetition ID (starting at `1`). This ID increments sequentially only for copies or alternate qualities of the same channel (e.g. if there are 4 variants of "Canal 13", they will be formatted as `Canal 13 1`, `Canal 13 2`, `Canal 13 3`, `Canal 13 4`).
   - The final visible name format is: `<global_id> <clean_name> <repetition_index>`.

6. **`tvg-name` Attribute**: All channels must include the `tvg-name` attribute on the `#EXTINF` line. The format is `<global_id> <clean_name> <repetition_index>` (e.g. `1 Chilevision 1`, `4 Canal 13 1`). Each `tvg-name` must be unique across the entire list; none may be duplicated. The correlative global ID always goes at the beginning of the name.

7. **`tvg-id` Attribute**: Do not include `tvg-id` on any channel. This list is used in IPTV TV apps without EPG, so the attribute is not needed.

8. **Quality Prioritization**: When grouping duplicate variants of the same channel, they must be ordered with the best available resolution first (prioritizing HEVC > FHD/1080p > HD/720p > SD/576p/480p).

9. **Unique URLs**: No two channels may share the same stream URL. If duplicate entries are added, the cleanup script automatically removes copies and keeps only one (prioritizing better quality in the name and, on tie, the first appearance in the file). After deduplication, correlative IDs are recalculated.

---

## Running the Cleanup Script

To automate the application of these rules (including reordering, name normalization, ID updates, and general formatting), simply run the Python script provided in the workspace:

```bash
python3 scripts/clean_m3u.py
```

> [!IMPORTANT]
> **You must run this script every time you modify or add channels in `official.m3u`.** This prevents lineup inconsistencies, removes duplicate URLs, and ensures IDs and order are updated correctly and idempotently.
