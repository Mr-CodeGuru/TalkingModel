import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from llama_cpp import Llama
import pyttsx3
import queue
import sys
import argparse

# -------------------------
# PATHS (YOUR SETUP)
# -------------------------
RECORD_FILE = "/Users/aman/Desktop/Projects/MLTalkingModel/record.txt"

# -------------------------
# CONVERSATIONAL MEMORY
# -------------------------
chat_memory = []
MAX_MEMORY_TURNS = 4  # Remembers the last 4 exchanges without overloading the LLM's 2048 context window

# -------------------------
# TERMINAL UI COLORS
# -------------------------
class Colors:
    USER = '\033[92m'      # Green
    AI = '\033[96m'        # Cyan
    SYSTEM = '\033[95m'    # Magenta
    WARNING = '\033[93m'   # Yellow
    BOLD = '\033[1m'
    END = '\033[0m'

# -------------------------
# ARGUMENT PARSING
# -------------------------
parser = argparse.ArgumentParser(description="TM Engine")
parser.add_argument("--text", action="store_true", help="Run in text-only mode without voice inputs/outputs")
parser.add_argument("--llm_path", type=str, required=True, help="Path to the GGUF LLM model")
parser.add_argument("--vosk_path", type=str, help="Path to the Vosk language model folder")
args = parser.parse_args()

# -------------------------
# LOAD MODELS
# -------------------------
if not args.text:
    print(f"{Colors.SYSTEM}Loading Vosk...{Colors.END}")
    if not args.vosk_path:
        print(f"{Colors.WARNING}Error: --vosk_path is required for Voice Mode!{Colors.END}")
        sys.exit(1)
    vosk_model = Model(args.vosk_path)
    rec = KaldiRecognizer(vosk_model, 16000)

print(f"{Colors.SYSTEM}Loading LLM...{Colors.END}")
llm = Llama(
    model_path=args.llm_path,
    n_ctx=2048,
    n_threads=6,      # good for M-series
    verbose=False
)

if not args.text:
    print(f"{Colors.SYSTEM}Initializing TTS...{Colors.END}")
    engine = pyttsx3.init()
    engine.setProperty('rate', 170)

# -------------------------
# FUNCTIONS
# -------------------------
import shlex
import subprocess

def speak(text):
    print(f"{Colors.BOLD}{Colors.AI}> TM-ENGINE:{Colors.END} {text}")
    if args.text:
        return
    if sys.platform == "darwin":
        # pyttsx3 natively fails to block/speak on macOS Python 3.11+ without a complex AppKit event loop.
        # The built-in native 'say' command is identical, offline, perfectly blocking, and 100% reliable.
        subprocess.run(["say", "-r", "170", text])
    else:
        engine.say(text)
        engine.runAndWait()

def process_text(user_text):
    global chat_memory
    
    # A strong "System Prompt" forces the 1B model into AI format instead of text-predicting a forum
    system_prompt = (
        "You are TM Engine, a highly advanced AI voice assistant. "
        "You are helpful, smart, and concise. "
        "Never pretend to be a human. Always give direct, accurate answers."
    )
    
    # Format the prompt strictly to include historical context
    prompt = f"System: {system_prompt}\n"
    for memory_u, memory_a in chat_memory:
        prompt += f"User: {memory_u}\nAssistant: {memory_a}\n"
        
    prompt += f"User: {user_text}\nAssistant:"
    
    output = llm(
        prompt,
        max_tokens=300, # A safe length for voice responses
        stop=["User:", "\nUser", "System:"], # Removed '\n' so it can speak multiple sentences
        echo=False
    )
    
    response = output["choices"][0]["text"].strip()
    
    # Save the exchange to conversational memory
    chat_memory.append((user_text, response))
    if len(chat_memory) > MAX_MEMORY_TURNS:
        chat_memory.pop(0)
        
    # Append to the persistent log record
    with open(RECORD_FILE, "a", encoding="utf-8") as f:
        f.write(f"🧑: {user_text}\n🤖: {response}\n")
        
    return response

# -------------------------
# AUDIO STREAMING QUEUE
# -------------------------
audio_queue = queue.Queue()

def callback(indata, frames, time, status):
    """
    Called from a separate thread by SoundDevice for each audio block.
    Must be extremely fast and non-blocking.
    """
    if status:
        print(f"⚠️ Audio status: {status}", file=sys.stderr)
        
    # Convert CFFI buffer to raw Python bytes safely without NumPy
    audio_queue.put(bytes(indata))

# -------------------------
# START ENGINE
# -------------------------
if args.text:
    print(f"\n{Colors.BOLD}{Colors.SYSTEM}▶ TM Engine Ready... Type your prompt below ◀{Colors.END}\n")
    print(f"{Colors.SYSTEM}Press Ctrl+C to stop...{Colors.END}\n")
    try:
        while True:
            text = input(f"{Colors.BOLD}{Colors.USER}> YOU:{Colors.END} ")
            if text.strip():
                response = process_text(text)
                speak(response)
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}🛑 Stopping Engine...{Colors.END}")
        with open(RECORD_FILE, "a", encoding="utf-8") as f:
            f.write("------\n")
    except Exception as e:
        print(f"\n{Colors.WARNING}❌ Pipeline Error: {e}{Colors.END}")
else:
    print(f"\n{Colors.BOLD}{Colors.SYSTEM}▶ TM Engine Ready... Speak now ◀{Colors.END}\n")
    print(f"{Colors.SYSTEM}Press Ctrl+C to stop...{Colors.END}\n")

    try:
        with sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=callback
        ):
            while True:
                # Process audio chunks from the queue
                data = audio_queue.get()
                
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")

                    if text:
                        print(f"{Colors.BOLD}{Colors.USER}> YOU:{Colors.END} {text}")
                        
                        # 1. Process LLM
                        response = process_text(text)
                        
                        # 2. Speak the response (running on main thread avoids macOS AppKit crashes)
                        speak(response)
                        
                        # 3. Discard audio captured while the assistant was thinking & speaking.
                        with audio_queue.mutex:
                            audio_queue.queue.clear()
                            
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}🛑 Stopping Engine...{Colors.END}")
        with open(RECORD_FILE, "a", encoding="utf-8") as f:
            f.write("------\n")
    except Exception as e:
        print(f"\n{Colors.WARNING}❌ Pipeline Error: {e}{Colors.END}")