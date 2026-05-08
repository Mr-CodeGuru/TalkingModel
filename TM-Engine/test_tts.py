import pyttsx3
import time
print("Init")
engine = pyttsx3.init()
print("Saying")
engine.say("Testing 1 2 3")
print("Waiting")
engine.runAndWait()
print("Done")
