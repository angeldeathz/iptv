# IPTV

Curated IPTV channel lineup for Latin America, focused on Chilean signals and Spanish-language content. The playlist to import is [`official.m3u`](official.m3u).

## Usage

Import `official.m3u` into your IPTV player (SS IPTV, VLC, TiviMate, IPTV Smarters, etc.). Every source has a global incremental ID and, when a channel has backups, a repetition index: `88 Star Channel 1`, `89 Star Channel 2`…

## How the lineup is built

`official.m3u` is a **generated file**. Do not edit it by hand.

| Path | Content |
|------|---------|
| `datasource/<section>.m3u` | The channels of each section. File order is the lineup order. |
| `assets/logos.json` | One logo URL per channel name, shared by all its variants. |
| `scripts/iptv.py` | The only tool that changes the lineup; rebuilds `official.m3u` after every change. |

Sections, in lineup order: `nacionales`, `noticias`, `infantiles`, `peliculas`, `series`, `deportes`, `musica`, `documentales`, `variedades`, `internacionales`, `experimentales` (24/7 - Experimentales).

A datasource entry only holds the clean channel name and the stream URL (plus `#EXTVLCOPT` lines when a source needs them):

```text
#EXTINF:-1,Mega 2
http://38.225.116.4:22000/play/a00u
```

The build adds the global ID and repetition index (`tvg-name`), `group-title`, `tvg-logo` from `assets/logos.json` and `audio-track="spa,eng"` on Astra `/play/` URLs. It fails on duplicate stream URLs or malformed entries, and lists channels without a logo.

To reorder channels by hand, move the blocks inside the datasource files and run `python3 scripts/iptv.py build`.

### Commands

Run from the repository root. Every command prints JSON; `search`, `add`, `set-url` and `logo` need network access.

| Command | Purpose |
|---------|---------|
| `python3 scripts/iptv.py build` | Generate `official.m3u` (`--check` fails if it is out of date) |
| `python3 scripts/iptv.py list --filter espn` | Show global IDs, sections and URLs |
| `python3 scripts/iptv.py edit --remove 83 --backup 84 --move 50:series:47 --dry-run` | Delete, move to `backup.m3u`, or move/reorder channels in one atomic step |
| `python3 scripts/iptv.py add --name "ESPN 2" --url URL` | Add sources to a channel (`--section` for new channels) |
| `python3 scripts/iptv.py set-url 42 URL` | Replace the URL of one source |
| `python3 scripts/iptv.py logo 197` | Verify a channel logo and look for a working alternative (`--url` to set one) |
| `python3 scripts/iptv.py search "star channel"` | Search the Astra origin servers (`--regex`, `--source HOST`) |

`add` and `set-url` probe Astra URLs: they keep MPEG-TS (`/play/<id>`) when the server serves it, because SS IPTV only shows the audio language menu for MPEG-TS, and fall back to HLS (`/play/<id>/index.m3u8`).

## Stable hosts

Not every host behaves the same. Most of the lineup uses **restream IPs** (`187.102.211.240:9001`, `38.226.49.253:8000`, etc.): VPS or home headends without a CDN, with variable latency and stability. The ones that usually load faster and hold up better are broadcast infrastructure or professional CDNs.

### CDNs and streaming platforms (high priority)

| Host | Type | Notes |
|------|------|-------|
| `origin.dpsgo.com` | DPS CDN / Canal 13 (SSAI) | 13 Cultura, 13 Festival, 13 Realities, 13 Kids. HTTPS, native HLS. |
| `redirector.rudo.video` | Rudo.video CDN | T13, TV+, UCL. |
| `redirector.dps.live` | DPS CDN | 13 Teleseries, 13 Pop. |
| `unlimited*.dps.live`, `jireh-*.dps.live` | DPS CDN (regional edges) | UChile TV, UCV TV, Cooperativa, Bio Bio TV. |
| `cdn.40mediagroup.com` | 40media Group CDN | ENT Family, ENT Channel + 5 Totalmusic. See the pattern below. |
| `mdstrm.com` | Mediastream | NTV, TVN3, TV Chile, Canal 24 Horas. |
| `cdn.global.elektamedia.com` | Elekta CDN (same pack as 40media) | ENT Channel variant. |

**Why they work well:** HTTPS, CDN edge servers, optimized HLS and no intermediate restream. It shows in channel start-up time and fewer drops.

#### 40media Group — full catalog (7 signals)

They do not publish `/playlist.m3u`, but the URL pattern is predictable:

```text
https://cdn.40mediagroup.com/live/c7eds/{NAME}/SA_LIVE_hls_enc/master.m3u8
```

| `{NAME}` | Channel |
|----------|---------|
| `ENT_Family` | ENT Family |
| `ENT_Channel` | ENT Channel |
| `Totalmusic` | Totalmusic |
| `Totalmusic_80s` | Totalmusic 80s |
| `Totalmusic_00s` | Totalmusic 00s |
| `Totalmusic_Concerts` | Totalmusic Concerts |
| `Totalmusic_Dance` | Totalmusic Dance |

Site: [40mediagroup.com/canales](https://40mediagroup.com/canales). Official logos at `https://www.40mediagroup.com/images/channels/{slug}.png`.

#### DPS / Rudo — no public catalog

Each URL is a contracted endpoint (SSAI event on `dpsgo.com`, redirector on `rudo.video`). There is no list to browse; only the signals already in the playlist or found in another source.

### Fast Astra origins

Among the Astra servers (`/play/aXXX`), some respond noticeably better than the rest:

| Server | M3U list | Channels | Notes |
|--------|----------|----------|-------|
| `45.232.210.1:18000` | http://45.232.210.1:18000/playlist.m3u | 66 | Zona Latina, Vía X, CHV HD, Canal 13, CNN Chile, Cartoon Network, etc. Dedicated origin; starts faster than many generic restreams. |

### IP restreams (most of the list)

Hosts like `187.102.211.240:9001`, `190.60.40.165:1010` and `190.61.42.218:9000` carry many signals but depend on a single origin without a CDN. Useful for variety and backups; prefer a CDN when the same channel has one.

### Choosing a source when adding channels

1. **Same channel, several URLs:** prefer a host from the CDN table when there is one.
2. **Search Astra:** `python3 scripts/iptv.py search "channel name"` — prefer `45.232.210.1:18000` and hosts that already appear often in `official.m3u`.
3. **HLS URL:** prefer `master.m3u8` over `tracks-v1a1/mono.ts.m3u8` (adaptive bitrate).
4. **Test on TV** and move failures to `backup.m3u` with `python3 scripts/iptv.py edit --backup ID`.

## Origin playlists

Several servers feeding this playlist run Astra and publish their full catalog at `/playlist.m3u`. They are useful to find replacements when a channel goes down, or to compare signals of the same channel (for example, to find a 1080p source or one without English-first audio). `iptv.py search` queries all of them.

| Server | M3U list | Published channels |
|--------|----------|--------------------|
| `38.44.109.41:8003` | http://38.44.109.41:8003/playlist.m3u | 248 |
| `181.78.8.199:8000` | http://181.78.8.199:8000/playlist.m3u | 245 |
| `190.108.83.69:8000` | http://190.108.83.69:8000/playlist.m3u | 211 |
| `45.167.1.137:8000` | http://45.167.1.137:8000/playlist.m3u | 200 |
| `45.167.1.138:8000` | http://45.167.1.138:8000/playlist.m3u | 200 |
| `190.60.40.165:1010` | http://190.60.40.165:1010/playlist.m3u | 193 |
| `72.1.184.5:8089` | http://72.1.184.5:8089/playlist.m3u | 171 |
| `45.186.254.75:8000` | http://45.186.254.75:8000/playlist.m3u | 168 |
| `209.14.98.47:8000` | http://209.14.98.47:8000/playlist.m3u | 157 |
| `45.5.118.152:8000` | http://45.5.118.152:8000/playlist.m3u | 148 |
| `38.226.49.253:8000` | http://38.226.49.253:8000/playlist.m3u | 142 |
| `181.224.255.210:8001` | http://181.224.255.210:8001/playlist.m3u | 132 |
| `45.5.116.228:8000` | http://45.5.116.228:8000/playlist.m3u | 132 |
| `190.61.43.117:45000` | http://190.61.43.117:45000/playlist.m3u | 124 |
| `190.61.42.218:9000` | http://190.61.42.218:9000/playlist.m3u | 117 |
| `187.102.211.240:9001` | http://187.102.211.240:9001/playlist.m3u | 117 |
| `45.167.2.101:8000` | http://45.167.2.101:8000/playlist.m3u | 117 |
| `190.14.10.19:16000` | http://190.14.10.19:16000/playlist.m3u | 109 |
| `170.247.204.9:8000` | http://170.247.204.9:8000/playlist.m3u | 104 |
| `205.235.6.29:8000` | http://205.235.6.29:8000/playlist.m3u | 86 |
| `190.217.66.92:8000` | http://190.217.66.92:8000/playlist.m3u | 82 |
| `181.78.20.119:58002` | http://181.78.20.119:58002/playlist.m3u | 77 |
| `45.232.210.1:18000` | http://45.232.210.1:18000/playlist.m3u | 66 |
| `177.74.205.189:8000` | http://177.74.205.189:8000/playlist.m3u | 66 |
| `181.224.200.5:2277` | http://181.224.200.5:2277/playlist.m3u | 47 |
| `190.108.90.142:8000` | http://190.108.90.142:8000/playlist.m3u | 31 |
| `38.225.116.4:22000` | http://38.225.116.4:22000/playlist.m3u | 21 |

Counts verified in September 2026. Not applicable: `138.121.15.230:9002` (404), `177.234.249.178:8888` (404), `alfa.7057460.xyz:2095` (Xtream panel, not Astra) and CDNs with a closed catalog (`jmp2.uk`, `mdstrm.com`, `dps.live`, `dpsgo.com`, `rudo.video`, `40mediagroup.com`, etc.); see [Stable hosts](#stable-hosts).

Before adopting a new source, check resolution and audio tracks with `ffprobe`: some signals carry dual audio (English first) and several Smart TV players cannot switch tracks.
