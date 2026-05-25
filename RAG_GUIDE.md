# RAG Spec 查詢系統 — 實作說明

> RAG 已整合於主服務（`app/` 模組），本文件說明實作細節與如何維護產品規格資料。

---

## 架構概覽

```
POST /query_spec
      ↓
app/command_parser.py   → 從產品名稱文字解析關鍵字
      ↓
app/product_retriever.py → 三層查詢
  ├── Tier 1：精準名稱比對       → matched_by: exact_name
  ├── Tier 2：顏色 + 形狀規則    → matched_by: color_shape_rule
  └── Tier 3：bge-m3 RAG fallback → matched_by: rag_bge_m3
      ↓
data/products.json → 回傳對應 inspection_specs
```

---

## 產品規格資料（data/products.json）

每筆產品格式如下：

```json
{
  "product_id": "P001",
  "product_name": "藍色方塊",
  "weight": 100,
  "color": "藍色",
  "shape": "方塊",
  "size": {"length": 5, "width": 5, "height": 5, "unit": "cm"},
  "inspection_specs": {
    "外觀缺陷": {"threshold": 0.85, "method": "vision_detection", "standard": "無明顯刮痕、壓痕、異色"},
    "尺寸":     {"threshold": 0.95, "method": "vision_detection", "standard": "邊長誤差 ±0.5mm 以內"},
    "重量":     {"threshold": 0.90, "method": "manual",           "standard": "100g ±5g"},
    "顏色":     {"threshold": 0.90, "method": "vision_detection", "standard": "色差 ΔE < 2.0"}
  }
}
```

### 新增產品

直接在 `data/products.json` 新增一筆，重啟服務即生效。

### method 規則

| 檢查類型 | method |
|---------|--------|
| 外觀、缺陷、尺寸、顏色 | `vision_detection` |
| 重量、其他 | `manual` |

---

## API 規格

### `POST /query_spec`

**Request**
```json
{
  "product_name": "藍色方塊",
  "inspection_items": ["外觀缺陷", "重量"]
}
```

**Response（找到產品）**
```json
{
  "product_name": "藍色方塊",
  "product_found": true,
  "inspection_items": [
    {"name": "外觀缺陷", "threshold": 0.85, "method": "vision_detection", "standard": "無明顯刮痕、壓痕、異色"},
    {"name": "重量",     "threshold": 0.90, "method": "manual",           "standard": "100g ±5g"}
  ]
}
```

**Response（找不到產品）**
```json
{
  "product_name": "紫色星星",
  "product_found": false,
  "inspection_items": [...]
}
```

> `product_found: false` 時，LINE Bot 會停止流程並通知使用者，**不會派送給 Robot**。  
> `product_found: true` 但某個 `inspection_items` 不在該產品規格中，回傳預設值：`threshold: 0.80 / method: vision_detection / standard: 無明顯缺陷`

---

## 三層查詢說明

### Tier 1：精準名稱比對
`product_name` 文字中包含 `products.json` 裡的完整產品名稱，直接回傳。

### Tier 2：顏色 + 形狀規則
從文字中抽出顏色（藍色、紅色…）和形狀（方塊、圓球…），比對出對應產品。

### Tier 3：bge-m3 RAG fallback
前兩層都找不到時，用 Ollama `bge-m3` 將查詢文字和產品資料轉成向量，計算 cosine similarity，相似度 ≥ 0.5 才回傳結果。

> Ollama 未啟動或 bge-m3 未安裝時，Tier 3 會自動跳過，不影響前兩層。

---

## 模組檔案

| 檔案 | 功能 |
|------|------|
| `app/command_parser.py` | 解析產品名稱與屬性關鍵字 |
| `app/product_loader.py` | 載入 `data/products.json`（有 LRU 快取）|
| `app/product_retriever.py` | 三層查詢邏輯 |
| `app/rag_retriever.py` | bge-m3 embedding + cosine similarity |
| `data/products.json` | 產品規格資料 |

---

## 測試

```bash
/home/cluster/miniconda3/envs/openclaw_env/bin/python -m pytest tests/test_rag.py -v
```
