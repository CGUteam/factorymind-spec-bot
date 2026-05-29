from fastapi import FastAPI
from pydantic import BaseModel
import requests
import threading
import time

app = FastAPI()
busy = False

# 對方 Orin API
OTHER_API_RESULT_URL = "http://192.168.2.55:8000/result"

# 你的 Orin IP
MY_API_URL = "http://192.168.1.194:8000/inspect"


class InspectRequest(BaseModel):
    command: str = "inspect"
    task_id: str | None = None


def send_result_to_other(task_id, status, result):
    payload = {
        "task_id": task_id,
        "status": status,
        "result": result,
    }

    print("準備回傳給對方:", payload)

    try:
        r = requests.post(
            OTHER_API_RESULT_URL,
            json=payload,
            timeout=10
        )
        print("對方回應:", r.status_code, r.text)

    except Exception as e:
        print("回傳對方失敗:", e)


def robot_workflow(command, task_id):
    global busy

    try:
        print("收到對方命令:", command)
        print("task_id:", task_id)

        # 先測 API，不動 robot
        print("模擬執行 scale policy")
        time.sleep(2)

        print("模擬 camera 拍照")
        time.sleep(1)

        print("模擬 Gemini 判斷")
        time.sleep(1)

        gemini_result = {
            "產品": "大方塊",
            "產品邊長": 2.8,
            "頂部面積": 7.84,
            "重量": 12.3,
            "瑕疵面積": None,
            "瑕疵種類": None,
        }

        if gemini_result["瑕疵種類"] is None:
            action = "ok"
            print("判斷：無瑕疵，動作 = ok")
        else:
            action = "fail"
            print("判斷：有瑕疵，動作 = fail")

        send_result_to_other(
            task_id=task_id,
            status="done",
            result={
                "action": action,
                "gemini_result": gemini_result,
            }
        )

    except Exception as e:
        print("流程錯誤:", e)
        send_result_to_other(
            task_id=task_id,
            status="error",
            result={"message": str(e)}
        )

    finally:
        busy = False


@app.post("/inspect")
def inspect(req: InspectRequest):
    global busy

    if busy:
        return {
            "status": "busy",
            "message": "robot is already running"
        }

    busy = True

    thread = threading.Thread(
        target=robot_workflow,
        args=(req.command, req.task_id)
    )
    thread.start()

    return {
        "status": "started",
        "command": req.command,
        "task_id": req.task_id
    }


@app.get("/")
def home():
    return {
        "status": "robot api running",
        "my_api": MY_API_URL,
        "other_result_api": OTHER_API_RESULT_URL,
    }
