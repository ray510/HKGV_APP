import urllib.request, urllib.parse, json

terms = ["簡約公屋", "公共租住房屋單位資料", "學校位置及資料", "在校課後託管服務計劃",
         "簡約公屋 單位資料", "公共屋邨位置及資料"]

base = "https://data.gov.hk/tc-data/api/3/action/package_search?"
for t in terms:
    q = urllib.parse.urlencode({"q": t, "rows": 5})
    url = base + q
    try:
        req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
        res = d.get("result", {})
        print(f"\n=== 搜尋：{t}  (count={res.get('count')}) ===")
        for p in res.get("results", []):
            print(f"  ID: {p.get('name')}")
            print(f"     題: {p.get('title')}")
            org = p.get("organization") or {}
            print(f"     機構: {org.get('title') if isinstance(org,dict) else org}")
            for r in p.get("resources", [])[:4]:
                print(f"       - [{r.get('format')}] {r.get('name')} -> {r.get('url')}")
    except Exception as e:
        print(f"[{t}] ERROR {e}")
