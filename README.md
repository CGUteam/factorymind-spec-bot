# 🎯 工廠自動品管系統

本專案結合 **語音互動、RAG Spec 檢索、AI 視覺檢測與機器人品管**，打造一套智慧工廠品管系統。

[專案簡介文件(5/12報告)](https://docs.google.com/presentation/d/1nNs3pxZ__qHQd3AwB9CL2SthH0tneZKk/edit?usp=sharing&ouid=113393456849610287890&rtpof=true&sd=true)


開發人員: 
- 王喻筠
- [吳思聯](https://github.com/Poopogen)
- [張舒茹](https://github.com/shuru921)
- 謝易澄

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

支援資料來源：
- PDF / Excel / CSV / JSON

技術：
- Embedding：bge-m3 / e5
- Vector DB：FAISS / Qdrant
- Framework：LlamaIndex / LangChain / GraphRAG

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
- 語音 → Spec → 模擬結果

### Phase 2
- 加入 AI 視覺

### Phase 3
- 加入 Robot（SO-101 Arm）

### Phase 4
- 優化 + 部署

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
