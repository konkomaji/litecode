#!/usr/bin/env sh
# litecode installer (Linux / macOS). Built by Konko Maji.
set -e
PY=$(command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "Python 3.10+ is required. Install it first."; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Python 3.10+ is required."; exit 1; }
cd "$(dirname "$0")"
"$PY" -m pip install --user -e .
echo "Installed. Running setup..."
"$PY" -m litecode.cli setup
