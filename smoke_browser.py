# -*- coding: utf-8 -*-
"""煙霧測試：開／關 chromium，確認 profile 冇殘留（唔需要網絡）。"""
import os
from pwutil import open_browser

with open_browser() as (b, page):
    page.goto("about:blank")
    page.set_content("<h1 id=t>hello</h1>")
    print("頁面文字：", page.inner_text("#t"))
    print("chromium 版本：", b.version)

T = os.environ["TEMP"]
left = [n for n in os.listdir(T) if n.startswith(("playwright_chromiumdev_profile", "scoped_dir", "HeadlessChrome"))]
print("TEMP 殘留 profile：", left or "0 個 ✓")
