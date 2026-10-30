# -*- coding: utf-8 -*-
"""為地政總署冇名嘅新盤補位置（MONTEREY／SEA TO SKY／凱旋門…）。

座別來源（寧缺勿濫，唔會搶隔籬屋苑嘅樓）：
 1. 地政總署 160m 內 Tower，名要包含屋苑名
 2. OSM Overpass 160m 內有名建築，名要包含屋苑名
 3. 兩者都冇 → 只立屋苑級錨點（一個 est 座釘喺 geocode 點）

併入 derived_estates.json（supp=1）。
"""
import json, math, os, re, time, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "derived_estates.json")
CSDI = ("https://portal.csdi.gov.hk/server/rest/services/common/"
        "landsd_rcd_1637211194312_35158/FeatureServer/0/query")
OVERPASS = "https://overpass-api.de/api/interpreter"

LIST = [
    ("MONTEREY",     "MONTEREY Hong Kong"),
    ("SEA TO SKY",   "SEA TO SKY Hong Kong"),
    ("OCEAN MARINI", "OCEAN MARINI Hong Kong"),
    ("城中駅",        "Metro Town, Tseung Kwan O"),
    ("凱旋門",        "The Arch, Union Square, West Kowloon"),
    ("御海灣",        "御海灣 屯門"),
    ("滿名山",        "The Bloomsway, Tuen Mun"),
    ("Blue Coast",   "Blue Coast, Wong Chuk Hang"),
    ("KOKO ROSSO",   "KOKO ROSSO Hong Kong"),
    ("KOKO MARE",    "KOKO MARE Hong Kong"),
    ("爾巒",         "Riva, Kam Sheung Road, Yuen Long"),
    ("PARK YOHO",    "PARK YOHO, Kam Sheung Road"),
]


def http(url, timeout=45, data=None):
    req = urllib.request.Request(url, headers={"User-Agent": "HKGV-app/1.0 (estate supplement)"},
                                 data=data)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def geocode(q, tries=3):
    u = ("https://nominatim.openstreetmap.org/search?format=json&limit=3&accept-language=zh"
         "&q=" + urllib.parse.quote(q))
    for i in range(tries):
        try:
            return json.loads(http(u))
        except Exception as e:
            print("   geocode retry", str(e)[:50])
            time.sleep(2 + 2 * i)
    return []


def hav(a, b, c, d):
    R = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def landsd_named(lat, lng, name, meters=160):
    p = {"where": "BuildingBlockType='Tower' AND BuildingNameTC IS NOT NULL",
         "geometry": json.dumps({"x": lng, "y": lat, "spatialReference": {"wkid": 4326}}),
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "distance": meters, "units": "esriSRUnit_Meter",
         "spatialRel": "esriSpatialRelIntersects",
         "outFields": "BuildingNameTC,Storeys,TopHeight",
         "returnGeometry": "true", "returnCentroid": "true", "outSR": 4326,
         "resultRecordCount": 60, "f": "json"}
    try:
        d = json.loads(http(CSDI + "?" + urllib.parse.urlencode(p)))
    except Exception as e:
        print("   csdi fail", str(e)[:50])
        return []
    key = name.lower().replace(" ", "")
    out = []
    for f in d.get("features") or []:
        a, c = f.get("attributes") or {}, f.get("centroid") or {}
        n = (a.get("BuildingNameTC") or "").strip()
        if c.get("y") is None or not n or key not in n.lower().replace(" ", ""):
            continue
        out.append({"n": n[:14], "s": a.get("Storeys"), "h": a.get("TopHeight"),
                    "lat": round(c["y"], 6), "lng": round(c["x"], 6)})
    return out


def osm_named(lat, lng, name, meters=170):
    q = (f'[out:json][timeout:30];'
         f'(way["building"]["name"](around:{meters},{lat},{lng}););'
         f'out center 60;')
    try:
        d = json.loads(http(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode()))
    except Exception as e:
        print("   overpass fail", str(e)[:50])
        return []
    key = name.lower().replace(" ", "")
    out = []
    for f in d.get("elements") or []:
        c = f.get("center") or {}
        n = (f.get("tags") or {}).get("name", "")
        if not c or not n or key not in n.lower().replace(" ", ""):
            continue
        lv = (f.get("tags") or {}).get("building:levels")
        out.append({"n": n[:14], "s": int(lv) if lv else None,
                    "h": None, "lat": round(c["lat"], 6), "lng": round(c["lon"], 6)})
    return out


def dedupe(blocks):
    out = []
    for b in sorted(blocks, key=lambda z: -(z.get("s") or 0)):
        if any(hav(b["lat"], b["lng"], o["lat"], o["lng"]) < 20 for o in out):
            continue
        out.append(b)
    return out


def main():
    with open(OUT, encoding="utf-8") as f:
        derived = json.load(f)
    have = {x["name_tc"].upper() for x in derived}
    with open(os.path.join(BASE, "index.html"), encoding="utf-8") as f:
        h = f.read()
    i = h.find("const DATA = ") + 13
    j = h.find(";\nconst COVERED", i)
    D = json.loads(h[i:j])
    have |= {x["name_tc"].upper() for x in D}

    added = 0
    for name, q in LIST:
        if name.upper() in have:
            print(f"  {name}: 已有，跳過")
            continue
        res = geocode(q)
        if not res:
            print(f"  X {name}: geocode 失敗")
            continue
        r = res[0]
        lat, lng = float(r["lat"]), float(r["lon"])
        label = r.get("display_name", "")[:70]
        if "香港" not in label and "Hong Kong" not in label:
            print(f"  X {name}: geocode 飛咗外地（{label[:40]}）")
            continue
        blocks = dedupe(landsd_named(lat, lng, name) + osm_named(lat, lng, name))
        src = "地政/OSM 名匹配"
        if not blocks:
            blocks = [{"n": name[:14], "lat": round(lat, 6), "lng": round(lng, 6),
                       "s": None, "h": None, "est": 1}]
            src = "geocode 點（單釘）"
        clat = sum(b["lat"] for b in blocks) / len(blocks)
        clng = sum(b["lng"] for b in blocks) / len(blocks)
        units = sum(int(b.get("s") or 0) * 6 for b in blocks)
        derived.append({
            "name_tc": name, "lat": round(clat, 6), "lng": round(clng, 6),
            "towers": len(blocks), "storeys_med": None,
            "height_max": None,
            "est_units": units or None, "est_pop": int(units * 2.7) if units else None,
            "supp": 1,
            "member_names": [b["n"] for b in blocks][:40],
            "blocks": blocks,
        })
        added += 1
        print(f"  OK {name}: {label} | {len(blocks)} 座（{src}）| {[b['n'] for b in blocks][:5]}")
        time.sleep(1.5)

    derived.sort(key=lambda x: -x["towers"])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(derived, f, ensure_ascii=False)
    print(f"\n補充 {added} 個，總數 {len(derived)}")


if __name__ == "__main__":
    main()
