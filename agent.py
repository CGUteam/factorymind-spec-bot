import json
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
  "result": "pending"
}

method 規則：
- 外觀、缺陷、尺寸、顏色 → vision_detection
- 其他 → manual
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
    with httpx.Client(timeout=30) as client:
        resp = client.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # 清理可能的 markdown code block
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    return json.loads(content)
