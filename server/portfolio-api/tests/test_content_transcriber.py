from content_pipeline.transcriber import segments_to_text, Transcriber


def test_segments_to_text_joins_with_timestamps():
    segs = [{"start": 0.0, "end": 2.0, "text": " 你好"}, {"start": 2.0, "end": 4.0, "text": "世界 "}]
    text, stamped = segments_to_text(segs)
    assert text == "你好世界"
    assert stamped[0]["start"] == 0.0
    assert stamped[0]["text"] == "你好"


def test_transcriber_mock_mode_returns_placeholder(tmp_path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"x")
    t = Transcriber(mode="mock")
    out = t.transcribe(f)
    assert "text" in out and "segments" in out
    assert out["text"]  # non-empty placeholder
