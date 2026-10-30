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
import json, math, os, re, sys, time, urllib.error, urllib.parse, urllib.request

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
EMSD_BLOCK_LIFTS = os.path.join(BASE, "data", "normalized", "emsd_block_lifts.json")
PRV_BLOCK_CACHE = os.path.join(BASE, "data", "normalized", "prv_blocks.json")
CENSUS_POLY = os.path.join(BASE, "data", "normalized", "censtatd_estate_polygons.json")
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


BACKFILL_CACHE = os.path.join(BASE, "data", "normalized", "block_backfill.json")
NON_RESIDENTIAL = ("會所", "商場", "停車場", "車場", "幼稚園", "學校", "中學", "小學", "教堂", "診所",
                   "辦事處", "管理處", "警署", "警崗", "消防", "變電", "變壓", "泵房", "垃圾", "涼亭",
                   "通道", "平台", "閘", "泳池", "球場", "街市", "街坊", "公園", "廁", "郵局",
                   "安老院", "護理", "幼兒", "教會", "禮拜堂", "廟", "酒店", "銀行", "油站", "巴士",
                   "俱樂部", "車站", "服務中心", "發展中心", "社區中心", "文娛", "耆康", "福利", "書院")
NON_RESIDENTIAL_EN = ("SCHOOL", "KINDERGARTEN", "COLLEGE", "UNIVERSITY", "CHURCH", "HOTEL",
                      "MALL", "CLUBHOUSE", "CLUB HOUSE", "CAR PARK", "SUBSTATION", "TEMPLE",
                      "HOSPITAL", "CLINIC", "LIBRARY", "THEATRE")


def _is_residential_name(n):
    """判斷座名係唔係住宅（**只用作標記，唔用嚟刪**）。
    普查 bbox 會連學校／變電站／商場一齊抓返嚟，呢啲要標「非住宅」，但唔可以靜靜刪走。"""
    if not n:
        return False
    s = n.strip()
    if re.fullmatch(r"[\(（].*[\)）]", s):              # "(BRO)" 呢類佔位名
        return False
    if len(s) <= 1:                                    # 單字碎片
        return False
    if re.fullmatch(r"[A-Za-z0-9\-]{1,3}", s):         # "A"、"B1" 呢類佔位名
        return False
    u = s.upper()
    if any(k in s for k in NON_RESIDENTIAL) or any(k in u for k in NON_RESIDENTIAL_EN):
        return False
    # 結尾判斷：唔可以一刀切用 substring，否則「愉景新城第X座」會被「新城」誤殺
    if s.endswith(("站", "場", "房", "廠", "校", "新城")):
        return False
    return True


FRAGMENT = re.compile(r"^(第?[一二三四五六七八九十0-9]+期?|[A-Za-z]|[0-9]+)$")


def _mark_blocks(blocks, estate_name=""):
    """**唔刪座**：只標記 b["nr"]=1（非住宅）／b["ph"]=1（佔位名／碎片）。
    之前用白名單刪字，誤殺「晶巒」「珀峰」「愉景新城第X座」等真座名——改用標記，前端灰顯示。"""
    for b in blocks:
        n = (b.get("n") or "").strip()
        rest = n[len(estate_name):].strip() if estate_name and n.startswith(estate_name) else n
        ph = 1 if (FRAGMENT.match(rest) or re.fullmatch(r"[\(（].*[\)）]", n or "")) else 0
        b["nr"] = 0 if (_is_residential_name(n) and not ph) else 1
        if ph:
            b["ph"] = 1
    return blocks


def sanitize_block_heights(data):
    """層高不合理（<2.2m 或 >6.5m）＝樓高配對錯（多邊形揀錯附屬體）→ 丟棄高度，只保留層數。"""
    n = 0
    for e in data:
        for b in e.get("blocks", []):
            s, h = b.get("s"), b.get("h")
            if s and h and s > 3 and not (2.2 <= h / s <= 6.5):
                b["h"] = None
                n += 1
    if n:
        print(f"  樓高校正：{n} 座高度與層數唔匹配 → 只顯示層數（唔顯示可疑高度）", flush=True)
CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
PSEUDO_BLOCK = re.compile(r"第\s*[一二三四五六七八九十0-9]+\s*座\s*至\s*第\s*[一二三四五六七八九十0-9]+\s*座")


def _cn_num(s):
    """『第七座』→7、『二十三座』→23；認唔到返 None（用嚟排座序）。"""
    m = re.search(r"第\s*([一二三四五六七八九十]+)\s*(?:座|期|幢)", s)
    if not m:
        return None
    t = m.group(1)
    if "十" in t:
        a, _, b = t.partition("十")
        return (CN_DIGIT.get(a, 1) if a else 1) * 10 + (CN_DIGIT.get(b, 0) if b else 0)
    return CN_DIGIT.get(t)


def _block_sort_key(n):
    v = _cn_num(n)
    return (0, v, n) if v is not None else (1, 0, n)


def _landsd_like(name, timeout=25):
    """LandsD 建築物名稱模糊查（`LIKE '%名%'`），回傳同名樓宇全部多邊形。"""
    qs = urllib.parse.urlencode({
        "where": f"BuildingNameTC LIKE '%{name}%'",
        "outFields": "BuildingNameTC,BuildingBlockType,Storeys,TopHeight",
        "returnCentroid": "true", "returnGeometry": "false",
        "outSR": "4326", "f": "json", "resultRecordCount": "80"})
    req = urllib.request.Request(LANDSD_QUERY + "?" + qs,
                                 headers={"User-Agent": "HKGV-prototype/1.0 (CSDI Awards 2026)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    out = []
    for ft in d.get("features", []):
        a = ft.get("attributes") or {}
        c = ft.get("centroid") or {}
        nm = (a.get("BuildingNameTC") or "").strip()
        if not nm or c.get("x") is None:
            continue
        out.append({"n": nm, "lat": round(c["y"], 5), "lng": round(c["x"], 5),
                    "t": a.get("BuildingBlockType") or "",
                    "s": a.get("Storeys"), "h": a.get("TopHeight")})
    return out


def backfill_blocks(data):
    """補座別（只補座名／座標／層數／樓高，唔會砌單位數）：
    ① 居屋「第一座至第十座」呢類**範圍字串** → 用地政總署逐座名稱拆返真座名
    ② 私人屋苑完全冇座別 → 用屋苑名 LIKE 查返附近 Tower
    結果快取 block_backfill.json；網絡失敗唔記負快取，下次再試。"""
    cache = {}
    if os.path.exists(BACKFILL_CACHE):
        with open(BACKFILL_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    targets = []
    for e in data:
        if e.get("lat") is None:
            continue
        bs = e.get("blocks") or []
        if not bs and (e.get("source_type") == "PRV"):
            targets.append((e, "prv"))
        elif len(bs) == 1 and PSEUDO_BLOCK.search(bs[0].get("n") or ""):
            targets.append((e, "pseudo"))
    if not targets:
        return
    print(f"  座別補完：{len(targets)} 個屋苑（私人冇座別＋居屋範圍字串）待查…", flush=True)
    n_fill, n_query = 0, 0
    for e, kind in targets:
        nm = e["name_tc"]
        if nm not in cache:
            try:
                cache[nm] = _landsd_like(nm)
                n_query += 1
            except Exception:
                continue                      # 網絡失敗：唔記負快取
            time.sleep(0.35)
        cands = cache.get(nm) or []
        near = [c for c in cands
                if c.get("t") == "Tower"
                and haversine(e["lat"], e["lng"], c["lat"], c["lng"]) <= 700
                and not any(k in c["n"] for k in NON_RESIDENTIAL)
                and (kind != "pseudo" or c["n"].startswith(nm))]
        by_name = {}                          # 同名多邊形（主樓＋附屬）→ 取最高
        for c in near:
            k = c["n"]
            if k not in by_name or (c.get("h") or 0) > (by_name[k].get("h") or 0):
                by_name[k] = c
        blocks = []
        for c in by_name.values():
            disp = c["n"][len(nm):].strip() if c["n"].startswith(nm) else c["n"]
            blocks.append({"n": disp or c["n"], "u": None, "e": None, "f1": None, "f2": None, "a": None,
                           "lat": c["lat"], "lng": c["lng"], "s": c.get("s"), "bf": 1,
                           "h": round(float(c["h"]), 1) if c.get("h") is not None else None})
        if kind == "pseudo" and len(blocks) < 2:
            continue                          # 拆唔到就保留原本（唔好整走已知資訊）
        blocks = _mark_blocks(blocks, nm)
        if not blocks:
            continue
        blocks.sort(key=lambda b: _block_sort_key(b["n"]))
        e["blocks"] = blocks
        e["blocks_count"] = sum(1 for b in blocks if not b.get("nr"))
        e["blocks_source"] = "LandsD"
        n_fill += 1
    if n_query:
        with open(BACKFILL_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    print(f"  座別補完：查 {n_query} 個、成功補 {n_fill} 個屋苑", flush=True)


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


def attach_emsd_lifts(data):
    """機電署升降機覆核：為每座附加 EMSD 升降機部數（驗證房委單位檔「有𨋢比例」）。"""
    if not os.path.exists(EMSD_BLOCK_LIFTS):
        return 0
    with open(EMSD_BLOCK_LIFTS, encoding="utf-8") as f:
        lifts = json.load(f)
    n = 0
    for e in data:
        for b in e.get("blocks", []):
            key = e["source"] + "|" + e["name_tc"] + "|" + b["n"]
            cnt = lifts.get(key)
            if cnt:
                b["emsd_lifts"] = cnt
                n += 1
    print(f"  🛗 EMSD 升降機覆核：{n} 座有數據", flush=True)
    return n


def _point_in_ring(lat, lng, ring):
    """Ray casting：ring=[(x,y),...]。"""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_rings(lat, lng, rings):
    return any(_point_in_ring(lat, lng, ring) for ring in rings if len(ring) >= 3)


def ensure_prv_blocks(data):
    """私人屋苑（PRV）座別發現：普查數據冇座名 → 地政「建築物」每邨 bbox 一查
    （Tower＋BuildingNameTC 非空 → 逐座 centroid＋層數／樓高）。
    過濾：座 centroid 落喺普查分界多邊形內（point-in-polygon，精確防抓隔籬屋苑）；
    冇多邊形時 fallback 距邨中心 ≤450m。快取 prv_blocks.json（key=source|name_tc）。"""
    cache = {}
    if os.path.exists(PRV_BLOCK_CACHE):
        with open(PRV_BLOCK_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    polys = {}
    if os.path.exists(CENSUS_POLY):
        with open(CENSUS_POLY, encoding="utf-8") as f:
            polys = json.load(f)
    todo = [e for e in data
            if e.get("source_type") == "PRV" and e.get("lat") is not None and not e.get("blocks")
            and (e["source"] + "|" + e["name_tc"]) not in cache]
    if todo:
        print(f"  PRV 座別發現：{len(todo)} 個私人屋苑待查（每邨 1 bbox 查詢，多邊形過濾）…", flush=True)
    for idx, e in enumerate(todo):
        key = e["source"] + "|" + e["name_tc"]
        rings = polys.get(e["name_tc"], [])
        bbox = f"{e['lng'] - 0.005},{e['lat'] - 0.0038},{e['lng'] + 0.005},{e['lat'] + 0.0038}"
        qs = urllib.parse.urlencode({
            "where": "BuildingBlockType='Tower' AND BuildingNameTC IS NOT NULL",
            "geometry": bbox, "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "BuildingNameTC,Storeys,TopHeight",
            "returnCentroid": "true", "returnGeometry": "false",
            "outSR": "4326", "f": "json", "resultRecordCount": "80"})
        got = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(LANDSD_QUERY + "?" + qs,
                                             headers={"User-Agent": "HKGV-prototype/1.0 (CSDI Awards 2026)"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    got = json.loads(r.read().decode("utf-8", "replace"))
                break
            except urllib.error.HTTPError as ex:
                if ex.code in (403, 429) and attempt < 2:
                    time.sleep(15 * (attempt + 1))   # 節流：長退避
                elif attempt < 2:
                    time.sleep(2 * (attempt + 1))
            except Exception:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        blocks, seen = [], set()
        for ft in (got or {}).get("features", []):
            a = ft.get("attributes") or {}
            c = ft.get("centroid") or {}
            nm = (a.get("BuildingNameTC") or "").strip()
            if not nm or c.get("x") is None or nm in seen or not _is_residential_name(nm):
                continue
            if rings:
                if not _point_in_rings(c["y"], c["x"], rings):
                    continue
            elif haversine(e["lat"], e["lng"], c["y"], c["x"]) > 450:
                continue
            seen.add(nm)
            blocks.append({"n": nm, "u": None, "e": None, "f1": None, "f2": None, "a": None,
                           "lat": round(c["y"], 5), "lng": round(c["x"], 5),
                           "s": a.get("Storeys"),
                           "h": round(float(a["TopHeight"]), 1) if a.get("TopHeight") is not None else None})
        blocks.sort(key=lambda b: b["n"])
        cache[key] = blocks[:80]
        e["blocks"] = cache[key]
        e["blocks_count"] = e.get("blocks_count") or (len(cache[key]) or None)
        if (idx + 1) % 40 == 0:
            print(f"    … {idx + 1}/{len(todo)}", flush=True)
        time.sleep(0.25)
    if todo:
        with open(PRV_BLOCK_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    # 已快取嘅套用
    n_applied = 0
    for e in data:
        if e.get("source_type") != "PRV" or e.get("blocks"):
            continue
        cached = cache.get(e["source"] + "|" + e["name_tc"])
        if cached:
            e["blocks"] = _mark_blocks(cached, e["name_tc"])   # 唔刪，只標記
            e["blocks_count"] = sum(1 for b in e["blocks"] if not b.get("nr")) or e.get("blocks_count")
            n_applied += 1
    n_prv = sum(1 for e in data if e.get("source_type") == "PRV" and e.get("blocks"))
    print(f"  PRV 座別發現：{n_prv} 個私人屋苑有座別明細（新查 {len(todo)}，快取套用 {n_applied}）", flush=True)
    return n_prv


def _landsd_name_query(batch, cache):
    """LandsD BuildingNameTC IN 批量查詢 → 寫入 cache。
    成批失敗（403／WAF 對某啲名敏感，如 '(BRO)'、單字）就拆單名隔離重試；
    負快取只喺查詢「成功」但冇結果時記（節流失敗唔記，留待下次重試）。"""
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
        except urllib.error.HTTPError as ex:
            if ex.code in (403, 429) and attempt < 2:
                time.sleep(15 * (attempt + 1))   # 節流：長退避
            elif attempt < 2:
                time.sleep(2 * (attempt + 1))
        except Exception:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    if got is None or "error" in got:
        # 成批失敗 → 拆單名隔離（找出觸發 WAF 嘅名，其餘照樣命中）
        if len(batch) > 1:
            for n in batch:
                _landsd_name_query([n], cache)
            return
        if len(batch) == 1:
            print(f"    LandsD 單名仍失敗：{batch[0][:20]}（跳過，下次 build 重試）", flush=True)
        return   # 失敗：唔做負快取
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
    for n in batch:
        cache.setdefault(n, [])   # 負快取：查詢成功但冇結果先記


def _pick_landsd_candidate(cands, lat, lng, max_m=800):
    """同名樓宇喺 LandsD 有多個多邊形（主樓＋附屬體／平台／商場）。
    排序：Tower 優先 → **TopHeight 最高** → 最近。
    高度最高係關鍵：實測「愛寶樓」有 6.9m 附屬體同 74.7m 主樓，
    只按距離會揀中附屬體，令樓高變 6.9m（層高 0.33m／層，明顯錯）。"""
    best = None
    for c in cands:
        d = haversine(lat, lng, c["lat"], c["lng"])
        if d > max_m:
            continue
        key = (c.get("t") != "Tower", -(c.get("h") or 0), d)
        if best is None or key < best[0]:
            best = (key, d, c)
    return (best[1], best[2]) if best else (None, None)


def ensure_landsd_block_coords(data):
    """官方座級定位（主要來源）：地政總署「建築物」數據集（2026-10-22 更新）。
    BuildingNameTC 逐座名＋BuildingBlockType（Tower/Podium）＋Storeys/TopHeight，
    polygon centroid 作座級座標。按名批量查（每批 25 個），快取 landsd_block_coords.json。
    注意：同名樓宇跨屋邨存在（實測兩個耀富樓），故每座須距屋邨中心 ≤800m 才採用。"""
    cache = {}
    if os.path.exists(LANDSD_CACHE):
        with open(LANDSD_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    # 只查「未有座標或未有大廈高度」嘅座——普查分界發現嘅私人座已經有齊，唔需要再查名
    names = sorted({(b.get("n") or "").strip() for e in data for b in e.get("blocks", [])
                    if (b.get("n") or "").strip() and not GENERIC_BLOCK.match(b.get("n") or "")
                    and not b.get("bf") and (b.get("lat") is None or b.get("h") is None)})
    todo = [n for n in names if n not in cache]
    if todo:
        print(f"  LandsD 座級：{len(todo)} 個新座名待查（分 {len(todo)//25 + 1} 批）…", flush=True)
        fails = 0
        for i in range(0, len(todo), 25):
            before = len(cache)
            _landsd_name_query(todo[i:i+25], cache)
            if len(cache) == before:          # 成功查詢一定會寫入（命中或負快取）
                fails += 1
                if fails >= 3:
                    print("  LandsD 座級：連續 3 批零寫入，判定服務不可達 → 中止本輪（下次 build 再試）", flush=True)
                    break
            else:
                fails = 0
            time.sleep(0.6)
        with open(LANDSD_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    n_hit = 0
    for e in data:
        if e.get("lat") is None:
            continue
        for b in e.get("blocks", []):
            if b.get("bf") or (b.get("lat") is not None and b.get("h") is not None):
                continue                      # 已有座標＋樓高（普查／補完）→ 唔覆蓋
            cands = cache.get((b.get("n") or "").strip())
            if not cands:
                continue
            dist, best = _pick_landsd_candidate(cands, e["lat"], e["lng"])
            if best is None:
                continue
            b["lat"], b["lng"] = best["lat"], best["lng"]
            if best.get("s") is not None:
                b["s"] = best["s"]
            if best.get("h") is not None:
                b["h"] = round(float(best["h"]), 1)
            n_hit += 1
    # 第二 pass：仍冇座標嘅座試「邨名＋座名」串接（LandsD 對新居屋命名如「山麗苑松山閣」）
    todo2 = {}
    for e in data:
        if e.get("lat") is None:
            continue
        for b in e.get("blocks", []):
            if b.get("lat") is not None or not (b.get("n") or "").strip():
                continue
            combo = (e["name_tc"] + b["n"]).strip()
            if combo not in cache and combo not in todo2:
                todo2[combo] = True
    if todo2:
        combos = sorted(todo2)
        if os.environ.get("HKGV_SKIP_LANDSD"):
            # 只跳過「上網查」，唔可以跳過下面套快取——否則快取已有座標嘅座（如山麗苑 6 座）會白白變返 N/A
            print(f"  LandsD 座級（串接名 fallback）：{len(combos)} 個待查，HKGV_SKIP_LANDSD=1 → 唔查網，只套快取", flush=True)
        else:
            print(f"  LandsD 座級（串接名 fallback）：{len(combos)} 個待查…", flush=True)
            for i in range(0, len(combos), 25):
                _landsd_name_query(combos[i:i+25], cache)
                time.sleep(0.6)
            with open(LANDSD_CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        for e in data:
            if e.get("lat") is None:
                continue
            for b in e.get("blocks", []):
                if b.get("lat") is not None or not (b.get("n") or "").strip():
                    continue
                cands = cache.get((e["name_tc"] + b["n"]).strip())
                if not cands:
                    continue
                dist, best = _pick_landsd_candidate(cands, e["lat"], e["lng"])
                if best is None:
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
        consec_fail = 0          # 熔斷：連續 3 批失敗即判定 Overpass 不可達，跳過其餘批次（免 34 批 × 2 分鐘空等）
        for bi, batch in enumerate(batches, 1):
            if consec_fail >= 3:
                print(f"  OSM 座級座標：連續 {consec_fail} 批失敗，判定端點不可達 → 跳過餘下 "
                      f"{len(batches) - bi + 1} 批（LandsD 官方座標已覆蓋大部分座別）", flush=True)
                break
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
            consec_fail = 0 if named else consec_fail + 1
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

# 座別名單標記（唔刪）：非住宅建築／佔位名只加 nr/ph 旗標，前端灰顯示並排除喺「N 座」計數
for _e in data:
    if _e.get("blocks"):
        _mark_blocks(_e["blocks"], _e["name_tc"])
        _e["blocks_count"] = sum(1 for b in _e["blocks"] if not b.get("nr")) or _e.get("blocks_count")

# 座級定位三層 fallback：CSDI bbox 實測 → LandsD 按名查 → OSM
ensure_prv_blocks(data)        # 私人屋苑先由普查分界＋建築物做精確發現（point-in-polygon）
backfill_blocks(data)          # 再補：私人冇座別（普查分界缺失）＋居屋「第一座至第N座」範圍字串
ensure_csdi_block_coords(data)
ensure_landsd_block_coords(data)
ensure_block_coords(data)
sanitize_block_heights(data)   # 層高唔合理（<2.2m/層）→ 丟棄可疑高度，只保留層數

# 離島錨點：最近渡輪碼頭
attach_ferry_piers(data)
# EMSD 升降機覆核（機電署 74,550 部驗證座級有𨋢比例）
attach_emsd_lifts(data)

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
                                    "elderly_shelter": 50.0, "elevator": None}
        s["mtr"] = smooth_score(t["distance_m"], 200, 900)
        e["sub_scores"] = s
        if e.get("total_units") and s.get("elevator") is not None:
            e["score"] = round(0.35 * s["mtr"] + 0.25 * s.get("school", 50.0)
                               + 0.10 * s.get("care", 50.0) + 0.05 * s.get("childcare", 50.0)
                               + 0.10 * s.get("elderly_shelter", 50.0)
                               + 0.15 * s.get("elevator", 100.0), 1)
        else:
            # 居屋／私人／村屋：升降機維度 N/A → 五維重歸一化
            e["score"] = round((0.35 * s["mtr"] + 0.25 * s.get("school", 50.0)
                                + 0.10 * s.get("care", 50.0) + 0.05 * s.get("childcare", 50.0)
                                + 0.10 * s.get("elderly_shelter", 50.0)) / 0.85, 1)

# 預設排序：評分 ↓、單位數 ↓（與管線一致）
data.sort(key=lambda x: (-x.get("score", 0), -(x.get("total_units") or 0)))

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
assert "__DATA__" not in payload, "data payload contains placeholder token"
assert "</script" not in payload.lower(), "data payload contains script-breaking sequence"

# ☔ 有蓋步行網絡圖層（路政署 2,116 個構築物中心點；只傳顯示所需欄位）
cov_path = os.path.join(BASE, "data", "normalized", "covered_network.json")
covered = []
if os.path.exists(cov_path):
    with open(cov_path, encoding="utf-8") as f:
        covered = json.load(f)
cov_payload = json.dumps(
    [{"t": c["type"], "n": c.get("str_no") or "", "l": c["length_m"],
      "la": round(c["lat"], 5), "lo": round(c["lng"], 5)} for c in covered],
    ensure_ascii=False, separators=(",", ":"))
assert "</script" not in cov_payload.lower(), "covered payload contains script-breaking sequence"

html = tpl.replace("__DATA__", payload).replace("__COVERED__", cov_payload)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"OK  {os.path.relpath(OUT, BASE)}  ({len(html)/1024:.0f} KB, {len(data)} estates, "
      f"mtr_candidates: {n_mtr}, school_candidates: {n_sch})")
