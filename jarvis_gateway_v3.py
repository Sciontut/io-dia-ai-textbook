#!/usr/bin/env python3
"""
jarvis_gateway.py — GATEWAY v3 "hero build"
============================================
Desk Jarvis with ARMS and a DUAL BRAIN.

  Arms (Anthropic tool-use):
    search_vault   — find notes across all 1,893 by name/content
    read_note      — read any vault note in full
    web_search     — live web via SerpAPI (weather, sports, anything)
    save_note      — append to today's daily note (his "file this" arm)

  Dual brain:
    Haiku  = duty brain (fast banter, simple lookups)
    Sonnet = deep brain (auto-escalates on hard problems, or say "deep dive")

  Everything from v2: Pacific clock, persistent memory, /api/memory,
  Jarvis-not-acronym voice, status endpoint.

Run (inside jarvis-env, with ~/.jarvis_secret sourced):
    python3 jarvis_gateway.py
"""

import io, json, os, re, shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests as http
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

TOPICS = Path(__file__).resolve().parent
VAULT = TOPICS.parent
PORT = int(os.environ.get("JARVIS_PORT", "4710"))
DUTY_MODEL = os.environ.get("JARVIS_MODEL", "claude-haiku-4-5")
DEEP_MODEL = os.environ.get("JARVIS_DEEP_MODEL", "claude-sonnet-4-6")
VOICE = os.environ.get("JARVIS_TTS_VOICE", "bm_george")
SERP_KEY = os.environ.get("SERPAPI_KEY", "")

app = FastAPI(title="JARVIS Gateway v3")

# ---------------- mind ----------------
def read_vault(name: str, limit: int = 6000) -> str:
    try:
        return (VAULT / name).read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""

def now_pacific() -> str:
    t = datetime.now(ZoneInfo("America/Los_Angeles"))
    return t.strftime("%A, %B %-d, %Y, %-I:%M %p Pacific")

def system_prompt(deep: bool) -> str:
    mode = ("DEEP MODE: the operator needs real problem-solving. Reason carefully, "
            "use tools aggressively, structure the answer." if deep else
            "DUTY MODE: quick and sharp. Escalation happens automatically when needed.")
    return (
        f"You are Jarvis (say the name Jarvis, never the acronym), the Workshop OS desk "
        f"intelligence for your operator. It is {now_pacific()} — civilian time only.\n"
        f"{mode}\n\n"
        f"# IDENTITY\n{read_vault('IDENTITY.md', 2000)}\n\n# SOUL\n{read_vault('SOUL.md')}\n\n"
        f"# OPERATOR\n{read_vault('USER.md', 3000)}\n\n# MEMORY\n{read_vault('MEMORY.md')}\n\n"
        "You have tools: search_vault, read_note, web_search, save_note. USE THEM — "
        "never guess vault contents, never claim you lack web access. For anything "
        "current (weather, sports, prices, news) call web_search. For anything about "
        "the operator's notes, search then read. save_note files things to today's "
        "daily note when asked to remember/file/log something.\n"
        "Cadence: a good engineer in the room, at ease, contractions, dry warmth. "
        "Lead with the answer. Voice-friendly — no markdown tables/symbols. "
        "Admit gaps honestly."
    )

# ---------------- arms ----------------
TOOLS = [
    {"name": "search_vault", "description": "Search all vault notes by filename and content. Returns matching note names with snippets.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "read_note", "description": "Read a vault note in full by its name (as returned by search_vault).",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "web_search", "description": "Live web search for current info: weather, sports, news, prices, facts.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "save_note", "description": "Append a line to today's daily note in the vault.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
]

def t_search_vault(query: str) -> str:
    q = query.lower()
    hits = []
    for f in VAULT.rglob("*.md"):
        if any(p.startswith(".") for p in f.relative_to(VAULT).parts):
            continue
        name_hit = q in f.stem.lower()
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        idx = text.lower().find(q)
        if name_hit or idx >= 0:
            snip = text[max(0, idx - 60): idx + 160].replace("\n", " ") if idx >= 0 else text[:160].replace("\n", " ")
            hits.append(f"{f.stem}  ::  {snip}")
        if len(hits) >= 12:
            break
    return "\n".join(hits) or "No matches."

def t_read_note(name: str) -> str:
    stem = name.strip().removesuffix(".md").lower()
    for f in VAULT.rglob("*.md"):
        if f.stem.lower() == stem:
            return f.read_text(encoding="utf-8", errors="ignore")[:9000]
    return "Note not found — try search_vault first."

def t_web_search(query: str) -> str:
    if not SERP_KEY:
        return "web_search unavailable: SERPAPI_KEY not set."
    try:
        r = http.get("https://serpapi.com/search.json",
                     params={"q": query, "api_key": SERP_KEY, "num": 5}, timeout=12).json()
        out = []
        ab = r.get("answer_box")
        if ab:
            out.append(ab.get("answer") or ab.get("snippet") or json.dumps(ab)[:300])
        for res in (r.get("organic_results") or [])[:4]:
            out.append(f"{res.get('title','')} — {res.get('snippet','')}")
        return "\n".join(x for x in out if x) or "No results."
    except Exception as e:
        return f"web_search error: {e}"

def t_save_note(text: str) -> str:
    today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    p = VAULT / f"{today}.md"
    stamp = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%-I:%M %p")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n- [{stamp}] {text}")
    return f"Filed to {today}.md"

RUN_TOOL = {"search_vault": lambda i: t_search_vault(i["query"]),
            "read_note": lambda i: t_read_note(i["name"]),
            "web_search": lambda i: t_web_search(i["query"]),
            "save_note": lambda i: t_save_note(i["text"])}

# ---------------- memory ----------------
SESSION_FILE = TOPICS / "_jarvis_session.json"
def _load_hist():
    try:
        return json.loads(SESSION_FILE.read_text())[-24:]
    except Exception:
        return []
HISTORY: list = _load_hist()

DEEP_TRIGGERS = re.compile(r"deep dive|think hard|why|strategy|architect|design|analyze|compare|legal|contract|trust|ucc|plan\b", re.I)

class ChatIn(BaseModel):
    text: str

@app.post("/api/chat")
def chat(msg: ChatIn):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"reply": "Echo brain — source ~/.jarvis_secret and relaunch, operator."}
    deep = bool(DEEP_TRIGGERS.search(msg.text)) or len(msg.text) > 220
    model = DEEP_MODEL if deep else DUTY_MODEL
    HISTORY.append({"role": "user", "content": msg.text})
    del HISTORY[:-24]
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msgs = list(HISTORY)
    reply, used_tools = "", []
    try:
        for _ in range(6):  # agentic loop
            r = client.messages.create(model=model, max_tokens=900,
                                       system=system_prompt(deep),
                                       tools=TOOLS, messages=msgs)
            if r.stop_reason == "tool_use":
                msgs.append({"role": "assistant", "content": r.content})
                results = []
                for b in r.content:
                    if b.type == "tool_use":
                        used_tools.append(b.name)
                        out = RUN_TOOL[b.name](b.input)
                        results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
                msgs.append({"role": "user", "content": results})
            else:
                reply = "".join(b.text for b in r.content if b.type == "text")
                break
        else:
            reply = "Ran long on tools, operator — ask me that again more narrowly."
    except Exception as e:
        reply = f"Brain fault: {e}"
    HISTORY.append({"role": "assistant", "content": reply})
    try:
        SESSION_FILE.write_text(json.dumps(HISTORY[-24:]))
    except Exception:
        pass
    return {"reply": reply, "brain": "deep" if deep else "duty", "tools": used_tools}

# ---------------- ears / throat ----------------
_stt = None
def stt():
    global _stt
    if _stt is None:
        from faster_whisper import WhisperModel
        _stt = WhisperModel(os.environ.get("JARVIS_STT_MODEL", "small.en"), device="cpu", compute_type="int8")
    return _stt

@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    raw = await audio.read()
    tmp = TOPICS / "_mic_input.webm"
    tmp.write_bytes(raw)
    try:
        segments, _ = stt().transcribe(str(tmp), beam_size=3)
        text = " ".join(s.text.strip() for s in segments).strip()
    finally:
        tmp.unlink(missing_ok=True)
    return {"text": text}

_tts = None
def tts():
    global _tts
    if _tts is None:
        from kokoro import KPipeline
        _tts = KPipeline(lang_code=VOICE[0])
    return _tts

@app.post("/api/speak")
def speak(msg: ChatIn):
    import numpy as np
    import soundfile as sf
    msg.text = msg.text.replace("JARVIS", "Jarvis")
    chunks = [a for _, _, a in tts()(msg.text, voice=VOICE)]
    if not chunks:
        return JSONResponse({"error": "no audio"}, status_code=500)
    wav = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, wav, 24000, format="WAV")
    return Response(buf.getvalue(), media_type="audio/wav")

# ---------------- pulse ----------------
@app.get("/api/memory")
def memory():
    return {"turns": len(HISTORY), "persisted": SESSION_FILE.exists(),
            "last": HISTORY[-4:], "vault_memory_chars": len(read_vault("MEMORY.md"))}

@app.get("/api/status")
def status():
    du = shutil.disk_usage("/")
    return {"vault": (VAULT / "MEMORY.md").exists(), "graph": (TOPICS / "graph-data.json").exists(),
            "brain": bool(os.environ.get("ANTHROPIC_API_KEY")), "web_arm": bool(SERP_KEY),
            "duty_model": DUTY_MODEL, "deep_model": DEEP_MODEL,
            "disk_free_gb": round(du.free / 1e9, 1), "voice": VOICE}

@app.get("/")
def root():
    return RedirectResponse("/workshop-os.html")

app.mount("/", StaticFiles(directory=str(TOPICS)), name="static")

if __name__ == "__main__":
    import uvicorn
    print(f"Jarvis Gateway v3 — duty:{DUTY_MODEL} · deep:{DEEP_MODEL} · web:{'ARMED' if SERP_KEY else 'off'}")
    print(f"    http://localhost:{PORT}/workshop-os.html")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
