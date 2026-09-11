---
name: m3u-remove-channels
description: "Remove channels from official.m3u by global ID and recalculate correlative IDs. Use when the user asks to remove, delete, or drop channels from the official list, remove sources that don't work, or clean up entries tested on TV."
---

# Remove channels from official.m3u

Workflow to permanently remove entries from `official.m3u` (they do not go to `backup.m3u`).

## Mandatory requirement: user IDs

**Do not run without IDs.** The user must provide one or more global IDs from `official.m3u` (the number at the start of `tvg-name`, e.g. `88` in `88 Star Channel 1`).

If the message does not include IDs:

1. Ask for them explicitly.
2. Stop. Do not infer IDs or search channels by name.

Accepted user formats:

- Comma-separated list: `88, 91, 102`
- Space-separated list: `88 91 102`
- Range: `88-92` (expand to `88 89 90 91 92`)

### Help the user identify IDs

If the user does not know which ID corresponds to a channel, you may list current entries without running the removal:

```bash
grep -E '^#EXTINF' official.m3u | head -30
```

Or, if they just tested on TV and want to remove down channels:

```bash
python3 scripts/check_channels.py
```

Even so, **do not remove until the user confirms the IDs**.

## Execution

From the repo root:

```bash
python3 scripts/remove_channels.py <id1> <id2> ...
```

Example:

```bash
python3 scripts/remove_channels.py 88 91
```

The script:

1. Extracts from `official.m3u` entries whose global ID matches.
2. Removes them permanently (they are not copied to `backup.m3u`).
3. Runs `python3 scripts/clean_m3u.py` to reorder categories, recalculate correlative IDs, and deduplicate URLs.

If any ID does not exist, the script fails; report the error to the user and do not say "trabajo realizado".

## Difference from m3u-to-backup

| Action | Skill / script |
|--------|----------------|
| Remove from official and save to backup | `m3u-to-backup` → `move_to_backup.py` |
| Remove from official without backup | `m3u-remove-channels` → `remove_channels.py` |

If the user wants to keep the source in case it works again, use `m3u-to-backup`, not this skill.

## Response to the user (required)

After a successful removal, the complete response to the user is **only** this line, with no text before or after:

```text
trabajo realizado
```

Do not add summaries, counts, channel names, removed IDs, extra confirmations, or any other phrase. Not even a period more.

## Common mistakes

- **Running without IDs**: forbidden; ask for IDs first.
- **Searching by name instead of ID**: forbidden; require the global ID.
- **Editing official.m3u manually**: always use `remove_channels.py`.
- **Confusing with backup**: if the user wants backup, use `move_to_backup.py`.
- **Forgetting cleanup**: the script already runs `clean_m3u.py`; no need to run it separately.
