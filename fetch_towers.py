"""下載地政總署「建築物」全部 Tower 質心 → cache/towers.jsonl（可分頁續傳）。

只用質心（returnCentroid），每幢約 230 bytes，213k 幢 ≈ 50MB，107 個 request。
"""
import json, os, sys, time, urllib.parse, urllib.request

BASE = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637211194312_35158/FeatureServer/0/query"
OUT = os.path.join("cache", "towers.jsonl")
PAGE = 2000


def fetch(offset, tries=3):
    p = {
        "where": "BuildingBlockType='Tower'",
        "outFields": "BuildingNameTC,Storeys,TopHeight,BaseHeight,BuildingID",
        "returnGeometry": "false", "returnCentroid": "true", "outSR": 4326,
        "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": PAGE, "f": "json",
    }
    url = BASE + "?" + urllib.parse.urlencode(p)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HKGV/1.0"})
            return json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 + 3 * i)


def main():
    os.makedirs("cache", exist_ok=True)
    done = 0
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            done = sum(1 for _ in f)
        print(f"續傳：已有 {done} 幢", flush=True)
    t0 = time.time()
    with open(OUT, "a", encoding="utf-8") as f:
        while True:
            d = fetch(done)
            feats = d.get("features") or []
            if not feats:
                break
            for ft in feats:
                a, c = ft.get("attributes") or {}, ft.get("centroid") or {}
                if c.get("y") is None:
                    continue
                f.write(json.dumps({
                    "n": a.get("BuildingNameTC"), "s": a.get("Storeys"),
                    "h": a.get("TopHeight"), "b": a.get("BaseHeight"),
                    "i": a.get("BuildingID"), "x": round(c["x"], 6), "y": round(c["y"], 6),
                }, ensure_ascii=False) + "\n")
            f.flush()
            done += len(feats)
            el = time.time() - t0
            print(f"  {done:,} 幢  ({el:.0f}s, {done/max(el,1):.0f}/s)", flush=True)
            if len(feats) < PAGE:
                break
    print(f"完成：{done:,} 幢 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
