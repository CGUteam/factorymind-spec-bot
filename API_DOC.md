# OpenClaw ASR Service — API 文件

> **服務位置（Jetson Orin 內網）：** `http://192.168.2.55:8000`  
> **外網測試用（ngrok，每次重啟會變）：** `https://xxxx.ngrok-free.app`

---

## 團隊分工

| 模組 | 負責人 | 位置 | 狀態 |
|------|--------|------|------|
| ASR + OpenClaw Agent | 張舒茹 | 實驗室（AI Office） | ✅ 完成 |
| RAG Spec 查詢 | 張舒茹 | 整合於主服務（port 8000） | ✅ 完成 |
| Robot SO-101 | 隊友 B | 實驗室（AI Office） | ⬜ 開發中 |

---

## 系統架構

**完整流程：**
```
LINE 語音 / 文字 / ESP32 音訊
          ↓
   POST /line/webhook 或 /process
          ↓
🎤 faster-whisper ASR → 文字
          ↓
📋 Ollama + Qwen2.5:7b → 結構化任務 JSON
          ↓
🔍 RAG Spec 查詢（POST /query_spec）→ 補充 threshold / 標準
          ↓
🤖 Robot 執行（POST /inspection_task）→ 手臂抓取、拍照、AI 判斷
          ↓
📊 POST /inspection_result 回傳結果
          ↓
LINE Push Message 品管報告
```

**LINE 訊息範例：**
```
🎤 辨識（faster-whisper）：
幫我檢查A產品是否有缺陷，有的話放到缺陷區

📋 檢查任務（Ollama + Qwen2.5:7b）：
產品：A產品
項目：外觀缺陷
狀態：查詢 Spec 中...

🔍 Spec 查詢（RAG）：
產品：A產品
  • 外觀缺陷：門檻 0.85｜無明顯刮痕、壓痕、異色

📊 品管報告（SO-101 Robot）：
產品：A產品
結果：✅ PASS
放置：📦 正常區

檢查明細：
  ✅ 外觀缺陷：0.91（門檻 0.85）
```
<img width="1066" height="1535" alt="S__34529289" src="https://github.com/user-attachments/assets/d28ac796-4d91-4af8-b2dc-8a3016042cfa" />

**輸入方式 A：LINE Bot**
```
LINE 語音 / 文字訊息
  ↓
POST /line/webhook
  ↓
Whisper ASR → 文字（語音）或直接解析（文字）
  ↓
Qwen2.5:7b Agent → 結構化任務 JSON
  ↓
LINE 回覆結果
```
<img width="1290" height="675" alt="S__34521135_0" src="https://github.com/user-attachments/assets/66ed61e0-1ba2-4dc5-adef-8c374374daf2" />

**輸入方式 B：ESP32 智慧音箱**
```
ESP32 按住按鈕錄音（WAV）
  ↓
POST /process
  ↓
Whisper ASR → 文字
  ↓
Qwen2.5:7b Agent → 結構化任務 JSON
  ↓
LINE Push Message 通知使用者
```
<img width="1290" height="581" alt="S__34521136_0" src="https://github.com/user-attachments/assets/c299661f-be0f-464f-9b12-3b1c55bac3d0" />

---

## Demo 當天網路架構

```
手機熱點
  ├── 你的 Jetson（ASR, :8000）
  ├── 隊友 B 的 Jetson（Robot, :PORT）
  └── ESP32 智慧音箱
```

> RAG 已整合於主服務（port 8000），`POST /query_spec` 直接提供 Spec 查詢

---

## Endpoints

### `GET /health`

確認服務是否正常運行。

**Response**
```json
{ "status": "ok" }
```

---

### `POST /process`

**ESP32 智慧音箱專用端點。** 一次完成 ASR + Agent 解析，回傳結構化任務 JSON，並自動推 LINE 通知使用者。

**Content-Type：** `multipart/form-data`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `file` | File | ✅ | 音訊檔（WAV 建議） |
| `language` | string | ❌ | 語言代碼，預設自動偵測 |

**Response**
```json
{
  "text": "幫我檢查 A 產品的外觀缺陷",
  "language": "zh",
  "task": {
    "product_name": "A產品",
    "inspection_items": [
      { "name": "外觀缺陷", "threshold": 0.8, "method": "vision_detection" }
    ],
    "placement": { "pass": "正常區", "fail": "缺陷區" },
    "result": "pending"
  }
}
```

**ESP32 呼叫範例（Arduino / C++）**
```cpp
HTTPClient http;
http.begin("http://<jetson-ip>:8000/process");
// multipart POST 傳送 WAV 音訊檔
```

---

### `POST /transcribe`

上傳音訊檔，回傳語音辨識文字。

**Content-Type：** `multipart/form-data`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `file` | File | ✅ | 音訊檔（WAV / MP3 / FLAC / OGG / M4A） |
| `language` | string | ❌ | 語言代碼，預設 `null`（自動偵測中英混合） |

**Response**
```json
{
  "text": "幫我檢查 A 產品的外觀缺陷",
  "language": "zh",
  "language_probability": 0.998
}
```

**curl 範例**
```bash
curl -X POST http://<jetson-ip>:8000/transcribe \
  -F "file=@audio.wav;type=audio/wav"
```

---

### `POST /inspection_result`

**Robot 執行完畢後呼叫此 endpoint 回傳結果**，Jetson 收到後推 LINE 品管報告。

**Request**
```json
{
  "product_name": "A產品",
  "inspection_items": [
    { "name": "外觀缺陷", "score": 0.92, "threshold": 0.85, "pass": true }
  ],
  "placed_in": "正常區",
  "result": "pass"
}
```

**Response**
```json
{ "status": "ok" }
```

---

## 任務 JSON 格式（Agent 輸出）

ASR 文字經過 Qwen2.5:7b 解析後，產生以下結構。  
**RAG 模組** 和 **Robot 模組** 應依此格式對接。

```json
{
  "product_name": "A產品",
  "inspection_items": [
    {
      "name": "外觀缺陷",
      "threshold": 0.8,
      "method": "vision_detection"
    }
  ],
  "placement": {
    "pass": "正常區",
    "fail": "缺陷區"
  },
  "result": "pending"
}
```

| 欄位 | 類型 | 說明 |
|------|------|------|
| `product_name` | string | 從語音指令解析的產品名稱 |
| `inspection_items` | array | 檢查項目列表 |
| `inspection_items[].name` | string | 檢查項目名稱 |
| `inspection_items[].threshold` | float | 允收門檻（0~1） |
| `inspection_items[].method` | string | `vision_detection` 或 `manual` |
| `placement.pass` | string | 合格時放置區域 |
| `placement.fail` | string | 不合格時放置區域 |
| `result` | string | `pending` / `pass` / `fail` |

---

## 串接說明

### RAG Spec 模組

RAG 已整合於主服務，`POST /query_spec` 直接可用，不需要另外架設服務。

Agent 解析出 `product_name` 和 `inspection_items` 後，自動呼叫 `/query_spec` 補充 `threshold` 與檢查標準。

**查詢策略（三層）：**
1. 精準名稱比對
2. 顏色 + 形狀規則比對
3. bge-m3 embedding RAG fallback

**新增或修改產品規格：** 編輯 `data/products.json`

> 詳細說明請參考 [RAG_GUIDE.md](./RAG_GUIDE.md)

---

### Robot 模組（給負責 Robot 的隊友）

RAG 補完 Spec 後，任務 JSON 送給 Robot 執行。

**Robot 服務需提供：**

```
POST /inspection_task
Body:
{
  "product_name": "A產品",
  "inspection_items": [
    { "name": "外觀缺陷", "threshold": 0.85, "method": "vision_detection" }
  ],
  "placement": { "pass": "正常區", "fail": "缺陷區" }
}

Response: { "status": "accepted" }
```

**執行完畢後，Robot 需回傳結果：**

```
POST http://192.168.2.55:8000/inspection_result
Body:
{
  "product_name": "A產品",
  "inspection_items": [
    { "name": "外觀缺陷", "score": 0.92, "threshold": 0.85, "pass": true }
  ],
  "placed_in": "正常區",
  "result": "pass"
}
```

**串接方式：** 告知你的服務 IP 和 Port，更新 Jetson 的 `.env`：
```
ROBOT_URL=http://<你的IP>:<PORT>/inspection_task
```

---

## 相關文件

| 文件 | 說明 |
|------|------|
| [RAG_GUIDE.md](./RAG_GUIDE.md) | RAG Spec 查詢系統實作指南（給負責 RAG 的隊友） |

---

## 環境資訊

| 項目 | 規格 |
|------|------|
| 設備 | Jetson AGX Orin |
| ASR 模型 | faster-whisper small (int8) |
| LLM | Ollama + Qwen2.5:7b |
| Python 環境 | conda `openclaw_env` (Python 3.11) |
| 服務 Port | 8000 |
| Mock Robot Port | 8002 |
| Ollama Port | 11434 |
