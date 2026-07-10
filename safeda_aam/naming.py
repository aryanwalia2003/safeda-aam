"""Filename convention checking and normalization.

Default convention: lowercase snake_case, ISO dates (YYYY-MM-DD), no
spaces or special characters, lowercase extensions.
"""

import re

GENERIC_TOKENS = {
    "untitled", "new", "copy", "final", "final2", "finalfinal",
    "test", "temp", "tmp", "asdf", "document", "download",
}

# Conventional filenames with their own well-known casing — not worth
# flagging as naming-convention violations (safeda-aam itself creates
# README.md stubs in every scaffolded folder, so this also keeps
# check-names quiet right after `init`/`quickstart`).
EXEMPT_FILENAMES = {
    "readme.md", "readme.txt", "readme",
    "license", "license.md", "license.txt",
    "changelog.md", "contributing.md",
    "makefile", "dockerfile",
    ".gitignore", ".gitattributes",
}

# (regex, replacement-format) pairs to normalize common date patterns to YYYY-MM-DD.
# Applied to the filename stem before other cleanup.
_DATE_PATTERNS = [
    # DD-MM-YYYY or DD_MM_YYYY or DD.MM.YYYY
    # (?<!\d)/(?!\d) instead of \b: \b treats '_' as a word char, so it
    # wouldn't match a boundary between digits and an adjacent underscore
    # (e.g. '20260103_calibration.txt') — (?<!\d)/(?!\d) only care about digits.
    (re.compile(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](\d{4})(?!\d)"), lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),
    # MM-DD-YYYY is ambiguous with DD-MM-YYYY; we don't guess it separately.
    # YYYYMMDD -> YYYY-MM-DD
    (re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"), lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
    # DD Mon YYYY (e.g. 03 Jan 2026) -> YYYY-MM-DD
    (re.compile(
        r"(?<!\d)(\d{1,2})[ _-](jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[ _-](\d{4})(?!\d)",
        re.IGNORECASE,
    ), None),  # handled specially below
]

_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


_DATE_MARKER = "\x00"  # placeholder so the date's dashes survive later separator collapsing


def _normalize_dates(stem: str) -> str:
    for pattern, repl in _DATE_PATTERNS:
        if repl is not None:
            stem = pattern.sub(lambda m: repl(m).replace("-", _DATE_MARKER), stem)
        else:
            def _month_repl(m):
                day = m.group(1).zfill(2)
                month = _MONTHS[m.group(2).lower()]
                year = m.group(3)
                return f"{year}{_DATE_MARKER}{month}{_DATE_MARKER}{day}"
            stem = pattern.sub(_month_repl, stem)
    return stem


def suggest_name(filename: str, separator: str = "_") -> dict:
    """Suggest a normalized filename.

    Returns a dict: {
        "original": str, "suggested": str, "changed": bool,
        "warnings": [str, ...]
    }
    """
    if filename.lower() in EXEMPT_FILENAMES:
        return {"original": filename, "suggested": filename, "changed": False, "warnings": []}

    warnings = []

    if "." in filename and not filename.startswith("."):
        stem, ext = filename.rsplit(".", 1)
        ext = "." + ext.lower()
    else:
        stem, ext = filename, ""

    original_stem = stem

    stem = _normalize_dates(stem)

    # lowercase
    stem = stem.lower()

    # spaces / dashes / dots (mid-name) -> separator
    stem = re.sub(r"[ \t]+", separator, stem)
    stem = stem.replace("-", separator)
    stem = stem.replace(".", separator)

    # strip anything that isn't alnum, underscore, or the date-dash marker
    stem = re.sub(rf"[^a-z0-9_{_DATE_MARKER}]", "", stem)

    # collapse repeated separators (marker excluded so date dashes stay intact)
    stem = re.sub(r"_+", "_", stem)
    stem = stem.strip("_")

    if not stem:
        stem = "unnamed"

    # restore normalized-date dashes now that separator collapsing is done
    stem = stem.replace(_DATE_MARKER, "-")

    suggested = stem + ext

    # generic/low-signal name warnings (don't auto-rename, just flag)
    tokens = re.split(r"[_\-]", original_stem.lower())
    hit = GENERIC_TOKENS.intersection(tokens)
    if hit:
        warnings.append(
            f"generic/low-signal name token(s) {sorted(hit)} — consider a more descriptive name"
        )

    if re.search(r"\(\d+\)", filename):
        warnings.append("looks like an OS-generated duplicate, e.g. 'name (1).ext'")

    return {
        "original": filename,
        "suggested": suggested,
        "changed": suggested != filename,
        "warnings": warnings,
    }
