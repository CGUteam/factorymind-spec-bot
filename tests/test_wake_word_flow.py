"""測試語音文字移除喚醒詞 Marvin 後的處理流程。

這個檔案是可直接執行的測試腳本，不會真的呼叫 Ollama、RAG 或 Robot。
測試情境：假裝 ASR 收到語音文字「Marvin 請幫我檢查藍色產品的規格」。

執行方式：
    python tests/test_wake_word_flow.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path


def _install_linebot_stubs() -> None:
    """讓測試可以在未安裝 line-bot-sdk 的環境匯入 line_bot.py。"""
    linebot = types.ModuleType("linebot")
    linebot_v3 = types.ModuleType("linebot.v3")
    linebot_messaging = types.ModuleType("linebot.v3.messaging")
    linebot_webhooks = types.ModuleType("linebot.v3.webhooks")

    class WebhookHandler:
        def __init__(self, *_args, **_kwargs):
            pass

        def add(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    class _Dummy:
        def __init__(self, *_args, **kwargs):
            self.__dict__.update(kwargs)

    linebot_v3.WebhookHandler = WebhookHandler
    linebot_messaging.ApiClient = _Dummy
    linebot_messaging.Configuration = _Dummy
    linebot_messaging.MessagingApi = _Dummy
    linebot_messaging.ReplyMessageRequest = _Dummy
    linebot_messaging.PushMessageRequest = _Dummy
    linebot_messaging.TextMessage = _Dummy
    linebot_webhooks.MessageEvent = _Dummy
    linebot_webhooks.AudioMessageContent = _Dummy
    linebot_webhooks.TextMessageContent = _Dummy

    sys.modules.setdefault("linebot", linebot)
    sys.modules.setdefault("linebot.v3", linebot_v3)
    sys.modules.setdefault("linebot.v3.messaging", linebot_messaging)
    sys.modules.setdefault("linebot.v3.webhooks", linebot_webhooks)


def _install_asr_stubs() -> None:
    """讓測試可以在未安裝 faster-whisper 的環境匯入 asr.py。"""
    faster_whisper = types.ModuleType("faster_whisper")

    class WhisperModel:
        def __init__(self, *_args, **_kwargs):
            pass

    faster_whisper.WhisperModel = WhisperModel
    sys.modules.setdefault("faster_whisper", faster_whisper)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    _install_linebot_stubs()
    _install_asr_stubs()

    import line_bot

    raw_voice_text = "Marvin 請幫我檢查藍色產品的規格"
    cleaned_text = line_bot._remove_wake_word(raw_voice_text)

    print("=== Wake Word Flow Test ===")
    print(f"ASR 原始文字：{raw_voice_text}")
    print(f"清理後文字：{cleaned_text}")

    assert cleaned_text == "請幫我檢查藍色產品的規格"
    assert "Marvin" not in cleaned_text

    # Mock Agent / RAG / Robot，驗證後續流程收到的是清理後文字。
    parsed_inputs: list[str] = []
    dispatched_tasks: list[dict] = []

    def fake_parse_command(text: str) -> dict:
        parsed_inputs.append(text)
        return {
            "product_name": "藍色產品",
            "inspection_items": [{"name": "規格", "threshold": 0.8, "method": "manual"}],
            "placement": {"pass": "正常區", "fail": "缺陷區"},
            "result": "pending",
        }

    def fake_query_spec(product_name: str, inspection_items: list[dict]) -> dict:
        return {
            "product_found": True,
            "inspection_items": inspection_items,
        }

    def fake_dispatch_robot(task: dict) -> bool:
        dispatched_tasks.append(task)
        return True

    line_bot.agent.parse_command = fake_parse_command
    line_bot.agent.query_spec = fake_query_spec
    line_bot.agent.dispatch_robot = fake_dispatch_robot

    task = line_bot.agent.parse_command(cleaned_text)
    spec = line_bot.agent.query_spec(task["product_name"], task["inspection_items"])
    if spec.get("inspection_items"):
        task["inspection_items"] = spec["inspection_items"]
    robot_ok = line_bot.agent.dispatch_robot(task)

    assert parsed_inputs == ["請幫我檢查藍色產品的規格"]
    assert dispatched_tasks == [task]
    assert robot_ok is True

    print("Agent 收到文字：", parsed_inputs[0])
    print("Robot 任務：", task)
    print("測試通過：Marvin 已移除，後續流程使用清理後文字。")


if __name__ == "__main__":
    main()