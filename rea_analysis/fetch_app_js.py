# -*- coding: utf-8 -*-
"""Download CSDI geoportal frontend JS files for REA analysis."""
import os
import urllib.request

BASE_PORTAL = "https://portal.csdi.gov.hk/geoportal/"
BASE_STATIC = "https://static.csdi.gov.hk/geoportal/"

FILES = [
    (BASE_PORTAL + "app/main.js", "geoportal/app/main.js"),
    (BASE_PORTAL + "app/context/AppContext.js", "geoportal/app/context/AppContext.js"),
    (BASE_PORTAL + "app/context/AppStarter.js", "geoportal/app/context/AppStarter.js"),
    (BASE_PORTAL + "app/configs/configJs.js", "geoportal/app/configs/configJs.js"),
    (BASE_STATIC + "custom/2024-revamp/js/script.js", "geoportal/custom/2024_script.js"),
    (BASE_STATIC + "custom/custom.js", "geoportal/custom/custom.js"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

out_dir = os.path.dirname(os.path.abspath(__file__))
for url, rel in FILES:
    dest = os.path.join(out_dir, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"OK   {len(data):>9,} B  {url}")
    except Exception as e:
        print(f"FAIL          {url}  ->  {e}")
