"""Bulk auto-classification: guess which project folder each file belongs in
from its extension and filename, so a cluttered directory of thousands of
files can be sorted with a handful of group-level decisions instead of one
decision per file.

This is a heuristic, not a guarantee — anything it can't classify with
reasonable confidence is left in a "review" pile for manual sorting.
"""

import re
from pathlib import Path

# filename-token -> ordered list of candidate folder-name keywords.
# Checked before extension, since a token match is usually more specific
# ("consent_2026.pdf" is a consent form, not just "a pdf").
TOKEN_MAP = [
    (r"consent", ["consent_forms"]),
    (r"\birb\b|ethic", ["ethics_irb"]),
    (r"survey", ["surveys"]),
    (r"pilot", ["pilot_data"]),
    (r"calibrat", ["calibration"]),
    (r"protocol|\bsop\b", ["protocols"]),
    (r"manuscript", ["manuscripts"]),
    (r"draft", ["drafts"]),
    (r"\breport\b", ["reports"]),
    (r"slide|presentation|poster|\btalk\b", ["presentations"]),
    (r"figure|\bfig\b|plot|chart", ["figures"]),
    (r"\btable\b|tbl", ["tables"]),
    (r"checkpoint|\bmodel\b|\bckpt\b|weights", ["models"]),
    (r"literature|\bpaper\b|citation|bib", ["literature", "references"]),
    (r"config|params?\b|settings", ["configs"]),
    (r"\blog\b|logfile", ["logs"]),
    (r"readme|codebook|dictionary", ["metadata", "docs"]),
    (r"backup|\bbak\b", ["backups"]),
    (r"archive|old_", ["archive"]),
    (r"supplement", ["supplementary"]),
]

# extension -> ordered list of candidate folder-name keywords, used when no
# filename token matched.
EXT_MAP = {
    ".csv": ["raw", "processed", "data"],
    ".tsv": ["raw", "processed", "data"],
    ".xlsx": ["raw", "processed", "data"],
    ".xls": ["raw", "processed", "data"],
    ".json": ["raw", "processed", "data"],
    ".parquet": ["processed", "raw", "data"],
    ".dat": ["raw", "data"],
    ".sav": ["raw", "data"],
    ".rdata": ["processed", "raw", "data"],
    ".rds": ["processed", "raw", "data"],
    ".mat": ["raw", "data"],
    ".h5": ["processed", "raw", "data"],

    ".py": ["scripts", "src", "code"],
    ".r": ["scripts", "src", "code"],
    ".rmd": ["notebooks", "scripts"],
    ".ipynb": ["notebooks", "scripts"],
    ".m": ["scripts", "src"],
    ".do": ["scripts"],
    ".sh": ["scripts"],
    ".sql": ["scripts"],

    ".png": ["figures"],
    ".jpg": ["figures"],
    ".jpeg": ["figures"],
    ".svg": ["figures"],
    ".tif": ["figures"],
    ".tiff": ["figures"],
    ".eps": ["figures"],
    ".gif": ["figures"],

    ".docx": ["manuscripts", "drafts", "reports"],
    ".doc": ["manuscripts", "drafts", "reports"],
    ".tex": ["manuscripts", "drafts"],
    ".odt": ["manuscripts", "drafts"],

    ".pptx": ["presentations"],
    ".ppt": ["presentations"],
    ".key": ["presentations"],

    ".yaml": ["configs"],
    ".yml": ["configs"],
    ".toml": ["configs"],
    ".ini": ["configs"],
    ".cfg": ["configs"],

    ".log": ["logs"],

    ".zip": ["archive"],
    ".tar": ["archive"],
    ".gz": ["archive"],
    ".7z": ["archive"],

    # .pdf is deliberately absent: it's ambiguous (literature, consent
    # forms, reports all end in .pdf) — resolved by filename token above,
    # else falls through to review.
}


def _singular(word: str) -> str:
    return word[:-1] if word.endswith("s") else word


def _match_folder(candidates, available_folders):
    """Return the first available folder whose name matches a candidate keyword.

    Matching is exact (or exact up to a trailing plural 's') on purpose —
    arbitrary substring matching is too loose here: e.g. 'scripts' is a
    literal substring of 'manuscripts', which would wrongly route .docx
    files into a scripts/ folder.
    """
    lower_map = {f.lower(): f for f in available_folders}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    for cand in candidates:
        cand_singular = _singular(cand)
        for name_lower, name in lower_map.items():
            if _singular(name_lower) == cand_singular:
                return name
    return None


def classify_file(filename: str, available_folders: list):
    """Return (folder_name_or_None, reason_str)."""
    p = Path(filename)
    stem = p.stem
    ext = p.suffix.lower()

    for pattern, candidates in TOKEN_MAP:
        if re.search(pattern, stem, re.IGNORECASE):
            folder = _match_folder(candidates, available_folders)
            if folder:
                return folder, f"filename matches '{pattern}'"

    if ext in EXT_MAP:
        folder = _match_folder(EXT_MAP[ext], available_folders)
        if folder:
            return folder, f"extension {ext}"

    return None, "no confident match"


def build_plan(files, available_folders):
    """Classify a list of Path objects.

    Returns (plan, review) where:
      plan is a dict {folder_name: [(path, reason), ...]}
      review is a list of paths that couldn't be confidently classified
    """
    plan = {}
    review = []
    for f in files:
        folder, reason = classify_file(f.name, available_folders)
        if folder:
            plan.setdefault(folder, []).append((f, reason))
        else:
            review.append(f)
    return plan, review
