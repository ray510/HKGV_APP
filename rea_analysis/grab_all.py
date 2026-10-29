# -*- coding: utf-8 -*-
"""
Grab ALL CSDI portal datasets via the REA reverse-engineered Elasticsearch endpoint.

Endpoint (from REA static reconstruction of the geoportal search panel):
  GET/POST https://portal.csdi.gov.hk/geoportal/elastic/metadata/item/_search
  - GET params: size, from, sort ("fileid:asc")
  - POST body:  ES DSL (query.bool.must / aggregations / track_total_hits / _source excludes)
  - index: metadata_v1 (from ./rest/geoportal -> metadataIndexName)

Outputs:
  data/csdi_catalog_full.json   - all 1,159 records, normalized (no XML blobs)
  data/csdi_metadata_xml.zip    - full ISO 19115 XML for every record
  data/csdi_facets.json         - facet aggregations (category/department/theme/format/type)
"""
import io
import json
import os
import time
import zipfile
import urllib.request
import urllib.error

BASE = "https://portal.csdi.gov.hk/geoportal/elastic/metadata/item/_search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Accept": "application/json"}
OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(OUT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PAGE = 500


def fetch(url, data=None, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, data=data)
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # transient sandbox-proxy hiccups
            last = e
            print(f"  retry {i+1}/{retries}: {e}")
            time.sleep(3 * (i + 1))
    raise last


def get_all_hits():
    hits = []
    first = fetch(f"{BASE}?size={PAGE}&from=0&sort=fileid:asc")
    total = first["hits"]["total"]["value"]
    hits.extend(first["hits"]["hits"])
    print(f"total={total}, page1={len(first['hits']['hits'])}")
    from_ = PAGE
    while len(hits) < total:
        d = fetch(f"{BASE}?size={PAGE}&from={from_}&sort=fileid:asc")
        batch = d["hits"]["hits"]
        if not batch:
            break
        hits.extend(batch)
        print(f"  from={from_} -> +{len(batch)} (cum {len(hits)})")
        from_ += PAGE
    assert len(hits) == total, f"collected {len(hits)} != {total}"
    return hits, total


def first_or_str(v):
    """apiso_* date fields may be a plain string or a list - handle both."""
    if isinstance(v, list):
        return v[0] if v else None
    return v


def normalize(h):
    s = h["_source"]
    orgs = s.get("contact_organizations_s") or []
    cats = s.get("categories_s") or []
    themes = s.get("themes_s") or []
    subjects = s.get("apiso_Subject_txt") or []
    bbox = None
    env = s.get("envelope_geo")
    if env:
        try:
            coords = env[0]["coordinates"]
            bbox = {"xmin": coords[0][0], "ymin": coords[1][1],
                    "xmax": coords[1][0], "ymax": coords[0][1]}
        except Exception:
            pass
    cen = s.get("envelope_cen_pt")
    centre = {"lat": cen[0]["lat"], "lng": cen[0]["lon"]} if cen else None
    cat_tc = [c for c in cats if any("\u4e00" <= ch <= "\u9fff" for ch in c)]
    cat_en = [c for c in cats if c not in cat_tc]
    org_tc = [o for o in orgs if any("\u4e00" <= ch <= "\u9fff" for ch in o)]
    org_en = [o for o in orgs if o not in org_tc]
    return {
        "id": s.get("fileid"),
        "title_en": s.get("title"),
        "title_tc": s.get("title_tc_s"),
        "title_sc": s.get("title_sc_s"),
        "description_en": s.get("description"),
        "dept_en": org_en[0] if org_en else None,
        "dept_tc": org_tc[0] if org_tc else None,
        "category_en": cat_en[0] if cat_en else None,
        "category_tc": cat_tc[0] if cat_tc else None,
        "themes": themes,
        "cssd": "Common Sharable Spatial Data (CSSD)" in subjects,
        "type": (s.get("apiso_Type_s") or [None])[0],
        "formats": s.get("apiso_Format_s") or [],
        "resources": [{"type": r.get("url_type_s"), "url": r.get("url_s")}
                      for r in (s.get("resources_nst") or [])],
        "links": s.get("links_s") or [],
        "access": s.get("sys_access_s"),
        "created": s.get("sys_created_dt"),
        "updated": s.get("sys_modified_dt"),
        "metadata_updated": first_or_str(s.get("apiso_Modified_dt")),
        "bbox": bbox,
        "centre": centre,
        "crs": (s.get("apiso_CRS") or {}).get("id_s"),
        "thumbnail": s.get("url_thumbnail_s"),
        "metadatatype": s.get("sys_metadatatype_s"),
        "has_full_xml": bool(s.get("sys_xml_clob")),
    }


FACETS = {
    "by_category": "categories_s",
    "by_department": "contact_organizations_s",
    "by_theme": "themes_s",
    "by_format": "apiso_Format_s",
    "by_type": "apiso_Type_s",
}


def fetch_facets():
    body = {"size": 0, "track_total_hits": True,
            "aggregations": {k: {"terms": {"field": v, "size": 200}}
                             for k, v in FACETS.items()}}
    d = fetch(f"{BASE}?size=0", data=json.dumps(body).encode("utf-8"))
    out = {}
    for k, v in d["aggregations"].items():
        out[k] = {b["key"]: b["doc_count"] for b in v["buckets"]}
    return out


def main():
    t0 = time.time()
    hits, total = get_all_hits()
    print(f"grabbed {len(hits)} hits in {time.time()-t0:.0f}s")

    # 1) full ISO 19115 XML -> zip
    xml_path = os.path.join(DATA_DIR, "csdi_metadata_xml.zip")
    n_xml = 0
    with zipfile.ZipFile(xml_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for h in hits:
            xml = h["_source"].get("sys_xml_clob")
            if xml:
                z.writestr(f"csdi_xml/{h['_id']}.xml", xml)
                n_xml += 1
    print(f"xml zip: {n_xml} files, {os.path.getsize(xml_path):,} bytes")

    # 2) normalized catalog (no XML blobs)
    catalog = [normalize(h) for h in hits]
    cat_path = os.path.join(DATA_DIR, "csdi_catalog_full.json")
    with open(cat_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    print(f"catalog: {len(catalog)} records, {os.path.getsize(cat_path):,} bytes")

    # 3) facet aggregations
    facets = fetch_facets()
    fac_path = os.path.join(DATA_DIR, "csdi_facets.json")
    with open(fac_path, "w", encoding="utf-8") as f:
        json.dump(facets, f, ensure_ascii=False, indent=1)
    print(f"facets: {os.path.getsize(fac_path):,} bytes")
    print(f"done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
