(function(){
  const bar=document.getElementById("jd-bar"); if(!bar||!window.JARVIS)return;
  const log=document.getElementById("jd-log");
  const say=t=>{const d=document.createElement("div");d.className="jd-msg jd-ai";d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;};
  const inp=document.createElement("input");inp.type="file";inp.accept=".pdf,.md,.txt";inp.style.display="none";
  const b=document.createElement("button");b.className="jd-btn";b.textContent="📚";b.title="Feed Jarvis a book (pdf/md/txt)";
  bar.appendChild(b);document.body.appendChild(inp);
  b.onclick=()=>inp.click();
  inp.onchange=async()=>{
    const f=inp.files[0]; if(!f)return; inp.value="";
    const n=say("Ingesting “"+f.name+"”…");
    const fd=new FormData();fd.append("doc",f,f.name);
    try{const r=await fetch("/api/ingest",{method:"POST",body:fd});const j=await r.json();
      if(j.filed){n.textContent="📚 Filed: "+j.filed+" ("+Math.round(j.chars/1000)+"k chars) — indexed and teachable.";
        JARVIS.ask("A new book was just ingested: "+j.filed.replace("Files/","").replace(".md","")+". Search the vault for it, confirm you can read it, and tell me in one line what it covers.");}
      else n.textContent="✗ "+(j.error||"ingest failed");
    }catch(e){n.textContent="✗ "+e.message;}
  };
})();
