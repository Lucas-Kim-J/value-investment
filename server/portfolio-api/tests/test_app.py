import app


def test_fernet_secret_roundtrip():
    """Exchange API secrets are Fernet-encrypted at rest; decrypt must recover the plaintext."""
    assert app._dec_secret(app._enc_secret("s3cr3t-key")) == "s3cr3t-key"


def test_slugify_lowercases_and_dashes_non_alnum():
    assert app._slugify("Hello World! 测试") == "hello-world-测试"


def test_signal_row_to_dict_shapes_card_meta_no_transcript():
    row = {"external_id": "e1", "source": "xiaoyuzhou", "show_title": "非共识的20分钟",
           "image_url": "http://img/x.jpg", "title": "Ep 7", "url": "http://u",
           "published_at": None, "signal_card": {"tldr": "t", "pillar": "资金传导"}}
    d = app._signal_row_to_dict(row)
    assert d["card"]["pillar"] == "资金传导"
    assert d["show_title"] == "非共识的20分钟"
    assert d["image_url"] == "http://img/x.jpg"
    assert "transcript" not in d


def test_signal_row_to_dict_parses_str_card_and_includes_transcript():
    row = {"external_id": "e1", "signal_card": '{"tldr": "t"}', "transcript": "全文",
           "published_at": None}
    d = app._signal_row_to_dict(row, include_transcript=True)
    assert d["card"]["tldr"] == "t"
    assert d["transcript"] == "全文"


def test_signals_endpoints_require_login():
    client = app.app.test_client()
    assert client.get("/api/signals").status_code == 401
    assert client.get("/api/signals/anything").status_code == 401
