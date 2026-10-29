import urllib.request, urllib.parse, json, sys

cats = [
    ("city-management","城市管理及公共設施"),
    ("climate-and-weather","氣象"),
    ("commerce-and-industry","工商業"),
    ("social-welfare","社區及社會福利"),
    ("development","發展、地理及土地資訊"),
    ("education","教育"),
    ("legislature","選舉及立法機關"),
    ("employment-and-labour","就業及勞工"),
    ("environment","環境"),
    ("finance","財經"),
    ("food","食物"),
    ("health","衞生"),
    ("housing","房屋"),
    ("law-and-security","法律及保安"),
    ("population","人口"),
    ("recreation-and-culture","康樂、體育及文化"),
    ("information-technology-and-broadcasting","科技及廣播"),
    ("tourism","旅遊"),
    ("transport","運輸"),
    ("miscellaneous","其他"),
]

base = "https://data.gov.hk/tc-data/api/3/action/package_search?"
out = {}
for slug, zh in cats:
    q = urllib.parse.urlencode({"fq": f"groups:{slug}", "rows": 60, "start": 0})
    url = base + q
    try:
        req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        res = data.get("result", {})
        total = res.get("count", 0)
        pkgs = res.get("results", [])
        titles = []
        for p in pkgs[:15]:
            t = p.get("title") or p.get("name")
            org = ""
            o = p.get("organization") or {}
            if isinstance(o, dict):
                org = o.get("title") or o.get("name") or ""
            titles.append((t, org))
        out[slug] = {"zh": zh, "count": total, "samples": titles}
        print(f"[{zh} / {slug}] total={total}, sampled={len(titles)}")
        for t, o in titles:
            print(f"   - {t}  ({o})")
    except Exception as e:
        out[slug] = {"zh": zh, "count": -1, "error": str(e)}
        print(f"[{slug}] ERROR {e}", file=sys.stderr)

with open("categories_result.json","w",encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nSAVED categories_result.json")
