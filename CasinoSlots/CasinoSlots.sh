#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-x11}
export PYGAME_HIDE_SUPPORT_PROMPT=1

python3 game.py
