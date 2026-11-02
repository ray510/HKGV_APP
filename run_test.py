# -*- coding: utf-8 -*-
"""跑任何 Python 測試腳本，前後都清一次 headless Chrome 暫存。

用法：
    python run_test.py _probe.py
    python run_test.py _probe.py --headless

做嘅事：
  1. 開跑前 sweep（清上次 crash 留低嘅 profile，順便殺 orphan headless chrome）
  2. 用同一個 Python 跑目標腳本（繼承 stdout／exit code）
  3. 跑完再 sweep（就算腳本 timeout／拋 exception 都照清）

想再穩陣啲，測試腳本內部用 `from pwutil import open_browser`，
咁就算你直接 `python _probe.py`（唔經 wrapper）都會自動清。
"""
from __future__ import annotations

import os
import subprocess
import sys

from chrome_cleanup import sweep


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__.strip())
        return 2
    script, rest = argv[0], argv[1:]
    if not os.path.exists(script):
        print(f"搵唔到：{script}")
        return 2

    before = sweep(kill=True)
    print(f"▶ {script}（開跑前清走 {before / 1048576:.1f} MB）", flush=True)
    try:
        rc = subprocess.run([sys.executable, script, *rest]).returncode
    except KeyboardInterrupt:
        rc = 130
    finally:
        after = sweep(kill=True)
        print(f"■ 完成（exit {rc}）｜跑完清走 {after / 1048576:.1f} MB", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
