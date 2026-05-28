from faster_whisper import WhisperModel

_model: WhisperModel | None = None

# 刻意短，避免 Whisper 把 prompt 當辨識結果輸出
MIXED_PROMPT = "品管指令"

# 常見 hallucination 片段，出現即視為無效辨識
_HALLUCINATION_FRAGMENTS = [
    "以下是中英文",
    "專業術語",
    "英文單字",
    "中英文語",
    "感謝您的",
    "請訂閱",
]


def load_model(model_size: str = "small", device: str = "cpu", compute_type: str = "int8") -> None:
    global _model
    print(f"Loading Whisper model: {model_size} ({device}, {compute_type})")
    _model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print("Model ready.")


def _is_hallucination(text: str) -> bool:
    return any(frag in text for frag in _HALLUCINATION_FRAGMENTS)


def transcribe(audio_path: str, language: str | None = None) -> dict:
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    segments_iter, info = _model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        initial_prompt=MIXED_PROMPT,
        # vad_filter 在 Jetson ARM 上會讓 onnxruntime crash，停用
    )

    segments = list(segments_iter)
    text = "".join(seg.text for seg in segments).strip()

    # 若平均無語音機率 > 0.6 或偵測到 prompt hallucination，視為空白
    if segments:
        avg_no_speech = sum(s.no_speech_prob for s in segments) / len(segments)
        if avg_no_speech > 0.6:
            print(f"[ASR] 疑似無語音（avg_no_speech={avg_no_speech:.2f}），丟棄")
            text = ""

    if text and _is_hallucination(text):
        print(f"[ASR] 偵測到 hallucination，丟棄：{text!r}")
        text = ""

    return {
        "text": text,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
    }
