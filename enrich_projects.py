# -*- coding: utf-8 -*-
"""為 10 個簡約公屋項目計算最近港鐵站（用 mtr_venue_polygon bbox 中心），輸出 enriched JSON。"""
import csv, json, math, os

BASE = os.path.dirname(os.path.abspath(__file__))


def haversine(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


venues = []
with open(os.path.join(BASE, "data", "raw", "mtr_venue_polygon.json"), encoding="utf-8") as f:
    gj = json.load(f)
for ft in gj["features"]:
    p = ft["properties"]
    bbox = p.get("bbox") or ft["geometry"].get("bbox")
    if not bbox:
        continue  # [xmin, ymin, xmax, ymax] -> 中心
    clat, clng = (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2
    venues.append({"zh": p.get("venue_name_zh"), "en": p.get("venue_name_en"),
                   "lat": clat, "lng": clng, "network": p.get("venue_network")})

rows = []
with open(os.path.join(BASE, "data", "normalized", "lph_projects_summary.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows.append(r)

out = []
for r in rows:
    lat, lng = float(r["lat"]), float(r["lng"])
    best = min(venues, key=lambda v: haversine(lat, lng, v["lat"], v["lng"]))
    dist = round(haversine(lat, lng, best["lat"], best["lng"]))
    out.append({
        "project_tc": r["project_tc"], "project_en": r["project_en"],
        "district_tc": r["district_tc"], "region_tc": r["region_tc"],
        "lat": lat, "lng": lng,
        "total_units": int(r["total_units"]),
        "elevator_units": int(r["elevator_units"]),
        "non_elevator_units": int(r["non_elevator_units"]),
        "blocks_count": int(r["blocks_count"]),
        "min_floor": float(r["min_floor"]), "max_floor": float(r["max_floor"]),
        "avg_area": float(r["avg_internal_area"]),
        "nearest_mtr": {"zh": best["zh"], "en": best["en"],
                        "lat": best["lat"], "lng": best["lng"], "distance_m": dist},
    })

out.sort(key=lambda x: -x["total_units"])
dst = os.path.join(BASE, "data", "normalized", "lph_projects_enriched.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("SAVED", os.path.relpath(dst, BASE))
for p in out:
    m = p["nearest_mtr"]
    print(f'{p["project_tc"]}（{p["district_tc"]}）最近：{m["zh"]}｜約 {m["distance_m"]} m')
