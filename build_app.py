# -*- coding: utf-8 -*-
"""
把 data/normalized/all_estates_enriched.json 注入 estate_matcher_template.html，
產出單檔原型 estate_matcher.html。

視圖層加工（stage2 管線唔做嘅嘢）：
1. mtr_candidates    —— 每個有座標屋邨最近 K=3 個港鐵場地錨點。
   錨點用「場地多邊形邊界最近點」（點到線段投影），唔係 bbox 中心——
   bbox 中心可能跌入站體範圍令行人網絡 snap 唔到
   （實例：天耀一邨→天水圍站 bbox 中心 197m 'No route'，邊界點 73m 實測 193m OK）。
2. school_candidates —— 最近 K=3 間小學（含座標），支援「返學 3D 路線」＋
   nearest_school 補 lat/lng。學校池快取 data/normalized/edb_schools.json。
3. 同步以邊界最近點距離修正 nearest_mtr ＋ 重算 sub_scores.mtr ＋ score（管線同款公式）。

用法：python build_app.py
"""
import json, math, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(BASE, "estate_matcher_template.html")
SRC = os.path.join(BASE, "data", "normalized", "all_estates_enriched.json")
SCHOOL_CACHE = os.path.join(BASE, "data", "normalized", "edb_schools.json")
OUT = os.path.join(BASE, "estate_matcher.html")
K_NEAREST = 3
sys.path.insert(0, BASE)


def load_schools():
    """有快取用快取；無則調 stage2 同款邏輯下載 EDB 學校 JSON（過濾小學＋香港範圍）。"""
    if os.path.exists(SCHOOL_CACHE):
        with open(SCHOOL_CACHE, encoding="utf-8") as f:
            return json.load(f)
    from stage2_full import build_schools
    schools = build_schools()
    with open(SCHOOL_CACHE, "w", encoding="utf-8") as f:
        json.dump(schools, f, ensure_ascii=False)
    print(f"  學校池快取 → {os.path.relpath(SCHOOL_CACHE, BASE)}")
    return schools


def haversine(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def smooth_score(d, d0, hl):
    if d is None:
        return 50.0
    if d <= d0:
        return 100.0
    return round(max(5.0, 100.0 * math.exp(-math.log(2) / hl * (d - d0))), 1)


def top_k_mtr(lat, lng, venues, k=K_NEAREST):
    """港鐵候選：bbox 中心粗排前 5 → 邊界最近點精算重排 → 取前 k。
    每個候選帶 2 個錨點 anchors：[邊界最近點, 站體 bbox 中心]——
    兩者各有 snap 得到／唔到嘅情況（天水圍站要邊界點、大窩口站要中心），
    前端規劃時逐錨點嘗試。distance_m 以邊界最近點為準（評分一致）。"""
    from stage2_full import nearest_point_on_rings
    coarse = sorted(venues, key=lambda v: haversine(lat, lng, v["lat"], v["lng"]))[:max(k + 2, 5)]
    precise = []
    for v in coarse:
        if v.get("rings"):
            qy, qx, d = nearest_point_on_rings(v["rings"], lat, lng)
        else:
            qy, qx, d = v["lat"], v["lng"], haversine(lat, lng, v["lat"], v["lng"])
        anchors = [{"lat": qy, "lng": qx, "kind": "boundary"}]
        if haversine(qy, qx, v["lat"], v["lng"]) > 25:   # 細場域兩點太近就唔使重複
            anchors.append({"lat": v["lat"], "lng": v["lng"], "kind": "center"})
        precise.append({"zh": v["zh"], "en": v.get("en") or "", "distance_m": int(d),
                        "anchors": anchors})
    precise.sort(key=lambda x: x["distance_m"])
    return precise[:k]


def top_k(lat, lng, pool, k=K_NEAREST):
    return sorted(
        ({"zh": v["zh"], "en": v.get("en") or "", "lat": v["lat"], "lng": v["lng"],
          "distance_m": int(haversine(lat, lng, v["lat"], v["lng"]))} for v in pool),
        key=lambda x: x["distance_m"])[:k]


with open(TPL, encoding="utf-8") as f:
    tpl = f.read()
with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

from stage2_full import build_mtr_venues
venues = build_mtr_venues()
schools = load_schools()
n_mtr = n_sch = 0
for e in data:
    if e.get("lat") is None:
        e["mtr_candidates"] = []
        e["school_candidates"] = []
        continue
    e["mtr_candidates"] = top_k_mtr(e["lat"], e["lng"], venues)
    e["school_candidates"] = top_k(e["lat"], e["lng"], schools)
    n_mtr += 1
    n_sch += 1
    # 以邊界最近點同步修正 nearest_mtr ＋ 重算 s_mtr ＋ score（與管線公式一致）
    if e["mtr_candidates"]:
        t = e["mtr_candidates"][0]
        a = t["anchors"][0]
        e["nearest_mtr"] = {"zh": t["zh"], "en": t["en"], "lat": a["lat"], "lng": a["lng"],
                            "distance_m": t["distance_m"]}
        s = e.get("sub_scores") or {"school": 50.0, "care": 50.0, "elevator": 100.0}
        s["mtr"] = smooth_score(t["distance_m"], 200, 900)
        e["sub_scores"] = s
        e["score"] = round(0.35 * s["mtr"] + 0.30 * s.get("school", 50.0)
                           + 0.20 * s.get("care", 50.0) + 0.15 * s.get("elevator", 100.0), 1)

# 預設排序：評分 ↓、單位數 ↓（與管線一致）
data.sort(key=lambda x: (-x.get("score", 0), -(x.get("total_units") or 0)))

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
assert "__DATA__" not in payload, "data payload contains placeholder token"
assert "</script" not in payload.lower(), "data payload contains script-breaking sequence"

html = tpl.replace("__DATA__", payload)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"OK  {os.path.relpath(OUT, BASE)}  ({len(html)/1024:.0f} KB, {len(data)} estates, "
      f"mtr_candidates: {n_mtr}, school_candidates: {n_sch})")
