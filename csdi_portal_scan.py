# -*- coding: utf-8 -*-
"""CSDI Portal (portal.csdi.gov.hk) full catalog scan via the search panel's
underlying REST API (Esri Geoportal Server 2):
  GET /geoportal/rest/metadata/search?f=json&q=<kw>&size=<n>&from=<offset>
Produces:
  - data/csdi_catalog.json   : compact full catalog (1 record per dataset)
  - csdi_portal_stats.json   : aggregated statistics + roadmap keyword scans
"""
import urllib.request, urllib.parse, json, time, collections, sys

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

def first(lst, default=""):
    if isinstance(lst, list) and lst:
        return lst[0]
    return lst if isinstance(lst, str) else default

# ---------- 1) full catalog ----------
hits, seen, from_, total = [], set(), 0, None
while True:
    d = search(size=200, start_from=from_)
    total = d.get("total", 0)
    batch = d.get("results", [])
    new = 0
    for r in batch:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        hits.append(r)
        new += 1
    sys.stderr.write(f"from={from_} got={len(batch)} new={new} total={total}\n")
    if new == 0 or len(hits) >= total:
        break
    from_ += max(len(batch), 1)
    time.sleep(0.4)

def compact(r):
    s = r.get("_source", {})
    org = s.get("apiso_OrganizationName_txt") or []
    cat = s.get("categories_s") or []
    subj = s.get("apiso_Subject_txt") or []
    res = []
    for it in s.get("resources_nst") or []:
        if it.get("url_s"):
            res.append({"type": it.get("url_type_s", ""), "url": it["url_s"]})
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
with open("data/csdi_catalog.json", "w", encoding="utf-8") as f:
    json.dump(catalog, f, ensure_ascii=False)

# ---------- 2) stats ----------
by_cat = collections.Counter(x["category_en"] or "(uncategorised)" for x in catalog)
by_dept = collections.Counter(x["dept_en"] or "(unknown)" for x in catalog)
by_svc = collections.Counter()
for x in catalog:
    types = {r["type"] for r in x["resources"]}
    for t in types:
        by_svc[t] += 1
cssd_n = sum(1 for x in catalog if x["cssd"])
with_bbox = sum(1 for x in catalog if x.get("bbox"))

def pdate(x):
    return (x.get("updated") or "")[:10]

recent90 = sum(1 for x in catalog if pdate(x) >= "2026-07-31")
recent365 = sum(1 for x in catalog if pdate(x) >= "2025-10-29")

stats = {
    "scan_date": "2026-10-29",
    "api": BASE,
    "total": len(catalog),
    "with_bbox": with_bbox,
    "cssd_total": cssd_n,
    "updated_last_90d": recent90,
    "updated_last_365d": recent365,
    "by_category_en": dict(by_cat.most_common()),
    "by_department_en_top25": dict(by_dept.most_common(25)),
    "by_service_type": dict(by_svc.most_common()),
}

# ---------- 3) roadmap keyword scans ----------
def kw_scan(q, size=10):
    try:
        d = search(q=q, size=size)
        out = []
        for r in d.get("results", []):
            s = r.get("_source", {})
            out.append({
                "title": first(s.get("title_tc_s"), r.get("title", "")),
                "title_en": r.get("title", ""),
                "dept": first(s.get("apiso_OrganizationName_txt"), (r.get("author") or {}).get("name", "")),
                "id": r.get("id", ""),
                "updated": (r.get("updated") or "")[:10],
                "endpoints": [x.get("url_type_s") for x in (s.get("resources_nst") or [])][:4],
                "first_url": first([x.get("url_s") for x in (s.get("resources_nst") or [])]),
            })
        return {"total": d.get("total", 0), "hits": out}
    except Exception as e:
        return {"total": -1, "error": str(e), "hits": []}

roadmap = {}
for label, kw in [
    ("hospital", "hospital"),
    ("hospital_tc", "醫院"),
    ("accident_emergency", "accident emergency"),
    ("residential_care_elderly", "residential care elderly"),
    ("residential_care_tc", "安老院"),
    ("pier", "pier"),
    ("pier_tc", "公眾碼頭"),
    ("bus_terminus", "bus terminus"),
    ("bus_tc", "巴士總站"),
    ("ferry", "ferry"),
    ("heat_shelter", "heat shelter"),
    ("playground_inclusive", "inclusive playground"),
]:
    roadmap[label] = kw_scan(kw)
    time.sleep(0.3)
stats["roadmap_scans"] = roadmap

# ---------- 4) bbox filter test ----------
try:
    d_all = search(q="pier", size=1)
    d_bbox = search(q="pier", size=1, extra={"bbox": "113.82,22.24,114.20,22.56", "geomRel": "esriGeometryRelationIntersection"})
    stats["bbox_test"] = {"kw_only": d_all.get("total"), "kw_plus_bbox_kowloon": d_bbox.get("total"),
                          "supported": d_all.get("total") != d_bbox.get("total")}
except Exception as e:
    stats["bbox_test"] = {"error": str(e)}

with open("csdi_portal_stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

# ---------- 5) console summary ----------
print(json.dumps({k: v for k, v in stats.items() if not k.startswith("roadmap")},
                 ensure_ascii=False, indent=2))
print("\n=== ROADMAP SCANS (total / top hits) ===")
for label, sc in roadmap.items():
    print(f"\n[{label}] total={sc.get('total')}")
    for h in sc.get("hits", [])[:3]:
        print(f"   - {h['title']} | {h['dept']} | {h['updated']} | {h['endpoints']}")
