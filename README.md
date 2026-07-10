# safeda-aam

A CLI for organizing PhD/research project data: scaffold a folder
structure, then sort a cluttered pile of files into it in bulk — designed
so a first-time user can sort a directory of thousands of files in a few
minutes, not hours.

## Install

**Windows** — one PowerShell command, no Python or PATH setup needed:

```powershell
irm https://raw.githubusercontent.com/aryanwalia2003/safeda-aam/main/install.ps1 | iex
```

**Linux** — one shell command, no Python needed:

```bash
curl -fsSL https://raw.githubusercontent.com/aryanwalia2003/safeda-aam/main/install.sh | bash
```

Both download a standalone binary from the [latest release](https://github.com/aryanwalia2003/safeda-aam/releases/latest),
put it somewhere sensible, and set up PATH for you — the command works
immediately, including in the same terminal window you ran the installer
in.

**Already have Python?** `pip install safeda-aam` works too (see
[Development](#development) for installing from source).

## Fastest path: `safeda-aam quickstart`

```bash
safeda-aam quickstart ~/research/my-study --source ~/Downloads/lab_dump
```

One command: scaffolds a sensible default folder set (`raw/`, `processed/`,
`scripts/`, `figures/`, `results/`, `docs/`, `literature/`, `logs/`), then
classifies every file by extension and filename (`results.csv` -> `raw/`,
`analysis.py` -> `scripts/`, `consent_form.pdf` -> flagged for review, etc.)
and shows **one plan** — a handful of lines like:

```
   1515 file(s) -> raw/       e.g. survey_data.csv, results.xlsx, +1512 more
   1379 file(s) -> figures/   e.g. fig1.png, plot_final.jpg, +1376 more
    483 file(s) -> scripts/   e.g. analysis.py, model.ipynb, +480 more
   1037 file(s) -> not confident enough to auto-place
```

One keystroke (`Enter`) applies it. Whatever it couldn't confidently
classify gets grouped by extension for one more quick round of decisions
(`92 file(s) '.pptx' -> folder:`), not one prompt per file. In testing,
5000 mixed files sorted completely in **7 keystrokes total**. Use
`--dry-run` to preview the plan without moving anything, and `--folders
a,b,c` to override the default folder set.

**Made a mistake? `safeda-aam undo <project>`** reverses the entire last run
(or `--run <id>` for an older one), moving every file back to where it
came from.

## Commands

### `safeda-aam quickstart <project> --source <dir>`
Scaffold + auto-sort in one shot. See above. This is what a first-time
user should reach for.

### `safeda-aam init <project>`
For when you want to hand-pick folders instead of the quickstart
defaults: browse a curated catalog (raw/, processed/, scripts/, figures/,
literature/, ethics_irb/, consent_forms/, ...) grouped by category, or
just press Enter to accept the same recommended default set quickstart
uses. Creates the directories (each with a starter `README.md`) and a
`.safeda-aam/config.json` recording your choices.

```bash
safeda-aam init ~/research/my-study
```

### `safeda-aam organize <project> --source <messy-dir>`
The auto-sort engine on its own, for a project you already `init`'d — same
classify-plan-confirm flow as quickstart, recurses into subfolders of
`--source` by default. Every move gets a naming-convention pass (applied
automatically for the bulk of files; anything flagged as a risky rename —
a generic name like `final_v2`, an OS duplicate-suffix like `report
(1).pdf` — keeps its original name so a human can look at it later via
`check-names`). Every move is logged to `.safeda-aam/manifest.jsonl` with a
timestamp, run id, and sha256 checksum.

```bash
safeda-aam organize ~/research/my-study --source ~/Downloads/lab_dump
safeda-aam organize ~/research/my-study --source ~/Downloads/lab_dump --dry-run   # preview only
safeda-aam organize ~/research/my-study --source ~/Downloads/lab_dump --manual    # old one-file-at-a-time flow
```

### `safeda-aam undo <project> [--run <id>]`
Reverses an `organize`/`quickstart` run, restoring every file it moved to
its original location and removing those entries from the manifest.
Defaults to the most recent run.

### `safeda-aam check-names <path> [--fix]`
Standalone naming linter — recursively scans any path (doesn't need to
be a safeda-aam project) and reports filenames that break convention
(spaces, mixed case, inconsistent date formats, generic names like
`final_v2.csv`, OS duplicate-suffixes like `report (1).pdf`). Conventional
files (`README.md`, `LICENSE`, `.gitignore`, ...) are exempt. `--fix` lets
you approve each rename interactively.

```bash
safeda-aam check-names ~/research/my-study --fix
```

### `safeda-aam log <project> [message...]`
Quick timestamped notebook entry, stored in `.safeda-aam/notebook.jsonl`.

```bash
safeda-aam log ~/research/my-study "reran pipeline with new calibration file"
```

### `safeda-aam status <project>`
Summarizes configured folders, how many files `organize` has logged
into each, and the last few notebook entries.

## Naming convention (default)

Lowercase `snake_case`, dates normalized to `YYYY-MM-DD` (dashes
preserved even though word-separators elsewhere become underscores),
spaces/dashes collapsed, lowercase extensions. Configurable separator via
`--separator` on `check-names`; project-level default lives in
`.safeda-aam/config.json` under `naming.separator`.

## How auto-classification decides

`safeda_aam/classify.py` checks, in order:
1. **Filename tokens** — `consent`, `survey`, `calibration`, `protocol`,
   `figure`, `manuscript`, `draft`, `report`, `model`/`checkpoint`,
   `literature`/`paper`/`citation`, `config`, `log`, etc. — matched
   against your configured folder names.
2. **Extension** — `.csv`/`.xlsx`/`.json`/... -> raw/processed,
   `.py`/`.r`/`.ipynb` -> scripts/notebooks, `.png`/`.jpg`/... -> figures,
   `.docx`/`.pptx` -> manuscripts/presentations, etc. `.pdf` is
   deliberately *not* extension-mapped (it's ambiguous — literature,
   consent forms, and reports are all PDFs) and relies on the token pass.
3. Anything that doesn't match a folder you actually created falls to the
   **review** pile, grouped by extension for one bulk decision each.

It only ever proposes a plan — nothing moves until you confirm it (or a
specific group within it), and `undo` can always put it all back.

## Development

Pure Python stdlib, no runtime dependencies.

```bash
git clone git@github.com:aryanwalia2003/safeda-aam.git
cd safeda-aam
pip install -e .
safeda-aam --help
```

Releases build standalone Linux and Windows binaries via PyInstaller in
`.github/workflows/release.yml`, triggered by pushing a `v*` tag.

## Layout

```
safeda-aam/
  bin/safeda-aam            # entry point for running straight from a checkout
  safeda_aam/
    catalog.py               # curated folder catalog + recommended defaults
    classify.py               # bulk auto-classification (extension/token heuristics)
    naming.py                 # filename suggestion/normalization
    util.py                   # config/manifest I/O, checksums, safe moves, undo
    cli.py                    # argparse commands
  packaging/pyinstaller_entry.py  # entry point used only to build standalone binaries
  install.sh / install.ps1        # one-command installers for the standalone binaries
  pyproject.toml                  # pip packaging (console_scripts entry point)
```

Each project you run `init`/`quickstart`/`organize` on gets its own
`.safeda-aam/` directory holding `config.json`, `manifest.jsonl`, and
`notebook.jsonl` — safeda-aam itself stays stateless.
