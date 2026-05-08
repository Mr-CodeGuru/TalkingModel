"""
engine/cli.py — Unified, Professional CLI for TalkingModel.

Features:
  • Interactive TUI on launch (Mode & Model selection)
  • Automatic model downloading with clean progress indicators
  • In-chat commands: /model, /voice, /quota, /session, /help
  • Threaded "thinking" spinner animation
  • Context quota tracking (estimated tokens)
"""

from __future__ import annotations

import os
import sys
import time
import json
import queue
import argparse
import threading
import subprocess
from pathlib import Path

# ── Ensure project root is on sys.path ────────────────────────────────────────
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Load .env early
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=False)
except ImportError:
    pass

# Setup tab-completion for commands
try:
    import readline
    _commands = ['/help', '/model', '/voice', '/quota', '/session', '/additions', '/exit']
    def _completer(text, state):
        options = [i for i in _commands if i.startswith(text)]
        return options[state] if state < len(options) else None
    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")
except ImportError:
    pass # Fallback for Windows or systems without readline

from utils.paths import RECORD_FILE, ensure_directories
from utils.model_manager import (
    ensure_gguf_model,
    ensure_vosk_model,
    list_local_gguf_models,
    list_local_vosk_models,
    list_available_models,
)

# ── Terminal Colors & Styles ──────────────────────────────────────────────────
class Style:
    RESET = "\033[0m"
    BOLD  = "\033[1m"
    DIM   = "\033[2m"
    
    # Foreground colors
    RED   = "\033[31m"
    GRN   = "\033[32m"
    YEL   = "\033[33m"
    BLU   = "\033[34m"
    MAG   = "\033[35m"
    CYN   = "\033[36m"
    WHT   = "\033[37m"
    
    # High intensity
    H_CYN = "\033[96m"
    H_GRN = "\033[92m"
    H_MAG = "\033[95m"

# ── Global State ─────────────────────────────────────────────────────────────
chat_memory: list[tuple[str, str]] = []
MAX_MEMORY_TURNS = 4
is_voice_mode = False
current_model_path = ""
current_vosk_path = ""
llm = None
vosk_model = None
rec = None
tts_engine = None
audio_queue = queue.Queue()
spinner_running = False

# =============================================================================
#  Animations & UI Helpers
# =============================================================================

def _spinner_task():
    """Thread task for the thinking spinner."""
    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    while spinner_running:
        for c in chars:
            sys.stdout.write(f"\r{Style.CYN}{c}{Style.RESET} Assistant is thinking...")
            sys.stdout.flush()
            time.sleep(0.08)
            if not spinner_running:
                break
    # Clear the line when done
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

def start_spinner():
    global spinner_running
    spinner_running = True
    threading.Thread(target=_spinner_task, daemon=True).start()

def stop_spinner():
    global spinner_running
    spinner_running = False
    time.sleep(0.1) # give it a moment to clean up the line

def print_banner():
    os.system("clear")
    print(f"{Style.BOLD}{Style.CYN}" + "="*50)
    print("        TALKING MODEL — Professional CLI")
    print("="*50 + f"{Style.RESET}\n")

# =============================================================================
#  TUI Menu Helpers
# =============================================================================

def _getch() -> str:
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

def select_menu(prompt: str, options: list[str]) -> int:
    selected = 0
    print(f"{Style.BOLD}{Style.CYN}{prompt}{Style.RESET}")
    for _ in options: print()

    while True:
        sys.stdout.write(f"\033[{len(options)}A")
        for i, opt in enumerate(options):
            if i == selected:
                sys.stdout.write(f"{Style.H_GRN} > {opt} {Style.RESET}\033[K\r\n")
            else:
                sys.stdout.write(f"   {opt} \033[K\r\n")

        ch = _getch()
        if ch == "\x1b[A": # Up
            selected = max(0, selected - 1)
        elif ch == "\x1b[B": # Down
            selected = min(len(options) - 1, selected + 1)
        elif ch in ("\r", "\n"): # Enter
            break
        elif ch in ("\x03", "\x04"): # Ctrl+C
            print(f"\n{Style.YEL}Aborted.{Style.RESET}")
            sys.exit(0)
    return selected

# =============================================================================
#  Core AI Logic
# =============================================================================

def load_llm(model_path):
    global llm, current_model_path
    print(f"{Style.H_MAG}Loading LLM ({Path(model_path).name})...{Style.RESET}")
    from llama_cpp import Llama
    llm = Llama(model_path=model_path, n_ctx=2048, n_threads=6, verbose=False)
    current_model_path = model_path
    print(f"{Style.H_GRN}✓ LLM Loaded.{Style.RESET}")

def load_vosk(vosk_path):
    global vosk_model, rec, current_vosk_path
    from vosk import Model, KaldiRecognizer
    print(f"{Style.H_MAG}Loading Vosk STT...{Style.RESET}")
    vosk_model = Model(vosk_path)
    rec = KaldiRecognizer(vosk_model, 16000)
    current_vosk_path = vosk_path
    print(f"{Style.H_GRN}✓ Vosk Loaded.{Style.RESET}")

def speak(text: str):
    print(f"{Style.BOLD}{Style.H_CYN}> Assistant:{Style.RESET} {text}")
    if not is_voice_mode:
        return
        
    if sys.platform == "darwin":
        subprocess.run(["say", "-r", "170", text], check=False)
    else:
        global tts_engine
        if tts_engine is None:
            import pyttsx3
            tts_engine = pyttsx3.init()
            tts_engine.setProperty("rate", 170)
        tts_engine.say(text)
        tts_engine.runAndWait()

def process_text(user_text: str) -> str:
    global chat_memory
    
    system_prompt = (
        "You are TM Engine, a highly advanced, ultra-intelligent AI assistant with a modern, sleek personality. "
        "Provide creative, insightful, and brilliant answers. Be concise but impactful. Never pretend to be human."
    )
    
    prompt = f"System: {system_prompt}\n"
    for u, a in chat_memory:
        prompt += f"User: {u}\nAssistant: {a}\n"
    prompt += f"User: {user_text}\nAssistant:"
    
    start_spinner()
    output = llm(prompt, max_tokens=300, stop=["User:", "\nUser", "System:"], echo=False)
    stop_spinner()
    
    response = output["choices"][0]["text"].strip()
    
    chat_memory.append((user_text, response))
    if len(chat_memory) > MAX_MEMORY_TURNS:
        chat_memory.pop(0)
        
    # Log it
    with open(RECORD_FILE, "a", encoding="utf-8") as f:
        f.write(f"🧑: {user_text}\n🤖: {response}\n")
        
    return response

# =============================================================================
#  Slash Commands
# =============================================================================

def handle_command(cmd_text: str):
    global is_voice_mode, chat_memory, current_model_path
    
    parts = cmd_text.split()
    command = parts[0].lower()
    
    if command == "/help":
        print(f"\n{Style.BOLD}Available Commands:{Style.RESET}")
        print("  /help       - Show this help message")
        print("  /model      - Switch LLM models")
        print("  /voice      - Toggle voice/text mode")
        print("  /quota      - Check context window usage")
        print("  /session    - Clear chat memory")
        print("  /additions  - Register external custom models")
        print("  /exit       - Quit the application\n")
        
    elif command == "/quota":
        # Estimate tokens based on characters (rough but functional without tiktoken)
        total_chars = 0
        for u, a in chat_memory:
            total_chars += len(u) + len(a)
        estimated_tokens = total_chars // 4
        percentage = (estimated_tokens / 2048) * 100
        
        # Dynamic progress bar
        bar_len = 20
        filled_len = int(bar_len * min(percentage, 100) / 100)
        bar = '█' * filled_len + '░' * (bar_len - filled_len)
        
        print(f"\n{Style.BOLD}Context Quota Usage:{Style.RESET}")
        print(f"  Memory Turns: {len(chat_memory)}/{MAX_MEMORY_TURNS}")
        print(f"  Est. Tokens:  {estimated_tokens}/2048 ({percentage:.1f}%)")
        print(f"  Status:       [{bar}]\n")
        
    elif command == "/session":
        if chat_memory:
            # Save the current session before clearing
            session_file = Path(_PROJECT_ROOT) / "logs" / f"session_{int(time.time())}.txt"
            with open(session_file, "w") as f:
                for u, a in chat_memory:
                    f.write(f"User: {u}\nAssistant: {a}\n\n")
            print(f"\n{Style.H_GRN}✓ Session saved to logs/{session_file.name}{Style.RESET}")
            
        chat_memory = []
        print(f"{Style.H_GRN}✓ New session started. Memory is fresh.{Style.RESET}\n")
        
    elif command == "/voice":
        is_voice_mode = not is_voice_mode
        status = "ENABLED" if is_voice_mode else "DISABLED"
        print(f"\n{Style.H_CYN}Voice mode {status}.{Style.RESET}\n")
        if is_voice_mode and vosk_model is None:
             print(f"{Style.YEL}Warning: Vosk not loaded. Restart with Voice enabled to use STT.{Style.RESET}")
             
    elif command == "/model":
        print(f"\n{Style.CYN}Available Local Models:{Style.RESET}")
        models = list_local_gguf_models()
        if not models:
            print("  No models cached.")
            return
            
        options = [m.name for m in models]
        idx = select_menu("Select a model to switch to:", options)
        selected_path = str(models[idx])
        
        if selected_path == current_model_path:
            print(f"{Style.YEL}Already using this model.{Style.RESET}\n")
        else:
            load_llm(selected_path)
            print(f"{Style.H_GRN}✓ Switched model successfully.{Style.RESET}\n")

    elif command == "/additions":
        print(f"\n{Style.BOLD}Add Custom Models{Style.RESET}")
        modes = ["1. Add LLM Model (.gguf file)", "2. Add Vosk STT Model (folder)"]
        idx = select_menu("What would you like to add?", modes)
        
        if idx == 0:
            path_str = input(f"{Style.CYN}Enter absolute path to the .gguf file:{Style.RESET} ").strip()
            p = Path(path_str)
            if not p.is_file() or not p.name.endswith('.gguf'):
                print(f"{Style.RED}Error: File not found or not a .gguf file.{Style.RESET}\n")
                return
            
            # Symlink it
            dest = Path(_PROJECT_ROOT) / "models" / "gguf" / p.name
            try:
                if dest.exists():
                    print(f"{Style.YEL}A link or file with this name already exists in models/gguf/.{Style.RESET}\n")
                    return
                os.symlink(p.resolve(), dest)
                print(f"{Style.H_GRN}✓ Linked {p.name} into models/gguf/.{Style.RESET}\n")
                print(f"{Style.CYN}It is now available in the /model list.{Style.RESET}\n")
            except Exception as e:
                print(f"{Style.RED}Error creating symlink: {e}{Style.RESET}\n")
                
        else:
            path_str = input(f"{Style.CYN}Enter absolute path to the Vosk model directory:{Style.RESET} ").strip()
            p = Path(path_str)
            if not p.is_dir():
                print(f"{Style.RED}Error: Directory not found.{Style.RESET}\n")
                return
                
            label = input(f"{Style.CYN}Enter a label for this model (e.g., 'Custom Large'):{Style.RESET} ").strip()
            
            # Append to models.yaml
            models_yaml_path = Path(_PROJECT_ROOT) / "config" / "models.yaml"
            try:
                with open(models_yaml_path, "a") as f:
                    f.write(f"""
    - id: {p.name}
      label: "{label} (Custom Local)"
      dirname: {p.name}
      default: false
""")
                # Symlink it
                dest = Path(_PROJECT_ROOT) / "models" / "vosk" / p.name
                if not dest.exists():
                    os.symlink(p.resolve(), dest)
                print(f"{Style.H_GRN}✓ Registered in models.yaml and linked to models/vosk/.{Style.RESET}\n")
                print(f"{Style.CYN}Restart the application or switch mode to use it.{Style.RESET}\n")
            except Exception as e:
                print(f"{Style.RED}Error: {e}{Style.RESET}\n")
            
    elif command in ("/exit", "/quit"):
        print(f"\n{Style.YEL}Goodbye!{Style.RESET}")
        sys.exit(0)
    else:
        print(f"\n{Style.RED}Unknown command: {command}. Type /help for list.{Style.RESET}\n")

# =============================================================================
#  Main Execution
# =============================================================================

def audio_callback(indata, frames, time, status):
    if status: print(f"Audio: {status}", file=sys.stderr)
    audio_queue.put(bytes(indata))

def main():
    global is_voice_mode
    ensure_directories()
    print_banner()
    
    # ── Step 1: Mode Selection ─────────────────────────────────────────────
    modes = ["🎤  Voice Interaction", "⌨️   Text Interaction"]
    m_idx = select_menu("Select Communication Mode:", modes)
    is_voice_mode = (m_idx == 0)
    
    # ── Step 2: Model Checks & Auto-Download ──────────────────────────────
    print(f"\n{Style.CYN}Checking required models...{Style.RESET}")
    
    try:
        llm_p = ensure_gguf_model()
        v_p = ensure_vosk_model() if is_voice_mode else None
    except Exception as e:
        print(f"{Style.RED}Error downloading models: {e}{Style.RESET}")
        sys.exit(1)
        
    # ── Step 3: Load Models ────────────────────────────────────────────────
    load_llm(str(llm_p))
    if is_voice_mode and v_p:
        load_vosk(str(v_p))
        
    print(f"\n{Style.H_GRN}▶ Ready. Type /help for commands.{Style.RESET}\n")
    
    # ── Step 4: Chat Loop ──────────────────────────────────────────────────
    if not is_voice_mode:
        try:
            while True:
                user_text = input(f"{Style.BOLD}{Style.H_GRN}> You:{Style.RESET} ")
                if not user_text.strip(): continue
                
                if user_text.startswith('/'):
                    handle_command(user_text)
                else:
                    response = process_text(user_text)
                    speak(response)
        except KeyboardInterrupt:
            print(f"\n{Style.YEL}Exiting...{Style.RESET}")
            
    else:
        # Voice Mode loop
        import sounddevice as sd
        print(f"{Style.SYSTEM}Voice streaming active. Speak now...{Style.RESET}\n")
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1, callback=audio_callback):
                while True:
                    data = audio_queue.get()
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text = result.get("text", "")
                        
                        if text:
                            print(f"{Style.BOLD}{Style.H_GRN}> You:{Style.RESET} {text}")
                            if text.startswith('/'):
                                handle_command(text)
                            else:
                                response = process_text(text)
                                speak(response)
                                
                                # clear audio buffer during speaking
                                with audio_queue.mutex:
                                    audio_queue.queue.clear()
        except KeyboardInterrupt:
             print(f"\n{Style.YEL}Exiting...{Style.RESET}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{Style.RED}Fatal Error: {e}{Style.RESET}")
