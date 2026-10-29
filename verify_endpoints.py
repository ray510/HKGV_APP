# -*- coding: utf-8 -*-
"""實測攻略文列出嘅關鍵 API 端點，驗證 1+2 聯動 / 構思3 嘅技術可行性。"""
import urllib.request, urllib.parse, json, ssl

UA = {"User-Agent": "Mozilla/5.0 (HK-OpenData-Verify)"}
CTX = ssl.create_default_context()


def get(label, url, max_len=400):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
            body = r.read().decode("utf-8", errors="replace")
        print(f"\n=== {label} === HTTP OK, bytes={len(body)}")
        print("  head:", body[:max_len].replace("\n", " "))
        return body
    except Exception as e:
        print(f"\n=== {label} === FAIL: {type(e).__name__}: {e}")
        return None


# 1) 三維行人路線 — 支援嘅出行模式
get("PedRoute travelModes",
    "https://mapapi.hkmapservice.gov.hk/PedRoute/NAServer/route/retrieveTravelModes?f=json")

# 2) 港鐵場地多邊形 WFS（先 GetCapabilities 探圖層名）
cap = get("mtr_venue_polygon GetCapabilities",
          "https://mapapi.hkmapservice.gov.hk/ogc/wfs/indoor/mtr_venue_polygon"
          "?service=WFS&version=1.1.0&request=GetCapabilities", max_len=600)
if cap:
    import re
    names = re.findall(r"<Name>([^<]+)</Name>", cap)
    print("  discovered typeNames:", names[:10])
    if names:
        q = urllib.parse.urlencode({
            "service": "WFS", "version": "1.1.0", "request": "GetFeature",
            "typeName": names[0], "outputFormat": "application/json", "maxFeatures": "2"})
        get("mtr_venue_polygon GetFeature",
            "https://mapapi.hkmapservice.gov.hk/ogc/wfs/indoor/mtr_venue_polygon?" + q)

# 3) 三維行人路線真實請求：彩興路 LPH → 觀塘站（lng,lat；travelMode=2 無障礙）
params = {"stops": "114.216,22.331;114.2253,22.3095", "f": "json",
          "returnZ": "true", "outSR": "4326", "travelMode": "2",
          "directionsLanguage": "zh-HK", "directionsStyleName": "NA Campus"}
get("PedRoute route (travelMode=2, returnZ=true)",
    "https://mapapi.hkmapservice.gov.hk/PedRoute/NAServer/route?" + urllib.parse.urlencode(params),
    max_len=500)

# 4) CKAN 驗證攻略文提到嘅數據集 ID 是否存在
BASE = "https://data.gov.hk/tc-data/api/3/action/package_show?id="
for ds in ["hk-housing-emms-emms-housing-stock", "hk-gld-suppmgmt2-auction-list",
           "hk-gld-suppmgmt4-addr-of-gld-auction-venue"]:
    try:
        req = urllib.request.Request(BASE + ds, headers=UA)
        d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
        if d.get("success"):
            r = d["result"]
            print(f"\n=== CKAN {ds} === 存在：「{r.get('title')}」 機構={r.get('organization',{}).get('title')}")
            for res in r.get("resources", [])[:5]:
                print(f"    [{res.get('format')}] {res.get('name')} -> {res.get('url')}")
        else:
            print(f"\n=== CKAN {ds} === API 返回 success=false")
    except Exception as e:
        print(f"\n=== CKAN {ds} === FAIL: {type(e).__name__}: {e}")
