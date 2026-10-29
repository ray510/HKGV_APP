# 屋邨智配・3D 無障礙生活圈

**全港公屋及簡約公屋智能配對與三維無障礙出行平台** —— 空間數據共享平台大獎 2026（CSDI Awards 2026）公開組參賽原型。

> 兩步式解決兩個城市痛點：
> **① 智能配對** — 由單位級政府數據即時篩選合適屋邨，輸出「生活圈評分卡」（港鐵／小學／託管可達性）；
> **② 3D 實測出行** — 一鍵調用地政總署三維行人路線 API，以無障礙、避雨、行樓梯等模式規劃屋邨 → 港鐵站實測步行路線，附繁中逐向導航與垂直高差。

---

## 目錄

1. [快速開始](#快速開始)
2. [功能特點](#功能特點)
3. [檔案結構](#檔案結構)
4. [數據管線](#數據管線)
5. [數據來源](#數據來源)
6. [生活圈評分公式](#生活圈評分公式)
7. [3D 路線 API 使用說明](#3d-路線-api-使用說明)
8. [已知限制與疑難排解](#已知限制與疑難排解)
9. [開發路線圖](#開發路線圖)
10. [合規與免責聲明](#合規與免責聲明)

---

## 快速開始

零第三方依賴（純 Python stdlib + 前端 Leaflet CDN）。

```bash
# 1. （可選，約 2–5 分鐘）重跑數據管線：下載 18 區公屋單位 + 學校 + 託管點 + 評分
python pipeline_stage1.py    # 簡約公屋 28,951 單位 + 公共屋邨名單
python stage2_full.py        # 18 區公屋聚合 + 小學 + 託管 → 生活圈評分

# 2. 注入數據產出單檔原型（每次數據更新後重跑）
python build_app.py          # → index.html

# 3. 起本地服務（3D 路線 API 需要 http(s) 環境，file:// 會被瀏覽器擋）
python -m http.server 8642
# 打開 http://127.0.0.1:8642/（index.html）
```

**環境需求**：Python 3.8+（管線）；現代瀏覽器（原型）；網絡可連 `mapapi.hkmapservice.gov.hk`。

---


## GitHub Pages 線上版

原型已托管於 GitHub Pages（Source：`main` 分支根目錄，push 到 `main` 即自動重新部署）：

> **https://ray510.github.io/HKGV_APP/**

- 無需本地環境，手機／電腦瀏覽器直接開啟；3D 路線 API 為 https，CORS 已實測通過
- URL Hash 深連結照常可用，例如 `https://ray510.github.io/HKGV_APP/#estate=葵涌邨&mode=2&dest=mtr`
- 如需關閉／改設定：Repo → Settings → Pages

## 功能特點

| 功能 | 說明 |
|------|------|
| 全港覆蓋 | 258 個屋邨／項目（248 公屋 + 10 簡約公屋），共 1,049,480 個單位，全部單位級數據聚合 |
| 生活圈評分卡 | 港鐵可達性（0–45）＋ 小學可達性（0–35）＋ 託管可達性（0–20），公式公開，分項進度條展示 |
| 七重篩選 | 關鍵字、類型（公屋／簡約公屋）、18 區、全幢升降機、港鐵步行距離、最低評分、四種排序 |
| 3D 無障礙路線 | CSDI 三維行人路線 API，4 種出行模式，逐向繁中導航、路徑點、垂直高差統計 |
| 🎒 返學路線 | 每個屋邨預載最近 3 間小學（含座標），一鍵規劃「屋邨 → 小學」3D 無障礙接送路線，支援小學距離排序 |
| ⛰ 垂直高程剖面圖 | 路線結果附 SVG 剖面圖（海拔 vs 距離），標示地面線與地底段——2D 地圖睇唔到嘅第三維差異化功能 |
| ⚡ 多模式同屏對比 | 一鍵同時請求最短／無障礙／避雨 3 條路線，地圖同屏渲染（灰虛線 vs 實色線），自動生成量化結論（距離差、時間差、垂直爬升差） |
| 👥 評分視角切換 | 4 個 Persona 權重矩陣（育兒 35/30/20/15、長者 25/0/0/75、通勤 70/0/0/30、均衡 40/20/15/25）——基於 v3 標準化 sub_scores 前端即時重算評分、排序、地圖著色，AI 顧問偵測長者／輪椅自動切換 |
| 📊 比較籃＋列印報告 | 最多 3 個屋邨並排 PK（單位數／升降機覆蓋率／評分分項／三類可達性），一鍵列印 A4 社工／家庭揀樓評估報告（@media print 排版，前線社工可印紙本畀唔識用手機嘅長者） |
| 🔗 URL Hash 深連結 | 每條規劃好的路線自動寫入 `#estate=葵涌邨&mode=2&dest=mtr`，評審由 PDF 建議書超連結一鍵跳入場景、自動畫好 3D 路線 |
| 🤖 AI 選樓顧問（廣東話） | 【預設隱藏——設 `SHOW_AI_ADVISOR = true` 重啟】自然語言輸入家庭需要，規則引擎解析後自動套用篩選＋切換出行模式；正式版採用 LLM 函數調用 |
| 智能候選站 fallback | 每個屋邨預載最近 3 個港鐵站，最近站冇行人路直達時自動逐個嘗試，並如實標示改站原因 |
| 聯動反應 | 已顯示路線時**轉換出行模式 → 即刻自動重新規劃**；篩選後該屋邨被篩走 → 自動清除路線；地圖圓點同步淡化唔符合篩選嘅屋邨 |
| 誠實錯誤處理 | 拆解 ArcGIS 錯誤碼；離島／無鐵路屋邨（長洲、坪洲、梅窩、赤柱等）會明確話你知「冇步行路線去港鐵站」而唔係報系統故障 |

---

## 檔案結構

```
.
├── README.md                        ← 本檔案
├── csdi_awards_2026_proposal.md     ← CSDI Awards 2026 參賽建議書（10 頁內）
│
│ ── 原型（前端）──
├── index.html                       ← ★ 最終成品：單檔原型（build 產出，勿手改；GitHub Pages 根頁）
├── estate_matcher_template.html     ← 原型模板（__DATA__ 佔位符）
├── build_app.py                     ← build 腳本：注入數據 + 計算港鐵候選站
├── app_template.html                ← v1 舊模板（歷史保留）
├── hk_lph_matcher.html              ← v1 舊原型：只有 10 個簡約公屋（歷史保留）
│
│ ── 數據管線（Python，純 stdlib）──
├── pipeline_stage1.py               ← Stage 1：簡約公屋單位 + 公共屋邨名單
├── stage2_full.py                   ← Stage 2：18 區公屋聚合 + 小學 + 託管 + 評分
├── enrich_projects.py               ← 輔助：10 個簡約公屋項目連接最近港鐵站
├── verify_endpoints.py              ← API 端點實測驗證腳本
│
│ ── 探索與報告（前期調研產物）──
├── find_datasets.py                 ← CKAN API 數據集搜尋
├── categories_probe.py              ← 20 官方分類探測
├── categories_result.json           ← 分類原始結果（803 數據集）
├── hk_open_data_classification.html ← 開放數據分類梳理報告
├── idea_comparison.html             ← 6 個構思評分比較報告
├── stage1_report.json / stage1_summary.html ← Stage 1 報告
│
└── data/
    ├── raw/                         ← 原始下載
    │   ├── lph_units.json           ← 簡約公屋單位（房屋局）
    │   ├── prh_estates.json         ← 公共屋邨名單（房委會 ES Locator）
    │   └── mtr_venue_polygon.json   ← 港鐵場地多邊形 98 個（地政總署 WFS）
    └── normalized/                  ← 清洗後
        ├── lph_units.csv            ← 28,951 個簡約公屋單位
        ├── lph_projects_summary.csv ← 10 個簡約公屋項目聚合
        ├── prh_estates.csv          ← 245 個公共屋邨
        ├── edb_schools.json         ← 697 間資助小學（含座標，build 快取）
        ├── swd_care_points.json     ← 311 個在校課後託管服務點（管線快取）
        ├── lph_projects_enriched.json
        └── all_estates_enriched.json ← ★ 258 屋邨 + v3 評分（sub_scores/density_800m，餵前端）
```

---

## 數據管線

### Stage 1 — `pipeline_stage1.py`
- 下載房屋局「簡約公屋」單位級 JSON（28,951 條）→ `lph_units.csv`、項目級聚合 → `lph_projects_summary.csv`
- 下載房委會 ES Locator 公共屋邨名單（245 個邨）→ `prh_estates.csv`
- 純 stdlib（`urllib` / `csv` / `json`），無需虛擬環境

### Stage 2 — `stage2_full.py`
1. **18 區房委會公屋單位**：`ha_prhs_{a..t}_en.json` 逐區下載，大檔用 `stream_records()` 流式解析（regex 切分避免 MemoryError），按屋邨聚合：升降機單位統計、平均面積、樓宇數、樓層範圍
2. **教育局學校位置** `SCH_LOC_EDB.json`：過濾小學（3,400+ 間學校 → 約 600 間小學）
3. **社署在校課後託管**：CSDI WFS `typename=csdi:SWDSBAEPS` → GeoJSON 服務點
4. **港鐵場地**：`mtr_venue_polygon.json`（98 個場地 bbox 中心）
5. 合併 LPH(10) + PRH(~248)，每個屋邨計算最近港鐵／小學／託管點（haversine 直線距離）+ 生活圈評分 → `all_estates_enriched.json`

### Build — `build_app.py`
- 讀取 `all_estates_enriched.json`，為每個有座標屋邨**計算最近 3 個港鐵站候選**（`mtr_candidates`，規劃路線 fallback 用）
- 注入 `estate_matcher_template.html` 的 `__DATA__` 佔位符 → `index.html`
- 內建安全檢查：payload 不得含 `__DATA__` 或 `</script`

### 輸出 schema（`all_estates_enriched.json`）

```jsonc
{
  "source": "PRH | LPH",
  "name_tc": "葵涌邨", "name_en": "Kwai Chung Estate",
  "district_tc": "葵青", "region_tc": "新界",
  "lat": 22.36, "lng": 114.13,          // 3 個新屋邨暫無座標
  "total_units": 13659, "elevator_units": 13659, "non_elevator_units": 0,
  "blocks_count": 30, "min_floor": 1, "max_floor": 40, "avg_area": 40.1,
  "score": 100,                          // 生活圈評分（見下節公式）
  "nearest_mtr":    { "zh": "大窩口鐵路站", "en": "...", "lat": ..., "lng": ..., "distance_m": 252 },
  "nearest_school": { "zh": "聖公會...", "distance_m": 119 },
  "nearest_care":   { "zh": "...託管中心", "distance_m": 136 },
  "mtr_candidates": [ { "zh": "...", "distance_m": ... } ]  // build_app.py 注入，最近 3 個
}
```

---

## 數據來源

| # | 數據集 | 提供機構 | 接口 |
|---|--------|----------|------|
| 1 | 「簡約公屋」單位資料 | 房屋局 | `https://data.hb.gov.hk/dataset/lph/hb_lphs_en.json` |
| 2 | 房屋委員會公共租住房屋單位資料 | 房委會 | `https://data.housingauthority.gov.hk/dataset/emms/ha_prhs_{a..t}_en.json`（18 區） |
| 3 | 三維行人路線搜尋 API（Enhanced 3D Pedestrian Route Search） | 地政總署 | `https://mapapi.hkmapservice.gov.hk/PedRoute/NAServer/route/solve` |
| 4 | 港鐵場地多邊形（mtr_venue_polygon） | 地政總署 | CSDI WFS（GeoJSON, WGS84, 98 個場地） |
| 5 | 學校位置及資料（SCH_LOC_EDB） | 教育局 | `http://www.edb.gov.hk/attachment/en/student-parents/sch-info/sch-search/sch-location-info/SCH_LOC_EDB.json` |
| 6 | 在校課後託管服務計劃（SBA） | 社會福利署 | CSDI WFS `typename=csdi:SWDSBAEPS&outputFormat=GEOJSON` |

全部經 [DATA.GOV.HK](https://data.gov.hk) / [CSDI Portal](https://portal.csdi.gov.hk) 公開發布；三維路線 API 已實測 CORS 開放（有反映 `Access-Control-Allow-Origin`），前端可直連、無需後端代理。

---

## 生活圈評分公式（v3：多維度 3D 空間可達性模型）

**v3 三大升級**（對比 v2 硬性分段 tier 制）：

1. **平滑衰減取代硬性分段**——消除「斷崖效應」：`S(d) = 100 × exp(-ln2/hl × max(0, d-d0))`，d0 為滿分半徑、hl 為半衰距離；無數據返中位數 50 分。分佈呈平滑曲線，滿分（≥99.95）屋邨由幾十個降至 **3 個**，排序鑑別度恢復（中位數 86.5）。
2. **距離 ＋ 800 米選擇密度**——小學分 ＝ 70% 最近距離 ＋ 30% 800m 內小學數（5 間滿分）；託管分 ＝ 80% 距離 ＋ 20% 密度（3 間滿分）。反映「步程內有幾多間可以揀」嘅真實生活圈資源差異。
3. **升降機無障礙覆蓋率納入評分**——單位級 `elevator_units/total_units × 100`，扣連「3D 無障礙生活圈」主題。

**各維度標準化參數**（0–100 分，一位小數）：

| 維度 | 滿分半徑 d0 | 半衰距離 hl | 備註 |
|------|------|------|------|
| 🚇 港鐵 | 200m | 900m | 最近港鐵場地直線距離 |
| 🏫 小學 | 150m | 800m | 70% 距離 ＋ 30% 密度（N₈₀₀/5） |
| 👶 託管 | 200m | 1200m | 80% 距離 ＋ 20% 密度（N₈₀₀/3） |
| 🛗 升降機 | — | — | 單位級覆蓋率直出 0–100 |

**4 個 Persona 權重矩陣**（前端即時重算，無需重跑管線）：

| 維度 | 👨‍👩‍👧 育兒家庭 | 👵 長者安居 | 🚇 極速通勤 | ⚖️ 均衡社區 |
|------|------|------|------|------|
| 港鐵可達性 | 35% | 25% | 70% | 40% |
| 小學可達性 | 30% | 0% | 0% | 20% |
| 託管可達性 | 20% | 0% | 0% | 15% |
| 升降機覆蓋 | 15% | 75% | 30% | 25% |

（長者模式接入醫管局急症室／民政署避暑中心後，75% 將拆分為「45% 升降機 ＋ 30% 醫療社區可達性」。）

**🎯 3D 實測校準（Two-Stage Calibration）**——規劃路線後即時以 Naismith 等效距離法則修正：`d_eff = d_3D + k × Σ正爬升`（k=8，無障礙模式多為斜道 k=4；實測步程滿分基準 300m、半衰 1100m），界面顯示「2D 預估 ➔ 3D 校準」對比＋繞路系數＋垂直爬升。核心案例：葵涌邨直線 150m（2D 高分）vs 3D 實測步行 696m（繞路系數 4.64×）——證明立體城市必須用 CSDI 3D 路網，唔可以用 2D 直線距離。

評分僅反映「社區設施直線可達性」（3D 校準除外），非官方指標；公式完全公開透明，無黑箱。

---

## 3D 路線 API 使用說明

**端點**：`https://mapapi.hkmapservice.gov.hk/PedRoute/NAServer/route/solve`（ArcGIS NAServer REST 慣例，注意係 `/route/solve` 唔係 `/route`）

**關鍵參數**：

| 參數 | 值 | 說明 |
|------|-----|------|
| `stops` | `lng,lat;lng,lat` | 順序係 **經度,緯度**（WGS84, EPSG:4326） |
| `returnZ` | `true` | 返回每個路徑點 (x, y, z, m)，z 用於高差統計 |
| `outSR` | `4326` | 輸出 WGS84，免除前端 HK1980 轉換 |
| `travelMode` | 1–5 | 見下表 |
| `directionsLanguage` | `zh-HK` | 繁體中文逐向導航 |
| `directionsStyleName` | `NA Campus` | 步行導航樣式 |

**出行模式**（`retrieveTravelModes` 實測確認）：

| travelMode | 模式 | 場景 |
|---|------|------|
| 1 | 最短路徑 | 基準 |
| 2 | 無障礙路徑 | 輪椅／嬰兒車：避梯級、優先升降機 |
| 3 | 推薦路徑 | API 預設 |
| 4 | 行樓梯健身 | 運動場景 |
| 5 | 非付費區優先 | 落雨免擔遮／全程有蓋有冷氣 |

**錯誤對照表**（實測整理）：

| 錯誤 | 意思 | 應對 |
|------|------|------|
| `400 / Unable to complete operation / No route from location ...` | 兩點之間**冇可行行人路**（隔住海、快速公路、封閉範圍），唔係系統故障 | 換候選站；離島屋邨（長洲、坪洲、梅窩、赤柱等）本質上冇路去任何港鐵站 |
| `GET /route` 只返服務資訊 | 打錯端點（少了 `/solve`） | 用 `/route/solve` |
| 前端 fetch 失敗 | 用 `file://` 開啟（CORS origin null）或網絡不通 | 用 `python -m http.server` 等 http(s) 環境開啟 |

---

## 已知限制與疑難排解

1. **必須以 http(s) 開啟**：3D 路線 API 由 `file://` 調用會被瀏覽器 CORS 擋。請 `python -m http.server` 後經 `http://127.0.0.1:8642/` 開啟（或直接用 GitHub Pages 線上版）。
2. **3 個屋邨暫無座標**：古雋邨（北區）、華富北邨（南區）、曉茵邨（觀塘）係新屋邨，房委會單位檔冇 `estate_map_latitude`、ES Locator 名單亦未收錄。已嘗試 Nominatim（無此新屋邨資料）與 geodata.gov.hk 地點搜尋（開發環境網絡受限）均失敗；原型標示「暫無座標」不上圖、不可規劃路線。待修：在正常網絡環境用 CSDI GeoAddress／數字政策辦公室「地址搜尋服務」補座標。
3. **6 個離島／無鐵路覆蓋屋邨無法規劃港鐵路線**：長貴邨（長洲）、金坪邨（坪洲）、銀灣邨（梅窩）、馬坑邨（赤柱）、龍田邨、雅寧苑 —— **地理事實，非 bug**。原型會如實說明。可考慮日後加「渡輪碼頭」作為替代錨點。
4. **距離為直線（haversine）近似**：評分卡距離非實測步行距離；實測路線以 3D API 為準。**錨點設計**：港鐵錨點取「場地多邊形邊界最近點」（點到線段投影）＋「站體中心」**雙錨點 fallback**，前端逐錨點嘗試——bbox 中心可能跌入站體範圍令網絡 snap 唔到（實例：天耀一邨→天水圍站直線 73m，邊界點實測 193m ✅，bbox 中心 ✗），邊界點亦可能面向路軌（葵涌邨→大窩口站直線 150m，中心實測 696m ✅，邊界點 ✗）。
5. **API 紀錄上限**：CSDI 服務單次查詢上限 5,000 條紀錄；管線以 18 區分檔下載、前端按場地逐個調用，已避開。
6. **舊座標系歷史數據**：個別數據集含 HK1980（EPSG:2326）EASTING/NORTHING 欄位，已於管線層處理；3D API 統一 `outSR=4326` 直出 WGS84。
7. **數據時效**：官方偶有欄位改名（2026-10 例子）；重跑 `stage2_full.py` 即可重新對齊。

---

## 開發路線圖

**比賽前（至 2026-12-05 截止）**
- [x] Stage 1 + Stage 2 數據管線（258 屋邨全量評分）
- [x] 可運行原型 v2（篩選 → 地圖 → 3D 路線 + 候選站 fallback）
- [x] 參賽建議書（`csdi_awards_2026_proposal.md`）
- [x] 垂直高程剖面圖（SVG，Z 軸差異化功能）
- [x] 地圖表面 Lands Department 版權聲明（合規）
- [x] 返學 3D 路線（最近 3 間小學候選＋小學距離排序）
- [x] AI 選樓顧問原型（廣東話規則引擎解析 → 自動套篩選＋切模式＋切評分視角）
- [x] 多模式同屏對比（最短 vs 無障礙 vs 避雨，量化結論）
- [x] 評分公式 v3：平滑衰減（消斷崖）＋ 800m 選擇密度 ＋ 升降機覆蓋 ＋ 4 Persona 權重矩陣
- [x] 3D 實測校準（Naismith 等效距離，「2D 預估 ➔ 3D 校準」動態對比標籤）
- [x] 比較籃並排 PK＋列印社工評估報告（提前實現賽後「社工版報告導出」）
- [x] URL Hash 深連結（評審由 PDF 一鍵跳入 3D 路線場景）
- [ ] AI 升級 LLM 函數調用（自然語言 → 篩選參數 + 粵語解釋，對應「最佳人工智能應用獎」）
- [ ] 1 分鐘演示片
- [ ] 3 個無座標新屋邨補座標（需正常網絡用官方地址搜尋服務）
- [ ] 長者模式數據升級：醫管局醫院／急症室位置＋民政署臨時避暑中心（CKAN 暫未搵到有座標嘅 HA JSON）
- [ ] 離島屋邨碼頭／巴士總站替代錨點（數碼共融）
- [ ] 配套數據擴充：幼稚園、安老院舍、社區會堂無障礙設施
- [ ] PWA manifest＋手機底部抽屜佈局

**決賽階段（12-19 工作坊起）**：現場演示三條真實路線（無障礙／避雨／健身）；3D 立體視覺（3D-BIT00 建築模型＋發光管線）如資源許可

**賽後 3 個月**：空氣質素圖層、臨時避暑中心、社工版報告導出（列印版已於賽前實現，賽後升級 PDF 導出）

---

## 合規與免責聲明

- 數據來源：香港特區政府 DATA.GOV.HK / CSDI Portal，版權屬各有關部門（房屋局、房委會、地政總署、教育局、社會福利署）。
- 地圖底圖 © [OpenStreetMap](https://www.openstreetmap.org/copyright) 貢獻者；路線服務由地政總署提供。
- 本專案為參賽開發原型，**非政府官方應用**；評分卡為開發者自訂指標，不構成任何揀樓／置業建議。
- 揀樓決定請以房屋局及房委會官方公布為準。

---

*最後更新：2026-10-29｜原型版本 v3.1（index.html, 479 KB, 雙錨點 fallback＋評分 v3＋3D 校準＋4 Persona；GitHub Pages 線上版見下）*
