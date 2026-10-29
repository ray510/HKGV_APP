# -*- coding: utf-8 -*-
"""
Scan the full CSDI catalog (1,159 datasets) and rank which ones are worth
adopting to optimize 屋邨智配 (5-dimension scoring + roadmap gaps).
Output: JSON ranking used to build report section 11.
"""
import json
import re
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CAT = os.path.join(HERE, "..", "data", "csdi_catalog_full.json")
FACETS = os.path.join(HERE, "..", "data", "csdi_facets.json")
OUT = os.path.join(HERE, "optimize_ranking.json")

# datasets the project ALREADY uses (from README data-source table) - exclude from "new"
ALREADY_USED_IDS = {
    "swd_rcd_1633501860637_42476",   # SWD DCUDECC 長者日間護理
    "had_rcd_1634531497753_36049",   # HAD 社區會堂
    "had_rcd_1634542411218_91745",   # HAD 臨時避暑中心
    "had_rcd_1635393119641_62162",   # HAD 無障礙設施
    "landsd_rcd_1637211194312_35158",  # LandsD 建築物
    "fhb_rcd_1637120936400_35338",   # HA 專科門診目錄
}
ALREADY_USED_PATTERNS = [
    r"sch_loc_edb", r"edb_rcd",           # EDB 學校/幼稚園
    r"mtr_venue", r"landsd_rcd_16\d+_mtr", # MTR venues
    r"swd.*sba", r"swdsba",                # 在校課後託管
    r"lcsd.*pefac", r"pefac",              # 共融遊樂場
    r"pedestrian|pedroute|3d.*route",      # 3D 路線
    r"weather|hko",                        # 天文台
]
# known winners from previous session (already flagged in report section 7)
KNOWN_WINNERS = {
    "fhb_rcd_1636947932221_94410": "急症室等候時間 18 醫院（長者維度官方升級）",
    "swd_rcd_1633511356628_23572": "香港安老院位置 827 間（路線圖『安老院舍』）",
    "cedd_rcd_1696844622988_9055": "公眾碼頭 531 點（離島替代錨點）",
}

# dimension -> (regex_en_tc, weight, why)
DIMENSIONS = {
    "安老/長者服務": (r"安老|護養院|護理安老|長者|耆|elderly|aged|RCHE|senior", 10,
                 "長者 Persona 核心維度（現時長者日間護理只有 3 個點，亟需擴充）"),
    "醫療/診所": (r"門診|診所|醫院|clinic|hospital|健康中心", 8,
               "長者/會堂維度 30% 急症醫院之外嘅基層醫療錨點"),
    "託兒/幼兒": (r"幼兒|託兒|nursery|child care|day creche|CCP", 9,
               "育兒 Persona：課後託管(SBA)只覆蓋小學，幼兒中心填 0-6 歲缺口"),
    "交通錨點": (r"巴士總站|巴士路線|公共運輸交匯處|transport interchange|bus (terminus|stop)|"
             r"碼頭|渡輪|pier|ferry|gmb|minibus|小巴", 8,
             "路線圖『離島替代錨點』＋港鐵以外嘅 3D 目的地"),
    "無障礙/升降機": (r"無障礙|暢通無阻|barrier[- ]free|accessib|升降機|扶手電梯|lift|escalator|斜道", 7,
                 "『3D 無障礙』主題深化（座級已有，補社區層面無障礙點）"),
    "空氣/環境": (r"空氣質素|air quality|噪音|noise", 5,
               "賽後路線圖『空氣質素圖層』"),
    "社區設施": (r"社區會堂|社區中心|社區客廳|community (hall|centre|fridge)|福利設施|活動室", 6,
               "會堂維度密度升級（現時 115 個）"),
    "教育/學校": (r"小學|中學|幼稚園|學校|school|kindergarten", 4,
               "學校維度已用 EDB 全量，僅確認有冇官方版可取代爬取"),
    "3D/建築": (r"三維|3d model|建築物|building (footprint|outline)|photogrammetric", 3,
              "賽後 3D 視覺（3D-BIT00 單體化）"),
}

QUALITY_BONUS_FS = 3      # has FeatureServer
QUALITY_BONUS_GJ = 2      # has geojson file-api
QUALITY_BONUS_CSSD = 1    # CSSD official


def match_dims(r):
    text = " ".join(filter(None, [r.get("title_en"), r.get("title_tc"),
                                  r.get("description_en")]))[:400].lower()
    hits = []
    for dim, (pat, w, why) in DIMENSIONS.items():
        if re.search(pat, text, re.I):
            hits.append((dim, w, why))
    return hits


def is_used(r):
    rid = (r.get("id") or "").lower()
    if r["id"] in ALREADY_USED_IDS:
        return True
    for p in ALREADY_USED_PATTERNS:
        if re.search(p, rid):
            return True
    return False


def rcd_of(r):
    """dataset 真正 ID 係 {dept}_rcd_... 形式，藏在 thumbnail / resource URL。"""
    m = re.search(r"([a-z]+_rcd_\d+_\d+)", r.get("thumbnail") or "")
    if m:
        return m.group(1)
    for x in r["resources"]:
        m = re.search(r"([a-z]+_rcd_\d+_\d+)", x["url"] or "")
        if m:
            return m.group(1)
    return None


def main():
    cat = json.load(open(os.path.abspath(CAT), encoding="utf-8"))
    rows = []
    for r in cat:
        if r.get("type") not in (None, "d", "dataset"):
            continue
        dims = match_dims(r)
        if not dims:
            continue
        score = sum(w for _, w, _ in dims)
        why = "；".join(w for _, _, w in dims[:3])
        has_fs = any(x["type"] == "FeatureServer" for x in r["resources"])
        has_gj = any(x["type"] == "geojson" for x in r["resources"])
        q = (QUALITY_BONUS_FS if has_fs else 0) + (QUALITY_BONUS_GJ if has_gj else 0) \
            + (QUALITY_BONUS_CSSD if r.get("cssd") else 0)
        rcd = rcd_of(r)
        used = (rcd in ALREADY_USED_IDS) or is_used(r)
        known = KNOWN_WINNERS.get(rcd)
        rows.append({
            "id": r["id"], "rcd": rcd, "title": r.get("title_tc") or r.get("title_en"),
            "title_en": r.get("title_en"), "dept": r.get("dept_tc") or r.get("dept_en"),
            "category": r.get("category_tc") or r.get("category_en"),
            "score": score + q, "base_score": score, "quality": q,
            "has_fs": has_fs, "has_gj": has_gj, "cssd": bool(r.get("cssd")),
            "updated": r.get("metadata_updated") or (r.get("updated") or "")[:10],
            "already_used": used, "known_winner": known,
            "dims": [d for d, _, _ in dims], "why": why,
            "geojson_url": next((x["url"] for x in r["resources"] if x["type"] == "geojson"), None),
            "fs_url": next((x["url"] for x in r["resources"] if x["type"] == "FeatureServer"), None),
        })
    rows.sort(key=lambda x: -x["score"])
    json.dump(rows, open(os.path.abspath(OUT), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # quick console summary
    new_rows = [r for r in rows if not r["already_used"] and not r["known_winner"]]
    print(f"total matched: {len(rows)} | new candidates: {len(new_rows)}")
    print("\n=== TOP 25 NEW candidates (not already used) ===")
    for r in new_rows[:25]:
        print(f"[{r['score']:>3}] {r['title'][:44]:44s} | {str(r['dept'])[:14]:14s} | "
              f"FS={int(r['has_fs'])} GJ={int(r['has_gj'])} | {r['rcd']}")
    print("\n=== known winners (cross-check) ===")
    for r in rows:
        if r["known_winner"]:
            print(f"[{r['score']:>3}] {r['title'][:40]:40s} | {r['known_winner']}")
    print("\n=== already used (correctly excluded) ===")
    for r in rows:
        if r["already_used"]:
            print(f"  {r['title'][:40]:40s} | {r['rcd']}")


if __name__ == "__main__":
    main()
