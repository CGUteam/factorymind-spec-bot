from faster_whisper import WhisperModel

_model: WhisperModel | None = None


def load_model(model_size: str = "small", device: str = "cpu", compute_type: str = "int8") -> None:
    global _model
    print(f"Loading Whisper model: {model_size} ({device}, {compute_type})")
    _model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print("Model ready.")


MIXED_PROMPT = "以下是中英文混合的對話，包含專業術語和英文單字。"


def transcribe(audio_path: str, language: str | None = None) -> dict:
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    segments, info = _model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        initial_prompt=MIXED_PROMPT,
        # vad_filter 在 Jetson ARM 上會讓 onnxruntime crash，停用
    )
    text = "".join(seg.text for seg in segments).strip()

    return {
        "text": text,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
    }
