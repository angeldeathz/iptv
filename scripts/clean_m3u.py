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
    name = re.sub(r'^(?:CL|MX|BR|USA|US|ES|LATIN\s*\d*|CINE)\s*[:|]\s*', '', display_name, flags=re.IGNORECASE)
    name = re.sub(r'^CINE\s*\|\s*', '', name, flags=re.IGNORECASE)
    
    # Step 2: Remove brackets/parentheses and their content (e.g., "(1080p)", "[Geo-blocked]", "(Event Only)")
    name = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]\s*', ' ', name)
    
    # Step 3: Remove country suffixes at the end of the name (e.g. " MX", " Brazil", " BR", " USA", " US", " CL", " Mexico")
    name = re.sub(r'\b(?:MX|Brazil|BR|USA|US|CL|Mexico|AR)\b\s*$', '', name, flags=re.IGNORECASE)
    
    # Step 4: Remove resolution/quality keywords at the end of the name (e.g. FHD, HD, SD, HEVC, 1080p? etc.)
    name = re.sub(r'\b(?:FHD|HD|SD|HEVC|1080p?|720p?|576p?|480p?)\b\s*$', '', name, flags=re.IGNORECASE)
    
    # Step 5: Normalize spaces
    name = re.sub(r'\s+', ' ', name).strip()
    
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

def classify_channel(clean_name, original_group, tvg_id):
    clean_name_lower = clean_name.lower()
    original_group_lower = (original_group or "").lower()
    tvg_id_lower = (tvg_id or "").lower()
    
    # 1. Nacionales
    if any(w in clean_name_lower for w in ["chilevision", "tvn", "bio bio tv", "la red", "mega", "vision latina"]):
        return "Nacionales"
    if original_group_lower in ["general", "latin 3", "nacionales"]:
        return "Nacionales"
        
    # 2. Regionales
    if "chilote" in clean_name_lower or original_group_lower in ["regionales", "regional"]:
        return "Regionales"
        
    # 3. Infantiles
    if any(w in clean_name_lower for w in ["cartoon", "disney", "dreamworks", "nick", "etc tv", "kids"]) or original_group_lower in ["animation", "kids", "infantiles"]:
        return "Infantiles"
        
    # 4. Peliculas
    if any(w in clean_name_lower for w in ["hbo", "cine", "dhe", "space", "paramount channel", "studio universal", "universal premier", "universal cinema"]):
        return "Peliculas"
    if original_group_lower in ["movies", "cine", "peliculas"]:
        return "Peliculas"
        
    # 5. Series
    if any(w in clean_name_lower for w in ["universal tv", "universal crime", "universal comedy", "sony entertainment", "axn", "fx", "star channel", "warner channel", "paramount network", "series"]):
        return "Series"
    if original_group_lower in ["series", "entertainment"]:
        return "Series"
        
    # 6. Deportes
    if any(w in clean_name_lower for w in ["sports", "espn", "fox sports", "directv sports", "stadium"]) or "deportes" in original_group_lower:
        return "Deportes"
        
    # 7. Noticias
    if any(w in clean_name_lower for w in ["cnn", "noticias", "news"]):
        return "Noticias"
        
    # 8. Musica
    if any(w in clean_name_lower for w in ["mtv", "festival", "music", "musica"]):
        return "Musica"
        
    # 9. Documentales
    if any(w in clean_name_lower for w in ["history", "discovery", "nat geo", "national geographic", "documentary"]) or "documentary" in original_group_lower or "documentales" in original_group_lower:
        return "Documentales"
        
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
        category = classify_channel(clean_name, attrs.get('group-title'), attrs.get('tvg-id'))
        
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
        first_idx = first_occurrence[e['clean_name']]
        q_score = e['quality_score']
        orig_idx = e['original_index']
        return (g_priority, first_idx, -q_score, orig_idx)
        
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
