# 附近餐廳搜尋系統 — 專案完整說明文件

> Python 課程期末專案 ｜ FastAPI 後端 + 靜態前端 ｜ 自然語言搜尋餐廳

---

## 目錄

1. [專案概述](#專案概述)
2. [系統架構](#系統架構)
3. [技術選用](#技術選用)
4. [目錄結構](#目錄結構)
5. [功能說明](#功能說明)
   - [使用者認證](#使用者認證)
   - [自然語言搜尋](#自然語言搜尋)
   - [地圖顯示](#地圖顯示)
   - [最愛餐廳](#最愛餐廳)
   - [幫我決定吃什麼](#幫我決定吃什麼轉盤)
   - [管理員功能](#管理員功能)
6. [API 端點](#api-端點)
7. [安全機制](#安全機制)
8. [NLP 模型](#nlp-模型)
9. [資料流程](#資料流程)
10. [部署說明](#部署說明)
11. [環境變數](#環境變數)

---

## 專案概述

本系統是一個以**繁體中文自然語言**搜尋附近餐廳的 Web 應用程式。使用者可以輸入像「10分鐘內想吃健康的午餐」這樣的自然語句，系統會自動解析意圖、搜尋附近符合條件的餐廳，並在互動地圖上標記結果。

### 核心設計原則

- **所有主要邏輯在 Python 後端執行**，前端 JavaScript 僅負責顯示
- 地圖由 Python Folium 在伺服器端產生，前端直接嵌入 HTML
- 使用 RSA-PSS SHA-256 數位簽章確保資料完整性

---

## 系統架構

```
使用者瀏覽器 (GitHub Pages)
    │
    │  HTTPS
    ▼
FastAPI 後端 (HuggingFace Spaces)
    ├── JWT 驗證
    ├── NLP 解析 (jieba + SVM)
    ├── Nominatim 搜尋 (OpenStreetMap)
    ├── Google Places API (補充搜尋)
    ├── OSRM 步行時間計算
    ├── Folium 地圖產生
    └── RSA-PSS SHA-256 簽章
```

### 前後端分離

| 層級 | 技術 | 部署位置 |
|------|------|---------|
| 前端 | HTML + CSS + 原生 JavaScript | GitHub Pages (靜態) |
| 後端 | Python FastAPI | HuggingFace Spaces (Docker) |
| 地圖 | Python Folium → Leaflet.js | 由後端產生，前端嵌入 |

---

## 技術選用

### 後端套件

| 套件 | 版本 | 用途 |
|------|------|------|
| fastapi | 0.115.0 | Web 框架、API 路由 |
| uvicorn | 0.30.6 | ASGI 伺服器 |
| python-jose | 3.3.0 | JWT Token 產生與驗證 |
| cryptography | 43.0.3 | RSA-PSS 數位簽章 |
| httpx | 0.27.2 | 非同步 HTTP 請求（Nominatim、OSRM、Google） |
| pydantic | 2.9.2 | 資料驗證與 Schema 定義 |
| folium | 0.17.0 | 伺服器端地圖產生 |
| scikit-learn | 1.5.2 | SVM 意圖分類模型 |
| jieba | 0.42.1 | 中文斷詞 |
| sentence-transformers | 3.3.1 | 語意相似度計算（NLP 備用） |
| numpy | 1.26.4 | 數值計算 |
| joblib | 1.4.2 | 模型序列化 |

### 前端技術

| 技術 | 用途 |
|------|------|
| 原生 JavaScript (ES6+) | 所有互動邏輯 |
| Web Crypto API | RSA-PSS 簽章驗證（瀏覽器端） |
| Leaflet.js | 互動地圖（由 Folium 自動引入） |
| SessionStorage | JWT Token 暫存 |

---

## 目錄結構

```
Finalproject/
├── backend/
│   ├── main.py                 # FastAPI 應用主程式、所有 API 端點
│   ├── config.py               # 環境變數設定
│   ├── auth/
│   │   └── jwt_handler.py      # JWT 產生與驗證
│   ├── crypto/
│   │   ├── keys.py             # RSA 金鑰載入
│   │   └── signer.py           # RSA-PSS 簽章 / 驗章
│   ├── nlp/
│   │   ├── train.py            # 離線訓練腳本
│   │   ├── predictor.py        # 推論（jieba + SVM）
│   │   └── models/             # 訓練好的 .pkl 模型檔
│   ├── services/
│   │   ├── nominatim.py        # OpenStreetMap 餐廳搜尋
│   │   ├── osrm.py             # 步行時間與路線計算
│   │   ├── google_places.py    # Google Places API 補充搜尋
│   │   ├── map_generator.py    # Folium 地圖產生
│   │   ├── favourites.py       # 最愛餐廳 JSON 儲存
│   │   └── user_store.py       # 使用者帳號 JSON 儲存
│   ├── models/
│   │   └── schemas.py          # Pydantic 資料模型
│   ├── scripts/
│   │   └── generate_keys.py    # 一次性 RSA 金鑰產生
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html              # 主頁面（登入 + 搜尋）
│   ├── css/
│   │   └── style.css           # 全站樣式（含 RWD）
│   └── js/
│       ├── config.js           # 後端 URL + RSA 公鑰
│       ├── auth.js             # JWT 登入 / 登出
│       ├── api.js              # fetch() 封裝
│       ├── signature.js        # SubtleCrypto 簽章驗證
│       └── app.js              # 主要應用邏輯
├── data/
│   ├── train_data.json         # NLP 訓練資料（50 筆標註）
│   ├── favourites.json         # 最愛餐廳資料（執行期產生）
│   └── users.json              # 使用者帳號資料（執行期產生）
├── keys/                       # RSA 金鑰（gitignore，不上傳）
│   ├── private_key.pem
│   └── public_key.pem
├── Dockerfile                  # HuggingFace Spaces 部署設定
├── README.md                   # HuggingFace Spaces 設定
└── PROJECT.md                  # 本文件
```

---

## 功能說明

### 使用者認證

#### 註冊 (`POST /register`)

使用者輸入帳號（2–20 字元）與密碼（至少 6 碼）進行註冊。

**密碼儲存流程：**
```
原始密碼
    ↓
PBKDF2-HMAC-SHA256（26萬次迭代 + 隨機 Salt）
    ↓
雜湊值存入 data/users.json（原始密碼永久丟棄）
```

`users.json` 儲存格式：
```json
{
  "alice": {
    "id": "uuid-v4",
    "username": "alice",
    "password_hash": "a3f2b1c4...(64字元十六進位)",
    "salt": "e9d2a1...(64字元隨機鹽值)",
    "created_at": "2026-05-21T14:30:00Z"
  }
}
```

#### 登入 (`POST /login`)

1. 前端以 `application/x-www-form-urlencoded` 格式送出帳號密碼
2. 後端驗證：重新計算 PBKDF2 雜湊，用 `hmac.compare_digest()` 比對（防時序攻擊）
3. 驗證通過 → 產生 JWT Token（HMAC-SHA256，含到期時間）
4. 前端將 Token 存入 `sessionStorage`（關閉分頁自動清除）

**JWT 結構：**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9   ← Header（演算法）
.eyJzdWIiOiJkZW1vIiwiZXhwIjoxNzc5...    ← Payload（帳號 + 到期）
.cfgPKHTlLwTKsUoTVttOJRvLDyn3Gdr...     ← Signature（HMAC-SHA256）
```

之後每個請求均在 HTTP Header 帶上：
```
Authorization: Bearer eyJhbGci...
```

---

### 自然語言搜尋

使用者輸入繁體中文查詢，系統執行以下完整流程：

#### 第一步：NLP 解析（`backend/nlp/predictor.py`）

- **斷詞**：`jieba.cut()` 中文斷詞
- **意圖分類**：TF-IDF 向量化 + SVM（RBF Kernel）分類
- **槽位抽取**：正規表示式抽取時間（「10分鐘」）、餐型（「午餐」）
- **食物關鍵字**：從斷詞結果直接抽取食物名詞

支援的意圖類別（16種）：

| 意圖 | 對應搜尋關鍵字 |
|------|--------------|
| find_japanese | japanese, sushi, ramen |
| find_korean | korean, bbq |
| find_western | western, pizza |
| find_hotpot | hotpot |
| find_chinese | chinese, dim sum |
| find_southeast_asian | vietnamese, thai |
| find_cafe | cafe, coffee |
| find_healthy | healthy, salad |
| find_vegetarian | vegetarian, vegan |
| find_dessert | dessert, cake, sweets |
| find_drinks | bubble tea, milk tea |
| find_fast_food | fast food, 麥當勞, 肯德基 |
| find_pasta | pasta, italian, 義大利麵 |
| find_steak | steak, 牛排 |
| find_rice | rice, 炒飯 |
| find_general | （直接用使用者輸入的關鍵字） |

#### 第二步：Nominatim 搜尋（`backend/services/nominatim.py`）

向 OpenStreetMap Nominatim API 搜尋附近符合條件的地點：

```
GET https://nominatim.openstreetmap.org/search
  ?q=<食物關鍵字>+restaurant
  &format=jsonv2
  &limit=20
  &viewbox=<使用者座標±範圍>
  &bounded=1
```

#### 第三步：Google Places 補充搜尋（`backend/services/google_places.py`）

當使用者切換至 Google 模式，額外呼叫 Google Places API (New) v1：

```
POST https://places.googleapis.com/v1/places:searchText
{
  "textQuery": "<食物關鍵字>",
  "locationBias": { "circle": { "center": {...}, "radius": 1200 } },
  "languageCode": "zh-TW",
  "maxResultCount": 10
}
```

- 同時取得 Google 評分（⭐）、評論數、評論文字
- 與 Nominatim 結果合併，距離 50 公尺內視為重複去除

#### 第四步：OSRM 步行時間（`backend/services/osrm.py`）

向 OSRM（Open Source Routing Machine）查詢實際步行時間：

```
GET https://router.project-osrm.org/table/v1/foot/<座標串>
  ?sources=0&annotations=duration
```

- 回傳秒數 ÷ 60 = 步行分鐘數
- 過濾超過使用者指定時間限制的餐廳

#### 第五步：Folium 地圖產生（`backend/services/map_generator.py`）

Python Folium 在伺服器端產生完整 Leaflet 互動地圖：

- 藍色標記：使用者目前位置
- 紅色標記：每間符合條件的餐廳（含名稱、地址、步行時間、推薦原因）
- 藍色路線：OSRM 提供的實際步行路線
- 愛心標記：已加入最愛的餐廳

地圖以 `m._repr_html_()` 輸出為 `<iframe>` 字串，包含在 API 回應中。

#### 第六步：RSA-PSS SHA-256 簽章

```python
# 後端簽章
signed_data = json.dumps({"restaurants": [...], "parsed_query": {...}, "timestamp": "..."})
signature   = RSA_private_key.sign(signed_data, PSS(MGF1(SHA256()), salt_length=32))

# 前端驗章
isValid = await window.crypto.subtle.verify(
    { name: "RSA-PSS", saltLength: 32 },
    RSA_public_key,
    signature,
    signed_data
)
// isValid 為 false → 顯示紅色警告，拒絕渲染
```

---

### 地圖顯示

- **全螢幕地圖**：後端回傳的 Folium HTML 嵌入頁面
- **預設位置**：新竹市中心（lat: 24.8138, lon: 120.9675）
- **GPS 定位**：瀏覽器 Geolocation API 取得真實座標
- **手動定位**：輸入地址，後端 Nominatim geocoding 轉換座標
- **RWD 適配**：
  - 桌面版：地圖與聊天面板左右並排
  - 平板：地圖縮至 45%
  - 手機：聊天面板從底部滑出（50vh），地圖縮至上半部

---

### 最愛餐廳

- 每張餐廳卡片右上角有愛心按鈕（🤍 / ❤️）
- 點擊加入/移除最愛，儲存至後端 `data/favourites.json`（依使用者帳號分開）
- 左側側欄顯示所有最愛餐廳清單
- 「🗺 全部顯示在地圖」按鈕：一次標記所有最愛在地圖上
- 搜尋結果中，最愛餐廳自動排在最前面

**儲存格式（`data/favourites.json`）：**
```json
{
  "demo": [
    { "id": "node:123456", "name": "餐廳名稱", "latitude": 24.81, "longitude": 120.99, "address": "地址" }
  ]
}
```

---

### 幫我決定吃什麼（轉盤）

點擊頁面右下角 🎲 骰子按鈕，後端根據**當前台灣時間**以加權隨機選出建議食物。

**時段加權規則（`backend/main.py`）：**

| 時段 | 加權項目（權重 × 3） |
|------|-------------------|
| 06:00–09:59 早餐 | 早午餐、咖啡廳、珍珠奶茶 |
| 10:00–13:59 午餐 | 拉麵、台式便當、壽司、韓式料理、義大利麵 |
| 14:00–16:59 下午 | 甜點、咖啡廳、珍珠奶茶 |
| 17:00–20:59 晚餐 | 火鍋、牛排、烤肉、炸雞、披薩、壽司 |
| 21:00–05:59 宵夜 | 鍋貼、拉麵、炸雞、漢堡、珍珠奶茶 |

16 種食物選項（拉麵、壽司、火鍋、漢堡、台式便當、韓式料理、義大利麵、披薩、牛排、炸雞、甜點、早午餐、咖啡廳、珍珠奶茶、烤肉、鍋貼）

確認後自動填入搜尋框並執行搜尋。

---

### 管理員功能

以 `demo` 帳號登入後，工具列出現 **👥 用戶** 按鈕，顯示：

- 所有已註冊使用者清單
- 每位使用者的：帳號名稱、註冊時間、**PBKDF2-SHA256 密碼雜湊值**

> **注意**：顯示的是雜湊值，非原始密碼。原始密碼經過單向雜湊後無法還原，即使管理員也無法得知。

---

## API 端點

| 方法 | 路徑 | 需要 JWT | 說明 |
|------|------|---------|------|
| GET | `/health` | ❌ | 服務存活確認 |
| GET | `/public-key` | ❌ | 取得 RSA 公鑰（前端驗章用） |
| POST | `/register` | ❌ | 新使用者註冊 |
| POST | `/login` | ❌ | 登入，回傳 JWT Token |
| GET | `/basemap` | ✅ | 取得基礎地圖（無餐廳標記） |
| GET | `/spin` | ✅ | 隨機食物建議（時段加權） |
| POST | `/search` | ✅ | 完整搜尋流程，回傳餐廳 + 地圖 + 簽章 |
| GET | `/favourites` | ✅ | 取得使用者最愛清單 |
| POST | `/favourites` | ✅ | 新增最愛 |
| DELETE | `/favourites/{id}` | ✅ | 移除最愛 |
| GET | `/favourites/map` | ✅ | 所有最愛顯示在地圖 |
| GET | `/admin/users` | ✅ (admin) | 所有使用者清單（含密碼雜湊） |

---

## 安全機制

### 1. PBKDF2-HMAC-SHA256 密碼雜湊

```python
hashlib.pbkdf2_hmac(
    "sha256",
    password.encode("utf-8"),
    salt.encode("utf-8"),
    iterations=260_000   # NIST 建議值
)
```

- 每個使用者有獨立的隨機 Salt（32 bytes）
- 雜湊值與 Salt 分開儲存
- 使用 `hmac.compare_digest()` 比對，防止時序攻擊

### 2. JWT（JSON Web Token）

- 演算法：HMAC-SHA256
- 儲存於：`sessionStorage`（關閉分頁自動清除，比 localStorage 安全）
- 每次請求放在 HTTP Header，不放在 URL 或 Body
- Server-side 驗證，前端解碼僅供 UX 顯示

### 3. RSA-PSS SHA-256 數位簽章

- 金鑰長度：RSA-2048
- Salt 長度：固定 32 bytes（前後端一致）
- 簽章涵蓋範圍：餐廳清單 + 查詢結果 + 時間戳記
- 排除欄位：`map_html`、`signature`（避免自我簽章問題）
- 前端使用 Web Crypto API 驗章，失敗則拒絕渲染

### 4. CORS 限制

只允許指定來源（GitHub Pages + localhost）存取 API。

### 5. 金鑰管理

- RSA 私鑰、JWT Secret Key 只存在 HuggingFace Spaces 環境變數
- 絕不寫入程式碼或 git commit
- `keys/` 與 `.env` 已加入 `.gitignore`

---

## NLP 模型

### 訓練流程（`backend/nlp/train.py`）

1. 讀取 `data/train_data.json`（50 筆人工標註中文查詢）
2. `jieba.cut()` 中文斷詞
3. `TfidfVectorizer(ngram_range=(1,2))` 特徵萃取
4. `SVC(kernel='rbf', C=10, probability=True)` 訓練
5. 3-fold StratifiedKFold 交叉驗證（目標準確率 ≥ 80%）
6. 輸出 4 個 `.pkl` 模型檔至 `backend/nlp/models/`

### 推論流程（`backend/nlp/predictor.py`）

```python
def predict(text: str) -> dict:
    # 1. jieba 斷詞
    # 2. SVM 預測意圖（信心分數 < 0.35 → find_general）
    # 3. 正規表示式抽取時間（預設 15 分鐘）
    # 4. 正規表示式抽取餐型（早餐/午餐/晚餐）
    # 5. 語意相似度備援（SentenceTransformer）
    # 6. 回傳 { intent, food, time, meal, keywords, raw_keyword }
```

---

## 資料流程

```
使用者輸入：「10分鐘內想吃健康的午餐」
    │
    ▼
[後端] JWT 驗證 → 確認身份
    │
    ▼
[後端] NLP 解析
    intent    = "find_healthy"
    food      = "healthy"
    time      = 10（分鐘）
    meal      = "lunch"
    raw_keyword = "健康"
    │
    ▼
[後端] Nominatim → 搜尋「healthy restaurant」附近地點（約 20 筆）
    │
    ▼
[後端] OSRM → 計算每筆的步行時間 → 過濾 > 10 分鐘
    │
    ▼
[後端] 建立推薦理由（rule-based 繁體中文）
    │
    ▼
[後端] Folium → 產生 Leaflet 互動地圖 HTML（約 450KB）
    │
    ▼
[後端] RSA-PSS SHA-256 → 對餐廳清單 + 查詢 + 時間戳記簽章
    │
    ▼
[前端] 收到 JSON 回應
    ├── 驗章（Web Crypto API）→ ✅ 通過
    ├── 嵌入 Folium 地圖（map_html → innerHTML）
    └── 顯示餐廳卡片（名稱、地址、步行時間、評分、推薦原因）
```

---

## 部署說明

### 後端：HuggingFace Spaces（Docker）

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./backend/
COPY data/ ./data/
RUN python -m backend.nlp.train   # 建置時訓練模型
EXPOSE 7860
CMD uvicorn backend.main:app --host 0.0.0.0 --port 7860
```

URL：`https://changraeyu-restaurant-finder-api.hf.space`

### 前端：GitHub Pages（靜態）

`frontend/` 目錄直接部署，無需建置流程。

URL：`https://raeyu0714.github.io/restaurant-finder/`

---

## 環境變數

在 HuggingFace Spaces → Settings → Variables and secrets 設定：

| 變數名稱 | 說明 |
|---------|------|
| `JWT_SECRET_KEY` | HMAC-SHA256 簽章密鑰（256-bit 隨機十六進位） |
| `DEMO_USERNAME` | 管理員帳號（預設 `demo`） |
| `DEMO_PASSWORD` | 管理員密碼 |
| `RSA_PRIVATE_KEY_PEM` | RSA-2048 私鑰（PEM 格式，`\n` 換行） |
| `RSA_PUBLIC_KEY_PEM` | RSA-2048 公鑰（同時放在 `frontend/js/config.js`） |
| `CORS_ORIGINS` | 允許的前端來源（JSON 陣列格式） |
| `GOOGLE_MAPS_API_KEY` | Google Places API 金鑰（選填） |

---

## 本機開發

```bash
# 1. 安裝套件
pip install -r backend/requirements.txt

# 2. 訓練 NLP 模型
python -m backend.nlp.train

# 3. 產生 RSA 金鑰（首次）
python backend/scripts/generate_keys.py

# 4. 設定環境變數
cp backend/.env.example backend/.env
# 編輯 backend/.env 填入金鑰

# 5. 啟動後端
uvicorn backend.main:app --reload --port 8000

# 6. 啟動前端（另開終端機）
python -m http.server 3000 --directory frontend

# 7. 開啟瀏覽器
# http://localhost:3000
```

---

*本文件由 Claude Code 自動產生，最後更新：2026-05-21*
