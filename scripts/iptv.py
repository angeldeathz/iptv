#!/usr/bin/env python3
"""Single CLI for the IPTV lineup.

datasource/*.m3u (channels) + assets/logos.json (logos) -> official.m3u (generated, never edited).
Every command prints JSON; commands that change channels rebuild official.m3u at the end.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

import logos
import streams
from playlist import (
    OFFICIAL_PATH,
    SECTIONS,
    Channel,
    Entry,
    Playlist,
    PlaylistError,
    Section,
    append_to_backup,
    normalize_text,
    render_official,
    search_text_matches_query,
    resolve_section,
    validate_channel_name,
)

FIRST_POSITION = "first"


@dataclass
class MoveRequest:
    channel: Channel
    section: Section
    anchor: object  # Entry to insert after, FIRST_POSITION, or None for the end of the section


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = args.handler(args)
    except PlaylistError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Generate official.m3u from datasource/")
    build.add_argument("--check", action="store_true", help="Fail if official.m3u is out of date")
    build.set_defaults(handler=run_build)

    listing = commands.add_parser("list", help="List channels with their global IDs")
    listing.add_argument("--filter", help="Case/accent-insensitive text to match in label or URL")
    listing.add_argument("--section", help=f"One of: {', '.join(s.key for s in SECTIONS)}")
    listing.set_defaults(handler=run_list)

    add = commands.add_parser("add", help="Add stream URLs for a channel (Astra URLs are probed)")
    add.add_argument("--name", required=True, help="Clean channel name, e.g. 'Star Channel'")
    add.add_argument("--url", dest="urls", action="append", required=True, help="Repeat per source")
    add.add_argument("--section", help="Required for new channels")
    add.add_argument("--after", type=int, help="New channels only: insert after this global ID")
    add.add_argument("--logo", help="Logo to register when the channel has none")
    add.set_defaults(handler=run_add)

    edit = commands.add_parser("edit", help="Remove, back up and move channels in one atomic step")
    edit.add_argument("--remove", nargs="+", type=int, action="extend", default=[], metavar="ID")
    edit.add_argument("--backup", nargs="+", type=int, action="extend", default=[], metavar="ID")
    edit.add_argument(
        "--move", nargs="+", action="extend", default=[], metavar="ID:SECTION[:AFTER_ID|first]"
    )
    edit.add_argument("--expect", nargs="+", action="extend", default=[], metavar="ID:NAME")
    edit.add_argument("--dry-run", action="store_true")
    edit.set_defaults(handler=run_edit)

    set_url = commands.add_parser("set-url", help="Replace the stream URL of one channel")
    set_url.add_argument("id", type=int)
    set_url.add_argument("url")
    set_url.add_argument("--expect", nargs="+", action="extend", default=[], metavar="ID:NAME")
    set_url.set_defaults(handler=run_set_url)

    logo = commands.add_parser("logo", help="Verify/repair channel logos in assets/logos.json")
    logo.add_argument("ids", nargs="+", type=int)
    logo.add_argument("--url", help="Set this logo (verified first); exactly one channel")
    logo.add_argument("--dry-run", action="store_true")
    logo.set_defaults(handler=run_logo)

    search = commands.add_parser("search", help="Search Astra origin playlists")
    search.add_argument("query")
    search.add_argument("--regex", action="store_true")
    search.add_argument("--source", action="append", default=[], metavar="HOST")
    search.set_defaults(handler=run_search)
    return parser


def run_build(args: argparse.Namespace) -> dict:
    playlist = Playlist.load()
    content, names_without_logo = render_official(playlist, logos.load_logos())
    if args.check:
        with open(OFFICIAL_PATH, encoding="utf-8") as handle:
            if handle.read() != content:
                raise PlaylistError("official.m3u is out of date; run: python3 scripts/iptv.py build")
        return {"status": "up_to_date"}
    write_official(content)
    return {"status": "built", "channels": len(playlist.channels()), "without_logo": names_without_logo}


def run_list(args: argparse.Namespace) -> dict:
    section = resolve_section(args.section) if args.section else None
    needle = normalize_text(args.filter or "")
    return {
        "channels": [
            channel.to_dict()
            for channel in Playlist.load().channels()
            if (section is None or channel.section == section)
            and needle in normalize_text(f"{channel.label} {channel.entry.url}")
        ]
    }


def run_add(args: argparse.Namespace) -> dict:
    validate_channel_name(args.name.strip())
    playlist = Playlist.load()
    logo_by_channel = logos.load_logos()
    variants = playlist.find_by_name(args.name.strip())
    name = variants[0].entry.name if variants else args.name.strip()
    section, index = resolve_add_position(playlist, variants, args)

    known_urls = {streams.canonical_url(c.entry.url): c.label for c in playlist.channels()}
    added: list[Entry] = []
    skipped = []
    for raw_url in args.urls:
        url = streams.resolve_stream_url(raw_url)
        existing_label = known_urls.get(streams.canonical_url(url))
        if existing_label:
            skipped.append({"url": url, "already_in": existing_label})
            continue
        entry = Entry(name, url)
        playlist.insert(entry, section, index)
        index += 1
        known_urls[streams.canonical_url(url)] = f"{name} (added by this command)"
        added.append(entry)

    logo_status = register_logo(name, args.logo, logo_by_channel)
    build = publish(playlist, logo_by_channel)
    if logo_status == "registered":
        logos.save_logos(logo_by_channel)
    return {
        "added": [playlist.channel_of(entry).to_dict() for entry in added],
        "skipped_duplicates": skipped,
        "logo": logo_status,
        "build": build,
    }


def run_edit(args: argparse.Namespace) -> dict:
    playlist = Playlist.load()
    snapshot = {channel.channel_id: channel for channel in playlist.channels()}
    verify_expectations(snapshot, args.expect)
    to_remove = [lookup(snapshot, channel_id) for channel_id in args.remove]
    to_backup = [lookup(snapshot, channel_id) for channel_id in args.backup]
    moves = [parse_move(raw, snapshot) for raw in args.move]
    ensure_valid_edit(to_remove + to_backup + [move.channel for move in moves], moves)

    move_steps = [{"action": "move", **move.channel.to_dict(), "to": describe_target(move)} for move in moves]
    plan = (
        [{"action": "remove", **channel.to_dict()} for channel in to_remove]
        + [{"action": "backup", **channel.to_dict()} for channel in to_backup]
        + move_steps
    )
    if args.dry_run:
        return {"dry_run": True, "plan": plan}

    for channel in to_remove + to_backup:
        playlist.remove(channel.entry)
    apply_moves(playlist, moves)

    logo_by_channel = logos.load_logos()
    skipped_backup = append_to_backup(to_backup, logo_by_channel) if to_backup else []
    build = publish(playlist, logo_by_channel)
    for step, move in zip(move_steps, moves):
        step["new_id"] = playlist.channel_of(move.channel.entry).channel_id
    return {
        "applied": plan,
        "backup_already_had": [channel.label for channel in skipped_backup],
        "build": build,
    }


def run_set_url(args: argparse.Namespace) -> dict:
    playlist = Playlist.load()
    verify_expectations({c.channel_id: c for c in playlist.channels()}, args.expect)
    channel = playlist.channel(args.id)
    old_url = channel.entry.url
    channel.entry.url = streams.resolve_stream_url(args.url)
    build = publish(playlist, logos.load_logos())
    return {
        "updated": {"id": channel.channel_id, "channel": channel.label, "old_url": old_url,
                    "new_url": channel.entry.url},
        "build": build,
    }


def run_logo(args: argparse.Namespace) -> dict:
    playlist = Playlist.load()
    logo_by_channel = logos.load_logos()
    names = list(dict.fromkeys(playlist.channel(channel_id).entry.name for channel_id in args.ids))
    if args.url and len(names) != 1:
        raise PlaylistError(f"--url applies to exactly one channel, got: {', '.join(names)}")

    results = [check_logo(name, args.url, logo_by_channel) for name in names]
    changed = any(result["status"] in ("fixed", "set") for result in results)
    build = None
    if changed and not args.dry_run:
        build = publish(playlist, logo_by_channel)
        logos.save_logos(logo_by_channel)
    return {"results": results, "dry_run": args.dry_run, "build": build}


def run_search(args: argparse.Namespace) -> dict:
    hosts = select_hosts(args.source)
    official_by_url = {streams.canonical_url(c.entry.url): c.label for c in Playlist.load().channels()}
    result = streams.search_sources(build_matcher(args.query, args.regex), hosts)
    for match in result["matches"]:
        match["in_official"] = official_by_url.get(streams.canonical_url(match["url"]))
    return {"query": args.query, "total_matches": len(result["matches"]), **result}


def publish(playlist: Playlist, logo_by_channel: dict) -> dict:
    """Render (and validate) before writing so a failing build never leaves datasource half-written."""
    content, names_without_logo = render_official(playlist, logo_by_channel)
    playlist.save()
    write_official(content)
    return {"channels": len(playlist.channels()), "without_logo": names_without_logo}


def write_official(content: str) -> None:
    with open(OFFICIAL_PATH, "w", encoding="utf-8") as handle:
        handle.write(content)


def resolve_add_position(playlist: Playlist, variants: list[Channel], args) -> tuple[Section, int]:
    requested_section = resolve_section(args.section) if args.section else None
    if variants:
        last_variant = variants[-1]
        if args.after is not None:
            raise PlaylistError("--after is only for new channels; new variants go after the last one")
        if requested_section and requested_section != last_variant.section:
            raise PlaylistError(
                f"'{last_variant.entry.name}' lives in section '{last_variant.section.key}' "
                f"(ID {last_variant.channel_id}); omit --section or use edit --move"
            )
        return playlist.position_after(last_variant.entry)
    if args.after is not None:
        anchor = playlist.channel(args.after)
        if requested_section and requested_section != anchor.section:
            raise PlaylistError(f"ID {args.after} is in section '{anchor.section.key}', not '{args.section}'")
        return playlist.position_after(anchor.entry)
    if requested_section is None:
        raise PlaylistError(f"'{args.name}' is a new channel: --section is required")
    return requested_section, len(playlist.entries_by_section[requested_section])


def register_logo(name: str, logo_url: str, logo_by_channel: dict) -> str:
    if name in logo_by_channel:
        return "kept_existing"
    if not logo_url:
        return "missing"
    if not logos.is_working_logo(logo_url):
        return "rejected_broken_url"
    logo_by_channel[name] = logo_url
    return "registered"


def verify_expectations(channels_by_id: dict, expectations: list[str]) -> None:
    errors = []
    for raw in expectations:
        id_part, separator, fragment = raw.partition(":")
        if not separator or not id_part.strip().isdigit() or not fragment.strip():
            raise PlaylistError(f"invalid --expect '{raw}', use ID:NAME (e.g. 82:Star Channel)")
        channel = channels_by_id.get(int(id_part))
        if channel is None:
            errors.append(f"ID {id_part} does not exist")
        elif normalize_text(fragment) not in normalize_text(channel.label):
            errors.append(f"ID {id_part} is '{channel.label}', expected '{fragment.strip()}'")
    if errors:
        raise PlaylistError("expectation failed: " + "; ".join(errors))


def parse_move(raw: str, snapshot: dict) -> MoveRequest:
    parts = raw.split(":")
    if len(parts) not in (2, 3) or not parts[0].strip().isdigit():
        raise PlaylistError(f"invalid --move '{raw}', use ID:SECTION or ID:SECTION:AFTER_ID|first")
    section = resolve_section(parts[1])
    anchor = None
    if len(parts) == 3:
        anchor_spec = parts[2].strip()
        if anchor_spec == FIRST_POSITION:
            anchor = FIRST_POSITION
        elif anchor_spec.isdigit():
            anchor_channel = lookup(snapshot, int(anchor_spec))
            if anchor_channel.section != section:
                raise PlaylistError(f"anchor ID {anchor_spec} is not in section '{section.key}'")
            anchor = anchor_channel.entry
        else:
            raise PlaylistError(f"invalid position '{anchor_spec}' in --move '{raw}'")
    return MoveRequest(lookup(snapshot, int(parts[0])), section, anchor)


def ensure_valid_edit(affected: list[Channel], moves: list[MoveRequest]) -> None:
    if not affected:
        raise PlaylistError("nothing to do: pass --remove, --backup and/or --move")
    requested_ids = [channel.channel_id for channel in affected]
    repeated = sorted({channel_id for channel_id in requested_ids if requested_ids.count(channel_id) > 1})
    if repeated:
        raise PlaylistError(f"IDs requested more than once: {', '.join(map(str, repeated))}")
    affected_entries = {channel.entry for channel in affected}
    for move in moves:
        if isinstance(move.anchor, Entry) and move.anchor in affected_entries:
            raise PlaylistError(
                f"the anchor of --move for ID {move.channel.channel_id} is also removed, backed up or moved"
            )


def lookup(snapshot: dict, channel_id: int) -> Channel:
    if channel_id not in snapshot:
        raise PlaylistError(f"ID {channel_id} does not exist in official.m3u")
    return snapshot[channel_id]


def describe_target(move: MoveRequest) -> str:
    if move.anchor is None:
        return f"{move.section.key} (end)"
    if move.anchor == FIRST_POSITION:
        return f"{move.section.key} (first)"
    return f"{move.section.key} (after {move.anchor.name})"


def apply_moves(playlist: Playlist, moves: list[MoveRequest]) -> None:
    """Moves sharing a target keep their requested order (each goes after the previous one)."""
    for move in moves:
        playlist.remove(move.channel.entry)
    last_inserted: dict = {}
    for move in moves:
        target_key = (move.section, move.anchor)
        if target_key in last_inserted:
            section, index = playlist.position_after(last_inserted[target_key])
        elif move.anchor is None:
            section, index = move.section, len(playlist.entries_by_section[move.section])
        elif move.anchor == FIRST_POSITION:
            section, index = move.section, 0
        else:
            section, index = playlist.position_after(move.anchor)
        playlist.insert(move.channel.entry, section, index)
        last_inserted[target_key] = move.channel.entry


def check_logo(name: str, forced_url: str, logo_by_channel: dict) -> dict:
    current_url = logo_by_channel.get(name, "")
    if forced_url:
        if not logos.is_working_logo(forced_url):
            return {"channel": name, "status": "failed", "reason": "URL is not a reachable image"}
        logo_by_channel[name] = forced_url
        return {"channel": name, "status": "set", "old_url": current_url, "new_url": forced_url}
    if current_url and logos.is_working_logo(current_url):
        return {"channel": name, "status": "ok", "url": current_url}
    replacement = logos.find_working_logo(name, rejected_url=current_url)
    if not replacement:
        return {"channel": name, "status": "failed", "old_url": current_url,
                "reason": "no working alternative found; ask the user for a logo URL"}
    logo_by_channel[name] = replacement
    return {"channel": name, "status": "fixed", "old_url": current_url, "new_url": replacement}


def select_hosts(fragments: list[str]) -> tuple[str, ...]:
    if not fragments:
        return streams.SOURCE_PLAYLISTS
    hosts = tuple(host for host in streams.SOURCE_PLAYLISTS if any(f in host for f in fragments))
    if not hosts:
        raise PlaylistError(f"no origin server matches --source {', '.join(fragments)}")
    return hosts


def build_matcher(query: str, use_regex: bool):
    if use_regex:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as exc:
            raise PlaylistError(f"invalid regex: {exc}") from None
        return lambda name, group, url: pattern.search(f"{name} {group} {url}") is not None
    return lambda name, group, url: search_text_matches_query(query, name, group, url)


if __name__ == "__main__":
    sys.exit(main())
