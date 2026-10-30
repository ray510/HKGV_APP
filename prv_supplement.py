# -*- coding: utf-8 -*-
"""私人屋苑補充名單：普查 2021「主要屋苑」表冇收錄、但實際存在嘅大型私人屋苑
（多為 2010 年後落成，或普查未獨立列出）。

做法：地政總署「建築物」按名 LIKE 查 → 同名 Tower 聚類 → 逐座（座名／座標／層數／樓高），
再用 stage2_full 同一套設施池計 nearest_* 同 sub_scores，寫入 all_estates_enriched.json。
可重複執行（已存在嘅屋苑會跳過）。
"""
import json, os, re, urllib.request, urllib.parse, time

import stage2_full as S

NORM = "data/normalized"
DST = os.path.join(NORM, "all_estates_enriched.json")
QUERY = ("https://portal.csdi.gov.hk/server/rest/services/common/"
         "landsd_rcd_1637211194312_35158/FeatureServer/0/query")

# (顯示名, 英文名, 區議會分區, LandsD 查詢關鍵字)
CANDIDATES = [
    ("逸峯", "Green Code", "北區", "逸峯"),
    ("柏傲莊", "The Pavilia Farm", "沙田區", "柏傲莊"),
    ("全城滙", "City Point", "荃灣區", "全城滙"),
    ("迎海", "Double Cove", "沙田區", "迎海"),
    ("駿景園", "Royal Ascot", "沙田區", "駿景園"),
    ("御龍山", "The Palazzo", "沙田區", "御龍山"),
    ("星漣海", "Stars by the Sea", "沙田區", "星漣海"),
    ("君臨天下", "The Harbourside", "油尖旺區", "君臨天下"),
    ("擎天半島", "Sorrento", "油尖旺區", "擎天半島"),
    ("漾日居", "The Waterfront", "油尖旺區", "漾日居"),
    ("一號銀海", "One Silver Sea", "油尖旺區", "一號銀海"),
    ("帝峯·皇殿", "The Hermitage", "油尖旺區", "帝峯"),
    ("海桃灣", "Florient Rise", "油尖旺區", "海桃灣"),
    ("何文田山畔", "Homantin Hillside", "九龍城區", "何文田山畔"),
    ("尚悅", "The Reach", "元朗區", "尚悅"),
]

NON_RES = ("會所", "商場", "停車場", "車場", "幼稚園", "學校", "中學", "小學", "教堂", "診所",
           "辦事處", "管理處", "變電", "變壓", "泵房", "垃圾", "街市", "公園", "廁", "郵局",
           "安老院", "護理", "幼兒", "教會", "禮拜堂", "酒店", "銀行", "油站", "巴士", "俱樂部",
           "車站", "服務中心", "發展中心", "社區中心", "社區會堂", "文娛", "耆康", "福利", "書院",
           "獨立屋", "洋房", "別墅")


def landsd_like(name, timeout=30):
    qs = urllib.parse.urlencode({
        "where": f"BuildingNameTC LIKE '%{name}%'",
        "outFields": "BuildingNameTC,BuildingBlockType,Storeys,TopHeight",
        "returnCentroid": "true", "returnGeometry": "false",
        "outSR": "4326", "f": "json", "resultRecordCount": "120"})
    req = urllib.request.Request(QUERY + "?" + qs,
                                 headers={"User-Agent": "HKGV-prototype/1.0 (CSDI Awards 2026)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    out = []
    for ft in d.get("features", []):
        a = ft.get("attributes") or {}
        c = ft.get("centroid") or {}
        nm = (a.get("BuildingNameTC") or "").replace("\u3000", " ").strip()
        if not nm or c.get("x") is None or a.get("BuildingBlockType") != "Tower":
            continue
        if any(k in nm for k in NON_RES):
            continue
        out.append({"n": nm, "lat": round(c["y"], 5), "lng": round(c["x"], 5),
                    "s": a.get("Storeys"),
                    "h": round(float(a["TopHeight"]), 1) if a.get("TopHeight") is not None else None})
    return out


def build_blocks(key):
    """同名 Tower 聚類：以中位點為中心，保留 400m 內（防止同名跨區誤配）。"""
    raw = landsd_like(key)
    towers = [t for t in raw if t["n"].startswith(key)]
    if not towers:
        towers = raw
    if len(towers) < 1:
        return [], None
    lat0 = sorted(t["lat"] for t in towers)[len(towers) // 2]
    lng0 = sorted(t["lng"] for t in towers)[len(towers) // 2]
    near = [t for t in towers
            if ((t["lat"] - lat0) ** 2 + (t["lng"] - lng0) ** 2) ** 0.5 * 111000 <= 400]
    by_name = {}
    for t in near:
        k = t["n"]
        if k not in by_name or (t.get("h") or 0) > (by_name[k].get("h") or 0):
            by_name[k] = t
    blocks = []
    for t in by_name.values():
        disp = t["n"][len(key):].strip() or t["n"]
        blocks.append({"n": disp, "u": None, "e": None, "f1": None, "f2": None, "a": None,
                       "lat": t["lat"], "lng": t["lng"], "s": t["s"], "h": t["h"]})
    blocks.sort(key=lambda b: b["n"])
    lat = round(sum(b["lat"] for b in blocks) / len(blocks), 6)
    lng = round(sum(b["lng"] for b in blocks) / len(blocks), 6)
    return blocks, (lat, lng)


def main():
    data = json.load(open(DST, encoding="utf-8"))
    have = {e["name_tc"] for e in data}
    todo = [c for c in CANDIDATES if c[0] not in have]
    print(f"補充名單：{len(CANDIDATES)} 個候選，{len(todo)} 個未收錄")

    pools = None
    added = []
    for name, en, district, key in todo:
        blocks, center = build_blocks(key)
        if not blocks or not center:
            print(f"  ✗ {name}：地政總署搵唔到同名 Tower，跳過")
            continue
        if pools is None:
            print("  載入設施池（港鐵／小學／託管／幼兒／長者／會堂／醫院／Phase A）…", flush=True)
            pools = {
                "mtr": S.build_mtr_venues(), "schools": S.build_schools(),
                "kgs": S.build_kindergartens(), "pgs": S.build_playgrounds(),
                "care": S.build_care(), "childcare": S.build_childcare(),
                "hospitals": S.build_hospitals(), "phase_a": S.build_phase_a(),
            }
            elderly, halls = S.build_community()
            pools["elderly_all"] = elderly + S.build_elder_services() + pools["phase_a"]["rhomes"]
            pools["halls"] = halls
            pools["ae"] = [h for h in pools["hospitals"] if h.get("ae")]

        lat, lng = center
        m, mn = S.nearest_mtr_precise(lat, lng, pools["mtr"])
        s, sn = S.nearest_and_count(lat, lng, pools["schools"])
        kg, kgn = S.nearest_and_count(lat, lng, pools["kgs"])
        pg, pgn = S.nearest_and_count(lat, lng, pools["pgs"])
        c, cn = S.nearest_and_count(lat, lng, pools["care"])
        cc, ccn = S.nearest_and_count(lat, lng, pools["childcare"])
        el, eln = S.nearest_and_count(lat, lng, pools["elderly_all"])
        sh, shn = S.nearest_and_count(lat, lng, pools["halls"])
        ae, aen = S.nearest_and_count(lat, lng, pools["ae"])
        hp, _ = S.nearest_and_count(lat, lng, pools["hospitals"])
        pa = pools["phase_a"]
        mk, mkn = S.nearest_and_count(lat, lng, pa["markets"])
        lb, lbn = S.nearest_and_count(lat, lng, pa["libraries"])
        cl, _ = S.nearest_and_count(lat, lng, pa["clinics"])
        lr, _ = S.nearest_and_count(lat, lng, pa["livingrooms"])
        mh, _ = S.nearest_and_count(lat, lng, pa["maternal"])
        po, _ = S.nearest_and_count(lat, lng, pa["postoffices"])
        fs, _ = S.nearest_and_count(lat, lng, pa["firestations"])
        cs, _ = S.nearest_and_count(lat, lng, pa["cold_shelters"])

        score, subs = S.compute_living_circle_metrics(
            m["distance_m"] if m else None, s["distance_m"] if s else None, sn, kgn,
            c["distance_m"] if c else None, cn, cc["distance_m"] if cc else None, ccn,
            el["distance_m"] if el else None, sh["distance_m"] if sh else None,
            ae["distance_m"] if ae else None, None, None)

        e = {
            "source": "PRV", "source_type": "PRV", "name_tc": name, "name_en": en,
            "district_tc": district, "region_tc": None, "lat": lat, "lng": lng,
            "total_units": None, "elevator_units": None, "non_elevator_units": None,
            "min_floor": None, "max_floor": None, "avg_area": None,
            "blocks_count": len(blocks), "blocks": blocks, "blocks_source": "LandsD",
            "census_pop": None, "census_income_md": None,
            "census_note": "普查未獨立列出（補充名單）",
            "nearest_mtr": dict(m, count_800m=mn) if m else None,
            "nearest_school": {"zh": s["item"]["zh"], "en": s["item"].get("en"), "lat": s["item"]["lat"],
                               "lng": s["item"]["lng"], "distance_m": s["distance_m"],
                               "count_800m": sn} if s else None,
            "kindergartens_800m": kgn,
            "nearest_kg_dist_m": kg["distance_m"] if kg else None,
            "nearest_kg_name_tc": kg["item"]["zh"] if kg else None,
            "nearest_kg_lat": kg["item"]["lat"] if kg else None,
            "nearest_kg_lng": kg["item"]["lng"] if kg else None,
            "playgrounds_800m": pgn,
            "nearest_pg_dist_m": pg["distance_m"] if pg else None,
            "nearest_pg_name_tc": pg["item"]["zh"] if pg else None,
            "nearest_pg_lat": pg["item"]["lat"] if pg else None,
            "nearest_pg_lng": pg["item"]["lng"] if pg else None,
            "nearest_care": {"zh": c["item"]["zh"], "lat": c["item"]["lat"], "lng": c["item"]["lng"],
                             "distance_m": c["distance_m"], "count_800m": cn} if c else None,
            "nearest_childcare": {"zh": cc["item"]["zh"], "lat": cc["item"]["lat"],
                                  "lng": cc["item"]["lng"], "distance_m": cc["distance_m"],
                                  "count_800m": ccn} if cc else None,
            "nearest_elderly": {"zh": el["item"]["zh"], "en": el["item"].get("en"),
                                "lat": el["item"]["lat"], "lng": el["item"]["lng"],
                                "distance_m": el["distance_m"], "count_800m": eln} if el else None,
            "nearest_shelter": {"zh": sh["item"]["zh"], "en": sh["item"].get("en"),
                                "lat": sh["item"]["lat"], "lng": sh["item"]["lng"],
                                "distance_m": sh["distance_m"], "count_800m": shn} if sh else None,
            "nearest_ae_hospital": {"zh": ae["item"]["zh"], "lat": ae["item"]["lat"],
                                    "lng": ae["item"]["lng"], "distance_m": ae["distance_m"],
                                    "count_800m": aen} if ae else None,
            "nearest_hospital": {"zh": hp["item"]["zh"], "lat": hp["item"]["lat"],
                                 "lng": hp["item"]["lng"], "distance_m": hp["distance_m"],
                                 "ae": bool(hp["item"].get("ae"))} if hp else None,
            "nearest_cold_shelter": {"zh": cs["item"]["zh"], "lat": cs["item"]["lat"],
                                     "lng": cs["item"]["lng"], "distance_m": cs["distance_m"]} if cs else None,
            "nearest_market": {"zh": mk["item"]["zh"], "lat": mk["item"]["lat"], "lng": mk["item"]["lng"],
                               "distance_m": mk["distance_m"], "count_800m": mkn} if mk else None,
            "nearest_library": {"zh": lb["item"]["zh"], "lat": lb["item"]["lat"], "lng": lb["item"]["lng"],
                                "distance_m": lb["distance_m"], "count_800m": lbn} if lb else None,
            "nearest_clinic": {"zh": cl["item"]["zh"], "lat": cl["item"]["lat"], "lng": cl["item"]["lng"],
                               "distance_m": cl["distance_m"]} if cl else None,
            "nearest_livingroom": {"zh": lr["item"]["zh"], "lat": lr["item"]["lat"],
                                   "lng": lr["item"]["lng"], "distance_m": lr["distance_m"]} if lr else None,
            "nearest_maternal": {"zh": mh["item"]["zh"], "lat": mh["item"]["lat"],
                                 "lng": mh["item"]["lng"], "distance_m": mh["distance_m"]} if mh else None,
            "nearest_postoffice": {"zh": po["item"]["zh"], "lat": po["item"]["lat"],
                                   "lng": po["item"]["lng"], "distance_m": po["distance_m"]} if po else None,
            "nearest_firestation": {"zh": fs["item"]["zh"], "lat": fs["item"]["lat"],
                                    "lng": fs["item"]["lng"], "distance_m": fs["distance_m"]} if fs else None,
            "score": score, "sub_scores": subs,
            "density_800m": {"schools": sn, "cares": cn, "childcare": ccn},
        }
        data.append(e)
        added.append(e)
        print(f"  ✓ {name}：{len(blocks)} 座，{lat:.4f},{lng:.4f}，評分 {score}")

    if added:
        try:
            import covered_network
            covered_network.attach(added, verbose=False)
        except Exception as ex:
            print(f"  ⚠️ 有蓋步行維度計算失敗：{type(ex).__name__}: {ex}")
        json.dump(data, open(DST, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"已寫入 {DST}：新增 {len(added)} 個私人屋苑，總數 {len(data)}")
    else:
        print("冇新增")


if __name__ == "__main__":
    main()
