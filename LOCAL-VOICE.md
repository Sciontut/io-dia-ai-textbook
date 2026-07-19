# 🎙 LOCAL-VOICE.md
## The 100% Local Voice Stack — faster-whisper + Kokoro → JARVIS

*Harvested from the repos on the slide: `SYSTRAN/faster-whisper` (23.6k★, STT) and `hexgrad/kokoro` (7.5k★, TTS). READMEs pulled 2026-07-18.*

## Why this is the right upgrade

Mission Control's current voice loop uses the browser's Web Speech API — which works, but Chrome's speech recognition ships your audio to Google's servers, and quality/voices vary by browser. This stack replaces both ends with local models:

```
CURRENT:  Mic → Chrome ASR (cloud) → Brain → speechSynthesis (OS voices)
UPGRADE:  Mic → faster-whisper (local) → Brain → Kokoro (local) → speakers
```

Responsive, private, essentially free — speech never leaves the machine. Only the Brain call is remote, and even that goes local once the DGX Spark lands. This is IO DIA **Chapter 15 implemented for real**, and it checks the "Multimodal & speech pipelines" box on the Senior AI Solutions career matrix.

## What the repos actually are

**`SYSTRAN/faster-whisper`** — OpenAI's Whisper reimplemented on CTranslate2, a fast Transformer inference engine. Key facts from the README:
- Python 3.9+, **no system FFmpeg needed** (PyAV bundles it)
- `pip install faster-whisper` — that's the whole install on CPU
- Model sizes: `tiny.en` → `small.en` (CPU sweet spot) → `large-v3` / `turbo` (GPU class)
- CPU runs use `compute_type="int8"`; GPU uses `"float16"` — quantization tradeoffs straight out of IO DIA Chapter 17
- GPU path needs cuBLAS + cuDNN 9 for CUDA 12 (or the official `nvidia/cuda:12.3.2-cudnn9-runtime` Docker image) — i.e., the DGX Spark's native habitat
- `segments` is a **generator** — transcription only runs when you iterate it (classic gotcha)
- `BatchedInferencePipeline` is a drop-in for batch throughput on GPU

**`hexgrad/kokoro`** — an 82M-parameter open-weight TTS model, Apache-licensed, quality comparable to much larger models while significantly faster and cheaper. Key facts:
- `pip install "kokoro>=0.9.4" soundfile` + **espeak-ng** system package (G2P fallback)
- 24kHz output, streaming generator API: `pipeline(text, voice=...)` yields audio chunks
- 8 languages; voices per language — including **British English (`lang_code='b'`) with male voices like `bm_george`** — the butler register, made for JARVIS
- Apple Silicon: `PYTORCH_ENABLE_MPS_FALLBACK=1` enables GPU acceleration on the M-series Macs
- Uses `misaki` for grapheme-to-phoneme; `[Kokoro](/kˈOkəɹO/)` syntax allows inline pronunciation control

## Install (macOS, your MacBook)

```bash
brew install espeak-ng portaudio
pip install faster-whisper "kokoro>=0.9.4" soundfile sounddevice numpy anthropic
```

Run the loop:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 python jarvis_voice_local.py                    # echo brain
ANTHROPIC_API_KEY=sk-ant-... PYTORCH_ENABLE_MPS_FALLBACK=1 python jarvis_voice_local.py  # real brain
```

`jarvis_voice_local.py` (in this repo) implements: Enter-to-talk → records until 1.2s of silence → `small.en` int8 transcription with VAD filtering → Claude (or echo) → `bm_george` speaks the reply. SOUL.md's voice rules are baked into the system prompt.

## Tuning knobs

| Env var | Default | Notes |
|---------|---------|-------|
| `JARVIS_STT_MODEL` | `small.en` | `tiny.en` for speed, `turbo`/`large-v3` on GPU |
| `JARVIS_STT_DEVICE` | `cpu` | `cuda` on the Spark / Kristie's rig |
| `JARVIS_TTS_VOICE` | `bm_george` | try `bm_lewis`, or `af_heart` (American) |

## The growth path

1. **Now (Mac, CPU):** `small.en` int8 + Kokoro on MPS — fully usable latency for study sessions
2. **Phase 2 (gateway):** wrap STT/TTS behind FastAPI WebSocket endpoints (`/voice/transcribe`, `/voice/speak`) so Mission Control's browser UI streams audio to the local gateway instead of using Web Speech API — same UI, upgraded engine, matches the OpenClaw gateway pattern from the teardown
3. **Phase 3 (DGX Spark):** `device="cuda"`, `large-v3` or `turbo` + `BatchedInferencePipeline` — server-class transcription; Kokoro is so light it barely registers
4. **Wake word later:** the OpenClaw docs mention Voice Wake on-device; openWakeWord or Porcupine slots in front of `record_utterance()` when you want "Hey JARVIS" instead of Enter-to-talk

*Filed under Learning Bridge R&D · the voice becomes sovereign.*
