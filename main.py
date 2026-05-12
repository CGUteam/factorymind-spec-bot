import os
import tempfile
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Header, Request
from fastapi.responses import JSONResponse
from linebot.v3.exceptions import InvalidSignatureError

import asr
import agent
import line_bot

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    asr.load_model(
        model_size=os.getenv("WHISPER_MODEL", "small"),
        device=os.getenv("WHISPER_DEVICE", "cpu"),
        compute_type=os.getenv("WHISPER_COMPUTE", "int8"),
    )
    line_bot.init(
        channel_secret=os.getenv("LINE_CHANNEL_SECRET", ""),
        channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""),
    )
    yield


app = FastAPI(title="OpenClaw ASR Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default="zh"),
):
    allowed = {"audio/wav", "audio/wave", "audio/x-wav", "audio/webm",
               "audio/ogg", "audio/flac", "audio/mpeg"}
    if file.content_type and file.content_type not in allowed:
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {file.content_type}")

    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = asr.transcribe(tmp_path, language=language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)

    return JSONResponse(result)


@app.post("/process")
async def process(
    file: UploadFile = File(...),
    language: str = Form(default=None),
):
    """
    ESP32 智慧音箱使用的整合端點。
    傳入音訊 → ASR 辨識 → Agent 解析 → 回傳 JSON 並推 LINE 通知。
    """
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        asr_result = asr.transcribe(tmp_path, language=language)
        text = asr_result.get("text", "")
        if not text:
            return JSONResponse({"text": "", "task": None, "error": "無法辨識語音"})
        task = agent.parse_command(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)

    # 推 LINE 通知給使用者
    notify_user_id = os.getenv("LINE_NOTIFY_USER_ID")
    if notify_user_id:
        items = task.get("inspection_items", [])
        item_names = ", ".join(i["name"] for i in items)
        msg = (
            f"📡 ESP32 語音指令\n"
            f"🎤 辨識（faster-whisper）：{text}\n\n"
            f"📋 檢查任務（Ollama + Qwen2.5:7b）：\n"
            f"產品：{task.get('product_name', '未知')}\n"
            f"項目：{item_names}\n"
            f"狀態：{task.get('result', 'pending')}"
        )
        try:
            line_bot.push(notify_user_id, msg)
        except Exception as e:
            print(f"[LINE] push failed: {e}")

    return JSONResponse({
        "text": text,
        "language": asr_result.get("language"),
        "task": task,
    })


@app.post("/inspection_result")
async def inspection_result(request: Request):
    """Robot 執行完畢後回傳結果，推 LINE 報告"""
    data = await request.json()
    product_name = data.get("product_name", "未知")
    result       = data.get("result", "unknown")
    items        = data.get("inspection_items", [])

    result_icon = "✅" if result == "pass" else "❌"
    placed_in   = data.get("placed_in") or ("正常區" if result == "pass" else "缺陷區")
    items_str = "\n".join(
        f"  {'✅' if i.get('pass') else '❌'} {i['name']}：{i.get('score', 0):.2f} "
        f"（門檻 {i.get('threshold', 0.8):.2f}）"
        for i in items
    )
    msg = (
        f"📊 品管報告（SO-101 Robot）：\n"
        f"產品：{product_name}\n"
        f"結果：{result_icon} {'PASS' if result == 'pass' else 'FAIL'}\n"
        f"放置：📦 {placed_in}\n\n"
        f"檢查明細：\n{items_str}"
    )

    notify_user_id = os.getenv("LINE_NOTIFY_USER_ID")
    if notify_user_id:
        try:
            line_bot.push(notify_user_id, msg)
        except Exception as e:
            print(f"[LINE] push failed: {e}")

    print(f"[Result] {product_name}: {result}")
    return {"status": "ok"}


@app.post("/line/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(...),
):
    body = await request.body()
    try:
        line_bot.get_handler().handle(body.decode("utf-8"), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"
