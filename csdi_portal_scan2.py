# -*- coding: utf-8 -*-
"""Fix pagination (stable sort), test search recipes, pull item details
for roadmap-winning datasets."""
import urllib.request, urllib.parse, json, time, sys

BASE = "https://portal.csdi.gov.hk/geoportal/rest/metadata/search"
HDRS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def search(q="", size=200, start_from=0, extra=None):
    params = {"f": "json", "size": str(size), "from": str(start_from)}
    if q:
        params["q"] = q
    if extra:
        params.update(extra)
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))

# ---- 1) stable pagination test: sortField=title ----
d = search(size=5, extra={"sortField": "title", "sortOrder": "asc"})
print("sort test total:", d.get("total"), "| first titles:", [r["title"][:30] for r in d.get("results", [])])

hits, seen, from_ = [], set(), 0
total = None
while True:
    d = search(size=200, start_from=from_, extra={"sortField": "title", "sortOrder": "asc"})
    total = d.get("total", 0)
    batch = d.get("results", [])
    new = 0
    for r in batch:
        if r["id"] not in seen:
            seen.add(r["id"])
            hits.append(r)
            new += 1
    sys.stderr.write(f"from={from_} got={len(batch)} new={new} total={total}\n")
    if new == 0 or len(hits) >= total or not batch:
        break
    from_ += max(len(batch), 1)
    time.sleep(0.35)
print("unique records collected:", len(hits), "/", total)

def first(l, dflt=""):
    return l[0] if isinstance(l, list) and l else (l if isinstance(l, str) else dflt)

def compact(r):
    s = r.get("_source", {})
    org = s.get("apiso_OrganizationName_txt") or []
    cat = s.get("categories_s") or []
    subj = s.get("apiso_Subject_txt") or []
    res = [{"type": it.get("url_type_s", ""), "url": it["url_s"]}
           for it in (s.get("resources_nst") or []) if it.get("url_s")]
    dl = s.get("url_http_download_s")
    if dl and not any(x["url"] == dl for x in res):
        res.append({"type": "http_download", "url": dl})
    return {
        "id": r.get("id", s.get("fileid", "")),
        "title_en": r.get("title", ""),
        "title_tc": first(s.get("title_tc_s"), r.get("title", "")),
        "dept_en": first(org),
        "dept_tc": (org[1] if isinstance(org, list) and len(org) > 1 else first(org)),
        "category_en": first(cat),
        "category_tc": (cat[1] if isinstance(cat, list) and len(cat) > 1 else first(cat)),
        "cssd": "Common Sharable Spatial Data (CSSD)" in subj,
        "topics": subj,
        "formats": s.get("apiso_Format_s") or [],
        "resources": res,
        "updated": first(s.get("apiso_Modified_dt"), r.get("updated", "")),
        "bbox": r.get("bbox"),
        "crs": (s.get("apiso_CRS") or {}).get("id_s", ""),
        "thumbnail": first(s.get("url_thumbnail_s")),
    }

catalog = [compact(r) for r in hits]
json.dump(catalog, open("data/csdi_catalog.json", "w", encoding="utf-8"), ensure_ascii=False)
print("saved data/csdi_catalog.json")

# ---- 2) search recipes ----
recipes = [
    ('plain single TC word', '醫院'),
    ('quoted TC phrase', '"急症室"'),
    ('quoted TC phrase 2', '"香港安老院"'),
    ('field title TC', 'title:"急症室"'),
    ('field title EN', 'title:hospital'),
    ('desc EN phrase', 'description:"Accident and Emergency"'),
    ('dept scoped', 'apiso_OrganizationName_txt:"Hospital Authority"'),
]
print("\n=== SEARCH RECIPES ===")
for label, q in recipes:
    try:
        d = search(q=q, size=3)
        tot = d.get("total")
        tot = tot.get("value") if isinstance(tot, dict) else tot
        tops = [first(r.get("_source", {}).get("title_tc_s"), r.get("title", ""))[:44] for r in d.get("results", [])]
        print(f"[{label}] q={q!r} total={tot} | {tops}")
    except Exception as e:
        print(f"[{label}] q={q!r} ERROR {e}")
    time.sleep(0.3)

# ---- 3) roadmap winners: item details ----
def item_detail(q, want_title_kw):
    d = search(q=q, size=10)
    out = []
    for r in d.get("results", []):
        s = r.get("_source", {})
        t_tc = first(s.get("title_tc_s"), "")
        t_en = r.get("title", "")
        if want_title_kw in t_tc or want_title_kw.lower() in t_en.lower():
            urls = {it.get("url_type_s"): it.get("url_s") for it in (s.get("resources_nst") or [])}
            out.append({"title_tc": t_tc, "title_en": t_en, "id": r.get("id", ""),
                        "updated": first(s.get("apiso_Modified_dt")),
                        "urls": urls,
                        "abstract": first(s.get("apiso_Abstract_txt"))[:260]})
    return out

print("\n=== ROADMAP WINNERS DETAIL ===")
winners = {}
for key, (q, kw) in {
    "a_and_e_waiting": ('"急症室"', "急症室"),
    "elderly_homes": ('"香港安老院位置"', "香港安老院位置"),
    "public_piers": ('"公眾碼頭"', "公眾碼頭"),
}.items():
    winners[key] = item_detail(q, kw)
    time.sleep(0.3)

for k, v in winners.items():
    print(f"\n[{k}]")
    for it in v[:2]:
        print("  ✔", it["title_tc"], "|", it["updated"])
        print("    id:", it["id"])
        for t, u in it["urls"].items():
            print(f"      {t}: {u}")
        print("    abstract:", it["abstract"].replace("\n", " ")[:200])

json.dump(winners, open("csdi_roadmap_winners.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\nsaved csdi_roadmap_winners.json")

# ---- 4) probe record counts of the 3 winners' FeatureServers ----
print("\n=== FEATURE COUNT CHECK ===")
for k, v in winners.items():
    for it in v[:1]:
        fs = it["urls"].get("FeatureServer", "")
        if not fs:
            continue
        try:
            meta = json.loads(urllib.request.urlopen(urllib.request.Request(fs + "?f=json", headers=HDRS), timeout=40).read())
            layers = [l.get("name") for l in meta.get("layers", [])]
            cnts = []
            for l in meta.get("layers", []):
                u = f"{fs}/{l['id']}/query?where=1%3D1&returnCountOnly=true&f=json"
                c = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=HDRS), timeout=40).read())
                cnts.append((l.get("name"), c.get("count")))
            print(f"[{k}] {it['title_tc']}: layers={layers} counts={cnts}")
        except Exception as e:
            print(f"[{k}] ERROR {e}")
        time.sleep(0.3)
