"""Audio → text via faster-whisper. Lazy import (heavy model) + a 'mock' mode
so local dev / tests never need the model. Set VI_WHISPER_MODE=mock to mock."""
from __future__ import annotations

import os
from pathlib import Path


def segments_to_text(segments) -> tuple[str, list[dict]]:
    """Join whisper segments into full text + a cleaned [{start,end,text}] list."""
    stamped = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()}
               for s in segments]
    text = "".join(s["text"] for s in stamped)
    return text, stamped


class Transcriber:
    def __init__(self, mode: str | None = None, model_name: str = "large-v3"):
        self.mode = mode or os.environ.get("VI_WHISPER_MODE", "whisper")
        self.model_name = model_name

    def transcribe(self, audio_path) -> dict:
        if self.mode == "mock":
            return {"text": "（mock 转录占位文本）", "segments": [
                {"start": 0.0, "end": 1.0, "text": "（mock 转录占位文本）"}]}
        from faster_whisper import WhisperModel  # lazy: heavy
        model = WhisperModel(self.model_name, device="auto", compute_type="auto")
        segments, _info = model.transcribe(str(Path(audio_path)), language="zh")
        seg_dicts = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        text, stamped = segments_to_text(seg_dicts)
        return {"text": text, "segments": stamped}
