# -*- coding: utf-8 -*-
"""Verify building-level location datasets:
1. LandsD 建築物 (BuildingName layer) — does it contain PRH block names + coords?
2. BD 樓宇資料及樓齡紀錄 — fields/granularity
3. HA 公共屋邨位置及資料 — estate or block level?
4. 3D-BIT00 — what's in it
"""
import urllib.request, urllib.parse, json

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read())

def fs_info(fs):
    m = get(fs + "?f=json")
    out = []
    for l in m.get("layers", []):
        u = f"{fs}/{l['id']}/query?where=1%3D1&returnCountOnly=true&f=json"
        try:
            c = get(u).get("count")
        except Exception:
            c = "?"
        out.append((l["id"], l.get("name"), c))
    return out

def sample(fs, layer, n=2, where="1%3D1"):
    u = f"{fs}/{layer}/query?where={where}&outFields=*&resultRecordCount={n}&outSR=4326&f=json"
    d = get(u)
    feats = []
    for f in d.get("features", [])[:n]:
        feats.append({"attrs": f.get("attributes", {}), "geom": f.get("geometry", {})})
    return feats

# ---- 1) LandsD Building ----
FS_B = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637211194312_35158/FeatureServer"
print("=== LandsD 建築物 layers ===")
for lid, name, cnt in fs_info(FS_B):
    print(f"  layer {lid}: {name} = {cnt}")

# BuildingName sample
print("\n--- BuildingName sample ---")
s = sample(FS_B, 2, n=2)  # guess layer id 2 = BuildingName (order from listing)
for f in s:
    print(json.dumps(f["attrs"], ensure_ascii=False)[:400])
    print("   geom:", str(f["geom"])[:120])
