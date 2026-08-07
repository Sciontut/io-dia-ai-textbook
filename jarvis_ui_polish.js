(function(){
  const css=`
  #jd-dock{width:400px !important;max-width:calc(100vw - 32px);}
  #jd-body{height:440px !important;}
  #jd-bar{flex-wrap:wrap !important;gap:8px !important;padding:12px !important;}
  #jd-in{flex:1 1 100% !important;font-size:.92rem !important;padding:11px 13px !important;}
  #jd-bar .jd-btn{flex:1 1 0;min-height:44px;font-size:.95rem;display:flex;align-items:center;
    justify-content:center;gap:6px;padding:0 8px;}
  .jd-btn small{font-size:.6rem;letter-spacing:1px;color:#7a8a72;text-transform:uppercase;}
  #jd-log{font-size:.84rem !important;}
  @media (max-width:900px){#jd-dock{width:calc(100vw - 24px) !important;bottom:8px !important;right:12px !important;}}
  `;
  const st=document.createElement("style");st.textContent=css;document.head.appendChild(st);
  const labels={"jd-mic":"Voice","jd-send":"Send"};
  document.querySelectorAll("#jd-bar .jd-btn").forEach(b=>{
    const t=b.textContent.trim();
    let name=labels[b.id]||({"⏩":"Flow","📚":"Book"})[t]||"";
    if(name&&!b.querySelector("small")){const s=document.createElement("small");s.textContent=name;b.appendChild(s);}
  });
})();
