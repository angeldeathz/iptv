---
name: m3u-lineup
description: >-
  Applies editorial lineup rules to official.m3u: LATAM-first channel priority,
  1080p preferred, provider-style category blocks (Movistar, DIRECTV, Claro).
  Use when the user asks to ordenar, curar, reordenar la parrilla/grilla, fix
  category placement, or align the grid like a TV operator — without adding new
  stream URLs. Do NOT use for searching origin servers, deleting channels,
  moving to backup.m3u, or repairing tvg-logo icons.
---

# M3U Playlist Curator

This skill defines how to maintain `official.m3u` as a TV provider lineup: clean, consistent, and Latin America–oriented.

## Goal

1. Treat `official.m3u` as an editorial grid, not a link dump.
2. Prioritize Latin American channels, focusing on Spanish-speaking and pan-regional streams.
3. Leave Brazil and other non-priority markets at the end, only when they add unique or necessary coverage.
4. Always prefer the best available quality, with clear priority for `1080p`.
5. Order by categories like a provider: nationals, kids, movies, series, sports, news, music, documentaries, and others.

## Selection criteria

1. If a channel has multiple sources, choose the most stable one with the best resolution first.
2. Quality preference order is `1080p`, `720p`, `576p`, `480p`, `SD`.
3. Keep secondary variants only when they serve as real backups or add a different region within LATAM.
4. Avoid unnecessary duplicates. If there is more than one entry for the same channel, the first must be the primary one.
5. Do not invent metadata: preserve `tvg-name`, `tvg-logo`, `group-title`, `user-agent`, and `#EXTVLCOPT` when they exist. Do not add `tvg-id` (see `.agents/AGENTS.md`).

## Lineup order

Follow this sorting logic:

1. National and open channels of the target market.
2. Relevant regional or local channels.
3. Kids.
4. Movies.
5. Series and entertainment.
6. Sports.
7. News and information.
8. Music, lifestyle, and culture.
9. Documentaries and education.
10. International and secondary variants.

Within each group:

1. Main channel first.
2. `HD` or `1080p` version immediately after.
3. `720p`, `576p`, and `SD` versions at the end.
4. If there are regional variants, keep the Spanish-speaking Latin America block before other variants.

## Suggested group taxonomy

Use consistent, user-recognizable categories:

1. `NACIONALES`
2. `REGIONALES`
3. `INFANTILES`
4. `PELICULAS`
5. `SERIES`
6. `DEPORTES`
7. `NOTICIAS`
8. `MUSICA`
9. `DOCUMENTALES`
10. `VARIEDADES`
11. `INTERNACIONALES`

## Editorial rules

1. Do not sort alphabetically unless the user asks.
2. Do not mix Brazil into the main Spanish-speaking Latin America block.
3. Do not move channels by name alone if that breaks provider logic.
4. If a channel is duplicated with different qualities, keep the best version higher up.
5. Preserve exact M3U syntax so players do not break.

## Expected outcome

When this skill is used on `official.m3u`, the result should look like a list curated by a TV operator: thematic block order, LATAM priority, high quality first, and stable structure.
