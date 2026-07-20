# Workspace Rules for IPTV Playlist Curation

## Curation and Formatting of `official.m3u`

Whenever modifications are made to `official.m3u` (such as adding, removing, or updating channels), you MUST follow these guidelines:

1. **Idempotent Cleanup**: Always run the automated Python cleanup script located at `scripts/clean_m3u.py` immediately after editing to ensure proper grouping, taxonomy assignment, and formatting:
   ```bash
   python3 scripts/clean_m3u.py
   ```
2. **Channel Name Formatting**: Channel display names must conform to the following pattern:
   `<global_incremental_id> <clean_name> <repetition_index>`
   - Country prefix codes (e.g., `CL: `, `MX: `, `BR: `) and suffix codes must be removed.
   - Resolution keywords (e.g., `HD`, `FHD`, `SD`, `HEVC`, `1080p`, `720p`) must be removed from the `<clean_name>` segment.
3. **group-title Attribute**: All `group-title` values must use **PascalCase** (e.g. `Nacionales`, `Peliculas`, `Series`). Never use ALL CAPS or all lowercase.
4. **tvg-name Attribute**: Every `#EXTINF` line must have a unique `tvg-name` in the format `<global_id> <clean_name> <repetition_index>` (e.g. `1 Chilevision 1`, `4 Canal 13 2`). The correlative global ID must always appear at the beginning. No two channels may share the same `tvg-name`.
5. **tvg-id Attribute**: Do not include `tvg-id` on any channel. This playlist is used in IPTV TV apps without EPG, so the attribute is not needed.
6. **Line-up order**: Order groups according to operator lineup priority:
   `Nacionales` > `Regionales` > `Infantiles` > `Peliculas` > `Series` > `Deportes` > `Noticias` > `Musica` > `Documentales` > `Pluto Tv` > `Variedades` > `Internacionales`.
7. **Quality Sort**: Quality variations of the same channel must be grouped together and sorted by quality/resolution descending (best quality first).
8. **Unique URLs**: No two channels may share the same stream URL. The cleanup script automatically removes duplicate URLs, keeping the best-quality entry (or the earliest one on tie), then recalculates correlative IDs.
