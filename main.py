import os
import queue
import tempfile
import threading
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Header, Request
from fastapi.responses import JSONResponse
from linebot.v3.exceptions import InvalidSignatureError
from pydantic import BaseModel

import asr
import agent
import line_bot
from app.command_parser import parse_command as parse_product_command
from app.product_retriever import retrieve_product
from app.rag_retriever import _ensure_product_embeddings

load_dotenv()

_esp32_queue: queue.Queue = queue.Queue()


def _esp32_worker():
    while True:
        job = _esp32_queue.get()
        try:
            tmp_path = job["path"]
            language = job["language"]
            notify_user_id = os.getenv("LINE_NOTIFY_USER_ID")

            asr_result = asr.transcribe(tmp_path, language=language)
            text = asr_result.get("text", "")
            if not text:
                print("[ESP32] 無法辨識語音")
                continue

            if notify_user_id:
                try:
                    line_bot.push(notify_user_id, f"🎤 {text}")
                except Exception as e:
                    print(f"[LINE] push failed: {e}")

            task = agent.parse_command(text)
            try:
                spec = agent.query_spec(task["product_name"], task["inspection_items"])
                if spec.get("product_found") and spec.get("inspection_items"):
                    task["inspection_items"] = spec["inspection_items"]
            except Exception as e:
                print(f"[RAG] failed: {e}")
            try:
                agent.dispatch_robot(task)
            except Exception as e:
                print(f"[Robot] dispatch failed: {e}")
        except Exception as e:
            print(f"[ESP32 Worker] error: {e}")
        finally:
            try:
                os.unlink(job["path"])
            except OSError:
                pass
            _esp32_queue.task_done()


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
    threading.Thread(target=_ensure_product_embeddings, daemon=True).start()
    threading.Thread(target=_esp32_worker, daemon=True).start()
    yield


app = FastAPI(title="OpenClaw ASR Service", lifespan=lifespan)


class QuerySpecRequest(BaseModel):
    product_name: str
    inspection_items: list[str]


DEFAULT_SPEC: dict[str, Any] = {
    "threshold": 0.80,
    "method": "vision_detection",
    "standard": "無明顯缺陷",
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query_spec")
def query_spec(req: QuerySpecRequest) -> dict[str, Any]:
    parsed = parse_product_command(req.product_name)
    retrieval = retrieve_product(req.product_name, parsed)

    if retrieval is None:
        product = None
        inspection_specs: dict[str, Any] = {}
    else:
        product = retrieval["product"]
        inspection_specs = product.get("inspection_specs", {})

    result = []
    for item_name in req.inspection_items:
        if item_name in inspection_specs:
            spec = inspection_specs[item_name]
            result.append({"name": item_name, **spec})
        else:
            # LLM 可能在項目名稱後加「檢查」等後綴，嘗試部分比對
            fuzzy = next(
                (spec for key, spec in inspection_specs.items() if key in item_name or item_name in key),
                None,
            )
            if fuzzy:
                result.append({"name": item_name, **fuzzy})
            else:
                result.append({"name": item_name, **DEFAULT_SPEC})

    product_found = product is not None
    resolved_name = product["product_name"] if product else req.product_name
    matched_by = retrieval["matched_by"] if retrieval else "not_found"
    print(f"[RAG] {resolved_name} ({matched_by}) → {[i['name'] for i in result]}")
    return {"product_name": resolved_name, "product_found": product_found, "inspection_items": result}


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
    """ESP32 音箱端點：音訊排隊處理，ASR → LINE push → Ollama → RAG → Robot"""
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    _esp32_queue.put({"path": tmp_path, "language": language})
    return JSONResponse({"status": "queued", "queue_size": _esp32_queue.qsize()})


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
