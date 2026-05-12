# OpenClaw ASR Service — API 文件

> **服務位置（Jetson Orin 內網）：** `http://<jetson-ip>:8000`  
> **外網測試用（ngrok，每次重啟會變）：** `https://xxxx.ngrok-free.app`

---

## 系統架構

**輸入方式 A：LINE Bot**
```
LINE 語音訊息
  ↓
POST /line/webhook
  ↓
Whisper ASR → 文字
  ↓
Qwen2.5:7b Agent → 結構化任務 JSON
  ↓
LINE 回覆結果
```

**輸入方式 B：ESP32 智慧音箱**
```
ESP32 麥克風錄音（WAV）
  ↓
POST /process
  ↓
Whisper ASR → 文字
  ↓
Qwen2.5:7b Agent → 結構化任務 JSON
  ↓
LINE Push Message 通知使用者
```

**兩者共同的後續串接（待完成）：**
```
結構化任務 JSON
  ↓
[待串接] RAG Spec 查詢
  ↓
[待串接] Robot 執行
  ↓
LINE 回報最終結果
```

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
    "result": "pending"
  }
}
```

**處理完成後自動推送 LINE 訊息格式：**
```
📡 ESP32 語音指令
🎤 辨識：幫我檢查 A 產品的外觀缺陷

📋 檢查任務：
產品：A產品
項目：外觀缺陷
狀態：pending
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
| `result` | string | `pending` / `pass` / `fail` |

**method 判斷規則：**
- 外觀、缺陷、尺寸、顏色相關 → `vision_detection`
- 其他 → `manual`

---

## 串接說明

### RAG Spec 模組（給負責 RAG 的隊友）

目前 Agent 解析出 `product_name` 和 `inspection_items` 後，  
**下一步需要 RAG 根據 `product_name` 查詢對應的 Spec**，補充正確的 `threshold` 與檢查標準。

RAG 服務需提供以下 endpoint 供 ASR 服務呼叫：

```
POST /query_spec
Body: { "product_name": "A產品", "inspection_items": ["外觀缺陷"] }

Response:
{
  "product_name": "A產品",
  "inspection_items": [
    { "name": "外觀缺陷", "threshold": 0.85, "method": "vision_detection", "standard": "無明顯刮痕" }
  ]
}
```

> 詳細實作方式請參考 [RAG_GUIDE.md](./RAG_GUIDE.md)

---

### Robot 模組（給負責 Robot 的隊友）

RAG 補完 Spec 後，任務 JSON 會送給 Robot 執行。  
Robot 執行完畢後，請回傳結果更新 `result` 欄位：

```
POST /inspection_result   （⚠️ 待實作，目前尚未開通）
Body:
{
  "product_name": "A產品",
  "inspection_items": [
    { "name": "外觀缺陷", "score": 0.92, "pass": true }
  ],
  "result": "pass"
}
```

> 格式確認後，由 ASR 服務這邊開通此 endpoint，結果將透過 LINE Push Message 回報給使用者。

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
| Ollama Port | 11434 |
