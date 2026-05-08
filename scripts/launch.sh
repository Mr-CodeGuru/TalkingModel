#!/usr/bin/env bash
# =============================================================================
#  TalkingModel — Master Launch Script (Aliased as 'tm')
#
#  This script handles:
#    1. Trust check on first run.
#    2. Automatic environment creation and dependency installation.
#    3. Launching the unified master CLI.
# =============================================================================

set -euo pipefail

# Resolve project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

VENV=".venv"

# ── Colors ──────────────────────────────────────────────────────────────────
RED="\033[31m"; YEL="\033[33m"; GRN="\033[32m"; CYN="\033[36m"; BOLD="\033[1m"; RESET="\033[0m"

# ── Phase 1: Check if environment exists ────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo -e "${BOLD}${CYN}=== TalkingModel First-Run Setup ===${RESET}"
    echo -e "This script will set up a Python virtual environment and install dependencies."
    echo -e "Path: ${PROJECT_ROOT}\n"
    
    # Ask for Trust
    echo -e "${BOLD}${YEL}⚠️  Do you trust this folder and want to proceed with installation? (y/n)${RESET}"
    read -r response
    
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted by user. Setup not completed.${RESET}"
        exit 1
    fi
    
    echo -e "\n${BOLD}${CYN}▶ Setting up environment...${RESET}"
    
    # Check Python
    PYTHON_CMD=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            PYTHON_CMD="$cmd"
            break
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}Error: Python 3 not found. Please install Python 3.9+${RESET}"
        exit 1
    fi
    
    # Create Venv
    "$PYTHON_CMD" -m venv .venv
    
    # Activate and install
    # shellcheck disable=SC1091
    source .venv/bin/activate
    
    echo -e "${CYN}▶ Installing Python dependencies (this may take a minute)...${RESET}"
    pip install --upgrade pip --no-cache-dir --quiet
    pip install -r requirements.txt --no-cache-dir --quiet
    
    if [[ "$(uname -s)" == "Darwin" ]]; then
        echo -e "${CYN}▶ Installing macOS voice support...${RESET}"
        pip install "pyobjc>=12.0" --no-cache-dir --quiet || true
    fi
    
    echo -e "${GRN}✓ Environment set up successfully!${RESET}\n"
    
    # Ask to create global 'tm' command
    echo -e "${BOLD}${CYN}▶ Would you like to create a global 'tm' command? (y/n)${RESET}"
    read -r alias_resp
    
    if [[ "$alias_resp" =~ ^[Yy]$ ]]; then
        SHELL_PROFILE=""
        if [[ "$SHELL" == *"zsh"* ]]; then
            SHELL_PROFILE="$HOME/.zshrc"
        elif [[ "$SHELL" == *"bash"* ]]; then
            SHELL_PROFILE="$HOME/.bashrc"
        fi
        
        if [ -n "$SHELL_PROFILE" ]; then
            echo "alias tm='${PROJECT_ROOT}/scripts/launch.sh'" >> "$SHELL_PROFILE"
            echo -e "${GRN}✓ Alias 'tm' added to $SHELL_PROFILE${RESET}"
            echo -e "${YEL}👉 Please run 'source $SHELL_PROFILE' or restart terminal to use 'tm' anywhere.${RESET}\n"
        fi
    fi
else
    # Environment already exists, just activate it
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

# ── Phase 2: Launch the application ─────────────────────────────────────────
# This will hand off to cli.py, which handles the model downloads with animations!
exec python engine/cli.py "$@"
