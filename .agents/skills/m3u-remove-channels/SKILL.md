---
name: m3u-remove-channels
description: >-
  Permanently deletes channel entries from official.m3u via scripts/remove_channels.py
  or scripts/channel_ops.py and recalculates IDs. Entries are NOT saved to backup.m3u.
  Use when the user wants to eliminar, borrar, quitar, delete, or drop channels/sources
  for good after TV testing. Requires explicit global IDs — never infer from name. If the
  user says backup, respaldo, or mover a backup, use m3u-to-backup instead. For mixed
  remove+backup in one request, use channel_ops.py. Do NOT use for fixing logos or
  searching new stream URLs.
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

## ID safety (critical — read before every run)

**IDs are reassigned after every remove/backup because `clean_m3u.py` recalculates them.**

To avoid deleting the wrong channel:

1. **List and verify first** when the user names a channel or when multiple IDs are involved:

   ```bash
   python3 scripts/channel_ops.py --list --filter "universal premiere"
   ```

2. **Never chain** `remove_channels.py` and `move_to_backup.py` in separate commands for one user request. IDs from the first command are stale for the second. Use `channel_ops.py` instead.

3. **Use `--expect ID:NAME`** whenever you know the channel name from context. The script aborts if the ID does not match.

4. **Use `--dry-run`** before applying when the request touches 2+ IDs or mixes remove + backup.

5. **Read the plan output** before confirming success. If any resolved name does not match the user's intent, stop and fix the command.

## Execution

### Single action: remove only

From the repo root:

```bash
python3 scripts/remove_channels.py <id1> <id2> ... --expect <id>:<name> ...
```

Example:

```bash
python3 scripts/remove_channels.py 83 85 --expect '83:UNIVERSAL PREMIERE' --expect '85:UNIVERSAL CINEMA' --dry-run
python3 scripts/remove_channels.py 83 85 --expect '83:UNIVERSAL PREMIERE' --expect '85:UNIVERSAL CINEMA'
```

### Mixed action: remove + backup in one request

Use the atomic script:

```bash
python3 scripts/channel_ops.py --backup 84 --remove 83 85 --expect '84:UNIVERSAL PREMIERE' --expect '83:UNIVERSAL PREMIERE' --expect '85:UNIVERSAL CINEMA'
```

`channel_ops.py` resolves all IDs in a single read, applies every change, then runs `clean_m3u.py` once.

The script:

1. Prints the resolved plan (`REMOVE:` / `BACKUP:` with ID, tvg-name, URL).
2. Aborts if `--expect` does not match or an ID is missing.
3. Removes matching entries permanently (not copied to `backup.m3u`).
4. Runs `python3 scripts/clean_m3u.py` once at the end.

If any ID does not exist or name verification fails, the script fails; report the error to the user and do not say "trabajo realizado".

## Difference from m3u-to-backup

| Action | Skill / script |
|--------|----------------|
| Remove from official and save to backup | `m3u-to-backup` → `move_to_backup.py` or `channel_ops.py --backup` |
| Remove from official without backup | `m3u-remove-channels` → `remove_channels.py` or `channel_ops.py --remove` |
| Both in one user message | `channel_ops.py` only |

If the user wants to keep the source in case it works again, use `m3u-to-backup`, not this skill.

## Response to the user (required)

After a successful removal, the complete response to the user is **only** this line, with no text before or after:

```text
trabajo realizado
```

Do not add summaries, counts, channel names, removed IDs, extra confirmations, or any other phrase. Not even a period more.

## Common mistakes

- **Running without IDs**: forbidden; ask for IDs first.
- **Chaining remove + backup scripts**: forbidden; use `channel_ops.py`.
- **Using stale IDs after a prior remove/backup in the same turn**: forbidden; re-list IDs or pass all IDs to `channel_ops.py` in one command.
- **Skipping `--expect` when the channel name is known**: risky; always add it.
- **Searching by name instead of ID**: forbidden for choosing targets; `grep`/`--list` is only to help the user confirm IDs.
- **Editing official.m3u manually**: always use the scripts.
- **Confusing with backup**: if the user wants backup, use `move_to_backup.py` or `channel_ops.py --backup`.
- **Forgetting cleanup**: the scripts already run `clean_m3u.py`; no need to run it separately.
