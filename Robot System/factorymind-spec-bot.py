import os
import json
import time
import cv2
import requests
import subprocess
import threading
from PIL import Image
from fastapi import FastAPI, Request
from google import genai
from datetime import datetime

app = FastAPI()
busy = False

# =========================
# 對方接收結果 API
# =========================
OTHER_API_URL = "http://192.168.2.55:8000/inspection_result"

# =========================
# 圖片設定
# =========================
STANDARD_IMG = "Image.jpg"
TEST_IMG = "test.jpg"
CAMERA_ID = 8

# =========================
# LeRobot policy
# =========================
POLICY_SCALE = "yywang122/DL_project_scale"
POLICY_OK = "yywang122/DL_project_box_ok"
POLICY_FAIL = "yywang122/DL_project_box_fail"

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def run_policy(policy_path, task_name,seconds=8):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cmd = [
        "lerobot-record",
        "--robot.type=so101_follower",
        "--robot.port=/dev/ttyACM0",
        "--robot.id=R12255107",
        '--robot.cameras={"handeye":{"type":"opencv","index_or_path":"/dev/video0","width":640,"height":360,"fps":30,"warmup_s":5},"side":{"type":"opencv","index_or_path":"/dev/video2","width":640,"height":360,"fps":30,"warmup_s":5}}',
        f"--dataset.repo_id=yywang122/eval_{task_name}_{timestamp}",
        f"--dataset.single_task={task_name}",
        "--dataset.num_episodes=1",
        f"--dataset.episode_time_s={seconds}",
        "--dataset.reset_time_s=3",
        "--dataset.fps=5",
        f"--policy.path={policy_path}",
        "--policy.device=cuda",
        "--dataset.push_to_hub=False",
        "--display_data=false",
    ]

    subprocess.run(cmd, check=True)


'''def capture_test_image():
    cap = cv2.VideoCapture(CAMERA_ID)

    if not cap.isOpened():
        raise RuntimeError("無法開啟 camera")

    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("無法讀取 frame")

    cv2.imwrite(TEST_IMG, frame)
    print(f"已儲存測試圖: {TEST_IMG}")'''
def capture_test_image():

    import pyrealsense2 as rs
    import numpy as np

    pipeline = rs.pipeline()
    config = rs.config()

    # RealSense RGB stream
    config.enable_stream(
        rs.stream.color,
        1920,
        1080,
        rs.format.bgr8,
        8
    )

    # 啟動 camera
    pipeline.start(config)

    try:

        # 等曝光穩定
        for _ in range(30):
            frames = pipeline.wait_for_frames()

        color_frame = frames.get_color_frame()

        if not color_frame:
            raise RuntimeError("沒有讀到 color frame")

        # 轉 numpy
        frame = np.asanyarray(
            color_frame.get_data()
        )

        print("camera shape:", frame.shape)

        # 可選：亮度微調
        frame = cv2.convertScaleAbs(
            frame,
            alpha=1.2,
            beta=30
        )

        # 存圖
        cv2.imwrite(TEST_IMG, frame)

        print(f"已儲存測試圖: {TEST_IMG}")

    finally:

        pipeline.stop()

def ask_gemini(task_json):
    prompt = f"""
你會收到一份檢測任務 JSON，以及標準圖與測試圖。
請根據檢測任務內容、標準圖、測試圖進行判斷。

檢測任務 JSON：
{json.dumps(task_json, ensure_ascii=False, indent=2)}

請只輸出 JSON。
不要 markdown。
不要解釋。
不要多餘文字。

輸出格式必須完全符合：

{{
  "產品": str,
  "產品邊長":float ,
  "頂部面積": float,
  "重量": float,
  "瑕疵面積": float,
  "瑕疵種類": str,
  "pass": true,
  "requester_id": "U6fa767..."
}}

規則：
1. "產品" 請使用 task_json 的 product_name。
2. "requester_id" 請使用 task_json 的 requester_id。
3. 產品邊長單位是 mm。
4. 頂部面積單位是 mm²。
5. 重量單位是 g。
6. 若沒有瑕疵，"瑕疵面積" 請填 null，"瑕疵種類" 請填 null。
7. 若有黑點、污點、異色、缺角、塊狀瑕疵，請填寫瑕疵面積與瑕疵種類。
8. 請根據 inspection_items 的 threshold 與 standard 判斷是否通過。
9. 如果所有項目都符合標準，"pass": true。
10. 如果任一項目不符合標準，"pass": false。
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=[
            prompt,
            Image.open(STANDARD_IMG),
            Image.open(TEST_IMG),
        ],
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


def normalize_result(result_json, task_json):
    result_json["產品"] = result_json.get("產品", task_json.get("product_name"))
    result_json["requester_id"] = result_json.get(
        "requester_id",
        task_json.get("requester_id")
    )

    result_json["產品邊長"] = float(result_json.get("產品邊長", 0.0))
    result_json["頂部面積"] = float(result_json.get("頂部面積", 0.0))
    result_json["重量"] = float(result_json.get("重量", 0.0))

    if result_json.get("瑕疵種類") is None:
        result_json["瑕疵面積"] = None
        result_json["瑕疵種類"] = None

    result_json["pass"] = bool(result_json.get("pass", False))

    return result_json


def send_to_other(result_json):
    print("\n準備回傳給對方:")
    print(json.dumps(result_json, indent=2, ensure_ascii=False))

    r = requests.post(
        OTHER_API_URL,
        json=result_json,
        timeout=10
    )

    print("Status Code:", r.status_code)
    print("Response:", r.text)


def workflow(task_json):
    global busy

    try:
        print("開始執行 scale policy")
        run_policy(POLICY_SCALE, "scale", seconds=200)

        print("拍攝測試圖")
        capture_test_image()

        print("Gemini 判斷")
        result_json = ask_gemini(task_json)
        result_json = normalize_result(result_json, task_json)

        print("Gemini 最終結果:")
        print(json.dumps(result_json, indent=2, ensure_ascii=False))

        if result_json["pass"]:
            print("判斷 PASS → 執行 OK policy")
            run_policy(POLICY_OK, "ok", seconds=200)
        else:
            print("判斷 FAIL → 執行 FAIL policy")
            run_policy(POLICY_FAIL, "fail", seconds=200)

        send_to_other(result_json)

    except Exception as e:
        print("流程錯誤:", e)

        error_json = {
            "產品": task_json.get("product_name"),
            "產品邊長": 0.0,
            "頂部面積": 0.0,
            "重量": 0.0,
            "瑕疵面積": 0.0,
            "瑕疵種類": "None",
            "pass": False,
            "requester_id": task_json.get("requester_id"),
            "error": str(e)
        }

        send_to_other(error_json)

    finally:
        busy = False


@app.post("/inspection_task")
async def inspection_task(request: Request):
    global busy

    task_json = await request.json()

    print("\n收到對方檢測任務:")
    print(json.dumps(task_json, indent=2, ensure_ascii=False))

    with open("received_task.json", "w", encoding="utf-8") as f:
        json.dump(task_json, f, indent=2, ensure_ascii=False)

    if busy:
        return {
            "status": "busy",
            "message": "robot is already running"
        }

    busy = True

    thread = threading.Thread(
        target=workflow,
        args=(task_json,)
    )
    thread.start()

    return {
        "status": "started",
        "message": "inspection task started",
        "product_name": task_json.get("product_name"),
        "requester_id": task_json.get("requester_id")
    }


@app.get("/")
def home():
    return {"status": "robot inspection api running"}
