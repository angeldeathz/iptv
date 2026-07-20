#!/usr/bin/env python3
import re
import os
import sys

def parse_extinf(extinf_line):
    # Split the attributes and the display name on the first comma not in quotes
    comma_idx = -1
    in_quotes = False
    for idx, char in enumerate(extinf_line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            comma_idx = idx
            break
            
    if comma_idx == -1:
        attrs_part = extinf_line
        display_name = ""
    else:
        attrs_part = extinf_line[:comma_idx]
        display_name = extinf_line[comma_idx+1:].strip()
        
    # Extract attributes key="value"
    attrs = {}
    pattern = r'([\w\-]+)\s*=\s*"([^"]*)"'
    for key, val in re.findall(pattern, attrs_part):
        attrs[key] = val
        
    duration_match = re.match(r'^#EXTINF:\s*(-?\d+)', attrs_part)
    duration = duration_match.group(1) if duration_match else "-1"
    
    return duration, attrs, display_name

def clean_channel_name(display_name):
    # If the name is already in the formatted structure (e.g. "1 Chilevision 1"), extract the middle part first
    match = re.match(r'^\d+\s+(.+)\s+\d+$', display_name)
    if match:
        display_name = match.group(1)

    # Step 1: Strip country prefixes (e.g. CL:, MX:, BR:, USA:, US:, ES:, CINE |) at the beginning
    name = re.sub(r'^:\s*', '', display_name)
    name = re.sub(r'^(?:CL|MX|BR|USA|US|ES|LATIN\s*\d*|CINE)\s*[:|]\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^CINE\s*\|\s*', '', name, flags=re.IGNORECASE)
    
    # Step 2: Remove brackets/parentheses and their content (e.g., "(1080p)", "[Geo-blocked]", "(Event Only)")
    name = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]\s*', ' ', name)
    
    # Step 3: Remove lineup number prefixes (e.g. "89 - DW Español")
    name = re.sub(r'^\d+\s*-\s*', '', name)

    # Step 4: Remove pipe-delimited metadata (e.g. "| HD | Santiago", "| HD | Alt.")
    name = re.sub(
        r'\s*\|\s*(?:HD|SD|FHD|HEVC|1080p?|720p?|576p?|480p?|Santiago|Alt\.?)\s*',
        ' ',
        name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r'\s*\|+\s*', ' ', name)

    # Step 5: Remove country suffixes at the end of the name (e.g. " MX", " PE", " CO")
    name = re.sub(r'\b(?:MX|Brazil|BR|USA|US|CL|Mexico|AR|PE|CO)\b\s*$', '', name, flags=re.IGNORECASE)
    
    # Step 6: Remove resolution/quality keywords at the end of the name (e.g. FHD, HD, SD, HEVC, 1080p? etc.)
    name = re.sub(r'\b(?:FHD|HD|SD|HEVC|1080p?|720p?|576p?|480p?)\b\s*$', '', name, flags=re.IGNORECASE)
    
    # Step 7: Normalize spaces
    name = re.sub(r'\s+', ' ', name).strip()

    # Known display-name overrides
    overrides = {
        "zona latina": "Zona Latina",
        "via x": "Via X",
        "t13": "T13",
        "ucv tv": "UCV TV",
        "tv+": "TV+",
        "multipremier": "Multipremier",
        "tv nostalgia": "TV Nostalgia",
        "disney jr": "Disney Jr.",
        "ent family": "ENT Family",
        "atres series": "ATRES Series",
        "bbc series": "BBC Series",
        "tnt sports premium": "TNT Sports Premium",
        "dw español": "DW Español",
    }
    name = overrides.get(name.lower(), name)
    
    return name

def get_quality_score(display_name):
    display_name_lower = display_name.lower()
    if re.search(r'\bhevc\b', display_name_lower):
        return 6
    if re.search(r'\bfhd\b|\b1080p?\b', display_name_lower):
        return 5
    if re.search(r'\bhd\b|\b720p?\b', display_name_lower):
        return 4
    if re.search(r'\b576p?\b', display_name_lower):
        return 3
    if re.search(r'\bsd\b|\b480p?\b', display_name_lower):
        return 2
    return 1

def is_13_channel(name_lower):
    """All Canal 13 / T13 variants belong to the 13 family."""
    if name_lower in ("13c", "t13"):
        return True
    if re.search(r"\bcanal\s*13\b", name_lower):
        return True
    if re.search(r"\b13\s+(internacional|cultura|teleseries|pop|festival)\b", name_lower):
        return True
    if re.search(r"^13\s", name_lower):
        return True
    return False


def get_13_suborder(name_lower):
    """Order within the 13 channel block (like open-TV lineup)."""
    if re.search(r"\bcanal\s*13\b", name_lower):
        return 0
    if name_lower == "t13":
        return 1
    if "13 internacional" in name_lower:
        return 2
    if "13 festival" in name_lower:
        return 3
    if name_lower in ("13c",) or "13 cultura" in name_lower:
        return 4
    if "13 teleseries" in name_lower:
        return 5
    if "13 pop" in name_lower:
        return 6
    return 7


def is_pluto_tv(clean_name, url="", logo=""):
    """Detect Pluto TV channels by name, logo host, or stream URL."""
    name_lower = clean_name.lower()
    url_lower = (url or "").lower()
    logo_lower = (logo or "").lower()
    if "pluto tv" in name_lower or name_lower.startswith("pluto "):
        return True
    if "pluto.tv" in logo_lower:
        return True
    if "jmp2.uk/plu-" in url_lower:
        return True
    return False


def get_nacional_lineup_key(clean_name):
    """Operator-style order for Chilean open-TV nationals."""
    n = clean_name.lower()

    if re.search(r"\bmega\b", n) and not re.search(r"señal|senal", n):
        return (0, 0, clean_name.lower())
    if re.search(r"\bmega\b", n):
        return (0, 1, clean_name.lower())

    if n == "chv" or "chilevision" in n:
        return (1, 0, clean_name.lower())

    if re.search(r"\btvn\b", n) or n.startswith("tvn"):
        if "nostalgia" in n:
            return (90, 0, clean_name.lower())
        sub = 0 if n == "tvn" else 1
        return (2, sub, clean_name.lower())

    if is_13_channel(n):
        return (3, get_13_suborder(n), clean_name.lower())

    if "ucv" in n:
        return (4, 0, clean_name.lower())

    if "zona latina" in n:
        return (5, 0, clean_name.lower())
    if "via x" in n:
        return (5, 1, clean_name.lower())

    if n in ("tv+", "tv plus"):
        return (6, 0, clean_name.lower())

    if any(w in n for w in ["bio bio tv", "la red", "vision latina", "24 horas", "ntv", "etc tv"]):
        return (7, 0, clean_name.lower())

    return (8, 0, clean_name.lower())


def classify_channel(clean_name, original_group, tvg_id, url="", logo=""):
    clean_name_lower = clean_name.lower()
    original_group_lower = (original_group or "").lower()
    tvg_id_lower = (tvg_id or "").lower()

    # Pluto TV -> dedicated group (before content-based categories)
    if is_pluto_tv(clean_name, url, logo):
        return "Pluto Tv"

    # EnerGeek -> Infantiles
    if "energeek" in clean_name_lower:
        return "Infantiles"

    # All 13-family channels -> Nacionales (before festival/music false positives)
    if is_13_channel(clean_name_lower):
        return "Nacionales"

    # TNT Sports -> Deportes (before generic series/tnt checks)
    if "tnt sports" in clean_name_lower:
        return "Deportes"

    # Zona Latina, Via X, TV+ -> Nacionales
    if any(w in clean_name_lower for w in ["zona latina", "via x"]) or clean_name_lower in ("tv+", "tv plus"):
        return "Nacionales"

    # Puranoticia -> Noticias
    if "puranoticia" in clean_name_lower:
        return "Noticias"

    # 1. Nacionales
    if any(w in clean_name_lower for w in ["chilevision", "tvn", "bio bio tv", "la red", "mega", "vision latina", "ucv", "24 horas", "chv", "ntv"]):
        return "Nacionales"
    if original_group_lower in ["general", "latin 3", "nacionales", "01. tv abierta"]:
        return "Nacionales"
        
    # 2. Regionales
    if "chilote" in clean_name_lower or original_group_lower in ["regionales", "regional"]:
        return "Regionales"
        
    # 3. Infantiles
    if any(w in clean_name_lower for w in ["cartoon", "cartoons", "disney", "dreamworks", "nick", "kids", "esponja", "spongebob", "disney jr", "tooncast", "cartoonito", "retromagico", "supertoons", "laika channel", "ent family"]):
        return "Infantiles"
        
    # 4. Peliculas
    if any(w in clean_name_lower for w in ["hbo", "cinecanal", "cine", "dhe", "space", "paramount channel", "studio universal", "universal premier", "universal cinema", "showtime", "artflix", "golden", "de pelicula", "pelicula", "tcm", "cinemax", "fmh movies", "film&arts", "europa", "multipremier"]):
        return "Peliculas"
    if any(g in original_group_lower for g in ["movies", "cine", "peliculas", "classic"]):
        return "Peliculas"
        
    # 5. Series
    if any(w in clean_name_lower for w in ["universal tv", "universal crime", "universal comedy", "universal reality", "sony entertainment", "axn", "fx", "star channel", "warner channel", "paramount network", "series", "comedy central", "a&e", "pop tv", "e! latin", "lifetime", "usa network", "syfy", "vh1", "tnt novelas", "tnt series", "adult swim", "atres series", "distrito comedia", "bbc series", "las estrellas"]):
        return "Series"
    if any(g in original_group_lower for g in ["series", "entertainment", "comedy", "entretenimiento premium", "03. entretenimiento"]):
        return "Series"
        
    # 6. Deportes
    if any(w in clean_name_lower for w in ["sports", "espn", "fox sport", "fox sports", "directv sports", "stadium", "goltv", "gol tv", "tnt sports"]):
        return "Deportes"
    if any(g in original_group_lower for g in ["deportes", "sports", "⚽ deportes 🏆"]):
        return "Deportes"
        
    # 7. Noticias
    if any(w in clean_name_lower for w in ["cnn", "noticias", "news", "estrella news", "abc news"]):
        return "Noticias"
    if "news" in original_group_lower:
        return "Noticias"
        
    # 8. Musica
    if any(w in clean_name_lower for w in ["mtv", "music", "musica"]) or (
        "festival" in clean_name_lower and not is_13_channel(clean_name_lower)
    ):
        return "Musica"
    if "music" in original_group_lower:
        return "Musica"
        
    # 9. Documentales
    if clean_name_lower == "id" or any(w in clean_name_lower for w in ["history", "discovery", "nat geo", "national geographic", "documentary", "archivos forenses", "animal planet", "dw español", "dw espanol"]):
        return "Documentales"
    if any(g in original_group_lower for g in ["documentary", "documentales", "documentales y cultura"]):
        return "Documentales"

    # 11. Internacionales
    if "tve" in clean_name_lower:
        return "Internacionales"

    # Fallback to original group hints from source playlists
    group_fallback = {
        "infantiles": "Infantiles",
        "animation": "Infantiles",
        "kids": "Infantiles",
        "peliculas": "Peliculas",
        "movies": "Peliculas",
        "cine": "Peliculas",
        "classic": "Peliculas",
        "series": "Series",
        "entertainment": "Series",
        "comedy": "Series",
        "entretenimiento premium": "Series",
        "03. entretenimiento": "Series",
        "deportes": "Deportes",
        "sports": "Deportes",
        "⚽ deportes 🏆": "Deportes",
        "news": "Noticias",
        "02. noticias": "Noticias",
        "music": "Musica",
        "documentary": "Documentales",
        "documentales": "Documentales",
        "documentales y cultura": "Documentales",
        "regionales": "Regionales",
        "regional": "Regionales",
        "nacionales": "Nacionales",
        "01. tv abierta": "Nacionales",
        "general": "Nacionales",
        "latin 3": "Nacionales",
    }
    if original_group_lower in group_fallback:
        return group_fallback[original_group_lower]
        
    return "Variedades"

GROUP_ORDER = [
    "Nacionales",
    "Regionales",
    "Infantiles",
    "Peliculas",
    "Series",
    "Deportes",
    "Noticias",
    "Musica",
    "Documentales",
    "Pluto Tv",
    "Variedades",
    "Internacionales"
]

def get_group_priority(group_name):
    try:
        return GROUP_ORDER.index(group_name)
    except ValueError:
        return len(GROUP_ORDER)

def normalize_url(url):
    return url.strip()

def deduplicate_by_url(entries):
    """Keep one entry per unique URL, preferring higher quality then earliest appearance."""
    best_by_url = {}
    for entry in entries:
        url = normalize_url(entry['url'])
        if url not in best_by_url:
            best_by_url[url] = entry
            continue
        current = best_by_url[url]
        candidate = entry
        if (candidate['quality_score'], -candidate['original_index']) > (
            current['quality_score'], -current['original_index']
        ):
            best_by_url[url] = candidate

    deduped = sorted(best_by_url.values(), key=lambda e: e['original_index'])
    return deduped, len(entries) - len(deduped)

def clean_m3u(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} does not exist.")
        sys.exit(1)
        
    with open(file_path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()
        
    # Step 1: Parse entries
    entries = []
    current_extinf = None
    current_options = []
    
    for idx, line in enumerate(raw_lines):
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith("#EXTM3U"):
            continue
            
        if line_str.startswith("#EXTINF:"):
            current_extinf = line_str
            current_options = []
        elif line_str.startswith("#EXTVLCOPT:"):
            current_options.append(line_str)
        elif line_str.startswith("#") and not line_str.startswith("#EXTINF") and not line_str.startswith("#EXTVLCOPT"):
            continue
        else:
            # We have a URL line
            if current_extinf:
                entries.append({
                    'extinf': current_extinf,
                    'options': current_options,
                    'url': line_str,
                    'original_index': len(entries)
                })
                current_extinf = None
                current_options = []
            else:
                # Orphaned URL recovery (like universalcomedy)
                if "universalcomedy" in line_str:
                    recovered_extinf = '#EXTINF:-1 tvg-id="UniversalComedy.us@SD" tvg-logo="https://i.imgur.com/avBL8pQ.png" group-title="Movies",Universal Comedy (1080p)'
                    entries.append({
                        'extinf': recovered_extinf,
                        'options': current_options,
                        'url': line_str,
                        'original_index': len(entries)
                    })
                    current_options = []
                else:
                    # Ignore other orphaned URLs
                    pass

    # Step 2: Clean, classify, and score entries
    # Gather casing mapping based on first occurrence
    casing_map = {}
    for entry in entries:
        _, _, display_name = parse_extinf(entry['extinf'])
        clean_name = clean_channel_name(display_name)
        clean_name_lower = clean_name.lower()
        if clean_name_lower not in casing_map:
            casing_map[clean_name_lower] = clean_name

    for entry in entries:
        duration, attrs, display_name = parse_extinf(entry['extinf'])
        raw_clean_name = clean_channel_name(display_name)
        clean_name = casing_map[raw_clean_name.lower()]
        
        # Determine taxonomy category
        forced_group = attrs.pop('editorial-group', None)
        if forced_group in GROUP_ORDER:
            category = forced_group
        else:
            category = classify_channel(
                clean_name,
                attrs.get('group-title'),
                attrs.get('tvg-id'),
                entry['url'],
                attrs.get('tvg-logo', ''),
            )
        
        # Remove tvg-id (not needed for IPTV TV apps)
        attrs.pop('tvg-id', None)
        # Set category as group-title
        attrs['group-title'] = category
        
        entry['duration'] = duration
        entry['attrs'] = attrs
        entry['clean_name'] = clean_name
        entry['quality_score'] = get_quality_score(display_name)
        entry['category'] = category

    entries, removed_duplicates = deduplicate_by_url(entries)

    # Step 3: Identify the first occurrence index of each clean name to preserve lineup order
    first_occurrence = {}
    for idx, entry in enumerate(entries):
        c_name = entry['clean_name']
        if c_name not in first_occurrence:
            first_occurrence[c_name] = idx

    # Step 4: Sort entries
    def sort_key(e):
        g_priority = get_group_priority(e['category'])
        if e['category'] == 'Nacionales':
            lineup_key = get_nacional_lineup_key(e['clean_name'])
        else:
            lineup_key = (first_occurrence[e['clean_name']], 0, e['clean_name'].lower())
        q_score = e['quality_score']
        orig_idx = e['original_index']
        return (g_priority, lineup_key, -q_score, orig_idx)
        
    sorted_entries = sorted(entries, key=sort_key)

    # Step 5: Assign global incremental IDs and repetition indexes
    occurrence_count = {}
    for idx, entry in enumerate(sorted_entries):
        global_id = idx + 1
        c_name = entry['clean_name']
        occurrence_count[c_name] = occurrence_count.get(c_name, 0) + 1
        rep_index = occurrence_count[c_name]
        
        entry['global_id'] = global_id
        entry['rep_index'] = rep_index
        entry['attrs']['tvg-name'] = f"{global_id} {c_name} {rep_index}"

    # Step 6: Write output
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        
        current_category = None
        for entry in sorted_entries:
            # Add visual separation/header comment for each category group
            if entry['category'] != current_category:
                current_category = entry['category']
                f.write(f"\n# ===== {current_category} =====\n\n")
                
            # Build the attribute string
            attrs_str = ""
            for k, v in entry['attrs'].items():
                attrs_str += f' {k}="{v}"'
                
            # Build the final channel name
            final_name = f"{entry['global_id']} {entry['clean_name']} {entry['rep_index']}"
            
            # Write #EXTINF line
            f.write(f"#EXTINF:{entry['duration']}{attrs_str},{final_name}\n")
            
            # Write #EXTVLCOPT lines if any
            for option in entry['options']:
                f.write(f"{option}\n")
                
            # Write URL
            f.write(f"{entry['url']}\n\n")

    print(
        f"Successfully cleaned and sorted {len(sorted_entries)} channels in {file_path}"
        + (f" (removed {removed_duplicates} duplicate URL(s))." if removed_duplicates else ".")
    )

if __name__ == "__main__":
    target = "/home/angeldeathz/iptv/official.m3u"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    clean_m3u(target)
