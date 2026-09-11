---
name: m3u-fix-logos
description: "Fix broken icons (tvg-logo 404/400) in official.m3u by channel global ID. Use when the user reports logos not showing on TV, icons returning 404, or asks to fix the tvg-logo of one or more channels."
---

# Fix channel icons in official.m3u

Automated workflow to verify and replace `tvg-logo` URLs that do not load in IPTV TV apps.

## Mandatory requirement: user IDs

**Do not run without IDs.** The user must provide one or more global IDs from `official.m3u` (the number at the start of `tvg-name`, e.g. `197` in `197 TLC 1`).

If the message does not include IDs:

1. Ask for them explicitly.
2. Stop. Do not infer IDs or search channels by name.

Accepted user formats:

- Comma-separated list: `197, 200`
- Space-separated list: `197 200`
- Range: `197-199` (expand to `197 198 199`)

### Help the user identify IDs

If the user does not know which ID corresponds to a channel, list entries without running the fix:

```bash
grep -E '^#EXTINF' official.m3u | grep -i 'tlc'
```

Even so, **do not fix until the user confirms the IDs**.

## Execution

From the repo root, with **full network access** (`required_permissions: ["full_network"]`):

```bash
python3 scripts/fix_logos.py <id1> <id2> ... --json
```

Example:

```bash
python3 scripts/fix_logos.py 197 198 --json
```

### What the script does (no manual agent intervention)

1. Locates channels by ID in `official.m3u`.
2. Groups by base channel name (e.g. all `TLC 1`, `TLC 2` share a logo).
3. Verifies the current URL with GET (not HEAD; Wikipedia and other hosts block HEAD).
4. If the URL fails, searches for alternatives in this order:
   - `assets/logos.json` (already verified URLs)
   - `LOGO_LIBRARY` from `clean_m3u.py`
   - `docdog.top` (latino / argentina)
   - `tv-logo/tv-logos` on GitHub
5. Updates `tvg-logo` on **all variants** of the same channel.
6. Saves the verified URL in `assets/logos.json`.
7. Syncs `LOGO_LIBRARY` in `clean_m3u.py` if applicable.
8. Runs `python3 scripts/clean_m3u.py`.

### JSON output

Parse only the JSON from `--json`. Possible status per channel:

| status | Meaning |
|--------|---------|
| `ok` | Current logo already works |
| `fixed` | Replaced with a verified URL |
| `failed` | No alternative found |

## Persistent icon registry

`assets/logos.json` stores verified URLs by channel name:

```json
{
  "tlc": {
    "channel": "TLC",
    "url": "https://docdog.top/logo/countries/latino/tlc.png",
    "source": "docdog_latino",
    "verified_at": "2026-09-11"
  }
}
```

Used to reuse the icon if the channel is replaced later (new stream URL, same logo).

`clean_m3u.py` reads this file when filling missing logos; priority: sibling variants > assets > LOGO_LIBRARY.

## Agent rules

1. **Single command**: do not run curl manually or edit `official.m3u` by hand.
2. **Do not read the entire official.m3u**: the script resolves everything; use `--json` for the summary.
3. **Optional dry-run**: if the user only wants diagnosis, use `--dry-run --json` (does not write files).
4. **Multiple IDs**: one command with all IDs; the script deduplicates base channels.
5. **Cleanup included**: do not run `clean_m3u.py` separately after a successful fix.

## Response to the user

After a successful fix (`fixed` or `ok` on all channels), summarize in plain language:

- Which IDs/channels were processed
- Whether it stayed `ok` or the URL changed (`fixed`)
- The new URL only if there was a change

If any channel returns `failed`, indicate which ones and that no alternative was found.

## Common mistakes

- **Running without IDs**: forbidden; ask for IDs first.
- **Searching by name instead of ID**: forbidden; require the global ID.
- **Editing official.m3u manually**: always use `fix_logos.py`.
- **Forgetting network**: the script needs HTTP to verify and discover logos.
- **Forgetting --json**: always use `--json` to spend fewer tokens interpreting results.
