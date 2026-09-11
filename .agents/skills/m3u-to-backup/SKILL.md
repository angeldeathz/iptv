---
name: m3u-to-backup
description: >-
  Moves channel entries from official.m3u to backup.m3u via scripts/move_to_backup.py
  (keeps the source, removes from official, recalculates official IDs). Use when
  the user says backup, respaldo, mover a backup, pasar a backup, or wants to
  quitar de official but keep the stream for later. Requires explicit global IDs —
  never infer from name. If the user wants permanent deletion with no backup, use
  m3u-remove-channels instead. Do NOT use for fixing logos or searching new URLs.
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

## Execution

From the repo root:

```bash
python3 scripts/move_to_backup.py <id1> <id2> ...
```

Example:

```bash
python3 scripts/move_to_backup.py 88 91
```

The script:

1. Extracts from `official.m3u` entries whose global ID matches.
2. Adds them to `backup.m3u` without the global ID in `tvg-name` or the visible name (format `Star Channel 1`).
3. Skips URLs already present in `backup.m3u`.
4. Regroups `backup.m3u` by `group-title`.
5. Runs `python3 scripts/clean_m3u.py` to reorder and recalculate IDs in `official.m3u`.

If any ID does not exist, the script fails; report the error to the user and do not say "trabajo realizado".

## Response on completion (required)

When the work finishes successfully, the response to the user must be **exactly** one line:

```text
trabajo realizado
```

Nothing else. No summary, no list of moved channels, no counts, no explanations, no follow-up questions.

## Common mistakes

- **Running without IDs**: forbidden; ask for IDs first.
- **Searching by name instead of ID**: forbidden; require the global ID.
- **Editing lists manually**: always use `move_to_backup.py`.
- **Forgetting cleanup**: the script already runs `clean_m3u.py`; no need to run it separately.
