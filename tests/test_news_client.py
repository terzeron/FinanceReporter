"""뉴스 RSS 피드 수집 클라이언트 테스트."""

import json
from unittest.mock import MagicMock, patch

import pytest

from news.client import FEEDS_MAP, NewsFetcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    title="Test Title",
    summary="Test summary text",
    link="https://example.com/article",
    published_parsed=(2024, 1, 2, 0, 0, 0, 0, 0, 0),
):
    """feedparser entry 모의 객체."""
    entry = MagicMock()
    entry.title = title
    entry.summary = summary
    entry.link = link
    entry.published_parsed = published_parsed
    return entry


def _make_feed(entries):
    """feedparser feed 모의 객체."""
    feed = MagicMock()
    feed.entries = entries
    return feed


@pytest.fixture
def fetcher():
    return NewsFetcher()


# ---------------------------------------------------------------------------
# FEEDS_MAP 검증
# ---------------------------------------------------------------------------


class TestFeedsMap:
    def test_contains_required_sources(self):
        """필수 소스가 정의되어 있는지 확인."""
        sources = {info["source"] for info in FEEDS_MAP.values()}
        assert "Reuters" in sources
        assert "Bloomberg" in sources
        assert "CNBC" in sources
        assert "Yahoo Finance" in sources

    def test_each_entry_has_required_fields(self):
        """각 항목에 url, source가 있는지 확인."""
        for feed_id, info in FEEDS_MAP.items():
            assert "url" in info, f"{feed_id} missing url"
            assert "source" in info, f"{feed_id} missing source"
            assert info["url"].startswith("https://"), f"{feed_id} url must be https"


# ---------------------------------------------------------------------------
# fetch_feed
# ---------------------------------------------------------------------------


class TestFetchFeed:
    @patch("news.client.feedparser.parse")
    def test_returns_articles_list(self, mock_parse, fetcher):
        """피드에서 기사 리스트 반환."""
        mock_parse.return_value = _make_feed([_make_entry()])
        result = fetcher.fetch_feed("reuters")
        assert isinstance(result, list)
        assert len(result) == 1

    @patch("news.client.feedparser.parse")
    def test_article_has_required_fields(self, mock_parse, fetcher):
        """기사 dict에 필수 필드가 있는지 확인."""
        mock_parse.return_value = _make_feed([_make_entry()])
        result = fetcher.fetch_feed("reuters")
        article = result[0]
        for field in ("source", "title", "summary", "text", "url", "published"):
            assert field in article, f"missing field: {field}"

    @patch("news.client.feedparser.parse")
    def test_source_matches_feeds_map(self, mock_parse, fetcher):
        """source가 FEEDS_MAP의 값과 일치."""
        mock_parse.return_value = _make_feed([_make_entry()])
        result = fetcher.fetch_feed("reuters")
        assert result[0]["source"] == FEEDS_MAP["reuters"]["source"]

    @patch("news.client.feedparser.parse")
    def test_limits_to_max_per_source(self, mock_parse, fetcher):
        """MAX_PER_SOURCE 이상 기사를 반환하지 않는다."""
        from news.client import MAX_PER_SOURCE

        entries = [_make_entry() for _ in range(10)]
        mock_parse.return_value = _make_feed(entries)
        result = fetcher.fetch_feed("reuters")
        assert len(result) <= MAX_PER_SOURCE

    @patch("news.client.feedparser.parse")
    def test_empty_feed_returns_empty_list(self, mock_parse, fetcher):
        """빈 피드는 빈 리스트를 반환."""
        mock_parse.return_value = _make_feed([])
        result = fetcher.fetch_feed("reuters")
        assert result == []

    @patch("news.client.feedparser.parse")
    def test_published_date_parsed(self, mock_parse, fetcher):
        """published_parsed가 YYYY-MM-DD 형식으로 변환."""
        entry = _make_entry(published_parsed=(2024, 3, 15, 10, 30, 0, 0, 0, 0))
        mock_parse.return_value = _make_feed([entry])
        result = fetcher.fetch_feed("reuters")
        assert result[0]["published"] == "2024-03-15"

    @patch("news.client.feedparser.parse")
    def test_html_tags_stripped_from_summary(self, mock_parse, fetcher):
        """summary의 HTML 태그가 제거된다."""
        entry = _make_entry(summary="<b>Breaking:</b> <p>Market falls</p>")
        mock_parse.return_value = _make_feed([entry])
        result = fetcher.fetch_feed("reuters")
        assert "<b>" not in result[0]["summary"]
        assert "<p>" not in result[0]["summary"]

    def test_unknown_feed_id_raises(self, fetcher):
        """FEEDS_MAP에 없는 feed_id → KeyError."""
        with pytest.raises(KeyError):
            fetcher.fetch_feed("nonexistent")


# ---------------------------------------------------------------------------
# fetch_article_text
# ---------------------------------------------------------------------------


class TestFetchArticleText:
    @patch("news.client.requests.get")
    def test_returns_text_from_article_tag(self, mock_get, fetcher):
        """<article> 태그에서 텍스트 추출."""
        content = "Article content here with enough text to qualify."
        mock_get.return_value.text = (
            f"<html><body><article><p>{content}</p></article></body></html>"
        )
        mock_get.return_value.raise_for_status = MagicMock()
        result = fetcher.fetch_article_text("https://example.com/a")
        assert result is not None
        assert "Article content" in result

    @patch("news.client.requests.get")
    def test_fallback_to_p_tags(self, mock_get, fetcher):
        """<article> 없으면 <p> 태그에서 추출."""
        long_p = "This is a sufficiently long paragraph to pass the eighty character filter condition."
        mock_get.return_value.text = f"<html><body><p>{long_p}</p></body></html>"
        mock_get.return_value.raise_for_status = MagicMock()
        result = fetcher.fetch_article_text("https://example.com/a")
        assert result is not None

    @patch("news.client.requests.get")
    def test_returns_none_on_request_failure(self, mock_get, fetcher):
        """요청 실패 시 None 반환."""
        mock_get.side_effect = Exception("Connection error")
        result = fetcher.fetch_article_text("https://example.com/a")
        assert result is None

    @patch("news.client.requests.get")
    def test_text_capped_at_max_chars(self, mock_get, fetcher):
        """텍스트가 ARTICLE_MAX_CHARS를 초과하지 않는다."""
        from news.client import ARTICLE_MAX_CHARS

        long_text = "x" * 1000
        mock_get.return_value.text = (
            f"<html><body><article><p>{long_text}</p></article></body></html>"
        )
        mock_get.return_value.raise_for_status = MagicMock()
        result = fetcher.fetch_article_text("https://example.com/a")
        assert result is not None
        assert len(result) <= ARTICLE_MAX_CHARS

    @patch("news.client.requests.get")
    def test_returns_none_on_empty_content(self, mock_get, fetcher):
        """빈 HTML에서 None 반환."""
        mock_get.return_value.text = "<html><body></body></html>"
        mock_get.return_value.raise_for_status = MagicMock()
        result = fetcher.fetch_article_text("https://example.com/a")
        assert result is None


# ---------------------------------------------------------------------------
# fetch_all
# ---------------------------------------------------------------------------


class TestFetchAll:
    @patch("news.client.requests.get")
    @patch("news.client.feedparser.parse")
    def test_returns_articles_from_sources(self, mock_parse, mock_get, fetcher):
        """소스에서 기사를 수집."""
        mock_parse.return_value = _make_feed([_make_entry()])
        mock_get.return_value.text = (
            "<html><body><article>"
            "<p>Article text long enough to pass the filter.</p>"
            "</article></body></html>"
        )
        mock_get.return_value.raise_for_status = MagicMock()
        result = fetcher.fetch_all()
        assert len(result) > 0

    @patch("news.client.requests.get")
    @patch("news.client.feedparser.parse")
    def test_saves_to_cache(self, mock_parse, mock_get, fetcher, tmp_path):
        """data_dir 지정 시 news.json 저장."""
        mock_parse.return_value = _make_feed([_make_entry()])
        mock_get.return_value.text = (
            "<html><body><article><p>content</p></article></body></html>"
        )
        mock_get.return_value.raise_for_status = MagicMock()
        fetcher.fetch_all(data_dir=tmp_path)
        assert (tmp_path / "news.json").exists()

    @patch("news.client.feedparser.parse")
    def test_uses_cache(self, mock_parse, fetcher, tmp_path):
        """캐시 유효 시 feedparser 호출 안 함."""
        cached_data = {"articles": [{"source": "Reuters", "title": "cached article"}]}
        (tmp_path / "news.json").write_text(json.dumps(cached_data))
        result = fetcher.fetch_all(data_dir=tmp_path, fetch_text=False)
        mock_parse.assert_not_called()
        assert result[0]["source"] == "Reuters"

    @patch("news.client.feedparser.parse")
    def test_continues_on_feed_failure(self, mock_parse, fetcher):
        """피드 수집 실패 시 건너뛰고 계속 진행."""
        mock_parse.side_effect = Exception("Network error")
        result = fetcher.fetch_all(fetch_text=False)
        assert isinstance(result, list)

    @patch("news.client.feedparser.parse")
    def test_fetch_text_false_skips_article_fetch(self, mock_parse, fetcher):
        """fetch_text=False 시 기사 본문 추가 수집 안 함."""
        mock_parse.return_value = _make_feed([_make_entry()])
        with patch.object(fetcher, "fetch_article_text") as mock_text:
            fetcher.fetch_all(fetch_text=False)
            mock_text.assert_not_called()

    @patch("news.client.requests.get")
    @patch("news.client.feedparser.parse")
    def test_cache_wraps_articles_in_dict(
        self, mock_parse, mock_get, fetcher, tmp_path
    ):
        """캐시 파일이 {"articles": [...]} 형식으로 저장된다."""
        mock_parse.return_value = _make_feed([_make_entry()])
        mock_get.return_value.text = (
            "<html><body><article><p>text</p></article></body></html>"
        )
        mock_get.return_value.raise_for_status = MagicMock()
        fetcher.fetch_all(data_dir=tmp_path)
        saved = json.loads((tmp_path / "news.json").read_text())
        assert "articles" in saved
        assert isinstance(saved["articles"], list)


# ---------------------------------------------------------------------------
# news.client.main
# ---------------------------------------------------------------------------


class TestNewsClientMain:
    @patch("news.client.requests.get")
    @patch("news.client.feedparser.parse")
    def test_main_prints_results(self, mock_parse, mock_get, tmp_path, capsys):
        """main() 실행 시 수집 결과 출력."""
        from news.client import main as news_main

        mock_parse.return_value = _make_feed([_make_entry()])
        mock_get.return_value.text = (
            "<html><body><article><p>text</p></article></body></html>"
        )
        mock_get.return_value.raise_for_status = MagicMock()
        news_main(data_dir=tmp_path)
        captured = capsys.readouterr()
        assert "완료" in captured.out or "캐시" in captured.out

    @patch("news.client.feedparser.parse")
    def test_main_uses_cache(self, mock_parse, tmp_path, capsys):
        """캐시 유효 시 '캐시 사용' 출력."""
        from news.client import main as news_main

        cached = {"articles": [{"source": "Reuters", "title": "cached"}]}
        (tmp_path / "news.json").write_text(json.dumps(cached))
        news_main(data_dir=tmp_path)
        captured = capsys.readouterr()
        assert "캐시" in captured.out
        mock_parse.assert_not_called()

    @patch("news.client.requests.get")
    @patch("news.client.feedparser.parse")
    def test_main_default_data_dir(
        self, mock_parse, mock_get, tmp_path, monkeypatch, capsys
    ):
        """data_dir=None 시 data/news/ 경로를 기본으로 사용한다."""
        from news.client import main as news_main

        monkeypatch.chdir(tmp_path)
        mock_parse.return_value = _make_feed([_make_entry()])
        mock_get.return_value.text = (
            "<html><body><article><p>text</p></article></body></html>"
        )
        mock_get.return_value.raise_for_status = MagicMock()
        news_main()
        assert (tmp_path / "data" / "news" / "news.json").exists()


# ---------------------------------------------------------------------------
# fetch_feed — published_parsed 예외 처리
# ---------------------------------------------------------------------------


class TestFetchFeedEdgeCases:
    @patch("news.client.feedparser.parse")
    def test_invalid_published_parsed_falls_back_to_empty_string(
        self, mock_parse, fetcher
    ):
        """published_parsed가 datetime() 생성에 실패하면 빈 문자열로 처리된다."""
        entry = _make_entry(
            published_parsed=(2024, 99, 1, 0, 0, 0, 0, 0, 0)
        )  # 월=99 → 예외
        mock_parse.return_value = _make_feed([entry])
        result = fetcher.fetch_feed("reuters")
        assert result[0]["published"] == ""

    @patch("news.client.feedparser.parse")
    def test_none_published_parsed_returns_empty_string(self, mock_parse, fetcher):
        """published_parsed가 None이면 published는 빈 문자열이다."""
        entry = MagicMock()
        entry.title = "No date"
        entry.summary = "summary"
        entry.link = "https://example.com"
        entry.published_parsed = None
        mock_parse.return_value = _make_feed([entry])
        result = fetcher.fetch_feed("reuters")
        assert result[0]["published"] == ""

    @patch("news.client.feedparser.parse")
    def test_summary_truncated_at_max_chars(self, mock_parse, fetcher):
        """RSS summary가 ARTICLE_MAX_CHARS를 초과하면 잘린다."""
        from news.client import ARTICLE_MAX_CHARS

        long_summary = "x" * (ARTICLE_MAX_CHARS + 100)
        entry = _make_entry(summary=long_summary)
        mock_parse.return_value = _make_feed([entry])
        result = fetcher.fetch_feed("reuters")
        assert len(result[0]["summary"]) <= ARTICLE_MAX_CHARS
