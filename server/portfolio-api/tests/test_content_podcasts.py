from content_pipeline import podcasts


def test_default_podcast_ids_include_the_three_columns(monkeypatch):
    monkeypatch.delenv("VI_PIPELINE_PODCAST_IDS", raising=False)
    monkeypatch.delenv("VI_PIPELINE_PODCAST_ID", raising=False)
    ids = podcasts.podcast_ids()
    assert "6978a31df828d4e9f2787d3d" in ids        # 非共识的20分钟
    assert "626b46ea9cbbf0451cf5a962" in ids        # 张小珺Jùn｜商业访谈录
    assert "65539db173f6183e975cfccc" in ids        # The Wanderers 流浪者
    assert len(ids) == 3


def test_env_override_is_comma_separated_and_trimmed(monkeypatch):
    monkeypatch.setenv("VI_PIPELINE_PODCAST_IDS", " a , b ,, c ")
    assert podcasts.podcast_ids() == ["a", "b", "c"]


def test_legacy_singular_env_still_honoured(monkeypatch):
    monkeypatch.delenv("VI_PIPELINE_PODCAST_IDS", raising=False)
    monkeypatch.setenv("VI_PIPELINE_PODCAST_ID", "solo")
    assert podcasts.podcast_ids() == ["solo"]


def test_plural_env_wins_over_singular(monkeypatch):
    monkeypatch.setenv("VI_PIPELINE_PODCAST_IDS", "x,y")
    monkeypatch.setenv("VI_PIPELINE_PODCAST_ID", "solo")
    assert podcasts.podcast_ids() == ["x", "y"]
