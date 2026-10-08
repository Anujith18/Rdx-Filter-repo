"""Alias-aware filename filters used by the search buttons.

The callback handlers store compact markers in their search state.  This module
turns those markers into one Mongo-compatible regular expression, so filtering
happens in the database instead of only across the first page of results.
"""

import re


_MARKER_RE = re.compile(
    r"\[\[(language|season|episode|quality|combined):([^\]]+)\]\]",
    flags=re.IGNORECASE,
)
# Match spaces and filename punctuation without explicit nested bracket sets.
# This stays compatible with MongoDB PCRE and avoids Python's
# "Possible nested set" FutureWarning.
_SEPARATOR = r"[\W_]*"


LANGUAGE_PATTERNS = {
    "hin": rf"(?<![a-z0-9])hin(?:di)?(?![a-z0-9])",
    "eng": rf"(?<![a-z0-9])eng(?:lish)?(?![a-z0-9])",
    "bangla": rf"(?<![a-z0-9])(?:bangla|bengali|bangali|bengoli)(?![a-z0-9])",
    "urdu": rf"(?<![a-z0-9])urd(?:u)?(?![a-z0-9])",
    "tam": rf"(?<![a-z0-9])tam(?:il)?(?![a-z0-9])",
    "tel": rf"(?<![a-z0-9])tel(?:ugu)?(?![a-z0-9])",
    "mal": rf"(?<![a-z0-9])mal(?:ayalam)?(?![a-z0-9])",
    "kan": rf"(?<![a-z0-9])kan(?:nada)?(?![a-z0-9])",
    "mar": rf"(?<![a-z0-9])mar(?:athi)?(?![a-z0-9])",
    "pun": rf"(?<![a-z0-9])pun(?:jabi)?(?![a-z0-9])",
    "guj": rf"(?<![a-z0-9])guj(?:arati|rati)?(?![a-z0-9])",
    "bhojpuri": rf"(?<![a-z0-9])bhoj(?:puri)?(?![a-z0-9])",
    "oriya": rf"(?<![a-z0-9])(?:odia|oriya)(?![a-z0-9])",
    "asm": rf"(?<![a-z0-9])asm(?:assamese)?(?![a-z0-9])|(?<![a-z0-9])assamese(?![a-z0-9])",
    "kor": rf"(?<![a-z0-9])kor(?:ean)?(?![a-z0-9])",
    "chi": rf"(?<![a-z0-9])chi(?:nese)?(?![a-z0-9])",
    "jap": rf"(?<![a-z0-9])jap(?:anese)?(?![a-z0-9])",
    "ara": rf"(?<![a-z0-9])ara(?:bic)?(?![a-z0-9])",
    "spa": rf"(?<![a-z0-9])spa(?:nish)?(?![a-z0-9])",
    "fre": rf"(?<![a-z0-9])fre(?:nch)?(?![a-z0-9])",
    "ger": rf"(?<![a-z0-9])ger(?:man)?(?![a-z0-9])",
    "por": rf"(?<![a-z0-9])por(?:tuguese)?(?![a-z0-9])",
    "rus": rf"(?<![a-z0-9])rus(?:sian)?(?![a-z0-9])",
    "dual": rf"(?<![a-z0-9])dual(?:{_SEPARATOR}audio)?(?![a-z0-9])",
    "multi": rf"(?<![a-z0-9])multi(?:ple)?(?:{_SEPARATOR}audio)?(?![a-z0-9])",
}

LANGUAGE_LABELS = {
    "hin": "Hindi",
    "eng": "English",
    "bangla": "Bengali/Bangla",
    "urdu": "Urdu",
    "tam": "Tamil",
    "tel": "Telugu",
    "mal": "Malayalam",
    "kan": "Kannada",
    "mar": "Marathi",
    "pun": "Punjabi",
    "guj": "Gujarati",
    "bhojpuri": "Bhojpuri",
    "oriya": "Odia/Oriya",
    "asm": "Assamese",
    "kor": "Korean",
    "chi": "Chinese",
    "jap": "Japanese",
    "ara": "Arabic",
    "spa": "Spanish",
    "fre": "French",
    "ger": "German",
    "por": "Portuguese",
    "rus": "Russian",
    "dual": "Dual Audio",
    "multi": "Multi Audio",
}

QUALITY_PATTERNS = {
    "360p": r"(?<!\d)360[\W_]*p(?![a-z0-9])",
    "480p": r"(?<!\d)480[\W_]*p(?![a-z0-9])",
    "720p": r"(?<!\d)720[\W_]*p(?![a-z0-9])",
    "1080p": r"(?<!\d)1080[\W_]*p(?![a-z0-9])",
    "1440p": r"(?<!\d)(?:1440[\W_]*p|2[\W_]*k)(?![a-z0-9])",
    "2160p": r"(?<!\d)(?:2160[\W_]*p|4[\W_]*k)(?![a-z0-9])",
}

_COMBINED_LABEL_PATTERN = (
    r"(?<![a-z0-9])(?:combined|complete|pack)(?![a-z0-9])"
)
_COMBINED_RANGE_PATTERN = (
    rf"(?:e|ep|episode){_SEPARATOR}0*\d{{1,3}}"
    rf"\s*(?:-|–|—|to|through|thru|&|/|_)\s*"
    rf"(?:(?:e|ep|episode){_SEPARATOR})?0*\d{{1,3}}(?!\d)"
)
COMBINED_PATTERN = (
    rf"(?:{_COMBINED_LABEL_PATTERN}|{_COMBINED_RANGE_PATTERN})"
)


def _canonical_language(value):
    value = str(value or "").strip().lower()
    aliases = {
        "hindi": "hin",
        "english": "eng",
        "bengali": "bangla",
        "bengoli": "bangla",
        "bangali": "bangla",
        "tamil": "tam",
        "telugu": "tel",
        "malayalam": "mal",
        "kannada": "kan",
        "marathi": "mar",
        "punjabi": "pun",
        "gujarati": "guj",
        "odia": "oriya",
        "assamese": "asm",
        "korean": "kor",
        "chinese": "chi",
        "japanese": "jap",
        "arabic": "ara",
        "spanish": "spa",
        "french": "fre",
        "german": "ger",
        "portuguese": "por",
        "russian": "rus",
        "dual audio": "dual",
        "multi audio": "multi",
    }
    return aliases.get(value, value)


def _number(value):
    match = re.search(r"\d{1,3}", str(value or ""))
    return int(match.group()) if match else None


def _canonical_quality(value):
    value = re.sub(r"[\W_]+", "", str(value or "").strip().lower())
    aliases = {
        "360": "360p",
        "480": "480p",
        "720": "720p",
        "1080": "1080p",
        "1440": "1440p",
        "2k": "1440p",
        "2160": "2160p",
        "4k": "2160p",
        "uhd": "2160p",
    }
    return aliases.get(value, value)


def _enabled(value):
    return str(value or "").strip().lower() in {
        "1", "true", "yes", "on", "combined",
    }


def parse_filter_query(query):
    filters = {}

    def collect(match):
        filters[match.group(1).lower()] = match.group(2).strip()
        return " "

    base = _MARKER_RE.sub(collect, str(query or ""))
    base = re.sub(r"\s+", " ", base).strip()
    return base, filters


def make_filter_query(query, **updates):
    """Add or replace stackable filename-search markers."""
    base, filters = parse_filter_query(query)
    # Remove older filename-style constraints before storing their replacement
    # as a marker. This keeps combinations such as S02 + E16 + Hindi + 1080p
    # from accidentally retaining an earlier E01/720p term in the base title.
    if updates.get("language") is not None:
        base = _strip_language_terms(base)
    if updates.get("season") is not None:
        base = _strip_season_terms(base)
    if updates.get("episode") is not None:
        base = _strip_episode_terms(base)
    if updates.get("quality") is not None:
        base = _strip_quality_terms(base)
    if updates.get("combined") is not None:
        base = _strip_combined_terms(base)
    base = re.sub(r"\s+", " ", base).strip()

    for kind, value in updates.items():
        if kind not in {"language", "season", "episode", "quality", "combined"}:
            continue
        if value is None:
            filters.pop(kind, None)
        elif kind == "language":
            filters[kind] = _canonical_language(value)
        elif kind == "quality":
            quality = _canonical_quality(value)
            if quality:
                filters[kind] = quality
        elif kind == "combined":
            if _enabled(value):
                filters[kind] = "1"
            else:
                filters.pop(kind, None)
        else:
            number = _number(value)
            if number is not None:
                filters[kind] = str(number)

    markers = " ".join(
        f"[[{kind}:{filters[kind]}]]"
        for kind in ("language", "season", "episode", "quality", "combined")
        if filters.get(kind)
    )
    return f"{base} {markers}".strip()


def _strip_language_terms(text):
    for pattern in LANGUAGE_PATTERNS.values():
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _strip_quality_terms(text):
    for pattern in QUALITY_PATTERNS.values():
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _strip_combined_terms(text):
    return re.sub(
        _COMBINED_LABEL_PATTERN,
        " ",
        text,
        flags=re.IGNORECASE,
    )


def _strip_episode_terms(text):
    # S01E01 / S01 E01 -> S01
    text = re.sub(
        rf"(?i)((?:s|season){_SEPARATOR}0*\d{{1,2}}){_SEPARATOR}"
        rf"(?:e|ep|episode){_SEPARATOR}0*\d{{1,3}}",
        r"\1",
        text,
    )
    # E01 / E 01 / EP01 / Episode 01
    return re.sub(
        rf"(?i)(?:e|ep|episode){_SEPARATOR}0*\d{{1,3}}(?!\d)",
        " ",
        text,
    )


def _strip_season_terms(text):
    return re.sub(
        rf"(?i)(?<![a-z0-9])(?:s|season){_SEPARATOR}0*\d{{1,2}}"
        rf"(?:{_SEPARATOR}(?:e|ep|episode){_SEPARATOR}0*\d{{1,3}})?",
        " ",
        text,
    )


def _base_pattern(text):
    text = re.sub(r"[_\-.+\[\]\{\}\(\)]+", " ", text)
    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    if not tokens:
        return None
    return r".*?".join(re.escape(token) for token in tokens)


def _season_pattern(value):
    number = _number(value)
    if number is None:
        return None
    return (
        rf"(?<![a-z0-9])(?:s|season){_SEPARATOR}0*{number}"
        rf"(?!\d)"
    )


def _episode_pattern(value):
    number = _number(value)
    if number is None:
        return None
    # Match the episode number regardless of the filename convention:
    # E1/E01, Ep1/Ep01, Episode 1, S01E01, S01 E01, S1Ep1, S1 Ep1, etc.
    # The season prefix is optional because some files contain only E01/Ep01.
    return (
        rf"(?i)(?:"
        rf"(?:s|season){_SEPARATOR}0*\d{{1,3}}{_SEPARATOR}"
        rf")?(?:e|ep|episode){_SEPARATOR}0*{number}(?!\d)"
    )


def extract_episode_numbers(text):
    """Return explicit episodes and episodes covered by combined ranges.

    Supported examples include E16, E01, E 16, EP16, Ep01, Episode 16,
    S01E16, S01 E16, S1Ep16, S1 Ep16, and combined episode ranges.
    """
    text = str(text or "")
    episodes = set()
    token = r"(?:e|ep|episode)"

    explicit_range = re.compile(
        rf"(?i){token}{_SEPARATOR}0*(\d{{1,3}})"
        rf"\s*(?:-|–|—|to|through|thru|&|/)\s*"
        rf"(?:{token}{_SEPARATOR})?0*(\d{{1,3}})(?!\d)"
    )
    combined_range = re.compile(
        rf"(?i){token}{_SEPARATOR}0*(\d{{1,3}})"
        rf"\s+0*(\d{{1,3}})"
        rf"(?=[\W_]+(?:combined|complete|pack)\b)"
    )

    for pattern in (explicit_range, combined_range):
        for match in pattern.finditer(text):
            start, end = int(match.group(1)), int(match.group(2))
            if 0 < start <= end <= 999 and end - start <= 200:
                episodes.update(range(start, end + 1))

    for match in re.finditer(
        rf"(?i){token}{_SEPARATOR}0*(\d{{1,3}})(?!\d)",
        text,
    ):
        number = int(match.group(1))
        if number > 0:
            episodes.add(number)
    return episodes


def _find_season(text):
    match = re.search(
        rf"(?i)(?<![a-z0-9])(?:s|season){_SEPARATOR}0*(\d{{1,2}})",
        text,
    )
    return int(match.group(1)) if match else None


def _find_episode(text):
    match = re.search(
        rf"(?i)(?:e|ep|episode){_SEPARATOR}0*(\d{{1,3}})(?!\d)",
        text,
    )
    return int(match.group(1)) if match else None


def build_search_pattern(query):
    """Build one regex that handles aliases and common episode separators."""
    base, filters = parse_filter_query(query)

    if filters.get("language"):
        base = _strip_language_terms(base)
    if filters.get("quality"):
        base = _strip_quality_terms(base)
    if filters.get("combined"):
        base = _strip_combined_terms(base)
    selected_season = _number(filters.get("season"))
    selected_episode = _number(filters.get("episode"))

    # Direct searches like S01E01 and S01 E01 should use the same tolerant
    # season/episode constraints even before a filter button is clicked.
    detected_season = selected_season if selected_season is not None else _find_season(base)
    detected_episode = selected_episode if selected_episode is not None else _find_episode(base)

    if detected_season is not None:
        base = _strip_season_terms(base)
    elif detected_episode is not None:
        base = _strip_episode_terms(base)

    constraints = []
    base_regex = _base_pattern(base)
    if base_regex:
        constraints.append(base_regex)

    language = _canonical_language(filters.get("language"))
    if language:
        constraints.append(LANGUAGE_PATTERNS.get(language, re.escape(language)))

    quality = _canonical_quality(filters.get("quality"))
    if quality:
        constraints.append(QUALITY_PATTERNS.get(quality, re.escape(quality)))

    if _enabled(filters.get("combined")):
        constraints.append(COMBINED_PATTERN)

    season_regex = _season_pattern(detected_season)
    if season_regex:
        constraints.append(season_regex)

    episode_regex = _episode_pattern(detected_episode)
    if episode_regex:
        constraints.append(episode_regex)

    if not constraints:
        return "."
    return "^" + "".join(f"(?=.*{item})" for item in constraints) + ".*$"


def display_filter_query(query):
    """Return a clean title for captions instead of exposing state markers."""
    base, filters = parse_filter_query(query)
    if filters.get("language"):
        base = _strip_language_terms(base)
    if filters.get("season"):
        base = _strip_season_terms(base)
    if filters.get("episode"):
        base = _strip_episode_terms(base)
    if filters.get("quality"):
        base = _strip_quality_terms(base)
    if filters.get("combined"):
        base = _strip_combined_terms(base)
    base = re.sub(r"\s+", " ", base).strip()
    labels = []
    language = _canonical_language(filters.get("language"))
    if language:
        labels.append(LANGUAGE_LABELS.get(language, language.title()))
    season = _number(filters.get("season"))
    if season is not None:
        labels.append(f"Season {season:02d}")
    episode = _number(filters.get("episode"))
    if episode is not None:
        labels.append(f"E{episode:02d}")
    quality = _canonical_quality(filters.get("quality"))
    if quality:
        labels.append(quality.upper())
    if _enabled(filters.get("combined")):
        labels.append("Combined Files")
    suffix = " • ".join(labels)
    return f"{base} • {suffix}".strip(" •") if suffix else base


def matches_filter(filename, query):
    text = str(filename or "")
    _, filters = parse_filter_query(query)
    episode = _number(filters.get("episode"))
    if episode is not None:
        if episode not in extract_episode_numbers(text):
            return False
        query = make_filter_query(query, episode=None)
    return bool(re.search(build_search_pattern(query), text, re.IGNORECASE))
