"""
測試腳本：送任務給 192.168.1.194:8000/inspection_task
"""
import httpx
import json

ROBOT_URL = "http://192.168.1.194:8000/inspection_task"

task = {
    "product_name": "紅色方塊",
    "inspection_items": [
        {"name": "產品邊長", "threshold": 0.95, "method": "vision_detection", "standard": "28mm ±1mm"},
        {"name": "頂部面積", "threshold": 0.95, "method": "vision_detection", "standard": "784mm² ±50mm²"},
        {"name": "重量",     "threshold": 0.90, "method": "manual",           "standard": "16g ±1g"},
        {"name": "瑕疵面積", "threshold": 0.85, "method": "vision_detection", "standard": "< 7.84mm²（頂部面積 1% 以內）"},
        {"name": "瑕疵種類", "threshold": 0.85, "method": "vision_detection", "standard": "無黑點、無塊狀瑕疵"},
    ],
    "placement": {"pass": "正常區", "fail": "缺陷區"},
    "result": "pending",
    "requester_id": "test-user-001",
}

print(f"送出任務到 {ROBOT_URL}")
print(json.dumps(task, ensure_ascii=False, indent=2))
print()

try:
    resp = httpx.post(ROBOT_URL, json=task, timeout=10)
    print(f"狀態碼：{resp.status_code}")
    print(f"回應：{resp.text}")
except Exception as e:
    print(f"失敗：{e}")
