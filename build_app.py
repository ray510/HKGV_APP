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
import json, math, os, re, sys, time, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(BASE, "estate_matcher_template.html")
SRC = os.path.join(BASE, "data", "normalized", "all_estates_enriched.json")
SCHOOL_CACHE = os.path.join(BASE, "data", "normalized", "edb_schools.json")
KG_CACHE = os.path.join(BASE, "data", "normalized", "edb_kindergartens.json")
HOSPITAL_SRC = os.path.join(BASE, "data", "raw", "osm_hospitals.json")
OSM_CACHE = os.path.join(BASE, "data", "normalized", "osm_block_coords.json")
LANDSD_CACHE = os.path.join(BASE, "data", "normalized", "landsd_block_coords.json")
CSDI_BLOCK_CACHE = os.path.join(BASE, "data", "normalized", "csdi_block_coords.json")
FERRY_CACHE = os.path.join(BASE, "data", "normalized", "ferry_piers.json")
LANDSD_QUERY = ("https://portal.csdi.gov.hk/server/rest/services/common/"
                "landsd_rcd_1637211194312_35158/FeatureServer/0/query")
GENERIC_BLOCK = re.compile(r"^\s*(第\s*[0-9一二兩三四五六七八九十]+\s*座|BLOCK\s*\d+)\s*$", re.I)
OUT = os.path.join(BASE, "index.html")   # GitHub Pages 根路徑直接開 app
K_NEAREST = 3
sys.path.insert(0, BASE)


def load_kindergartens():
    """EDB 幼稚園池（快取 normalized；無則調 stage2 同款邏輯下載）。"""
    if os.path.exists(KG_CACHE):
        with open(KG_CACHE, encoding="utf-8") as f:
            return json.load(f)
    from stage2_full import build_kindergartens
    kgs = build_kindergartens()
    with open(KG_CACHE, "w", encoding="utf-8") as f:
        json.dump(kgs, f, ensure_ascii=False)
    print(f"  幼稚園池快取 → {os.path.relpath(KG_CACHE, BASE)}")
    return kgs


def load_ae_hospitals():
    """OSM 醫院快取（stage2 抓取）；只取 emergency=yes 急症醫院。"""
    if not os.path.exists(HOSPITAL_SRC):
        return []
    with open(HOSPITAL_SRC, encoding="utf-8") as f:
        arr = json.load(f)
    return [h for h in arr if h.get("ae")]


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


def ensure_csdi_block_coords(data):
    """座級座標第一層：全港 bbox 實測快取（csdi_block_coords.json，1,571/1,713 座＝91.7%，
    key = source|邨名|座名）。含 csuid／storeys。"""
    if not os.path.exists(CSDI_BLOCK_CACHE):
        return 0
    with open(CSDI_BLOCK_CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    n = 0
    for e in data:
        for b in e.get("blocks", []):
            if b.get("lat") is not None:
                continue
            v = cache.get(f'{e["source"]}|{e["name_tc"]}|{b.get("n", "")}')
            if not v:
                continue
            b["lat"], b["lng"] = v["lat"], v["lng"]
            if v.get("storeys") is not None:
                b["s"] = v["storeys"]
            n += 1
    print(f"  CSDI 座級座標：套用 {n} 座（bbox 實測快取）", flush=True)
    return n


def attach_ferry_piers(data):
    """離島錨點：運輸署「渡輪碼頭位置」（74 個，2026-10-26 更新）＋OSM 名配對。
    每邨計算最近碼頭，供「⛴️ 碼頭」3D 路線目的地（尤其 6 個無鐵路屋邨）。"""
    if not os.path.exists(FERRY_CACHE):
        return 0
    with open(FERRY_CACHE, encoding="utf-8") as f:
        piers = json.load(f)
    if not piers:
        return 0
    n = 0
    for e in data:
        if e.get("lat") is None:
            continue
        best, bd = None, 1e18
        for p in piers:
            d = haversine(e["lat"], e["lng"], p["lat"], p["lng"])
            if d < bd:
                best, bd = p, d
        e["nearest_pier"] = {"zh": best["zh"], "lat": round(best["lat"], 5),
                             "lng": round(best["lng"], 5), "distance_m": int(bd)}
        n += 1
    print(f"  ⛴️ 渡輪碼頭錨點：{n} 邨（最近碼頭中位數 {sorted(x['nearest_pier']['distance_m'] for x in data)[n//2]}m）", flush=True)
    return n


def ensure_landsd_block_coords(data):
    """官方座級定位（主要來源）：地政總署「建築物」數據集（2026-10-22 更新）。
    BuildingNameTC 逐座名＋BuildingBlockType（Tower/Podium）＋Storeys/TopHeight，
    polygon centroid 作座級座標。按名批量查（每批 25 個），快取 landsd_block_coords.json。
    注意：同名樓宇跨屋邨存在（實測兩個耀富樓），故每座須距屋邨中心 ≤800m 才採用。"""
    cache = {}
    if os.path.exists(LANDSD_CACHE):
        with open(LANDSD_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    names = sorted({(b.get("n") or "").strip() for e in data for b in e.get("blocks", [])
                    if (b.get("n") or "").strip() and not GENERIC_BLOCK.match(b.get("n") or "")})
    todo = [n for n in names if n not in cache]
    if todo:
        print(f"  LandsD 座級：{len(todo)} 個新座名待查（分 {len(todo)//25 + 1} 批）…", flush=True)
        for i in range(0, len(todo), 25):
            batch = todo[i:i+25]
            where = "BuildingNameTC IN (" + ",".join("'" + n.replace("'", "''") + "'" for n in batch) + ")"
            qs = urllib.parse.urlencode({
                "where": where,
                "outFields": "BuildingNameTC,BuildingBlockType,Storeys,TopHeight",
                "returnCentroid": "true", "returnGeometry": "false",
                "outSR": "4326", "f": "json"})
            got = None
            for attempt in range(3):
                try:
                    req = urllib.request.Request(LANDSD_QUERY + "?" + qs,
                                                 headers={"User-Agent": "HKGV-prototype/1.0 (CSDI Awards 2026)"})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        got = json.loads(r.read().decode("utf-8", "replace"))
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(2 * (attempt + 1))
            if not got or "error" in (got or {}):
                continue
            for ft in got.get("features", []):
                a = ft.get("attributes") or {}
                c = ft.get("centroid") or {}
                nm = (a.get("BuildingNameTC") or "").strip()
                if not nm or c.get("x") is None:
                    continue
                cache.setdefault(nm, []).append({
                    "lat": round(c["y"], 5), "lng": round(c["x"], 5),
                    "t": a.get("BuildingBlockType") or "",
                    "s": a.get("Storeys"), "h": a.get("TopHeight")})
            time.sleep(0.3)
        with open(LANDSD_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    n_hit = 0
    for e in data:
        if e.get("lat") is None:
            continue
        for b in e.get("blocks", []):
            cands = cache.get((b.get("n") or "").strip())
            if not cands:
                continue
            ranked = sorted(
                ((haversine(e["lat"], e["lng"], c["lat"], c["lng"]), c) for c in cands),
                key=lambda x: (x[1].get("t") != "Tower", x[0]))   # Tower 優先，再按距離
            dist, best = ranked[0]
            if dist > 800:
                continue
            b["lat"], b["lng"] = best["lat"], best["lng"]
            if best.get("s") is not None:
                b["s"] = best["s"]
            if best.get("h") is not None:
                b["h"] = round(float(best["h"]), 1)
            n_hit += 1
    print(f"  LandsD 座級座標：套用 {n_hit} 座（官方，快取 {os.path.relpath(LANDSD_CACHE, BASE)}）", flush=True)
    return n_hit


def ensure_block_coords(data):
    """用 OSM Overpass 為 PRH 專名座（耀康樓等）補座級座標（LandsD 未覆蓋時嘅 fallback）。
    批次模式：每 20 個屋邨併一條查詢（全港約 13 條請求），事後按
    「座名精確匹配 + 距屋邨中心 ≤400m」歸配。跳過「第N座／BLOCK N」通用名（易誤配）。
    快取 data/normalized/osm_block_coords.json（key: source|邨名）。
    網絡受阻時可設環境變數 HKGV_SKIP_OSM=1 跳過查詢（只用快取）。"""
    if os.environ.get("HKGV_SKIP_OSM"):
        print("  OSM 座級座標：HKGV_SKIP_OSM=1，跳過查詢", flush=True)
    cache = {}
    if os.path.exists(OSM_CACHE):
        with open(OSM_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    skip = bool(os.environ.get("HKGV_SKIP_OSM"))
    todo = []
    for e in data:
        key = e["source"] + "|" + e["name_tc"]
        if e.get("lat") is None or not e.get("blocks") or key in cache or skip:
            continue
        if all(GENERIC_BLOCK.match(b["n"] or "") for b in e["blocks"]):
            cache[key] = {}          # 冇可匹配座名，記空免重查
            continue
        todo.append(e)
    if not todo:
        print("  OSM 座級座標：快取已齊，0 次查詢", flush=True)
    else:
        BATCH = 20
        batches = [todo[i:i+BATCH] for i in range(0, len(todo), BATCH)]
        print(f"  OSM 座級座標：{len(todo)} 個屋邨待查，分 {len(batches)} 批…", flush=True)
        for bi, batch in enumerate(batches, 1):
            clauses = ";".join(f'way["building"]["name"](around:400,{e["lat"]},{e["lng"]});'
                               for e in batch)
            q = f"[out:json][timeout:90];({clauses});out center tags;"
            named = []
            for attempt in range(3):
                try:
                    url = "https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(q)
                    req = urllib.request.Request(url, headers={"User-Agent": "HKGV-prototype/1.0 (CSDI Awards 2026)"})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        d = json.loads(r.read().decode("utf-8", "replace"))
                    for el in d.get("elements", []):
                        nm = ((el.get("tags") or {}).get("name") or "").strip()
                        c = el.get("center") or {}
                        if nm and c.get("lat") and c.get("lon"):
                            named.append((nm, float(c["lat"]), float(c["lon"])))
                    break
                except Exception as ex:
                    if attempt < 2:
                        time.sleep(4 * (attempt + 1))
                    else:
                        print(f"  OSM 批 {bi}/{len(batches)} FAIL {type(ex).__name__}，該批下次重試", flush=True)
            if named:
                for e in batch:
                    key = e["source"] + "|" + e["name_tc"]
                    hit = {}
                    for b in e["blocks"]:
                        bn = (b["n"] or "").strip()
                        if not bn or GENERIC_BLOCK.match(bn):
                            continue
                        cand = [(nm, la, lo) for nm, la, lo in named
                                if (bn in nm or nm in bn)
                                and haversine(e["lat"], e["lng"], la, lo) <= 400]
                        if cand:
                            nm, la, lo = min(cand, key=lambda x: haversine(e["lat"], e["lng"], x[1], x[2]))
                            hit[bn] = (la, lo)
                    cache[key] = hit
            time.sleep(2.0)
            print(f"  OSM 批 {bi}/{len(batches)} 完成（累計 named buildings {len(named)}）", flush=True)
            with open(OSM_CACHE, "w", encoding="utf-8") as f:   # 每批即寫快取
                json.dump(cache, f, ensure_ascii=False)
    n_hit = 0
    for e in data:
        key = e["source"] + "|" + e["name_tc"]
        coords = cache.get(key) or {}
        for b in e.get("blocks", []):
            if b.get("lat") is not None:      # LandsD 官方座標優先，唔覆蓋
                continue
            pos = coords.get((b["n"] or "").strip())
            if pos:
                b["lat"], b["lng"] = pos
                n_hit += 1
    with open(OSM_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    print(f"  OSM 座級座標：套用 {n_hit} 座（快取 {os.path.relpath(OSM_CACHE, BASE)}）", flush=True)
    return n_hit


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

# 地政總署標誌（官方 SVG）base64 內嵌 —— CSDI 3D 行人路線 API 合規要求（標誌＋版權聲明）
LOGO = os.path.join(BASE, "assets", "landsd_logo_sm.svg")
import base64
with open(LOGO, "rb") as f:
    svg_b64 = base64.b64encode(f.read()).decode()
tpl = tpl.replace("__LAND_SVG__", "data:image/svg+xml;base64," + svg_b64)

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

from stage2_full import build_mtr_venues
venues = build_mtr_venues()
schools = load_schools()
kgs = load_kindergartens()
ae_hosp = load_ae_hospitals()

# 座級定位三層 fallback：CSDI bbox 實測 → LandsD 按名查 → OSM
ensure_csdi_block_coords(data)
ensure_landsd_block_coords(data)
ensure_block_coords(data)

# 離島錨點：最近渡輪碼頭
attach_ferry_piers(data)

n_mtr = n_sch = 0
for e in data:
    if e.get("lat") is None:
        e["mtr_candidates"] = []
        e["school_candidates"] = []
        continue
    e["mtr_candidates"] = top_k_mtr(e["lat"], e["lng"], venues)
    e["school_candidates"] = top_k(e["lat"], e["lng"], schools)
    # 800m 內全部幼稚園（供用戶逐間揀；上限 40，冇就退到 2km 內最近 1 間）
    kg_all = top_k(e["lat"], e["lng"], kgs, k=40)
    within = [k for k in kg_all if k["distance_m"] <= 800]
    if not within and kg_all and kg_all[0]["distance_m"] <= 2000:
        within = kg_all[:1]
    e["nearest_kgs"] = within
    for k in e["nearest_kgs"]:
        k["n"] = k.pop("zh")
        k["d"] = k.pop("distance_m")
        k.pop("en", None)
        k["lat"] = round(k["lat"], 5)
        k["lng"] = round(k["lng"], 5)
    # 5km 內全部急症醫院（供逐間揀；上限 12，冇就最近 3 間）
    hosp_ranked = sorted(
        ({"n": h["zh"], "lat": round(h["lat"], 5), "lng": round(h["lng"], 5),
          "d": int(haversine(e["lat"], e["lng"], h["lat"], h["lng"]))} for h in ae_hosp),
        key=lambda x: x["d"])
    near_h = [h for h in hosp_ranked if h["d"] <= 5000][:12]
    e["ae_hospitals"] = near_h if near_h else hosp_ranked[:3]
    n_mtr += 1
    n_sch += 1
    # 以邊界最近點同步修正 nearest_mtr ＋ 重算 s_mtr ＋ score（與管線公式一致）
    if e["mtr_candidates"]:
        t = e["mtr_candidates"][0]
        a = t["anchors"][0]
        e["nearest_mtr"] = {"zh": t["zh"], "en": t["en"], "lat": a["lat"], "lng": a["lng"],
                            "distance_m": t["distance_m"]}
        s = e.get("sub_scores") or {"school": 50.0, "care": 50.0, "childcare": 50.0,
                                    "elderly_shelter": 50.0, "elevator": 100.0}
        s["mtr"] = smooth_score(t["distance_m"], 200, 900)
        e["sub_scores"] = s
        e["score"] = round(0.35 * s["mtr"] + 0.25 * s.get("school", 50.0)
                           + 0.10 * s.get("care", 50.0) + 0.05 * s.get("childcare", 50.0)
                           + 0.10 * s.get("elderly_shelter", 50.0)
                           + 0.15 * s.get("elevator", 100.0), 1)

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
