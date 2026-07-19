#!/usr/bin/env python3
"""
jarvis_voice_local.py — 100% local voice loop for JARVIS
========================================================
Mic in → faster-whisper (STT, local) → Brain → Kokoro (TTS, local) → speakers

The upgrade path from the browser Web Speech API in Mission Control:
same ASR → Brain → TTS architecture (IO DIA Chapter 15), zero cloud audio.
Speech never leaves the machine. Only the Brain call is remote — and even
that goes local once the DGX Spark arrives.

Setup (macOS):
    brew install espeak-ng portaudio
    pip install faster-whisper "kokoro>=0.9.4" soundfile sounddevice numpy anthropic

Run:
    PYTORCH_ENABLE_MPS_FALLBACK=1 python jarvis_voice_local.py
    # Optional cloud brain:
    ANTHROPIC_API_KEY=sk-ant-... PYTORCH_ENABLE_MPS_FALLBACK=1 python jarvis_voice_local.py

Controls: press Enter to talk, speak, it auto-stops on silence. Ctrl+C to exit.
"""

import os
import queue
import sys
import time

import numpy as np
import sounddevice as sd

# ----------------------------- Config ---------------------------------------
SAMPLE_RATE = 16_000          # faster-whisper expects 16kHz mono
SILENCE_THRESHOLD = 0.012     # RMS below this counts as silence
SILENCE_SECONDS = 1.2         # stop recording after this much silence
MAX_UTTERANCE_SECONDS = 30

WHISPER_MODEL = os.environ.get("JARVIS_STT_MODEL", "small.en")
# CPU-friendly default. Options: tiny.en (fastest) → small.en (sweet spot)
# → large-v3 / turbo when running on DGX Spark with device="cuda".
WHISPER_DEVICE = os.environ.get("JARVIS_STT_DEVICE", "cpu")
WHISPER_COMPUTE = "int8" if WHISPER_DEVICE == "cpu" else "float16"

KOKORO_LANG = "b"             # 'b' = British English — the butler register
KOKORO_VOICE = os.environ.get("JARVIS_TTS_VOICE", "bm_george")
KOKORO_RATE = 24_000          # Kokoro outputs 24kHz audio

SOUL = (
    "You are JARVIS: calm, precise, lightly witty — British-butler-meets-"
    "flight-engineer. Replies are spoken aloud: 2-5 sentences, no markdown, "
    "no emojis. Just answer; have a take; cite the IO DIA chapter when teaching."
)

# ----------------------------- Models ---------------------------------------
print("◉ Loading faster-whisper (%s, %s/%s)..." % (WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE))
from faster_whisper import WhisperModel
stt = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)

print("◉ Loading Kokoro TTS (voice=%s)..." % KOKORO_VOICE)
from kokoro import KPipeline
tts = KPipeline(lang_code=KOKORO_LANG)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
claude = None
if ANTHROPIC_KEY:
    try:
        from anthropic import Anthropic
        claude = Anthropic(api_key=ANTHROPIC_KEY)
        print("◉ Cloud Brain armed (claude-sonnet-4-6)")
    except ImportError:
        print("⚠ anthropic package missing — falling back to echo brain")
if claude is None:
    print("◉ Local echo brain (set ANTHROPIC_API_KEY for real reasoning)")

history = []

# ----------------------------- Audio in -------------------------------------
def record_utterance() -> np.ndarray:
    """Record from the default mic until sustained silence."""
    q: "queue.Queue[np.ndarray]" = queue.Queue()

    def cb(indata, frames, t, status):
        q.put(indata.copy())

    chunks, silent_for, started = [], 0.0, time.time()
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=cb):
        print("🎤 listening… (speak now)")
        while True:
            chunk = q.get()
            chunks.append(chunk)
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            dur = len(chunk) / SAMPLE_RATE
            silent_for = silent_for + dur if rms < SILENCE_THRESHOLD else 0.0
            if silent_for >= SILENCE_SECONDS and len(chunks) > 8:
                break
            if time.time() - started > MAX_UTTERANCE_SECONDS:
                break
    return np.concatenate(chunks).flatten()

# ----------------------------- Pipeline stages -------------------------------
def transcribe(audio: np.ndarray) -> str:
    segments, info = stt.transcribe(audio, beam_size=5, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    return text

def think(text: str) -> str:
    if claude is None:
        return "Echo brain online. You said: %s. Arm the cloud brain for real answers." % text
    history.append({"role": "user", "content": text})
    msg = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SOUL,
        messages=history[-10:],
    )
    reply = "".join(b.text for b in msg.content if b.type == "text").strip()
    history.append({"role": "assistant", "content": reply})
    return reply

def speak(text: str) -> None:
    for _, _, audio in tts(text, voice=KOKORO_VOICE, speed=1.0):
        sd.play(audio, KOKORO_RATE)
        sd.wait()

# ----------------------------- Main loop -------------------------------------
def main() -> None:
    print("\n🌪️  JARVIS local voice loop — Enter to talk, Ctrl+C to exit.\n")
    speak("Local voice loop online. Speech stays on this machine, operator.")
    while True:
        try:
            input("⏎  press Enter, then speak: ")
            audio = record_utterance()
            heard = transcribe(audio)
            if not heard:
                print("… heard nothing.")
                continue
            print("🗣  you: %s" % heard)
            reply = think(heard)
            print("🤖 jarvis: %s" % reply)
            speak(reply)
        except KeyboardInterrupt:
            print("\n◉ Voice loop offline.")
            sys.exit(0)

if __name__ == "__main__":
    main()
