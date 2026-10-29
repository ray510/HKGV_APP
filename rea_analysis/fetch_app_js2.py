# -*- coding: utf-8 -*-
"""Download second batch: AppClient, app-topics, main/App."""
import os
import urllib.request

BASE_PORTAL = "https://portal.csdi.gov.hk/geoportal/"

FILES = [
    (BASE_PORTAL + "app/context/AppClient.js", "geoportal/app/context/AppClient.js"),
    (BASE_PORTAL + "app/context/app-topics.js", "geoportal/app/context/app-topics.js"),
    (BASE_PORTAL + "app/main/App.js", "geoportal/app/main/App.js"),
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
