"""
utils/startup_check.py — Pre-flight validation on every launch.

Catches common setup problems early (wrong Python, missing packages,
unwritable directories) and prints clear, actionable error messages
instead of cryptic tracebacks deep inside the engine.
"""

from __future__ import annotations

import sys
import os
import importlib
import platform
from pathlib import Path

# ── Ensure project root is on sys.path when run standalone ────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Colour helpers (no external deps)
_R = "\033[91m"   # red
_Y = "\033[93m"   # yellow
_G = "\033[92m"   # green
_B = "\033[96m"   # cyan
_D = "\033[1m"    # bold
_E = "\033[0m"    # reset


def _ok(msg: str) -> None:
    print(f"  {_G}✓{_E}  {msg}")


def _warn(msg: str) -> None:
    print(f"  {_Y}⚠{_E}  {msg}")


def _fail(msg: str) -> None:
    print(f"  {_R}✗{_E}  {msg}")


# =============================================================================
#  Individual checks
# =============================================================================

def _check_python_version() -> bool:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 9):
        _fail(
            f"Python 3.9+ required (found {major}.{minor}). "
            "Please upgrade: https://python.org/downloads"
        )
        return False
    _ok(f"Python {major}.{minor}.{sys.version_info[2]} ({platform.system()})")
    return True


def _check_required_packages() -> bool:
    required = [
        ("llama_cpp",       "llama-cpp-python", "pip install llama-cpp-python"),
        ("vosk",            "vosk",             "pip install vosk"),
        ("sounddevice",     "sounddevice",      "pip install sounddevice"),
        ("pyttsx3",         "pyttsx3",          "pip install pyttsx3"),
        ("requests",        "requests",         "pip install requests"),
        ("tqdm",            "tqdm",             "pip install tqdm"),
        ("huggingface_hub", "huggingface-hub",  "pip install huggingface-hub"),
        ("dotenv",          "python-dotenv",    "pip install python-dotenv"),
        ("yaml",            "PyYAML",           "pip install PyYAML"),
    ]
    all_ok = True
    for import_name, pkg_name, fix in required:
        try:
            importlib.import_module(import_name)
            _ok(f"{pkg_name}")
        except ImportError:
            _fail(f"{pkg_name} not installed  →  {fix}")
            all_ok = False
    return all_ok


def _check_models_directory() -> bool:
    try:
        from utils.paths import GGUF_DIR, VOSK_DIR, LOGS_DIR, ensure_directories
        ensure_directories()
    except Exception as exc:
        _fail(f"Cannot create models/logs directories: {exc}")
        return False

    # Check writable
    for d in (GGUF_DIR, VOSK_DIR, LOGS_DIR):
        test_file = d / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except OSError:
            _fail(f"Directory not writable: {d}")
            return False

    _ok(f"models/ and logs/ directories are writable")
    return True


def _check_config_file() -> bool:
    try:
        from utils.paths import MODELS_YAML
    except ImportError:
        _fail("Cannot import utils.paths — run from the project root directory.")
        return False

    if not MODELS_YAML.exists():
        _fail(f"Model registry missing: {MODELS_YAML}")
        return False
    try:
        import yaml
        with open(MODELS_YAML) as fh:
            data = yaml.safe_load(fh)
        llm_count  = len(data.get("models", {}).get("llm",  []))
        vosk_count = len(data.get("models", {}).get("vosk", []))
        _ok(f"config/models.yaml loaded ({llm_count} LLM, {vosk_count} Vosk models)")
    except Exception as exc:
        _fail(f"Error parsing config/models.yaml: {exc}")
        return False
    return True


def _check_audio_device() -> bool:
    """Best-effort check — warn instead of hard-fail (text mode doesn't need audio)."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = [d for d in devices if d["max_input_channels"] > 0]
        if inputs:
            _ok(f"Audio input device detected ({len(inputs)} input(s) available)")
        else:
            _warn("No audio input devices found — voice mode will not work (text mode is fine)")
    except Exception as exc:
        _warn(f"Could not query audio devices: {exc}")
    return True  # non-fatal


# =============================================================================
#  Main entry point
# =============================================================================

def run(exit_on_failure: bool = True) -> bool:
    """
    Run all startup checks.

    Parameters
    ----------
    exit_on_failure : bool
        If True (default), call sys.exit(1) when a critical check fails.
        Set to False in tests.

    Returns
    -------
    bool
        True if all critical checks passed.
    """
    print(f"\n{_D}{_B}=== TalkingModel — Startup Check ==={_E}\n")

    checks = [
        ("Python version",     _check_python_version),
        ("Required packages",  _check_required_packages),
        ("Directories",        _check_models_directory),
        ("Config file",        _check_config_file),
        ("Audio device",       _check_audio_device),
    ]

    all_passed = True
    for label, fn in checks:
        print(f"\n{_D}[{label}]{_E}")
        ok = fn()
        if not ok:
            all_passed = False

    print()
    if all_passed:
        print(f"{_G}{_D}✅  All checks passed — launching engine…{_E}\n")
    else:
        print(
            f"{_R}{_D}❌  Some checks failed.{_E}\n"
            f"    Run:  pip install -r requirements.txt\n"
            f"    Then: python utils/startup_check.py\n"
        )
        if exit_on_failure:
            sys.exit(1)

    return all_passed


if __name__ == "__main__":
    run()
