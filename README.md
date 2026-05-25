# 🎯 工廠自動品管系統

本專案結合 **語音互動、RAG Spec 檢索、AI 視覺檢測與機器人品管**，打造一套智慧工廠品管系統。

[專案簡介文件(5/12報告)](https://docs.google.com/presentation/d/1nNs3pxZ__qHQd3AwB9CL2SthH0tneZKk/edit?usp=sharing&ouid=113393456849610287890&rtpof=true&sd=true)


開發人員: 
- 王喻筠
- [吳思聯](https://github.com/Poopogen)
- [張舒茹](https://github.com/shuru921)
- [謝易澄](https://github.com/dean900334)

## 📦 相關 Repository

| 模組 | Repository | Branch |
|------|-----------|--------|
| Jetson ASR / OpenClaw Agent | [factorymind-spec-bot](https://github.com/CGUteam/factorymind-spec-bot) | `feature/asr-service` |
| ESP32 智慧音箱韌體 | [nn-speaker](https://github.com/shuru921/nn-speaker) | `feature/jetson-asr` |

---

## 🚀 系統特色

- 🎤 語音控制工廠檢測流程
- 🧠 RAG Spec 智能檢索（支援非結構化文件）
- 🤖 機器手臂自動抓取與分類產品
- 👁️ AI 視覺檢測缺陷（pass / fail）
- 📊 自動生成檢查報告

---

## 🧩 系統架構

```
User (語音)
   ↓
ESP32 (麥克風)
   ↓
Jetson Orin
   ├── OpenClaw Agent
   ├── RAG Spec 檢索
   └── 任務派送
        ↓
Robot System (SO-101 Arm + Camera + AI Model)
        ↓
檢查結果 → 報告輸出
```

---

## 🏗️ 系統模組

### 1️⃣ 語音系統（ESP32）
- 收音（I2S 麥克風）
- 傳送音訊（HTTP / MQTT / WebSocket）

👉 建議：只做「收音 + 傳輸」，ASR 放在 Jetson

---

### 2️⃣ Jetson Orin（核心）

負責：
- 語音辨識（Whisper）
- 指令理解（LLM / OpenClaw）
- Spec 查詢（RAG）
- 任務派送
- 報告生成

---

### 3️⃣ OpenClaw Agent

負責：
- 解析使用者意圖
- 查詢 Spec
- 生成檢查任務
- 整理檢查報告

---

### 4️⃣ RAG Spec 檢索

實作於 `app/` 模組，採三層查詢策略：

| 優先順序 | 方式 | 說明 |
|---------|------|------|
| 1 | 精準名稱比對 | 文字中包含 `product_name` |
| 2 | 顏色 + 形狀規則 | 從文字推斷顏色與形狀 |
| 3 | RAG fallback | Ollama `bge-m3` embedding + cosine similarity（threshold 0.5）|

產品規格資料：`data/products.json`，每筆包含 `inspection_specs`（外觀缺陷、尺寸、重量、顏色的 threshold / method / standard）。

端點：`POST /query_spec`（與主服務同一 port，不需獨立服務）

---

### 5️⃣ Robot System（核心亮點）

使用：

👉 **LeRobot SO-101 Arm**

功能：

- 抓取產品
- 移動到檢測位置
- Camera 拍照
- AI 模型檢測缺陷
- 分類（合格 / 不合格）

---

## 🤖 Robot 流程

```
抓取產品
   ↓
移動到檢測區
   ↓
拍照
   ↓
AI 判斷
   ↓
分類放置
   ↓
回傳結果
```

---

## 👁️ AI 視覺模型

| 任務 | 模型 |
|------|------|
| 分類 | ResNet / EfficientNet |
| 偵測 | YOLOv8 |
| 分割 | U-Net / Mask R-CNN |
| 異常檢測 | PatchCore / PaDiM |

👉 建議：
- 資料少 → anomaly detection
- 資料多 → YOLO

---

## 🎤 語音模型

| 任務 | 模型 |
|------|------|
| 語音辨識 | Whisper / faster-whisper |
| 語音合成 | Piper / Edge TTS |

---

## 🧠 LLM / NLP

- Qwen2.5
- Llama 3
- GPT API

用途：
- 指令解析
- 報告生成

---

## 🔌 API 設計

### 查詢 Spec
```
POST /query_spec
```

### 建立檢查任務
```
POST /inspection_task
```

### 回傳結果
```
POST /inspection_result
```

> 詳細 API 格式請參考 [API_DOC.md](./API_DOC.md)  
> RAG 模組實作指南請參考 [RAG_GUIDE.md](./RAG_GUIDE.md)

---

## ⚙️ 環境設定

複製並填寫 `.env`：

```env
# LINE Bot
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
LINE_NOTIFY_USER_ID=

# Whisper ASR
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE=int8

# 產品規格查詢（與主服務同一 port，不需獨立 RAG 服務）
RAG_URL=http://localhost:8000/query_spec

# Robot
ROBOT_URL=http://localhost:8002/inspection_task
```

## 🚀 啟動方式

```bash
# 確認 Ollama 已啟動並安裝 bge-m3（RAG fallback 用）
ollama pull bge-m3

# 一鍵啟動服務 + ngrok 公開 URL
./start.sh
```

啟動後終端會印出 LINE Webhook URL，貼到 LINE Developers 後台即可。

> ngrok 免費版每次重啟 URL 會變，需重新更新 LINE Webhook 設定。

---

## 📦 硬體需求

| 類別 | 設備 |
|------|------|
| 邊緣運算 | Jetson Orin |
| 語音 | ESP32 + 麥克風 |
| 機器手臂 | SO-101 Arm |
| 視覺 | USB / 工業相機 |
| 光源 | LED |
| 儲存 | NVMe SSD |

---

## 🧪 開發階段

### Phase 1（MVP）
- ✅ 語音辨識（faster-whisper，支援中英混合）
- ✅ LINE Bot 語音輸入整合
- ✅ OpenClaw Agent 指令解析（Ollama + Qwen2.5:7b）
- ✅ 結構化任務 JSON 輸出
- ✅ RAG Spec 查詢串接（三層查詢 + bge-m3，整合於主服務）
- ⬜ 模擬結果回傳 LINE

### Phase 2
- ⬜ 加入 AI 視覺（YOLOv8 / PatchCore）

### Phase 3
- ⬜ 加入 Robot（SO-101 Arm）

### Phase 4
- ⬜ 優化 + 部署

---

## ⚠️ 風險

- RAG 數值錯誤（→ 建議結構化 Spec）
- 視覺資料不足
- Jetson 資源不足

---

## 🏁 結論

本系統整合三大核心：

1️⃣ 語音互動（ESP32 + Whisper）  
2️⃣ Spec 檢索（RAG + LLM）  
3️⃣ AI 機器人品管（SO-101 Arm + Vision AI）

👉 打造真正「會聽、會查、會動」的智慧工廠系統 🚀
