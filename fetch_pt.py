# -*- coding: utf-8 -*-
"""抓全港巴士站＋路線（九巴 KMB、城巴 CTB），產生 pt_stops.json。

Phase 1 只需要「邊個站、有咩路線號」，唔需要班次／走線。

數據源（data.gov.hk 開放數據，可商用，需標示來源）：
  九巴  https://data.etabus.gov.hk/v1/transport/kmb/stop/          （一次過全量）
        https://data.etabus.gov.hk/v1/transport/kmb/route-stop/    （一次過全量）
        https://data.etabus.gov.hk/v1/transport/kmb/route/         （路線目的地）
  城巴  https://rt.data.gov.hk/v2/transport/citybus/route/CTB       （路線清單）
        https://rt.data.gov.hk/v2/transport/citybus/route-stop/CTB/{route}/{dir}
        https://rt.data.gov.hk/v2/transport/citybus/stop/{stop_id} （逐站，有快取）

注意：KMB 端點**必須帶結尾斜線**，冇斜線會 403。

用法：
    python fetch_pt.py              # 有快取就唔重抓
    python fetch_pt.py --refresh    # 強制重抓
輸出：cache/pt_kmb_stops.json, cache/pt_ctb_stops.json, pt_stops.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
OUT = os.path.join(BASE, "pt_stops.json")
UA = "HKGV-prototype/1.0 (accessibility research; contact: local)"

KMB_STOP = "https://data.etabus.gov.hk/v1/transport/kmb/stop/"
KMB_RS = "https://data.etabus.gov.hk/v1/transport/kmb/route-stop/"
KMB_ROUTE = "https://data.etabus.gov.hk/v1/transport/kmb/route/"
CTB_ROUTE = "https://rt.data.gov.hk/v2/transport/citybus/route/CTB"
CTB_RS = "https://rt.data.gov.hk/v2/transport/citybus/route-stop/CTB/{r}/{d}"
CTB_STOP = "https://rt.data.gov.hk/v2/transport/citybus/stop/{s}"


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    return None


def cached(name):
    return os.path.join(CACHE, name)


def fetch_kmb(refresh=False):
    """回傳 (stops, route_stops, routes)。"""
    os.makedirs(CACHE, exist_ok=True)
    f_stop, f_rs, f_rt = cached("pt_kmb_stops.json"), cached("pt_kmb_rs.json"), cached("pt_kmb_routes.json")
    if refresh or not (os.path.exists(f_stop) and os.path.exists(f_rs) and os.path.exists(f_rt)):
        print("抓九巴：站／路線站序／路線…", flush=True)
        for url, path in ((KMB_STOP, f_stop), (KMB_RS, f_rs), (KMB_ROUTE, f_rt)):
            d = get(url)["data"]
            json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"   {os.path.basename(path)}: {len(d):,}", flush=True)
            time.sleep(1)
    return (json.load(open(f_stop, encoding="utf-8")),
            json.load(open(f_rs, encoding="utf-8")),
            json.load(open(f_rt, encoding="utf-8")))


def fetch_ctb(refresh=False):
    """城巴冇全量站表，要逐條路線攞站序，再逐個站攞名／座標（有快取，可斷點續）。"""
    os.makedirs(CACHE, exist_ok=True)
    f_rs, f_stop = cached("pt_ctb_rs.json"), cached("pt_ctb_stops.json")
    routes = get(CTB_ROUTE)["data"]
    if refresh or not os.path.exists(f_rs):
        print(f"抓城巴站序（{len(routes)} 條路線 × 2 方向）…", flush=True)
        rs = []
        jobs = [(r["route"], d) for r in routes for d in ("outbound", "inbound")]
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(get, CTB_RS.format(r=r, d=d)): (r, d) for r, d in jobs}
            for k, f in enumerate(as_completed(futs), 1):
                try:
                    rs.extend(f.result()["data"])
                except Exception:
                    pass
                if k % 100 == 0:
                    print(f"   {k}/{len(jobs)}", flush=True)
        json.dump(rs, open(f_rs, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"   站序 {len(rs):,} 筆", flush=True)

    rs = json.load(open(f_rs, encoding="utf-8"))
    ids = sorted({x["stop"] for x in rs})
    stops = {}
    if os.path.exists(f_stop):
        stops = {s["stop"]: s for s in json.load(open(f_stop, encoding="utf-8"))}
    todo = [i for i in ids if i not in stops]
    if todo:
        print(f"抓城巴站資料（{len(todo):,} 個新站，已有 {len(stops):,}）…", flush=True)
        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(get, CTB_STOP.format(s=i)): i for i in todo}
            for k, f in enumerate(as_completed(futs), 1):
                try:
                    d = f.result().get("data") or {}
                    if d.get("stop"):
                        stops[d["stop"]] = d
                except Exception:
                    pass
                if k % 500 == 0:
                    print(f"   {k}/{len(todo)}", flush=True)
                    json.dump(list(stops.values()), open(f_stop, "w", encoding="utf-8"),
                              ensure_ascii=False)
        json.dump(list(stops.values()), open(f_stop, "w", encoding="utf-8"), ensure_ascii=False)
    return rs, stops


def main():
    refresh = "--refresh" in sys.argv
    kmb_stops, kmb_rs, kmb_routes = fetch_kmb(refresh)
    print(f"九巴：{len(kmb_stops):,} 站／{len(kmb_rs):,} 站序／{len(kmb_routes):,} 路線", flush=True)

    # 路線目的地（顯示「1A 竹園邨→尖沙咀碼頭」用）
    rdest = {}
    for r in kmb_routes:
        rdest[(r["route"], r["bound"], r["service_type"])] = (r.get("orig_tc"), r.get("dest_tc"))

    out = {}   # stop_id -> {n, lat, lng, routes:set}

    def add(sid, name, lat, lng, route, co):
        s = out.get(sid)
        if s is None:
            s = out[sid] = {"n": name, "lat": round(float(lat), 5), "lng": round(float(lng), 5),
                            "r": set(), "co": co}
        s["r"].add(route)

    for s in kmb_stops:
        out.setdefault(s["stop"], {"n": s["name_tc"], "lat": round(float(s["lat"]), 5),
                                   "lng": round(float(s["long"]), 5), "r": set(), "co": "KMB"})
    for rs in kmb_rs:
        sid = rs["stop"]
        if sid in out:
            out[sid]["r"].add(rs["route"])

    print("抓城巴…", flush=True)
    try:
        ctb_rs, ctb_stops = fetch_ctb(refresh)
        for rs in ctb_rs:
            sid = rs["stop"]
            s = ctb_stops.get(sid)
            if s and s.get("lat"):
                add(sid, s.get("name_tc") or "", s["lat"], s["long"], rs["route"], "CTB")
        print(f"城巴：{len(ctb_stops):,} 站", flush=True)
    except Exception as e:
        print(f"⚠️ 城巴抓取失敗（{e}），先出九巴版本", flush=True)

    stops = []
    for sid, s in out.items():
        if not s["r"] or s["lat"] is None:
            continue
        stops.append({"id": sid, "n": s["n"], "lat": s["lat"], "lng": s["lng"],
                      "co": s["co"], "r": sorted(s["r"])})
    stops.sort(key=lambda x: (x["lat"], x["lng"]))
    json.dump(stops, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    routes = sorted({r for s in stops for r in s["r"]})
    print(f"\n✅ pt_stops.json：{len(stops):,} 個站、{len(routes):,} 條路線、"
          f"{sum(len(s['r']) for s in stops):,} 個站×路線組合", flush=True)
    print(f"   檔案大小 {os.path.getsize(OUT)/1024:.0f} KB", flush=True)


if __name__ == "__main__":
    main()
