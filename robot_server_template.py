"""
Robot Server 範本（給 192.168.1.194 那台 Orin 跑）
接收品管任務 → 執行檢查 → 回傳結果給 192.168.2.76:8000/inspection_result
"""
import threading
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Robot Inspection Server")

# 你這台（192.168.2.76）的 callback 位址
CALLBACK_URL = "http://192.168.2.76:8000/inspection_result"


class InspectionItem(BaseModel):
    name: str
    threshold: float = 0.80
    method: str = "vision_detection"
    standard: str = ""


class InspectionTask(BaseModel):
    product_name: str
    inspection_items: list[InspectionItem]
    placement: dict = {"pass": "正常區", "fail": "缺陷區"}
    result: str = "pending"
    requester_id: str | None = None


def run_inspection(task: InspectionTask):
    """
    ─── 在這裡寫真實的機器人檢查邏輯 ───

    task.product_name          → 產品名稱（例：紅色方塊）
    task.inspection_items      → 要檢查的項目清單
      .name                    → 項目名稱（外觀、重量、尺寸...）
      .threshold               → 合格門檻（0.0 ~ 1.0）
      .method                  → vision_detection 或 manual
      .standard                → 規格描述（例：150g ±5g）
    """
    items_result = []
    overall_pass = True

    for item in task.inspection_items:
        # ↓↓↓ 把這裡換成你們的實際檢測邏輯 ↓↓↓
        score = 0.0          # 實際檢測分數（0.0 ~ 1.0）
        # ↑↑↑ ─────────────────────────────── ↑↑↑

        passed = score >= item.threshold
        if not passed:
            overall_pass = False

        items_result.append({
            "name": item.name,
            "score": round(score, 2),
            "threshold": item.threshold,
            "pass": passed,
        })

    final_result = "pass" if overall_pass else "fail"
    placed_in = task.placement.get(final_result, "未知區")

    # 回傳結果給 192.168.2.76
    payload = {
        "product_name": task.product_name,
        "inspection_items": items_result,
        "placement": task.placement,
        "placed_in": placed_in,
        "result": final_result,
        "requester_id": task.requester_id,   # ← 必須帶回，LINE 才知道發給誰
    }

    try:
        with httpx.Client(timeout=10) as client:
            client.post(CALLBACK_URL, json=payload)
        print(f"[Robot] 結果已回傳：{final_result} → {placed_in}")
    except Exception as e:
        print(f"[Robot] 回傳失敗：{e}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/inspection_task")
def inspection_task(task: InspectionTask):
    print(f"[Robot] 收到任務：{task.product_name}，項目：{[i.name for i in task.inspection_items]}")
    threading.Thread(target=run_inspection, args=(task,), daemon=True).start()
    return {"status": "received", "message": f"inspection task received"}
