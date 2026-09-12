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
        
    return attrs, display_name


def sanitize_display_name(name):
    """Replace characters that break XML-based IPTV parsers on smart TVs."""
    name = re.sub(r'\bA&E\b', '__AE_BRAND__', name, flags=re.IGNORECASE)
    name = name.replace('&', 'and')
    name = name.replace('__AE_BRAND__', 'A&E')
    # Preserve 24/7; normalize other slashes (e.g. "HGTV / Discovery")
    name = re.sub(r'(?<!\d)/(?!\d)', ' ', name)
    name = re.sub(r'\b24\s+7\b', '24/7', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def normalize_url(url):
    url = url.strip()
    # Repair repeated .m3u8 suffixes from earlier buggy normalize runs
    url = re.sub(r'(\.m3u8)+(?=\?|$)', '.m3u8', url, flags=re.IGNORECASE)
    path = url.split('?', 1)[0]
    if path.lower().endswith('.m3u8'):
        return url
    # Xtream-style /play/<id> URLs without extension break many IPTV TV apps
    if re.search(r'/play/[^/?]+$', url):
        url += '.m3u8'
    return url


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
    name = re.sub(r'\b(?:MX|Brazil|BR|USA|US|CL|Mexico|AR|PE|CO|SUR|Oeste)\b\s*$', '', name, flags=re.IGNORECASE)

    # Step 5b: Remove regional / market descriptors from channel names
    name = re.sub(r'\bLatin\s+America\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\bLatinoamerica(?:no|na)?\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\bInternational\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^Pluto\s+TV\s+', '', name, flags=re.IGNORECASE)
    
    # Step 6: Remove resolution/quality keywords at the end of the name (e.g. FHD, HD, SD, HEVC, 1080p? etc.)
    name = re.sub(r'\b(?:FHD|HD|SD|HEVC|1080p?|720p?|576p?|480p?)\b\s*$', '', name, flags=re.IGNORECASE)
    
    # Step 7: Normalize spaces
    name = re.sub(r'\s+', ' ', name).strip()

    # HBO2 without space (and numbered variants like "069 HBO2") -> HBO 2
    hbo2_candidate = re.sub(r'^\d+\s+', '', name, flags=re.IGNORECASE)
    if re.fullmatch(r'hbo\s*2', hbo2_candidate, flags=re.IGNORECASE):
        name = 'HBO 2'

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
        "win futbol": "WIN Futbol",
        "bbc series": "BBC Series",
        "tnt sports premium": "https://docdog.top/logo/countries/latino/tnt.png",
        "dw español": "DW Español",
        "omusica tv": "OMusica TV",
        "warner channel": "Warner Channel",
        "star channel": "Star Channel",
        "cinemax": "Cinemax",
        "hbo mundi": "HBO Mundi",
        "hbo pop": "HBO Pop",
        "hbo xtreme": "HBO Xtreme",
        "hbo signature": "HBO Signature",
        "hbo family": "HBO Family",
        "hbo+": "HBO+",
        "hbo 2": "HBO 2",
        "hbo oeste": "HBO Oeste",
        "espn premium": "ESPN Premium",
        "documentary+": "Documentary+",
        "nickelodeon en español": "Nickelodeon",
        "nickelodeon teen": "Nickelodeon Teen",
        "nickelodeon toons": "Nickelodeon Toons",
        "comedy central en español": "Comedy Central",
        "mtv en español": "MTV",
        "cine terror": "Cine Terror",
        "bob esponja pantalones cuadrados": "Bob Esponja",
        "ucv televisión": "UCV TV",
        "tv chile": "TV Chile",
        "uchile tv": "UChile TV",
        "13 kids": "13 Kids",
        "13 realities": "13 Realities",
        "el pingüino tv": "El Pinguino TV",
        "solotv": "Solo TV",
        "cooperativa": "Cooperativa",
        "cnn chile": "CNN Chile",
        "fmh movies": "FMH Movies",
        "sony channel": "Sony Channel",
        "sony accion": "Sony Accion",
        "cine sony": "Sony Cine",
        "sony cine": "Sony Cine",
        "capitan tsubasa": "Capitan Tsubasa",
        "one piece 24/7": "One Piece 24/7",
        "mega 2": "Mega 2",
        "simpsons latino 24/7": "Simpsons Latino 24/7",
        "eurochannel": "Eurochannel",
        "grjngo": "Grjngo",
        "rewind": "Rewind",
        "west": "West",
        "paramount": "Paramount",
        "multipremier": "Multipremier",
        "history": "History",
        "history 2": "History 2",
        "max2": "MAX2",
        "maxcine comedy": "MAXCINE Comedy",
        "ucl": "UCL",
        "film&arts": "Film and Arts",
        "film and arts": "Film and Arts",
        "a&e": "https://download.logo.wine/logo/A%26E_(Australian_TV_channel)/A%26E_(Australian_TV_channel)-Logo.wine.png",
        "a and e": "A&E",
        "aande": "A&E",
        "discovery h&h": "Discovery Home and Health",
        "discovery home and health": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-kingdom/discovery-home-and-health-uk.png",
        "home & health": "Home and Health",
        "home and health": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/home-us.png",
    }
    name = overrides.get(name.lower(), name)
    name = sanitize_display_name(name)

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
    if re.search(r"\b13\s+(internacional|cultura|teleseries|pop|festival|realities)\b", name_lower):
        return True
    if re.search(r"^13\s", name_lower):
        return True
    return False


def get_13_suborder(name_lower):
    """Order within the 13 channel block (like open-TV lineup)."""
    if re.search(r"\bcanal\s*13\b", name_lower):
        return 0
    if name_lower in ("13c",) or "13 cultura" in name_lower:
        return 1
    if name_lower == "t13":
        return 2
    if "13 internacional" in name_lower:
        return 3
    if "13 festival" in name_lower:
        return 4
    if "13 teleseries" in name_lower:
        return 5
    if "13 pop" in name_lower:
        return 6
    if "13 realities" in name_lower:
        return 7
    return 8


def get_nacional_lineup_key(clean_name):
    """Operator-style order for Chilean open-TV nationals."""
    n = clean_name.lower()

    if n == "mega 2":
        return (0, 1, clean_name.lower())
    if re.search(r"\bmega\b", n) and not re.search(r"señal|senal|mega 2", n):
        return (0, 0, clean_name.lower())
    if re.search(r"\bmega\b", n):
        return (0, 2, clean_name.lower())

    if n == "chv" or "chilevision" in n:
        return (1, 0, clean_name.lower())

    if n == "ntv":
        return (2, 1, clean_name.lower())
    if re.search(r"\btvn\b", n) or n.startswith("tvn"):
        if "nostalgia" in n:
            return (90, 0, clean_name.lower())
        if n == "tvn":
            return (2, 0, clean_name.lower())
        return (2, 2, clean_name.lower())
    if "tv chile" in n:
        return (2, 3, clean_name.lower())
    if "uchile" in n:
        return (2, 4, clean_name.lower())

    if is_13_channel(n):
        return (3, get_13_suborder(n), clean_name.lower())

    if "ucv" in n:
        return (4, 0, clean_name.lower())
    if "la red" in n:
        return (4, 1, clean_name.lower())

    if "zona latina" in n:
        return (5, 0, clean_name.lower())
    if "via x" in n:
        return (5, 1, clean_name.lower())

    if n in ("tv+", "tv plus"):
        return (6, 0, clean_name.lower())

    if any(w in n for w in ["bio bio tv", "24 horas"]):
        return (7, 0, clean_name.lower())

    return (8, 0, clean_name.lower())


def get_hbo_suborder(name_lower):
    """Keep the full HBO block contiguous in Peliculas."""
    if name_lower == "hbo":
        return 0
    if name_lower == "hbo 2":
        return 1
    if name_lower.startswith("hbo 2 "):
        return 2
    if name_lower == "hbo mundi":
        return 3
    if name_lower == "hbo signature":
        return 4
    if name_lower == "hbo+":
        return 5
    if name_lower == "hbo pop":
        return 6
    if name_lower == "hbo xtreme":
        return 7
    if name_lower == "hbo family":
        return 8
    return 99


def get_peliculas_known_suborder(name_lower):
    """Operator-style block for well-known movie channels after HBO."""
    if name_lower == "cinecanal":
        return (1, 0)
    if name_lower == "space":
        return (2, 0)
    if name_lower == "cinemax":
        return (3, 0)
    if name_lower == "tnt" or (
        name_lower.startswith("tnt ")
        and not any(x in name_lower for x in ["sports", "novelas", "series"])
    ):
        return (3, 1)
    if name_lower == "paramount":
        return (4, 0)
    if name_lower == "star channel":
        return (5, 0)
    if name_lower == "fx" or name_lower.startswith("fx "):
        return (6, 0)
    if name_lower == "dhe" or name_lower.startswith("dhe "):
        return (7, 0)
    if name_lower == "amc" or name_lower.startswith("amc "):
        return (8, 0)
    if name_lower == "amc series" or name_lower.startswith("amc series "):
        return (8, 1)
    if name_lower == "sony channel" or name_lower.startswith("sony channel "):
        return (9, 2)
    if name_lower == "sony accion" or name_lower.startswith("sony accion "):
        return (9, 3)
    if name_lower == "sony cine" or name_lower.startswith("sony cine "):
        return (9, 4)
    if name_lower == "sony" or name_lower.startswith("sony "):
        return (9, 1)
    if name_lower == "studio universal" or name_lower.startswith("studio universal "):
        return (10, 0)
    if name_lower == "tcm" or name_lower.startswith("tcm "):
        return (11, 0)
    if name_lower == "europa" or name_lower.startswith("europa "):
        return (12, 0)
    if name_lower == "film and arts" or name_lower.startswith("film and arts "):
        return (13, 0)
    if name_lower == "golden edge" or name_lower.startswith("golden edge "):
        return (14, 0)
    if name_lower == "golden" or name_lower.startswith("golden "):
        return (14, 1)
    if name_lower == "multipremier" or name_lower.startswith("multipremier "):
        return (15, 0)
    if name_lower == "mc" or name_lower.startswith("mc "):
        return (16, 0)
    return (99, 0)


def get_peliculas_lineup_key(clean_name, first_occurrence_idx, hbo_anchor_idx):
    n = clean_name.lower()
    if "hbo" in n:
        return (hbo_anchor_idx, get_hbo_suborder(n), n)
    known = get_peliculas_known_suborder(n)
    if known[0] != 99:
        return (hbo_anchor_idx + 1, known[0], known[1], n)
    return (hbo_anchor_idx + 2, first_occurrence_idx, 0, n)


def get_documentales_lineup_key(clean_name):
    """Operator-style order for documentary channels (Discovery block, then History, lifestyle)."""
    n = clean_name.lower()

    if n == "discovery channel":
        return (0, 0, n)
    if n == "discovery theater":
        return (0, 1, n)
    if n == "discovery turbo":
        return (0, 2, n)
    if n == "discovery world":
        return (0, 3, n)

    if n == "discovery science":
        return (1, 0, n)
    if n == "discovery sci":
        return (1, 1, n)
    if n == "animal planet":
        return (1, 2, n)
    if n == "natgeo":
        return (1, 3, n)

    if n == "id":
        return (2, 0, n)
    if n == "discovery id":
        return (2, 1, n)

    if n == "history":
        return (3, 0, n)
    if n == "history 2":
        return (3, 1, n)
    if n == "history channel":
        return (3, 2, n)

    if n == "discovery home and health":
        return (4, 0, n)
    if n == "home and health":
        return (4, 1, n)
    if n == "hgtv discovery hgtv":
        return (4, 2, n)
    if n == "hgtv":
        return (4, 3, n)
    if n == "tlc":
        return (4, 4, n)

    return (9, 0, n)


def get_series_lineup_key(clean_name, first_occurrence_idx):
    """Operator-style order for series channels."""
    n = clean_name.lower()

    if n == "universal tv" or n.startswith("universal tv "):
        return (0, 0, n)
    if n == "axn" or n.startswith("axn "):
        return (1, 0, n)
    if n == "universal channel" or n.startswith("universal channel "):
        return (1, 1, n)
    if n == "warner channel" or n.startswith("warner channel "):
        return (2, 0, n)
    if n == "warner" or n.startswith("warner "):
        return (2, 1, n)
    if n.startswith("e!") or n == "e":
        return (3, 0, n)
    if n == "lifetime" or n.startswith("lifetime "):
        return (4, 0, n)
    if n == "usa network" or n.startswith("usa network "):
        return (5, 0, n)

    return (9, first_occurrence_idx, 0, n)


def get_noticias_lineup_key(clean_name):
    n = clean_name.lower()
    if n == "cnn en español" or n == "cnn en espanol":
        return (0, 0, n)
    if n == "cnn chile":
        return (0, 1, n)
    if "cnn" in n:
        return (0, 2, n)
    if "estrella news" in n:
        return (1, 0, n)
    if "puranoticia" in n:
        return (2, 0, n)
    if n == "cooperativa":
        return (3, 0, n)
    if "dw español" in n or "dw espanol" in n:
        return (4, 0, n)
    if n == "ucl":
        return (5, 0, n)
    return (9, 0, n)


LOGO_LIBRARY = {
    "via x esports": "https://static.wikia.nocookie.net/logopedia/images/2/29/V%C3%ADa_X_2005.jpg/revision/latest?cb=20190809004317&path-prefix=es",
    "cnn en español": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/cnn-us.png",
    "cnn internacional": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/cnn-us.png",
    "cooperativa": "https://cdn.m3u.cl/logo/1035_Cooperativa.png",
    "bbc news": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-kingdom/bbc-news-uk.png",
    "disney channel": "https://docdog.top/logo/countries/latino/disneychannel.png",
    "discovery kids": "https://docdog.top/logo/countries/latino/discoverykids.png",
    "cartoonito": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/cartoonito-us.png",
    "adult swim": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/adult-swim-us.png",
    "disney jr.": "https://upload.wikimedia.org/wikipedia/commons/e/e3/2024_Disney_Jr._Logo.svg",
    "nick jr": "https://i.imgur.com/E84jnP8.png",
    "star channel": "https://upload.wikimedia.org/wikipedia/commons/c/cd/Star_Channel_2023.svg",
    "fx": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/FX_International_logo.svg/960px-FX_International_logo.svg.png",
    "golden edge": "https://upload.wikimedia.org/wikipedia/commons/d/d5/Golden_Edge_Logo_2020.png",
    "golden": "https://upload.wikimedia.org/wikipedia/commons/d/d5/Golden_Edge_Logo_2020.png",
    "ent family": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/StudioUniversal2016.png/960px-StudioUniversal2016.png",
    "global": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Global_TV_%28Argentina%29_logo.svg/320px-Global_TV_%28Argentina%29_logo.svg.png",
    "eurochannel": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Eurochannel_logo.svg/320px-Eurochannel_logo.svg.png",
    "lifetime": "https://docdog.top/logo/countries/latino/lifetime.png",
    "tnt novelas": "https://docdog.top/logo/countries/latino/tnt.png",
    "tnt series": "https://docdog.top/logo/countries/latino/tntseries.png",
    "las estrellas": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Las_Estrellas_logo.svg/320px-Las_Estrellas_logo.svg.png",
    "comedy central": "https://docdog.top/logo/countries/latino/comedycentral.png",
    "tnt sports premium": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/TNT_Sports_logo.svg/320px-TNT_Sports_logo.svg.png",
    "id": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Investigation_Discovery_2018_logo.svg/320px-Investigation_Discovery_2018_logo.svg.png",
    "discovery channel": "https://docdog.top/logo/countries/latino/discoverychannel.png",
    "discovery theater": "https://docdog.top/logo/countries/latino/discoverytheater.png",
    "animal planet": "https://docdog.top/logo/countries/latino/animalplanet.png",
    "hgtv discovery hgtv": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/hgtv-us.png",
    "hgtv": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/hgtv-us.png",
    "discovery science": "https://docdog.top/logo/countries/latino/discoveryscience.png",
    "discovery turbo": "https://docdog.top/logo/countries/latino/discoveryturbo.png",
    "history channel": "https://i.imgur.com/J897iGL.jpg",
    "discovery id": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Investigation_Discovery_2018_logo.svg/320px-Investigation_Discovery_2018_logo.svg.png",
    "discovery home and health": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Discovery_Home_%26_Health_logo.svg/320px-Discovery_Home_%26_Health_logo.svg.png",
    "home and health": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Discovery_Home_%26_Health_logo.svg/320px-Discovery_Home_%26_Health_logo.svg.png",
    "discovery world": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Discovery_Channel_-_Logo_2019.svg/320px-Discovery_Channel_-_Logo_2019.svg.png",
    "discovery sci": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Discovery_Science_logo.svg/320px-Discovery_Science_logo.svg.png",
    "el gourmet": "https://docdog.top/logo/countries/latino/elgourmet.png",
    "tlc": "https://docdog.top/logo/countries/latino/tlc.png",
    "tv nostalgia": "http://xplatinmedia.com:8080/images/2e919b7e465da0c85b58943f21294e26.png",
    "natgeo": "https://docdog.top/logo/countries/latino/natgeo.png",
    "warner": "https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/12f5712d-1535-4d60-a967-e7d5e3c1902f/dhrbjhn-eb1b8a6f-8873-4fe0-bdee-eade1218a86b.png?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7InBhdGgiOiIvZi8xMmY1NzEyZC0xNTM1LTRkNjAtYTk2Ny1lN2Q1ZTNjMTkwMmYvZGhyYmpobi1lYjFiOGE2Zi04ODczLTRmZTAtYmRlZS1lYWRlMTIxOGE4NmIucG5nIn1dXSwiYXVkIjpbInVybjpzZXJ2aWNlOmZpbGUuZG93bmxvYWQiXX0.iswXcWSD3c_tODdOVs4e2eV0hAIgB-EQllC7W2bqDc0",
    "panamericana": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Panamericana_Televisi%C3%B3n_logo.svg/320px-Panamericana_Televisi%C3%B3n_logo.svg.png",
    "france 24": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/France_24_logo.svg/320px-France_24_logo.svg.png",
    "hola tv": "https://docdog.top/logo/countries/latino/holatv.png",
    "baby tv": "https://docdog.top/logo/countries/latino/babytv.png",
    "telemundo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/telemundo-us.png",
    "nuestra tele": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Nuestra_Tele_logo.svg/320px-Nuestra_Tele_logo.svg.png",
    "daystar": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Daystar_TV_logo.svg/320px-Daystar_TV_logo.svg.png",
    "cgtn": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/international/cgtn-int.png",
    "tlnovelas": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Tlnovelas_logo.svg/320px-Tlnovelas_logo.svg.png",
    "htv": "https://docdog.top/logo/countries/argentina/htv-ar.png",
    "tnt": "https://docdog.top/logo/countries/latino/tnt.png",
    "universal channel": "https://i.imgur.com/jnjvR5f.png",
    "hei": "https://cdn.m3u.cl/logo/1036_HEI.png",
    "gagsnetwork": "https://i.imgur.com/VgYCskX.png",
    "tve": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/TVE_logo.svg/320px-TVE_logo.svg.png",
}


def get_channel_base(clean_name):
    """Strip trailing repetition index (e.g. 'Disney Channel 2' -> 'Disney Channel')."""
    return re.sub(r"\s+\d+$", "", clean_name).strip()


def load_logo_assets():
    """Load verified logo URLs from assets/logos.json."""
    assets_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logos.json")
    if not os.path.exists(assets_path):
        return {}
    try:
        import json

        with open(assets_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    result = {}
    for key, entry in data.items():
        if isinstance(entry, dict) and entry.get("url"):
            result[key.lower()] = entry["url"]
    return result


def resolve_missing_logos(entries):
    """Fill missing tvg-logo from sibling variants, assets, or LOGO_LIBRARY."""
    logo_assets = load_logo_assets()
    logos_by_base = {}
    for entry in entries:
        logo = entry["attrs"].get("tvg-logo", "")
        if logo:
            base = get_channel_base(entry["clean_name"]).lower()
            logos_by_base.setdefault(base, logo)

    for entry in entries:
        if entry["attrs"].get("tvg-logo"):
            continue

        base = get_channel_base(entry["clean_name"]).lower()
        clean_lower = entry["clean_name"].lower()

        if base in logos_by_base:
            entry["attrs"]["tvg-logo"] = logos_by_base[base]
            continue

        for known_base, logo in logos_by_base.items():
            if known_base.startswith(base) or base.startswith(known_base):
                entry["attrs"]["tvg-logo"] = logo
                break
        else:
            if base in logo_assets:
                entry["attrs"]["tvg-logo"] = logo_assets[base]
            elif clean_lower in logo_assets:
                entry["attrs"]["tvg-logo"] = logo_assets[clean_lower]
            elif clean_lower in LOGO_LIBRARY:
                entry["attrs"]["tvg-logo"] = LOGO_LIBRARY[clean_lower]
            elif base in LOGO_LIBRARY:
                entry["attrs"]["tvg-logo"] = LOGO_LIBRARY[base]
            else:
                for key, logo in logo_assets.items():
                    if key in clean_lower:
                        entry["attrs"]["tvg-logo"] = logo
                        break
                else:
                    for key, logo in LOGO_LIBRARY.items():
                        if key in clean_lower:
                            entry["attrs"]["tvg-logo"] = logo
                            break


def classify_channel(clean_name, original_group, tvg_id, url="", logo=""):
    clean_name_lower = clean_name.lower()
    original_group_lower = (original_group or "").lower()
    tvg_id_lower = (tvg_id or "").lower()

    # Editorial overrides (explicit category assignments)
    if "13 kids" in clean_name_lower:
        return "Infantiles"
    if "via x esports" in clean_name_lower or "via x esport" in clean_name_lower:
        return "Infantiles"
    if clean_name_lower == "hei" or clean_name_lower.startswith("hei "):
        return "Musica"
    if clean_name_lower == "tve" or clean_name_lower.startswith("tve "):
        if "1088_1" in url:
            return "Musica"
    if clean_name_lower.startswith("e!") or clean_name_lower == "e":
        return "Series"
    if clean_name_lower == "amc" or (
        clean_name_lower.startswith("amc ") and "series" not in clean_name_lower
    ):
        return "Peliculas"
    if any(w in clean_name_lower for w in ["home and health", "home & health", "hgtv", "tlc"]):
        return "Documentales"
    if any(w in clean_name_lower for w in ["natgeo", "nat geo"]):
        return "Documentales"
    if "warner" in clean_name_lower:
        return "Series"
    if "panamericana" in clean_name_lower:
        return "Internacionales"
    if "france 24" in clean_name_lower:
        return "Noticias"
    if "baby tv" in clean_name_lower or clean_name_lower == "babytv":
        return "Infantiles"
    if "telemundo" in clean_name_lower:
        return "Series"
    if "win futbol" in clean_name_lower:
        return "Deportes"
    if "nuestra tele" in clean_name_lower:
        return "Series"
    if clean_name_lower.startswith("cgtn"):
        return "Internacionales"
    if "tlnovelas" in clean_name_lower or "tl novelas" in clean_name_lower:
        return "Series"
    if clean_name_lower == "htv" or clean_name_lower.startswith("htv "):
        return "Musica"
    if clean_name_lower == "tnt" or (
        clean_name_lower.startswith("tnt ")
        and not any(x in clean_name_lower for x in ["sports", "novelas", "series"])
    ):
        return "Peliculas"
    if "universal channel" in clean_name_lower:
        return "Series"
    if "bbc news" in clean_name_lower:
        return "Noticias"
    if clean_name_lower == "global" or clean_name_lower.startswith("global "):
        return "Peliculas"
    if "eurochannel" in clean_name_lower:
        return "Peliculas"
    if "golden" in clean_name_lower:
        return "Peliculas"
    if "comedy central" in clean_name_lower:
        return "Series"
    if "las estrellas" in clean_name_lower:
        return "Series"
    if "lifetime" in clean_name_lower:
        return "Series"
    if clean_name_lower in ("cooperativa", "cnn chile", "ucl"):
        return "Noticias"
    if clean_name_lower in ("dw español", "dw espanol"):
        return "Noticias"
    if clean_name_lower == "amc series" or clean_name_lower.startswith("amc series "):
        return "Peliculas"
    if clean_name_lower in ("solotv", "solo tv", "el pinguino tv"):
        return "Regionales"
    if clean_name_lower in ("global", "fx", "star channel"):
        return "Peliculas"
    if "etc tv" in clean_name_lower or clean_name_lower == "etc":
        return "Infantiles"
    if "vision latina" in clean_name_lower:
        return "Internacionales"
    if "rcn novelas" in clean_name_lower:
        return "Internacionales"
    if "atres series" in clean_name_lower:
        return "Internacionales"
    if "max anime" in clean_name_lower:
        return "Infantiles"
    internacionales_channels = [
        "gagsnetwork", "awe", "axs tv", "syfy", "tv land", "tv one",
        "vh1", "vice tv", "we tv", "hallmark mystery", "scares by shudder",
        "sun channel", "kanald", "concert channel", "caracol", "tve",
    ]
    if any(w in clean_name_lower for w in internacionales_channels):
        return "Internacionales"
    if original_group_lower == "internacionales":
        return "Internacionales"
    if "omusica" in clean_name_lower:
        return "Musica"
    if "mtv" in clean_name_lower:
        return "Musica"
    if "ent family" in clean_name_lower:
        return "Peliculas"
    if "adult swim" in clean_name_lower:
        return "Infantiles"
    if "documentary+" in clean_name_lower or clean_name_lower == "documentary+":
        return "Documentales"
    if "warner channel" in clean_name_lower:
        return "Series"

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
    if any(w in clean_name_lower for w in ["chilevision", "tvn", "tv chile", "uchile", "bio bio tv", "la red", "mega", "ucv", "24 horas", "chv", "ntv"]):
        return "Nacionales"
    if original_group_lower in ["general", "latin 3", "nacionales", "01. tv abierta"]:
        return "Nacionales"
        
    # 2. Regionales
    if "chilote" in clean_name_lower or original_group_lower in ["regionales", "regional"]:
        return "Regionales"
        
    # 3. Infantiles
    if any(w in clean_name_lower for w in ["cartoon", "cartoons", "disney", "dreamworks", "nick", "kids", "esponja", "spongebob", "disney jr", "tooncast", "cartoonito", "retromagico", "supertoons", "laika channel", "capitan tsubasa", "one piece", "simpsons", "baby tv", "babytv"]):
        return "Infantiles"
        
    # 4. Peliculas
    if any(w in clean_name_lower for w in ["hbo", "cinecanal", "dhe", "space", "paramount", "paramount channel", "studio universal", "universal premier", "universal cinema", "showtime", "artflix", "golden", "de pelicula", "tcm", "cinemax", "amc", "fmh movies", "film and arts", "europa", "multipremier", "sony", "eurochannel", "grjngo", "rewind", "west"]):
        return "Peliculas"
    if re.search(r"\bcine\b", clean_name_lower) and "documentary" not in clean_name_lower:
        return "Peliculas"
    if any(g in original_group_lower for g in ["movies", "cine", "peliculas", "películas", "classic", "pack hbo"]):
        return "Peliculas"
        
    # 5. Series
    if any(w in clean_name_lower for w in ["universal tv", "universal channel", "universal crime", "universal comedy", "universal reality", "sony entertainment", "axn", "fx", "star channel", "warner channel", "warner", "paramount network", "series", "comedy central", "a and e", "pop tv", "e!", "e! latin", "lifetime", "usa network", "syfy", "vh1", "tnt novelas", "tnt series", "distrito comedia", "bbc series", "las estrellas", "telemundo", "nuestra tele", "tlnovelas", "tl novelas"]):
        return "Series"
    if any(g in original_group_lower for g in ["series", "entertainment", "comedy", "entretenimiento premium", "03. entretenimiento"]):
        return "Series"
        
    # 6. Deportes
    if any(w in clean_name_lower for w in ["sports", "espn", "fox sport", "fox sports", "directv sports", "stadium", "goltv", "gol tv", "tnt sports"]):
        return "Deportes"
    if any(g in original_group_lower for g in ["deportes", "sports", "espn", "⚽ deportes 🏆"]):
        return "Deportes"
        
    # 7. Noticias
    if any(w in clean_name_lower for w in ["cnn", "noticias", "news", "estrella news", "abc news", "france 24", "cgtn", "bbc news"]):
        return "Noticias"
    if "news" in original_group_lower:
        return "Noticias"
        
    # 8. Musica
    if any(w in clean_name_lower for w in ["mtv", "music", "musica", "htv"]) or (
        "festival" in clean_name_lower and not is_13_channel(clean_name_lower)
    ):
        return "Musica"
    if "music" in original_group_lower:
        return "Musica"
        
    # 9. Documentales
    if clean_name_lower == "id" or any(w in clean_name_lower for w in ["history", "discovery", "nat geo", "natgeo", "national geographic", "documentary", "archivos forenses", "animal planet", "hgtv", "tlc", "home and health"]):
        return "Documentales"
    if any(g in original_group_lower for g in ["documentary", "documentales", "documentales y cultura"]):
        return "Documentales"

    # 11. Internacionales
    if any(w in clean_name_lower for w in ["tve", "rcn novelas", "atres series", "vision latina", "panamericana"]):
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
        "internacionales": "Internacionales",
    }
    if original_group_lower in group_fallback:
        return group_fallback[original_group_lower]
        
    return "Variedades"

GROUP_ORDER = [
    "Nacionales",
    "Regionales",
    "Noticias",
    "Infantiles",
    "Peliculas",
    "Series",
    "Deportes",
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
        _, display_name = parse_extinf(entry['extinf'])
        clean_name = clean_channel_name(display_name)
        clean_name_lower = clean_name.lower()
        if clean_name_lower not in casing_map:
            casing_map[clean_name_lower] = clean_name

    for entry in entries:
        attrs, display_name = parse_extinf(entry['extinf'])
        raw_clean_name = clean_channel_name(display_name)
        clean_name = casing_map[raw_clean_name.lower()]
        entry['url'] = normalize_url(entry['url'])
        
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
        
        entry['duration'] = '-1'
        entry['attrs'] = attrs
        entry['clean_name'] = clean_name
        entry['quality_score'] = get_quality_score(display_name)
        entry['category'] = category

    resolve_missing_logos(entries)

    entries, removed_duplicates = deduplicate_by_url(entries)

    # Step 3: Identify the first occurrence index of each clean name to preserve lineup order
    first_occurrence = {}
    for idx, entry in enumerate(entries):
        c_name = entry['clean_name']
        if c_name not in first_occurrence:
            first_occurrence[c_name] = idx

    hbo_anchor_idx = min(
        first_occurrence[e['clean_name']]
        for e in entries
        if e['category'] == 'Peliculas' and 'hbo' in e['clean_name'].lower()
    ) if any(
        e['category'] == 'Peliculas' and 'hbo' in e['clean_name'].lower()
        for e in entries
    ) else 0

    # Step 4: Sort entries
    def sort_key(e):
        g_priority = get_group_priority(e['category'])
        if e['category'] == 'Nacionales':
            lineup_key = get_nacional_lineup_key(e['clean_name'])
        elif e['category'] == 'Peliculas':
            lineup_key = get_peliculas_lineup_key(
                e['clean_name'], first_occurrence[e['clean_name']], hbo_anchor_idx
            )
        elif e['category'] == 'Noticias':
            lineup_key = get_noticias_lineup_key(e['clean_name'])
        elif e['category'] == 'Documentales':
            lineup_key = get_documentales_lineup_key(e['clean_name'])
        elif e['category'] == 'Series':
            lineup_key = get_series_lineup_key(
                e['clean_name'], first_occurrence[e['clean_name']]
            )
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
    # Default to official.m3u in the parent directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(script_dir, "..", "official.m3u")
    if len(sys.argv) > 1:
        target = sys.argv[1]
    clean_m3u(target)
