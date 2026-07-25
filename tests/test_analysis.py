"""경제 동향 분석 모듈 테스트."""

import json
from unittest.mock import patch

import pytest

from analysis import (
    US_SERIES_GROUPS,
    KR_SERIES_GROUPS,
    FALLBACK_MESSAGE,
    analyze_with_ai,
    build_prompt,
    extract_all_recent,
    extract_recent_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_series(series_id, title, title_ko, dates_values):
    """테스트용 시리즈 데이터 생성."""
    return {
        "series_id": series_id,
        "title": title,
        "title_ko": title_ko,
        "observations": [{"date": d, "value": v} for d, v in dates_values],
    }


def _date_range(start: str, count: int) -> list[str]:
    """start부터 count일간의 날짜 문자열 리스트."""
    import datetime as dt

    base = dt.datetime.strptime(start, "%Y-%m-%d")
    return [(base + dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(count)]


@pytest.fixture
def long_series(tmp_path):
    """60일치 데이터가 있는 시리즈 JSON."""
    dates = _date_range("2024-01-01", 60)
    obs = [(d, float(i)) for i, d in enumerate(dates)]
    data = _make_series("TEST01", "Test Series", "테스트", obs)
    path = tmp_path / "TEST01.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def short_series(tmp_path):
    """10일치 데이터 (30일 이내 전부)."""
    obs = [("2024-02-20", 1.0), ("2024-02-25", 2.0), ("2024-02-28", 3.0)]
    data = _make_series("SHORT", "Short Series", "짧은 시리즈", obs)
    path = tmp_path / "SHORT.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def data_dir(tmp_path):
    """여러 시리즈가 담긴 디렉토리."""
    for sid, n_days in [("AAA", 90), ("BBB", 60)]:
        dates = _date_range("2024-01-01", n_days)
        obs = [(d, float(i)) for i, d in enumerate(dates)]
        data = _make_series(sid, f"Series {sid}", f"시리즈 {sid}", obs)
        (tmp_path / f"{sid}.json").write_text(json.dumps(data))
    return tmp_path


# ---------------------------------------------------------------------------
# extract_recent_data
# ---------------------------------------------------------------------------


class TestExtractRecentData:
    def test_extracts_last_30_days(self, long_series, tmp_path):
        """최근 30일 데이터만 추출."""
        out = tmp_path / "TEST01_1m.json"
        result = extract_recent_data(long_series, out)
        assert out.exists()
        assert all(
            obs["date"] >= result["observations"][0]["date"]
            for obs in result["observations"]
        )
        # 원본 60일 중 일부만 추출
        assert len(result["observations"]) < 60
        assert len(result["observations"]) > 0

    def test_preserves_metadata(self, long_series, tmp_path):
        """series_id, title, title_ko가 보존."""
        out = tmp_path / "TEST01_1m.json"
        result = extract_recent_data(long_series, out)
        assert result["series_id"] == "TEST01"
        assert result["title"] == "Test Series"
        assert result["title_ko"] == "테스트"

    def test_short_series_returns_all(self, short_series, tmp_path):
        """30일 이내 데이터만 있으면 전부 포함."""
        out = tmp_path / "SHORT_1m.json"
        result = extract_recent_data(short_series, out)
        assert len(result["observations"]) == 3

    def test_saves_json_file(self, long_series, tmp_path):
        """JSON 파일로 저장."""
        out = tmp_path / "TEST01_1m.json"
        extract_recent_data(long_series, out)
        loaded = json.loads(out.read_text())
        assert loaded["series_id"] == "TEST01"

    def test_custom_days(self, long_series, tmp_path):
        """days 파라미터로 기간 변경."""
        out = tmp_path / "TEST01_1m.json"
        result_7 = extract_recent_data(long_series, out, days=7)
        out2 = tmp_path / "TEST01_2m.json"
        result_60 = extract_recent_data(long_series, out2, days=60)
        assert len(result_7["observations"]) <= len(result_60["observations"])

    def test_empty_observations(self, tmp_path):
        """observations가 빈 리스트이면 빈 결과 반환."""
        data = _make_series("EMPTY", "Empty", "빈 시리즈", [])
        path = tmp_path / "EMPTY.json"
        path.write_text(json.dumps(data))
        out = tmp_path / "EMPTY_1m.json"
        result = extract_recent_data(path, out)
        assert result["observations"] == []
        assert result["series_id"] == "EMPTY"


# ---------------------------------------------------------------------------
# extract_all_recent
# ---------------------------------------------------------------------------


class TestExtractAllRecent:
    def test_creates_1m_files(self, data_dir):
        """모든 원본 JSON에 대해 _1m 파일 생성."""
        results = extract_all_recent(data_dir)
        assert (data_dir / "AAA_1m.json").exists()
        assert (data_dir / "BBB_1m.json").exists()
        assert len(results) == 2

    def test_skips_existing_derived_files(self, data_dir):
        """_1m, _1y 파일은 처리 대상에서 제외."""
        (data_dir / "AAA_1m.json").write_text("{}")
        (data_dir / "AAA_1y.json").write_text("{}")
        # 기존 _1m 캐시를 만료시켜서 재생성 유도
        import os
        import time

        old = time.time() - 25 * 3600
        os.utime(data_dir / "AAA_1m.json", (old, old))
        results = extract_all_recent(data_dir)
        series_ids = [r["series_id"] for r in results]
        assert "AAA" in series_ids
        assert "BBB" in series_ids
        assert len(results) == 2

    def test_caching_skips_fresh(self, data_dir):
        """캐시 유효 시 추출 건너뜀."""
        extract_all_recent(data_dir)
        # 두 번째 호출 — 캐시 사용
        results = extract_all_recent(data_dir)
        assert len(results) == 2

    def test_expired_cache_regenerates(self, data_dir):
        """24시간 경과 시 자동 재생성."""
        import os
        import time

        extract_all_recent(data_dir)
        # _1m 파일의 mtime을 25시간 전으로
        old = time.time() - 25 * 3600
        for p in data_dir.glob("*_1m.json"):
            os.utime(p, (old, old))
        results = extract_all_recent(data_dir)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_includes_series_names(self, data_dir):
        """프롬프트에 시리즈명이 포함."""
        recent = extract_all_recent(data_dir)
        prompt = build_prompt(recent)
        assert "시리즈 AAA" in prompt or "AAA" in prompt
        assert "시리즈 BBB" in prompt or "BBB" in prompt

    def test_includes_data_summary(self, data_dir):
        """프롬프트에 그룹별 지표 방향성 요약이 포함."""
        recent = extract_all_recent(data_dir)
        prompt = build_prompt(recent)
        assert "상승" in prompt or "하락" in prompt or "보합" in prompt

    def test_returns_string(self, data_dir):
        """문자열 반환."""
        recent = extract_all_recent(data_dir)
        prompt = build_prompt(recent)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_empty_list_returns_prompt(self):
        """빈 데이터도 프롬프트 반환 (분석 불가 안내)."""
        prompt = build_prompt([])
        assert isinstance(prompt, str)


# ---------------------------------------------------------------------------
# analyze_with_ai
# ---------------------------------------------------------------------------


class TestAnalyzeWithAi:
    @patch("analysis._call_claude")
    def test_claude_success(self, mock_claude, tmp_path):
        """Claude 성공 시 결과 반환."""
        mock_claude.return_value = "<p>분석 결과</p>"
        result = analyze_with_ai("test prompt", data_dir=tmp_path)
        assert result["provider"] == "claude"
        assert "<p>분석 결과</p>" in result["content"]
        assert "generated_at" in result

    @patch("analysis._call_gemini")
    @patch("analysis._call_chatgpt")
    @patch("analysis._call_claude")
    def test_fallback_to_chatgpt(
        self, mock_claude, mock_chatgpt, mock_gemini, tmp_path
    ):
        """Claude 실패 → ChatGPT로 fallback."""
        mock_claude.side_effect = Exception("Claude error")
        mock_chatgpt.return_value = "<p>ChatGPT 분석</p>"
        result = analyze_with_ai("test prompt", data_dir=tmp_path)
        assert result["provider"] == "chatgpt"

    @patch("analysis._call_gemini")
    @patch("analysis._call_chatgpt")
    @patch("analysis._call_claude")
    def test_fallback_to_gemini(self, mock_claude, mock_chatgpt, mock_gemini, tmp_path):
        """Claude+ChatGPT 실패 → Gemini로 fallback."""
        mock_claude.side_effect = Exception("fail")
        mock_chatgpt.side_effect = Exception("fail")
        mock_gemini.return_value = "<p>Gemini 분석</p>"
        result = analyze_with_ai("test prompt", data_dir=tmp_path)
        assert result["provider"] == "gemini"

    @patch("analysis._call_gemini")
    @patch("analysis._call_chatgpt")
    @patch("analysis._call_claude")
    def test_all_fail_returns_fallback(
        self, mock_claude, mock_chatgpt, mock_gemini, tmp_path
    ):
        """3개 모두 실패 → fallback 메시지."""
        mock_claude.side_effect = Exception("fail")
        mock_chatgpt.side_effect = Exception("fail")
        mock_gemini.side_effect = Exception("fail")
        result = analyze_with_ai("test prompt", data_dir=tmp_path)
        assert result["provider"] == "none"
        assert FALLBACK_MESSAGE in result["content"]

    @patch("analysis._call_claude")
    def test_caches_result(self, mock_claude, tmp_path):
        """결과가 data/analysis.json에 캐싱."""
        mock_claude.return_value = "<p>캐시 테스트</p>"
        analyze_with_ai("prompt", data_dir=tmp_path)
        assert (tmp_path / "analysis.json").exists()

    @patch("analysis._call_claude")
    def test_uses_cache(self, mock_claude, tmp_path):
        """캐시 유효 시 API 호출 안 함."""
        mock_claude.return_value = "<p>첫 호출</p>"
        analyze_with_ai("prompt", data_dir=tmp_path)
        mock_claude.reset_mock()
        # 두 번째 호출 — 캐시 사용
        result = analyze_with_ai("prompt", data_dir=tmp_path)
        mock_claude.assert_not_called()
        assert "첫 호출" in result["content"]

    @patch("analysis._call_claude")
    def test_expired_cache_regenerates(self, mock_claude, tmp_path):
        """24시간 경과 시 캐시 자동 무효화 → 재호출."""
        import os
        import time

        mock_claude.return_value = "<p>v1</p>"
        analyze_with_ai("prompt", data_dir=tmp_path)
        mock_claude.return_value = "<p>v2</p>"
        # analysis.json의 mtime을 25시간 전으로
        old = time.time() - 25 * 3600
        os.utime(tmp_path / "analysis.json", (old, old))
        result = analyze_with_ai("prompt", data_dir=tmp_path)
        assert "v2" in result["content"]

    @patch("analysis._call_claude")
    def test_wraps_non_html_response(self, mock_claude, tmp_path):
        """HTML 태그 없는 응답은 <p>로 감싸기."""
        mock_claude.return_value = "그냥 텍스트 응답"
        result = analyze_with_ai("prompt", data_dir=tmp_path)
        assert "<p>" in result["content"]


# ---------------------------------------------------------------------------
# _summarize_series
# ---------------------------------------------------------------------------


class TestSummarizeSeries:
    def test_all_none_observations(self):
        """모든 observation value가 None이면 '데이터 없음' 반환."""
        from analysis import _summarize_series

        data = {
            "series_id": "TEST",
            "title": "Test Series",
            "title_ko": "테스트",
            "observations": [
                {"date": "2024-01-01", "value": None},
                {"date": "2024-01-02", "value": None},
            ],
        }
        result = _summarize_series(data)
        assert "데이터 없음" in result
        assert "TEST" in result

    def test_no_title_ko_uses_title(self):
        """title_ko 없으면 title 사용."""
        from analysis import _summarize_series

        data = {
            "series_id": "X",
            "title": "Fallback Title",
            "observations": [
                {"date": "2024-01-01", "value": None},
            ],
        }
        result = _summarize_series(data)
        assert "Fallback Title" in result


# ---------------------------------------------------------------------------
# _ensure_html
# ---------------------------------------------------------------------------


class TestEnsureHtml:
    def test_whitespace_only_text(self):
        """공백만 있는 텍스트도 <p>로 감싼다."""
        from analysis import _ensure_html

        result = _ensure_html("   ")
        assert "<p>" in result

    def test_multi_paragraph(self):
        """빈 줄로 구분된 여러 문단을 각각 <p>로 감싼다."""
        from analysis import _ensure_html

        result = _ensure_html("첫 문단\n\n두 번째 문단")
        assert result.count("<p>") == 2

    def test_already_html(self):
        """이미 <p> 태그가 있으면 그대로 반환."""
        from analysis import _ensure_html

        html = "<p>이미 HTML</p>"
        assert _ensure_html(html) == html


# ---------------------------------------------------------------------------
# _call_claude / _call_chatgpt / _call_gemini 개별 함수 테스트
# ---------------------------------------------------------------------------


class TestCallClaude:
    def test_returns_text(self):
        """Claude API 호출 후 텍스트 반환."""
        from unittest.mock import MagicMock

        mock_anthropic = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="<p>Claude 분석</p>")]
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_msg

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from analysis import _call_claude

            result = _call_claude("테스트 프롬프트")
        assert result == "<p>Claude 분석</p>"


class TestCallChatgpt:
    def test_returns_text(self):
        """ChatGPT API 호출 후 텍스트 반환."""
        from unittest.mock import MagicMock

        mock_openai = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "<p>GPT 분석</p>"
        mock_openai.OpenAI.return_value.chat.completions.create.return_value = (
            MagicMock(choices=[mock_choice])
        )

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from analysis import _call_chatgpt

            result = _call_chatgpt("테스트 프롬프트")
        assert result == "<p>GPT 분석</p>"


class TestCallGemini:
    def test_returns_text(self):
        """Gemini API 호출 후 텍스트 반환."""
        from unittest.mock import MagicMock

        mock_google = MagicMock()
        mock_genai = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<p>Gemini 분석</p>"
        mock_genai.Client.return_value.models.generate_content.return_value = (
            mock_response
        )
        mock_google.genai = mock_genai

        with patch.dict(
            "sys.modules", {"google": mock_google, "google.genai": mock_genai}
        ):
            from analysis import _call_gemini

            result = _call_gemini("테스트 프롬프트")
        assert result == "<p>Gemini 분석</p>"


# ---------------------------------------------------------------------------
# 한국 시장 분석 지원
# ---------------------------------------------------------------------------


class TestKrPrompt:
    def test_kr_prompt_template_exists(self):
        """KR용 프롬프트 템플릿이 존재."""
        from analysis import PROMPT_TEMPLATE_KR

        assert "한국" in PROMPT_TEMPLATE_KR
        assert "{data_summary}" in PROMPT_TEMPLATE_KR

    def test_build_prompt_kr(self, data_dir):
        """market='kr' 시 한국 프롬프트 사용."""
        recent = extract_all_recent(data_dir)
        prompt = build_prompt(recent, market="kr")
        assert "한국" in prompt

    def test_build_prompt_us_default(self, data_dir):
        """market 미지정 시 기존 US 프롬프트."""
        recent = extract_all_recent(data_dir)
        prompt = build_prompt(recent)
        assert "경제 분석 전문가" in prompt


class TestAnalyzeWithAiMarket:
    @patch("analysis._call_claude")
    def test_kr_separate_cache(self, mock_claude, tmp_path):
        """KR 분석은 별도 캐시 파일 사용."""
        mock_claude.return_value = "<p>한국 분석</p>"
        analyze_with_ai("prompt", data_dir=tmp_path, market="kr")
        assert (tmp_path / "analysis_kr.json").exists()
        assert not (tmp_path / "analysis.json").exists()

    @patch("analysis._call_claude")
    def test_us_cache_unchanged(self, mock_claude, tmp_path):
        """US 분석은 기존 analysis.json 사용."""
        mock_claude.return_value = "<p>US 분석</p>"
        analyze_with_ai("prompt", data_dir=tmp_path, market="us")
        assert (tmp_path / "analysis.json").exists()


# ---------------------------------------------------------------------------
# _summarize_series — 방향성 분기
# ---------------------------------------------------------------------------


class TestSummarizeSeriesDirections:
    def _make_data(self, sid, values):
        import datetime as dt

        base = dt.datetime(2024, 1, 1)
        obs = [
            {"date": (base + dt.timedelta(days=i)).strftime("%Y-%m-%d"), "value": v}
            for i, v in enumerate(values)
        ]
        return {"series_id": sid, "title": sid, "title_ko": sid, "observations": obs}

    def test_rising_returns_상승(self):
        """마지막 값이 첫 값보다 유의미하게 높으면 '상승' 반환."""
        from analysis import _summarize_series

        data = self._make_data("UP", [100.0, 105.0])  # +5%
        assert "상승" in _summarize_series(data)

    def test_declining_returns_하락(self):
        """마지막 값이 첫 값보다 유의미하게 낮으면 '하락' 반환."""
        from analysis import _summarize_series

        data = self._make_data("DOWN", [100.0, 90.0])  # -10%
        assert "하락" in _summarize_series(data)

    def test_flat_returns_보합(self):
        """변동폭이 0.5% 미만이면 '보합' 반환."""
        from analysis import _summarize_series

        data = self._make_data("FLAT", [100.0, 100.3])  # +0.3%
        assert "보합" in _summarize_series(data)

    def test_zero_start_value_no_division_error(self):
        """첫 값이 0인 경우 ZeroDivisionError가 발생하지 않는다."""
        from analysis import _summarize_series

        data = self._make_data("ZERO", [0.0, 1.0])
        result = _summarize_series(data)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _format_grouped_data
# ---------------------------------------------------------------------------


class TestFormatGroupedData:
    def _make_series(self, sid, start, end):
        return {
            "series_id": sid,
            "title": sid,
            "title_ko": f"지표 {sid}",
            "observations": [
                {"date": "2024-01-01", "value": start},
                {"date": "2024-01-30", "value": end},
            ],
        }

    def test_groups_series_with_headers(self):
        """그룹 헤더(▶)와 시리즈가 포함된다."""
        from analysis import _format_grouped_data

        data = [self._make_series("DGS10", 4.0, 4.5)]
        groups = {"금리": ["DGS10"]}
        result = _format_grouped_data(data, groups)
        assert "▶ 금리" in result
        assert "DGS10" in result

    def test_multiple_groups_each_have_header(self):
        """여러 그룹이 각각 헤더와 함께 출력된다."""
        from analysis import _format_grouped_data

        data = [
            self._make_series("DGS10", 4.0, 4.5),
            self._make_series("UNRATE", 3.7, 3.9),
        ]
        groups = {"금리": ["DGS10"], "고용": ["UNRATE"]}
        result = _format_grouped_data(data, groups)
        assert "▶ 금리" in result
        assert "▶ 고용" in result

    def test_ungrouped_series_in_기타(self):
        """그룹 정의에 없는 시리즈는 '기타' 그룹에 포함된다."""
        from analysis import _format_grouped_data

        data = [self._make_series("UNKNOWN", 1.0, 2.0)]
        groups = {"금리": ["DGS10"]}
        result = _format_grouped_data(data, groups)
        assert "▶ 기타" in result
        assert "UNKNOWN" in result

    def test_no_기타_when_all_grouped(self):
        """모든 시리즈가 그룹에 포함되면 '기타' 없음."""
        from analysis import _format_grouped_data

        data = [self._make_series("DGS10", 4.0, 4.5)]
        groups = {"금리": ["DGS10"]}
        result = _format_grouped_data(data, groups)
        assert "기타" not in result

    def test_empty_data_returns_no_data_message(self):
        """데이터가 없으면 안내 메시지 반환."""
        from analysis import _format_grouped_data

        result = _format_grouped_data([], {})
        assert "분석할 데이터가 없습니다" in result

    def test_group_series_not_in_data_skipped(self):
        """그룹에 정의됐지만 데이터에 없는 시리즈는 조용히 건너뛴다."""
        from analysis import _format_grouped_data

        data = [self._make_series("DGS10", 4.0, 4.5)]
        groups = {"금리": ["DGS10", "MISSING_ID"]}
        result = _format_grouped_data(data, groups)
        assert "MISSING_ID" not in result
        assert "DGS10" in result

    def test_series_not_duplicated_across_groups(self):
        """동일 시리즈가 두 그룹에 정의돼도 첫 그룹에만 출력되고 두 번째 그룹은 생략된다."""
        from analysis import _format_grouped_data

        data = [self._make_series("DGS10", 4.0, 4.5)]
        groups = {"그룹A": ["DGS10"], "그룹B": ["DGS10"]}
        result = _format_grouped_data(data, groups)
        # DGS10이 그룹A에 할당됐으므로 그룹B 헤더는 나오지 않는다
        assert "▶ 그룹A" in result
        assert "▶ 그룹B" not in result


# ---------------------------------------------------------------------------
# _format_news
# ---------------------------------------------------------------------------


class TestFormatNews:
    def test_empty_list_returns_no_news_message(self):
        """빈 리스트이면 '뉴스 없음' 메시지 반환."""
        from analysis import _format_news

        result = _format_news([])
        assert "뉴스 없음" in result

    def test_formats_source_title_date_text(self):
        """출처·제목·날짜·본문이 포함된 형식으로 변환된다."""
        from analysis import _format_news

        articles = [
            {
                "source": "Reuters",
                "title": "Fed holds rates",
                "text": "The Fed kept rates steady.",
                "published": "2024-04-15",
            }
        ]
        result = _format_news(articles)
        assert "[Reuters]" in result
        assert "Fed holds rates" in result
        assert "2024-04-15" in result
        assert "The Fed kept rates steady." in result

    def test_article_without_date_still_formatted(self):
        """날짜 없는 기사도 출처·제목이 포함된다."""
        from analysis import _format_news

        articles = [
            {
                "source": "CNBC",
                "title": "Markets rally",
                "text": "Stocks rose.",
                "published": "",
            }
        ]
        result = _format_news(articles)
        assert "[CNBC]" in result
        assert "Markets rally" in result

    def test_falls_back_to_summary_when_text_empty(self):
        """text가 빈 문자열이면 summary를 사용한다."""
        from analysis import _format_news

        articles = [
            {
                "source": "Bloomberg",
                "title": "Oil prices",
                "text": "",
                "summary": "Oil fell sharply.",
                "published": "2024-01-01",
            }
        ]
        result = _format_news(articles)
        assert "Oil fell sharply." in result

    def test_multiple_articles_all_included(self):
        """여러 기사가 모두 출력에 포함된다."""
        from analysis import _format_news

        articles = [
            {
                "source": "Reuters",
                "title": "A",
                "text": "text A",
                "published": "2024-01-01",
            },
            {
                "source": "CNBC",
                "title": "B",
                "text": "text B",
                "published": "2024-01-02",
            },
        ]
        result = _format_news(articles)
        assert "Reuters" in result
        assert "CNBC" in result


# ---------------------------------------------------------------------------
# build_prompt — news_list 파라미터
# ---------------------------------------------------------------------------


class TestBuildPromptWithNews:
    def test_news_included_when_provided(self, data_dir):
        """news_list 제공 시 뉴스 출처·제목이 프롬프트에 포함된다."""
        recent = extract_all_recent(data_dir)
        news = [
            {
                "source": "Reuters",
                "title": "Fed holds rates",
                "text": "The Fed...",
                "published": "2024-04-15",
            }
        ]
        prompt = build_prompt(recent, news_list=news)
        assert "Reuters" in prompt
        assert "Fed holds rates" in prompt

    def test_no_news_shows_no_news_message(self, data_dir):
        """news_list=None 시 '뉴스 없음' 안내가 포함된다."""
        recent = extract_all_recent(data_dir)
        prompt = build_prompt(recent, news_list=None)
        assert "뉴스 없음" in prompt

    def test_news_changes_prompt_content(self, data_dir):
        """뉴스 유무에 따라 프롬프트 내용이 달라진다."""
        recent = extract_all_recent(data_dir)
        no_news = build_prompt(recent, news_list=None)
        with_news = build_prompt(
            recent,
            news_list=[
                {
                    "source": "CNBC",
                    "title": "Markets",
                    "text": "Stocks rise.",
                    "published": "2024-01-01",
                }
            ],
        )
        assert no_news != with_news

    def test_grouped_data_header_in_prompt(self, data_dir):
        """그룹 헤더(▶)가 프롬프트에 포함된다."""
        recent = extract_all_recent(data_dir)
        prompt = build_prompt(recent)
        assert "▶" in prompt

    def test_kr_news_uses_kr_template(self, data_dir):
        """market='kr' + news_list 조합 시 KR 템플릿이 적용된다."""
        recent = extract_all_recent(data_dir)
        news = [
            {
                "source": "Reuters",
                "title": "Korea growth",
                "text": "KR GDP...",
                "published": "2024-01-01",
            }
        ]
        prompt = build_prompt(recent, market="kr", news_list=news)
        assert "한국" in prompt
        assert "Reuters" in prompt


# ---------------------------------------------------------------------------
# US_SERIES_GROUPS / KR_SERIES_GROUPS 구조 검증
# ---------------------------------------------------------------------------


class TestSeriesGroups:
    def test_us_groups_include_precious_metals_together(self):
        """US 그룹에서 금·은·동이 같은 그룹에 배치된다."""
        metals = {"GOLD", "SILVER", "COPPER"}
        for group_ids in US_SERIES_GROUPS.values():
            if metals & set(group_ids):
                assert metals.issubset(set(group_ids)), (
                    "GOLD·SILVER·COPPER는 동일 그룹에 있어야 한다"
                )
                return
        raise AssertionError("GOLD·SILVER·COPPER가 US_SERIES_GROUPS에 없음")

    def test_us_groups_contain_yahoo_series(self):
        """US 그룹에 Yahoo Finance 시리즈(TNX, VIX, DXY, WTI)가 포함된다."""
        all_ids = {sid for ids in US_SERIES_GROUPS.values() for sid in ids}
        for sid in ("TNX", "VIX", "DXY", "WTI"):
            assert sid in all_ids, f"{sid} not in US_SERIES_GROUPS"

    def test_kr_groups_contain_stock_market_series(self):
        """KR 그룹에 KOSPI·KOSDAQ이 포함된다."""
        all_ids = {sid for ids in KR_SERIES_GROUPS.values() for sid in ids}
        assert "KOSPI" in all_ids
        assert "KOSDAQ" in all_ids

    def test_no_duplicate_series_ids_within_market(self):
        """같은 시장 그룹 내에서 동일 series_id가 중복되지 않는다."""
        for groups, label in [(US_SERIES_GROUPS, "US"), (KR_SERIES_GROUPS, "KR")]:
            seen: set[str] = set()
            for ids in groups.values():
                for sid in ids:
                    assert sid not in seen, f"{label}: {sid} duplicated"
                    seen.add(sid)
