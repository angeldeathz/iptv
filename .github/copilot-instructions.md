# IPTV Repository Instructions

When editing `official.m3u`, treat the file like a curated TV provider lineup rather than a raw playlist dump.

## Core rules

1. Prioritize Latin American channels, especially Spanish-speaking and pan-regional LATAM sources.
2. Do not give priority to Brazil or other non-priority markets unless they provide unique coverage.
3. Prefer `1080p` streams first, then lower resolutions only when needed.
4. Keep channels ordered like an IPTV provider: national channels together, then kids, movies, series, sports, news, music, documentaries, and other groups.
5. Preserve M3U syntax and metadata fields exactly.

## Ordering model

1. National and free-to-air channels first.
2. Regional and local channels next.
3. Kids, movies, series, sports, news, music, documentaries, then international channels.
4. Place the best quality source first for each channel.
5. Keep secondary sources only when they are useful backups or add a meaningful region variant.

## Editing discipline

1. Avoid alphabetical ordering unless explicitly requested.
2. Avoid unnecessary duplicates.
3. Keep the lineup stable and provider-like, similar to Movistar, DIRECTV, or Claro.
4. Preserve `tvg-id`, `tvg-name`, `tvg-logo`, `group-title`, `user-agent`, and `#EXTVLCOPT` when present.
