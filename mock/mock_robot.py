"""
Mock Robot 檢測服務（模擬用）
真實 Robot 完成後，把 URL 換掉即可，程式不用改
"""
import random
import threading
import time
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Robot Service")

# Jetson ASR 服務的位址（接收檢查結果）
JETSON_CALLBACK_URL = "http://localhost:8000/inspection_result"


class InspectionTask(BaseModel):
    product_name: str
    inspection_items: list[dict]
    placement: dict = {"pass": "正常區", "fail": "缺陷區"}
    result: str = "pending"
    requester_id: str | None = None


def simulate_inspection(task: InspectionTask):
    """模擬機器手臂執行檢查（背景執行）"""
    print(f"[Robot] 開始檢查 {task.product_name}，模擬 3 秒...")
    time.sleep(3)  # 模擬檢查時間

    # 隨機產生檢查結果（80% pass）
    items_result = []
    overall_pass = True
    for item in task.inspection_items:
        score = round(random.uniform(0.70, 0.99), 2)
        threshold = item.get("threshold", 0.80)
        passed = score >= threshold
        if not passed:
            overall_pass = False
        items_result.append({
            "name": item["name"],
            "score": score,
            "threshold": threshold,
            "pass": passed,
        })

    final_result = "pass" if overall_pass else "fail"
    placement_zone = task.placement.get(final_result, "未知區")
    print(f"[Robot] 完成：{final_result} → 放到 {placement_zone}")

    result = {
        "product_name": task.product_name,
        "inspection_items": items_result,
        "placement": task.placement,
        "placed_in": placement_zone,
        "result": final_result,
        "requester_id": task.requester_id,
    }

    # 回傳結果給 Jetson
    try:
        with httpx.Client(timeout=10) as client:
            client.post(JETSON_CALLBACK_URL, json=result)
        print("[Robot] 結果已回傳給 Jetson")
    except Exception as e:
        print(f"[Robot] 回傳失敗：{e}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-robot"}


@app.post("/inspection_task")
def inspection_task(task: InspectionTask):
    print(f"[Robot] 收到任務：{task.product_name}")
    # 背景執行，立刻回 202 避免 timeout
    threading.Thread(target=simulate_inspection, args=(task,), daemon=True).start()
    return {"status": "accepted", "message": f"開始檢查 {task.product_name}"}
