---
name: m3u-to-backup
description: >-
  Moves channel entries from official.m3u to backup.m3u via scripts/move_to_backup.py
  or scripts/channel_ops.py (keeps the source, removes from official, recalculates
  official IDs). Use when the user says backup, respaldo, mover a backup, pasar a
  backup, or wants to quitar de official but keep the stream for later. Requires
  explicit global IDs — never infer from name. If the user wants permanent deletion
  with no backup, use m3u-remove-channels instead. For mixed remove+backup in one
  request, use channel_ops.py. Do NOT use for fixing logos or searching new URLs.
---

# Move channels to backup.m3u

Workflow to remove entries from `official.m3u` and save them in `backup.m3u`.

## Mandatory requirement: user IDs

**Do not run without IDs.** The user must provide one or more global IDs from `official.m3u` (the number at the start of `tvg-name`, e.g. `88` in `88 Star Channel 1`).

If the message does not include IDs, ask for them and stop. Do not infer IDs or search channels by name.

Accepted user formats:

- Comma-separated list: `88, 91, 102`
- Space-separated list: `88 91 102`
- Range: `88-92` (expand to `88 89 90 91 92`)

## ID safety (critical — read before every run)

**IDs are reassigned after every remove/backup because `clean_m3u.py` recalculates them.**

To avoid moving the wrong channel:

1. **List and verify first** when the user names a channel or when multiple IDs are involved:

   ```bash
   python3 scripts/channel_ops.py --list --filter amc
   ```

2. **Never chain** `move_to_backup.py` and `remove_channels.py` in separate commands for one user request. Use `channel_ops.py` instead.

3. **Use `--expect ID:NAME`** whenever you know the channel name from context. The script aborts if the ID does not match.

4. **Use `--dry-run`** before applying when the request touches 2+ IDs or mixes remove + backup.

5. **Read the plan output** before confirming success. If any resolved name does not match the user's intent, stop and fix the command.

## Execution

### Single action: backup only

From the repo root:

```bash
python3 scripts/move_to_backup.py <id1> <id2> ... --expect <id>:<name> ...
```

Example:

```bash
python3 scripts/move_to_backup.py 84 --expect '84:UNIVERSAL PREMIERE' --dry-run
python3 scripts/move_to_backup.py 84 --expect '84:UNIVERSAL PREMIERE'
```

### Mixed action: backup + remove in one request

Use the atomic script:

```bash
python3 scripts/channel_ops.py --backup 84 --remove 83 85 --expect '84:UNIVERSAL PREMIERE' --expect '83:UNIVERSAL PREMIERE' --expect '85:UNIVERSAL CINEMA'
```

`channel_ops.py` resolves all IDs in a single read, applies every change, then runs `clean_m3u.py` once.

The script:

1. Prints the resolved plan (`BACKUP:` / `REMOVE:` with ID, tvg-name, URL).
2. Aborts if `--expect` does not match or an ID is missing.
3. Adds matches to `backup.m3u` without the global ID in `tvg-name`.
4. Skips URLs already present in `backup.m3u`.
5. Regroups `backup.m3u` by `group-title`.
6. Runs `python3 scripts/clean_m3u.py` once on `official.m3u`.

If any ID does not exist or name verification fails, the script fails; report the error to the user and do not say "trabajo realizado".

## Response on completion (required)

When the work finishes successfully, the response to the user must be **exactly** one line:

```text
trabajo realizado
```

Nothing else. No summary, no list of moved channels, no counts, no explanations, no follow-up questions.

## Common mistakes

- **Running without IDs**: forbidden; ask for IDs first.
- **Chaining backup + remove scripts**: forbidden; use `channel_ops.py`.
- **Using stale IDs after a prior remove/backup in the same turn**: forbidden; re-list IDs or pass all IDs to `channel_ops.py` in one command.
- **Skipping `--expect` when the channel name is known**: risky; always add it.
- **Searching by name instead of ID**: forbidden for choosing targets; `grep`/`--list` is only to help the user confirm IDs.
- **Editing lists manually**: always use the scripts.
- **Forgetting cleanup**: the scripts already run `clean_m3u.py`; no need to run it separately.
