# -*- coding: utf-8 -*-
"""
Stage 2 全量管線：
  1) 18 區房委會公屋單位 → 屋邨級聚合（升降機統計、平均面積、樓宇數）
  2) 教育局學校位置 JSON → 過濾小學
  3) CSDI WFS 在校課後託管服務計劃 → 服務點
  4) 合併 LPH(10) + PRH(~245)，計算最近港鐵／小學／託管點 + 生活圈評分
輸出：data/normalized/all_estates_enriched.json（餵前端）
"""
import csv, json, math, os, re, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
NORM = os.path.join(BASE, "data", "normalized")
UA = {"User-Agent": "Mozilla/5.0 (HK-OpenData-Stage2)"}

LETTERS = ["a","b","c","d","e","f","g","h","j","k","l","m","n","p","q","r","s","t"]  # 18 區
DIST_URL = "https://data.housingauthority.gov.hk/dataset/emms/ha_prhs_{}_en.json"
SCHOOL_URL = "http://www.edb.gov.hk/attachment/en/student-parents/sch-info/sch-search/sch-location-info/SCH_LOC_EDB.json"
PLAYGROUND_URL = "https://www.lcsd.gov.hk/datagovhk/facility/facility-pefac.json"
PLAYGROUND_CACHE = os.path.join(NORM, "lcsd_playgrounds.json")
CARE_URL = ("https://portal.csdi.gov.hk/server/services/common/swd_rcd_1727429602437_81314/MapServer/WFSServer"
            "?service=wfs&version=2.0.0&request=GetFeature&typename=csdi:SWDSBAEPS&outputFormat=GEOJSON")
MTR_PATH = os.path.join(NORM, "mtr_venue_polygon.json")
MTR_FALLBACK = os.path.join(BASE, "data", "raw", "mtr_venue_polygon.json")
RAW = os.path.join(BASE, "data", "raw")

# 3 個 2026/27 新屋邨：房委會單位檔無座標、ES Locator 未收錄 → 手動補（外部提供之約略位置）
NEW_ESTATE_COORDS_PATCH = {
    "古雋邨": {"lat": 22.5068, "lng": 114.0992,
               "note_tc": "古洞北新發展區（港鐵古洞站預計 2027 通車，現以鄰近站計算）"},
    "華富北邨": {"lat": 22.2540, "lng": 114.1365,
                 "note_tc": "薄扶林華景街（華富邨重建接收屋邨）"},
    "曉茵邨": {"lat": 22.3154, "lng": 114.2331,
               "note_tc": "觀塘秀茂坪曉明街（行人天橋連接曉光街）"},
}

# 幼兒中心組合（社署 4 個數據集，約 326 點，補 0–6 歲育兒維度）
CHILDCARE_DATASETS = [
    dict(dataset_id="swd_rcd_1629267205235_2324", layer=None, static=None, save_as="swd_ccc_kg.json"),
    dict(dataset_id="swd_rcd_1629267205216_48300", layer=None, static=None, save_as="swd_ccc_standalone.json"),
    dict(dataset_id="swd_rcd_1629267205235_96246", layer=None, static=None, save_as="swd_ccc_private.json"),
    dict(dataset_id="swd_rcd_1727429358872_6783", layer=None, static=None, save_as="swd_ccc_respite.json"),
]
# 長者服務組合（社署 3 個數據集，約 342 點，補長者維度鑑別度）
ELDER_DATASETS = [
    dict(dataset_id="swd_rcd_1629267205235_1216", layer=None, static=None, save_as="swd_dec.json"),
    dict(dataset_id="swd_rcd_1629267205235_34036", layer=None, static=None, save_as="swd_nec.json"),
    dict(dataset_id="swd_rcd_1696994103126_1549", layer=None, static=None, save_as="swd_elder_support.json"),
]
CSDI_DATASETS = {
    "elderly": dict(dataset_id="swd_rcd_1633501860637_42476", layer="DCUDECC",
                    static="https://static.csdi.gov.hk/csdi-webpage/download/common/145157f813ced72d715daece518d7f4df60ba7dd87413fb955628ae3b162aeb6",
                    save_as="swd_elderly_dcu.json"),
    "halls": dict(dataset_id="had_rcd_1634531497753_36049", layer="CHCC",
                  static="https://static.csdi.gov.hk/csdi-webpage/download/common/bf7100a5efea99aaf9ba42ef9bb7e01730990f1b99d2e34986051c786a125c96",
                  save_as="had_community_halls.json"),
    "shelters": dict(dataset_id="had_rcd_1634542411218_91745", layer=None, static=None,
                     save_as="had_heat_shelters.json"),
    "barrierfree": dict(dataset_id="had_rcd_1635393119641_62162", layer=None, static=None,
                        save_as="had_barrierfree_halls.json"),
}


def fetch_json(url, timeout=180):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def haversine(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_and_count(lat, lng, pool, radius=800):
    """返回 (最近設施, radius 米內設施總數)。radius 內總數用於「選擇密度」評分。"""
    if lat is None or not pool:
        return None, 0
    best, bd, cnt = None, 1e18, 0
    for p in pool:
        d = haversine(lat, lng, p["lat"], p["lng"])
        if d < bd:
            best, bd = p, d
        if d <= radius:
            cnt += 1
    return {"item": best, "distance_m": int(bd)}, cnt


def elevator_flag(v):
    return str(v).strip().upper() == "Y"


def smooth_distance_score(dist_m, full_radius=200.0, half_life=1000.0):
    """平滑指數衰減評分（0.0~100.0，一位小數）：
    d <= full_radius 滿分；超過後按指數平滑遞減（half_life 米跌一半），
    消除硬性分段嘅「斷崖效應」（499m vs 501m 動輒差 10 分）。無數據返中位數 50。"""
    if dist_m is None:
        return 50.0
    if dist_m <= full_radius:
        return 100.0
    decay = math.log(2) / half_life
    return round(max(5.0, 100.0 * math.exp(-decay * (dist_m - full_radius))), 1)


def compute_living_circle_metrics(mtr_d, sch_d, sch_n800, kg_n800, care_d, care_n800,
                                  childcare_d, childcare_n800,
                                  elder_svc_d, shelter_d, hosp_d, elev_u, total_u):
    """生活圈評分 v3.3：五維標準化 0~100 後加權。
    小學 = 60% 最近距離 + 25% 800m 小學密度（5 間滿分）+ 15% 800m 幼稚園密度（3 間滿分）；
    託管 = 80% 最近距離 + 20% 密度（3 間滿分）；
    幼兒中心 = 80% 最近距離 + 20% 密度（3 間滿分）；
    長者/會堂 = 30% 最近長者服務（DEC/NEC/支援隊/DCUDECC）+ 40% 社區會堂（避暑中心）+ 30% 急症醫院；
    升降機 = 單位級覆蓋率 ×100。
    預設（育兒家庭）= 港鐵 35% + 小學 25% + 託管 10% + 幼兒中心 5% + 長者/會堂 10% + 升降機 15%。"""
    s_mtr = smooth_distance_score(mtr_d, 200, 900)
    s_sch = round(0.6 * smooth_distance_score(sch_d, 150, 800)
                  + 0.25 * min(1.0, (sch_n800 or 0) / 5.0) * 100.0
                  + 0.15 * min(1.0, (kg_n800 or 0) / 3.0) * 100.0, 1)
    s_care = round(0.8 * smooth_distance_score(care_d, 200, 1200)
                   + 0.2 * min(1.0, (care_n800 or 0) / 3.0) * 100.0, 1)
    s_childcare = round(0.8 * smooth_distance_score(childcare_d, 200, 1200)
                        + 0.2 * min(1.0, (childcare_n800 or 0) / 3.0) * 100.0, 1)
    s_elder = round(0.30 * smooth_distance_score(elder_svc_d, 200, 1000)
                    + 0.40 * smooth_distance_score(shelter_d, 200, 1000)
                    + 0.30 * smooth_distance_score(hosp_d, 300, 1500), 1)
    s_elev = round(elev_u / total_u * 100.0, 1) if total_u > 0 else 100.0
    score = round(0.35 * s_mtr + 0.25 * s_sch + 0.10 * s_care
                  + 0.05 * s_childcare + 0.10 * s_elder + 0.15 * s_elev, 1)
    return score, {"mtr": s_mtr, "school": s_sch, "care": s_care,
                   "childcare": s_childcare, "elderly_shelter": s_elder, "elevator": s_elev}


# ---------------- Part 1: PRH 18 區單位 → 屋邨級 ----------------
def stream_records(url, timeout=300):
    """下載大 JSON 並逐條解析（records 為平面物件，可安全按 '},{' 切分），避免 MemoryError。"""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
    i = raw.find('"records"')
    if i == -1:
        return []
    start = raw.find("[", i)
    end = raw.rfind("]")
    body = raw[start + 1:end]
    recs = []
    for chunk in re.split(r"\}\s*,\s*\{", body):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.startswith("{"):
            chunk = "{" + chunk
        if not chunk.endswith("}"):
            chunk = chunk + "}"
        try:
            recs.append(json.loads(chunk))
        except json.JSONDecodeError:
            pass
    return recs


def build_prh_estates():
    est = {}
    for i, L in enumerate(LETTERS, 1):
        try:
            recs = stream_records(DIST_URL.format(L))
        except Exception as e:
            print(f"  [{i}/18] {L} FAIL {type(e).__name__} {e}", flush=True)
            continue
        n_units = n_lift = 0
        for r in recs:
            key = (r.get("estate_chinese_name"), r.get("district_chinese_name"))
            e = est.setdefault(key, {
                "name_tc": r.get("estate_chinese_name") or "",
                "name_en": r.get("estate_english_name") or "",
                "district_tc": r.get("district_chinese_name") or "",
                "region_tc": r.get("region_chinese_name") or "",
                "lat": None, "lng": None, "blocks": set(),
                "total_units": 0, "elevator_units": 0,
                "floors": [], "areas": [], "blk": {}})
            lift = elevator_flag(r.get("avail_of_elevator_services"))
            e["total_units"] += 1
            n_units += 1
            if lift:
                e["elevator_units"] += 1
                n_lift += 1
            if r.get("chinese_name_of_block"):
                e["blocks"].add(r["chinese_name_of_block"])
            # 座別聚合（改善「揀樓前知呢座有冇𨋢」痛點）
            bn = (r.get("chinese_name_of_block") or "").strip() or "?"
            b = e["blk"].setdefault(bn, {"u": 0, "e": 0, "f": [], "a": []})
            b["u"] += 1
            if lift:
                b["e"] += 1
            try:
                b["f"].append(float(str(r.get("floor_number")).strip()))
            except (TypeError, ValueError):
                pass
            try:
                b["a"].append(float(r.get("internal_floor_area")))
            except (TypeError, ValueError):
                pass
            try:
                e["floors"].append(float(str(r.get("floor_number")).strip()))
            except (TypeError, ValueError):
                pass
            try:
                e["areas"].append(float(r.get("internal_floor_area")))
            except (TypeError, ValueError):
                pass
            if e["lat"] is None and r.get("estate_map_latitude"):
                e["lat"] = float(r["estate_map_latitude"])
                e["lng"] = float(r.get("estate_map_longitude"))
        print(f"  [{i}/18] {L}: {n_units} 單位 / {n_lift} 有升降機", flush=True)
    out = []
    for e in est.values():
        fl, ar = e["floors"], e["areas"]
        blocks = sorted(
            ({"n": bn, "u": b["u"], "e": b["e"],
              "f1": min(b["f"]) if b["f"] else None, "f2": max(b["f"]) if b["f"] else None,
              "a": round(sum(b["a"]) / len(b["a"]), 1) if b["a"] else None}
             for bn, b in e["blk"].items()),
            key=lambda x: -x["u"])
        out.append({
            "source": "PRH", "name_tc": e["name_tc"], "name_en": e["name_en"],
            "district_tc": e["district_tc"], "region_tc": e["region_tc"],
            "lat": e["lat"], "lng": e["lng"],
            "total_units": e["total_units"], "elevator_units": e["elevator_units"],
            "non_elevator_units": e["total_units"] - e["elevator_units"],
            "blocks_count": len(e["blocks"]),
            "min_floor": min(fl) if fl else None, "max_floor": max(fl) if fl else None,
            "avg_area": round(sum(ar) / len(ar), 2) if ar else None,
            "blocks": blocks})
    out.sort(key=lambda x: -x["total_units"])
    # 3 個新屋邨補座標（房委會單位檔無 estate_map_latitude）
    for e in out:
        if e["lat"] is None:
            patch = NEW_ESTATE_COORDS_PATCH.get(e["name_tc"])
            if patch:
                e["lat"], e["lng"] = patch["lat"], patch["lng"]
                e["coords_note"] = patch["note_tc"]
                print(f"  座標補全：{e['name_tc']} → {patch['lat']}, {patch['lng']}", flush=True)
    print(f"Part 1 完成：{len(out)} 個屋邨 / {sum(x['total_units'] for x in out):,} 個單位 / "
          f"{sum(len(x['blocks']) for x in out)} 座", flush=True)
    return out


# ---------------- Part 2: 小學 ----------------
def build_schools():
    d = fetch_json(SCHOOL_URL)
    arr = d if isinstance(d, list) else d.get("data") or list(d.values())[0]
    out = []
    for s in arr:
        level = str(s.get("學校類型") or s.get("SCHOOL LEVEL") or "")
        if "PRIMARY" not in level.upper() and "小學" not in level:
            continue
        try:
            lat = float(s.get("LATITUDE") or s.get("緯度"))
            lng = float(s.get("LONGITUDE") or s.get("經度"))
        except (TypeError, ValueError):
            continue
        if not (22.0 < lat < 22.7 and 113.7 < lng < 114.6):
            continue
        out.append({"zh": s.get("中文名稱") or s.get("ENGLISH NAME"),
                    "en": s.get("ENGLISH NAME"), "lat": lat, "lng": lng})
    print(f"Part 2 完成：{len(out)} 間小學（全部學校 {len(arr)}）", flush=True)
    return out


# ---------------- Part 3: 課後託管點 ----------------
def build_kindergartens():
    """EDB 同一份學校位置 JSON：幼稚園（AM/PM/全日 分開列 → 同名同座標去重）。"""
    d = fetch_json(SCHOOL_URL)
    arr = d if isinstance(d, list) else d.get("data") or list(d.values())[0]
    seen, out = set(), []
    for s in arr:
        cat = f'{s.get("ENGLISH CATEGORY", "")} {s.get("中文類別", "")}'
        if "KINDERGARTEN" not in cat.upper() and "幼稚園" not in cat:
            continue
        try:
            lat = float(s.get("LATITUDE") or s.get("緯度"))
            lng = float(s.get("LONGITUDE") or s.get("經度"))
        except (TypeError, ValueError):
            continue
        if not (22.0 < lat < 22.7 and 113.7 < lng < 114.6):
            continue
        name = s.get("中文名稱") or s.get("ENGLISH NAME")
        key = (name, round(lat, 4), round(lng, 4))
        if key in seen:
            continue
        seen.add(key)
        out.append({"zh": name, "en": s.get("ENGLISH NAME"), "lat": lat, "lng": lng})
    print(f"Part 2b 完成：{len(out)} 間幼稚園（去重後）", flush=True)
    return out


def dms_to_decimal(v):
    """LCSD 座標格式 '22-25-38'（度-分-秒）→ 十進制；已是十進制則直接回傳。"""
    s = str(v).strip()
    try:
        if "-" in s:
            parts = [float(x) for x in s.split("-")]
            if len(parts) == 3:
                return parts[0] + parts[1] / 60 + parts[2] / 3600
            if len(parts) == 2:
                return parts[0] + parts[1] / 60
        return float(s)
    except (TypeError, ValueError):
        return None


def build_playgrounds():
    """LCSD 共融遊樂場（facility-pefac.json，約 44 個，座標為 DMS）；快取 normalized。"""
    gj = None
    if os.path.exists(PLAYGROUND_CACHE):
        try:
            with open(PLAYGROUND_CACHE, encoding="utf-8") as f:
                gj = json.load(f)
        except Exception:
            gj = None
    if gj is None:
        try:
            gj = fetch_json(PLAYGROUND_URL, timeout=60)
        except Exception as e:
            print(f"Part 2c LCSD 遊樂場抓取失敗 {type(e).__name__}，跳過", flush=True)
            return []
        with open(PLAYGROUND_CACHE, "w", encoding="utf-8") as f:
            json.dump(gj, f, ensure_ascii=False)
    out = []
    for x in (gj if isinstance(gj, list) else []):
        lat = dms_to_decimal(x.get("Latitude"))
        lng = dms_to_decimal(x.get("Longitude"))
        if lat is None or lng is None or not (22.0 < lat < 22.7 and 113.7 < lng < 114.6):
            continue
        out.append({"zh": x.get("Name_cn") or x.get("Name_en"),
                    "en": x.get("Name_en"), "lat": lat, "lng": lng,
                    "district": x.get("District_cn") or ""})
    print(f"Part 2c 完成：{len(out)} 個 LCSD 共融遊樂場", flush=True)
    return out


def build_care():
    try:
        gj = fetch_json(CARE_URL)
    except Exception as e:
        print(f"Part 3 WFS FAIL: {type(e).__name__} {e}", flush=True)
        return []
    out = []
    for ft in gj.get("features", []):
        g = ft.get("geometry") or {}
        c = g.get("coordinates")
        if not c:
            continue
        p = ft.get("properties") or {}
        name = None
        for k, v in p.items():
            if "name" in k.lower() and isinstance(v, str) and v.strip():
                name = v.strip() if name is None or len(v) < len(name) else name
        if name is None:
            name = ";".join(str(v) for v in list(p.values())[:2])
        out.append({"zh": name, "lat": float(c[1]), "lng": float(c[0])})
    print(f"Part 3 完成：{len(out)} 個在校課後託管服務點", flush=True)
    return out


# ---------------- Part 4: 港鐵 + 合併評分 ----------------
def nearest_point_on_rings(rings, lat, lng):
    """GeoJSON 多邊形 rings（[lng,lat] 頂點）上距 (lat,lng) 最近嘅點（點到線段投影）。
    返回 (lat, lng, dist_m)。bbox 中心可能跌入站體範圍令行人網絡 snap 唔到
    （實例：天耀一邨→天水圍站 bbox 中心 'No route'，邊界最近點 193m OK）。"""
    cosL = math.cos(math.radians(lat))
    best = (None, None, 1e18)
    for r in rings:
        for i in range(len(r) - 1):
            x1, y1 = r[i][0], r[i][1]        # lng, lat
            x2, y2 = r[i+1][0], r[i+1][1]
            dx = (x2 - x1) * 111320.0 * cosL
            dy = (y2 - y1) * 110574.0
            px = (lng - x1) * 111320.0 * cosL
            py = (lat - y1) * 110574.0
            L2 = dx*dx + dy*dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px*dx + py*dy) / L2))
            qx = x1 + t * (x2 - x1)
            qy = y1 + t * (y2 - y1)
            d = haversine(lat, lng, qy, qx)
            if d < best[2]:
                best = (qy, qx, d)
    return best


def build_mtr_venues():
    path = MTR_PATH if os.path.exists(MTR_PATH) else MTR_FALLBACK
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    out = []
    for ft in gj["features"]:
        p = ft["properties"]
        bbox = p.get("bbox") or ft["geometry"].get("bbox")
        if not bbox:
            continue
        g = ft["geometry"]
        rings = []
        if g.get("type") == "Polygon":
            rings = g["coordinates"]
        elif g.get("type") == "MultiPolygon":
            rings = [r for poly in g["coordinates"] for r in poly]
        out.append({"zh": p.get("venue_name_zh"), "en": p.get("venue_name_en"),
                    "lat": (bbox[1] + bbox[3]) / 2, "lng": (bbox[0] + bbox[2]) / 2,
                    "rings": rings})
    print(f"Part 4a：{len(out)} 個港鐵場地", flush=True)
    return out


def nearest_mtr_precise(lat, lng, venues, coarse=5):
    """先以 bbox 中心粗排，再以多邊形邊界最近點精算。
    返回 (錨點 dict, 800m 內場地數)。錨點 dict 與管線 nearest_mtr schema 一致。"""
    if lat is None or not venues:
        return None, 0
    ranked = sorted(venues, key=lambda v: haversine(lat, lng, v["lat"], v["lng"]))[:coarse]
    cnt = sum(1 for v in venues if haversine(lat, lng, v["lat"], v["lng"]) <= 800)
    best, best_v = None, None
    for v in ranked:
        q = nearest_point_on_rings(v["rings"], lat, lng) if v.get("rings") \
            else (v["lat"], v["lng"], haversine(lat, lng, v["lat"], v["lng"]))
        if best is None or q[2] < best[2]:
            best, best_v = q, v
    return ({"zh": best_v["zh"], "en": best_v["en"], "lat": best[0], "lng": best[1],
             "distance_m": int(best[2])}, cnt) if best else (None, cnt)


# ---------------- Part 5: CSDI 新數據集（長者日間護理／社區會堂／避暑中心／無障礙設施） ----------------
NAME_KEYS_TC = ["NameTC", "NAME_TC", "NAME_ZH", "CHI_NAME", "FACILITY_NAME_TC", "名稱", "中心名稱", "會堂名稱"]
NAME_KEYS_EN = ["NameEN", "NAME_EN", "ENG_NAME", "FACILITY_NAME_EN"]


def pick_name(p, keys):
    for k in keys:
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def fetch_csdi_geojson(spec):
    """file-api（已知 layer）→ FeatureServer（f=geojson, outSR=4326）→ static fallback；成功即存 raw。"""
    did, layer = spec["dataset_id"], spec.get("layer")
    urls = []
    if layer:
        urls.append(f"https://portal.csdi.gov.hk/csdi-webpage/file-api?dataset_id={did}&format=geojson&layer_name={layer}")
    urls.append(f"https://portal.csdi.gov.hk/server/rest/services/common/{did}/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson")
    if spec.get("static"):
        urls.append(spec["static"])
    for u in urls:
        try:
            gj = fetch_json(u, timeout=90)
            if isinstance(gj, dict) and gj.get("features"):
                with open(os.path.join(RAW, spec["save_as"]), "w", encoding="utf-8") as f:
                    json.dump(gj, f, ensure_ascii=False)
                return gj
        except Exception:
            continue
    print(f"    CSDI {did} 全部來源失敗", flush=True)
    return {"features": []}


def parse_facilities(gj, accessible=False):
    """動態鍵名解析（兼容 2026-10 民政署欄位改名）；座標統一 WGS84（outSR=4326 / file-api 已轉）。"""
    out = []
    for ft in gj.get("features", []):
        p = ft.get("properties") or {}
        zh = pick_name(p, NAME_KEYS_TC) or pick_name(p, NAME_KEYS_EN)
        en = pick_name(p, NAME_KEYS_EN) or zh
        g = ft.get("geometry") or {}
        lat = lng = None
        c = g.get("coordinates")
        if g.get("type") == "Point" and c and len(c) >= 2:
            x, y = float(c[0]), float(c[1])
            if -180 <= x <= 180 and -90 <= y <= 90:      # WGS84 直接可用
                lng, lat = x, y
            elif x > 800000 and y > 800000:              # HK1980 網格（罕見）→ 交由屬性 Latitude/Longitude
                lat = lng = None
        if lat is None:
            try:
                lat, lng = float(p.get("Latitude")), float(p.get("Longitude"))
            except (TypeError, ValueError):
                pass
        if not zh or lat is None:
            continue
        item = {"zh": zh, "en": en, "lat": lat, "lng": lng,
                "district": p.get("DistrictTC") or p.get("DistrictEN") or ""}
        if accessible:
            item["accessible"] = any(
                str(p.get(k, "")).strip().upper() not in ("", "N", "NO", "否", "沒有", "無")
                for k in ("AccessibleLiftTC", "AccessibleToiletTC", "AccessibleEntranceExitTC", "AccessibleCarparkTC"))
        out.append(item)
    return out


def build_community():
    """長者日間護理單位 + 社區會堂（合併避暑中心／無障礙設施標記）。"""
    elderly = parse_facilities(fetch_csdi_geojson(CSDI_DATASETS["elderly"]))
    halls = parse_facilities(fetch_csdi_geojson(CSDI_DATASETS["halls"]))
    shelters = parse_facilities(fetch_csdi_geojson(CSDI_DATASETS["shelters"]))
    barrier = parse_facilities(fetch_csdi_geojson(CSDI_DATASETS["barrierfree"]), accessible=True)
    shelter_names = {f["zh"] for f in shelters}
    acc_map = {f["zh"]: f.get("accessible") for f in barrier}
    n_shelter_hit = 0
    for h in halls:
        h["heat_shelter"] = h["zh"] in shelter_names
        if h["heat_shelter"]:
            n_shelter_hit += 1
        h["accessible"] = acc_map.get(h["zh"])
    print(f"Part 5 完成：{len(elderly)} 個長者日間護理單位 / {len(halls)} 個社區會堂"
          f"（{n_shelter_hit} 個避暑中心配對、{len(barrier)} 個無障礙設施記錄）", flush=True)
    return elderly, halls


HOSPITAL_CACHE = os.path.join(RAW, "osm_hospitals.json")
SZ_SKIP = ("深圳市", "罗湖", "人民医院", "远东", "希思", "盐田", "福田", "南山", "宝安", "龙岗", "珠海", "广州")


def build_hospitals():
    """醫院及急症室：OSM Overpass（amenity=hospital，emergency=yes 即設急症室）。
    醫管局無公開設施座標（CSDI 無 ha 圖層、DATA.GOV.HK 只有統計），故用 OSM（ODbL）。
    快取 data/raw/osm_hospitals.json；抓取失敗回 []（評分該維度退中位數）。"""
    if os.path.exists(HOSPITAL_CACHE):
        with open(HOSPITAL_CACHE, encoding="utf-8") as f:
            return json.load(f)
    q = ('[out:json][timeout:60];(node["amenity"="hospital"](22.15,113.83,22.56,114.45);'
         'way["amenity"="hospital"](22.15,113.83,22.56,114.45););out center tags 400;')
    d = None
    for attempt in range(3):
        try:
            d = fetch_json("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(q), timeout=90)
            break
        except Exception as e:
            if attempt < 2:
                print(f"Part 6 OSM 重試 {attempt+1}/2（{type(e).__name__}）…", flush=True)
                time.sleep(4 * (attempt + 1))
            else:
                print(f"Part 6 OSM 醫院抓取失敗 {type(e).__name__}，跳過", flush=True)
    if d is None:
        return []
    out = []
    for el in d.get("elements", []):
        t = el.get("tags") or {}
        nm = (t.get("name") or "").strip()
        if not nm or any(s in nm for s in SZ_SKIP):
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or not (22.15 < lat < 22.56 and 113.83 < lng < 114.45):
            continue
        zh = nm.split(" ")[0] if any("\u4e00" <= ch <= "\u9fff" for ch in nm) else nm
        out.append({"zh": zh, "en": nm, "lat": float(lat), "lng": float(lng),
                    "ae": str(t.get("emergency", "")).lower() == "yes"})
    with open(HOSPITAL_CACHE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"Part 6 完成：{len(out)} 間醫院（{sum(1 for x in out if x['ae'])} 間設急症室）", flush=True)
    return out


def build_childcare():
    """幼兒中心組合（0–6 歲）：附設幼稚園資助 243＋資助獨立 21＋私營非牟利 14＋殘疾暫託 48。"""
    pool, seen = [], set()
    for spec in CHILDCARE_DATASETS:
        for f in parse_facilities(fetch_csdi_geojson(spec)):
            key = (f["zh"], round(f["lat"], 4), round(f["lng"], 4))
            if key in seen:
                continue
            seen.add(key)
            pool.append(f)
    print(f"Part 7 完成：{len(pool)} 個幼兒中心（0–6 歲組合）", flush=True)
    return pool


def build_elder_services():
    """長者服務組合：長者地區中心 62＋長者鄰舍中心 216＋長者支援服務隊 64（另加 DCUDECC 3）。"""
    pool, seen = [], set()
    for spec in ELDER_DATASETS:
        for f in parse_facilities(fetch_csdi_geojson(spec)):
            key = (f["zh"], round(f["lat"], 4), round(f["lng"], 4))
            if key in seen:
                continue
            seen.add(key)
            pool.append(f)
    print(f"Part 7 完成：{len(pool)} 個長者服務點（地區中心／鄰舍中心／支援隊）", flush=True)
    return pool


def main():
    prh = build_prh_estates()
    schools = build_schools()
    kgs = build_kindergartens()
    pgs = build_playgrounds()
    care = build_care()
    mtr = build_mtr_venues()
    elderly, halls = build_community()
    elderly_all = elderly + build_elder_services()      # 345 點：DCUDECC＋DEC＋NEC＋支援隊
    childcare = build_childcare()                       # 326 點：0–6 歲幼兒中心組合
    hospitals = build_hospitals()
    ae_hospitals = [h for h in hospitals if h.get("ae")]

    # 託管點池快取（供 build_app.py／日後前端密度展示用）
    with open(os.path.join(NORM, "swd_care_points.json"), "w", encoding="utf-8") as f:
        json.dump(care, f, ensure_ascii=False)

    # LPH 座別聚合（由 Stage 1 單位級 CSV）
    lph_blocks = {}
    with open(os.path.join(NORM, "lph_units.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            k = (r["project_tc"], (r.get("block_tc") or "").strip() or "?")
            b = lph_blocks.setdefault(k, {"u": 0, "e": 0, "f": [], "a": []})
            b["u"] += 1
            if str(r.get("elevator", "")).strip().upper() == "Y":
                b["e"] += 1
            try:
                b["f"].append(float(r.get("floor_num")))
            except (TypeError, ValueError):
                pass
            try:
                b["a"].append(float(r.get("internal_floor_area")))
            except (TypeError, ValueError):
                pass

    # LPH 10 項目（用現有 summary CSV）
    lph = []
    with open(os.path.join(NORM, "lph_projects_summary.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            lph.append({"source": "LPH", "name_tc": r["project_tc"], "name_en": r["project_en"],
                        "district_tc": r["district_tc"], "region_tc": r["region_tc"],
                        "lat": float(r["lat"]), "lng": float(r["lng"]),
                        "total_units": int(r["total_units"]), "elevator_units": int(r["elevator_units"]),
                        "non_elevator_units": int(r["non_elevator_units"]),
                        "blocks_count": int(r["blocks_count"]),
                        "min_floor": float(r["min_floor"]), "max_floor": float(r["max_floor"]),
                        "avg_area": float(r["avg_internal_area"]),
                        "blocks": sorted(
                            ({"n": bn, "u": b["u"], "e": b["e"],
                              "f1": min(b["f"]) if b["f"] else None,
                              "f2": max(b["f"]) if b["f"] else None,
                              "a": round(sum(b["a"]) / len(b["a"]), 1) if b["a"] else None}
                             for (ptc, bn), b in lph_blocks.items() if ptc == r["project_tc"]),
                            key=lambda x: -x["u"])})

    all_est = lph + prh
    for e in all_est:
        m, mn = nearest_mtr_precise(e["lat"], e["lng"], mtr)
        s, sn = nearest_and_count(e["lat"], e["lng"], schools)
        kg, kgn = nearest_and_count(e["lat"], e["lng"], kgs)
        pg, pgn = nearest_and_count(e["lat"], e["lng"], pgs)
        c, cn = nearest_and_count(e["lat"], e["lng"], care)
        cc, ccn = nearest_and_count(e["lat"], e["lng"], childcare)
        el, eln = nearest_and_count(e["lat"], e["lng"], elderly_all)
        sh, shn = nearest_and_count(e["lat"], e["lng"], halls)
        ae, aen = nearest_and_count(e["lat"], e["lng"], ae_hospitals)
        hp, hpn = nearest_and_count(e["lat"], e["lng"], hospitals)
        e["nearest_mtr"] = dict(m, count_800m=mn) if m else None
        e["nearest_school"] = {"zh": s["item"]["zh"], "en": s["item"].get("en"),
                               "lat": s["item"]["lat"], "lng": s["item"]["lng"],
                               "distance_m": s["distance_m"], "count_800m": sn} if s else None
        e["kindergartens_800m"] = kgn
        e["nearest_kg_dist_m"] = kg["distance_m"] if kg else None
        e["nearest_kg_name_tc"] = kg["item"]["zh"] if kg else None
        e["nearest_kg_lat"] = kg["item"]["lat"] if kg else None
        e["nearest_kg_lng"] = kg["item"]["lng"] if kg else None
        e["playgrounds_800m"] = pgn
        e["nearest_pg_dist_m"] = pg["distance_m"] if pg else None
        e["nearest_pg_name_tc"] = pg["item"]["zh"] if pg else None
        e["nearest_pg_lat"] = pg["item"]["lat"] if pg else None
        e["nearest_pg_lng"] = pg["item"]["lng"] if pg else None
        e["nearest_care"] = {"zh": c["item"]["zh"], "lat": c["item"]["lat"], "lng": c["item"]["lng"],
                             "distance_m": c["distance_m"], "count_800m": cn} if c else None
        e["nearest_childcare"] = {"zh": cc["item"]["zh"], "lat": cc["item"]["lat"], "lng": cc["item"]["lng"],
                                  "distance_m": cc["distance_m"], "count_800m": ccn} if cc else None
        e["nearest_elderly"] = {"zh": el["item"]["zh"], "en": el["item"].get("en"),
                                "lat": el["item"]["lat"], "lng": el["item"]["lng"],
                                "distance_m": el["distance_m"], "count_800m": eln} if el else None
        e["nearest_shelter"] = {"zh": sh["item"]["zh"], "en": sh["item"].get("en"),
                                "lat": sh["item"]["lat"], "lng": sh["item"]["lng"],
                                "distance_m": sh["distance_m"], "count_800m": shn,
                                "heat_shelter": bool(sh["item"].get("heat_shelter")),
                                "accessible": sh["item"].get("accessible")} if sh else None
        e["nearest_ae_hospital"] = {"zh": ae["item"]["zh"], "lat": ae["item"]["lat"],
                                    "lng": ae["item"]["lng"], "distance_m": ae["distance_m"],
                                    "count_800m": aen} if ae else None
        e["nearest_hospital"] = {"zh": hp["item"]["zh"], "lat": hp["item"]["lat"],
                                 "lng": hp["item"]["lng"], "distance_m": hp["distance_m"],
                                 "ae": bool(hp["item"].get("ae"))} if hp else None
        e["score"], e["sub_scores"] = compute_living_circle_metrics(
            m["distance_m"] if m else None,
            s["distance_m"] if s else None, sn, kgn,
            c["distance_m"] if c else None, cn,
            cc["distance_m"] if cc else None, ccn,
            el["distance_m"] if el else None,
            sh["distance_m"] if sh else None,
            ae["distance_m"] if ae else None,
            e["elevator_units"], e["total_units"])
        e["density_800m"] = {"schools": sn, "cares": cn, "childcare": ccn}
    all_est.sort(key=lambda x: (-x["score"], -(x["total_units"] or 0)))

    dst = os.path.join(NORM, "all_estates_enriched.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(all_est, f, ensure_ascii=False)
    print(f"SAVED {os.path.relpath(dst, BASE)}  ({len(all_est)} 筆)", flush=True)

    # 統計
    sc = [x for x in all_est if x["score"] is not None]
    top = sc[:10]
    print("\n=== 生活圈評分 v3 Top 10 ===")
    for e in top:
        print(f'{e["score"]:>5} 分｜{e["name_tc"]}（{e["district_tc"]}）{e["total_units"]:,} 單位｜'
              f'港鐵 {e["nearest_mtr"]["distance_m"]}m｜小學 {e["nearest_school"]["distance_m"] if e["nearest_school"] else "-"}m｜'
              f'託管 {e["nearest_care"]["distance_m"] if e["nearest_care"] else "-"}m｜'
              f'升降機 {e["sub_scores"]["elevator"]}%')
    full = sum(1 for x in sc if x["score"] >= 99.95)
    print(f"\n滿分（≥99.95）屋邨數：{full} / {len(sc)}（v2 tier 制曾經幾十個並列 100）")


if __name__ == "__main__":
    main()
