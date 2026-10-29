# -*- coding: utf-8 -*-
"""深挖②：社署/運輸署/醫管局數據盤點（離線聚合）＋深挖③：3D 模型源探測"""
import urllib.request, urllib.parse, json, collections

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
cat = json.load(open("data/csdi_catalog.json", encoding="utf-8"))

def get(u, timeout=60):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout).read())

# ---------- ② 盤點 ----------
def by_dept(dept_kw):
    return [x for x in cat if dept_kw.lower() in (x.get("dept_en") or "").lower()]

out = {}
for key, kw in {"swd": "Social Welfare", "td": "Transport Department", "ha": "Hospital Authority"}.items():
    ds = by_dept(kw)
    titles = sorted((x["title_tc"], x["title_en"], x["updated"][:10], x["cssd"]) for x in ds)
    out[key] = {"count": len(ds), "titles": titles}
    print(f"[{key}] {len(ds)} datasets")

# SWD theme categorization (TC title keywords)
swd_themes = collections.OrderedDict([
    ("長者/安老", ["長者", "安老", "老"]),
    ("復康/殘疾", ["殘疾", "復康", "盲人", "聾", "傷殘"]),
    ("託管/兒童/青少年", ["託管", "兒童", "青少年", "幼兒", "青年"]),
    ("家庭/輔導", ["家庭", "輔導", "婚姻", "親子"]),
    ("醫務/健康", ["醫務", "健康", "醫院"]),
    ("社區中心/服務", ["社區", "中心", "服務隊", "支援"]),
])
swd = out["swd"]["titles"]
theme_rows = {k: [] for k in swd_themes}
assigned = set()
for i, (tc, en, upd, cssd) in enumerate(swd):
    for theme, kws in swd_themes.items():
        if any(k in tc for k in kws):
            theme_rows[theme].append(f"{tc}（{upd}）")
            assigned.add(i)
            break
other = [f"{t[0]}（{t[2]}）" for i, t in enumerate(swd) if i not in assigned]
out["swd_themes"] = {k: v for k, v in theme_rows.items()}
out["swd_other"] = other

print("\n=== SWD 主題分佈 ===")
for k, v in theme_rows.items():
    print(f"  {k}: {len(v)}")
print(f"  其他: {len(other)}")

print("\n=== TD 全部 ===")
for t in out["td"]["titles"]:
    print("  -", t[0], f"({t[2]})")

print("\n=== HA 全部 ===")
for t in out["ha"]["titles"]:
    print("  -", t[0], f"({t[2]})")

# ---------- ③ 3D 模型源 ----------
print("\n=== 3D-BIT00 layers ===")
FS_3D = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637306559892_42396/FeatureServer"
try:
    m = get(FS_3D + "?f=json")
    for l in m.get("layers", []):
        cnt = get(f"{FS_3D}/{l['id']}/query?where=1%3D1&returnCountOnly=true&f=json").get("count")
        print(f"  layer {l['id']}: {l.get('name')} = {cnt}")
        feats = get(f"{FS_3D}/{l['id']}/query?where=1%3D1&outFields=*&resultRecordCount=1&f=json").get("features", [])
        if feats:
            print("    fields:", list(feats[0]["attributes"].keys()))
            print("    sample:", json.dumps(feats[0]["attributes"], ensure_ascii=False)[:260])
except Exception as e:
    print("  ERROR", e)

print("\n=== 可視化三維地圖（單體化）layers ===")
FS_IND = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1671676915450_88604/FeatureServer"
try:
    m = get(FS_IND + "?f=json")
    for l in m.get("layers", []):
        cnt = get(f"{FS_IND}/{l['id']}/query?where=1%3D1&returnCountOnly=true&f=json").get("count")
        print(f"  layer {l['id']}: {l.get('name')} = {cnt}")
        feats = get(f"{FS_IND}/{l['id']}/query?where=1%3D1&outFields=*&resultRecordCount=1&f=json").get("features", [])
        if feats:
            print("    fields:", list(feats[0]["attributes"].keys()))
            print("    sample:", json.dumps(feats[0]["attributes"], ensure_ascii=False)[:260])
except Exception as e:
    print("  ERROR", e)

json.dump(out, open("csdi_deepdive_inventory.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nsaved csdi_deepdive_inventory.json")
