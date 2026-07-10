"""Shared helpers: config/manifest I/O, checksums, safe file moves."""

import hashlib
import json
import shutil
import time
from pathlib import Path

STATE_DIR = ".safeda-aam"
CONFIG_FILE = "config.json"
MANIFEST_FILE = "manifest.jsonl"
NOTEBOOK_FILE = "notebook.jsonl"


def state_dir(project: Path) -> Path:
    return project / STATE_DIR


def config_path(project: Path) -> Path:
    return state_dir(project) / CONFIG_FILE


def manifest_path(project: Path) -> Path:
    return state_dir(project) / MANIFEST_FILE


def notebook_path(project: Path) -> Path:
    return state_dir(project) / NOTEBOOK_FILE


def is_initialized(project: Path) -> bool:
    return config_path(project).exists()


def load_config(project: Path) -> dict:
    path = config_path(project)
    if not path.exists():
        raise FileNotFoundError(
            f"No .safeda-aam config found at {project}. Run `safeda-aam init {project}` first."
        )
    return json.loads(path.read_text())


def save_config(project: Path, config: dict) -> None:
    state_dir(project).mkdir(parents=True, exist_ok=True)
    config_path(project).write_text(json.dumps(config, indent=2, sort_keys=True))


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def new_run_id() -> str:
    """Identifier grouping all manifest entries from one organize invocation, for undo."""
    return time.strftime("%Y%m%d-%H%M%S")


def unique_destination(dest: Path) -> Path:
    """If dest exists, append _1, _2, ... before the extension until free."""
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    i = 1
    while True:
        candidate = dest.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def safe_move(src: Path, dest_dir: Path, new_name: str = None) -> Path:
    """Move src into dest_dir, optionally renaming, avoiding overwrite collisions."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = new_name or src.name
    dest = unique_destination(dest_dir / name)
    shutil.move(str(src), str(dest))
    return dest


def log_move(project: Path, src: Path, dest: Path, folder: str, checksum: str, renamed: bool, run_id: str) -> None:
    append_jsonl(manifest_path(project), {
        "timestamp": timestamp(),
        "run_id": run_id,
        "src": str(src),
        "dest": str(dest),
        "folder": folder,
        "sha256": checksum,
        "renamed": renamed,
    })


def last_run_id(project: Path) -> str:
    entries = read_jsonl(manifest_path(project))
    if not entries:
        return None
    return entries[-1].get("run_id")


def undo_run(project: Path, run_id: str) -> dict:
    """Move every file logged under run_id back to its original src path.

    Returns {"restored": [...], "skipped": [(entry, reason), ...]}. Rewrites
    the manifest to drop the entries that were successfully undone.
    """
    entries = read_jsonl(manifest_path(project))
    keep = []
    restored = []
    skipped = []
    for entry in entries:
        if entry.get("run_id") != run_id:
            keep.append(entry)
            continue
        dest = Path(entry["dest"])
        src = Path(entry["src"])
        if not dest.exists():
            skipped.append((entry, f"expected file not found at {dest} (already moved/deleted?)"))
            keep.append(entry)
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        target = unique_destination(src) if src.exists() else src
        shutil.move(str(dest), str(target))
        restored.append({"from": str(dest), "to": str(target)})

    path = manifest_path(project)
    with path.open("w") as f:
        for entry in keep:
            f.write(json.dumps(entry) + "\n")

    return {"restored": restored, "skipped": skipped}
