# -*- coding: utf-8 -*-
"""Prove PRH block names exist in LandsD Building layer; check BD & HA granularity."""
import urllib.request, urllib.parse, json

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def get(u, timeout=90):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout).read())

FS_B = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637211194312_35158/FeatureServer"

def q(where, n=3, layer=0, extra=""):
    u = (f"{FS_B}/{layer}/query?where={urllib.parse.quote(where)}&outFields=*&"
         f"resultRecordCount={n}&outSR=4326&returnGeometry=true&f=json{extra}")
    return get(u)

# 1) named buildings count
c = q("BuildingNameTC IS NOT NULL", n=0)
print("BuildingNameTC 非空數量:", c.get("count"))

# 2) PRH block name test: 耀康樓 (葵涌邨)
d = q("BuildingNameTC LIKE '%耀康樓%'")
print("\n=== 搜「耀康樓」===")
print("count:", d.get("count"))
for f in d.get("features", []):
    a = f["attributes"]
    print(" ", a.get("BuildingNameTC"), "|", a.get("BuildingNameEN"), "|", a.get("BuildingBlockType"),
          "| CSUID:", a.get("BuildingCSUID"))
    rings = (f.get("geometry") or {}).get("rings") or []
    if rings:
        pts = [p for ring in rings for p in ring]
        lat = sum(p[1] for p in pts) / len(pts)
        lng = sum(p[0] for p in pts) / len(pts)
        print(f"   polygon centroid ≈ {lat:.6f}, {lng:.6f} ({len(pts)} vertices)")

# 3) another estate: 天耀邨 天耀樓? try 天逸邨/天澤樓
for kw in ["元州樓", "逸東樓"]:
    d = q(f"BuildingNameTC LIKE '%{kw}%'", n=1)
    fs = d.get("features", [])
    print(f"\n搜「{kw}」count={d.get('count')}")
    for f in fs:
        a = f["attributes"]
        print(" ", a.get("BuildingNameTC"), "|", a.get("BuildingBlockType"), "|", a.get("BuildingCSUID"))

# 4) block type distribution probe (Tower vs Podium counts)
for bt in ["Tower", "Podium", "Block"]:
    c = q(f"BuildingBlockType='{bt}'", n=0)
    print(f"\nBuildingBlockType={bt}: {c.get('count')}")

# ---- 5) BD 樓宇資料及樓齡紀錄 ----
FS_BD = "https://portal.csdi.gov.hk/server/rest/services/common/bd_rcd_1631167534872_19764/FeatureServer"
m = get(FS_BD + "?f=json")
print("\n=== BD 樓宇資料及樓齡紀錄 layers ===")
for l in m.get("layers", []):
    cnt = get(f"{FS_BD}/{l['id']}/query?where=1%3D1&returnCountOnly=true&f=json").get("count")
    print(f"  layer {l['id']}: {l.get('name')} = {cnt}")
    feats = get(f"{FS_BD}/{l['id']}/query?where=1%3D1&outFields=*&resultRecordCount=1&outSR=4326&f=json").get("features", [])
    if feats:
        print("   fields:", list(feats[0]["attributes"].keys()))
        print("   sample:", json.dumps(feats[0]["attributes"], ensure_ascii=False)[:280])
        print("   geom:", str(feats[0].get("geometry"))[:100])

# ---- 6) HA 公共屋邨位置及資料 – 公共屋邨 ----
FS_HA = "https://portal.csdi.gov.hk/server/rest/services/common/housingauthority_rcd_1765182404740_4034/FeatureServer"
m = get(FS_HA + "?f=json")
print("\n=== HA 公共屋邨位置及資料 layers ===")
for l in m.get("layers", []):
    cnt = get(f"{FS_HA}/{l['id']}/query?where=1%3D1&returnCountOnly=true&f=json").get("count")
    print(f"  layer {l['id']}: {l.get('name')} = {cnt}")
    feats = get(f"{FS_HA}/{l['id']}/query?where=1%3D1&outFields=*&resultRecordCount=1&outSR=4326&f=json").get("features", [])
    if feats:
        print("   fields:", list(feats[0]["attributes"].keys()))
        print("   sample:", json.dumps(feats[0]["attributes"], ensure_ascii=False)[:300])
