#!/usr/bin/env bash
# Install safeda-aam on Linux: downloads the latest standalone binary
# release and puts it on PATH. No Python required.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/aryanwalia2003/safeda-aam/main/install.sh | bash

set -euo pipefail

REPO="aryanwalia2003/safeda-aam"
INSTALL_DIR="$HOME/.local/bin"
BINARY_NAME="safeda-aam"
ASSET_NAME="safeda-aam-linux-x64"

os="$(uname -s)"
if [ "$os" != "Linux" ]; then
  echo "This installer is for Linux (detected: $os)." >&2
  echo "On macOS/other platforms with Python installed: pip install safeda-aam" >&2
  echo "On Windows: see install.ps1 in the repo." >&2
  exit 1
fi

url="https://github.com/${REPO}/releases/latest/download/${ASSET_NAME}"

echo "Installing safeda-aam..."
mkdir -p "$INSTALL_DIR"
tmp="$(mktemp)"
curl -fsSL "$url" -o "$tmp"
chmod +x "$tmp"
mv "$tmp" "$INSTALL_DIR/$BINARY_NAME"
echo "Installed to $INSTALL_DIR/$BINARY_NAME"

# Make sure it's usable right away, and next time you open a shell too.
case ":${PATH}:" in
  *":${INSTALL_DIR}:"*)
    ;;
  *)
    shell_name="$(basename "${SHELL:-bash}")"
    case "$shell_name" in
      zsh) rc_file="$HOME/.zshrc" ;;
      bash) rc_file="$HOME/.bashrc" ;;
      *) rc_file="$HOME/.profile" ;;
    esac
    if ! grep -qs "safeda-aam installer" "$rc_file" 2>/dev/null; then
      {
        echo ""
        echo "# added by the safeda-aam installer"
        echo "export PATH=\"$INSTALL_DIR:\$PATH\""
      } >> "$rc_file"
      echo "Added $INSTALL_DIR to PATH in $rc_file"
    fi
    export PATH="$INSTALL_DIR:$PATH"
    echo "(Open a new terminal, or run 'source $rc_file', for future sessions to pick it up.)"
    ;;
esac

echo ""
echo "Done. Try: safeda-aam --help"
