"""
Mock RAG Spec 查詢服務（模擬用）
真實 RAG 完成後，把 URL 換掉即可，程式不用改
"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock RAG Service")

# 模擬產品規格資料庫
SPEC_DB = {
    "A產品": [
        {"name": "外觀缺陷", "threshold": 0.85, "method": "vision_detection", "standard": "無明顯刮痕、壓痕、異色"},
        {"name": "尺寸",     "threshold": 0.95, "method": "vision_detection", "standard": "長寬誤差 ±0.5mm 以內"},
        {"name": "重量",     "threshold": 0.90, "method": "manual",           "standard": "100g ±5g"},
    ],
    "B產品": [
        {"name": "外觀缺陷", "threshold": 0.80, "method": "vision_detection", "standard": "無裂痕、缺角"},
        {"name": "顏色",     "threshold": 0.90, "method": "vision_detection", "standard": "色差 ΔE < 2.0"},
    ],
}

DEFAULT_SPEC = [
    {"name": "外觀缺陷", "threshold": 0.80, "method": "vision_detection", "standard": "無明顯缺陷"},
]


class QueryRequest(BaseModel):
    product_name: str
    inspection_items: list[str]


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-rag"}


@app.post("/query_spec")
def query_spec(req: QueryRequest):
    all_specs = SPEC_DB.get(req.product_name, DEFAULT_SPEC)

    # 只回傳被要求的項目，找不到就用預設
    result = []
    for item_name in req.inspection_items:
        matched = next((s for s in all_specs if s["name"] == item_name), None)
        if matched:
            result.append(matched)
        else:
            result.append({
                "name": item_name,
                "threshold": 0.80,
                "method": "vision_detection",
                "standard": "無明顯缺陷",
            })

    print(f"[RAG] Query: {req.product_name} → {[i['name'] for i in result]}")
    return {"product_name": req.product_name, "inspection_items": result}
