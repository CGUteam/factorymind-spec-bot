# RAG Spec 查詢系統 — 實作指南

> 本文件給負責 RAG Spec 查詢模組的隊友參考。

---

## RAG 是什麼

**RAG = Retrieval-Augmented Generation（檢索增強生成）**

不用 RAG 的問題：
```
問 LLM：「A產品外觀缺陷的 threshold 是多少？」
LLM：「我不知道，這是你們公司內部資料」
```

用 RAG 的流程：
```
1. 先去產品規格書（PDF/Excel）裡搜尋「A產品 外觀缺陷」
2. 找到相關段落：「外觀缺陷允收標準：0.85」
3. 把這段資料丟給 LLM
4. LLM 根據這段資料回答正確答案
```

---

## 系統架構

```
產品規格文件（PDF / Excel / CSV）
        ↓
   切成小段（Chunking）
        ↓
   Embedding 模型轉成向量
        ↓
   存進 Vector DB（FAISS / Qdrant）
        ↓
收到查詢請求（product_name + inspection_items）
        ↓
   在 Vector DB 搜尋最相關段落
        ↓
   丟給 LLM 整理成結構化資料
        ↓
   回傳 threshold 和標準
```

---

## 推薦技術選擇

| 用途 | 推薦 | 理由 |
|------|------|------|
| RAG 框架 | LlamaIndex | 文件處理最方便，支援 PDF/Excel |
| Embedding | bge-m3 | 支援中文，本地跑 |
| Vector DB | FAISS | 輕量，不用架服務 |
| LLM | Ollama + Qwen2.5:7b | 跟系統現有的一樣 |
| API | FastAPI | 跟 ASR 服務風格一致 |

---

## API 規格（必須對齊）

ASR 服務會呼叫你的 RAG API，格式如下：

### `POST /query_spec`

**Request**
```json
{
  "product_name": "A產品",
  "inspection_items": ["外觀缺陷", "尺寸"]
}
```

**Response**
```json
{
  "product_name": "A產品",
  "inspection_items": [
    {
      "name": "外觀缺陷",
      "threshold": 0.85,
      "method": "vision_detection",
      "standard": "無明顯刮痕、壓痕、異色"
    },
    {
      "name": "尺寸",
      "threshold": 0.95,
      "method": "vision_detection",
      "standard": "長寬誤差 ±0.5mm 以內"
    }
  ]
}
```

---

## 建議實作方式

### 方式 A：結構化查表（推薦先做）

如果規格是 Excel / CSV，**不需要 RAG**，直接查表最準確，數值不會被 LLM 亂生。

```python
# spec_db.csv 格式範例：
# product_name, item, threshold, method, standard
# A產品, 外觀缺陷, 0.85, vision_detection, 無明顯刮痕

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
df = pd.read_csv("spec_db.csv")

class QueryRequest(BaseModel):
    product_name: str
    inspection_items: list[str]

@app.post("/query_spec")
def query_spec(req: QueryRequest):
    items = []
    for item_name in req.inspection_items:
        row = df[
            (df["product_name"] == req.product_name) &
            (df["item"] == item_name)
        ]
        if not row.empty:
            items.append({
                "name": item_name,
                "threshold": float(row.iloc[0]["threshold"]),
                "method": row.iloc[0]["method"],
                "standard": row.iloc[0]["standard"],
            })
    return {"product_name": req.product_name, "inspection_items": items}
```

### 方式 B：完整 RAG（規格是非結構化文件時使用）

規格書是 PDF / Word 等非結構化格式時，才需要完整 RAG 流程。

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# 1. 載入文件
documents = SimpleDirectoryReader("./specs/").load_data()

# 2. 建立 Embedding + Index
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")
index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)

# 3. 查詢
query_engine = index.as_query_engine()
response = query_engine.query("A產品外觀缺陷的允收標準是什麼？")
```

---

## 建議開發順序

1. **先用方式 A（查表）** — 快速讓整個系統跑通
2. **確認 API 格式與 ASR 服務對齊** — 用上方的 Request / Response 格式
3. **之後再升級成方式 B（RAG）** — 支援更複雜的非結構化規格書

---

## 安裝套件

```bash
conda activate openclaw_env

# 方式 A（查表）
pip install fastapi uvicorn pandas

# 方式 B（完整 RAG）
pip install llama-index llama-index-embeddings-huggingface faiss-cpu
```

---

## 聯絡

串接問題請參考 `API_DOC.md`，或直接找負責 ASR 模組的隊友。
