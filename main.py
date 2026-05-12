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
    傳入音訊 → ASR 辨識 → Agent 解析 → 回傳結構化任務 JSON。
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

    return JSONResponse({
        "text": text,
        "language": asr_result.get("language"),
        "task": task,
    })


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
