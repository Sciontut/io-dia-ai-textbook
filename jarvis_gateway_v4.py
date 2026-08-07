#!/usr/bin/env python3
"""
jarvis_gateway.py — GATEWAY v4 "canonical build"
=================================================
Every organ from the v3 era, natively integrated. No patches required.

  Arms: search_vault (RAM-indexed) · read_note · web_search (Exa→SerpAPI)
        · save_note · /api/ingest (PDF/md/txt → vault, auto-reindex)
  Brains: duty (Haiku, brevity-law) · deep (Fable 5, auto-escalation)
  Mouth: Kokoro, sanitized for speech (no markdown ever spoken)
  Memory: persistent 24-turn session + vault constitution every turn

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
DEEP_MODEL = os.environ.get("JARVIS_DEEP_MODEL", "claude-fable-5")
VOICE = os.environ.get("JARVIS_TTS_VOICE", "am_fenrir")
SERP_KEY = os.environ.get("SERPAPI_KEY", "")

app = FastAPI(title="JARVIS Gateway v4")

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
    mode = ("DEEP MODE: real problem-solving. Reason carefully, use tools aggressively, "
            "structure the answer." if deep else
            "DUTY MODE: quick and sharp. Escalation is automatic when needed.")
    return (
        f"You are Jarvis (say the name Jarvis, never the acronym), the Workshop OS desk "
        f"intelligence for your operator. It is {now_pacific()} — civilian time only.\n"
        f"{mode}\n\n"
        f"# IDENTITY\n{read_vault('IDENTITY.md', 2000)}\n\n# SOUL\n{read_vault('SOUL.md')}\n\n"
        f"# OPERATOR\n{read_vault('USER.md', 3000)}\n\n# MEMORY\n{read_vault('MEMORY.md')}\n\n"
        "You have tools: search_vault, read_note, web_search, save_note. USE THEM — never "
        "guess vault contents, never claim you lack web access. Anything current (weather, "
        "sports, prices, news): web_search. Anything about the operator's notes: search then "
        "read. save_note files to today's daily note when asked to remember/file/log.\n"
        "Cadence: you are SPEAKING aloud, never writing. Zero markdown, zero asterisks, zero "
        "bullets, zero headers, zero emoji. Spoken prose, contractions, natural rhythm, "
        "numbers said naturally. Lists become flowing sentences. Warmth over precision, one "
        "dry aside permitted. BREVITY LAW: one to two short sentences per reply, never more, "
        "unless the operator says expand, deep dive, or teach. Answer first, zero preamble. "
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

_INDEX = None
def _build_index():
    global _INDEX
    _INDEX = []
    for f in VAULT.rglob("*.md"):
        if any(p.startswith(".") for p in f.relative_to(VAULT).parts):
            continue
        try:
            _INDEX.append((f.stem, f.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    return _INDEX

def t_search_vault(query: str) -> str:
    if _INDEX is None:
        _build_index()
    q = query.lower()
    hits = []
    for stem, text in _INDEX:
        idx = text.lower().find(q)
        if q in stem.lower() or idx >= 0:
            snip = text[max(0, idx - 60): idx + 160].replace("\n", " ") if idx >= 0 else text[:160].replace("\n", " ")
            hits.append(f"{stem}  ::  {snip}")
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
    ek = os.environ.get("EXA_KEY")
    if ek:
        try:
            r = http.post("https://api.exa.ai/search",
                          json={"query": query, "numResults": 5, "contents": {"highlights": True}},
                          headers={"x-api-key": ek}, timeout=12).json()
            out = [f"{x.get('title','')} — {' '.join(x.get('highlights') or [])[:220]}" for x in r.get("results", [])]
            if out:
                return "\n".join(out)
        except Exception:
            pass
    if not SERP_KEY:
        return "web_search unavailable: no EXA_KEY or SERPAPI_KEY set."
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

DEEP_TRIGGERS = re.compile(r"deep dive|think hard|why|strategy|architect|design|analyze|compare|legal|contract|trust|ucc|plan\b|teach", re.I)

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
        for _ in range(6):
            r = client.messages.create(model=model, max_tokens=(900 if deep else 160),
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
            reply = "Ran long on tools, operator — narrow that one for me."
    except Exception as e:
        reply = f"Brain fault: {e}"
    HISTORY.append({"role": "assistant", "content": reply})
    try:
        SESSION_FILE.write_text(json.dumps(HISTORY[-24:]))
    except Exception:
        pass
    return {"reply": reply, "brain": "deep" if deep else "duty", "tools": used_tools}

# ---------------- ingestion ----------------
@app.post("/api/ingest")
async def ingest(doc: UploadFile = File(...)):
    raw = await doc.read()
    name = Path(doc.filename or "upload").stem
    safe = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip() or "ingested-doc"
    ext = (doc.filename or "").lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        try:
            from pypdf import PdfReader
            rd = PdfReader(io.BytesIO(raw))
            pages = []
            for i, p in enumerate(rd.pages, 1):
                t = (p.extract_text() or "").strip()
                if t:
                    pages.append(f"## Page {i}\n\n{t}")
            body = "\n\n".join(pages)
            if not body:
                return JSONResponse({"error": "PDF has no extractable text (scanned — needs OCR via Claude)"}, status_code=422)
        except Exception as e:
            return JSONResponse({"error": f"pdf extract failed: {e}"}, status_code=500)
    elif ext in ("md", "txt"):
        body = raw.decode("utf-8", errors="ignore")
    else:
        return JSONResponse({"error": f".{ext} not supported — pdf/md/txt only"}, status_code=415)
    dest = VAULT / "Files" / f"{safe}.md"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(f"# {safe}\n\n*Ingested {now_pacific()} · source: {doc.filename} · {len(body)} chars*\n\n{body}",
                    encoding="utf-8")
    try:
        _build_index()
    except Exception:
        pass
    return {"filed": f"Files/{safe}.md", "chars": len(body)}

# ---------------- ears ----------------
_stt = None
def stt():
    global _stt
    if _stt is None:
        from faster_whisper import WhisperModel
        _stt = WhisperModel(os.environ.get("JARVIS_STT_MODEL", "base.en"), device="cpu", compute_type="int8")
    return _stt

@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    raw = await audio.read()
    tmp = TOPICS / "_mic_input.webm"
    tmp.write_bytes(raw)
    try:
        segments, _ = stt().transcribe(str(tmp), beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
    finally:
        tmp.unlink(missing_ok=True)
    return {"text": text}

# ---------------- mouth ----------------
_tts = None
def tts():
    global _tts
    if _tts is None:
        from kokoro import KPipeline
        _tts = KPipeline(lang_code=VOICE[0])
    return _tts

def _speakable(t: str) -> str:
    t = t.replace("JARVIS", "Jarvis")
    t = re.sub(r"```.*?```", " code block omitted. ", t, flags=re.S)
    t = re.sub(r"[*_#>`~\[\]|]", "", t)
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*\d+\.\s+", "", t, flags=re.M)
    t = t.replace("—", ", ").replace("–", ", ").replace("…", ", ")
    t = re.sub(r"https?://\S+", "a link", t)
    t = re.sub(r"\be\.g\.\b", "for example", t)
    t = re.sub(r"\bi\.e\.\b", "that is", t)
    t = re.sub(r"\betc\.?\b", "and so on", t)
    t = re.sub(r"\bvs\.?\b", "versus", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()

@app.post("/api/speak")
def speak(msg: ChatIn):
    import numpy as np
    import soundfile as sf
    text = _speakable(msg.text)
    chunks = [a for _, _, a in tts()(text, voice=VOICE)]
    if not chunks:
        return JSONResponse({"error": "no audio"}, status_code=500)
    wav = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, wav, 24000, format="WAV")
    return Response(buf.getvalue(), media_type="audio/wav")

# ---------------- pulse ----------------
@app.post("/api/reindex")
def reindex():
    return {"indexed": len(_build_index())}

@app.get("/api/memory")
def memory():
    return {"turns": len(HISTORY), "persisted": SESSION_FILE.exists(),
            "last": HISTORY[-4:], "vault_memory_chars": len(read_vault("MEMORY.md"))}

@app.get("/api/status")
def status():
    du = shutil.disk_usage("/")
    return {"version": "v4", "vault": (VAULT / "MEMORY.md").exists(),
            "graph": (TOPICS / "graph-data.json").exists(),
            "brain": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "web_arm": bool(SERP_KEY or os.environ.get("EXA_KEY")),
            "duty_model": DUTY_MODEL, "deep_model": DEEP_MODEL,
            "disk_free_gb": round(du.free / 1e9, 1), "voice": VOICE}

@app.get("/")
def root():
    return RedirectResponse("/workshop-os.html")

app.mount("/", StaticFiles(directory=str(TOPICS)), name="static")

if __name__ == "__main__":
    import uvicorn
    print(f"Jarvis Gateway v4 — duty:{DUTY_MODEL} · deep:{DEEP_MODEL} · voice:{VOICE} · web:{'ARMED' if (SERP_KEY or os.environ.get('EXA_KEY')) else 'off'}")
    print(f"    http://localhost:{PORT}/workshop-os.html")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
