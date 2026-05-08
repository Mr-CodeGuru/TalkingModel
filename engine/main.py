"""
engine/main.py — TalkingModel core engine.

Handles:
  • Voice mode: Vosk STT → LLM → macOS say / pyttsx3 TTS
  • Text mode:  Terminal input → LLM → terminal output

Run via engine/launcher.py which passes the correct --llm_path and
--vosk_path arguments after model validation and download.
"""

from __future__ import annotations

import json
import queue
import sys
import argparse
import subprocess
import os

# ── Ensure project root is on sys.path ────────────────────────────────────────
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.paths import RECORD_FILE, ensure_directories

# ── Terminal UI colours ────────────────────────────────────────────────────────
class Colors:
    USER    = "\033[92m"   # green
    AI      = "\033[96m"   # cyan
    SYSTEM  = "\033[95m"   # magenta
    WARNING = "\033[93m"   # yellow
    BOLD    = "\033[1m"
    END     = "\033[0m"


# ── Argument parsing ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="TM Engine — AI Voice/Text Assistant")
parser.add_argument(
    "--text",
    action="store_true",
    help="Run in text-only mode (no microphone or TTS required)",
)
parser.add_argument(
    "--llm_path",
    type=str,
    required=True,
    help="Absolute path to the GGUF LLM model file",
)
parser.add_argument(
    "--vosk_path",
    type=str,
    help="Absolute path to the Vosk model directory (required for voice mode)",
)
args = parser.parse_args()

# ── Conversational memory ──────────────────────────────────────────────────────
chat_memory: list[tuple[str, str]] = []
MAX_MEMORY_TURNS = 4   # keep last 4 exchanges within llama's 2048 context

# ── Ensure runtime directories exist ──────────────────────────────────────────
ensure_directories()

# ── Load models ───────────────────────────────────────────────────────────────
if not args.text:
    from vosk import Model, KaldiRecognizer
    import sounddevice as sd

    print(f"{Colors.SYSTEM}Loading Vosk STT…{Colors.END}")
    if not args.vosk_path:
        print(
            f"{Colors.WARNING}Error: --vosk_path is required for voice mode.{Colors.END}"
        )
        sys.exit(1)
    vosk_model = Model(args.vosk_path)
    rec = KaldiRecognizer(vosk_model, 16000)

print(f"{Colors.SYSTEM}Loading LLM…{Colors.END}")
from llama_cpp import Llama

llm = Llama(
    model_path=args.llm_path,
    n_ctx=2048,
    n_threads=6,    # safe default; good for M-series Apple Silicon
    verbose=False,
)

if not args.text:
    print(f"{Colors.SYSTEM}Initializing TTS…{Colors.END}")
    import pyttsx3
    tts_engine = pyttsx3.init()
    tts_engine.setProperty("rate", 170)


# =============================================================================
#  Core functions
# =============================================================================

def speak(text: str) -> None:
    """Print the AI response and (in voice mode) play it via TTS."""
    print(f"{Colors.BOLD}{Colors.AI}> TM-ENGINE:{Colors.END} {text}")

    if args.text:
        return

    if sys.platform == "darwin":
        # The built-in macOS `say` command is perfectly blocking and avoids
        # the AppKit event-loop issues that pyttsx3 has on Python 3.11+.
        subprocess.run(["say", "-r", "170", text], check=False)
    else:
        tts_engine.say(text)
        tts_engine.runAndWait()


def process_text(user_text: str) -> str:
    """Run the LLM, update conversational memory, write to log, return response."""
    global chat_memory

    system_prompt = (
        "You are TM Engine, a highly advanced AI voice assistant. "
        "You are helpful, smart, and concise. "
        "Never pretend to be a human. Always give direct, accurate answers."
    )

    # Build prompt with rolling history
    prompt = f"System: {system_prompt}\n"
    for u, a in chat_memory:
        prompt += f"User: {u}\nAssistant: {a}\n"
    prompt += f"User: {user_text}\nAssistant:"

    output = llm(
        prompt,
        max_tokens=300,
        stop=["User:", "\nUser", "System:"],
        echo=False,
    )

    response: str = output["choices"][0]["text"].strip()

    # Update rolling memory
    chat_memory.append((user_text, response))
    if len(chat_memory) > MAX_MEMORY_TURNS:
        chat_memory.pop(0)

    # Persist conversation to log file
    with open(RECORD_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"🧑: {user_text}\n🤖: {response}\n")

    return response


# =============================================================================
#  Audio callback (voice mode only)
# =============================================================================

audio_queue: queue.Queue = queue.Queue()


def _audio_callback(indata, frames, time, status) -> None:   # noqa: ANN001
    """SoundDevice callback — must be fast and non-blocking."""
    if status:
        print(f"⚠️  Audio: {status}", file=sys.stderr)
    audio_queue.put(bytes(indata))


# =============================================================================
#  Engine loop
# =============================================================================

def _write_session_separator() -> None:
    with open(RECORD_FILE, "a", encoding="utf-8") as fh:
        fh.write("------\n")


if args.text:
    # ── Text mode ─────────────────────────────────────────────────────────────
    print(
        f"\n{Colors.BOLD}{Colors.SYSTEM}"
        f"▶  TM Engine Ready — type your prompt below  ◀"
        f"{Colors.END}\n"
        f"{Colors.SYSTEM}Press Ctrl+C to quit.{Colors.END}\n"
    )
    try:
        while True:
            text = input(f"{Colors.BOLD}{Colors.USER}> YOU:{Colors.END} ")
            if text.strip():
                response = process_text(text)
                speak(response)
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}🛑  Stopping Engine…{Colors.END}")
        _write_session_separator()
    except Exception as exc:
        print(f"\n{Colors.WARNING}❌  Error: {exc}{Colors.END}")
        _write_session_separator()

else:
    # ── Voice mode ────────────────────────────────────────────────────────────
    print(
        f"\n{Colors.BOLD}{Colors.SYSTEM}"
        f"▶  TM Engine Ready — speak now  ◀"
        f"{Colors.END}\n"
        f"{Colors.SYSTEM}Press Ctrl+C to quit.{Colors.END}\n"
    )
    try:
        with sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=_audio_callback,
        ):
            while True:
                data = audio_queue.get()

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")

                    if text:
                        print(f"{Colors.BOLD}{Colors.USER}> YOU:{Colors.END} {text}")
                        response = process_text(text)
                        speak(response)

                        # Discard audio buffered while engine was processing
                        with audio_queue.mutex:
                            audio_queue.queue.clear()

    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}🛑  Stopping Engine…{Colors.END}")
        _write_session_separator()
    except Exception as exc:
        print(f"\n{Colors.WARNING}❌  Pipeline Error: {exc}{Colors.END}")
        _write_session_separator()
