#!/usr/bin/env bash
# One-time setup (Linux/macOS): creates a virtual environment and installs everything.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
echo; echo "Done. Check the content with:  (cd demo && ../.venv/bin/ctf lint)"; echo "Then start the game with:      ./run.sh"
