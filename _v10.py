# -*- coding: utf-8 -*-
"""驗證拆檔載入：初始 1,431 → 撳載入 → 2,759；規模篩選；JS 錯誤。"""
import subprocess, re, os
BASE = r"C:/Users/kbl/WorkBuddy AI/2026-10-28-14-48-21"
CHROME = r"C:/Users/kbl/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe"
H = open(BASE + "/index.html", encoding="utf-8").read()
pre = '<script>window.__errs=[];window.onerror=function(m,s,l){window.__errs.push(String(m).slice(0,90)+"@"+l);};</script>'
inj = ('<script>setTimeout(function(){'
       'var s0=document.getElementById("statbar").textContent.slice(0,60);'
       'var btn=document.getElementById("loadDerived");'
       'if(btn) btn.click();'
       'setTimeout(function(){'
       'var s1=document.getElementById("statbar").textContent.slice(0,60);'
       'var sc=document.getElementById("scale");sc.value="10";sc.dispatchEvent(new Event("change"));'
       'setTimeout(function(){'
       'var cards=document.querySelectorAll(".card").length;'
       'document.title="init:"+s0+"||after:"+s1+"||cards≥10座:"+cards+"||err:"+(window.__errs[0]||"0");'
       '},1200);},3500);},2500);</script>')
open(BASE + "/_v.html", "w", encoding="utf-8").write(H.replace("<script>", pre + "<script>", 1) + inj)
out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=26000", "--dump-dom",
                      "file:///" + BASE.replace(" ", "%20") + "/_v.html"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace")
m = re.search(r"<title>(.*?)</title>", out.stdout, re.S)
print("->", m.group(1)[:300] if m else "-")
os.remove(BASE + "/_v.html")
