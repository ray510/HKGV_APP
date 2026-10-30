# -*- coding: utf-8 -*-
"""為「有座別但冇座標」嘅座補圖釘。

三層：
 1. 地政總署 bbox（450m）Tower 質心，按座名比對（完全同名 → 包含關係）
 2. 同名失敗 → 用層數＋距離配對（est=1，估算）
 3. 仍然配唔到 → 喺屋苑現有座釘嘅幾何中心／普查界線內，用確定性環形排位（est=2，純估算）

輸出：data/normalized/block_pin_fill.json
      key = "source|屋苑名|座名" → {"lat","lng","est"}
"""
import json, math, os, re, sys, urllib.parse, urllib.request, collections

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "normalized", "block_pin_fill.json")
URL = ("https://portal.csdi.gov.hk/server/rest/services/common/"
       "landsd_rcd_1637211194312_35158/FeatureServer/0/query")
POLY = os.path.join(BASE, "data", "normalized", "censtatd_estate_polygons.json")
R = 450


def hav(a, b, c, d):
    Rr = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * Rr * math.asin(math.sqrt(x))


CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def cn2int(s):
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + CN.get(s[1], 0)
    if "十" in s:
        a, b = s.split("十", 1)
        return CN.get(a, 0) * 10 + (CN.get(b, 0) if b else 0)
    return CN.get(s)


def norm(s):
    s = (s or "").strip().replace("　", "")
    s = s.replace("（", "(").replace("）", ")").replace("．", ".")
    for fw, hw in zip("０１２３４５６７８９", "0123456789"):
        s = s.replace(fw, hw)
    for fw, hw in zip("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
                      "ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        s = s.replace(fw, hw)
    return s


def key_form(s):
    """「第四十四座」→「44」、「第4座」→「4」、「Ａ座」→「A」。"""
    s = norm(s)
    m = re.fullmatch(r"第?([0-9]+|[一二三四五六七八九十]+)座", s)
    if m:
        return f"#{cn2int(m.group(1))}"
    m = re.fullmatch(r"([A-Z])座", s)
    if m:
        return f"#{m.group(1)}"
    return s


def near(lat, lng, meters=R, limit=250):
    p = {"where": "BuildingBlockType='Tower' AND BuildingNameTC IS NOT NULL",
         "geometry": json.dumps({"x": lng, "y": lat, "spatialReference": {"wkid": 4326}}),
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "distance": meters, "units": "esriSRUnit_Meter",
         "spatialRel": "esriSpatialRelIntersects",
         "outFields": "BuildingNameTC,Storeys,TopHeight",
         "returnGeometry": "true", "returnCentroid": "true", "outSR": 4326,
         "resultRecordCount": limit, "f": "json"}
    url = URL + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": "HKGV/1.0"})
    for i in range(3):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"))
        except Exception:
            if i == 2:
                return {}
    return {}


def ring_points(clat, clng, n, fixed):
    """喺屋苑現有座釘之間嘅空隙擺位：半徑＝現有座釘平均距離，角度逐個揀最空曠嘅。"""
    if fixed:
        rs = [hav(clat, clng, p[0], p[1]) for p in fixed]
        radius = max(35.0, min(160.0, sum(rs) / len(rs)))
    else:
        radius = 60.0
    pts, ref = [], list(fixed)
    for _ in range(n):
        best, bd = None, -1.0
        for a in range(0, 360, 10):
            ang = math.radians(a)
            la = clat + radius * math.cos(ang) / 111320.0
            lo = clng + radius * math.sin(ang) / (111320.0 * math.cos(math.radians(clat)))
            d = min([hav(la, lo, p[0], p[1]) for p in ref] or [1e9])
            if d > bd:
                bd, best = d, (la, lo)
        pts.append(best)
        ref.append(best)
    return pts


def main():
    H = open(os.path.join(BASE, "index.html"), encoding="utf-8").read()
    i = H.find("const DATA = ") + 13
    j = H.find(";\nconst COVERED", i)
    D = json.loads(H[i:j])

    cache = {}
    if os.path.exists(OUT):
        cache = json.load(open(OUT, encoding="utf-8"))

    todo = [e for e in D if any(b.get("lat") is None for b in (e.get("blocks") or []))]
    print(f"缺座標屋苑 {len(todo)} 個", flush=True)

    n_name = n_storey = n_ring = 0
    for e in todo:
        missing = [b for b in e["blocks"] if b.get("lat") is None]
        if not missing:
            continue
        fixed = [(b["lat"], b["lng"]) for b in e["blocks"] if b.get("lat") is not None]
        clat = sum(p[0] for p in fixed) / len(fixed) if fixed else e["lat"]
        clng = sum(p[1] for p in fixed) / len(fixed) if fixed else e["lng"]

        towers = []
        for f in (near(e["lat"], e["lng"]).get("features") or []):
            a, c = f.get("attributes") or {}, f.get("centroid") or {}
            if c.get("y") is None or not a.get("BuildingNameTC"):
                continue
            if any(hav(c["y"], c["x"], p[0], p[1]) < 25 for p in fixed):
                continue          # 已經有座釘嘅樓，唔重用
            towers.append({"n": a["BuildingNameTC"], "s": a.get("Storeys"),
                           "lat": c["y"], "lng": c["x"]})

        used = set()
        rest = []
        # 1) 名稱比對
        for b in missing:
            k = key_form(b["n"])
            hit = None
            for t in towers:
                if t["n"] in used:
                    continue
                if key_form(t["n"]) == k or (len(k) >= 3 and (k in t["n"] or t["n"] in k)):
                    hit = t
                    break
            if hit:
                used.add(hit["n"])
                cache[f'{e["source"]}|{e["name_tc"]}|{b["n"]}'] = {
                    "lat": round(hit["lat"], 6), "lng": round(hit["lng"], 6), "est": 0}
                n_name += 1
            else:
                rest.append(b)

        # 2) 同前綴＋樓／閣／臺 異名（俊禮樓 ↔ 俊禮閣），距離 <250m
        still2 = []
        for b in rest:
            kb = key_form(b["n"])
            hit, hd = None, 1e9
            for t in towers:
                if t["n"] in used or len(kb) < 2:
                    continue
                kt = key_form(t["n"])
                if kt[:2] != kb[:2] or kt == kb:
                    continue
                if kb[-1] in "樓閣臺台軒苑" and kt[-1] in "樓閣臺台軒苑":
                    d = hav(clat, clng, t["lat"], t["lng"])
                    if d < 250 and d < hd:
                        hit, hd = t, d
            if hit:
                used.add(hit["n"])
                cache[f'{e["source"]}|{e["name_tc"]}|{b["n"]}'] = {
                    "lat": round(hit["lat"], 6), "lng": round(hit["lng"], 6), "est": 1}
                n_storey += 1
            else:
                still2.append(b)

        # 3) 層數＋距離配對
        still = []
        for b in still2:
            best, bd = None, 1e9
            for t in towers:
                if t["n"] in used or not b.get("s") or not t.get("s"):
                    continue
                if abs(t["s"] - b["s"]) > 1:
                    continue
                d = hav(clat, clng, t["lat"], t["lng"])
                if d < bd:
                    best, bd = t, d
            if best and bd < 350:
                used.add(best["n"])
                cache[f'{e["source"]}|{e["name_tc"]}|{b["n"]}'] = {
                    "lat": round(best["lat"], 6), "lng": round(best["lng"], 6), "est": 1}
                n_storey += 1
            else:
                still.append(b)

        # 4) 環形排位（確定性）
        if still:
            pts = ring_points(clat, clng, len(still), fixed)
            for b, (la, lo) in zip(still, pts):
                cache[f'{e["source"]}|{e["name_tc"]}|{b["n"]}'] = {
                    "lat": round(la, 6), "lng": round(lo, 6), "est": 2}
                n_ring += 1
        cnt = collections.Counter()
        for b in missing:
            v = cache.get(f'{e["source"]}|{e["name_tc"]}|{b["n"]}')
            if v:
                cnt[v["est"]] += 1
        print(f"  {e['name_tc']}: 名 {cnt[0]} 層 {cnt[1]} 環 {cnt[2]}", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n寫入 {len(cache)} 筆（名 {n_name}／層 {n_storey}／環 {n_ring}）→ {OUT}", flush=True)


if __name__ == "__main__":
    main()
