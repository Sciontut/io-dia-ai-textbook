(function(){
  const old=document.getElementById("jd-mic"); if(!old||!window.JARVIS)return;
  const btn=old.cloneNode(true); old.replaceWith(btn);
  const log=document.getElementById("jd-log");
  const say=(c,t)=>{const d=document.createElement("div");d.className="jd-msg "+c;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;};
  const SIL=()=>parseInt(localStorage.jd_sil||"1000"), MIN_VOICED=300, PRE=3;
  const mime=["audio/mp4","audio/webm;codecs=opus","audio/webm",""].find(m=>!m||MediaRecorder.isTypeSupported(m));
  let stream,ctx,an,buf,rec,ring=[],mark=-1;
  let live=false,talking=false,sil0=0,v0=0,busy=false,TH=0.012;
  async function arm(){
    if(stream)return true;
    const n=say("jd-ai","Arming and calibrating to your room…");
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      ctx=new (window.AudioContext||window.webkitAudioContext)();
      an=ctx.createAnalyser();an.fftSize=2048;buf=new Float32Array(an.fftSize);
      ctx.createMediaStreamSource(stream).connect(an);
      rec=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);
      rec.ondataavailable=e=>{if(!e.data.size)return;ring.push(e.data);if(mark<0&&ring.length>PRE)ring.shift();};
      rec.start(250);
      let amb=0,n2=0;const t0=Date.now();
      await new Promise(res=>{const c=()=>{an.getFloatTimeDomainData(buf);
        let s=0;for(let i=0;i<buf.length;i++)s+=buf[i]*buf[i];
        amb+=Math.sqrt(s/buf.length);n2++;
        if(Date.now()-t0<900)requestAnimationFrame(c);else res();};c();});
      const ambient=amb/Math.max(n2,1);
      TH=Math.max(0.006, ambient*2.6);
      if(localStorage.jd_vad)TH=parseFloat(localStorage.jd_vad);
      n.textContent="Calibrated — ambient "+ambient.toFixed(4)+", trigger "+TH.toFixed(4)+". Speak naturally; I keep a pre-buffer so first words are never lost.";
      return true;
    }catch(e){n.textContent="Mic blocked: "+e.name;return false;}
  }
  async function pipe(blob){
    busy=true;
    const fd=new FormData();fd.append("audio",blob,"u."+((mime||"").includes("mp4")?"m4a":"webm"));
    const th=say("jd-ai jd-think","…");
    try{const tr=await(await fetch("/api/transcribe",{method:"POST",body:fd})).json();
      if(!tr.text){th.remove();busy=false;return;}
      th.textContent="…";say("jd-me",tr.text);
      const ch=await(await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:tr.text})})).json();
      th.remove();say("jd-ai",(ch.brain==="deep"?"🧠 ":"")+ch.reply);
      const sp=await fetch("/api/speak",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:ch.reply.slice(0,280)})});
      if(sp.ok){const a=new Audio(URL.createObjectURL(await sp.blob()));await new Promise(r=>{a.onended=r;a.onerror=r;a.play();});}
    }catch(e){th.remove();say("jd-ai","fault: "+e.message);}
    busy=false;
  }
  function commit(){
    const take=ring.slice(Math.max(0,mark-PRE));mark=-1;ring=ring.slice(-PRE);
    if(take.length)pipe(new Blob(take,{type:mime||"audio/webm"}));
  }
  function loop(){
    if(!live)return;
    an.getFloatTimeDomainData(buf);
    let s=0;for(let i=0;i<buf.length;i++)s+=buf[i]*buf[i];
    const rms=Math.sqrt(s/buf.length),now=Date.now();
    if(!busy){
      if(!talking&&rms>TH){talking=true;v0=now;sil0=0;mark=ring.length;btn.textContent="🔴";}
      else if(talking){
        if(rms>TH)sil0=0;else{if(!sil0)sil0=now;
          if(now-sil0>SIL()){talking=false;btn.textContent="🟢";
            if(now-v0>MIN_VOICED+SIL())commit();else{mark=-1;ring=ring.slice(-PRE);}}}
      }
    }
    requestAnimationFrame(loop);
  }
  btn.onclick=async()=>{
    if(!await arm())return;
    if(ctx.state==="suspended")await ctx.resume();
    live=!live;
    if(live){btn.textContent="🟢";btn.classList.add("rec");say("jd-ai","Channel open — just talk.");loop();}
    else{btn.textContent="🎤";btn.classList.remove("rec");if(talking){talking=false;try{rec.stop()}catch(e){}}say("jd-ai","Channel closed.");}
  };
})();
