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
3. **EPG Compatibility**: Every `#EXTINF` line must have a `tvg-name` attribute equal to `<clean_name>` (the base clean name of the channel without IDs or quality markers).
4. ** line-up order**: Order groups according to operator lineup priority:
   `NACIONALES` > `REGIONALES` > `INFANTILES` > `PELICULAS` > `SERIES` > `DEPORTES` > `NOTICIAS` > `MUSICA` > `DOCUMENTALES` > `VARIEDADES` > `INTERNACIONALES`.
5. **Quality Sort**: Quality variations of the same channel must be grouped together and sorted by quality/resolution descending (best quality first).
