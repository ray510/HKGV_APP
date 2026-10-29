# -*- coding: utf-8 -*-
"""全港 258 邨座級定位覆蓋率實測：
地政總署「建築物」多邊形（Tower+有名）× 管線座名匹配 → centroid
輸出: data/normalized/csdi_block_coords.json + csdi_coverage_result.json
"""
import urllib.request, urllib.parse, json, time, sys, re

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
FS_B = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637211194312_35158/FeatureServer"

def get(u, timeout=60):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout).read())

FW = str.maketrans("０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ（）", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz()")

def norm(s):
    if not s:
        return ""
    s = s.translate(FW)
    s = re.sub(r"\s+", "", s)
    return s.upper()

def centroid(feat):
    rings = (feat.get("geometry") or {}).get("rings") or []
    pts = [p for ring in rings for p in ring]
    if not pts:
        return None
    return (sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts))

estates = json.load(open("data/normalized/all_estates_enriched.json", encoding="utf-8"))

cache = {}
stats = {"estates": 0, "estates_with_match": 0, "blocks_total": 0, "blocks_matched": 0,
         "blocks_matched_tower": 0, "generic_total": 0, "generic_matched": 0,
         "lph_estates": 0, "lph_matched_estates": 0, "unmatched_sample": [], "errors": []}

WHERE = "BuildingBlockType='Tower' AND BuildingNameTC IS NOT NULL"
t0 = time.time()
for idx, e in enumerate(estates):
    src, name = e["source"], e["name_tc"]
    lat, lng = e.get("lat"), e.get("lng")
    blocks = e.get("blocks") or []
    stats["estates"] += 1
    stats["blocks_total"] += len(blocks)
    if src == "LPH":
        stats["lph_estates"] += 1
    if lat is None or not blocks:
        continue
    # 500m bbox
    dlat, dlng = 0.0045, 0.0049
    env = f"{lng-dlng:.6f},{lat-dlat:.6f},{lng+dlng:.6f},{lat+dlat:.6f}"
    q = (f"{FS_B}/0/query?where={urllib.parse.quote(WHERE)}"
         f"&geometry={env}&geometryType=esriGeometryEnvelope&inSR=4326"
         f"&spatialRel=esriSpatialRelIntersects"
         f"&outFields=BuildingNameTC,BuildingCSUID,Storeys,Shape__Area"
         f"&returnGeometry=true&maxAllowableOffset=0.0002"
         f"&resultRecordCount=300&outSR=4326&f=json")
    try:
        d = get(q)
    except Exception as ex:
        try:
            time.sleep(1.0)
            d = get(q, timeout=90)
        except Exception as ex2:
            stats["errors"].append(f"{name}: {str(ex2)[:80]}")
            continue
    feats = d.get("features", [])
    # build lookup: normalized landsd name -> best (largest area) feature
    landsd = {}
    for f in feats:
        a = f.get("attributes", {})
        nm = norm(a.get("BuildingNameTC"))
        if not nm:
            continue
        area = a.get("Shape__Area") or 0
        if nm not in landsd or area > landsd[nm][0]:
            landsd[nm] = (area, a, f)
    matched_here = 0
    for b in blocks:
        bn = norm(b.get("n", ""))
        key = f"{src}|{name}|{b.get('n','')}"
        if not bn:
            continue
        is_generic = ("座" in b.get("n", "")) and ("樓" not in b.get("n", "")) and len(b.get("n", "")) <= 6
        if is_generic:
            stats["generic_total"] += 1
        hit = None
        if bn in landsd:
            hit = landsd[bn]
        else:
            # fallback: landsd name ends with pipeline name (estate-prefixed)
            for nm, v in landsd.items():
                if nm.endswith(bn) and len(bn) >= 2:
                    hit = v
                    break
        if hit:
            area, a, f = hit
            c = centroid(f)
            if c:
                cache[key] = {"lat": round(c[0], 6), "lng": round(c[1], 6),
                              "csuid": a.get("BuildingCSUID", ""), "storeys": a.get("Storeys"),
                              "landsd_name": a.get("BuildingNameTC")}
                stats["blocks_matched"] += 1
                matched_here += 1
                if is_generic:
                    stats["generic_matched"] += 1
                if not stats["blocks_matched_tower"] or matched_here == 1:
                    pass
        else:
            if len(stats["unmatched_sample"]) < 40:
                stats["unmatched_sample"].append(f"{name}｜{b.get('n','')}")
    if matched_here:
        stats["estates_with_match"] += 1
        if src == "LPH":
            stats["lph_matched_estates"] += 1
    if idx % 40 == 0:
        sys.stderr.write(f"[{idx}/258] {time.time()-t0:.0f}s matched={stats['blocks_matched']}\n")
    time.sleep(0.12)

json.dump(cache, open("data/normalized/csdi_block_coords.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
stats["elapsed_s"] = round(time.time() - t0, 1)
json.dump(stats, open("csdi_coverage_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(stats, ensure_ascii=False, indent=2))
