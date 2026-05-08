#!/usr/bin/env bash
# =============================================================================
#  TalkingModel — First-Run Setup Script (Linux / macOS)
#
#  Usage:
#    bash scripts/setup.sh
#
#  What this does:
#    1. Creates a Python virtual environment at .venv/
#    2. Installs all Python dependencies from requirements.txt
#    3. Downloads the default LLM and Vosk models from Hugging Face /
#       alphacephei.com and caches them in models/
#    4. Prints the command to start the assistant
#
#  Run this once after cloning. On subsequent runs you can go straight to
#    bash scripts/launch.sh
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED="\033[91m"; YEL="\033[93m"; GRN="\033[92m"; CYN="\033[96m"
BLD="\033[1m";  RST="\033[0m"

step()  { echo -e "\n${BLD}${CYN}▶  $*${RST}"; }
ok()    { echo -e "  ${GRN}✓${RST}  $*"; }
warn()  { echo -e "  ${YEL}⚠${RST}  $*"; }
fail()  { echo -e "  ${RED}✗${RST}  $*"; exit 1; }

# ── Resolve project root (directory containing this script's parent) ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "\n${BLD}============================================${RST}"
echo -e "${BLD}   TalkingModel — Setup${RST}"
echo -e "${BLD}============================================${RST}"
echo -e "  Project root: ${PROJECT_ROOT}"

# ── 1. Check Python ───────────────────────────────────────────────────────────
step "Checking Python version"

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
            PYTHON_CMD="$cmd"
            ok "Found Python $VER ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    fail "Python 3.9+ not found. Install from https://python.org/downloads"
fi

# ── 2. Create virtual environment ────────────────────────────────────────────
step "Creating virtual environment (.venv/)"

if [ -d ".venv" ]; then
    warn ".venv already exists — skipping creation"
else
    "$PYTHON_CMD" -m venv .venv
    ok "Virtual environment created"
fi

# ── 3. Activate venv ─────────────────────────────────────────────────────────
# shellcheck disable=SC1091
source .venv/bin/activate
ok "Virtual environment activated"

# ── 4. Upgrade pip ───────────────────────────────────────────────────────────
step "Upgrading pip"
pip install --upgrade pip --quiet
ok "pip upgraded"

# ── 5. Install dependencies ───────────────────────────────────────────────────
step "Installing Python dependencies (requirements.txt)"
pip install -r requirements.txt

# macOS: install pyobjc for better TTS compatibility
if [[ "$(uname -s)" == "Darwin" ]]; then
    echo -e "\n  ${CYN}macOS detected — installing pyobjc for native TTS support…${RST}"
    pip install "pyobjc>=12.0" --quiet || warn "pyobjc install failed (non-fatal, TTS still works via 'say')"
fi

ok "All dependencies installed"

# ── 6. Copy .env.example → .env (if not present) ─────────────────────────────
step "Environment configuration"

if [ ! -f ".env" ]; then
    cp .env.example .env
    ok ".env created from .env.example — edit it to set HF_TOKEN if needed"
else
    warn ".env already exists — skipping"
fi

# ── 7. Download models ────────────────────────────────────────────────────────
step "Downloading AI models (first run only — cached after this)"

"$PYTHON_CMD" - <<'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())

print("\n  Downloading LLM model (GGUF)…")
try:
    from utils.model_manager import ensure_gguf_model
    p = ensure_gguf_model()
    print(f"  ✓  LLM model ready: {p.name}")
except Exception as e:
    print(f"  ⚠  LLM model download failed: {e}")
    print("     You can retry later by running: python engine/launcher.py")

print("\n  Downloading Vosk STT model…")
try:
    from utils.model_manager import ensure_vosk_model
    p = ensure_vosk_model()
    print(f"  ✓  Vosk model ready: {p.name}")
except Exception as e:
    print(f"  ⚠  Vosk model download failed: {e}")
    print("     You can retry later by running: python engine/launcher.py")
PYEOF

# ── 8. Final instructions ─────────────────────────────────────────────────────
echo -e "\n${BLD}${GRN}============================================"
echo -e "   ✅  Setup complete!"
echo -e "============================================${RST}"
echo -e ""
echo -e "  To start TalkingModel:"
echo -e ""
echo -e "    ${BLD}bash scripts/launch.sh${RST}"
echo -e ""
echo -e "  Or manually:"
echo -e ""
echo -e "    ${BLD}source .venv/bin/activate${RST}"
echo -e "    ${BLD}python engine/launcher.py${RST}"
echo -e ""
