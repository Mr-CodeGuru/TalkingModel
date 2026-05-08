"""
engine/launcher.py — Interactive TUI launcher for TalkingModel.

Presents keyboard-navigable menus to select:
  1. Interaction mode  (Voice / Text)
  2. LLM model         (from models/gguf/)
  3. Vosk language     (Voice mode only, from models/vosk/)

On first run, missing models are automatically downloaded from
Hugging Face / alphacephei.com before launching the engine.
"""

from __future__ import annotations

import os
import sys

# ── Ensure project root is on sys.path regardless of how this is invoked ──────
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import subprocess

# ── Load .env early so env-vars are available to all imports ──────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=False)
except ImportError:
    pass

from utils.paths import ENGINE_DIR, GGUF_DIR, VOSK_DIR
from utils.model_manager import (
    ensure_gguf_model,
    ensure_vosk_model,
    list_local_gguf_models,
    list_local_vosk_models,
)

# ── Terminal colours ───────────────────────────────────────────────────────────
C_USER = "\033[92m"
C_AI   = "\033[96m"
C_BOLD = "\033[1m"
C_WARN = "\033[93m"
C_END  = "\033[0m"

MAIN_SCRIPT = os.path.join(os.path.dirname(__file__), "main.py")


# =============================================================================
#  Terminal menu helpers
# =============================================================================

def _getch() -> str:
    """Read a single keypress (including arrow keys) without echoing."""
    import tty
    import termios

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def _select_menu(prompt: str, options: list[str]) -> int:
    """
    Display an arrow-key navigable menu and return the selected index.
    Raises SystemExit on Ctrl+C / Ctrl+D.
    """
    selected = 0
    print(f"\n{C_BOLD}{C_AI}{prompt}{C_END}")
    for _ in options:
        print()

    while True:
        sys.stdout.write(f"\033[{len(options)}A")
        for i, opt in enumerate(options):
            if i == selected:
                sys.stdout.write(f"{C_USER} > {opt} {C_END}\033[K\r\n")
            else:
                sys.stdout.write(f"   {opt} \033[K\r\n")

        ch = _getch()
        if ch == "\x1b[A":            # Up arrow
            selected = max(0, selected - 1)
        elif ch == "\x1b[B":          # Down arrow
            selected = min(len(options) - 1, selected + 1)
        elif ch in ("\r", "\n"):      # Enter
            break
        elif ch in ("\x03", "\x04"):  # Ctrl+C / Ctrl+D
            print(f"\n{C_WARN}Aborted.{C_END}")
            sys.exit(0)

    return selected


# =============================================================================
#  Main launcher logic
# =============================================================================

def main() -> None:
    os.system("clear")
    print(f"{C_BOLD}{'='*40}")
    print(f"   TalkingModel Launcher")
    print(f"{'='*40}{C_END}")

    # ── Step 1: Run startup checks ────────────────────────────────────────────
    try:
        from utils.startup_check import run as startup_run
        startup_run(exit_on_failure=True)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"{C_WARN}⚠ Startup check error: {exc}{C_END}")

    os.system("clear")
    print(f"{C_BOLD}{'='*40}")
    print(f"   TalkingModel Launcher")
    print(f"{'='*40}{C_END}")

    # ── Step 2: Choose interaction mode ───────────────────────────────────────
    modes = ["🎤  Voice Interaction", "⌨️   Text Interaction"]
    m_idx = _select_menu("Select Interaction Mode  (↑/↓ + Enter):", modes)
    is_text = m_idx == 1

    # ── Step 3: Ensure & select LLM model ────────────────────────────────────
    print(f"\n{C_AI}Checking LLM model…{C_END}")
    try:
        ensure_gguf_model()          # downloads default if not cached
    except Exception as exc:
        print(f"\n{C_WARN}❌  Failed to obtain LLM model:\n    {exc}{C_END}")
        sys.exit(1)

    gguf_files = list_local_gguf_models()
    if not gguf_files:
        print(f"{C_WARN}Error: No .gguf models found in {GGUF_DIR}{C_END}")
        sys.exit(1)

    if len(gguf_files) == 1:
        selected_llm = str(gguf_files[0])
        print(f"\n  ✓  Using LLM: {gguf_files[0].name}")
    else:
        model_labels = [f.name for f in gguf_files]
        m = _select_menu("Select LLM Model:", model_labels)
        selected_llm = str(gguf_files[m])

    # ── Step 4: Ensure & select Vosk model (voice mode only) ─────────────────
    selected_vosk: str | None = None
    if not is_text:
        print(f"\n{C_AI}Checking Vosk model…{C_END}")
        try:
            ensure_vosk_model()      # downloads default (small) if not cached
        except Exception as exc:
            print(f"\n{C_WARN}❌  Failed to obtain Vosk model:\n    {exc}{C_END}")
            sys.exit(1)

        vosk_dirs = list_local_vosk_models()
        if not vosk_dirs:
            print(f"{C_WARN}Error: No vosk-model-* dirs found in {VOSK_DIR}{C_END}")
            sys.exit(1)

        if len(vosk_dirs) == 1:
            selected_vosk = str(vosk_dirs[0])
            print(f"\n  ✓  Using Vosk: {vosk_dirs[0].name}")
        else:
            labels = [d.name for d in vosk_dirs]
            v = _select_menu("Select Language Model (Vosk):", labels)
            selected_vosk = str(vosk_dirs[v])

    # ── Step 5: Build command and launch ─────────────────────────────────────
    cmd = [sys.executable, MAIN_SCRIPT, "--llm_path", selected_llm]
    if is_text:
        cmd.append("--text")
    else:
        cmd.extend(["--vosk_path", selected_vosk])

    os.system("clear")
    print(f"{C_AI}Launching Engine…{C_END}\n")

    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
