"""safeda-aam: sort a cluttered research directory in minutes, not hours.

Fastest path for a first-time user:
  safeda-aam quickstart <project> --source <messy-dir>

Full commands:
  safeda-aam quickstart <project> --source <dir>   one-shot: scaffold + auto-sort
  safeda-aam init <project>                        interactively scaffold a folder structure
  safeda-aam organize <project> --source <dir>     auto-sort loose files into it (bulk, few prompts)
  safeda-aam check-names <path> [--fix]            find/fix filenames that break naming conventions
  safeda-aam undo <project> [--run <id>]           reverse the last (or a given) organize run
  safeda-aam log <project> <message...>            append a timestamped note to the project's notebook
  safeda-aam status <project>                      summarize folders, manifest, and notebook
"""

import argparse
import fnmatch
import sys
from pathlib import Path

from safeda_aam import util
from safeda_aam.catalog import flat_catalog, DEFAULT_FOLDERS
from safeda_aam.classify import build_plan
from safeda_aam.naming import suggest_name

IGNORE_DIRS = {".safeda-aam", ".git", "__pycache__"}


# --------------------------------------------------------------------------
# small interactive helpers
# --------------------------------------------------------------------------

def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def parse_ranges(spec: str, n: int) -> set:
    """Parse '1,3,5-8' (1-based, inclusive) into a 0-based index set, bounds-checked."""
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            for i in range(a, b + 1):
                if 1 <= i <= n:
                    out.add(i - 1)
        else:
            i = int(part)
            if 1 <= i <= n:
                out.add(i - 1)
    return out


def resolve_selection(spec: str, pool_names: list) -> set:
    """Turn user input into a set of indices into pool_names.

    Accepts: 'all', comma/range lists ('1,3,5-8'), or a glob ('*.csv').
    """
    spec = spec.strip()
    if not spec or spec.lower() == "none":
        return set()
    if spec.lower() == "all":
        return set(range(len(pool_names)))
    if any(c in spec for c in "*?[]"):
        return {i for i, name in enumerate(pool_names) if fnmatch.fnmatch(name.lower(), spec.lower())}
    try:
        return parse_ranges(spec, len(pool_names))
    except ValueError:
        print(f"  Couldn't parse '{spec}' as numbers/ranges/glob — try again.")
        return set()


def confirm_rename(original: str, suggestion: dict, separator: str) -> str:
    """Show a naming suggestion for one file, return the final name to use."""
    for w in suggestion["warnings"]:
        print(f"    ! {w}")
    if not suggestion["changed"]:
        return original
    print(f"    naming convention suggests: '{original}' -> '{suggestion['suggested']}'")
    choice = ask("    [Y]es rename / [n]o keep original / type a custom name: ")
    if choice == "" or choice.lower() in ("y", "yes"):
        return suggestion["suggested"]
    if choice.lower() in ("n", "no"):
        return original
    return choice


# --------------------------------------------------------------------------
# shared scaffolding logic (used by both `init` and `quickstart`)
# --------------------------------------------------------------------------

def create_folders(project: Path, folders: list) -> None:
    project.mkdir(parents=True, exist_ok=True)
    for name in folders:
        folder_path = project / name
        folder_path.mkdir(parents=True, exist_ok=True)
        readme = folder_path / "README.md"
        if not readme.exists():
            readme.write_text(f"# {name}\n\n(Describe what belongs in this folder.)\n")

    config = {}
    if util.is_initialized(project):
        config = util.load_config(project)
    config["folders"] = sorted(set(config.get("folders", [])) | set(folders))
    config.setdefault("naming", {"separator": "_"})
    config.setdefault("created", util.timestamp())
    util.save_config(project, config)


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------

def cmd_init(args):
    project = Path(args.project).expanduser().resolve()

    existing = []
    if util.is_initialized(project):
        existing = util.load_config(project).get("folders", [])
        print(f"Project already initialized at {project} with folders: {existing}")
        print("Re-running init will let you add more folders.\n")

    catalog = flat_catalog()
    print(f"Setting up research project structure at: {project}\n")
    print("Pick the folders you want. Enter numbers/ranges (e.g. 1,3,5-8), 'all',")
    print(f"or just press Enter to use a recommended default set: {', '.join(DEFAULT_FOLDERS)}\n")

    current_category = None
    for i, (category, name, desc) in enumerate(catalog, start=1):
        if category != current_category:
            print(f"\n  {category}")
            current_category = category
        print(f"    {i:2d}. {name:<15} - {desc}")

    print()
    spec = ask("Your selection (Enter for defaults): ")
    if not spec:
        chosen = list(DEFAULT_FOLDERS)
        print(f"Using recommended defaults: {', '.join(chosen)}")
    else:
        chosen_indices = resolve_selection(spec, [name for _, name, _ in catalog])
        chosen = [catalog[i][1] for i in sorted(chosen_indices)]

    custom = ask("\nAny custom folder names to add (comma-separated, blank to skip): ")
    if custom:
        chosen += [c.strip() for c in custom.split(",") if c.strip()]

    folders = sorted(set(existing) | set(chosen))
    if not folders:
        print("No folders selected — nothing to create.")
        return

    create_folders(project, folders)

    print(f"\nCreated {len(folders)} folder(s) under {project}:")
    for name in folders:
        print(f"  - {name}/")
    print(f"\nConfig saved to {util.config_path(project)}")
    print(f"Next: safeda-aam organize {project} --source <folder with loose files>")


# --------------------------------------------------------------------------
# organize: auto-sort fast path + manual fallback
# --------------------------------------------------------------------------

def gather_files(source: Path, recursive: bool) -> list:
    if recursive:
        paths = [p for p in source.rglob("*") if p.is_file()]
    else:
        paths = [p for p in source.iterdir() if p.is_file()]
    paths = [p for p in paths if not any(part in IGNORE_DIRS for part in p.parts)]
    return sorted(paths)


def _move_one(project, source, src_file, folder_name, separator, run_id, auto_rename):
    """Apply naming + move for a single file. Returns (dest, renamed: bool)."""
    suggestion = suggest_name(src_file.name, separator)
    if auto_rename:
        # Auto mode: apply safe formatting fixes silently, but never
        # silently accept a rename flagged as risky (generic name, OS
        # duplicate) — those keep their original name so a human can look
        # at them later via `check-names`.
        final_name = suggestion["suggested"] if (suggestion["changed"] and not suggestion["warnings"]) else src_file.name
    else:
        final_name = confirm_rename(src_file.name, suggestion, separator)

    dest_dir = project / folder_name
    checksum = util.sha256_of(src_file)
    dest = util.safe_move(src_file, dest_dir, new_name=final_name)
    renamed = final_name != src_file.name
    util.log_move(project, src_file, dest, folder_name, checksum, renamed=renamed, run_id=run_id)
    return dest, renamed


def auto_sort(pool, folders, project, source, separator, run_id, dry_run=False):
    plan, review = build_plan(pool, folders)

    if not plan:
        print("Couldn't confidently auto-classify any files (extensions/names too generic).")
        print("Falling back to manual sort for everything.\n")
        manual_sort(pool, folders, project, source, separator, run_id)
        return

    print(f"\nAuto-sort plan for {len(pool)} file(s):\n")
    for folder, items in sorted(plan.items(), key=lambda kv: -len(kv[1])):
        names = [p.name for p, _ in items]
        examples = ", ".join(names[:3])
        more = f", +{len(names) - 3} more" if len(names) > 3 else ""
        print(f"  {len(items):5d} file(s) -> {folder}/   e.g. {examples}{more}")
    if review:
        print(f"  {len(review):5d} file(s) -> not confident enough to auto-place, will review individually")

    if dry_run:
        print("\nDry run only — no files were moved. Re-run without --dry-run to apply.")
        return

    print()
    while True:
        choice = ask("Apply this plan? [Y]es / [n]o do everything manually / [e]dit a group: ").lower()
        if choice in ("", "y", "yes"):
            break
        if choice in ("n", "no"):
            print("\nSwitching to fully manual sort.\n")
            manual_sort(pool, folders, project, source, separator, run_id)
            return
        if choice in ("e", "edit"):
            gname = ask(f"Redirect which group? ({'/'.join(plan.keys())}): ").strip()
            if gname not in plan:
                print("  Not a group in this plan.")
                continue
            newdest = ask(f"Send those {len(plan[gname])} file(s) to which folder instead? ({'/'.join(folders)}): ").strip()
            if newdest not in folders:
                print("  Not a configured project folder — skipped.")
                continue
            plan.setdefault(newdest, []).extend(plan.pop(gname))
            print(f"  -> {newdest}/ now has {len(plan[newdest])} file(s) queued.\n")
            for folder, items in sorted(plan.items(), key=lambda kv: -len(kv[1])):
                print(f"  {len(items):5d} file(s) -> {folder}/")
            print()
            continue
        print("  Please answer y, n, or e.")

    moved, renamed_count = 0, 0
    for folder, items in plan.items():
        for src_file, _reason in items:
            _dest, renamed = _move_one(project, source, src_file, folder, separator, run_id, auto_rename=True)
            moved += 1
            renamed_count += renamed
    print(f"\nAuto-sorted {moved} file(s) ({renamed_count} renamed to match naming convention).")

    if review:
        print(f"\n{len(review)} file(s) couldn't be auto-classified — grouping by type for quick placement:")
        grouped_review_sort(review, folders, project, source, separator, run_id)
    else:
        print("\nAll files sorted.")

    print(f"\nMade a mistake? Undo this whole run with: safeda-aam undo {project} --run {run_id}")


def grouped_review_sort(pool, folders, project, source, separator, run_id):
    """Bulk-place the leftover, not-confidently-classified files.

    Groups by extension so even a large, varied leftover pile is a handful
    of decisions (one folder pick per extension group) instead of one
    prompt per file — this is what keeps sorting thousands of files inside
    a few minutes even when auto-classification can't place everything.
    """
    if not pool:
        return

    groups = {}
    for p in pool:
        ext = p.suffix.lower() or "(no extension)"
        groups.setdefault(ext, []).append(p)
    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))

    print(f"({len(ordered)} group(s) to place)")
    print("Folders: " + ", ".join(f"{i + 1}) {f}" for i, f in enumerate(folders)))
    print("For each group: enter a folder number/name, 'new:<name>' to create one, or Enter to leave unsorted.\n")

    remaining = []
    for ext, items in ordered:
        examples = ", ".join(p.name for p in items[:3])
        more = f", +{len(items) - 3} more" if len(items) > 3 else ""
        spec = ask(f"  {len(items):4d} file(s) '{ext}'  e.g. {examples}{more}  -> folder: ").strip()

        if not spec:
            remaining.extend(items)
            continue

        if spec.lower().startswith("new:"):
            new_name = spec[4:].strip()
            if not new_name:
                print("    (blank name — skipped)")
                remaining.extend(items)
                continue
            create_folders(project, [new_name])
            folders.append(new_name)
            dest_folder = new_name
        elif spec.isdigit() and 1 <= int(spec) <= len(folders):
            dest_folder = folders[int(spec) - 1]
        elif spec in folders:
            dest_folder = spec
        else:
            print(f"    ('{spec}' isn't a configured folder — skipped; use a number, exact name, or new:<name>)")
            remaining.extend(items)
            continue

        for src_file in items:
            _move_one(project, source, src_file, dest_folder, separator, run_id, auto_rename=True)
        print(f"    moved {len(items)} file(s) -> {dest_folder}/")

    _report_remaining(remaining, source)


def manual_sort(pool, folders, project, source, separator, run_id):
    if not pool:
        return
    print("For each folder you'll see only files NOT YET assigned.")
    print("Selection syntax: '1,3,5-8', 'all', 'none', a glob like '*.csv', or 'quit' to stop.\n")

    for folder_name in folders:
        if not pool:
            break
        while True:
            print(f"\n=== Folder: {folder_name} ({len(pool)} unassigned file(s) remaining) ===")
            for i, p in enumerate(pool, start=1):
                rel = p.relative_to(source)
                print(f"  {i:2d}. {rel}")
            spec = ask(f"Move which files into '{folder_name}'? (blank = none, skip to next folder): ")
            if spec.lower() in ("quit", "q"):
                print("Stopping organize early. Remaining files are left unassigned.")
                _report_remaining(pool, source)
                return
            if not spec:
                break
            indices = resolve_selection(spec, [str(p.relative_to(source)) for p in pool])
            if not indices:
                continue
            selected = [pool[i] for i in sorted(indices)]
            for src_file in selected:
                dest, _renamed = _move_one(project, source, src_file, folder_name, separator, run_id, auto_rename=False)
                print(f"    moved -> {dest.relative_to(project)}")
            pool = [p for p in pool if p not in selected]
            if not pool:
                break
            if not ask("Add more to this same folder? [y/N]: ").lower().startswith("y"):
                break

    _report_remaining(pool, source)


def _report_remaining(pool, source):
    if not pool:
        print("\nAll files assigned. Nothing left unsorted.")
        return
    print(f"\n{len(pool)} file(s) still unassigned:")
    for p in pool:
        print(f"  - {p.relative_to(source)}")


def cmd_organize(args):
    project = Path(args.project).expanduser().resolve()
    config = util.load_config(project)
    folders = config["folders"]
    separator = config.get("naming", {}).get("separator", "_")

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        print(f"Source directory not found: {source}")
        sys.exit(1)

    pool = gather_files(source, args.recursive)
    if not pool:
        print(f"No files found in {source}.")
        return

    print(f"Found {len(pool)} file(s) in {source}. Sorting into: {project}")
    run_id = util.new_run_id()

    if args.manual:
        manual_sort(pool, folders, project, source, separator, run_id)
    else:
        auto_sort(pool, folders, project, source, separator, run_id, dry_run=args.dry_run)


# --------------------------------------------------------------------------
# quickstart: init (defaults) + organize (auto) in one shot
# --------------------------------------------------------------------------

def cmd_quickstart(args):
    project = Path(args.project).expanduser().resolve()
    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        print(f"Source directory not found: {source}")
        sys.exit(1)

    if args.folders:
        folders = [f.strip() for f in args.folders.split(",") if f.strip()]
    else:
        folders = list(DEFAULT_FOLDERS)

    if util.is_initialized(project):
        folders = sorted(set(util.load_config(project)["folders"]) | set(folders))

    create_folders(project, folders)
    print(f"Project ready at {project} with folders: {', '.join(folders)}")
    print("(Use `safeda-aam init` instead if you want to hand-pick from the full folder catalog.)\n")

    config = util.load_config(project)
    separator = config.get("naming", {}).get("separator", "_")
    pool = gather_files(source, recursive=True)
    if not pool:
        print(f"No files found in {source}.")
        return

    print(f"Found {len(pool)} file(s) in {source}.")
    run_id = util.new_run_id()
    auto_sort(pool, folders, project, source, separator, run_id, dry_run=args.dry_run)


# --------------------------------------------------------------------------
# undo
# --------------------------------------------------------------------------

def cmd_undo(args):
    project = Path(args.project).expanduser().resolve()
    if not util.is_initialized(project):
        print(f"No .safeda-aam config at {project} — nothing to undo.")
        sys.exit(1)

    run_id = args.run or util.last_run_id(project)
    if not run_id:
        print("No recorded organize runs to undo.")
        return

    result = util.undo_run(project, run_id)
    print(f"Undoing run {run_id}:")
    print(f"  restored {len(result['restored'])} file(s) to their original location")
    if result["skipped"]:
        print(f"  {len(result['skipped'])} file(s) could not be restored:")
        for entry, reason in result["skipped"]:
            print(f"    - {entry['dest']}: {reason}")


# --------------------------------------------------------------------------
# check-names
# --------------------------------------------------------------------------

def cmd_check_names(args):
    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        print(f"Path not found: {path}")
        sys.exit(1)

    files = [p for p in path.rglob("*") if p.is_file() and not any(part in IGNORE_DIRS for part in p.parts)]
    files.sort()

    flagged = []
    for f in files:
        suggestion = suggest_name(f.name, args.separator)
        if suggestion["changed"] or suggestion["warnings"]:
            flagged.append((f, suggestion))

    if not flagged:
        print(f"All {len(files)} filename(s) under {path} already match the convention.")
        return

    print(f"{len(flagged)} of {len(files)} filename(s) have naming issues:\n")
    for f, suggestion in flagged:
        rel = f.relative_to(path)
        print(f"  {rel}")
        if suggestion["changed"]:
            print(f"    -> suggest: {suggestion['suggested']}")
        for w in suggestion["warnings"]:
            print(f"    ! {w}")

    if not args.fix:
        print("\nRun with --fix to interactively rename these.")
        return

    print()
    for f, suggestion in flagged:
        if not suggestion["changed"]:
            continue
        rel = f.relative_to(path)
        choice = ask(f"Rename '{rel}' -> '{suggestion['suggested']}'? [Y]es/[n]o/custom: ")
        if choice == "" or choice.lower() in ("y", "yes"):
            new_name = suggestion["suggested"]
        elif choice.lower() in ("n", "no"):
            continue
        else:
            new_name = choice
        dest = util.unique_destination(f.with_name(new_name))
        f.rename(dest)
        print(f"  renamed -> {dest.relative_to(path)}")


# --------------------------------------------------------------------------
# log / status
# --------------------------------------------------------------------------

def cmd_log(args):
    project = Path(args.project).expanduser().resolve()
    if not util.is_initialized(project):
        print(f"No .safeda-aam config at {project} — run `safeda-aam init {project}` first.")
        sys.exit(1)
    message = " ".join(args.message)
    if not message:
        message = ask("Note: ")
    util.append_jsonl(util.notebook_path(project), {
        "timestamp": util.timestamp(),
        "message": message,
    })
    print("Logged.")


def cmd_status(args):
    project = Path(args.project).expanduser().resolve()
    config = util.load_config(project)
    manifest = util.read_jsonl(util.manifest_path(project))
    notebook = util.read_jsonl(util.notebook_path(project))

    print(f"Project: {project}")
    print(f"Created: {config.get('created', 'unknown')}")
    print(f"\nFolders ({len(config.get('folders', []))}):")
    counts = {}
    for entry in manifest:
        counts[entry["folder"]] = counts.get(entry["folder"], 0) + 1
    for name in config.get("folders", []):
        print(f"  - {name}/  ({counts.get(name, 0)} file(s) logged via organize)")

    print(f"\nTotal files moved via organize: {len(manifest)}")
    if notebook:
        print(f"\nLast {min(5, len(notebook))} notebook entries:")
        for entry in notebook[-5:]:
            print(f"  [{entry['timestamp']}] {entry['message']}")


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="safeda-aam", description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_quick = sub.add_parser("quickstart", help="One-shot: scaffold + auto-sort a messy directory")
    p_quick.add_argument("project", help="Path to the project directory (created if missing)")
    p_quick.add_argument("--source", required=True, help="Directory containing the loose/unsorted files")
    p_quick.add_argument("--folders", help="Comma-separated folder list (default: a sensible built-in set)")
    p_quick.add_argument("--dry-run", action="store_true", help="Preview the plan without moving anything")
    p_quick.set_defaults(func=cmd_quickstart)

    p_init = sub.add_parser("init", help="Scaffold a project's folder structure")
    p_init.add_argument("project", help="Path to the project directory (created if missing)")
    p_init.set_defaults(func=cmd_init)

    p_org = sub.add_parser("organize", help="Auto-sort loose files into the project structure")
    p_org.add_argument("project", help="Path to an already-initialized project directory")
    p_org.add_argument("--source", required=True, help="Directory containing the loose/unsorted files")
    p_org.add_argument("--no-recursive", dest="recursive", action="store_false",
                        help="Only look at top-level files in --source (default: recurse into subfolders)")
    p_org.add_argument("--manual", action="store_true",
                        help="Skip auto-classification; pick files folder-by-folder yourself")
    p_org.add_argument("--dry-run", action="store_true", help="Preview the auto-sort plan without moving anything")
    p_org.set_defaults(func=cmd_organize, recursive=True)

    p_undo = sub.add_parser("undo", help="Reverse an organize run, restoring files to their original location")
    p_undo.add_argument("project", help="Path to an already-initialized project directory")
    p_undo.add_argument("--run", help="Run id to undo (default: the most recent run)")
    p_undo.set_defaults(func=cmd_undo)

    p_names = sub.add_parser("check-names", help="Find/fix filenames that break naming conventions")
    p_names.add_argument("path", help="File or directory to check (recursive)")
    p_names.add_argument("--fix", action="store_true", help="Interactively apply suggested renames")
    p_names.add_argument("--separator", default="_", help="Word separator to normalize to (default: _)")
    p_names.set_defaults(func=cmd_check_names)

    p_log = sub.add_parser("log", help="Append a timestamped note to the project's notebook")
    p_log.add_argument("project", help="Path to an already-initialized project directory")
    p_log.add_argument("message", nargs="*", help="Note text (prompted if omitted)")
    p_log.set_defaults(func=cmd_log)

    p_status = sub.add_parser("status", help="Summarize a project's folders, manifest, and notebook")
    p_status.add_argument("project", help="Path to an already-initialized project directory")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
