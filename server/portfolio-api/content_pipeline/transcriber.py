"""Audio → text via faster-whisper. Lazy import (heavy model) + a 'mock' mode
so local dev / tests never need the model. Set VI_WHISPER_MODE=mock to mock,
and VI_WHISPER_MODEL to pick the model size (default large-v3; prod uses medium)."""
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
    def __init__(self, mode: str | None = None, model_name: str | None = None):
        self.mode = mode or os.environ.get("VI_WHISPER_MODE", "whisper")
        self.model_name = model_name or os.environ.get("VI_WHISPER_MODEL", "large-v3")

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


class FallbackTranscriber:
    """Try `primary`; on ANY failure (rate limit / quota / payment / network / error)
    fall back to `fallback`. Lets us run Groq with local faster-whisper as the safety net."""

    def __init__(self, primary, fallback, log=print):
        self.primary = primary
        self.fallback = fallback
        self._log = log

    def transcribe(self, audio_path) -> dict:
        try:
            return self.primary.transcribe(audio_path)
        except Exception as e:  # noqa: BLE001 — any primary failure → local fallback
            self._log(f"[transcriber] primary failed ({str(e)[:140]}); falling back to local")
            return self.fallback.transcribe(audio_path)


def make_transcriber():
    """Pick the transcriber from VI_TRANSCRIBER: 'mock' | 'groq' | 'local' (default).
    'groq' = Groq primary with local faster-whisper as automatic fallback."""
    mode = os.environ.get("VI_TRANSCRIBER", "local").lower()
    if mode == "mock":
        return Transcriber(mode="mock")
    if mode == "groq":
        from content_pipeline.groq_transcriber import GroqTranscriber  # lazy: keep base import light
        return FallbackTranscriber(GroqTranscriber(), Transcriber())
    return Transcriber()
