# -*- coding: utf-8 -*-
"""Deep check: building name availability + PRH block name search."""
import urllib.request, urllib.parse, json, re

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def get(u, timeout=90):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout).read())

def raw(u, timeout=90):
    return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout).read().decode("utf-8", "replace")

def fs_sample(fs, layer, where="1%3D1", n=2):
    u = f"{fs}/{layer}/query?where={where}&outFields=*&resultRecordCount={n}&outSR=4326&f=json"
    return get(u).get("features", [])

# ---- 1) LandsD Building layer 0: fields? ----
FS_B = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637211194312_35158/FeatureServer"
print("=== Building layer 0 sample ===")
for f in fs_sample(FS_B, 0):
    print(" attrs:", json.dumps(f["attributes"], ensure_ascii=False)[:300])
    print(" geom type:", list((f.get("geometry") or {}).keys()))

# try search block name in polygons
for field_probe in ["NAME_TC", "NAME_EN", "NAME"]:
    try:
        u = f"{FS_B}/0/query?where={urllib.parse.quote(f'{field_probe} IS NOT NULL')}&returnCountOnly=true&f=json"
        print(f" probe {field_probe} non-null count:", get(u).get("count"))
    except Exception as e:
        print(f" probe {field_probe}: no such field ({str(e)[:60]})")

# ---- 2) WFS capabilities: find BuildingName layer name ----
print("\n=== WFS capabilities (Building dataset) ===")
caps = raw("https://portal.csdi.gov.hk/server/services/common/landsd_rcd_1637211194312_35158/MapServer/WFSServer?service=wfs&request=GetCapabilities")
names = re.findall(r"<Name>([^<]+)</Name>", caps)
print(" layers:", names[:20])
