# -*- coding: utf-8 -*-
"""一次性 review 檢查（唔入 git）。"""
import json, re, subprocess, time, math, os, collections, statistics as st

BASE = r"C:/Users/kbl/WorkBuddy AI/2026-10-28-14-48-21"
CHROME = r"C:/Users/kbl/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe"
H = open(BASE + "/index.html", encoding="utf-8").read()
i = H.find("const DATA = ") + 13
j = H.find(";\nconst COVERED", i)
D = json.loads(H[i:j])


def hav(a, b, c, d):
    R = 6371000
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


print("=== 1. 規模 ===")
print("estates", len(D), "| HTML MB", round(len(H) / 1048576, 2))
sizes = {}
for e in D:
    sizes[e["source_type"]] = sizes.get(e["source_type"], 0) + len(json.dumps(e, ensure_ascii=False))
for k, v in sorted(sizes.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v/1048576:.2f} MB")

print("=== 2. 資料完整性 ===")
print("無座標", sum(1 for e in D if e.get("lat") is None))
print("無評分", sum(1 for e in D if e.get("score") is None))
print("有座別但零座釘", sum(1 for e in D if (e.get("blocks") or []) and not any(b.get("lat") is not None for b in e["blocks"])))
print("座釘總數", sum(1 for e in D for b in (e.get("blocks") or []) if b.get("lat") is not None))
_miss = sum(1 for e in D for b in (e.get("blocks") or []) if b.get("lat") is None)
_est = sum(1 for e in D for b in (e.get("blocks") or []) if b.get("est"))
print("缺座標座數", _miss, "（必須 0）｜估算位置座數", _est)
print("同名座（同一屋苑內）", sum(1 for e in D for n, c in collections.Counter(
    b["n"] for b in (e.get("blocks") or []) if not b.get("nr")).items() if c > 1))

print("=== 3. 重複屋苑 ===")
off = [e for e in D if e["source_type"] != "PRVD"]
dups = []
for e in D:
    if e["source_type"] != "PRVD":
        continue
    for o in off:
        if (e["name_tc"] == o["name_tc"] or (len(e["name_tc"]) >= 3 and
            (e["name_tc"] in o["name_tc"] or o["name_tc"] in e["name_tc"]))):
            d = hav(e["lat"], e["lng"], o["lat"], o["lng"])
            if d < 800:
                dups.append((e["name_tc"], o["name_tc"], o["source_type"], int(d)))
                break
print("PRVD↔官方 <800m 疑似重複:", len(dups), dups[:6])

print("=== 4. 評分分佈 ===")
g = collections.defaultdict(list)
for e in D:
    g[e["source_type"]].append(e.get("score") or 0)
for k, v in sorted(g.items()):
    print(f"  {k}: mean {st.mean(v):.1f} / median {st.median(v):.1f} / max {max(v):.1f}")

print("=== 5. 村落錨點異常（高分村） ===")
vl = sorted([e for e in D if e["source_type"] == "VLG"], key=lambda e: -(e.get("score") or 0))[:5]
for e in vl:
    print("  ", e["name_tc"], e["district_tc"], e["score"])

print("=== 6. 載入效能＋JS 錯誤 ===")
t = time.time()
_pre = '<script>window.__errs=[];window.onerror=function(m,s,l){window.__errs.push(String(m).slice(0,120)+" @"+l);};</script>'
_h2 = H.replace("<script>", _pre + "<script>", 1) + \
    '<script>setTimeout(function(){document.title="HEALTH|errs:"+window.__errs.join(" ;; ");},2500);</script>'
_tmp = os.path.join(BASE, "_health_tmp.html")
open(_tmp, "w", encoding="utf-8").write(_h2)
out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=30000",
                      "--dump-dom", "file:///" + _tmp.replace(" ", "%20")],
                     capture_output=True, text=True, encoding="utf-8", errors="replace")
os.remove(_tmp)
el = time.time() - t
cards = out.stdout.count('class="card"')
print("耗時", round(el, 1), "s | 首屏卡片", cards, "| DOM MB", round(len(out.stdout) / 1048576, 1))
m = re.search(r"<title>HEALTH\|(.*?)</title>", out.stdout, re.S)
errs = m.group(1) if m else "?"
print("JS 錯誤:", errs if errs.strip() and errs != "errs:" else "0（無）")
m = re.search(r'id="statbar"[^>]*>(.*?)</div>', out.stdout, re.S)
print("statbar:", re.sub(r"<[^>]+>", "", m.group(1))[:120] if m else "-")

print("=== 7. 資料來源聲明 ===")
for kw in ["推算", "估算", "非官方"]:
    print(f"  '{kw}' 出現次數:", H.count(kw))
