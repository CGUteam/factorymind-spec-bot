import os
import tempfile
import threading
import httpx
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, AudioMessageContent, TextMessageContent

import asr
import agent

_handler = None
_messaging_api = None


def init(channel_secret: str, channel_access_token: str) -> None:
    global _handler, _messaging_api
    _handler = WebhookHandler(channel_secret)
    config = Configuration(access_token=channel_access_token)
    _messaging_api = MessagingApi(ApiClient(config))
    _register_handlers()


def get_handler() -> WebhookHandler:
    return _handler


def push(user_id: str, text: str) -> None:
    _messaging_api.push_message(
        PushMessageRequest(
            to=user_id,
            messages=[TextMessage(type="text", text=text)],
        )
    )

# 內部別名
_push = push


def _download_audio(message_id: str, token: str) -> str:
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client() as client:
        resp = client.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(resp.content)
        return f.name


def _process_text(user_id: str, text: str) -> None:
    try:
        print(f"[Text] user={user_id} text={text}")

        # Agent 解析指令
        task = agent.parse_command(text)
        print(f"[Agent] task: {task}")

        # 查 RAG
        try:
            spec = agent.query_spec(task["product_name"], task["inspection_items"])
            if spec.get("inspection_items"):
                task["inspection_items"] = spec["inspection_items"]
                spec_items = spec["inspection_items"]
                spec_str = "\n".join(
                    f"  • {i['name']}：門檻 {i.get('threshold', 0.8)}｜{i.get('standard', '')}"
                    for i in spec_items
                )
                _push(user_id, f"🔍 Spec 查詢（RAG）：\n產品：{task.get('product_name')}\n{spec_str}")
        except Exception as e:
            print(f"[RAG] failed: {e}")

        items = task.get("inspection_items", [])
        task_str = (
            f"📋 檢查任務（Ollama + Qwen2.5:7b）：\n"
            f"產品：{task.get('product_name', '未知')}\n"
            f"項目：{', '.join(i['name'] for i in items)}\n"
            f"狀態：派送中..."
        )
        _push(user_id, task_str)

        # 派送給 Robot
        try:
            agent.dispatch_robot(task)
        except Exception as e:
            print(f"[Robot] dispatch failed: {e}")
            _push(user_id, f"⚠️ Robot 派送失敗：{e}")
    except Exception as e:
        print(f"[Text] ERROR: {e}")
        _push(user_id, f"處理失敗：{e}")


def _process_audio(user_id: str, message_id: str, token: str) -> None:
    try:
        print(f"[ASR] user={user_id} msg={message_id} downloading...")
        audio_path = _download_audio(message_id, token)
        print(f"[ASR] transcribing {audio_path}")
        result = asr.transcribe(audio_path)
        os.unlink(audio_path)
        text = result["text"] or ""
        print(f"[ASR] result: {text}")

        if not text:
            _push(user_id, "（無法辨識，請再說一次）")
            return

        _push(user_id, f"🎤 辨識（faster-whisper）：\n{text}")

        # Agent 解析指令
        print("[Agent] parsing command...")
        task = agent.parse_command(text)
        print(f"[Agent] task: {task}")

        # 查 RAG 取得正確 Spec
        try:
            spec = agent.query_spec(task["product_name"], task["inspection_items"])
            if spec.get("inspection_items"):
                task["inspection_items"] = spec["inspection_items"]
                spec_items = spec["inspection_items"]
                spec_str = "\n".join(
                    f"  • {i['name']}：門檻 {i.get('threshold', 0.8)}｜{i.get('standard', '')}"
                    for i in spec_items
                )
                _push(user_id, f"🔍 Spec 查詢（RAG）：\n產品：{task.get('product_name')}\n{spec_str}")
            print(f"[RAG] spec: {spec}")
        except Exception as e:
            print(f"[RAG] failed: {e}")

        items = task.get("inspection_items", [])
        task_str = (
            f"📋 檢查任務（Ollama + Qwen2.5:7b）：\n"
            f"產品：{task.get('product_name', '未知')}\n"
            f"項目：{', '.join(i['name'] for i in items)}\n"
            f"狀態：派送中..."
        )
        _push(user_id, task_str)

        # 派送給 Robot
        try:
            agent.dispatch_robot(task)
            print("[Robot] task dispatched")
        except Exception as e:
            print(f"[Robot] dispatch failed: {e}")
            _push(user_id, f"⚠️ Robot 派送失敗：{e}")
        print("[ASR] push sent")
    except Exception as e:
        print(f"[ASR] ERROR: {e}")
        try:
            _push(user_id, f"辨識失敗：{e}")
        except Exception as e2:
            print(f"[ASR] push failed: {e2}")


def _register_handlers() -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

    @_handler.add(MessageEvent, message=AudioMessageContent)
    def handle_audio(event: MessageEvent) -> None:
        # 立刻返回，背景執行 ASR 避免 LINE 5 秒 timeout
        threading.Thread(
            target=_process_audio,
            args=(event.source.user_id, event.message.id, token),
            daemon=True,
        ).start()

    @_handler.add(MessageEvent, message=TextMessageContent)
    def handle_text(event: MessageEvent) -> None:
        text = event.message.text.strip()
        # 立刻回覆，背景處理避免 timeout
        _messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(type="text", text=f"📝 收到指令：{text}\n處理中...")],
            )
        )
        threading.Thread(
            target=_process_text,
            args=(event.source.user_id, text),
            daemon=True,
        ).start()
