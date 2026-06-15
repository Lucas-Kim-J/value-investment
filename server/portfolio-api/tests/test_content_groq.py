import pytest

from content_pipeline.transcriber import FallbackTranscriber, Transcriber, make_transcriber
from content_pipeline.groq_transcriber import GroqTranscriber


# ---- FallbackTranscriber ----

class _OK:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def transcribe(self, p):
        self.calls += 1
        return {"text": self.text, "segments": []}


class _Boom:
    def __init__(self):
        self.calls = 0

    def transcribe(self, p):
        self.calls += 1
        raise RuntimeError("groq 429 rate limit")


def test_fallback_uses_primary_when_ok():
    prim, fb = _OK("groq-text"), _OK("local-text")
    out = FallbackTranscriber(prim, fb, log=lambda *_: None).transcribe("a.m4a")
    assert out["text"] == "groq-text"
    assert fb.calls == 0


def test_fallback_switches_to_local_on_any_primary_error():
    prim, fb = _Boom(), _OK("local-text")
    out = FallbackTranscriber(prim, fb, log=lambda *_: None).transcribe("a.m4a")
    assert out["text"] == "local-text"
    assert prim.calls == 1 and fb.calls == 1


# ---- make_transcriber factory ----

def test_make_transcriber_mock(monkeypatch):
    monkeypatch.setenv("VI_TRANSCRIBER", "mock")
    t = make_transcriber()
    assert isinstance(t, Transcriber) and t.mode == "mock"


def test_make_transcriber_defaults_local(monkeypatch):
    monkeypatch.delenv("VI_TRANSCRIBER", raising=False)
    assert isinstance(make_transcriber(), Transcriber)


def test_make_transcriber_groq_wraps_local_fallback(monkeypatch):
    monkeypatch.setenv("VI_TRANSCRIBER", "groq")
    t = make_transcriber()
    assert isinstance(t, FallbackTranscriber)
    assert isinstance(t.primary, GroqTranscriber)
    assert isinstance(t.fallback, Transcriber)


# ---- GroqTranscriber chunk orchestration (injected I/O) ----

def _write(tmp_path, name, n):
    f = tmp_path / name
    f.write_bytes(b"x" * n)
    return f


def test_groq_single_request_when_under_cap(tmp_path):
    f = _write(tmp_path, "a.m4a", 5)
    posts = []

    def no_split(_):
        raise AssertionError("should not split a small file")

    g = GroqTranscriber(api_key="k", max_bytes=100,
                        poster=lambda p, k, m: (posts.append(p) or "hello "),
                        splitter=no_split)
    out = g.transcribe(f)
    assert out["text"] == "hello"
    assert len(posts) == 1


def test_groq_chunks_when_over_cap_and_joins(tmp_path):
    f = _write(tmp_path, "a.m4a", 50)
    c1, c2 = _write(tmp_path, "a_chunk000.m4a", 5), _write(tmp_path, "a_chunk001.m4a", 5)
    posts = []
    g = GroqTranscriber(api_key="k", max_bytes=10,
                        poster=lambda p, k, m: (posts.append(p.name) or f"[{p.name}]"),
                        splitter=lambda p: [c1, c2])
    out = g.transcribe(f)
    assert posts == ["a_chunk000.m4a", "a_chunk001.m4a"]
    assert out["text"] == "[a_chunk000.m4a][a_chunk001.m4a]"


def test_groq_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    f = _write(tmp_path, "a.m4a", 5)
    with pytest.raises(RuntimeError):
        GroqTranscriber(api_key=None).transcribe(f)
