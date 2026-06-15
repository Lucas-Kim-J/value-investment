"""Audio → text via Groq's hosted Whisper (OpenAI-compatible endpoint).

Groq runs whisper-large-v3(-turbo) on LPU hardware at ~200x realtime — an hour of
audio in ~15s — and its free tier (no card, ~2000 req/day) covers our volume. The
only wrinkle is a 25MB per-request cap, so long episodes are split with ffmpeg into
~10-min chunks, transcribed, and joined.

Pure orchestration (chunk-or-not, join) is unit-tested via injected `poster`/`splitter`;
the real HTTP (`_groq_post`, urllib multipart) and ffmpeg split (`_ffmpeg_split`) are
thin I/O, smoke-tested live. Any failure here propagates so FallbackTranscriber can
fall back to local faster-whisper.
"""
from __future__ import annotations

import glob
import os
import subprocess
import urllib.request
from pathlib import Path

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_MAX_BYTES = 24 * 1024 * 1024   # safety margin under Groq's 25MB cap
_CHUNK_SECONDS = 600            # ~10 min/chunk (well under 25MB at podcast bitrates)
_HTTP_TIMEOUT = 300
# Groq's API is behind Cloudflare, which 403s the default "Python-urllib" UA
# (CF error 1010). A normal browser/curl-style UA passes.
_UA = "Mozilla/5.0 (compatible; value-investment-pipeline/1.0)"


def _groq_post(path: Path, api_key: str, model: str, language: str = "zh") -> str:
    """POST one audio file to Groq; return the plain-text transcript (response_format=text)."""
    boundary = "----vi-groq-boundary-7r4nscr1b3"
    fields = {"model": model, "language": language, "response_format": "text", "temperature": "0"}
    body = bytearray()
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
             f"filename=\"{Path(path).name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
    body += Path(path).read_bytes()
    body += (f"\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(
        GROQ_URL, data=bytes(body), method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "User-Agent": _UA,
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as r:
        return r.read().decode("utf-8", "replace").strip()


def _ffmpeg_split(path: Path, seconds: int = _CHUNK_SECONDS) -> list[Path]:
    """Split audio into <=`seconds` chunks with ffmpeg (stream-copy, no re-encode)."""
    p = Path(path)
    stem = str(p.with_suffix(""))
    pattern = f"{stem}_chunk%03d{p.suffix}"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(p),
         "-f", "segment", "-segment_time", str(seconds), "-reset_timestamps", "1",
         "-c", "copy", pattern],
        check=True, timeout=_HTTP_TIMEOUT)
    return sorted(Path(x) for x in glob.glob(f"{stem}_chunk*{p.suffix}"))


class GroqTranscriber:
    """Same interface as Transcriber: transcribe(path) -> {"text", "segments"}."""

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 max_bytes: int = _MAX_BYTES, poster=None, splitter=None):
        self.api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY")
        # VI_GROQ_MODEL: 'whisper-large-v3' (max quality) or 'whisper-large-v3-turbo' (faster/cheaper)
        self.model = model or os.environ.get("VI_GROQ_MODEL", "whisper-large-v3-turbo")
        self.max_bytes = max_bytes
        self._post = poster or _groq_post
        self._split = splitter or _ffmpeg_split

    def transcribe(self, audio_path) -> dict:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        p = Path(audio_path)
        parts = [p] if p.stat().st_size <= self.max_bytes else list(self._split(p))
        texts = [self._post(part, self.api_key, self.model) for part in parts]
        return {"text": "".join(texts).strip(), "segments": []}
