---
name: m3u-sync-logos-json
description: >-
  Copies current tvg-logo URLs from official.m3u into assets/logos.json by global
  channel ID via scripts/sync_logos_json.py. Use when the user asks to actualizar
  logos.json, sync logos json, volcar iconos al registro, or guardar URLs de iconos
  without repairing the playlist. Requires explicit global IDs — never infer from name.
  Do NOT use for broken/missing icons on TV, searching alternative logo URLs, or
  editing official.m3u — use m3u-fix-logos instead.
---

# Sync channel icons to assets/logos.json

Copy `tvg-logo` values from `official.m3u` into the persistent registry `assets/logos.json`.

**Scope is only `assets/logos.json`.** No HTTP checks, no URL discovery, no edits to `official.m3u`, no `clean_m3u.py`.

## When to use this skill vs m3u-fix-logos

| | **m3u-sync-logos-json** (this skill) | **m3u-fix-logos** |
|---|--------------------------------------|-------------------|
| **User intent** | Save/register current icon URLs in JSON | Fix icons that don't show on TV |
| **Reads** | `tvg-logo` from `official.m3u` | `tvg-logo` + probes the web |
| **Writes** | `assets/logos.json` only | `official.m3u`, `assets/logos.json`, maybe `clean_m3u.py` |
| **Network** | Not required | Required |
| **Verifies URL works** | No | Yes |
| **Searches alternatives** | No | Yes |

## Mandatory requirement: user IDs

**Do not run without IDs.** The user must provide global IDs from `official.m3u` (e.g. `4` in `4 TVN 1`).

If the message does not include IDs, ask and stop. Do not infer IDs or search channels by name.

Accepted formats: `4, 19, 35` · `4 19 35` · `1-15` (expand ranges).

## Execution

From the repo root (**no network access needed**):

```bash
python3 scripts/sync_logos_json.py <id1> <id2> ... --json
```

Example:

```bash
python3 scripts/sync_logos_json.py 1 2 3 4 5 --json
```

### What the script does

1. Locates channels by ID in `official.m3u`.
2. Groups by base channel name (e.g. `Nickelodeon 1` and `Nickelodeon 2` → one entry).
3. Takes the first non-empty `tvg-logo` among variants.
4. Writes or updates `assets/logos.json` with `source: "official_m3u"`.

### JSON output

| status | Meaning |
|--------|---------|
| `added` | New entry in `logos.json` |
| `updated` | URL changed |
| `unchanged` | Same URL already stored |
| `skipped` | Channel has no `tvg-logo` in `official.m3u` |

## Agent rules

1. **Single command** — do not hand-edit `logos.json` or curl URLs manually.
2. **Do not read the entire official.m3u** — the script resolves IDs; use `--json` for the summary.
3. **Do not run fix_logos.py** for this task.
4. **Do not run clean_m3u.py** — this skill does not touch the playlist.
5. **Do not verify or search logos** — copy as-is from `official.m3u`.

## Response to the user

Summarize: which IDs/channels were synced, and counts of `added` / `updated` / `unchanged` / `skipped`.

If any channel is `skipped`, say it has no `tvg-logo` in `official.m3u` (suggest `m3u-fix-logos` only if they want to repair it).

## Common mistakes

- **Using fix_logos.py** when the user only asked to update `logos.json`.
- **Probing URLs on the web** — out of scope; use `m3u-fix-logos`.
- **Running without IDs** — ask first.
- **Editing official.m3u** — never for this skill.
