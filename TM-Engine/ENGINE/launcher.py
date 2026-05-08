import os
import sys
import tty
import termios
import subprocess

# Define Paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GGUF_DIR = os.path.join(PROJECT_ROOT, "TM-GGUF")
ENGINE_DIR = os.path.join(PROJECT_ROOT, "TM-Engine", "ENGINE")
MAIN_SCRIPT = os.path.join(ENGINE_DIR, "main.py")

Colors_USER = '\033[92m'
Colors_AI = '\033[96m'
Colors_BOLD = '\033[1m'
Colors_END = '\033[0m'

def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def select_menu(prompt, options):
    selected = 0
    print(f"\n{Colors_BOLD}{Colors_AI}{prompt}{Colors_END}")
    for _ in options:
        print()
    
    while True:
        sys.stdout.write(f"\033[{len(options)}A")
        for i, opt in enumerate(options):
            if i == selected:
                sys.stdout.write(f"{Colors_USER} > {opt} {Colors_END}\033[K\r\n")
            else:
                sys.stdout.write(f"   {opt} \033[K\r\n")
        
        ch = getch()
        if ch == '\x1b[A': # Up
            selected = max(0, selected - 1)
        elif ch == '\x1b[B': # Down
            selected = min(len(options) - 1, selected + 1)
        elif ch in ('\r', '\n', '\x03', '\x04'): # Enter, Ctrl+C, Ctrl+D
            break
            
    if ch in ('\x03', '\x04'):
        print("\nAborted.")
        sys.exit(0)
    
    return selected

def main():
    os.system('clear')
    print(f"{Colors_BOLD}=== MLTalkingModel Launcher ==={Colors_END}")
    
    # Mode selection
    modes = ["VOICE Interaction", "TEXT Interaction"]
    m_idx = select_menu("Select Interaction Mode (Up/Down + Enter):", modes)
    is_text = (m_idx == 1)
    
    # Discover GGUF Models
    gguf_files = [f for f in os.listdir(GGUF_DIR) if f.endswith(".gguf")]
    if not gguf_files:
        print("Error: No .gguf models found in TM-GGUF!")
        sys.exit(1)
        
    model_idx = select_menu("Select LLM Model:", gguf_files)
    selected_llm = os.path.join(GGUF_DIR, gguf_files[model_idx])
    
    # Discover Vosk Languages (Only if VOICE mode)
    selected_vosk = None
    if not is_text:
        vosk_dirs = [d for d in os.listdir(ENGINE_DIR) if d.startswith("vosk-model-") and os.path.isdir(os.path.join(ENGINE_DIR, d))]
        if not vosk_dirs:
            print("Error: No vosk-model-* directories found in ENGINE!")
            sys.exit(1)
            
        vosk_idx = select_menu("Select Language Model (Vosk):", vosk_dirs)
        selected_vosk = os.path.join(ENGINE_DIR, vosk_dirs[vosk_idx])
        
    # Build command
    cmd = ["python3", MAIN_SCRIPT, "--llm_path", selected_llm]
    if is_text:
        cmd.append("--text")
    else:
        cmd.extend(["--vosk_path", selected_vosk])
        
    os.system('clear')
    print(f"{Colors_AI}Launching Engine...{Colors_END}\n")
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass
        
if __name__ == "__main__":
    main()
