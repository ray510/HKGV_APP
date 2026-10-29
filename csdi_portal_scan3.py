# -*- coding: utf-8 -*-
"""Final stats recompute + extra winners + sample feature field check."""
import urllib.request, urllib.parse, json, time, collections

BASE = "https://portal.csdi.gov.hk/geoportal/rest/metadata/search"
HDRS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def search(q, size=6):
    url = BASE + "?" + urllib.parse.urlencode({"f": "json", "q": q, "size": str(size),
                                              "sortField": "title", "sortOrder": "asc"})
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def first(l, dflt=""):
    return l[0] if isinstance(l, list) and l else (l if isinstance(l, str) else dflt)

catalog = json.load(open("data/csdi_catalog.json", encoding="utf-8"))

by_cat = collections.Counter(x["category_en"] or "(uncategorised)" for x in catalog)
by_dept = collections.Counter(x["dept_en"] or "(unknown)" for x in catalog)
by_svc = collections.Counter()
for x in catalog:
    for t in {r["type"] for r in x["resources"]}:
        by_svc[t] += 1
cssd_n = sum(1 for x in catalog if x["cssd"])
with_bbox = sum(1 for x in catalog if x.get("bbox"))
recent90 = sum(1 for x in catalog if (x.get("updated") or "")[:10] >= "2026-07-31")
recent365 = sum(1 for x in catalog if (x.get("updated") or "")[:10] >= "2025-10-29")
depts = len(by_dept)

stats = {
    "scan_date": "2026-10-29",
    "api": BASE,
    "total": len(catalog),
    "with_bbox": with_bbox,
    "cssd_total": cssd_n,
    "departments": depts,
    "updated_last_90d": recent90,
    "updated_last_365d": recent365,
    "by_category_en": dict(by_cat.most_common()),
    "by_department_en_top20": dict(by_dept.most_common(20)),
    "by_service_type": dict(by_svc.most_common()),
}

# extra winners: HA hospital directory + HAD heat shelters
extra = {}
for key, q in {"ha_directory": '"醫院管理局轄下醫院"', "heat_shelter": '"臨時避暑中心"'}.items():
    try:
        d = search(q)
        for r in d.get("results", []):
            s = r.get("_source", {})
            t_tc = first(s.get("title_tc_s"), "")
            urls = {it.get("url_type_s"): it.get("url_s") for it in (s.get("resources_nst") or [])}
            if ("醫院" in t_tc and key == "ha_directory") or ("避暑" in t_tc and key == "heat_shelter"):
                extra[key] = {"title_tc": t_tc, "id": r.get("id", ""),
                              "updated": first(s.get("apiso_Modified_dt"))[:10], "urls": urls}
                break
    except Exception as e:
        extra[key] = {"error": str(e)}
    time.sleep(0.3)
stats["extra_winners"] = extra
print(json.dumps(extra, ensure_ascii=False, indent=2))

# sample feature check: coordinates present?
def sample_feature(fs_url, layer_idx=0):
    u = f"{fs_url.rstrip('/')}/{layer_idx}/query?where=1%3D1&outFields=*&resultRecordCount=1&outSR=4326&f=json"
    req = urllib.request.Request(u, headers=HDRS)
    return json.loads(urllib.request.urlopen(req, timeout=40).read())

print("\n=== SAMPLE FEATURES ===")
samples = {}
checks = {
    "a_and_e": ("https://portal.csdi.gov.hk/server/rest/services/common/fhb_rcd_1636947932221_94410/FeatureServer", 0),
    "elderly_homes": ("https://portal.csdi.gov.hk/server/rest/services/common/swd_rcd_1633511356628_23572/FeatureServer", 0),
    "public_piers": ("https://portal.csdi.gov.hk/server/rest/services/common/cedd_rcd_1696844622988_9055/FeatureServer", 0),
}
for k, (fs, li) in checks.items():
    try:
        d = sample_feature(fs, li)
        f0 = (d.get("features") or [{}])[0]
        attrs = f0.get("attributes", {})
        geom = f0.get("geometry", {})
        small = {kk: (str(vv)[:40]) for kk, vv in list(attrs.items())[:10]}
        samples[k] = {"fields": list(attrs.keys()), "sample": small, "geometry": geom}
        print(f"[{k}] geometry={geom}")
        print(f"     fields={list(attrs.keys())}")
        print(f"     sample={small}")
    except Exception as e:
        samples[k] = {"error": str(e)}
        print(f"[{k}] ERROR {e}")
    time.sleep(0.3)
stats["sample_features"] = samples

json.dump(stats, open("csdi_portal_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nsaved csdi_portal_stats.json")
print(json.dumps({k: stats[k] for k in ["total", "with_bbox", "cssd_total", "departments",
                                        "updated_last_90d", "updated_last_365d"]}, ensure_ascii=False))
