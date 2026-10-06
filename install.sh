#!/usr/bin/env sh
# litecode installer for Linux and macOS. Built by Konko Maji.
#
#   curl -fsSL https://raw.githubusercontent.com/konkomaji/litecode/main/install.sh | sh
#
# or, from a cloned repo:  sh install.sh
#
# Installs litecode into its own Python environment (~/.local/share/litecode),
# links `litecode` and `lite` into ~/.local/bin, then starts setup.
# Set LITECODE_NO_SETUP=1 to skip setup. Uninstall: rm -rf ~/.local/share/litecode ~/.local/bin/litecode ~/.local/bin/lite
set -e
ZIP="https://github.com/konkomaji/litecode/archive/refs/heads/main.zip"
APP="${XDG_DATA_HOME:-$HOME/.local/share}/litecode"
VENV="$APP/venv"
BIN="$HOME/.local/bin"

say() { printf '  %s\n' "$*"; }
printf '\n\033[38;5;209m* litecode installer\033[0m\n  \033[2mBuilt by Konko Maji\033[0m\n\n'

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  say "Python 3.10 or newer is required. Install it, then run this again:"
  if command -v apt-get >/dev/null 2>&1; then say "  sudo apt-get install -y python3 python3-venv"
  elif command -v dnf >/dev/null 2>&1; then say "  sudo dnf install -y python3"
  elif command -v pacman >/dev/null 2>&1; then say "  sudo pacman -S python"
  elif command -v brew >/dev/null 2>&1; then say "  brew install python"
  else say "  https://www.python.org/downloads/"; fi
  exit 1
fi
say "Python: $("$PY" -c 'import sys; print(sys.version.split()[0])')"

SRC="$ZIP"
DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || true)"
[ -n "$DIR" ] && [ -f "$DIR/pyproject.toml" ] && SRC="$DIR"

mkdir -p "$APP" "$BIN"
if [ ! -x "$VENV/bin/python" ]; then
  say "Creating environment in $VENV"
  if ! "$PY" -m venv "$VENV" 2>/dev/null; then
    say "Could not create a Python environment."
    command -v apt-get >/dev/null 2>&1 && say "Fix: sudo apt-get install -y python3-venv"
    exit 1
  fi
fi
say "Installing litecode from $SRC"
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
if [ "$SRC" = "$ZIP" ]; then
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade "$SRC"
else
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade -e "$SRC"
fi
ln -sf "$VENV/bin/litecode" "$BIN/litecode"
ln -sf "$VENV/bin/litecode" "$BIN/lite"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *)
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
      if [ -f "$rc" ] && ! grep -q 'litecode installer' "$rc"; then
        printf '\n# added by litecode installer\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
      fi
    done
    say "Added ~/.local/bin to PATH in your shell profile. Open a new terminal, or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
    PATH="$BIN:$PATH"; export PATH
    ;;
esac

printf '\n  \033[32mlitecode is installed.\033[0m\n'
say "Commands: litecode (or lite)"
echo
if [ -z "$LITECODE_NO_SETUP" ]; then
  # setup asks questions; read them from the terminal even when this script is piped from curl
  if [ -t 1 ] && [ -r /dev/tty ]; then "$VENV/bin/litecode" setup < /dev/tty; else "$VENV/bin/litecode" setup; fi
  echo
  say "Next: cd into a project folder and run: litecode"
fi
