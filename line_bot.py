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

        _push(user_id, f"🎤 辨識：{text}")

        print("[Agent] parsing command...")
        task = agent.parse_command(text)
        print(f"[Agent] task: {task}")
        task_str = (
            f"📋 檢查任務：\n"
            f"產品：{task.get('product_name', '未知')}\n"
            f"項目：{', '.join(i['name'] for i in task.get('inspection_items', []))}\n"
            f"狀態：{task.get('result', 'pending')}"
        )
        _push(user_id, task_str)
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
        _messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(type="text", text="請傳送語音訊息進行辨識 🎤")],
            )
        )
