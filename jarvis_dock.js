/* jarvis_dock.js — the JARVIS cockpit overlay for Workshop OS
   Injected by one <script> tag. Adds: chat panel, push-to-talk, spoken replies,
   status LEDs, and an extensible widget registry (window.JARVIS.registerWidget). */
(function () {
  const css = `
  #jd-dock{position:fixed;bottom:16px;right:16px;width:330px;z-index:50;
    background:rgba(10,15,10,.95);border:1px solid rgba(118,185,0,.35);border-radius:16px;
    backdrop-filter:blur(14px);font-family:'Outfit',sans-serif;color:#d8e4d0;
    display:flex;flex-direction:column;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.5)}
  #jd-head{display:flex;align-items:center;gap:8px;padding:10px 14px;cursor:pointer;
    border-bottom:1px solid rgba(118,185,0,.2)}
  #jd-head b{font-size:.8rem;letter-spacing:2px;color:#9dff00}
  .jd-led{width:8px;height:8px;border-radius:50%;background:#444}
  .jd-led.on{background:#76B900;box-shadow:0 0 6px #76B900}
  .jd-led.err{background:#ff5555}
  #jd-leds{margin-left:auto;display:flex;gap:5px}
  #jd-body{display:flex;flex-direction:column;height:380px}
  #jd-widgets{display:flex;gap:6px;padding:8px 10px 0;flex-wrap:wrap}
  .jd-widget{font-family:'JetBrains Mono',monospace;font-size:.58rem;color:#7a8a72;
    background:rgba(118,185,0,.07);border:1px solid rgba(118,185,0,.18);
    border-radius:8px;padding:4px 8px}
  #jd-log{flex:1;overflow-y:auto;padding:10px 12px;display:flex;flex-direction:column;gap:8px}
  .jd-msg{max-width:88%;padding:8px 11px;border-radius:12px;font-size:.8rem;line-height:1.45}
  .jd-me{align-self:flex-end;background:rgba(118,185,0,.16);border:1px solid rgba(118,185,0,.3)}
  .jd-ai{align-self:flex-start;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}
  .jd-ai.jd-think{opacity:.55;font-style:italic}
  #jd-bar{display:flex;gap:6px;padding:10px;border-top:1px solid rgba(118,185,0,.2)}
  #jd-in{flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(118,185,0,.3);
    border-radius:10px;padding:9px 11px;color:#d8e4d0;font-family:'Outfit';font-size:.82rem}
  #jd-in:focus{outline:none;border-color:#76B900}
  .jd-btn{border:1px solid rgba(118,185,0,.4);background:rgba(118,185,0,.12);color:#9dff00;
    border-radius:10px;padding:0 12px;cursor:pointer;font-size:1rem}
  .jd-btn:hover{background:rgba(118,185,0,.25)}
  #jd-mic.rec{background:#7a1f1f;border-color:#ff5555;color:#ff9999;animation:jdpulse 1s infinite}
  @keyframes jdpulse{50%{opacity:.55}}
  #jd-dock.min #jd-body{display:none}
  ::selection{background:rgba(118,185,0,.4)}`;
  const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  const dock = document.createElement("div");
  dock.id = "jd-dock";
  dock.innerHTML = `
    <div id="jd-head"><span>🌪️</span><b>JARVIS</b>
      <div id="jd-leds">
        <span class="jd-led" id="led-vault" title="vault"></span>
        <span class="jd-led" id="led-brain" title="brain"></span>
        <span class="jd-led" id="led-voice" title="voice"></span>
      </div></div>
    <div id="jd-body">
      <div id="jd-widgets"></div>
      <div id="jd-log"></div>
      <div id="jd-bar">
        <input id="jd-in" placeholder="Speak or type, operator…">
        <button class="jd-btn" id="jd-mic" title="hold to talk">🎤</button>
        <button class="jd-btn" id="jd-send">➤</button>
      </div></div>`;
  document.body.appendChild(dock);

  const log = dock.querySelector("#jd-log"), input = dock.querySelector("#jd-in");
  const micBtn = dock.querySelector("#jd-mic");
  let speakOn = true;

  dock.querySelector("#jd-head").onclick = () => dock.classList.toggle("min");

  function add(cls, text) {
    const d = document.createElement("div");
    d.className = "jd-msg " + cls; d.textContent = text;
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }

  async function ask(text) {
    if (!text.trim()) return;
    add("jd-me", text); input.value = "";
    const think = add("jd-ai jd-think", "…");
    try {
      const r = await fetch("/api/chat", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      const j = await r.json();
      think.remove(); add("jd-ai", j.reply);
      if (speakOn) speak(j.reply);
    } catch (e) { think.textContent = "gateway unreachable — is jarvis_gateway.py running?"; }
  }

  async function speak(text) {
    try {
      const r = await fetch("/api/speak", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 600) }) });
      if (!r.ok) return;
      new Audio(URL.createObjectURL(await r.blob())).play();
    } catch (e) { /* silent */ }
  }

  let rec = null, chunks = [];
  micBtn.onmousedown = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = []; rec = new MediaRecorder(stream);
      rec.ondataavailable = e => chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const fd = new FormData();
        fd.append("audio", new Blob(chunks, { type: "audio/webm" }), "mic.webm");
        const t = add("jd-me", "🎤 …");
        const r = await fetch("/api/transcribe", { method: "POST", body: fd });
        const j = await r.json(); t.remove();
        if (j.text) ask(j.text); else add("jd-ai", "Caught nothing, sir — closer to the mic.");
      };
      rec.start(); micBtn.classList.add("rec");
    } catch (e) { add("jd-ai", "Mic permission denied, operator."); }
  };
  micBtn.onmouseup = () => { if (rec && rec.state === "recording") rec.stop(); micBtn.classList.remove("rec"); };

  dock.querySelector("#jd-send").onclick = () => ask(input.value);
  input.addEventListener("keydown", e => { if (e.key === "Enter") ask(input.value); });

  const widgets = dock.querySelector("#jd-widgets");
  window.JARVIS = {
    ask, speak,
    registerWidget(name, renderFn, everyMs) {
      const el = document.createElement("div");
      el.className = "jd-widget"; widgets.appendChild(el);
      const tick = async () => { try { el.innerHTML = await renderFn(); } catch (e) { el.textContent = name + " ✗"; } };
      tick(); if (everyMs) setInterval(tick, everyMs);
      return el;
    },
  };

  JARVIS.registerWidget("clock", () => new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}), 30000);
  JARVIS.registerWidget("status", async () => {
    const s = await (await fetch("/api/status")).json();
    document.getElementById("led-vault").className = "jd-led " + (s.vault ? "on" : "err");
    document.getElementById("led-brain").className = "jd-led " + (s.brain ? "on" : "err");
    document.getElementById("led-voice").className = "jd-led " + (s.tts_loaded || s.voice ? "on" : "");
    return `disk ${s.disk_free_gb}GB · ${s.brain ? "cloud brain" : "echo"}`;
  }, 20000);
  JARVIS.registerWidget("graph", () => {
    const n = (window.DATA && DATA.nodes) ? DATA.nodes.length : "?";
    const l = (window.DATA && DATA.links) ? DATA.links.length : "?";
    return `🧠 ${n} nodes · ${l} links`;
  });

  add("jd-ai", "Cockpit online, operator. The graph is yours — speak or type.");
})();
