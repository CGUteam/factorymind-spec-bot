import os
import json
from PIL import Image
from google import genai

# =========================
# 圖片
# =========================
STANDARD_IMG = "Image.jpg"
TEST_IMG = "test.jpg"

# =========================
# Gemini
# =========================
client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

# =========================
# 從 JSON 檔讀取
# =========================
with open(
    "received_task.json",
    "r",
    encoding="utf-8"
) as f:

    task_json = json.load(f)

# =========================
# Prompt
# =========================
prompt = f"""
你會收到一份已知物理資訊任務 JSON，以及標準圖與測試圖。
請根據檢測任務內容、標準圖、測試圖進行判斷。

檢測任務 JSON：
{json.dumps(task_json, ensure_ascii=False, indent=2)}

請只輸出 JSON。
不要 markdown。
不要解釋。
不要多餘文字。

JSON Schema:

{{
 "產品": string,
 "產品邊長": float,
 "頂部面積": float,
 "重量": float,
 "瑕疵面積": float or null,
 "瑕疵種類": string or null,
 "pass": true or false,
 "requester_id": "U123456"
}}
"""

# =========================
# Gemini
# =========================
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=[
        prompt,
        Image.open(STANDARD_IMG),
        Image.open(TEST_IMG),
    ],
)

text = response.text.strip()
text = text.replace("```json", "")
text = text.replace("```", "")
text = text.strip()

print("\nGemini 原始輸出:\n")
print(text)

# =========================
# Parse JSON
# =========================
try:

    result = json.loads(text)

    print("\nJSON 解析成功:\n")

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False
    ))

except Exception as e:

    print("\nJSON 解析失敗:")
    print(e)
