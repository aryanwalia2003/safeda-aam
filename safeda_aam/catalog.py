"""Curated catalog of common research-data folders, grouped by category.

Used by `safeda-aam init` to offer a menu instead of making the user type
folder names from scratch. Anything not listed here can still be added
as a custom folder during init.
"""

CATALOG = {
    "Data": [
        ("raw", "Untouched original data, exactly as received/collected"),
        ("processed", "Cleaned/transformed data ready for analysis"),
        ("interim", "Intermediate data between raw and processed"),
        ("external", "Third-party or reference datasets you didn't collect"),
    ],
    "Code": [
        ("scripts", "Standalone analysis/processing scripts"),
        ("notebooks", "Jupyter/R Markdown notebooks"),
        ("src", "Reusable library/package code"),
    ],
    "Outputs": [
        ("results", "Numeric/tabular outputs of analysis"),
        ("figures", "Plots and images for papers/slides"),
        ("tables", "Formatted tables for papers/reports"),
        ("models", "Trained model files / checkpoints"),
    ],
    "Writing": [
        ("manuscripts", "Paper drafts in progress"),
        ("drafts", "Early/working drafts of any document"),
        ("reports", "Internal reports, progress updates"),
        ("presentations", "Slides, posters, talks"),
    ],
    "Reference": [
        ("literature", "PDFs of papers you're citing/reading"),
        ("references", "Bibliography files, citation exports"),
        ("protocols", "Experimental/analysis protocols and SOPs"),
    ],
    "Admin & provenance": [
        ("logs", "Run logs, lab notebook entries"),
        ("configs", "Config files, parameter sets"),
        ("docs", "General documentation"),
        ("ethics_irb", "IRB/ethics approvals and consent materials"),
    ],
    "Storage": [
        ("archive", "Completed/old material kept for record"),
        ("backups", "Redundant copies of critical data"),
        ("temp_scratch", "Throwaway working space, safe to delete"),
    ],
    "Human subjects": [
        ("surveys", "Survey instruments and raw survey exports"),
        ("consent_forms", "Signed consent/assent forms"),
        ("pilot_data", "Pilot-study data, kept separate from main study"),
    ],
    "Misc": [
        ("supplementary", "Supplementary material for publications"),
        ("calibration", "Instrument calibration data/files"),
        ("metadata", "Standalone metadata/codebooks/data dictionaries"),
    ],
}


# Sensible starting point for someone who just wants to get moving —
# covers the extension/token groups classify.py knows about without making
# a first-time user read a 30-item menu.
DEFAULT_FOLDERS = [
    "raw", "processed", "scripts", "figures", "results",
    "docs", "literature", "logs",
]


def flat_catalog():
    """Return a flat list of (category, name, description) tuples, in display order."""
    out = []
    for category, items in CATALOG.items():
        for name, desc in items:
            out.append((category, name, desc))
    return out
