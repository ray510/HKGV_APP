# -*- coding: utf-8 -*-
"""Batch download all app/search modules + templates + deps for REA analysis."""
import os
import urllib.request

BASE = "https://portal.csdi.gov.hk/geoportal/"

SEARCH_MODULES = [
    "SearchPane", "PageUrlFilter", "SearchBox", "SpatialFilter", "DateFilter",
    "TemporalFilter", "TermsAggregation", "TermsAggregationFSDT", "HierarchyTree",
    "BasicNumericFilter", "NumericFilter", "AppliedFilters", "ResultsPane",
    "OpenSearchLinksPane", "CollectionsFilter", "OnGeoAddress",
    "MetadataInfoPane", "QueryParameters", "BrowsePanel",
]
EXTRA = [
    ("app/main/templates/SearchPanel.html", "geoportal/app/main/templates/SearchPanel.html"),
    ("app/common/Templated.js", "geoportal/app/common/Templated.js"),
    ("app/etc/util.js", "geoportal/app/etc/util.js"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
out_dir = os.path.dirname(os.path.abspath(__file__))

ok = fail = 0
for name in SEARCH_MODULES:
    url = BASE + f"app/search/{name}.js"
    dest = os.path.join(out_dir, "geoportal", "app", "search", f"{name}.js")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        ok += 1
        print(f"OK   {len(data):>9,} B  app/search/{name}.js")
    except Exception as e:
        fail += 1
        print(f"FAIL           app/search/{name}.js -> {e}")

for rel, rel_dest in EXTRA:
    url = BASE + rel
    dest = os.path.join(out_dir, *rel_dest.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        ok += 1
        print(f"OK   {len(data):>9,} B  {rel}")
    except Exception as e:
        fail += 1
        print(f"FAIL           {rel} -> {e}")

print(f"\ndone: {ok} ok, {fail} fail")
