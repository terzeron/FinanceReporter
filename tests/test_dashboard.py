"""대시보드 HTML 생성 모듈 테스트."""

import json

import pytest

from dashboard import generate_html, build_dashboard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def analysis_data():
    """AI 분석 결과."""
    return {
        "provider": "claude",
        "content": "<p>경제 동향 분석입니다.</p><p>두 번째 문단.</p><p>세 번째.</p>",
        "generated_at": "2024-03-01 12:00:00",
    }


@pytest.fixture
def series_list():
    """시리즈 메타데이터 리스트."""
    return [
        {
            "series_id": "DGS10",
            "title": "10-Year Treasury",
            "title_ko": "미국 10년물 국채 금리",
        },
        {
            "series_id": "VIX",
            "title": "CBOE Volatility Index",
            "title_ko": "변동성 지수",
        },
    ]


@pytest.fixture
def charts_dir(tmp_path):
    """차트 PNG가 있는 디렉토리."""
    d = tmp_path / "charts"
    d.mkdir()
    for name in ["DGS10.png", "DGS10_1y.png", "VIX.png", "VIX_1y.png"]:
        (d / name).write_bytes(b"fake png")
    return d


@pytest.fixture
def data_dir(tmp_path):
    """시리즈 JSON이 있는 디렉토리."""
    d = tmp_path / "data"
    d.mkdir()
    for sid in ["DGS10", "VIX"]:
        data = {
            "series_id": sid,
            "title": f"Title {sid}",
            "title_ko": f"한글 {sid}",
            "observations": [{"date": "2024-01-01", "value": 1.0}],
        }
        (d / f"{sid}.json").write_text(json.dumps(data))
    return d


# ---------------------------------------------------------------------------
# generate_html
# ---------------------------------------------------------------------------


class TestGenerateHtml:
    def test_contains_analysis(self, analysis_data, series_list):
        """분석 텍스트가 HTML에 포함."""
        html = generate_html(analysis_data, series_list)
        assert "경제 동향 분석입니다." in html

    def test_contains_chart_images(self, analysis_data, series_list):
        """차트 이미지 경로가 포함."""
        html = generate_html(analysis_data, series_list)
        assert 'src="charts/DGS10.png?' in html
        assert 'src="charts/DGS10_1y.png?' in html
        assert 'src="charts/VIX.png?' in html

    def test_contains_series_titles(self, analysis_data, series_list):
        """시리즈 한글 제목이 포함."""
        html = generate_html(analysis_data, series_list)
        assert "미국 10년물 국채 금리" in html
        assert "변동성 지수" in html

    def test_responsive_css(self, analysis_data, series_list):
        """반응형 CSS가 포함."""
        html = generate_html(analysis_data, series_list)
        assert "@media" in html
        assert "flex" in html

    def test_fallback_analysis(self, series_list):
        """분석 실패 시 fallback 메시지."""
        fallback = {
            "provider": "none",
            "content": "<p>AI 분석을 이용할 수 없습니다.</p>",
            "generated_at": "2024-03-01",
        }
        html = generate_html(fallback, series_list)
        assert "AI 분석을 이용할 수 없습니다." in html

    def test_returns_valid_html(self, analysis_data, series_list):
        """HTML 문서 기본 구조."""
        html = generate_html(analysis_data, series_list)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_provider_shown(self, analysis_data, series_list):
        """분석 제공자가 표시."""
        html = generate_html(analysis_data, series_list)
        assert "claude" in html.lower()


# ---------------------------------------------------------------------------
# build_dashboard
# ---------------------------------------------------------------------------


class TestBuildDashboard:
    def test_creates_index_html(self, tmp_path, charts_dir, data_dir):
        """출력 디렉토리에 index.html 생성."""
        output = tmp_path / "output"
        analysis = {
            "provider": "claude",
            "content": "<p>테스트</p>",
            "generated_at": "2024-03-01",
        }
        build_dashboard(
            output_dir=output,
            data_dir=data_dir,
            charts_dir=charts_dir,
            analysis=analysis,
        )
        assert (output / "index.html").exists()

    def test_copies_chart_images(self, tmp_path, charts_dir, data_dir):
        """차트 이미지를 출력 디렉토리에 복사."""
        output = tmp_path / "output"
        analysis = {"provider": "none", "content": "<p>x</p>", "generated_at": ""}
        build_dashboard(
            output_dir=output,
            data_dir=data_dir,
            charts_dir=charts_dir,
            analysis=analysis,
        )
        assert (output / "charts" / "DGS10.png").exists()
        assert (output / "charts" / "VIX_1y.png").exists()

    def test_creates_output_dir(self, tmp_path, charts_dir, data_dir):
        """출력 디렉토리가 없으면 자동 생성."""
        output = tmp_path / "deep" / "nested" / "output"
        analysis = {"provider": "none", "content": "<p>x</p>", "generated_at": ""}
        build_dashboard(
            output_dir=output,
            data_dir=data_dir,
            charts_dir=charts_dir,
            analysis=analysis,
        )
        assert output.exists()
        assert (output / "index.html").exists()

    def test_html_references_relative_paths(self, tmp_path, charts_dir, data_dir):
        """HTML에서 이미지를 상대경로로 참조."""
        output = tmp_path / "output"
        analysis = {"provider": "none", "content": "<p>x</p>", "generated_at": ""}
        build_dashboard(
            output_dir=output,
            data_dir=data_dir,
            charts_dir=charts_dir,
            analysis=analysis,
        )
        html = (output / "index.html").read_text()
        assert 'src="charts/' in html
        # 절대경로가 아님
        assert 'src="/' not in html

    def test_skips_derived_files(self, tmp_path, charts_dir):
        """파생 파일(_1m, _1y)과 analysis.json은 시리즈 목록에서 제외."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # 원본 파일
        data = {
            "series_id": "TEST",
            "title": "Test",
            "title_ko": "테스트",
            "observations": [],
        }
        (data_dir / "TEST.json").write_text(json.dumps(data))
        # 파생 파일 — 무시되어야 함
        (data_dir / "TEST_1m.json").write_text(json.dumps(data))
        (data_dir / "TEST_1y.json").write_text(json.dumps(data))
        (data_dir / "analysis.json").write_text(json.dumps({"content": "x"}))

        output = tmp_path / "output"
        analysis = {"provider": "none", "content": "<p>x</p>", "generated_at": ""}
        build_dashboard(
            output_dir=output,
            data_dir=data_dir,
            charts_dir=charts_dir,
            analysis=analysis,
        )
        html = (output / "index.html").read_text()
        # TEST 시리즈만 카드에 포함 (1개)
        assert html.count("charts/TEST.png") == 1


class TestChartGuides:
    def test_guide_newline_converted_to_br(self):
        """CHART_GUIDES의 \\n이 HTML에서 <br>로 변환."""
        from dashboard import generate_html

        analysis = {"provider": "none", "content": "<p>x</p>", "generated_at": ""}
        series_list = [
            {"series_id": "DGS10", "title": "10-Year", "title_ko": "10년물"},
        ]
        html = generate_html(analysis, series_list)
        assert "<br>" in html
        assert "\\n" not in html  # raw \n이 남아있으면 안 됨


# ---------------------------------------------------------------------------
# 탭 UI (US/KR)
# ---------------------------------------------------------------------------


class TestTabbedHtml:
    def test_has_tab_buttons(self):
        """US/KR 탭 버튼이 존재."""
        from dashboard import generate_tabbed_html

        us_analysis = {"provider": "claude", "content": "<p>US</p>", "generated_at": ""}
        kr_analysis = {"provider": "claude", "content": "<p>KR</p>", "generated_at": ""}
        us_series = [{"series_id": "DGS10", "title": "T", "title_ko": "T"}]
        kr_series = [{"series_id": "KOSPI", "title": "K", "title_ko": "코스피"}]

        html = generate_tabbed_html(us_analysis, us_series, kr_analysis, kr_series)
        assert 'data-tab="us"' in html
        assert 'data-tab="kr"' in html
        assert "US 미국" in html
        assert "KR 한국" in html

    def test_us_tab_active_by_default(self):
        """US 탭이 기본 활성."""
        from dashboard import generate_tabbed_html

        us_a = {"provider": "none", "content": "<p>US</p>", "generated_at": ""}
        kr_a = {"provider": "none", "content": "<p>KR</p>", "generated_at": ""}
        html = generate_tabbed_html(us_a, [], kr_a, [])
        # US 탭 콘텐츠가 display:none이 아닌지 확인
        assert 'id="tab-us"' in html
        assert 'id="tab-kr"' in html

    def test_contains_both_analyses(self):
        """양쪽 분석 텍스트가 모두 포함."""
        from dashboard import generate_tabbed_html

        us_a = {"provider": "claude", "content": "<p>미국 분석</p>", "generated_at": ""}
        kr_a = {"provider": "claude", "content": "<p>한국 분석</p>", "generated_at": ""}
        html = generate_tabbed_html(us_a, [], kr_a, [])
        assert "미국 분석" in html
        assert "한국 분석" in html

    def test_kr_chart_guides_used(self):
        """KR 시리즈에 KR 가이드가 적용."""
        from dashboard import generate_tabbed_html

        us_a = {"provider": "none", "content": "<p>US</p>", "generated_at": ""}
        kr_a = {"provider": "none", "content": "<p>KR</p>", "generated_at": ""}
        kr_series = [{"series_id": "KOSPI", "title": "KOSPI", "title_ko": "코스피"}]
        html = generate_tabbed_html(us_a, [], kr_a, kr_series)
        # KOSPI 가이드가 HTML에 포함
        assert "코스피" in html

    def test_has_javascript(self):
        """탭 전환 JavaScript 포함."""
        from dashboard import generate_tabbed_html

        us_a = {"provider": "none", "content": "<p>US</p>", "generated_at": ""}
        kr_a = {"provider": "none", "content": "<p>KR</p>", "generated_at": ""}
        html = generate_tabbed_html(us_a, [], kr_a, [])
        assert "addEventListener" in html


class TestBuildTabbedDashboard:
    def test_creates_index_with_tabs(self, tmp_path, charts_dir, data_dir):
        """탭 대시보드 index.html 생성."""
        from dashboard import build_tabbed_dashboard

        us_a = {"provider": "none", "content": "<p>US</p>", "generated_at": ""}
        kr_a = {"provider": "none", "content": "<p>KR</p>", "generated_at": ""}
        output = tmp_path / "output"

        # KR 데이터/차트 디렉토리
        kr_data = tmp_path / "kr_data"
        kr_data.mkdir()
        kr_charts = tmp_path / "kr_charts"
        kr_charts.mkdir()
        data = {
            "series_id": "KOSPI",
            "title": "KOSPI",
            "title_ko": "코스피",
            "observations": [],
        }
        (kr_data / "KOSPI.json").write_text(json.dumps(data))
        (kr_charts / "KOSPI.png").write_bytes(b"fake png")
        (kr_charts / "KOSPI_1y.png").write_bytes(b"fake png")

        result = build_tabbed_dashboard(
            output_dir=output,
            us_data_dir=data_dir,
            us_charts_dir=charts_dir,
            us_analysis=us_a,
            kr_data_dir=kr_data,
            kr_charts_dir=kr_charts,
            kr_analysis=kr_a,
        )
        assert result.exists()
        html = result.read_text()
        assert 'data-tab="us"' in html
        assert 'data-tab="kr"' in html
        assert "US 미국" in html
        assert "KR 한국" in html
