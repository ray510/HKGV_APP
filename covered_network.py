# -*- coding: utf-8 -*-
"""
⑬c ① 有蓋步行網絡（立體行人層）——路政署三個數據集：
    行人天橋 STR_FB 1,199 ／ 行人隧道 STR_SUBWAY 573 ／ 行人通道上蓋 STR_WALKWAY 344
合共 2,116 個構築物（Polygon／MultiPolygon footprint，WGS84）。

為每個屋邨錨點計算：
  nearest_covered      最近有蓋構築物（類型／編號／距離）
  covered_500m         500m 內有蓋構築物段數＋總長度（按 segment 中點計，避免長天橋 centroid 偏差）
  mtr_corridor         往最近港鐵嘅直線走廊取樣（診斷用，唔入評分——直線走廊唔等於真實步行路線）
  sub_scores.covered   0–100 有蓋步行維度（45% 最近距離 + 55% 500m 網絡總長）

用法：
  python covered_network.py            # 抓取＋計算＋回寫 all_estates_enriched.json
  python covered_network.py --stats    # 只印分佈（需先跑過一次）
"""
import json, math, os, sys, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "data", "raw")
NORM = os.path.join(BASE, "data", "normalized")
SRC = os.path.join(NORM, "all_estates_enriched.json")
UA = {"User-Agent": "Mozilla/5.0 (HK-OpenData-CoveredNetwork)"}

SPECS = [
    ("hyd_rcd_1632360512481_74705", "STR_FB",      "FB",      "行人天橋",   "hyd_footbridges.json"),
    ("hyd_rcd_1632360845029_59241", "STR_SUBWAY",  "SUBWAY",  "行人隧道",   "hyd_subways.json"),
    ("hyd_rcd_1632360364210_72608", "STR_WALKWAY", "WALKWAY", "行人通道上蓋", "hyd_walkway_covers.json"),
]

CELL = 0.004          # 網格 ~440m
M_PER_DEG_LAT = 110540.0


def m_per_deg_lng(lat):
    return 111320.0 * math.cos(math.radians(lat))


def fetch_geojson(did, layer, save_as):
    path = os.path.join(RAW, save_as)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    urls = [
        f"https://portal.csdi.gov.hk/csdi-webpage/file-api?dataset_id={did}&format=geojson&layer_name={layer}",
        f"https://portal.csdi.gov.hk/server/rest/services/common/{did}/FeatureServer/0/query"
        "?where=1%3D1&outFields=*&outSR=4326&f=geojson",
    ]
    for u in urls:
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                gj = json.loads(r.read().decode("utf-8", errors="replace"))
            if isinstance(gj, dict) and gj.get("features"):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(gj, f, ensure_ascii=False)
                return gj
        except Exception as e:
            print(f"  {did} {type(e).__name__}: {e}", flush=True)
    raise RuntimeError(f"{did} 全部來源失敗")


def rings_of(geom):
    """Polygon / MultiPolygon → 所有環（list of [x,y]）。"""
    if not geom:
        return []
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon":
        return c or []
    if t == "MultiPolygon":
        return [r for poly in (c or []) for r in poly]
    return []


def seg_len_m(x1, y1, x2, y2, lat0):
    dx = (x2 - x1) * m_per_deg_lng(lat0)
    dy = (y2 - y1) * M_PER_DEG_LAT
    return math.hypot(dx, dy)


def build_structures():
    out = []
    for did, layer, code, label, save_as in SPECS:
        gj = fetch_geojson(did, layer, save_as)
        n0 = len(out)
        for ft in gj.get("features", []):
            p = ft.get("properties") or {}
            segs = []
            for ring in rings_of(ft.get("geometry")):
                for i in range(len(ring) - 1):
                    a, b = ring[i], ring[i + 1]
                    if a == b:
                        continue
                    segs.append([float(a[0]), float(a[1]), float(b[0]), float(b[1])])
            if not segs:
                continue
            lat0 = sum(s[1] for s in segs) / len(segs)
            length = sum(seg_len_m(s[0], s[1], s[2], s[3], lat0) for s in segs)
            if length <= 0:
                continue
            out.append({"type": code, "type_tc": label, "str_no": p.get("STR_NO") or "",
                        "length_m": round(length, 1), "segs": segs,
                        "lat": lat0, "lng": sum(s[0] for s in segs) / len(segs)})
        print(f"  {label}：{len(out) - n0} 個構築物", flush=True)
    return out


class CoveredIndex:
    def __init__(self, structures):
        self.structures = structures
        self.segs = []            # (x1,y1,x2,y2, si)
        self.grid = {}
        for si, st in enumerate(structures):
            for x1, y1, x2, y2 in st["segs"]:
                idx = len(self.segs)
                self.segs.append((x1, y1, x2, y2, si))
                for cell in self._cells_of_seg(x1, y1, x2, y2):
                    self.grid.setdefault(cell, []).append(idx)

    @staticmethod
    def _cell(x, y):
        return (int(math.floor(x / CELL)), int(math.floor(y / CELL)))

    def _cells_of_seg(self, x1, y1, x2, y2):
        cx1, cy1 = self._cell(min(x1, x2), min(y1, y2))
        cx2, cy2 = self._cell(max(x1, x2), max(y1, y2))
        for cx in range(cx1, cx2 + 1):
            for cy in range(cy1, cy2 + 1):
                yield (cx, cy)

    @staticmethod
    def _pt_seg_m(lat, lng, x1, y1, x2, y2):
        """點到線段距離（米，局部等距投影）。"""
        kx, ky = m_per_deg_lng(lat), M_PER_DEG_LAT
        px, py = 0.0, 0.0
        ax, ay = (x1 - lng) * kx, (y1 - lat) * ky
        bx, by = (x2 - lng) * kx, (y2 - lat) * ky
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        if L2 == 0:
            return math.hypot(ax, ay)
        t = max(0.0, min(1.0, -((ax * vx) + (ay * vy)) / L2))
        return math.hypot(ax + t * vx, ay + t * vy)

    def nearest(self, lat, lng, max_ring=10):
        cx, cy = self._cell(lng, lat)
        best_d, best_si = None, None
        cell_m = CELL * M_PER_DEG_LAT * 0.93      # 保守下限（lng 向較短）
        for r in range(max_ring + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    for idx in self.grid.get((cx + dx, cy + dy), ()):
                        x1, y1, x2, y2, si = self.segs[idx]
                        d = self._pt_seg_m(lat, lng, x1, y1, x2, y2)
                        if best_d is None or d < best_d:
                            best_d, best_si = d, si
            if best_d is not None and best_d <= r * cell_m:
                break
        return (best_d, best_si) if best_d is not None else (None, None)

    def within(self, lat, lng, radius):
        """radius 內有蓋結構：段長合計（按段中點）＋去重結構清單。"""
        kx, ky = m_per_deg_lng(lat), M_PER_DEG_LAT
        r2 = radius * radius
        cx, cy = self._cell(lng, lat)
        seen, total = set(), 0.0
        span = int(math.ceil(radius / (CELL * M_PER_DEG_LAT * 0.93))) + 1
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                for idx in self.grid.get((cx + dx, cy + dy), ()):
                    x1, y1, x2, y2, si = self.segs[idx]
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    ddx, ddy = (mx - lng) * kx, (my - lat) * ky
                    if ddx * ddx + ddy * ddy > r2:
                        continue
                    total += seg_len_m(x1, y1, x2, y2, lat)
                    seen.add(si)
        return total, seen

    def corridor_pct(self, lat, lng, dlat, dlng, step=40.0, tol=55.0):
        """由錨點到目的地嘅直線走廊取樣，回傳有蓋覆蓋率（%）。"""
        kx, ky = m_per_deg_lng(lat), M_PER_DEG_LAT
        dx, dy = (dlng - lng) * kx, (dlat - lat) * ky
        dist = math.hypot(dx, dy)
        if dist < 120:
            return None, 0
        n = max(3, int(dist // step))
        hit = 0
        for i in range(n + 1):
            t = i / n
            qlat, qlng = lat + (dlat - lat) * t, lng + (dlng - lng) * t
            d, _ = self.nearest(qlat, qlng, max_ring=1)
            if d is not None and d <= tol:
                hit += 1
        return round(hit / (n + 1) * 100.0, 1), int(dist)


def covered_subscore(nearest_m, length_500m):
    """有蓋步行維度 0–100：45% 最近有蓋構築物距離 + 55% 500m 內有蓋網絡總長。
    密度滿分定於 2,000m（實測 p85 左右，避免大量屋邨並列 100 分）。
    註：呢個係「立體有蓋資源密度」指標，唔係點對點有蓋路徑證明。"""
    if nearest_m is None:
        return 50.0
    s_near = 100.0 if nearest_m <= 60 else max(5.0, 100.0 * math.exp(-math.log(2) / 220.0 * (nearest_m - 60)))
    s_dens = min(1.0, (length_500m or 0) / 2000.0) * 100.0
    return round(0.45 * s_near + 0.55 * s_dens, 1)


def attach(all_est, verbose=True):
    structures = build_structures()
    idx = CoveredIndex(structures)
    n_fb = sum(1 for s in structures if s["type"] == "FB")
    n_sub = sum(1 for s in structures if s["type"] == "SUBWAY")
    n_cov = sum(1 for s in structures if s["type"] == "WALKWAY")
    total_len = sum(s["length_m"] for s in structures)
    if verbose:
        print(f"  索引：{len(structures)} 個構築物（天橋 {n_fb}／隧道 {n_sub}／上蓋 {n_cov}），"
              f"總長 {total_len/1000:.1f} km，{len(idx.segs):,} 段", flush=True)
    for e in all_est:
        lat, lng = e.get("lat"), e.get("lng")
        if lat is None or lng is None:
            e["nearest_covered"] = None
            e["covered_500m"] = None
            e["mtr_corridor"] = None
            e.setdefault("sub_scores", {})["covered"] = None
            continue
        d, si = idx.nearest(lat, lng)
        st = structures[si] if si is not None else None
        e["nearest_covered"] = ({"type": st["type_tc"], "str_no": st["str_no"],
                                 "distance_m": int(round(d))} if st else None)
        length, sids = idx.within(lat, lng, 500)
        types = [structures[i]["type"] for i in sids]
        e["covered_500m"] = {"count": len(sids), "length_m": int(round(length)),
                             "fb": types.count("FB"), "subway": types.count("SUBWAY"),
                             "walkway": types.count("WALKWAY")}
        mtr = e.get("nearest_mtr") or {}
        pct = None
        if mtr.get("lat") is not None and mtr.get("distance_m") is not None and mtr["distance_m"] <= 1500:
            pct, _ = idx.corridor_pct(lat, lng, mtr["lat"], mtr["lng"])
        e["mtr_corridor"] = ({"pct": pct, "dest": mtr.get("zh"),
                              "dist_m": mtr.get("distance_m")} if pct is not None else None)
        e.setdefault("sub_scores", {})["covered"] = covered_subscore(d, length)

    return structures


def main():
    with open(SRC, encoding="utf-8") as f:
        all_est = json.load(f)
    print(f"讀入 {len(all_est)} 個錨點", flush=True)
    structures = attach(all_est)
    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(all_est, f, ensure_ascii=False)
    with open(os.path.join(NORM, "covered_network.json"), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in s.items() if k != "segs"} for s in structures],
                  f, ensure_ascii=False)
    print(f"已回寫 {os.path.relpath(SRC, BASE)}", flush=True)

    # 分佈檢查
    vals = [e["sub_scores"]["covered"] for e in all_est if e.get("sub_scores", {}).get("covered") is not None]
    vals.sort()
    def q(p):
        return vals[min(len(vals) - 1, int(len(vals) * p))] if vals else None
    print(f"\ncovered 分數：n={len(vals)} min={vals[0]} p25={q(.25)} 中位={q(.5)} p75={q(.75)} p90={q(.9)} max={vals[-1]}")
    lens = sorted(e["covered_500m"]["length_m"] for e in all_est if e.get("covered_500m"))
    print(f"500m 內有蓋總長：p50={lens[len(lens)//2]}m p75={lens[int(len(lens)*.75)]}m p90={lens[int(len(lens)*.9)]}m max={lens[-1]}m")
    corr = sorted(e["mtr_corridor"]["pct"] for e in all_est if e.get("mtr_corridor"))
    if corr:
        print(f"往港鐵走廊有蓋率：n={len(corr)} p25={corr[len(corr)//4]} p50={corr[len(corr)//2]} p75={corr[len(corr)*3//4]} max={corr[-1]}")
    print("\nTop 8 有蓋網絡：")
    for e in sorted(all_est, key=lambda x: -(x.get("sub_scores", {}).get("covered") or 0))[:8]:
        c = e["sub_scores"]["covered"]
        print(f"  {c:>5}｜{e['name_tc']}（{e.get('district_tc') or '-'}）"
              f"最近 {e['nearest_covered']['distance_m']}m {e['nearest_covered']['type']}｜"
              f"500m {e['covered_500m']['count']} 段 {e['covered_500m']['length_m']}m｜"
              f"走廊 {e['mtr_corridor']['pct'] if e.get('mtr_corridor') else '-'}%")


if __name__ == "__main__":
    main()
