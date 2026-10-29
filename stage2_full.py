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
CARE_URL = ("https://portal.csdi.gov.hk/server/services/common/swd_rcd_1727429602437_81314/MapServer/WFSServer"
            "?service=wfs&version=2.0.0&request=GetFeature&typename=csdi:SWDSBAEPS&outputFormat=GEOJSON")
MTR_PATH = os.path.join(NORM, "mtr_venue_polygon.json")
MTR_FALLBACK = os.path.join(BASE, "data", "raw", "mtr_venue_polygon.json")


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


def compute_living_circle_metrics(mtr_d, sch_d, sch_n800, care_d, care_n800, elev_u, total_u):
    """生活圈評分 v3：各維度標準化 0~100 後加權。
    小學 = 70% 最近距離 + 30% 800m 內選擇密度（5 間滿分）；
    託管 = 80% 最近距離 + 20% 密度（3 間滿分）；
    升降機 = 單位級覆蓋率 ×100。預設（育兒家庭）= 港鐵 35% + 小學 30% + 託管 20% + 升降機 15%。"""
    s_mtr = smooth_distance_score(mtr_d, 200, 900)
    s_sch = round(0.7 * smooth_distance_score(sch_d, 150, 800)
                  + 0.3 * min(1.0, (sch_n800 or 0) / 5.0) * 100.0, 1)
    s_care = round(0.8 * smooth_distance_score(care_d, 200, 1200)
                   + 0.2 * min(1.0, (care_n800 or 0) / 3.0) * 100.0, 1)
    s_elev = round(elev_u / total_u * 100.0, 1) if total_u > 0 else 100.0
    score = round(0.35 * s_mtr + 0.30 * s_sch + 0.20 * s_care + 0.15 * s_elev, 1)
    return score, {"mtr": s_mtr, "school": s_sch, "care": s_care, "elevator": s_elev}


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
                "floors": [], "areas": []})
            lift = elevator_flag(r.get("avail_of_elevator_services"))
            e["total_units"] += 1
            n_units += 1
            if lift:
                e["elevator_units"] += 1
                n_lift += 1
            if r.get("chinese_name_of_block"):
                e["blocks"].add(r["chinese_name_of_block"])
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
        out.append({
            "source": "PRH", "name_tc": e["name_tc"], "name_en": e["name_en"],
            "district_tc": e["district_tc"], "region_tc": e["region_tc"],
            "lat": e["lat"], "lng": e["lng"],
            "total_units": e["total_units"], "elevator_units": e["elevator_units"],
            "non_elevator_units": e["total_units"] - e["elevator_units"],
            "blocks_count": len(e["blocks"]),
            "min_floor": min(fl) if fl else None, "max_floor": max(fl) if fl else None,
            "avg_area": round(sum(ar) / len(ar), 2) if ar else None})
    out.sort(key=lambda x: -x["total_units"])
    print(f"Part 1 完成：{len(out)} 個屋邨 / {sum(x['total_units'] for x in out):,} 個單位", flush=True)
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


def main():
    prh = build_prh_estates()
    schools = build_schools()
    care = build_care()
    mtr = build_mtr_venues()

    # 託管點池快取（供 build_app.py／日後前端密度展示用）
    with open(os.path.join(NORM, "swd_care_points.json"), "w", encoding="utf-8") as f:
        json.dump(care, f, ensure_ascii=False)

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
                        "avg_area": float(r["avg_internal_area"])})

    all_est = lph + prh
    for e in all_est:
        m, mn = nearest_mtr_precise(e["lat"], e["lng"], mtr)
        s, sn = nearest_and_count(e["lat"], e["lng"], schools)
        c, cn = nearest_and_count(e["lat"], e["lng"], care)
        e["nearest_mtr"] = m
        e["nearest_school"] = {"zh": s["item"]["zh"], "en": s["item"].get("en"),
                               "lat": s["item"]["lat"], "lng": s["item"]["lng"],
                               "distance_m": s["distance_m"]} if s else None
        e["nearest_care"] = {"zh": c["item"]["zh"], "distance_m": c["distance_m"]} if c else None
        e["score"], e["sub_scores"] = compute_living_circle_metrics(
            m["distance_m"] if m else None,
            s["distance_m"] if s else None, sn,
            c["distance_m"] if c else None, cn,
            e["elevator_units"], e["total_units"])
        e["density_800m"] = {"schools": sn, "cares": cn}
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
