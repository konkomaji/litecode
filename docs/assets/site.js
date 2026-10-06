(function(){
  var root=document.documentElement,btn=document.getElementById("theme");
  function get(){try{return localStorage.getItem("lc-theme")}catch(e){return null}}
  function set(v){try{localStorage.setItem("lc-theme",v)}catch(e){}}
  var t=get(); if(t) root.setAttribute("data-theme",t);
  if(btn) btn.addEventListener("click",function(){
    var cur=root.getAttribute("data-theme");
    var dark=cur==="dark"||(!cur&&window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches);
    var n=dark?"light":"dark"; root.setAttribute("data-theme",n); set(n);
  });
  var mb=document.querySelector(".menu-btn"),side=document.querySelector(".side");
  if(mb&&side) mb.addEventListener("click",function(){side.classList.toggle("open");mb.setAttribute("aria-expanded",side.classList.contains("open"))});
  document.querySelectorAll("pre").forEach(function(pre){
    if(pre.closest(".term")) return;
    var host=pre.parentNode.classList.contains("code")?pre.parentNode:pre;
    if(host.querySelector(".copy")) { bind(host.querySelector(".copy"),pre); return; }
    var b=document.createElement("button"); b.className="copy"; b.type="button"; b.textContent="copy";
    host.appendChild(b); bind(b,pre);
  });
  function bind(b,pre){b.addEventListener("click",function(){
    var txt=(pre.querySelector("code")||pre).innerText;
    if(navigator.clipboard) navigator.clipboard.writeText(txt).then(function(){b.textContent="copied";setTimeout(function(){b.textContent="copy"},1500)});
  });}
})();
