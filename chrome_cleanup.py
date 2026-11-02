# -*- coding: utf-8 -*-
"""清走 headless Chrome／Playwright 留低嘅暫存 profile。

背景：Playwright 每次開 chromium 都會喺 %TEMP% 開一個 profile 資料夾；
測試中途 crash／timeout（或者手動 kill）就會留低幾百 MB 垃圾。
呢個 project 之前就係咁樣被 121 個殘留 profile 食爆 C:（0 bytes，Python 一啟動就 crash）。

用法：
    python chrome_cleanup.py              # 掃描＋刪除，印返釋放幾多
    python chrome_cleanup.py --dry-run    # 只列出，唔刪
    python chrome_cleanup.py --kill       # 先殺 orphan headless chrome，再刪（預設已開）
    python chrome_cleanup.py --no-kill    # 唔殺 process，只刪資料夾

程式入面用：
    from chrome_cleanup import sweep
    sweep()          # 回傳釋放嘅 bytes

配搭 pwutil.open_browser() 就唔需要自己記得叫：佢開之前同閂之後都會自動 sweep。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))

# 只認呢啲開頭嘅資料夾，避免誤刪其他程式嘅暫存
PREFIXES = (
    "HeadlessChrome for Testing",
    "HeadlessChrome",
    "playwright_chromiumdev_profile",
    "playwright-artifacts",
    "playwright_firefoxdev_profile",
    "playwright_webkitsdev_profile",
    "scoped_dir",
    "chrome_scoped_dir",
    "hkgv_chrome_",          # 本 project 自己開嘅 profile（見 pwutil.py）
    "_cprof",                # 舊測試腳本用過嘅名字
)

# 掃描位置：%TEMP% ＋ 專案目錄
ROOTS = [os.environ.get("TEMP") or os.environ.get("TMP") or "", BASE]


def _targets(root: str) -> list[str]:
    """列出 root 之下符合前綴嘅資料夾（只一層，唔遞歸）。"""
    out = []
    if not root or not os.path.isdir(root):
        return out
    try:
        entries = os.scandir(root)
    except OSError:
        return out
    with entries as it:
        for e in it:
            try:
                if not e.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if e.name.startswith(PREFIXES):
                out.append(e.path)
    return out


def _size(path: str) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for fn in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                pass
    return total


def kill_orphan_headless(verbose: bool = False) -> int:
    """殺 headless chrome（連 --headless 或者用緊本 project profile 嘅）。

    正常 Chrome（用戶自己開嘅）唔會帶 --headless，所以唔會誤殺。
    """
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -match '--headless|hkgv_chrome_|_cprof' } | "
        "ForEach-Object { $_.ProcessId }"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return 0
    pids = [p.strip() for p in (r.stdout or "").split() if p.strip().isdigit()]
    n = 0
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", pid, "/F", "/T"],
                           capture_output=True, timeout=30)
            n += 1
        except (OSError, subprocess.SubprocessError):
            pass
    if verbose and n:
        print(f"  已殺 {n} 個 orphan headless chrome")
    return n


def _rm(path: str, attempts: int = 3) -> bool:
    for i in range(attempts):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(0.4 * (i + 1))   # 檔案鎖未放，等一等再試
    return False


def sweep(verbose: bool = False, dry_run: bool = False, kill: bool = True) -> int:
    """清一次，回傳釋放嘅 bytes。"""
    if kill and not dry_run:
        kill_orphan_headless(verbose)

    freed = 0
    failed = 0
    for root in ROOTS:
        for path in _targets(root):
            size = _size(path)
            if dry_run:
                print(f"  [dry-run] {path}  {size / 1048576:.1f} MB")
                freed += size
                continue
            if _rm(path):
                freed += size
                if verbose:
                    print(f"  刪 {os.path.basename(path)}  {size / 1048576:.1f} MB")
            else:
                failed += 1
                if verbose:
                    print(f"  ⚠️ 刪唔到（仍被佔用）：{path}")

    if verbose:
        print(f"  清理完成：釋放 {freed / 1048576:.1f} MB"
              + (f"，{failed} 個刪唔到" if failed else ""))
    return freed


def main() -> int:
    ap = argparse.ArgumentParser(description="清 headless Chrome／Playwright 暫存 profile")
    ap.add_argument("--dry-run", action="store_true", help="只列出，唔刪")
    ap.add_argument("--no-kill", action="store_true", help="唔殺 orphan headless chrome")
    ap.add_argument("-q", "--quiet", action="store_true", help="靜默")
    a = ap.parse_args()

    print("掃描：" + "、".join(r for r in ROOTS if r))
    freed = sweep(verbose=not a.quiet, dry_run=a.dry_run, kill=not a.no_kill)
    if a.dry_run:
        print(f"可釋放 {freed / 1048576:.1f} MB（未刪）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
