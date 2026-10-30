# -*- coding: utf-8 -*-
"""座別明細全量審計：對 index.html 內嵌 DATA 逐邨逐座做一致性／合理性檢查。
用法：python audit_blocks.py
"""
import json, re, os, sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
H = open(os.path.join(BASE, "index.html"), encoding="utf-8").read()
i = H.find("const DATA = ") + len("const DATA = ")
j = H.find(";\nconst COVERED", i)
DATA = json.loads(H[i:j])

HK = (22.15, 22.58, 113.82, 114.45)   # lat_min, lat_max, lng_min, lng_max
issues = []
stat = Counter()

def add(sev, estate, block, msg):
    issues.append((sev, estate, block, msg))

for e in DATA:
    st = e.get("source_type") or e.get("source")
    bs_all = e.get("blocks") or []
    bs = [b for b in bs_all if not b.get("nr")]      # 非住宅／未命名只列出，唔計座數
    stat[f"{st}_nonres"] += len(bs_all) - len(bs)
    stat[f"{st}_estates"] += 1
    if not bs:
        stat[f"{st}_no_blocks"] += 1
        continue
    stat[f"{st}_with_blocks"] += 1
    stat[f"{st}_blocks"] += len(bs)

    # 1) blocks_count 對唔對
    if e.get("blocks_count") is not None and e["blocks_count"] != len(bs):
        add("WARN", e["name_tc"], "-", f"blocks_count={e['blocks_count']} 但實際住宅座 {len(bs)}")

    names = [b.get("n") or "" for b in bs]
    dup = [n for n, c in Counter(names).items() if c > 1]
    if dup:
        add("ERR", e["name_tc"], ",".join(dup), "座名重複")

    empty = [b for b in bs if not (b.get("n") or "").strip()]
    if empty:
        add("ERR", e["name_tc"], "-", f"{len(empty)} 座冇座名")

    # 2) 單位／升降機合理性
    us = [b.get("u") for b in bs if b.get("u") is not None]
    for b in bs:
        n = b.get("n") or "?"
        u, el = b.get("u"), b.get("e")
        if u is not None:
            if u <= 0:
                add("ERR", e["name_tc"], n, f"單位數 = {u}")
            if el is not None and el > u:
                add("ERR", e["name_tc"], n, f"有𨋢單位 {el} > 總單位 {u}")
            if el is not None and u and el / u > 1.0001:
                add("ERR", e["name_tc"], n, f"有𨋢比例 >100%（{el}/{u}）")
        elif el is not None:
            add("WARN", e["name_tc"], n, "有升降機單位數但冇總單位數")

        # 3) 樓層
        f1, f2 = b.get("f1"), b.get("f2")
        if f1 is not None and f2 is not None:
            if f1 > f2:
                add("ERR", e["name_tc"], n, f"樓層範圍倒轉 {f1}–{f2}")
            if f2 > 90:
                add("WARN", e["name_tc"], n, f"最高樓層 {f2} 異常")
            if f1 < -3:
                add("WARN", e["name_tc"], n, f"最低樓層 {f1} 異常")

        # 4) 面積
        a = b.get("a")
        if a is not None and (a <= 5 or a > 300):
            add("WARN", e["name_tc"], n, f"平均面積 {a} ㎡ 異常")

        # 5) 座標
        la, lo = b.get("lat"), b.get("lng")
        if (la is None) != (lo is None):
            add("ERR", e["name_tc"], n, "只有 lat 或只有 lng")
        if la is not None and not (HK[0] <= la <= HK[1] and HK[2] <= lo <= HK[3]):
            add("ERR", e["name_tc"], n, f"座標出界 {la},{lo}")
        if la is not None and e.get("lat") is not None:
            d = ((la - e["lat"]) ** 2 + (lo - e["lng"]) ** 2) ** 0.5 * 111000
            if d > 1200:
                add("WARN", e["name_tc"], n, f"座離屋邨中心 {d:.0f}m")

        # 6) 樓高
        s, h = b.get("s"), b.get("h")
        if s is not None and (s <= 0 or s > 90):
            add("WARN", e["name_tc"], n, f"層數 {s} 異常")
        if h is not None and (h <= 3 or h > 350):
            add("WARN", e["name_tc"], n, f"樓高 {h}m 異常")
        if s is not None and h is not None and s > 3 and h / s < 2.2:
            add("WARN", e["name_tc"], n, f"層高 {h/s:.1f}m 偏低（{s}層/{h}m）")

        # 7) EMSD
        em = b.get("emsd_lifts")
        if em is not None and (em <= 0 or em > 60):
            add("WARN", e["name_tc"], n, f"EMSD 部數 {em} 異常")

    # 8) 總單位 vs 逐座合計（只對公屋／簡屋）
    if st in ("PRH", "LPH") and us and e.get("total_units"):
        if sum(us) != e["total_units"]:
            add("WARN", e["name_tc"], "-",
                f"逐座單位合計 {sum(us):,} ≠ 屋邨總數 {e['total_units']:,}（差 {sum(us)-e['total_units']:,}）")
    # 9) 居屋／私人：有單位值就代表前端會顯示（應該冇）
    if st in ("HOS", "PRV") and us:
        add("WARN", e["name_tc"], "-", f"{st} 竟有逐座單位數（{len(us)} 座）")

    # 10) 假座（「第一座至第二十二座」呢類範圍字串）
    for b in bs:
        n = b.get("n") or ""
        if re.search(r"第.+座\s*至\s*第.+座|至第.+座", n):
            add("WARN", e["name_tc"], n, "座名係範圍字串（非單一座）")

print("=== 覆蓋統計 ===")
for st in ("PRH", "LPH", "HOS", "PRV", "VLG"):
    a, b_, c = stat[f"{st}_estates"], stat[f"{st}_with_blocks"], stat[f"{st}_no_blocks"]
    blk = stat[f"{st}_blocks"]
    print(f"{st}: 屋苑 {a}｜有座別 {b_}｜冇座別 {c}｜住宅座 {blk}｜另標記非住宅 {stat[f'{st}_nonres']}")

sev = Counter(x[0] for x in issues)
print(f"\n=== 問題：{len(issues)} 條（ERR {sev['ERR']}／WARN {sev['WARN']}）===")
for s in ("ERR", "WARN"):
    sub = [x for x in issues if x[0] == s]
    print(f"\n--- {s}（{len(sub)}）---")
    for _, est, blk, msg in sub[:40]:
        print(f"  {est}｜{blk}｜{msg}")
    if len(sub) > 40:
        print(f"  …其餘 {len(sub)-40} 條")
