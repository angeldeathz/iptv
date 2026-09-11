---
name: m3u-source-update
description: "Search for channels in source M3U lists with scripts/search_sources.py and add the best sources (max 6) to official.m3u for the user to test on TV. Use when the user asks to search for sources, add backups, replace a down channel, or update the list from origin servers."
---

# Update official.m3u from source servers

Workflow to find streams on Astra servers and add them to `official.m3u`.

## Core policy

**Add only the best sources, max 6 per channel.** The user tests them on their TV and then removes the ones that don't work or asks to move the rest to backup.

Exceptions:

- If the user requests a different number (e.g. "only 3", "max 7"), use that limit.
- If they explicitly ask for **all** sources, add all without filtering.
- If they ask to replace a single URL or add only one source, follow that instruction.

## When to use this skill

- The user asks to search for a channel in the source servers.
- Backups or variants need to be added for TV testing.
- A down URL needs to be replaced (only if the user requests it).
- A new channel needs to be added from verified servers.

For editorial criteria (LATAM priority, lineup order), combine with the `m3u-lineup` skill.

## Step 1: Search for matches

Run from the repo root with **full network access** (`required_permissions: ["full_network"]` in the Shell tool). **Do not use the default sandbox**: Astra servers are not on the allowlist and return a false HTTP 403 on the first run.

```bash
python3 scripts/search_sources.py "<query>" --json
```

Prefer `--json` to avoid missing matches when parsing output.

If `total_matches` is 0 and all `failed_sources` show `HTTP 403`, **do not retry or report servers as down** — re-run the same command with `full_network` (or `all` if the permission fails).

Query rules:

- Use the clean channel name, without country prefixes or resolution (e.g. `star channel`, not `CL: Star Channel HD`).
- If there are many irrelevant results, refine the query or use `--regex`.
- Do not use `--source` unless the user limits the search to one server.

## Step 2: Select the best sources (max 6)

Go through all matches and **keep only the best**, up to **6 new URLs** per channel (or the limit the user requests).

For each match:

| Condition | Action |
|-----------|--------|
| URL already in `official.m3u` (`in_official: true`) | **Skip** — already available for testing |
| New URL | **Candidate** to add |
| Source with error (timeout, empty list) | **Skip** — no URL to add |

### Selection criteria (in order)

1. **Stable server**: prioritize hosts that already appear frequently in `official.m3u` (same criterion as HBO, Disney Channel, etc.).
2. **Quality**: prefer `1080p` / `FHD` / `HD` over `SD`.
3. **Complete URL**: prefer URLs with `/index.m3u8` over incomplete paths.
4. **Clean name**: discard odd variants (`ENVIADO`, `NUEVO`, internal line numbers).
5. **One URL per server**: if a host has multiple matches for the same channel, keep the highest-quality one.
6. **Logo in source**: tie-break in favor of entries with `tvg-logo` on the `#EXTINF`.

After ranking, add only the **top N** (default **6**). If there are fewer valid candidates, add all that qualify.

If the channel already has variants in `official.m3u` and the total would exceed the limit, **do not replace** existing ones unless the user asks; add only up to the remaining quota.

## Step 3: Edit official.m3u

### Existing channel

1. Locate the channel block in `official.m3u` (by name or ID).
2. Insert **below the last block for that channel** (or at the end of the group if there are no variants) one `#EXTINF` + URL per new source.
3. **Do not replace** the main URL unless the user asks.
4. Reuse the existing channel's `tvg-logo` in each new block.

### New channel (not in the list)

1. Insert all blocks in the appropriate thematic section.
2. Use the source's `tvg-logo` if present; otherwise leave without logo (cleanup may resolve it).

### Template per new source

```text
#EXTINF:-1 group-title="Peliculas" tvg-name="Star Channel HD",Star Channel HD
http://servidor/play/xxxx/index.m3u8
```

If the source includes `#EXTVLCOPT:http-user-agent=...`, copy those lines between `#EXTINF` and the URL.

Rules when copying metadata from the source:

- Do not copy `tvg-id`.
- Use the source's `display_name` as the provisional name in `#EXTINF`.
- Do not worry about correlative IDs, repetition indices, or final `group-title`: `clean_m3u.py` recalculates them and groups variants of the same channel.

### Remove channel

Only if the user asks: delete the full block (`#EXTINF`, `#EXTVLCOPT` if any, URL).

## Step 4: Clean the list (required)

After any edit to `official.m3u`:

```bash
python3 scripts/clean_m3u.py
```

Verify the script finishes without errors. After cleanup, variants of the same channel appear as `N Canal X 1`, `N Canal X 2`, etc., sorted by quality.

## Step 5: Confirm to the user

Summarize:

1. Query used and limit applied (default 6).
2. **Total added** vs **already present** vs **discarded by ranking** vs **skipped** (down source).
3. Final ID range for the channel after cleanup (e.g. `67 HBO 2 1` … `67 HBO 2 6`).
4. Brief list: server + URL for each **new** source added.
5. Remind them they can test on TV and ask to remove failed ones or move to backup.

## Checklist

```
- [ ] Run search_sources.py --json with full_network (never sandbox)
- [ ] Rank candidates and add only the best (max 6 by default)
- [ ] Skip URLs already present or unavailable sources
- [ ] Run clean_m3u.py
- [ ] Report how many sources were added and their final IDs
```

## Useful commands

```bash
# Search with structured output (always use when adding sources)
python3 scripts/search_sources.py "star channel" --json

# Readable search for quick review
python3 scripts/search_sources.py "espn 2"

# Verify down channels after TV testing (also requires full_network)
python3 scripts/check_channels.py
```

## Common mistakes

- **Running in sandbox**: causes HTTP 403 on all servers; always use `full_network` on the first attempt.
- **Adding all sources**: default is max 6 best; only add all if the user explicitly asks.
- **Editing names/IDs manually**: let `clean_m3u.py` normalize them.
- **Forgetting cleanup**: breaks taxonomy, IDs, and deduplication.
- **Replacing instead of adding**: only replace if the user explicitly asks.
- **Copying tvg-id from source**: forbidden; cleanup removes it anyway.
