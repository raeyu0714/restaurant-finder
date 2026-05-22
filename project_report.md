# 附近餐廳搜尋系統 — 完整技術報告

**專案名稱：** 附近餐廳搜尋 (Restaurant Finder)
**技術棧：** Python FastAPI · Folium · NLP (MiniLM + Logistic Regression) · Computer Vision (YOLOv8 + ViT) · JavaScript · Docker · HuggingFace Spaces · GitHub Pages

---

## 目錄

1. [系統架構總覽](#1-系統架構總覽)
2. [目錄結構](#2-目錄結構)
3. [Docker 部署](#3-docker-部署)
4. [後端 Backend](#4-後端-backend)
   - 4.1 config.py — 環境設定
   - 4.2 auth/jwt_handler.py — JWT 身份驗證
   - 4.3 crypto/signer.py — RSA 數位簽章
   - 4.4 main.py — FastAPI 應用程式與所有 API 端點
5. [NLP 自然語言處理系統](#5-nlp-自然語言處理系統)
   - 5.1 核心演算法：MiniLM 語意嵌入（Sentence Embedding）
   - 5.2 核心演算法：Logistic Regression 分類器
   - 5.3 nlp/train.py — 訓練腳本
   - 5.4 nlp/predictor.py — 推理引擎
6. [電腦視覺 / 食物辨識系統](#6-電腦視覺--食物辨識系統)
   - 6.1 核心演算法：YOLOv8n 物件偵測（第一關）
   - 6.2 核心演算法：Vision Transformer (ViT-B) 圖像分類（第二關）
   - 6.3 核心技術：遷移學習與 Last-Layer Fine-Tuning
   - 6.4 cv/scrape_data.py — 資料蒐集
   - 6.5 cv/prepare_dataset.py — 資料集整備
   - 6.6 cv/train.py — 模型訓練（完整說明）
   - 6.7 cv/food_recognizer.py — 推理引擎
7. [後端服務層 Services](#7-後端服務層-services)
   - 7.1 nominatim.py — OSM 地圖搜尋
   - 7.2 osrm.py — 步行時間計算
   - 7.3 map_generator.py — Folium 地圖產生器
   - 7.4 google_places.py — Google Places 補充搜尋
   - 7.5 user_store.py — 使用者資料
   - 7.6 favourites.py — 收藏功能
   - 7.7 group_store.py — 群組資料
   - 7.8 invitation_store.py — 邀請系統
   - 7.9 message_store.py — 群組聊天
   - 7.10 vote_store.py — 投票系統
   - 7.11 wallet_store.py — 錢包與轉帳
8. [資料模型 Pydantic Schemas](#8-資料模型-pydantic-schemas)
9. [前端 Frontend](#9-前端-frontend)
   - 9.1 index.html — 頁面結構
   - 9.2 css/style.css — 樣式設計
   - 9.3 js/config.js — 前端設定
   - 9.4 js/auth.js — 登入模組
   - 9.5 js/api.js — API 客戶端
   - 9.6 js/signature.js — 簽章驗證
   - 9.7 js/app.js (App) — 主應用程式邏輯
   - 9.8 js/app.js (GroupsPanel) — 群組面板
10. [完整資料流程](#10-完整資料流程)
11. [JSON 資料儲存](#11-json-資料儲存)
12. [安全設計](#12-安全設計)

---

## 1. 系統架構總覽

本系統是一個全端 Web 應用，採用前後端分離架構：

```
使用者瀏覽器
    │
    ├── 前端 (GitHub Pages — 靜態檔案)
    │     index.html / style.css / app.js / auth.js / api.js / signature.js
    │
    ↕  HTTPS / REST API (JWT Bearer Token)
    │
    └── 後端 (HuggingFace Spaces — Docker 容器)
          FastAPI (Python 3.11)
          ├── NLP 模組      — 解析中文自然語言查詢
          ├── CV 模組       — 食物圖片辨識
          ├── Nominatim     — OpenStreetMap 餐廳搜尋
          ├── OSRM          — 真實步行時間計算
          ├── Google Places — 補充搜尋 (選用)
          ├── Folium        — Python 生成地圖 HTML
          ├── RSA 簽章      — 防止資料竄改
          └── JSON 檔案     — 使用者/群組/投票/錢包資料
```

**核心設計原則：**
- 地圖由 Python (Folium) 在伺服器端產生，回傳 HTML iframe 字串給前端，前端只負責嵌入顯示。JavaScript 不直接操作地圖。
- 每次搜尋結果都附帶 RSA-PSS SHA-256 數位簽章，前端用 Web Crypto API 驗證，防止中間人竄改。
- NLP 模型完全自訓練，不依賴任何外部 AI API。
- 資料以 JSON 檔案持久化，使用 Python `threading.Lock` 保證執行緒安全。

---

## 2. 目錄結構

```
Finalproject/
├── Dockerfile                      # HuggingFace Spaces 建置腳本
├── backend/
│   ├── main.py                     # FastAPI 應用程式入口 + 所有 API 端點
│   ├── config.py                   # 設定 (env vars, 預設值)
│   ├── requirements.txt            # Python 相依套件
│   ├── auth/
│   │   └── jwt_handler.py          # JWT 建立/驗證
│   ├── crypto/
│   │   ├── keys.py                 # PEM 金鑰載入
│   │   └── signer.py               # RSA-PSS 簽章/驗章
│   ├── models/
│   │   └── schemas.py              # Pydantic 請求/回應模型
│   ├── nlp/
│   │   ├── train.py                # 訓練腳本 (離線執行)
│   │   ├── predictor.py            # 推理引擎 (runtime)
│   │   ├── models/                 # 訓練後的 .pkl 模型檔 (gitignored)
│   │   └── local_model/            # MiniLM 模型本地快取
│   ├── cv/
│   │   ├── scrape_data.py          # 台灣食物圖片爬取 (離線執行)
│   │   ├── prepare_dataset.py      # 資料集整備 (離線執行)
│   │   ├── train.py                # ViT 最後一層微調 (離線執行)
│   │   ├── food_recognizer.py      # 推理引擎 (runtime)
│   │   └── models/food_vit/        # 微調後的 ViT 模型 (327MB)
│   ├── services/
│   │   ├── nominatim.py            # OSM/Nominatim 搜尋
│   │   ├── osrm.py                 # OSRM 步行時間+路線
│   │   ├── map_generator.py        # Folium 地圖產生
│   │   ├── google_places.py        # Google Places API
│   │   ├── user_store.py           # 使用者 CRUD
│   │   ├── favourites.py           # 收藏 CRUD
│   │   ├── group_store.py          # 群組 CRUD
│   │   ├── invitation_store.py     # 邀請 CRUD
│   │   ├── message_store.py        # 群組訊息 CRUD
│   │   ├── vote_store.py           # 投票 CRUD
│   │   └── wallet_store.py         # 錢包/轉帳 CRUD
│   └── scripts/
│       └── generate_keys.py        # 一次性 RSA 金鑰生成
├── frontend/
│   ├── index.html                  # 頁面 HTML 結構
│   ├── css/style.css               # 全部樣式
│   └── js/
│       ├── config.js               # 後端 URL + RSA 公鑰
│       ├── auth.js                 # 登入/登出/JWT 儲存
│       ├── api.js                  # API 呼叫函式
│       ├── signature.js            # Web Crypto RSA 驗章
│       └── app.js                  # 主邏輯 (App + GroupsPanel)
└── data/
    ├── train_data.json             # NLP 訓練資料 (手工標注)
    ├── users.json                  # 使用者帳號 (bcrypt hash)
    ├── favourites.json             # 收藏資料
    ├── groups.json                 # 群組資料
    ├── invitations.json            # 邀請資料
    ├── group_messages.json         # 群組聊天訊息
    ├── group_votes.json            # 投票資料
    ├── wallets.json                # 錢包餘額
    └── transactions.json           # 消費紀錄
```

---

## 3. Docker 部署

**檔案：** `Dockerfile` (根目錄，供 HuggingFace Spaces 使用)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安裝 OpenCV/ultralytics 所需的系統套件
# Debian trixie 將 libgl1-mesa-glx 改名為 libgl1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# torch 和 torchvision 必須從同一個 CPU wheel index 安裝，版本才會匹配
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 安裝其餘套件 (requirements.txt 不含 torch/torchvision)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/

RUN mkdir -p backend/nlp/models backend/cv/models/food_vit

# 在建置時預下載 YOLOv8n 模型 (~6MB)，避免第一個請求很慢
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# 在建置時訓練 NLP 模型並儲存 .pkl 到 backend/nlp/models/
RUN python -m backend.nlp.train

EXPOSE 7860
CMD uvicorn backend.main:app --host 0.0.0.0 --port 7860
```

**關鍵設計決策：**

| 問題 | 解法 |
|------|------|
| `torchvision::nms` RuntimeError | `torch` 和 `torchvision` 從同一個 `--index-url https://download.pytorch.org/whl/cpu` 安裝，版本一致 |
| `libgl1-mesa-glx` 找不到 | Debian trixie 改名為 `libgl1`，直接用新名稱 |
| YOLO 第一次請求慢 | `RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"` 在 build 時預下載 |
| NLP 模型不存在 | `RUN python -m backend.nlp.train` 在 build 時完成訓練 |
| ViT 模型大小 327MB | 模型在本機訓練完後直接提交到 HF Spaces repo (需 Git LFS) |
| HF Spaces 預設 port | 使用 `--port 7860` (HF Spaces 標準 port) |

**`requirements.txt` (不含 torch/torchvision)：**
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.12
python-jose[cryptography]==3.3.0
cryptography==43.0.3
httpx==0.27.2
pydantic==2.9.2
python-dotenv==1.0.1
scikit-learn==1.5.2
jieba==0.42.1
folium==0.17.0
joblib==1.4.2
numpy==1.26.4
sentence-transformers
ultralytics>=8.3.0
```

---

## 4. 後端 Backend

### 4.1 `config.py` — 環境設定

所有設定從環境變數讀取，由 `Settings` 類別統一管理。`get_settings()` 回傳單例物件。

```python
class Settings:
    JWT_SECRET_KEY: str       # HMAC-SHA256 簽章金鑰
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60  # token 有效期 60 分鐘

    DEMO_USERNAME: str        # 管理員帳號名 (預設 "demo")
    DEMO_PASSWORD: str        # 管理員密碼 (只存在 env var，不進資料庫)

    RSA_PRIVATE_KEY_PEM: str  # RSA 私鑰 (簽章用)
    RSA_PUBLIC_KEY_PEM: str   # RSA 公鑰 (驗章用，也給前端)

    CORS_ORIGINS: list[str]   # 允許的跨域來源
    GOOGLE_MAPS_API_KEY: str  # Google Places API Key (選用)

    DEFAULT_LAT: float = 24.8138   # 新竹市中心 (GPS 失敗時的預設位置)
    DEFAULT_LON: float = 120.9675
```

`_pem()` 函式將環境變數中的 `\\n` 字面字串轉換為真正的換行符，因為 PEM 金鑰格式需要真實換行才能被 `cryptography` 函式庫解析。

---

### 4.2 `auth/jwt_handler.py` — JWT 身份驗證

使用 `python-jose` 函式庫實作 JWT (JSON Web Token)。

**`create_access_token()`：** 將 `{"sub": username, "exp": 到期時間}` 用 HMAC-SHA256 簽章，回傳 token 字串。

**`make_auth_dependency()`：** 工廠函式，回傳 FastAPI 的 Depends 依賴物件。每個需要登入的端點宣告 `user: dict = Depends(get_current_user)` 即可自動驗證 `Authorization: Bearer <token>` 標頭，驗證失敗時自動回傳 401。

**Token 儲存方式：** 前端將 token 存在 `sessionStorage`（非 localStorage），頁籤關閉時自動清除，安全性較高。

---

### 4.3 `crypto/signer.py` — RSA 數位簽章

使用 RSA-PSS SHA-256 演算法，防止搜尋結果在傳輸中被竄改。

**`build_signed_data()`：** 將餐廳列表、NLP 解析結果、時間戳記組成 canonical JSON 字串（`sort_keys=True`，確保欄位順序一致）。刻意排除 `map_html` 和 `signature` 本身，只簽有意義的搜尋結果資料。

**`sign(data, private_key_pem)`：**
1. 載入 RSA 私鑰
2. 用 PSS padding (MGF1 + SHA-256, salt_length=32) 對資料簽章
3. 回傳 base64 編碼的簽章字串

**`verify(data, signature_b64, public_key_pem)`：**
1. 載入 RSA 公鑰
2. 嘗試驗章，成功回傳 `True`，任何例外回傳 `False`

**重要細節：** `salt_length=32` 在 Python 和 JavaScript (Web Crypto API `{saltLength: 32}`) 兩端必須完全一致，否則驗章會失敗。

---

### 4.4 `main.py` — FastAPI 應用程式

#### 應用程式初始化

使用 `lifespan` context manager 管理應用程式生命週期：
- **啟動時：** 建立共享的 `httpx.AsyncClient`（持久連線，所有外部 HTTP 呼叫共用）並檢查 NLP 模型是否存在
- **關閉時：** 正確關閉 HTTP client，釋放連線

`create_app()` 工廠函式建立 FastAPI 實例，設定 CORS middleware，並在函式內定義所有端點（使用 closure 存取 `settings`）。

#### 所有 API 端點

| 方法 | 路徑 | 認證 | 說明 |
|------|------|------|------|
| GET | `/health` | 無 | 伺服器存活確認，回傳 NLP 模型狀態 |
| GET | `/public-key` | 無 | 回傳 RSA 公鑰 PEM (前端驗章用) |
| POST | `/register` | 無 | 建立新帳號 (帳號 2–20 字元，密碼至少 6 碼) |
| POST | `/login` | 無 | 登入，回傳 JWT token |
| GET | `/basemap` | JWT | 回傳無標記的基本 Folium 地圖 |
| POST | `/search` | JWT | 主搜尋端點：NLP→Nominatim→OSRM→Folium→RSA簽章 |
| POST | `/recognize` | JWT | 食物圖片辨識，回傳食物名稱和搜尋 query |
| GET | `/spin` | JWT | 隨機選擇今天吃什麼 (依台灣時間加權) |
| GET | `/favourites` | JWT | 取得我的收藏列表 |
| POST | `/favourites` | JWT | 新增收藏 |
| DELETE | `/favourites/{id}` | JWT | 移除收藏 |
| GET | `/favourites/map` | JWT | 顯示收藏餐廳地圖 |
| GET | `/admin/users` | JWT (管理員) | 列出所有使用者 |
| POST | `/admin/users/{u}/reset-password` | JWT (管理員) | 重設密碼 |
| GET | `/admin/users/{u}/wallet` | JWT (管理員) | 查看任意使用者餘額 |
| POST | `/admin/users/{u}/wallet` | JWT (管理員) | 調整使用者餘額 |
| GET | `/wallet` | JWT | 查看自己的餘額 |
| GET | `/wallet/transactions` | JWT | 查看自己的消費紀錄 |
| POST | `/groups` | JWT | 建立群組 |
| GET | `/groups` | JWT | 列出我的群組 |
| GET | `/groups/{gid}` | JWT | 取得群組詳情 |
| DELETE | `/groups/{gid}` | JWT | 刪除群組 (建立者或管理員) |
| POST | `/groups/{gid}/invite` | JWT | 邀請使用者加入群組 |
| GET | `/invitations` | JWT | 取得我的待接受邀請 |
| POST | `/invitations/{iid}/accept` | JWT | 接受邀請 |
| POST | `/invitations/{iid}/decline` | JWT | 拒絕邀請 |
| GET | `/groups/{gid}/messages` | JWT | 取得群組聊天記錄 |
| POST | `/groups/{gid}/messages` | JWT | 發送群組訊息 |
| POST | `/groups/{gid}/transfer` | JWT | 群組內轉帳 |
| GET | `/groups/{gid}/votes` | JWT | 取得投票列表 |
| POST | `/groups/{gid}/votes` | JWT | 建立投票 |
| POST | `/groups/{gid}/votes/{vid}/cast` | JWT | 投票 (可切換/取消) |
| POST | `/groups/{gid}/votes/{vid}/close` | JWT | 結束投票 |
| GET | `/groups/{gid}/votes/{vid}/map` | JWT | 顯示投票選項地圖 |

#### `/search` 端點詳細流程

這是系統最複雜的端點，完整流程如下：

```
POST /search { query, latitude, longitude, use_google }
    │
    ├── 1. NLP: predict(query)
    │        → { intent, food, time, meal, keywords, raw_keyword }
    │
    ├── 2. Nominatim: search_restaurants(lat, lon, food, keywords, time, raw_keyword)
    │        → 最多幾十筆 OSM 地點原始資料
    │
    ├── 3. (選用) Google Places: search_places(raw_keyword, lat, lon, radius_m)
    │        → 當 use_google=True 且有 API Key 時
    │        → _merge_places() 去重後合併 (50m 距離內視為同一地點)
    │
    ├── 4. OSRM: get_walking_times(origin, destinations)
    │        → 批次查詢所有候選地點的步行時間 (秒→分鐘)
    │
    ├── 5. 過濾: 只保留 walking_minutes <= parsed.time 的結果
    │
    ├── 6. 收藏加權: 已收藏的餐廳排在前面
    │
    ├── 7. Google Places reviews: asyncio.gather() 並發取得所有餐廳評分和評論
    │
    ├── 8. OSRM: get_walking_route() 並發取得所有餐廳的步行路線 GeoJSON
    │
    ├── 9. 產生推薦原因: _generate_reasons() 規則式中文說明
    │
    ├── 10. Folium: build_map() 產生含標記和路線的地圖 HTML iframe
    │
    ├── 11. RSA 簽章: sign(build_signed_data(restaurants, parsed, timestamp))
    │         → 後端也立刻驗章確認無誤
    │
    └── 回傳 SearchResponse (restaurants, parsed_query, reasons, map_html, signature, signed_data)
```

#### 管理員特殊處理

管理員帳號 (`DEMO_USERNAME`) 不存在於 `users.json`，只存在於環境變數。`_is_admin()` 和 `_assert_member()` 讓管理員可以：
- 訪問所有群組（`list_all_groups()`）
- 繞過群組成員檢查
- 關閉任何人建立的投票
- 每個新建立的群組都會自動加入管理員作為成員

---

## 5. NLP 自然語言處理系統

本系統的 NLP 管線負責把使用者輸入的一句中文（例如：「我想吃火鍋，15分鐘內」）轉換成搜尋指令（「去哪裡找、找什麼食物、走多久以內」）。整體流程分為**訓練階段**（只跑一次，在 Docker build 時執行）和**推理階段**（每次搜尋時即時執行）。

---

### 5.1 核心演算法：MiniLM 語意嵌入（Sentence Embedding）

#### 什麼是嵌入（Embedding）？

嵌入的概念是：**把一段文字轉換成一個數字向量，使語意相近的句子在向量空間中距離也近。**

想像把所有句子投影到一個 384 維的空間（就像 3D 空間，只是維度更多）：
- 「我想吃拉麵」和「給我一碗日式麵條」→ 在空間中位置很接近
- 「我想吃拉麵」和「推薦一家甜點店」→ 在空間中距離很遠
- 「今天好熱想喝冰的」和「珍珠奶茶在哪」→ 位置接近（語意相關）

這讓分類器不需要看到完全一樣的詞才能理解，可以「舉一反三」。

#### 本專案使用的模型：`paraphrase-multilingual-MiniLM-L12-v2`

這個模型由 HuggingFace `sentence-transformers` 函式庫提供，特性如下：

| 特性 | 說明 |
|------|------|
| 輸入 | 任意長度中文（或其他語言）文字 |
| 輸出 | 384 維浮點數向量 |
| 多語言 | 支援 50+ 語言，中文效果尤佳 |
| 模型架構 | Transformer（BERT 衍生），12 層 attention |
| 大小 | ~471 MB（推理時不需 GPU） |
| 訓練方式 | 在大量平行語料上用對比學習（contrastive learning）訓練：相同語意的句子對距離縮小，不同語意的句子對距離拉大 |

**L2 正規化（normalize_embeddings=True）：** 將每個向量的長度縮放為 1（讓它落在單位超球面上）。正規化後，**餘弦相似度 = 向量點積**，計算更快，且只比較「方向」不比較「長度」，讓不同長度句子的向量可公平比較。

```python
# 具體例子：把 3 句話分別向量化
sentences = [
    "我想吃拉麵",              # → [0.12, -0.34, ..., 0.87]  384個數字
    "想吃日式料理",             # → [0.11, -0.32, ..., 0.85]  → 很接近
    "今天天氣好",               # → [-0.45, 0.21, ..., -0.12] → 很遠
]
embeddings = model.encode(sentences, normalize_embeddings=True)
# embeddings.shape = (3, 384)
```

---

### 5.2 核心演算法：Logistic Regression 分類器

#### 什麼是 Logistic Regression？

Logistic Regression（邏輯回歸）是一個**把向量映射到各類別機率**的分類器。

最簡單的理解：給定一個 384 維向量 **x**，分類器學習 19 組「加權方向」（每個意圖類別各一組），計算輸入向量和每個方向的相似程度，再用 Softmax 把相似程度轉換成總和為 1 的機率。

**數學公式（多類別，softmax）：**

```
對每個意圖類別 k（k = 0, 1, ..., 18）：

    score(k) = W_k · x + b_k
    
    P(類別 = k | x) = exp(score(k)) / Σ exp(score(j))
                                         j=0..18

其中 W_k 是第 k 類的權重向量（384 個數字），b_k 是偏移量。
```

白話說：每個意圖類別都有一個「代表方向」（W_k）。如果輸入向量 x 和某個方向的點積（score）很高，代表這句話很可能屬於那個類別。Softmax 確保所有類別機率加起來等於 1。

**為什麼選 Logistic Regression，不選 Neural Network？**

| 方案 | 參數量 | 訓練資料需求 | 優點 |
|------|--------|-------------|------|
| Logistic Regression | 384 × 19 = 7,296 | 50–200 筆即可 | 少量資料就很準確，不過擬合，可解釋 |
| 2層神經網路 | ~100,000 | 需要數千筆 | 表達力強，但訓練資料不足時容易過擬合 |
| SVM (RBF) | — | 少量可行 | 可行，但 MiniLM 已提供好的線性空間，不需要非線性核函數 |

本專案只有 ~150 筆手工標注資料，Logistic Regression 在 MiniLM 向量空間中表現很好（5-fold CV 準確率通常超過 90%）。

#### 正規化參數 C = 5.0

C 值控制「有多嚴格要求每筆訓練資料都要被正確分類」：
- **C 很小（如 0.01）**：允許很多錯誤，決策邊界非常平滑，容易欠擬合
- **C 很大（如 100）**：幾乎要求所有訓練資料正確分類，邊界很彎曲，容易過擬合
- **C = 5.0**：中等嚴格度，適合我們小資料集的情況

---

### 5.3 `nlp/train.py` — 訓練腳本

**完整訓練流程說明：**

```python
# ── Step 1: 載入訓練資料 ──────────────────────────────────────────
texts, intents, slots = load_data("data/train_data.json")
# 約 150 筆手工標注的中文查詢
# 每筆格式：{"text": "我想吃火鍋", "intent": "find_hotpot", "slots": {"time": 15}}

# ── Step 2: 資料增強（Data Augmentation）──────────────────────────
# 問題：150 筆資料太少，容易過擬合
# 解法：對每筆資料套用同義詞替換，人工擴充訓練集
# 例如：「10分鐘內」→「10分鐘以內」、「走路」→「步行」、「想吃」→「要吃」
# 增強後訓練集約 400–500 筆
texts, intents, slots = augment_data(texts, intents, slots)

# ── Step 3: 標籤編碼 ──────────────────────────────────────────────
# 機器學習模型只能處理數字，需要把字串標籤轉成整數
# LabelEncoder: "find_hotpot" → 7, "find_japanese" → 5, ...
le = LabelEncoder()
y = le.fit_transform(intents)   # 字串 → 整數陣列

# ── Step 4: MiniLM 向量化（最耗時的步驟，約 30–60 秒）────────────
encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
embeddings = encoder.encode(texts, normalize_embeddings=True)
# embeddings.shape = (500, 384)
# 每一行是一句話的 384 維向量

# ── Step 5: 5-fold StratifiedKFold 交叉驗證 ──────────────────────
# 目的：估計模型在新資料上的真實準確率（而不只是訓練資料）
# 做法：把資料分成 5 份，輪流用 4 份訓練、1 份測試，重複 5 次取平均
# Stratified = 每份資料裡各類別的比例和原始資料集相同（防止某次測試集偶然缺少某類別）
clf = LogisticRegression(C=5.0, max_iter=1000, solver="lbfgs", multi_class="multinomial")
scores = cross_val_score(clf, embeddings, y, cv=StratifiedKFold(n_splits=5))
# scores = [0.92, 0.88, 0.94, 0.91, 0.93] → 平均 0.916

# ── Step 6: 用全部資料訓練最終模型 ──────────────────────────────
clf.fit(embeddings, y)
# 現在 clf 學到了 19 × 384 個權重（W 矩陣）
# 每個意圖類別都有一個「代表方向」在 384 維空間中

# ── Step 7: 儲存 4 個 .pkl 檔案 ──────────────────────────────────
# intent_clf.pkl    → 訓練好的 LogReg 模型（W 矩陣）
# label_encoder.pkl → 整數 ↔ 字串標籤的對應表
# slot_patterns.pkl → 用 regex 提取時間/餐別的 patterns
# food_type_map.pkl → intent → Nominatim 英文搜尋詞的對應表
```

**意圖類別（19 類）：**

| 類別 | 對應食物 | Nominatim 搜尋詞 |
|------|---------|----------------|
| `find_hotpot` | 火鍋、麻辣鍋 | hotpot restaurant |
| `find_japanese` | 壽司、拉麵、日料 | japanese restaurant |
| `find_taiwanese` | 滷肉飯、鹹酥雞 | taiwanese restaurant |
| `find_cafe` | 咖啡、下午茶 | cafe |
| `find_dessert` | 甜點、蛋糕、冰 | dessert shop |
| `find_drinks` | 奶茶、珍珠、飲料 | bubble tea shop |
| `find_korean` | 韓式、烤肉 | korean restaurant |
| `find_western` | 牛排、漢堡、披薩 | western restaurant |
| `find_healthy` | 健康、沙拉、輕食 | healthy food |
| `find_noodles` | 麵、麵條、米粉 | noodle shop |
| `find_fast_food` | 麥當勞、速食 | fast food |
| `find_chinese` | 中式、合菜、小吃 | chinese restaurant |
| `find_breakfast` | 早餐、早午餐 | breakfast restaurant |
| `find_vegetarian` | 素食、蔬食 | vegetarian restaurant |
| `find_southeast_asian` | 泰式、越式、咖哩 | southeast asian restaurant |
| `find_pasta` | 義大利麵 | italian restaurant |
| `find_steak` | 牛排館 | steak restaurant |
| `find_rice` | 飯類、便當 | rice restaurant |
| `find_general` | 其他/不明 | restaurant |

---

### 5.4 `nlp/predictor.py` — 推理引擎

每次使用者搜尋時，`predict(text)` 函式執行以下步驟：

#### Step 0：`@lru_cache` 模型快取

```python
@lru_cache(maxsize=1)
def _load_models():
    clf     = joblib.load("backend/nlp/models/intent_clf.pkl")
    encoder = SentenceTransformer("backend/nlp/local_model/")
    le      = joblib.load("backend/nlp/models/label_encoder.pkl")
    ...
    return clf, encoder, le, patterns, food_map
```

`@lru_cache(maxsize=1)` 的作用：**模型只在第一次呼叫時載入**（約耗時 2–3 秒），之後每次呼叫直接使用記憶體中的物件，無需重複讀取磁碟。若沒有這個快取，每次搜尋都要重新載入 471MB 的模型，每次搜尋會慢數秒。

#### Step 1：規則式快速過濾（在 ML 前執行）

```python
# 這些情況不需要 ML，直接用 regex 判斷更快更準確
_OOD_PATTERNS       = re.compile(r'(怎麼做|怎麼煮|食譜|做法|在家煮|自己做)')
_NAVIGATION_PATTERNS = re.compile(r'(診所|醫院|加油站|便利商店|藥局)')
_COMPLAINT_PATTERNS  = re.compile(r'(到底有什麼用|爛App|退費|客訴)')

if _OOD_PATTERNS.search(text):
    return {"intent": "out_of_domain", ...}  # 不是找餐廳
if _NAVIGATION_PATTERNS.search(text):
    return {"intent": "find_navigation", ...}  # 找的不是餐廳
```

**為什麼這樣做？** ML 模型在訓練資料範圍外（Out of Distribution）的輸入上會給出隨機答案。例如「火鍋怎麼煮」可能被分類為 `find_hotpot`，但用戶想要的是食譜，不是找餐廳。規則式過濾比 ML 更可靠且更快（微秒 vs 毫秒）。

#### Step 2：jieba 詞性標注提取食物關鍵字

jieba 是最流行的中文分詞函式庫，支援詞性標注（Part-of-Speech Tagging）。

**什麼是詞性標注？** 把句子的每個詞標上它的語法角色（名詞、動詞、副詞…）。

```
輸入：「我想吃壽司慶祝生日」
jieba POS 結果：
    我   (r)   → 代詞 (pronoun)
    想吃 (v)   → 動詞 (verb)
    壽司 (n)   → 名詞 (noun) ← 這是食物！
    慶祝 (v)   → 動詞 (verb) ← 遇到動詞停止收集
    生日 (n)   → 名詞 (noun)
```

**`_extract_food_keyword(text)` 的邏輯：**

```python
actions = ["想吃", "要吃", "想喝", "要喝", "去吃", "吃個", "來份", ...]

# 對全文做 POS tagging
segs = list(jieba.posseg.cut(text))
# segs = [("我","r"), ("想吃","v"), ("壽司","n"), ("慶祝","v"), ("生日","n")]

# 找到動作詞 ("想吃") 的位置，然後收集後面的名詞
for action in sorted(actions, key=len, reverse=True):  # 長詞優先，避免「吃」比「想吃」先匹配
    if action not in text:
        continue
    after_pos = ...  # 找到 action 在 segs 中的位置 + 1
    parts = []
    for seg, flag in segs[after_pos:]:
        if flag.startswith('v') or flag.startswith('a'):
            break  # 遇到動詞/形容詞 → 食物名稱收集結束
        if flag.startswith('n') or flag in ('eng', 'nz'):
            parts.append(seg)  # 名詞 → 加入食物名稱
    if parts:
        return "".join(parts)  # 例如 "壽司"、"雞腿飯"、"義大利麵"
```

**更多範例：**

| 輸入 | jieba POS 分析 | 提取結果 |
|------|---------------|---------|
| `吃個雞腿飯好了` | 吃個(v) 雞(n) 腿(n) 飯(n) 好(a) | `雞腿飯` |
| `我要喝珍珠奶茶` | 我(r) 要喝(v) 珍珠(n) 奶茶(n) | `珍珠奶茶` |
| `想吃點熱的暖胃` | 想吃(v) 點(m) 熱(a) | `None`（無名詞） |
| `想吃麥當勞的薯條` | 想吃(v) 麥當勞(nz) 的(u) 薯條(n) | `麥當勞薯條` |

#### Step 3：MiniLM 向量化 + LogReg 分類

```python
# 把輸入文字轉成 384 維向量
emb = encoder.encode([text], normalize_embeddings=True)  # shape: (1, 384)

# LogReg 計算每個意圖類別的機率
proba = clf.predict_proba(emb)[0]  # shape: (19,), 加起來 = 1.0
# 例如：[0.02, 0.01, 0.93, 0.01, ...]
#        find_cafe  find_steak  find_hotpot  ...

top_idx  = proba.argmax()          # 機率最高的類別索引
top_prob = proba[top_idx]          # 最高機率值（即信心度）

if top_prob >= 0.35:
    # 信心度足夠 → 使用分類結果
    intent = label_encoder.inverse_transform([top_idx])[0]
    # 整數 7 → "find_hotpot"
else:
    # 信心度不足 → 回退到通用搜尋（避免亂猜）
    intent = "find_general"
```

**信心度閾值 0.35 的意義：** 如果最高機率低於 35%，代表模型不確定（可能因為輸入太模糊或太奇怪），此時強行選最高機率類別容易出錯，不如用 `find_general` 做廣泛搜尋。

#### Step 4：多重 Fallback 機制

只用 ML 分類有時不夠準，系統加了多層備援：

```
輸入文字 → ML 分類
    ↓
    如果信心度 < 0.35 且有 raw_keyword（如「拉麵」）
        → 只對 raw_keyword 重新做 ML 分類
        （短詞通常比長句更容易分類準確）
    ↓
    如果還是 find_general
        → 用 substring 匹配 CUISINE_TEXT_QUERIES 字典
        （例如 raw_keyword 包含「咖哩」→ find_southeast_asian）
    ↓
    關鍵字-意圖一致性修正
        （例如 ML 說 find_rice 但 raw_keyword = "咖哩" → 修正為 find_southeast_asian）
    ↓
    排除句式處理
        （「除了火鍋之外」→ 先移除「火鍋」，用剩餘文字重新分類）
```

#### Step 5：時間提取 `_extract_time()`

用 regex 從文字中提取步行時間上限（預設 15 分鐘）：

```python
# 支援多種中文時間表達
patterns = [
    r'(\d+)\s*分鐘',          # "10分鐘" → 10
    r'(\d+)\s*分',             # "10分" → 10
    r'半\s*小時',              # "半小時" → 30
    r'(\d+)\s*小時',           # "2小時" → 120
    r'([一二三四五六七八九十]+)\s*分鐘',  # "十五分鐘" → 15（中文數字）
]

# 中文數字對應表
CN_NUM = {"一":1, "二":2, "三":3, "四":4, "五":5,
          "六":6, "七":7, "八":8, "九":9, "十":10,
          "十一":11, "十二":12, "十五":15, "二十":20, "三十":30}
```

| 輸入 | 提取結果 |
|------|---------|
| `10分鐘內` | 10 |
| `半小時步行` | 30 |
| `兩小時內` | 120 |
| `十五分鐘` | 15 |
| `（無時間詞）` | 15（預設） |

---

## 6. 電腦視覺 / 食物辨識系統

本系統讓使用者可以拍一張食物照片（或截圖），系統自動辨識出是什麼食物，然後搜尋附近賣這種食物的餐廳。整體架構是**兩個模型串接**：YOLOv8n 做初步偵測，ViT-B 做精確分類。

---

### 6.1 核心演算法：YOLOv8n 物件偵測（第一關）

#### 什麼是 YOLO？

YOLO（You Only Look Once）是一種實時物件偵測演算法。它的特點是**一次看整張圖就能同時偵測所有物件的位置和類別**，比早期的「先提取候選框再分類」方法快很多。

#### YOLOv8n 的工作原理（簡化版）

```
輸入圖片 (任意尺寸)
    ↓
縮放為 640×640
    ↓
特徵提取 (CSPDarknet backbone)
    將圖片理解為多尺度特徵圖
    ↓
偵測頭 (Detection Head)
    把圖片切成格子（例如 20×20、40×40、80×80 三種尺度）
    每個格子預測：
        - 這個格子裡有沒有物件？（信心度 0~1）
        - 物件的邊界框在哪？（x, y, w, h）
        - 這個物件屬於哪個類別？（COCO 80 類）
    ↓
NMS（非極大值抑制）
    移除重疊的冗餘框，只保留每個物件最好的那個框
    ↓
輸出: [(類別="pizza", 信心度=0.93, 位置=[120,80,300,250]), ...]
```

**本系統使用的版本：YOLOv8n（nano）**

| 模型 | 參數量 | 大小 | 速度 |
|------|--------|------|------|
| YOLOv8n (nano) | 3.2M | ~6 MB | 極快 |
| YOLOv8s (small) | 11.2M | ~22 MB | 快 |
| YOLOv8x (xlarge) | 68.2M | ~131 MB | 慢 |

選 nano 版本的原因：本系統的 YOLO 只是**「軟性關卡」**——只需要粗略確認圖片中有沒有食物相關物件，不需要高精度偵測。

**COCO 中與食物相關的 10 個類別：**

```python
YOLO_FOOD_CLASSES = {
    "apple", "banana", "orange",    # 水果
    "broccoli", "carrot",           # 蔬菜
    "hot dog", "pizza", "donut",    # 速食/烘焙
    "cake", "sandwich"              # 糕點/三明治
}
```

注意：YOLO 偵測不到拉麵、壽司、珍珠奶茶等亞洲食物（COCO 資料集沒有），這也是為什麼 YOLO 在本系統中是「軟性關卡」——沒偵測到也不直接拒絕，讓 ViT 繼續判斷。

---

### 6.2 核心演算法：Vision Transformer (ViT-B) 圖像分類（第二關）

#### 什麼是 Transformer？

Transformer 原本是 NLP 領域的模型架構（就是 GPT、BERT 使用的那個）。它的核心是**自注意力機制（Self-Attention）**：讓模型學習「這個位置的資訊和哪些位置最相關」。

ViT（Vision Transformer）把同樣的機制應用到圖像上。

#### ViT 如何處理圖片？

```
輸入圖片 (224×224 像素, 3 通道 RGB)
    ↓
切成 16×16 的小方塊（Patch）
    224/16 = 14 → 共 14×14 = 196 個 patch
    每個 patch 大小 = 16×16×3 = 768 個數字
    ↓
Patch Embedding（Linear 投影）
    把每個 patch 的 768 個數字 → 仍是 768 維向量
    （相當於把圖片片段轉成「詞向量」，和 NLP 的詞嵌入概念一樣）
    加上可學習的位置編碼（讓模型知道每個 patch 在哪個位置）
    ↓
加入 [CLS] token
    在 196 個 patch 向量前面加一個特殊的「分類 token」
    共 197 個向量（197 × 768 維矩陣）
    ↓
12 層 Transformer Encoder（ViT-B = Base，每層 768 維）
    每層做：
      1. Multi-Head Self-Attention（每個 patch「看」其他所有 patch）
      2. Feed-Forward Network（兩層 MLP）
      3. Layer Normalization
    
    效果：196 個 patch 互相「交換資訊」，理解全局上下文
    例如：「這個 patch 是棕色麵條，旁邊有紅色醬汁和蔥花，整體判斷是牛肉麵」
    ↓
取出 [CLS] token 的最終向量（768 維）
    這個向量濃縮了整張圖的語意資訊
    ↓
分類頭（Classifier Head）
    Linear(768 → N_classes)
    原始：Linear(768 → 101)  ← Food-101 的 101 類
    本系統：Linear(768 → 110) ← 101 + 9 台灣類別
    ↓
Softmax → 110 個機率值
```

#### ViT-B 的數字細節

| 元件 | 規格 |
|------|------|
| 輸入解析度 | 224 × 224 |
| Patch 大小 | 16 × 16 |
| Patch 數量 | 196 |
| 隱藏層維度 | 768 |
| Transformer 層數 | 12 |
| Attention Heads | 12 |
| 總參數量 | ~86M |
| 輸出（[CLS] vector） | 768 維 |

---

### 6.3 核心技術：遷移學習與 Last-Layer Fine-Tuning

#### 什麼是遷移學習（Transfer Learning）？

從頭訓練一個 86M 參數的 ViT-B 需要 **數百萬張圖片** 和 **數天 GPU 時間**。遷移學習的想法是：**借用別人已經訓練好的模型，只在上面稍作調整。**

就像一個廚師學過法式料理，要轉去學台灣料理時，不需要從頭學「怎麼切菜、怎麼控制火候」，只需要學新的配方和口味。

本系統使用 `nateraw/food`，這個模型已在 **Food-101**（101類西方食物，75,750張圖）上訓練完畢，能夠很好地辨識各種食物的視覺特徵（顏色、紋理、形狀）。

#### 什麼是 Last-Layer Fine-Tuning？

```
nateraw/food ViT-B 的結構：

    [Patch Embedding]
         ↓
    [Transformer Layer 1]  ← 學會辨識邊緣、顏色
    [Transformer Layer 2]  ← 學會辨識紋理
    ...
    [Transformer Layer 12] ← 學會辨識食物的高階特徵
         ↓
    [CLS] vector (768維)
         ↓
    [Linear: 768 → 101]   ← 原本是 101 類分類頭
         ↓
    [Softmax] → 101類機率
```

**我們做的修改：只換掉最後一層：**

```python
# 凍結全部 86M 參數（backbone 不更新）
for param in model.parameters():
    param.requires_grad = False

# 換上新的分類頭：768 → 110 類
model.classifier = nn.Linear(768, 110)
# 新的 Linear 層有 768×110 + 110 = 85,030 個可訓練參數（只有 0.1%！）
```

**為什麼這樣做有效？**
- 前 12 層 Transformer 已學會「食物長什麼樣」，這個知識對所有食物都適用（包括台灣食物）
- 只需要新的分類頭學習「這些特徵對應到哪 110 個類別」
- 訓練資料只需要約 200 張/類（而非 10,000 張/類），訓練時間從數天縮短到 15 分鐘

| 方案 | 訓練資料 | GPU 時間 | 準確率 |
|------|---------|---------|-------|
| 從頭訓練 ViT-B | 每類 10,000+ 張 | 數天 | 高 |
| Full fine-tuning | 每類 500+ 張 | 數小時 | 高 |
| **Last-layer only（本方案）** | **每類 160–600 張** | **~15 分鐘** | **足夠** |

---

### 6.4 `cv/scrape_data.py` — 資料蒐集（離線執行）

使用 `icrawler` 函式庫從 Google Images 爬取台灣特有食物的圖片：

```python
TAIWANESE_CLASSES = {
    "bubble_tea":          "台灣珍珠奶茶",
    "beef_noodle_soup":    "台灣牛肉麵",
    "braised_pork_rice":   "台灣滷肉飯",
    "soup_dumplings":      "小籠包",
    "fried_chicken_steak": "台灣雞排",
    "stinky_tofu":         "台灣臭豆腐",
    "gua_bao":             "台灣刈包",
    "scallion_pancake":    "台灣蔥油餅",
    "oyster_omelette":     "台灣蚵仔煎",
}
# 每類爬取約 250 張圖片，實際可用約 200 張（去除損毀圖）
```

**為什麼需要爬取？** 原始 Food-101 資料集只有西方食物，不包含台灣本地食物，需要自行蒐集訓練資料。

---

### 6.5 `cv/prepare_dataset.py` — 資料集整備（離線執行）

將 Food-101（101 類，每類 750 張）和爬取的台灣食物（9 類，每類約 200 張）合併，以 80/20 比例分成 train/val 兩個資料夾：

```
data/food_dataset/
    train/
        apple_pie/          (600 張)     ← Food-101
        beef_noodle_soup/   (160 張)     ← 台灣爬取
        bubble_tea/         (160 張)     ← 台灣爬取
        ... (共 110 類)
    val/
        apple_pie/          (150 張)
        beef_noodle_soup/   (40 張)
        ...
```

**80/20 分割的原因：** 訓練集用來更新模型權重，驗證集用來評估模型在未見過資料上的表現（模擬真實使用情況）。若只看訓練集準確率，模型可能「背答案」而非真正學會辨識。

---

### 6.6 `cv/train.py` — ViT 模型微調（離線執行，需 GPU）

**完整訓練流程說明：**

```python
# ── Step 1: 載入預訓練模型 ────────────────────────────────────────
model = AutoModelForImageClassification.from_pretrained("nateraw/food")
# 從 HuggingFace Hub 下載 ~327MB 的模型

# ── Step 2: 凍結 Backbone（86M 參數 → 全部 requires_grad = False）─
for param in model.parameters():
    param.requires_grad = False
# 凍結後 backward pass 不計算這些參數的梯度 → VRAM 節省 ~70%

# ── Step 3: 替換分類頭 ──────────────────────────────────────────
num_features = model.classifier.in_features  # = 768
model.classifier = nn.Linear(num_features, 110)
# 新的 Linear 層預設 requires_grad = True（新建的層預設可訓練）
model.config.num_labels = 110

# ── Step 4: 資料增強與 DataLoader ───────────────────────────────
transform = transforms.Compose([
    transforms.Resize((224, 224)),       # 縮放到 ViT 要求的 224×224
    transforms.RandomHorizontalFlip(),   # 隨機水平翻轉（資料增強）
    transforms.ToTensor(),               # PIL Image → [0,1] 浮點張量
    transforms.Normalize(               # 正規化：減去均值，除以標準差
        mean=[0.485, 0.456, 0.406],     # ImageNet 統計值（預訓練模型使用這個）
        std=[0.229, 0.224, 0.225]
    ),
])
# 正規化的作用：讓輸入數值範圍和模型預訓練時一致，加速收斂

# ── Step 5: 訓練迴圈（15 個 epoch）──────────────────────────────
optimizer = torch.optim.Adam(
    model.classifier.parameters(),  # 只優化新的分類頭
    lr=1e-3
)
criterion = nn.CrossEntropyLoss()
# CrossEntropyLoss = Softmax + NegativeLogLikelihood
# 公式：Loss = -log(P(正確類別))
# 當模型對正確答案很有信心（機率接近1）→ Loss 接近 0
# 當模型不確定（機率接近 1/110 = 0.009）→ Loss 很大

for epoch in range(15):
    # ── 訓練階段 ──
    model.train()  # 開啟 Dropout（如果有）
    for imgs, labels in train_dl:
        # imgs: (32, 3, 224, 224)，labels: (32,)
        imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
        
        optimizer.zero_grad()            # 清除上一個 batch 的梯度
        logits = model(imgs).logits      # 前向傳播 → (32, 110)
        loss = criterion(logits, labels) # 計算損失
        loss.backward()                  # 反向傳播：計算梯度
        optimizer.step()                 # 用梯度更新分類頭的 85K 個參數
    
    # ── 驗證階段 ──
    model.eval()  # 關閉 Dropout
    correct = total = 0
    with torch.no_grad():  # 不計算梯度（節省記憶體）
        for imgs, labels in val_dl:
            preds = model(imgs).logits.argmax(dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
    val_acc = correct / total  # 例如 0.847 = 84.7%
    
    if val_acc > best_acc:
        best_acc = val_acc
        model.save_pretrained("backend/cv/models/food_vit/")  # 儲存最佳模型
```

**Adam 優化器工作原理（簡化）：**

一般梯度下降每次更新：`W = W - lr × gradient`

Adam 在此基礎上做兩個改進：
1. **動量（Momentum）**：記住過去梯度的方向，減少震盪，更快收斂
2. **自適應學習率**：每個參數根據歷史梯度大小自動調整學習步幅，梯度大的參數步幅小，梯度小的步幅大

這讓訓練比普通 SGD 快約 3–5 倍，特別適合參數量少的分類頭訓練。

**訓練資源需求：**

| 項目 | 需求 | 原因 |
|------|------|------|
| VRAM | ~2–3 GB | Backbone 凍結，不儲存中間激活梯度 |
| RAM | ~4 GB | DataLoader 預載資料，BATCH_SIZE=32 |
| 訓練時間（NVIDIA GPU）| ~10–20 分鐘 | 只更新 85K 參數，每個 batch 非常快 |
| 訓練時間（CPU）| ~3–4 小時 | 可行但較慢 |
| 模型大小 | ~327 MB | 與原始模型相同（只換了最後一層） |

---

### 6.7 `cv/food_recognizer.py` — 推理引擎

**兩階段辨識完整流程：**

```
使用者上傳圖片（最大 10MB，JPEG/PNG/WebP）
    │
    ├── PIL.Image.open(io.BytesIO(image_bytes)).convert("RGB")
    │       PIL 重新解碼防止惡意 payload（例如 pixel flood attack）
    │
    ├── Stage 1: YOLOv8n 食物存在偵測
    │       results = yolo(img, verbose=False)
    │       detected = {results[0].names[int(c)] for c in results[0].boxes.cls}
    │       # detected = {"pizza", "donut"} 或 {} (空集合)
    │       
    │       如果 detected ∩ YOLO_FOOD_CLASSES == {} (沒有偵測到食物)
    │           → 記錄 warning，但繼續執行 Stage 2（軟性關卡）
    │           → 因為 YOLO 不認識拉麵、珍珠奶茶、牛肉麵等台灣食物
    │
    └── Stage 2: ViT-B 110類精確分類
            inputs = extractor(images=img, return_tensors="pt")
            # extractor 做：Resize(224×224) → Normalize → 轉 tensor
            
            with torch.no_grad():
                logits = model(**inputs).logits  # shape: (1, 110)
            
            probs = torch.softmax(logits, dim=1)[0]  # 110 個機率值
            # probs = [0.02, 0.00, 0.88, 0.01, ...]
            #          bubble_tea  steak  beef_noodle  ...
            
            top1_idx  = int(probs.argmax())     # 最高機率類別的索引
            top1_conf = float(probs[top1_idx])  # 最高機率值（信心度）
            
            if top1_conf < 0.20:
                raise ValueError("圖片中未偵測到明確食物")
                # 低於 20% 信心度 → 圖片不像食物或太模糊
            
            class_name = idx_to_class[top1_idx]  # 例如 "beef_noodle_soup"
            zh = FOOD_LABEL_MAP.get(class_name)  # → "牛肉麵"
            
            如果 zh 是 None（FOOD_LABEL_MAP 沒有這個類別的中文翻譯）：
                → Top-5 fallback：試前 5 個最高機率的類別
                → 取第一個有中文映射的類別
            
            verb = "喝" if any(k in zh for k in 飲料關鍵詞) else "吃"
            return {"food_label": "牛肉麵", "confidence": 0.88, "query": "我想吃牛肉麵"}
```

**信心度閾值 0.20 的設計考量：**

| 閾值 | 效果 |
|------|------|
| 0.50 | 太嚴格，許多模糊照片被拒絕 |
| 0.20 | 平衡：拒絕明顯不是食物的圖，接受有些模糊的食物照 |
| 0.05 | 太寬鬆，隨機圖片也能通過 |

110 個類別的均勻分布機率是 1/110 ≈ 0.009。如果最高機率達到 0.20，代表模型認為這個類別的可能性是隨機猜測的 **22 倍**，足以做出合理判斷。

**`FOOD_LABEL_MAP` 部分範例（共 110 個映射）：**

```python
FOOD_LABEL_MAP = {
    # 台灣特有（9 類，自行爬取訓練）
    "bubble_tea":          "珍珠奶茶",
    "beef_noodle_soup":    "牛肉麵",
    "braised_pork_rice":   "滷肉飯",
    "soup_dumplings":      "小籠包",
    "fried_chicken_steak": "雞排",
    "stinky_tofu":         "臭豆腐",
    "gua_bao":             "刈包",
    "scallion_pancake":    "蔥油餅",
    "oyster_omelette":     "蚵仔煎",
    # Food-101（101 類）
    "ramen":               "拉麵",
    "sushi":               "壽司",
    "pizza":               "披薩",
    "hamburger":           "漢堡",
    "ice_cream":           "冰淇淋",
    "waffles":             "鬆餅",
    "steak":               "牛排",
    "dumplings":           "水餃",
    ...
}
```

**動詞智慧選擇：**
```python
_DRINK_KEYWORDS = ("茶", "奶茶", "飲料", "咖啡", "飲", "汁", "水")
verb = "喝" if any(k in zh for k in _DRINK_KEYWORDS) else "吃"
# "珍珠奶茶" → "我想喝珍珠奶茶"  (搜尋飲料店)
# "壽司"     → "我想吃壽司"      (搜尋壽司餐廳)
```

兩個模型都用 `@lru_cache(maxsize=1)` 確保只載入一次，不會每次請求都重新載入（YOLO ~6MB + ViT ~327MB）。

---

## 7. 後端服務層 Services

### 7.1 `services/nominatim.py` — OSM 地圖搜尋

呼叫 `https://nominatim.openstreetmap.org/search` 查詢候選餐廳。

**5 層搜尋策略（按優先順序）：**

```
Strategy 1: raw_keyword 文字查詢
   直接用使用者輸入的食物名（如「火鍋」、「義大利麵」）搜尋
   → 適合任何食物類型，不受限於預定義清單

Strategy 2: CUISINE_TEXT_QUERIES 中文文字查詢
   用預定義的中文詞組搜尋（如「日式料理」、「壽司」、「拉麵」）
   → 適合 OSM 有正確標注的地點

Strategy 3: amenity tag 查詢
   用 OSM amenity 標籤（"restaurant", "cafe", "fast_food"）
   → 更廣泛的搜尋，當文字查詢結果不足時使用

Strategy 4: 擴大半徑的通用 restaurant 搜尋
   → 最後的備援，確保不會完全找不到

Strategy 5: 無邊界文字查詢 (unbounded)
   → 極端情況備援
```

**搜尋半徑計算：**
```python
tight_r = max(max_minutes * 130, 900)   # 步行速度約 ~4km/h = 67m/min
wide_r  = tight_r * 2                   # 擴大搜尋用
```

**結果處理管線：**
```python
deduped   = _deduplicate(all_results)   # 依 (osm_type, osm_id) 去重
food_only = [p for p in deduped if _is_food_place(p)]  # 只保留餐飲類型
excluded  = _filter_by_intent(base, food)  # 排除不相關 (如搜火鍋不要顯示速食)
strict    = _strict_cuisine_filter(base, food)  # 名稱必須包含相關詞
scored    = _score_by_keywords(narrow_base, food)  # 依關鍵字命中數排序
```

**`parse_place()` 地點資料正規化：**
將 OSM 的原始 JSON 轉換為統一格式 `{osm_type, osm_id, name, lat, lon, address}`。地址從 OSM 的 `addressdetails` 中提取路名和城市，組合成易讀格式。

---

### 7.2 `services/osrm.py` — 步行時間計算

呼叫 `https://router.project-osrm.org` 的 Table service 和 Route service。

**重要：OSRM 使用 `longitude, latitude` 順序（與大多數慣例相反）。**

**`get_walking_times()`：** 批次查詢，一次呼叫取得 origin 到所有餐廳的步行時間：
```
URL: /table/v1/foot/{origin};{dest1};{dest2};...
     ?sources=0&annotations=duration
返回: durations[0][1:] = 從 origin 到每個目的地的秒數
```

**`get_walking_route()`：** 取得單一路線的 GeoJSON 座標，供 Folium 畫折線路線。OSRM 回傳 `[lon, lat]`，必須轉換為 Folium 需要的 `[lat, lon]`。

---

### 7.3 `services/map_generator.py` — Folium 地圖產生器

**`build_map()`** 使用 Python folium 函式庫在伺服器端產生完整的 Leaflet.js 地圖，回傳 HTML 字串。

```python
m = folium.Map(location=[user_lat, user_lon], zoom_start=16, tiles="OpenStreetMap")

# 使用者位置標記 (藍色 home 圖示)
folium.Marker(location=[user_lat, user_lon], icon=folium.Icon(color="blue", icon="home")).add_to(m)

# 每間餐廳的標記
for restaurant in restaurants:
    is_fav = restaurant.id in fav_ids
    color  = "orange" if is_fav else "red"   # 收藏的用橘色
    icon   = "heart"  if is_fav else "cutlery"
    folium.Marker(location=[restaurant.latitude, restaurant.longitude],
                  icon=folium.Icon(color=color, icon=icon, prefix="fa")).add_to(m)

# 步行路線折線
for restaurant, route_coords in routes.items():
    folium.PolyLine(locations=route_coords, color="#2196F3", weight=4).add_to(m)

# 自動調整視野包含所有標記
m.fit_bounds([[min_lat-0.003, min_lon-0.003], [max_lat+0.003, max_lon+0.003]])
```

**特殊技術：使用 `get_root().render()` 而非 `_repr_html_()`**

Folium 預設的 `_repr_html_()` 使用 `padding-bottom: 60%` 的 CSS trick，會導致地圖在動態 resize 時顯示為細條。改用 `get_root().render()` 產生完整 HTML，再自行包裝成 `<iframe srcdoc="...">` 並設定 `style="width:100%;height:100%;"`，地圖就能填滿容器。

---

### 7.4 `services/google_places.py` — Google Places 補充搜尋

呼叫 Google Places API (New) v1 的 `searchText` 端點，作為 Nominatim 的補充。

**API 呼叫：**
```
POST https://places.googleapis.com/v1/places:searchText
Headers: X-Goog-Api-Key, X-Goog-FieldMask
Body: {
    "textQuery": "義大利麵",
    "locationBias": {"circle": {"center": {...}, "radius": 1200}},
    "languageCode": "zh-TW",
    "maxResultCount": 10
}
```

回傳結果轉換為與 Nominatim 相同的格式 `{osm_type: "google", name, lat, lon, address, _rating, _reviews}`，讓 `main.py` 可以統一處理兩個來源的結果。

**`fetch_reviews()`：** 取得指定地點的評分和前3則評論。只在 `use_google=True` 模式下呼叫。

---

### 7.5–7.11 資料儲存服務（全部採用相同模式）

所有 JSON 儲存服務都遵循相同設計模式：

```python
_STORE_PATH = "data/xxx.json"
_lock = threading.Lock()  # 執行緒鎖，確保讀寫不會 race condition

def _load() -> dict: ...   # 讀取 JSON，失敗時回傳空物件
def _save(data) -> None: ...  # 寫入 JSON，自動建立目錄

def create_xxx(...) -> dict:
    with _lock:       # 取得鎖
        data = _load()
        new = {..., "id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat()}
        data[new["id"]] = new
        _save(data)
    return new
```

**為什麼用 `threading.Lock`？** uvicorn 預設用多執行緒 (threadpool) 處理 async 任務，多個請求可能同時讀寫同一個 JSON 檔案，Lock 防止資料損毀。

**各服務負責的資料：**

| 服務 | JSON 檔案 | 主要功能 |
|------|----------|---------|
| `user_store.py` | `users.json` | 帳號建立、密碼 bcrypt hash 驗證、列出所有用戶 |
| `favourites.py` | `favourites.json` | 每位使用者的收藏列表 (dict，username為key) |
| `group_store.py` | `groups.json` | 群組 CRUD，成員管理 |
| `invitation_store.py` | `invitations.json` | 邀請建立、接受、拒絕 |
| `message_store.py` | `group_messages.json` | 群組聊天訊息，取最新 100 則 |
| `vote_store.py` | `group_votes.json` | 投票建立、投票（可切換），關閉投票 |
| `wallet_store.py` | `wallets.json` + `transactions.json` | 餘額查詢、管理員調整、使用者間轉帳，餘額不能為負 |

**`wallet_store.transfer()`** 在同一個 Lock 內完成雙方餘額更新和交易記錄寫入，確保轉帳原子性（不會出現錢已扣但未入帳的情況）。

---

## 8. 資料模型 Pydantic Schemas

`models/schemas.py` 定義了所有 API 的請求和回應格式，Pydantic 自動驗證輸入資料型別。

**主要模型：**

```python
class SearchRequest(BaseModel):
    query: str          # 使用者輸入的中文查詢
    latitude: float     # 使用者緯度
    longitude: float    # 使用者經度
    use_google: bool = False  # 是否使用 Google Places

class ParsedQuery(BaseModel):
    intent: str         # 意圖類別 (find_japanese, find_hotpot...)
    food: str           # Nominatim 搜尋詞 (japanese restaurant...)
    time: int           # 最大步行分鐘數
    meal: Optional[str] # 餐別 (breakfast/lunch/dinner)
    keywords: list[str] # 輔助搜尋關鍵字
    raw_keyword: str    # 用戶直接輸入的食物詞 (拉麵, 火鍋...)

class Restaurant(BaseModel):
    id: str             # "node:12345678" 或 "google:ChIJxxx"
    name: str
    latitude: float
    longitude: float
    address: str
    walking_minutes: float
    rating: Optional[float]    # Google 評分
    review_count: Optional[int]
    reviews: list[str]  # 評論摘要

class SearchResponse(BaseModel):
    restaurants: list[Restaurant]
    parsed_query: ParsedQuery
    recommendation_reasons: dict[str, str]  # restaurant_id → 中文推薦原因
    favourite_ids: list[str]
    map_html: str       # <iframe srcdoc="...Folium地圖...">
    timestamp: str      # ISO 8601
    signature: str      # RSA-PSS 簽章 (base64)
    signed_data: str    # 被簽章的 canonical JSON
```

---

## 9. 前端 Frontend

### 9.1 `index.html` — 頁面結構

全頁面單一 HTML 檔案，採 SPA (Single Page Application) 設計，所有面板共存於頁面，用 CSS `display:none/flex` 切換顯示狀態。

**主要 HTML 元素結構：**
```
<body>
    #map-container          ← 全螢幕地圖 (Folium iframe 注入點)
    #toolbar                ← 頂部工具列 (標題、定位、管理員按鈕)
    
    #login-overlay          ← 登入/註冊 Modal (遮罩全頁)
    #admin-overlay          ← 管理員用戶管理 Modal
    
    #wallet-btn             ← 左側浮動按鈕 💰 (切換錢包面板)
    #groups-btn             ← 左側浮動按鈕 👪 (切換群組面板)
    #fav-sidebar            ← 左側滑出收藏面板 (含 #fav-tab 標籤)
    
    #camera-btn             ← 右側浮動按鈕 📷 (食物圖片辨識)
    #spin-btn               ← 右側浮動按鈕 🎲 (隨機選擇今天吃什麼)
    #chat-toggle            ← 右側浮動按鈕 💬 (切換搜尋聊天面板)
    
    #chat-panel             ← 右側滑出搜尋面板
    #wallet-panel           ← 左側滑出錢包面板
    #groups-panel           ← 左側滑出群組面板 (含 3 個 view)
    
    #spin-overlay           ← 骰子轉盤 Modal
    #share-overlay          ← 分享到群組發起投票 Modal
    #transfer-overlay       ← 轉帳 Modal
    #adjust-overlay         ← 管理員調整餘額 Modal
    
    <script> config.js / auth.js / api.js / signature.js / app.js
```

---

### 9.2 `css/style.css` — 樣式設計

**版面架構：**
```css
/* 地圖全螢幕，根據開啟的面板自動縮放 */
#map-container {
    position: fixed; inset: 0;
    transition: left 0.3s ease, right 0.3s ease;
}
body.chat-open   #map-container { right: 360px; }  /* 聊天面板開啟 */
body.groups-open #map-container { left: 360px; }   /* 群組面板開啟 */
body.fav-open    #map-container { left: 360px; }   /* 收藏面板開啟 */
body.wallet-open #map-container { left: 360px; }   /* 錢包面板開啟 */
```

**左側滑出面板通用設計：**
```css
#groups-panel, #wallet-panel {
    position: fixed;
    top: 48px; left: 0; bottom: 0;
    width: 360px;
    background: #fff;
    border-right: 1px solid #dde3ea;
    box-shadow: 4px 0 24px rgba(0,0,0,.12);
    animation: slideInLeft .22s ease;
    overflow: hidden;
}
@keyframes slideInLeft {
    from { transform: translateX(-100%); opacity: 0; }
    to   { transform: translateX(0);     opacity: 1; }
}
```

**左側浮動標籤按鈕（wallet/groups/fav-tab 共同樣式）：**
```css
#wallet-btn, #groups-btn {
    position: fixed;
    left: 0;
    border-left: none;
    border-radius: 0 10px 10px 0;
    box-shadow: 3px 0 10px rgba(0,0,0,.1);
}
```

**RWD 響應式設計：** 手機版本收藏面板改為 bottom-sheet（從底部滑出），群組面板寬度縮為 100vw。

---

### 9.3 `js/config.js` — 前端設定

```javascript
const CONFIG = {
    BACKEND_URL: "https://changraeyu-restaurant-finder-api.hf.space",
    DEFAULT_LAT: 24.8138,  // 新竹市
    DEFAULT_LON: 120.9675,
    RSA_PUBLIC_KEY_PEM: `-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----`,
};
```

RSA 公鑰直接硬編碼在前端，不是秘密，任何人都可以驗章。私鑰只存在後端環境變數。

---

### 9.4 `js/auth.js` — 登入模組

```javascript
const Auth = {
    TOKEN_KEY: "rf_access_token",

    async login(username, password) {
        // POST /login (application/x-www-form-urlencoded，OAuth2 標準格式)
        const form = new URLSearchParams();
        form.append("username", username);
        form.append("password", password);
        const res = await fetch(`${CONFIG.BACKEND_URL}/login`, { method: "POST", body: form });
        const data = await res.json();
        sessionStorage.setItem(this.TOKEN_KEY, data.access_token);
    },

    isLoggedIn() {
        const token = this.getToken();
        // 解碼 JWT payload (base64url decode) 並檢查 exp 欄位
        const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/")));
        return payload.exp * 1000 > Date.now();  // 前端 UX 用，後端仍是最終裁決
    }
}
```

**使用 `sessionStorage` 而非 `localStorage`：** token 會在關閉分頁時自動清除，避免長期暴露於 XSS 攻擊。

---

### 9.5 `js/api.js` — API 客戶端

集中管理所有後端 API 呼叫：

```javascript
const API = {
    async search(query, latitude, longitude, use_google = false) {
        const res = await fetch(`${CONFIG.BACKEND_URL}/search`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${Auth.getToken()}`,
            },
            body: JSON.stringify({ query, latitude, longitude, use_google }),
        });
        if (res.status === 401) { Auth.logout(); throw new Error("登入已過期"); }
        ...
    },

    async recognize(file) {
        // multipart/form-data 上傳圖片
        const fd = new FormData();
        fd.append("image", file);
        return fetch(`${CONFIG.BACKEND_URL}/recognize`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${Auth.getToken()}` },
            body: fd,
        });
    }
}
```

---

### 9.6 `js/signature.js` — 簽章驗證

使用瀏覽器內建的 Web Crypto API，不需要任何外部函式庫。

```javascript
const SignatureVerifier = {
    // 將 PEM 格式公鑰轉換為 ArrayBuffer
    _pemToBinary(pem) {
        const b64 = pem.replace(/-----.*-----/g, "").replace(/\s/g, "");
        return Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;
    },

    async verify(signedDataStr, signatureBase64) {
        // importKey 只在第一次呼叫時執行，之後快取於 this._publicKey
        if (!this._publicKey) {
            this._publicKey = await window.crypto.subtle.importKey(
                "spki", this._pemToBinary(CONFIG.RSA_PUBLIC_KEY_PEM),
                { name: "RSA-PSS", hash: "SHA-256" }, false, ["verify"]
            );
        }

        return window.crypto.subtle.verify(
            { name: "RSA-PSS", saltLength: 32 },  // 必須與 Python signer.py 一致
            this._publicKey,
            Uint8Array.from(atob(signatureBase64), c => c.charCodeAt(0)).buffer,
            new TextEncoder().encode(signedDataStr)
        );
    }
}
```

---

### 9.7 `js/app.js` — App 主物件

`App` 物件管理整個應用程式的狀態和邏輯：

**狀態變數：**
```javascript
const App = {
    _lat: null,         // 使用者當前緯度
    _lon: null,         // 使用者當前經度
    _useGoogle: false,  // 是否使用 Google Places 搜尋
    _favourites: [],    // 快取的收藏列表
    _chatOpen: false,   // 聊天面板狀態
    _favOpen: false,    // 收藏面板狀態
    _walletOpen: false, // 錢包面板狀態
    _spinResult: null,  // 骰子轉盤結果
}
```

**面板互斥邏輯：** 開啟任一面板都會關閉其他面板。

```javascript
_openWallet() {
    this._closeChat();       // 關閉聊天
    GroupsPanel.close();     // 關閉群組
    this._closeFavSidebar(); // 關閉收藏
    this._walletOpen = true;
    document.body.classList.add("wallet-open");  // 地圖向右移 360px
    document.getElementById("wallet-panel").style.display = "flex";
    GroupsPanel._openWalletView();  // 載入餘額和交易記錄
},
```

**定位流程：**
1. 嘗試 `navigator.geolocation.getCurrentPosition()`
2. 成功 → 使用真實 GPS 座標
3. 失敗/拒絕 → 使用預設新竹座標
4. 呼叫 `GET /basemap` 渲染基本地圖

**搜尋流程 (`_handleMessage()`)：**
```javascript
async _handleMessage(text) {
    // 顯示用戶訊息
    this._addMsg("user", text);
    // 顯示 "分析中..." 打字指示器
    const typingEl = this._addTypingIndicator();
    
    // 呼叫後端搜尋
    const data = await API.search(text, this._lat, this._lon, this._useGoogle);
    
    // RSA 簽章驗證 (前端安全檢查)
    const isValid = await SignatureVerifier.verify(data.signed_data, data.signature);
    this._showSignatureBadge(isValid, data.signature.slice(0, 8));
    
    if (!isValid) {
        this._addMsg("bot", "⚠️ 簽章驗證失敗！此結果可能已被竄改。");
        return;
    }
    
    // 注入 Folium 地圖
    this._injectMap(data.map_html);
    
    // 渲染餐廳卡片
    this._renderResults(data.restaurants, data.parsed_query, data);
}
```

**食物圖片辨識流程 (`_bindCamera()`)：**
```javascript
cameraInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";  // 重設，允許重複上傳相同檔案
    
    const data = await API.recognize(file);
    // data = { food_label: "珍珠奶茶", confidence: 0.88, query: "我想喝珍珠奶茶" }
    
    this._addMsg("bot", `識別到：${data.food_label} (${Math.round(data.confidence*100)}%)`);
    await this._handleMessage(data.query);  // 自動搜尋
});
```

**骰子轉盤 (`_startSpin()`)：**
1. 同時啟動 Python API 呼叫 (`API.spin()`) 和 CSS 動畫
2. 動畫在前端快速循環所有選項（80ms 間隔 → 漸慢）
3. Python 依台灣時間（UTC+8）加權選出結果（早上推早餐，晚上推火鍋燒烤）
4. API 回傳後，動畫「停在」選中的選項上
5. 最短動畫時間 2 秒，確保視覺效果

---

### 9.8 `js/app.js` — GroupsPanel 物件

管理群組系統的所有 UI 狀態：

**三個 View 之間的切換：**
```javascript
_showView(view) {
    // gp-list-view   ← 群組列表
    // gp-inv-view    ← 待接受邀請列表
    // gp-detail-view ← 群組詳情 (含 chat/votes/members 三個 tab)
    document.getElementById("gp-list-view").style.display   = view === "list"   ? "flex" : "none";
    document.getElementById("gp-inv-view").style.display    = view === "inv"    ? "flex" : "none";
    document.getElementById("gp-detail-view").style.display = view === "detail" ? "flex" : "none";
}
```

**群組聊天輪詢：**
```javascript
_startPolling() {
    // 每 5 秒自動刷新訊息
    this._pollTimer = setInterval(() => this._fetchMessages(), 5000);
},
_stopPolling() {
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null; }
}
```

**投票渲染 (`_renderVotes()`)：**
- 每個選項顯示票數和佔比進度條
- 使用者已投票的選項標記為 `active`
- `cast_vote` 實作「切換」邏輯：再次點擊同一選項可取消投票

**成員列表 (`_renderMembers()`)：**
顯示每個成員名稱，以及對非自己成員的 💸 轉帳按鈕，管理員 (demo) 額外顯示 ✏️ 調整餘額按鈕。

---

## 10. 完整資料流程

### 使用者搜尋「我想吃火鍋，15分鐘內」的完整旅程

```
1. [Browser] 使用者在聊天輸入框輸入「我想吃火鍋，15分鐘內」並按送出

2. [Browser → app.js] App._handleMessage("我想吃火鍋，15分鐘內") 被呼叫
   - 顯示 user bubble
   - 顯示 "分析中..." 打字指示器
   - 呼叫 API.search(text, lat, lon, useGoogle=false)

3. [Browser → Backend] POST /search
   Headers: Authorization: Bearer eyJhbGc...
   Body: { "query": "我想吃火鍋，15分鐘內", "latitude": 24.8138, "longitude": 120.9675 }

4. [Backend: JWT 驗證] make_auth_dependency() 解碼 Bearer token
   → 確認使用者身份，取得 user["sub"] = "alice"

5. [Backend: NLP] predict("我想吃火鍋，15分鐘內")
   → jieba 分詞，POS tagging: 火鍋(n), 15(m), 分鐘(t)
   → raw_keyword = "火鍋"
   → MiniLM 向量化 → LogReg 分類 → intent = "find_hotpot" (confidence 0.97)
   → time = 15 (regex 提取)
   → food = "hotpot restaurant"
   → keywords = ["hotpot"]

6. [Backend: Nominatim] search_restaurants(lat, lon, food="hotpot restaurant", time=15)
   → Strategy 1: GET nominatim.../search?q=火鍋&viewbox=...&bounded=1
   → Strategy 2: GET nominatim.../search?q=麻辣鍋&viewbox=...
   → Strategy 2: GET nominatim.../search?q=涮涮鍋&viewbox=...
   → 去重 + 過濾食品類 + 排名
   → 返回 ~8 個候選地點

7. [Backend: OSRM] get_walking_times(origin, [8個目的地])
   → GET router.project-osrm.org/table/v1/foot/120.9675,24.8138;...
   → 一次 API 呼叫取回所有步行時間
   → 過濾 <= 15 分鐘 → 剩 5 間

8. [Backend: Favourites] 檢查 alice 的收藏
   → 「麻辣王子火鍋」在收藏中 → 排到第一位

9. [Backend: asyncio.gather()] 並發取得 5 條步行路線 GeoJSON
   → 5 個 OSRM route API 呼叫同時執行

10. [Backend: Folium] build_map(user_coords, 5間餐廳, 5條路線)
    → 建立 Leaflet 地圖，加入使用者標記 (藍色)
    → 加入 5 個餐廳標記 (收藏的用橘色，其他紅色)
    → 加入 5 條藍色步行路線折線
    → m.get_root().render() → 完整 HTML
    → 包裝成 <iframe srcdoc="..."> 字串

11. [Backend: RSA 簽章] build_signed_data(restaurants, parsed_query, timestamp)
    → canonical JSON (sort_keys=True)
    → sign(data, RSA_PRIVATE_KEY_PEM) → base64 簽章
    → verify() 自我確認簽章有效

12. [Backend → Browser] 回傳 SearchResponse JSON (~100KB)
    {
        restaurants: [...5間餐廳...],
        parsed_query: {intent: "find_hotpot", food: "hotpot restaurant", time: 15, ...},
        recommendation_reasons: {"node:12345": "提供火鍋，距您步行約 8 分鐘..."},
        map_html: "<iframe srcdoc=\"...完整Leaflet地圖HTML...\"...>",
        signature: "BASE64==",
        signed_data: "{\"parsed_query\":...,\"restaurants\":[...],\"timestamp\":\"...\"}"
    }

13. [Browser: 簽章驗證] SignatureVerifier.verify(signed_data, signature)
    → Web Crypto API RSA-PSS 驗章
    → ✅ 驗證成功 → 顯示 "✅ 簽章驗證成功 (ABC123...)"
    → ❌ 驗證失敗 → 顯示警告，拒絕渲染地圖

14. [Browser: 地圖渲染] document.getElementById("map-container").innerHTML = data.map_html
    → Folium 產生的 Leaflet.js 在 iframe 中初始化
    → 互動式地圖顯示在頁面上

15. [Browser: 結果卡片] _renderResults()
    → 顯示 NLP 分析標籤 "🔍 搜尋：火鍋 ｜ 步行 15 分鐘內"
    → 每間餐廳一張卡片：名稱、地址、步行時間、推薦原因
    → ❤️ 最愛按鈕 (已收藏的顯示紅心)
    → 🗺 分享投票按鈕
```

---

## 11. JSON 資料儲存

所有資料以 JSON 檔案持久化於 `data/` 目錄，格式如下：

**`users.json`**
```json
{
    "uuid-xxx": {
        "id": "uuid-xxx",
        "username": "alice",
        "password_hash": "$2b$12$...",
        "created_at": "2024-01-01T00:00:00+00:00"
    }
}
```

**`groups.json`**
```json
{
    "group-uuid": {
        "id": "group-uuid",
        "name": "美食探險隊",
        "creator": "alice",
        "members": ["alice", "bob", "demo"],
        "created_at": "2024-01-01T00:00:00+00:00"
    }
}
```

**`group_votes.json`**
```json
{
    "vote-uuid": {
        "id": "vote-uuid",
        "group_id": "group-uuid",
        "title": "今天吃什麼？",
        "options": [
            {"id": "rest-id", "name": "壽司郎", "address": "...", "walking_minutes": 8.5,
             "latitude": 24.82, "longitude": 120.97}
        ],
        "votes": {"rest-id": ["alice", "bob"]},
        "creator": "alice",
        "status": "open",
        "created_at": "2024-01-01T00:00:00+00:00"
    }
}
```

**`wallets.json`**
```json
{
    "alice": {"balance": 1500.0, "updated_at": "2024-01-01T00:00:00+00:00"},
    "bob":   {"balance": 800.0,  "updated_at": "2024-01-01T00:00:00+00:00"}
}
```

**`transactions.json`**
```json
[
    {
        "id": "tx-uuid",
        "type": "transfer",
        "from_user": "alice",
        "to_user": "bob",
        "amount": 200.0,
        "note": "午餐費",
        "group_id": "group-uuid",
        "created_at": "2024-01-01T12:00:00+00:00"
    }
]
```

---

## 12. 安全設計

| 威脅 | 防護措施 |
|------|---------|
| 未授權存取 API | JWT Bearer Token，每個需認證的端點都有 `Depends(get_current_user)` |
| Token 竊取 | 儲存於 `sessionStorage`（非 localStorage），關閉頁籤即清除 |
| 搜尋結果竄改 | RSA-PSS SHA-256 數位簽章，前端強制驗章 |
| SQL Injection | 無 SQL，使用 JSON 檔案儲存 |
| XSS | 前端所有用戶輸入通過 `_esc()` HTML 轉義後才渲染 |
| CORS | 只允許 GitHub Pages URL 和 localhost，其他來源請求被拒絕 |
| 密碼洩露 | bcrypt hash 儲存，管理員密碼只存於環境變數 |
| 執行緒競爭 | `threading.Lock` 保護所有 JSON 讀寫操作 |
| 圖片攻擊 | POST /recognize 限制最大 10MB，PIL 重新解碼防止惡意 payload |
| 管理員冒充 | `_is_admin()` 只對比 JWT payload 的 `sub` 欄位與環境變數 |
