"""
scripts/test_tts.py — Quick TTS smoke test.

Usage:
    python scripts/test_tts.py

Tests that text-to-speech is working correctly on your system.
"""

import sys
import platform

print(f"Platform: {platform.system()} {platform.release()}")
print(f"Python:   {sys.version}")

if platform.system() == "darwin":
    import subprocess
    print("Testing macOS native 'say' command…")
    result = subprocess.run(["say", "-r", "170", "TTS test successful"], check=False)
    if result.returncode == 0:
        print("✅  macOS 'say' TTS working.")
    else:
        print("❌  macOS 'say' failed.")
else:
    import pyttsx3
    print("Testing pyttsx3…")
    engine = pyttsx3.init()
    engine.setProperty("rate", 170)
    engine.say("TTS test successful")
    engine.runAndWait()
    print("✅  pyttsx3 TTS working.")
