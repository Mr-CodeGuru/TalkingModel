#!/usr/bin/env bash
# =============================================================================
#  TalkingModel — Launch Script (Linux / macOS)
#
#  Usage:
#    bash scripts/launch.sh
#
#  Activates the virtual environment and starts the interactive launcher.
#  Run scripts/setup.sh first if you haven't already.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV="${PROJECT_ROOT}/.venv"

if [ ! -d "${VENV}" ]; then
    echo "❌  Virtual environment not found at ${VENV}"
    echo "    Please run:  bash scripts/setup.sh"
    exit 1
fi

# Activate venv
# shellcheck disable=SC1091
source "${VENV}/bin/activate"

# Start launcher (pass through any CLI args)
exec python "${PROJECT_ROOT}/engine/launcher.py" "$@"
