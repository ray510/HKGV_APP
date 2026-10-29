# -*- coding: utf-8 -*-
"""Final verification: counts, SC field, estate-bbox demo (Kwai Chung Estate)."""
import urllib.request, urllib.parse, json

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
FS_B = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637211194312_35158/FeatureServer"

def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=90).read())

def count(where):
    u = f"{FS_B}/0/query?where={urllib.parse.quote(where)}&returnCountOnly=true&f=json"
    return get(u).get("count")

print("總多邊形:", count("1=1"))
print("有 BuildingNameTC:", count("BuildingNameTC IS NOT NULL"))
print("Tower:", count("BuildingBlockType='Tower'"))
print("Tower+有名:", count("BuildingBlockType='Tower' AND BuildingNameTC IS NOT NULL"))
print("Status=Active:", count("Status='Active'"))

# field list (check SC)
m = get(FS_B + "/0?f=json")
flds = [f["name"] for f in m.get("fields", [])]
print("\n全部欄位:", flds)

# estate bbox demo: 葵涌邨 (approx 22.443-22.455, 114.000-114.015)
bbox = "113.995,22.440,114.020,22.458"
u = (f"{FS_B}/0/query?where={urllib.parse.quote('BuildingBlockType=\'Tower\' AND BuildingNameTC IS NOT NULL')}"
     f"&geometry={bbox}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects"
     f"&outFields=BuildingNameTC,BuildingNameEN,BuildingBlockType,BuildingCSUID&returnGeometry=false"
     f"&resultRecordCount=40&f=json")
d = get(u)
print(f"\n=== 葵涌邨一帶 bbox 內有名 Tower（{d.get('features') and len(d['features']) or 0} 條）===")
names = sorted({(f['attributes'].get('BuildingNameTC'), f['attributes'].get('BuildingNameEN')) for f in d.get("features", [])})
for tc, en in names:
    print("  ", tc, "|", en)
