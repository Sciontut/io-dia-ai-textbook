(function(){
  const input=document.getElementById("jd-in"); if(!input||!window.JARVIS)return;
  const bar=document.getElementById("jd-bar");
  const b=document.createElement("button"); b.className="jd-btn"; b.textContent="⏩"; b.title="Flow Mode: auto-send after dictation pause";
  bar.appendChild(b);
  let on=false,timer=null;
  b.onclick=()=>{on=!on;b.style.background=on?"rgba(118,185,0,.4)":"";
    const l=document.getElementById("jd-log"),d=document.createElement("div");
    d.className="jd-msg jd-ai";d.textContent=on?"Flow Mode on — dictate into the box; I'll take it from silence.":"Flow Mode off.";
    l.appendChild(d);l.scrollTop=l.scrollHeight;};
  input.addEventListener("input",()=>{ if(!on)return; clearTimeout(timer);
    if(input.value.trim().length>2) timer=setTimeout(()=>{JARVIS.ask(input.value);},1200); });
})();
