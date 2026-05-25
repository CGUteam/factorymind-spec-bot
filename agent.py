import json
import os
import httpx

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL = "qwen2.5:7b"

SYSTEM_PROMPT = """你是工廠品管助理（OpenClaw Agent）。
將使用者的語音指令解析為 JSON 格式的檢查任務。
只輸出 JSON，不要任何其他文字或說明。

輸出格式：
{
  "product_name": "產品名稱",
  "inspection_items": [
    {
      "name": "檢查項目",
      "threshold": 0.8,
      "method": "vision_detection 或 manual"
    }
  ],
  "placement": {
    "pass": "正常區",
    "fail": "缺陷區"
  },
  "result": "pending"
}

規則：
- inspection_items name：使用最短的名詞，不加「檢查」、「檢測」等動詞後綴（例如：「重量」而非「重量檢查」，「外觀缺陷」而非「外觀缺陷檢查」）
- method：外觀、缺陷、尺寸、顏色 → vision_detection；其他 → manual
- placement：從語音中判斷合格放哪區、不合格放哪區；若未提及則預設 pass→正常區、fail→缺陷區
"""


def parse_command(text: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # 清理可能的 markdown code block
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    return json.loads(content)


def query_spec(product_name: str, inspection_items: list) -> dict:
    rag_url = os.getenv("RAG_URL")
    if not rag_url:
        return {}
    payload = {
        "product_name": product_name,
        "inspection_items": [i["name"] for i in inspection_items],
    }
    with httpx.Client(timeout=10) as client:
        resp = client.post(rag_url, json=payload)
        resp.raise_for_status()
    return resp.json()


def dispatch_robot(task: dict) -> bool:
    robot_url = os.getenv("ROBOT_URL")
    if not robot_url:
        return False
    with httpx.Client(timeout=10) as client:
        resp = client.post(robot_url, json=task)
        resp.raise_for_status()
    return True
