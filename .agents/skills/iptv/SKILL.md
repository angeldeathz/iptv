---
name: iptv
description: >-
  Single skill for every change to the IPTV lineup (official.m3u) through
  scripts/iptv.py: delete channels, move them to another section or reorder,
  move to backup, add channels or stream sources, search origin servers,
  replace a URL, fix or change logos, list global IDs, rebuild/verify
  official.m3u. Use for eliminar, borrar, quitar, mover, déjalo en, ordenar,
  backup, respaldo, agregar canal, buscar fuentes, nuevas variantes, URL caída,
  actualizar URL, iconos, logos, IDs, parrilla, grilla, lista de pruebas,
  pruebas.m3u, buscar canales para probar.
---

# IPTV lineup

## How the repo works

- `datasource/<section>.m3u`: the channels. One file per section; **file order is the lineup order**.
- `assets/logos.json`: `{"<exact channel name>": "<logo URL>"}`. Every variant of a channel shares its logo.
- `official.m3u`: **generated** by the build. Never edited.
- Global ID = position across all sections in order. Labels are `<id> <name> <rep>` (e.g. `88 Star Channel 1`); `rep` numbers the variants of one channel.
- Everything goes through `python3 scripts/iptv.py <command>` from the repo root. Output is JSON; errors go to stderr with exit code 1. Every command that changes channels or logos rebuilds `official.m3u` itself.
- `pruebas.m3u`: scratch playlist for the user to test streams on TV. **Not** part of the build. Filled only by the [search → pruebas](#workflow-search-channels-into-pruebasm3u) workflow.

Sections (use the key): `nacionales`, `noticias`, `infantiles`, `peliculas`, `series`, `deportes`, `musica`, `documentales`, `variedades`, `internacionales`, `experimentales` (24/7 - Experimentales). Accents and case are ignored.

## Golden rules

1. Never edit `official.m3u`, `datasource/` or `assets/logos.json` by hand or with edit tools. Only `iptv.py` writes them.
2. Never touch `pluto_tv.m3u`. `backup.m3u` is only written by `edit --backup`. Edit `pruebas.m3u` **only** when the user asks to search channels and put them on the test list (see workflow below); do **not** copy entries from `official.m3u` for that request.
3. ID-based operations need explicit global IDs from the user (`88`, `88, 91`, `88-92` = 88 to 92). If they are missing, ask and stop. Never choose IDs by name; `list --filter` is only to show candidates for the user to confirm.
4. IDs shift after `edit` and `add`. Put all removes, backups and moves of one request in **one** `edit` call. Run `set-url` and `logo` (they do not shift IDs) before `edit`/`add`; if something must run after them, `list` again for fresh IDs.
5. For `edit` with 2+ IDs run `--dry-run` first and check that every planned name matches the user's intent. Pass `--expect ID:NAME` whenever the name is known.
6. `search`, `add`, `set-url` and `logo` need network: run them with `required_permissions: ["full_network"]`. In the sandbox the Astra servers answer a false `HTTP 403`; rerun with full network instead of reporting them as down.
7. If a command fails, report the error. Never work around it by editing files.

## Catalog

| User intent | Command |
|---|---|
| Find IDs | `list --filter "espn"` · `list --section deportes` |
| Delete for good (IDs, no destination) | `edit --remove 83 85` |
| Move to backup (backup, respaldo, guardar para después) | `edit --backup 84` |
| Move to another section (IDs + destination) | `edit --move 188:infantiles` (goes to the end) |
| Reorder | `edit --move 50:series:47` (after ID 47) · `edit --move 50:series:first` |
| Several actions in one request | `edit --remove 83 85 --backup 84 --move 50:series --expect 83:Universal` |
| Replace the URL of a source | `set-url 42 "http://host/play/a0xx"` |
| Add sources to an existing channel | `add --name "ESPN 2" --url URL1 --url URL2` (inserted after its last variant) |
| Add a new channel | `add --name "Star Channel" --section peliculas [--after 104] --url URL [--logo LOGO]` |
| Search stream sources | `search "star channel"` · `search "espn.*1080" --regex` · `--source 45.232.210.1` (token match: `&`/`and`, `+`/`plus`, glued names like `ESPN2`, `TVChile`; short names match on channel title only) |
| Search channels → test list | Per channel: `search "<name>"`, rank, top **3** URLs → write `pruebas.m3u` (workflow below) |
| Fix broken logos | `logo 197 198` |
| Set a specific logo | `logo 197 --url "https://..."` |
| Rebuild / verify official | `build` · `build --check` |

### Disambiguation

- IDs **and** a destination section (*déjalo en infantiles*, *mueve a películas*, *sácalo de experimentales y ponlo en series*) = `--move`, even if the user says *borra* or *saca*.
- *backup*, *respaldo*, *quitar pero guardar* = `--backup`.
- Only IDs with *eliminar / borrar / quitar* = `--remove`.
- A given replacement URL = `set-url`. *Buscar fuentes*, *agregar respaldos/variantes*, *la URL se cayó y no hay otra* = search and add.
- *Buscar canales* + *pruebas* / *lista de pruebas* / *dejarlos en pruebas.m3u* = [search → pruebas](#workflow-search-channels-into-pruebasm3u), **not** `list --filter` and **not** copying `official.m3u`.

## Workflow: search channels into `pruebas.m3u`

When the user names one or more channels and wants them on the test playlist (*buscar … y ponerlos en pruebas*, *lista de pruebas*, etc.):

1. For **each** channel name, run `search "<clean name>"` on the configured Astra origin hosts (same as add-sources search). If the result is empty or clearly wrong, retry with a host spelling alias (`Universal Channel` for Universal TV, `Nat Geo` for National Geographic, `Film & Arts`, `H&H` / `Home & Health`, `HBO Plus` for HBO+) or `--regex`. Use `--source` only if the user limits servers.
2. Rank matches with the same rules as [add stream sources](#workflow-add-stream-sources) (stable hosts, quality, clean LATAM/ES variants, one URL per host, logo tie-break). Ignore `failed_sources`.
3. Unlike `add`, **do not** discard hits just because `in_official` is set — pruebas is for trying origins, including alternatives to what is already in the lineup.
4. Keep the top **3** URLs per channel (unless the user gives another count). Fewer than 3 if there are not enough good matches; say so in the reply.
5. Rewrite `pruebas.m3u` from scratch for that request: `#EXTM3U`, then all chosen entries in the order the user listed the channels. For each family use the lineup **clean name** with variants `1`–`3` (best first), e.g. `NTV 1`, `NTV 2`, `NTV 3`. Set `tvg-name` and display name to match; add `tvg-logo` from the best match that has one; add `audio-track="spa,eng"` on Astra `/play/<id>` URLs (not on bare HLS unless the repo already does elsewhere).
6. Do not run `add`, `edit`, or `build` for this workflow unless the user also asks to change `official.m3u`.

## Workflow: add stream sources

1. `search "<clean name>"`: no country prefix, no resolution (`star channel`, not `CL: Star Channel HD`). Same token matching as above; if too few hits, retry aliases or `--regex`. Use `--source` only if the user limits servers.
2. Discard matches whose `in_official` is not null (already in the lineup) and sources in `failed_sources`.
3. Rank the rest:
   1. Stable host: hosts that already appear often in `official.m3u`.
   2. Quality from the source name: `1080p`/`FHD` > `HD`/`720p` > `SD`.
   3. Clean variants: discard `ENVIADO`, `NUEVO`, internal line numbers, other languages or markets.
   4. One URL per host (keep its best quality).
   5. Tie-break: the match has a `logo`.
4. Keep the top **6** new URLs (or the number the user asks; "todas" = all). Never replace existing variants unless asked.
5. `add` once with every chosen `--url`, best first. New channel: add `--section`, and `--logo` with the best match `logo` if any. Astra URLs are probed automatically (MPEG-TS `/play/<id>` when served, HLS `/index.m3u8` as fallback) and get `audio-track="spa,eng"` in the build.
6. Report the added IDs; the user tests them on TV and later asks to remove or back up the failures.

## Naming rules

- Clean name only: no country prefixes or suffixes (`CL:`, `MX`, `USA`), no resolution or tags (`HD`, `FHD`, `HEVC`, `1080p`, `[Geo-blocked]`), no `"`.
- Avoid `&` (it breaks some Smart TV parsers) except the brand `A&E`; use `/` only in `24/7`.
- To add variants reuse the existing name (`add` matches it case-insensitively and keeps its spelling).

## Editorial policy

- Latin American and Spanish-speaking channels first; Brazil and non-priority markets at the end of their section.
- Within a channel, variant `1` is the best source; put better sources first.
- File order is the lineup the user maintains: never reorder unless asked, never sort alphabetically.

## Logos

`logo` checks the current URL of each channel and, if broken, tries docdog and tv-logo/tv-logos. Per channel status: `ok`, `fixed`, `set` or `failed`. On `failed`, tell the user and ask for a logo URL, then use `logo ID --url URL`. The build lists channels without a logo in `without_logo`.

## Response

Answer in the user's language with 1 to 3 short lines: what changed, with IDs and channel names (and the new ID when a channel moved), plus any failure. Example: `Eliminados 83 Universal Premiere 1 y 85 Universal Cinema 1; 84 pasó a backup. Official reconstruida: 191 canales.`
