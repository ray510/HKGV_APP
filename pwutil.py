# -*- coding: utf-8 -*-
"""Playwright 開瀏覽器嘅唯一入口——保證「用完即清」。

為咩要包一層：Playwright 每次開 chromium 都會喺 %TEMP% 開 profile
（playwright_chromiumdev_profile-*）＋ crashpad（scoped_dir*）。正常 close 會自己刪，
但一 crash／timeout／被 kill 就留低幾百 MB。呢個 project 曾經被 121 個殘留
profile 食爆 C:（0 bytes → Python 一啟動即 crash）。

用法：
    from pwutil import open_browser

    with open_browser() as (browser, page):
        page.goto("http://127.0.0.1:8000/index.html")

離開 with 區塊（包括 exception）都會：
  1. 關 browser
  2. 掃走所有殘留 profile（chrome_cleanup.sweep）

自己寫測試時唔好用 p.chromium.launch()，用呢個 context manager 就唔會再漏。
"""
from __future__ import annotations

import contextlib
import os

from chrome_cleanup import sweep

DEFAULT_CHROME = os.path.expandvars(
    r"%LOCALAPPDATA%\ms-playwright\chromium-1243\chrome-win64\chrome.exe"
)


def chrome_path() -> str:
    """優先用環境變數 HKGV_CHROME，否則用本機 playwright 安裝嘅 chromium。"""
    return os.environ.get("HKGV_CHROME") or DEFAULT_CHROME


@contextlib.contextmanager
def open_browser(headless: bool = True, args: list[str] | None = None,
                 viewport: dict | None = None, keep_profile: bool = False):
    """開一個用完即清嘅 chromium，yield (browser, page)。

    keep_profile=True 只為除錯（保留 profile 唔刪）。
    """
    from playwright.sync_api import sync_playwright

    # 開之前先清上一次殘留（上次 crash 就會有）
    sweep(kill=True)

    launch_args = ["--proxy-server=direct://", "--proxy-bypass-list=*"]
    launch_args += list(args or [])

    pw = browser = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            executable_path=chrome_path(),
            headless=headless,
            args=launch_args,
        )
        ctx = browser.new_context(viewport=viewport or {"width": 1400, "height": 900})
        page = ctx.new_page()
        yield browser, page
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            if pw is not None:
                pw.stop()
        except Exception:
            pass
        if not keep_profile:
            sweep(kill=True)     # 收尾再掃：連 crashpad／scoped_dir 都清埋
