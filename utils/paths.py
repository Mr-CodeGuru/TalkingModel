"""
utils/paths.py — Single source of truth for all project paths.

All paths are computed relative to the repository root so the project
is fully portable across machines, operating systems, and install locations.
No hardcoded absolute paths anywhere else in the codebase.
"""

from pathlib import Path

# ── Repository Root ────────────────────────────────────────────────────────────
# This file lives at <root>/utils/paths.py → two parents up = root
PROJECT_ROOT: Path = Path(__file__).parent.parent.resolve()

# ── Models (gitignored — downloaded on first run) ─────────────────────────────
MODELS_DIR: Path = PROJECT_ROOT / "models"
GGUF_DIR: Path   = MODELS_DIR / "gguf"
VOSK_DIR: Path   = MODELS_DIR / "vosk"

# ── Logs / Records ────────────────────────────────────────────────────────────
LOGS_DIR: Path    = PROJECT_ROOT / "logs"
RECORD_FILE: Path = LOGS_DIR / "record.txt"

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_DIR: Path   = PROJECT_ROOT / "config"
MODELS_YAML: Path  = CONFIG_DIR / "models.yaml"
ENV_FILE: Path     = PROJECT_ROOT / ".env"

# ── Engine ────────────────────────────────────────────────────────────────────
ENGINE_DIR: Path = PROJECT_ROOT / "engine"


def ensure_directories() -> None:
    """Create all required runtime directories if they don't already exist."""
    for d in (GGUF_DIR, VOSK_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
