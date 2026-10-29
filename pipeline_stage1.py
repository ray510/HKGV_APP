# -*- coding: utf-8 -*-
"""
HK 開放數據 Web App — 構思②（公屋/簡約公屋 AI 配對）Stage 1 數據管線
================================================================
用途：拉取並清洗構思② 嘅核心房屋數據，輸出標準化 CSV + 項目級摘要 JSON，
     作為「單位配對 + 15 分鐘生活圈」嘅地基。

數據源（DATA.GOV.HK 實測確認，2026-10-28）：
  1. 「簡約公屋」單位資料   hk-hb-lph-housing-stock     (房屋局, JSON, 單位級)
  2. 公共屋邨位置及資料     hk-housing-eslocator-eslocator (房委會, JSON, 屋邨級)

註：教育局「學校位置及資料」(hk-edb-schinfo-school-location-and-information)
    同社署「在校課後託管服務計劃」(hk-swd-ycb-sba) 走 CSDI WFS API，
    喺 Stage 1.5 另行接入（見 build_lifecircle_notes()）。
"""
import csv, json, os, sys, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "data", "raw")
NORM = os.path.join(BASE, "data", "normalized")

SOURCES = {
    "lph": "https://data.hb.gov.hk/dataset/lph/hb_lphs_en.json",
    "estates": "https://www.housingauthority.gov.hk/datagovhk/prh-estates.json",
}

UA = {"User-Agent": "Mozilla/5.0 (HK-OpenData-Stage1)"}


def fetch_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def save_raw(name, obj):
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def write_csv(path, header, rows):
    os.makedirs(NORM, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def elevator_flag(v):
    """歸一化『有無升降機』欄位（兼容 Yes/No、是/否、有/冇）。"""
    s = str(v).strip().lower()
    return 1 if s in {"yes", "true", "1", "y", "有", "是", "係"} else 0


def as_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def normalize_lph_units(records):
    """單位級 → tidy 行 + 項目級聚合。"""
    unit_rows, projects = [], {}
    raw_elev_values = set()
    for r in records:
        pe = r.get("project_english_name") or ""
        pc = r.get("project_chinese_name") or ""
        de, dc = r.get("district_english_name") or "", r.get("district_chinese_name") or ""
        re_, rc = r.get("region_english_name") or "", r.get("region_chinese_name") or ""
        be, bc = r.get("english_name_of_block") or "", r.get("chinese_name_of_block") or ""
        raw_elev_values.add(str(r.get("avail_of_elevator_services")))
        elev = elevator_flag(r.get("avail_of_elevator_services"))
        floor_raw = str(r.get("floor_number") or "").strip()
        floor = as_float(floor_raw)
        area = as_float(r.get("internal_floor_area"))
        lat = as_float(r.get("project_map_latitude"))
        lng = as_float(r.get("project_map_longitude"))
        unit_rows.append([pe, pc, de, dc, re_, rc, be, bc,
                          r.get("unit_number"), floor_raw, floor, area, elev, lat, lng])
        key = (pe, pc)
        p = projects.setdefault(key, {
            "project_en": pe, "project_tc": pc, "district_en": de, "district_tc": dc,
            "region_en": re_, "region_tc": rc, "lat": lat, "lng": lng,
            "total_units": 0, "elevator_units": 0, "non_elevator_units": 0,
            "floors": [], "areas": [], "blocks": set(),
        })
        p["total_units"] += 1
        p["elevator_units" if elev else "non_elevator_units"] += 1
        if floor is not None:
            p["floors"].append(floor)
        if area is not None:
            p["areas"].append(area)
        p["blocks"].add(be or bc)

    proj_rows = []
    for p in projects.values():
        fl, ar = p["floors"], p["areas"]
        proj_rows.append([
            p["project_en"], p["project_tc"], p["district_en"], p["district_tc"],
            p["region_en"], p["region_tc"], p["lat"], p["lng"],
            p["total_units"], p["elevator_units"], p["non_elevator_units"],
            len(p["blocks"]),
            min(fl) if fl else None, max(fl) if fl else None,
            round(sum(ar) / len(ar), 2) if ar else None,
        ])
    return unit_rows, proj_rows, sorted(raw_elev_values)


def localize(d, lang):
    """公共屋邨欄位形如 {'en':..,'zh-Hant':..}，抽指定語言；若非 dict 原樣返回。"""
    if isinstance(d, dict):
        return d.get(lang) or d.get("zh-Hant") or d.get("en") or ""
    return d or ""


def normalize_estates(records):
    rows = []
    for e in records:
        rows.append([
            localize(e.get("Estate Name"), "zh-Hant"), localize(e.get("Estate Name"), "en"),
            localize(e.get("District Name"), "zh-Hant"), localize(e.get("District Name"), "en"),
            localize(e.get("Region Name"), "zh-Hant"), localize(e.get("Region Name"), "en"),
            as_float(e.get("Estate Map Latitude")), as_float(e.get("Estate Map Longitude")),
            localize(e.get("Type of Estate"), "zh-Hant"),
            localize(e.get("Year of Intake"), "zh-Hant"),
            localize(e.get("Type(s) of Block(s)"), "zh-Hant"),
            localize(e.get("No. of Blocks"), "zh-Hant"),
            localize(e.get("Name of Block(s)"), "zh-Hant"),
            localize(e.get("No. of Rental Flats"), "zh-Hant"),
            localize(e.get("Flat Size (m2)"), "zh-Hant"),
            localize(e.get("Estate Management Advisory Committee (EMAC)"), "zh-Hant"),
            localize(e.get("Property Management"), "zh-Hant"),
            localize(e.get("Estate Website"), "zh-Hant"),
        ])
    return rows


def build_lifecircle_notes():
    """Stage 1.5 待接入：CSDI WFS（學校位置 / 在校課後託管）嘅接入指引。"""
    return {
        "next_datasets": [
            {"name": "學校位置及資料", "ckan_id": "hk-edb-schinfo-school-location-and-information",
             "csdi": "edb_rcd_1629267205213_6391 (資助小學) 等，走 CSDI WFS GeoJSON"},
            {"name": "在校課後託管服務計劃", "ckan_id": "hk-swd-ycb-sba",
             "csdi": "swd_rcd_1727429602437_81314，走 CSDI WFS GeoJSON"},
        ],
        "note": "兩者需要 CSDI WFS 服務 URL + 圖層 ID；Stage 1.5 接入後可算『15 分鐘生活圈』。",
    }


def main():
    report = {"run_at": "2026-10-28", "sources": SOURCES}

    # 1) 簡約公屋（單位級）
    lph = fetch_json(SOURCES["lph"])
    records = lph.get("records", [])
    raw_path = save_raw("lph_units.json", lph)
    unit_rows, proj_rows, elev_vals = normalize_lph_units(records)
    write_csv(os.path.join(NORM, "lph_units.csv"),
              ["project_en", "project_tc", "district_en", "district_tc", "region_en",
               "region_tc", "block_en", "block_tc", "unit_number", "floor_raw",
               "floor_num", "internal_floor_area", "elevator", "lat", "lng"], unit_rows)
    write_csv(os.path.join(NORM, "lph_projects_summary.csv"),
              ["project_en", "project_tc", "district_en", "district_tc", "region_en",
               "region_tc", "lat", "lng", "total_units", "elevator_units",
               "non_elevator_units", "blocks_count", "min_floor", "max_floor",
               "avg_internal_area"], proj_rows)
    report["lph"] = {
        "total_units": len(unit_rows),
        "total_projects": len(proj_rows),
        "elevator_raw_values": elev_vals,
        "sample_project": proj_rows[0] if proj_rows else None,
        "raw_file": raw_path,
    }

    # 2) 公共屋邨（屋邨級）
    estates = fetch_json(SOURCES["estates"])
    raw_path2 = save_raw("prh_estates.json", estates)
    est_rows = normalize_estates(estates)
    write_csv(os.path.join(NORM, "prh_estates.csv"),
              ["estate_tc", "estate_en", "district_tc", "district_en", "region_tc",
               "region_en", "lat", "lng", "estate_type", "year_intake", "block_types",
               "no_blocks", "block_names", "no_rental_flats", "flat_size_m2",
               "emac", "property_management", "website"], est_rows)
    regions = {}
    for r in est_rows:
        regions[r[4]] = regions.get(r[4], 0) + 1
    report["estates"] = {
        "total_estates": len(est_rows),
        "by_region": regions,
        "raw_file": raw_path2,
    }

    # 3) Stage 1.5 路標
    report["stage_1_5"] = build_lifecircle_notes()

    out = os.path.join(BASE, "stage1_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 4) 人類可讀摘要
    print("=" * 60)
    print("Stage 1 完成 ✔")
    print("-" * 60)
    print(f"簡約公屋：{len(unit_rows)} 個單位 / {len(proj_rows)} 個項目")
    for p in proj_rows[:8]:
        print(f"   {p[1]}（{p[3]}）單位 {p[8]}｜有升降機 {p[9]}｜樓層 {p[12]}–{p[13]}｜平均面積 {p[14]} m²")
    print(f"升降機欄位原始值：{elev_vals}")
    print("-" * 60)
    print(f"公共屋邨：{len(est_rows)} 個")
    for k, v in report["estates"]["by_region"].items():
        print(f"   {k}: {v} 個邨")
    print("-" * 60)
    print("輸出檔案：")
    for root in (RAW, NORM):
        if os.path.isdir(root):
            for fn in sorted(os.listdir(root)):
                print(f"   {os.path.relpath(os.path.join(root, fn), BASE)}")
    print(f"   stage1_report.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
