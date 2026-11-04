# -*- coding: utf-8 -*-
"""抓 OSM 地名節點，做「分區」（18 區之下再細分：上水／大圍／聯和墟…）。

為咩用 OSM：政府冇一份現成「18 區 → 分區」對照表可以免費下載，
而 OSM 有 place=city/town/suburb/quarter/neighbourhood 節點，覆蓋全港。

分配規則（重要，否則會出現「恒峰花園 → 香粉寮」呢種 250m 外嘅小村名）：
  優先級 city > town > suburb > quarter > neighbourhood，
  但每級有可接受距離：city 10km、town 6km、suburb 3km、quarter/neighbourhood 1km。
  → 恒峰花園：香粉寮 250m（quarter）輸給 大圍 874m（suburb）✓
  → 上水中心：上水 122m（town）勝出 ✓

用法：python fetch_areas.py
輸出：data/areas_osm.json（約 900 個地名，commit 入 repo，CI 唔需要上網）
"""
from __future__ import annotations

import json
import math
import os
import re
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "areas_osm.json")
UA = "HKGV-prototype/1.0"

# 香港 bbox（含少量深圳，下面會過濾）
BBOX = "22.13,113.83,22.58,114.52"
QUERY = f"""[out:json][timeout:180];
(
  node["place"~"^(city|town|suburb|quarter|neighbourhood)$"]({BBOX});
);
out tags center;"""

RANK = {"city": 1, "town": 2, "suburb": 3, "quarter": 4, "neighbourhood": 5}
RADIUS = {"city": 10000, "town": 6000, "suburb": 3000, "quarter": 1000, "neighbourhood": 1000}

# 深圳／內地地名（同一個 bbox 會抓到）
MAINLAND = re.compile(r"(区|區|社区|社區|街道|新区|新區)$")


def main():
    url = "https://overpass-api.de/api/interpreter?" + urllib.parse.urlencode({"data": QUERY})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=240) as r:
        raw = json.loads(r.read().decode("utf-8"))

    out = []
    for e in raw.get("elements", []):
        t = e.get("tags", {})
        nm = t.get("name:zh") or t.get("name:zh-Hant") or t.get("name")
        if not nm or e.get("lat") is None:
            continue
        if MAINLAND.search(nm) or e["lat"] > 22.55:
            continue                       # 深圳／內地
        out.append({"n": nm, "lat": round(e["lat"], 5), "lng": round(e["lon"], 5),
                    "p": t.get("place")})

    out.sort(key=lambda x: (RANK.get(x["p"], 9), x["n"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    from collections import Counter
    print(f"✅ {OUT}：{len(out)} 個地名 {Counter(x['p'] for x in out).most_common()}")


if __name__ == "__main__":
    main()
