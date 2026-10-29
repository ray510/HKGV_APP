# -*- coding: utf-8 -*-
"""
EMSD 升降機覆核：用機電署「升降機詳情」74,550 部驗證房委單位檔嘅「有𨋢比例」。
策略：
  1) 抓全部含「邨／苑」嘅記錄（~14,000）
  2) 地址解析 → 提取屋邨名＋座名
  3) 與管線 258 邨 1,713 座匹配
  4) 輸出驗證報告（HTML＋JSON）
"""
import json, os, re, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
NORM = os.path.join(BASE, "data", "normalized")
UA = {"User-Agent": "Mozilla/5.0 (HKGV-EMSD-validation)"}
EMSD_ID = "emsd_rcd_1630562381876_94541"
OUT_HTML = os.path.join(BASE, "emsd_elevator_validation.html")
OUT_JSON = os.path.join(NORM, "emsd_elevator_validation.json")

def fetch_estate_lifts():
    """抓全部含 邨/苑 的 EMSD 記錄。"""
    base = f"https://portal.csdi.gov.hk/server/rest/services/common/{EMSD_ID}/FeatureServer/0/query"
    all_feats = []
    offset = 0
    where = "Address_Chinese LIKE '%邨%' OR Address_Chinese LIKE '%苑%'"
    while True:
        params = {
            "where": where, "outFields": "Address_Chinese,Type_of_Lift_Chinese,Lift_No",
            "resultOffset": str(offset), "resultRecordCount": "2000",
            "f": "json"
        }
        req = urllib.request.Request(base + "?" + urllib.parse.urlencode(params), headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        feats = d.get("features", [])
        if not feats:
            break
        all_feats.extend(feats)
        offset += len(feats)
        print(f"  fetched {len(all_feats)} ...", flush=True)
        if len(feats) < 2000:
            break
    return all_feats

def parse_address(addr):
    """
    解析 EMSD 地址，提取 (estate_name, building_name)。
    格式例：「九龍 長沙灣 長沙灣道 391號 長沙灣邨 長欣樓」
           「新界 葵涌 石籬邨 石籬商場二期」
    """
    addr = addr.strip()
    # 找最後一個含「邨／苑」的詞作為屋邨名
    parts = addr.split()
    estate_idx = None
    for i, p in enumerate(parts):
        if "邨" in p or "苑" in p:
            estate_idx = i
    if estate_idx is None:
        return None, None
    estate_name = parts[estate_idx]
    # 座名 = 屋邨名之後的部分（如果有）
    building_name = parts[estate_idx + 1] if estate_idx + 1 < len(parts) else None
    return estate_name, building_name

def normalize_name(n):
    """半形化、去空格。"""
    import unicodedata
    n = unicodedata.normalize("NFKC", n).replace(" ", "").replace("　", "")
    return n

def main():
    print("Step 1/4: 抓取 EMSD 升降機記錄...")
    feats = fetch_estate_lifts()
    print(f"總記錄：{len(feats)}")

    print("Step 2/4: 解析地址...")
    estate_building_lifts = {}  # estate -> building -> count
    estate_only_lifts = {}      # estate -> count (無法分拆座名)
    for ft in feats:
        a = ft["attributes"]
        addr = a.get("Address_Chinese", "")
        estate, building = parse_address(addr)
        if not estate:
            continue
        if building:
            estate_building_lifts.setdefault(estate, {}).setdefault(building, 0)
            estate_building_lifts[estate][building] += 1
        else:
            estate_only_lifts[estate] = estate_only_lifts.get(estate, 0) + 1

    print(f"  解析到屋邨：{len(estate_building_lifts)}（有座名）+ {len(estate_only_lifts)}（無座名）")

    print("Step 3/4: 載入管線數據並匹配...")
    with open(os.path.join(NORM, "all_estates_enriched.json"), encoding="utf-8") as f:
        estates = json.load(f)

    # 建立管線座名索引
    pipeline_index = {}  # normalized estate name -> estate obj
    block_index = {}     # normalized estate|block -> block obj
    for e in estates:
        ne = normalize_name(e["name_tc"])
        pipeline_index[ne] = e
        for b in e.get("blocks", []):
            nb = normalize_name(b["n"])
            block_index[f"{ne}|{nb}"] = {"estate": e, "block": b}

    # 匹配統計
    matched_estates = set()
    matched_blocks = set()
    estate_emsd_counts = {}  # estate name -> total lifts from EMSD
    block_lifts = {}         # source|estate|block -> emsd lift count (for build_app)

    for estate_name, buildings in estate_building_lifts.items():
        ne = normalize_name(estate_name)
        e = pipeline_index.get(ne)
        if e:
            matched_estates.add(ne)
            estate_emsd_counts[e["name_tc"]] = estate_emsd_counts.get(e["name_tc"], 0) + sum(buildings.values())
            for bname, count in buildings.items():
                nb = normalize_name(bname)
                key = f"{ne}|{nb}"
                if key in block_index:
                    matched_blocks.add(key)
                    binfo = block_index[key]
                    bkey = f"{binfo['estate']['source']}|{binfo['estate']['name_tc']}|{binfo['block']['n']}"
                    block_lifts[bkey] = block_lifts.get(bkey, 0) + count
        else:
            # 試模糊匹配：去掉「邨／苑」再試
            ne2 = ne.replace("邨", "").replace("苑", "")
            for pne, pe in pipeline_index.items():
                if ne2 in pne or pne in ne2:
                    matched_estates.add(pne)
                    estate_emsd_counts[pe["name_tc"]] = estate_emsd_counts.get(pe["name_tc"], 0) + sum(buildings.values())
                    for bname, count in buildings.items():
                        nb = normalize_name(bname)
                        key = f"{pne}|{nb}"
                        if key in block_index:
                            matched_blocks.add(key)
                            binfo = block_index[key]
                            bkey = f"{binfo['estate']['source']}|{binfo['estate']['name_tc']}|{binfo['block']['n']}"
                            block_lifts[bkey] = block_lifts.get(bkey, 0) + count
                    break

    # 無座名的直接計入屋邨總數
    for estate_name, count in estate_only_lifts.items():
        ne = normalize_name(estate_name)
        e = pipeline_index.get(ne)
        if e:
            matched_estates.add(ne)
            estate_emsd_counts[e["name_tc"]] = estate_emsd_counts.get(e["name_tc"], 0) + count

    total_pipe_estates = len(estates)
    total_pipe_blocks = sum(len(e.get("blocks", [])) for e in estates)

    print(f"  匹配屋邨：{len(matched_estates)}/{total_pipe_estates}")
    print(f"  匹配座：{len(matched_blocks)}/{total_pipe_blocks}")

    print("Step 4/4: 生成報告...")

    # 逐邨對比表
    comparison = []
    for e in estates:
        ne = normalize_name(e["name_tc"])
        emsd_total = estate_emsd_counts.get(e["name_tc"], 0)
        pipe_elev = e.get("elevator_units", 0)
        pipe_total = e.get("total_units", 0)
        pipe_blocks = len(e.get("blocks", []))
        emsd_blocks = sum(1 for bn in estate_building_lifts.get(e["name_tc"], {}) if f"{ne}|{normalize_name(bn)}" in block_index)
        comparison.append({
            "name_tc": e["name_tc"],
            "district_tc": e.get("district_tc", ""),
            "pipe_total_units": pipe_total,
            "pipe_elevator_units": pipe_elev,
            "pipe_blocks": pipe_blocks,
            "emsd_total_lifts": emsd_total,
            "emsd_matched_blocks": emsd_blocks,
            "pipe_elev_ratio": round(pipe_elev / pipe_total * 100, 1) if pipe_total else 0,
        })
    comparison.sort(key=lambda x: -x["emsd_total_lifts"])

    report = {
        "meta": {
            "emsd_dataset": EMSD_ID,
            "emsd_total_records": 74550,
            "emsd_estate_filtered": len(feats),
            "pipeline_estates": total_pipe_estates,
            "pipeline_blocks": total_pipe_blocks,
            "matched_estates": len(matched_estates),
            "matched_blocks": len(matched_blocks),
            "timestamp": "2026-10-29"
        },
        "comparison": comparison
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 座級映射（供 build_app.py 附加到每座）
    BLOCK_LIFTS_JSON = os.path.join(NORM, "emsd_block_lifts.json")
    with open(BLOCK_LIFTS_JSON, "w", encoding="utf-8") as f:
        json.dump(block_lifts, f, ensure_ascii=False, indent=2)
    print(f"  座級映射：{len(block_lifts)} 座 → {BLOCK_LIFTS_JSON}")

    # HTML 報告
    rows = ""
    for c in comparison:
        cls = "match" if c["emsd_total_lifts"] > 0 else "miss"
        rows += f"""<tr class="{cls}">
<td>{c['name_tc']}</td><td>{c['district_tc']}</td>
<td>{c['pipe_total_units']}</td><td>{c['pipe_elevator_units']}</td><td>{c['pipe_elev_ratio']}%</td>
<td>{c['pipe_blocks']}</td><td>{c['emsd_total_lifts']}</td><td>{c['emsd_matched_blocks']}</td>
</tr>"""

    html = f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>EMSD 升降機覆核報告</title>
<style>
body {{font-family:system-ui,sans-serif;max-width:1200px;margin:20px auto;padding:0 16px}}
h1 {{font-size:1.4rem}} .summary {{background:#f0f9ff;padding:12px;border-radius:8px;margin:12px 0}}
table {{width:100%;border-collapse:collapse;font-size:.9rem;margin-top:12px}}
th {{background:#0b6e99;color:#fff;text-align:left;padding:8px}}
td {{padding:6px 8px;border-bottom:1px solid #e5e7eb}}
tr.match {{background:#ecfdf5}} tr.miss {{background:#fef2f2}}
.num {{text-align:right;font-variant-numeric:tabular-nums}}
</style></head><body>
<h1>EMSD 升降機覆核報告</h1>
<div class="summary">
<b>數據源</b>：機電署「升降機詳情」<code>{EMSD_ID}</code>（74,550 部）<br>
<b>篩選</b>：地址含「邨／苑」→ {len(feats):,} 條<br>
<b>匹配</b>：屋邨 {len(matched_estates)}/{total_pipe_estates}（{len(matched_estates)/total_pipe_estates*100:.1f}%）｜
座 {len(matched_blocks)}/{total_pipe_blocks}（{len(matched_blocks)/total_pipe_blocks*100:.1f}%）
</div>
<table>
<tr><th>屋邨</th><th>區</th><th class="num">單位總數</th><th class="num">有𨋢單位</th>
<th class="num">𨋢覆蓋率</th><th class="num">座數</th><th class="num">EMSD 升降機</th><th class="num">EMSD 匹配座</th></tr>
{rows}
</table>
<p style="color:#666;font-size:.85rem;margin-top:12px">
備註：EMSD 數據包含商場、學校、停車場等附屬設施升降機，因此「EMSD 升降機」數通常高於「有𨋢單位數」。<br>
「EMSD 匹配座」= EMSD 地址解析到具體座名且與管線座名匹配成功。
</p>
</body></html>"""
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"報告已輸出：{OUT_HTML} ｜ {OUT_JSON}")

if __name__ == "__main__":
    main()
