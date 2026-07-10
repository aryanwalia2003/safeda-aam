"""Entry point used only for building standalone binaries with PyInstaller.

Not part of the package's public interface — `bin/safeda-aam` or the
`safeda-aam` console script (installed via pip) are the normal ways to run
this from source.
"""

from safeda_aam.cli import main

if __name__ == "__main__":
    main()
