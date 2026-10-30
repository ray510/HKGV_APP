# -*- coding: utf-8 -*-
"""由地政總署「建築物」Tower 質心推導全港私人住宅屋苑（B 方案 v2）。

思路（唔用單鏈合併，避免「大角咀大廈 517 座」呢類鏈式爆炸）：
 1. 讀 cache/towers.jsonl（21 萬幢 Tower 質心）
 2. 剔除明顯非住宅名稱；剔除「大角咀」「旺角」等純地名（呢啲係地區，唔係屋苑）
 3. 已被現有 1,431 個錨點嘅座釘（200m 內）覆蓋 → 唔重複開新屋苑
 4. 前綴（3~7 字）分組 + **貪心緊湊聚類**（每組直徑 ≤300m，超過就切開）
 5. 組名 = 成員最長共同前綴（≥2 中文字且非地名），否則用前綴本身
 6. 同名／前綴關係且 <300m 再合併一次；對現有屋苑做名稱去重
 7. 單幢 ≥30 層亦收（單幢住宅大廈）

用法：python derive_estates.py [--min-towers 2]
輸出：derived_estates.json
"""
import json, math, os, re, sys, collections

BASE = os.path.dirname(os.path.abspath(__file__))
TOWERS = os.path.join(BASE, "cache", "towers.jsonl")
OUT = os.path.join(BASE, "derived_estates.json")
MAX_SPREAD = 300          # 一個屋苑嘅最大直徑（米）
MIN_TOWERS = 2

NONRES = ("學校", "中學", "小學", "幼稚園", "幼兒園", "大學", "書院", "學院", "教育",
          "教會", "教堂", "禮拜堂", "廟", "祠", "寺", "修道院", "靜修",
          "醫院", "診所", "醫療", "護養", "護老", "老人院", "安老", "敬老", "復康", "戒毒",
          "警署", "警崗", "消防局", "消防", "海關", "入境", "懲教", "監獄", "軍營", "軍部", "解放軍",
          "政府", "市政", "郵政", "郵局", "法院", "裁判", "圖書館", "體育館", "運動場", "球場",
          "泳池", "游泳池", "文娛", "社區中心", "社區會堂", "大會堂", "福利", "服務中心",
          "商場", "商廈", "寫字樓", "商業", "工業", "工廠", "貨倉", "倉庫", "貨櫃", "物流",
          "酒店", "賓館", "旅舍", "宿舍", "營舍", "度假",
          "車場", "停車場", "車房", "碼頭", "渡輪", "船廠", "油站", "加油站", "石油", "氣站",
          "變電", "電站", "電廠", "泵房", "水務", "水庫", "污水", "焚化", "堆填", "屠場", "屠房",
          "街市", "市集", "批發", "電訊", "機樓", "發射", "雷達", "氣象",
          "銀行", "會所", "俱樂部", "球會", "鄉事", "宗祠", "村公所", "互助",
          "農場", "公園", "植物園", "動物園", "水塘", "營地", "墳場", "墓", "骨灰", "火葬",
          "機場", "跑道", "貨運", "港口", "船塢", "魚市場", "村", "新村", "老圍",
          "通風", "康樂中心", "浸信", "宣道", "循道", "信義", "有限公司", "公司",
          "泳灘", "海灘", "沙灘", "寶福", "龕", "紀念", "涼亭", "燒烤", "觀景", "碼頭",
          "警局", "消防局", "救護", "醫療中心", "街坊", "合作社",
          "金融", "保險", "寫字樓", "商業大廈", "廣場", "酒店", "服務式", "商場", "百貨",
          "中心", "教區", "教堂", "修院", "神學院", "鐵路", "西鐵", "車廠", "機廠",
          "人壽", "保險大廈", "電訊", "電視", "廣播")
NONRES_EN = ("SCHOOL", "COLLEGE", "UNIVERSITY", "CHURCH", "HOTEL", "MALL", "INDUSTRIAL",
             "FACTORY", "WAREHOUSE", "HOSPITAL", "CLINIC", "POLICE", "FIRE STATION",
             "GOVERNMENT", "LIBRARY", "CINEMA", "THEATRE", "CAR PARK", "SUBSTATION",
             "TEMPLE", "MONASTERY", "OFFICE", "COMMERCIAL")

# 純地名（地區名）唔可以當屋苑名
GENERIC = {"香港", "九龍", "新界", "大角咀", "旺角", "油麻地", "佐敦", "尖沙咀", "紅磡",
           "土瓜灣", "九龍城", "黃大仙", "觀塘", "藍田", "油塘", "深水埗", "長沙灣", "荔枝角",
           "美孚", "荃灣", "葵涌", "青衣", "沙田", "大圍", "馬鞍山", "大埔", "粉嶺", "上水",
           "元朗", "天水圍", "屯門", "將軍澳", "西貢", "東涌", "灣仔", "銅鑼灣", "北角",
           "鰂魚涌", "西灣河", "筲箕灣", "柴灣", "香港仔", "鴨脷洲", "薄扶林", "堅尼地城",
           "中環", "上環", "半山", "山頂", "跑馬地", "何文田", "九龍塘", "石硤尾", "樂富",
           "慈雲山", "牛頭角", "牛池灣", "彩虹", "秀茂坪", "大坑", "掃管笏", "青山公路",
           "清水灣", "沙頭角", "梅窩", "長洲", "南丫島", "坪洲"}

BLOCK_SUFFIX = ("座", "閣", "樓", "臺", "台", "棟", "幢", "期")
CJK = re.compile(r"[\u4e00-\u9fff]")


def n_cjk(s):
    return len(CJK.findall(s or ""))


def is_res_name(n):
    if not n or n_cjk(n) < 2:
        return False
    s, u = n.strip(), n.strip().upper()
    if any(k in s for k in NONRES) or any(k in u for k in NONRES_EN):
        return False
    return True


def hav(a, b, c, d):
    R = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def norm(n):
    """繁簡／異體統一，否則「海天大廈／海天大厦」LCP 會斷成「海天大」。"""
    return (n or "").replace("厦", "廈").replace("臺", "台").replace("峯", "峰")


ADDR = re.compile(r"^.+[街道路里巷徑][0-9０-９]+[號A-Za-z]?$")


ROOT_STRIP = re.compile(
    r"([（(][^）)]*[）)]"                                       # （高座）
    r"|第?[0-9０-９一二三四五六七八九十百]+[A-Za-zＡ-Ｚ]?[座棟幢期]"  # 第1座／第２Ａ座／第一期
    r"|[Ａ-Ｚａ-ｚ]$"                                          # 全形字母座別（海天大廈Ａ）
    r"|(?<=[\u4e00-\u9fff座）)])\s*[A-Za-z]$"                # 半形字母只喺中文字後先剝（MONTEREY 唔可以剝爛）
    r"|座$|期$)\s*$")


def root_of(n):
    """「富匯豪庭第１座」→「富匯豪庭」；「海天大廈Ａ」→「海天大廈」。"""
    r = norm(n).strip()
    for _ in range(4):
        r2 = ROOT_STRIP.sub("", r).strip()
        if r2 == r:
            break
        r = r2
    return r


def lcp(names):
    names = [norm(x) for x in names]
    if not names:
        return ""
    s = names[0]
    for n in names[1:]:
        i = 0
        while i < min(len(s), len(n)) and s[i] == n[i]:
            i += 1
        s = s[:i]
        if not s:
            break
    return s


def trim_root(r):
    r = re.sub(r"第?[0-9０-９一二三四五六七八九十百]+[座棟幢期]?$", "", r or "")
    r = r.rstrip("第")
    r = re.sub(r"[A-Za-zＡ-Ｚａ-ｚⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]$", "", r.strip())   # 「匡湖居Ｆ」→「匡湖居」
    return r.strip()


def load_existing():
    """用 index.html 內嘅 DATA（已含 build_app 補完嘅 4,723 個座釘）。"""
    with open(os.path.join(BASE, "index.html"), encoding="utf-8") as f:
        h = f.read()
    i = h.find("const DATA = ") + len("const DATA = ")
    j = h.find(";\nconst COVERED", i)
    D = json.loads(h[i:j])
    out = []
    for e in D:
        if e.get("lat") is None or e.get("source_type") in ("PRVD", "VLG"):
            continue      # 唔可以用推導結果做「已覆蓋」；村落中心點唔係樓，唔計覆蓋
        pts = [(e["lat"], e["lng"])]
        for b in (e.get("blocks") or []):
            if b.get("lat") is not None and not b.get("nr"):
                pts.append((b["lat"], b["lng"]))
        out.append({"n": e["name_tc"], "lat": e["lat"], "lng": e["lng"],
                    "d": e.get("district_tc"), "t": e.get("source_type"), "pts": pts})
    return out


def load_towers():
    ts = []
    with open(TOWERS, encoding="utf-8") as f:
        for line in f:
            try:
                t = json.loads(line)
            except Exception:
                continue
            if t.get("x") is not None and t.get("y") is not None:
                ts.append(t)
    return ts


def dedupe_members(ms):
    """同一幢樓喺地政總署可能有多個 BuildingID（主樓／附屬體各自成塊）→ 同名同位置只留最高嗰個。"""
    out = []
    for t in sorted(ms, key=lambda z: -(z.get("s") or 0)):
        if any(t["n"] == o["n"] and hav(t["y"], t["x"], o["y"], o["x"]) < 20 for o in out):
            continue
        out.append(t)
    return out


def compact_cluster(members, radius):
    """貪心緊湊聚類：由一點開始，只收半徑內嘅點；超出就開新組。"""
    out = []
    for t in sorted(members, key=lambda x: (x["y"], x["x"])):
        placed = False
        for g in out:
            if hav(t["y"], t["x"], g["cy"], g["cx"]) <= radius:
                g["ms"].append(t)
                g["cy"] = sum(m["y"] for m in g["ms"]) / len(g["ms"])
                g["cx"] = sum(m["x"] for m in g["ms"]) / len(g["ms"])
                placed = True
                break
        if not placed:
            out.append({"cy": t["y"], "cx": t["x"], "ms": [t]})
    return out


def _blocks_out(ms, estate_name):
    """座名＝去掉屋苑名後嘅剩餘部分；剩餘為空或同名重複時，加（一）（二）區分，唔可以兩行同名。"""
    rows = []
    for t in sorted(ms, key=lambda z: ((z.get("s") or 0), (z.get("h") or 0)), reverse=True)[:40]:
        nm = t["n"].strip()
        rest = nm[len(estate_name):].strip() if nm.startswith(estate_name) else nm
        rows.append({"n": (rest or nm)[:14], "lat": round(t["y"], 6), "lng": round(t["x"], 6),
                     "s": t.get("s"), "h": round(t["h"], 1) if t.get("h") else None})
    seen = collections.Counter(r["n"] for r in rows)
    idx = collections.Counter()
    for r in rows:
        if seen[r["n"]] > 1:
            idx[r["n"]] += 1
            r["n"] = f"{r['n']}（{_CN[idx[r['n']]]}）"
    return rows


_CN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九",
       10: "十", 11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五", 16: "十六",
       17: "十七", 18: "十八", 19: "十九", 20: "二十"}


def main():
    global MIN_TOWERS
    if "--min-towers" in sys.argv:
        MIN_TOWERS = int(sys.argv[sys.argv.index("--min-towers") + 1])

    ex = load_existing()
    ts = load_towers()
    print(f"Tower {len(ts):,}｜現有錨點 {len(ex):,}", flush=True)

    named = [t for t in ts if is_res_name(t.get("n"))]
    print(f"有名且似住宅：{len(named):,}", flush=True)

    # 覆蓋：現有座釘 200m 內
    ex_idx = collections.defaultdict(list)
    for e in ex:
        for (py, px) in e["pts"]:
            ex_idx[(round(py, 2), round(px, 2))].append((e, py, px))

    def covered(t):
        gy, gx = round(t["y"], 2), round(t["x"], 2)
        for dy in (-0.01, 0, 0.01):
            for dx in (-0.01, 0, 0.01):
                for e, py, px in ex_idx.get((round(gy + dy, 2), round(gx + dx, 2)), ()):
                    # 座釘 120m／屋苑中心 100m：而家座釘係實測，唔需要 200m 咁闊，
                    # 否則隔籬屋苑（凱帆軒 vs 浪澄灣、揚海 vs 晉環）會被搶走
                    if hav(t["y"], t["x"], py, px) <= (120 if e.get("blocks") else 100):
                        return e
        return None

    left, n_cov = [], 0
    for t in named:
        if covered(t):
            n_cov += 1
        else:
            left.append(t)
    print(f"已被現有屋苑覆蓋 {n_cov:,}｜剩餘待聚類 {len(left):,}", flush=True)

    # 以「根名」分組：剝走 第X座／Ａ座／（…）／期 之後，同名同地＝同一屋苑
    by_root = collections.defaultdict(list)
    for t in left:
        r = root_of(t["n"])
        if ADDR.match(r):          # 「淺水灣道３７號」呢類係門牌，唔係屋苑名
            continue
        cjk = n_cjk(r)
        alpha = len(re.sub(r"[^0-9A-Za-z]", "", r))
        # 收中文名（≥2 字）同英文名（MONTEREY／LP6／SEA TO SKY…）——之前淨係收 3 字中文名，
        # 令 2013 後新盤（多數英文名）同「峻瀅II」呢類全部走甩
        if cjk + alpha < 2 or cjk + alpha > 20 or r in GENERIC \
                or r.endswith(("街", "道", "路", "里", "巷", "徑", "村")):
            continue
        if cjk < 2 and alpha < 3:
            continue
        by_root[r].append(t)

    used, groups = set(), []
    for r, members in by_root.items():
        cand = [t for t in members if t["i"] not in used]
        if len(cand) < MIN_TOWERS:
            continue
        # 2 字中文名（南灣、瑜一）撞名風險高 → 要 ≥3 座先收
        if n_cjk(r) == 2 and len(cand) < 3:
            continue
        for g in compact_cluster(cand, MAX_SPREAD / 2):
            ms = [t for t in g["ms"] if t["i"] not in used]
            if len(ms) < MIN_TOWERS:
                continue
            for t in ms:
                used.add(t["i"])
            groups.append({"name": r, "members": ms})

    # 單幢 ≥25 層（原本 ≥30，漏咗大量 25–29 層單幢樓）
    singles = 0
    for t in left:
        if t["i"] in used:
            continue
        if (t.get("s") or 0) >= 25:
            _r = root_of(t["n"])
            groups.append({"name": _r if (n_cjk(_r) >= 2 or len(re.sub(r"[^0-9A-Za-z]", "", _r)) >= 3)
                           else t["n"].strip(), "members": [t], "single": 1})
            used.add(t["i"]); singles += 1

    # 同名／前綴合併（<300m）
    for g in groups:
        g["lat"] = sum(t["y"] for t in g["members"]) / len(g["members"])
        g["lng"] = sum(t["x"] for t in g["members"]) / len(g["members"])
    groups.sort(key=lambda g: -len(g["members"]))
    merged = []
    for g in groups:
        for m in merged:
            same = g["name"] == m["name"]
            near_prefix = (m["name"].startswith(g["name"]) or g["name"].startswith(m["name"]))
            d = hav(g["lat"], g["lng"], m["lat"], m["lng"])
            if (same and d < 400) or (near_prefix and d < 300):
                m["members"].extend(g["members"])
                m["lat"] = sum(t["y"] for t in m["members"]) / len(m["members"])
                m["lng"] = sum(t["x"] for t in m["members"]) / len(m["members"])
                break
        else:
            merged.append(g)

    # 對現有屋苑去重（名近＋距近）
    ex_names = [(e["n"], e["lat"], e["lng"]) for e in ex]

    def dup(name, lat, lng):
        """同名／包含關係且夠近＝同一個屋苑（官方名可以係 2 字，例如「天晉」之於「海天晉」）。"""
        for nm, la, lo in ex_names:
            d = hav(lat, lng, la, lo)
            if nm == name and d < 1500:
                return nm
            if (nm in name or name in nm) and n_cjk(nm) >= 2 and n_cjk(name) >= 3 and d < 600:
                return nm
        return None

    out, n_low = [], 0
    for g in merged:
        ms = dedupe_members(g["members"])
        if len(ms) < MIN_TOWERS and not g.get("single"):
            continue
        if dup(g["name"], g["lat"], g["lng"]):
            continue
        st = [t["s"] for t in ms if t.get("s")]
        hh = [t["h"] for t in ms if t.get("h")]
        med = int(sorted(st)[len(st) // 2]) if st else None
        if med is not None and med < 3 and (len(ms) < 5 or g["name"].endswith("邨")):
            continue
        # 低密度（洋房／村屋群）唔算屋苑：匡湖居 454 幢「3 層」就係咁爆出嚟
        if med is None or med < 8:
            n_low += 1
            continue
        units = sum(int(t.get("s") or 0) * 6 for t in ms)
        out.append({
            "name_tc": g["name"], "lat": round(g["lat"], 6), "lng": round(g["lng"], 6),
            "towers": len(ms), "storeys_med": med,
            "height_max": round(max(hh), 1) if hh else None,
            "est_units": units, "est_pop": int(units * 2.7),
            "member_names": sorted({t["n"].strip() for t in ms})[:40],
            "blocks": _blocks_out(ms, g["name"]),
        })

    out.sort(key=lambda x: -x["towers"])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"\n推導屋苑 {len(out):,} 個（≥{MIN_TOWERS} 座）｜單幢 ≥30 層 {singles:,}｜低密度剔除 {n_low:,}", flush=True)
    print(f"  ≥3 座 {sum(1 for x in out if x['towers']>=3):,}｜≥10 座 {sum(1 for x in out if x['towers']>=10):,}", flush=True)
    print("  最大 12 個：", "、".join(f"{x['name_tc']}({x['towers']})" for x in out[:12]), flush=True)
    print(f"→ {OUT}", flush=True)


if __name__ == "__main__":
    main()
