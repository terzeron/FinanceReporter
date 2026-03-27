"""FRED 차트 생성 모듈 테스트."""

import json
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")  # GUI 없는 환경에서 렌더링

from fred.chart import load_series_data, plot_series, plot_all


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_data():
    """정상 시리즈 데이터."""
    return {
        "series_id": "TEST01",
        "title": "Test Series",
        "title_ko": "테스트 시리즈",
        "observations": [
            {"date": "2024-01-01", "value": 1.0},
            {"date": "2024-02-01", "value": 2.5},
            {"date": "2024-03-01", "value": 1.8},
            {"date": "2024-04-01", "value": 3.0},
        ],
    }


@pytest.fixture
def long_range_data():
    """2년치 월간 데이터 (최근 1년 필터링 테스트용)."""
    observations = []
    for year in [2023, 2024]:
        for month in range(1, 13):
            observations.append(
                {
                    "date": f"{year}-{month:02d}-01",
                    "value": float(month + (year - 2023) * 12),
                }
            )
    return {
        "series_id": "LONG01",
        "title": "Long Range Series",
        "title_ko": "장기 시리즈",
        "observations": observations,
    }


@pytest.fixture
def data_with_nulls():
    """결측치 포함 데이터."""
    return {
        "series_id": "TEST02",
        "title": "Series With Gaps",
        "observations": [
            {"date": "2024-01-01", "value": 1.0},
            {"date": "2024-02-01", "value": None},
            {"date": "2024-03-01", "value": 2.0},
            {"date": "2024-04-01", "value": None},
            {"date": "2024-05-01", "value": 3.0},
        ],
    }


@pytest.fixture
def empty_data():
    """관측값 없는 데이터."""
    return {
        "series_id": "EMPTY",
        "title": "Empty Series",
        "observations": [],
    }


@pytest.fixture
def data_dir(tmp_path, sample_data, data_with_nulls):
    """JSON 파일들이 담긴 임시 디렉토리."""
    for data in [sample_data, data_with_nulls]:
        path = tmp_path / f"{data['series_id']}.json"
        path.write_text(json.dumps(data))
    return tmp_path


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# load_series_data
# ---------------------------------------------------------------------------


class TestLoadSeriesData:
    def test_loads_valid_json(self, tmp_path, sample_data):
        """정상 JSON 파일 로드."""
        json_path = _write_json(tmp_path / "TEST01.json", sample_data)
        result = load_series_data(json_path)
        assert result["series_id"] == "TEST01"
        assert result["title"] == "Test Series"
        assert len(result["observations"]) == 4

    def test_file_not_found(self, tmp_path):
        """존재하지 않는 파일 → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_series_data(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# plot_series
# ---------------------------------------------------------------------------


class TestPlotSeries:
    def test_creates_png_file(self, tmp_path, sample_data):
        """PNG 파일 생성 확인."""
        json_path = _write_json(tmp_path / "TEST01.json", sample_data)
        out_path = tmp_path / "TEST01.png"
        plot_series(json_path, out_path)
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_handles_null_values(self, tmp_path, data_with_nulls):
        """결측치(None) 포함 데이터도 정상 차트 생성."""
        json_path = _write_json(tmp_path / "TEST02.json", data_with_nulls)
        out_path = tmp_path / "TEST02.png"
        plot_series(json_path, out_path)
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_empty_observations_creates_file(self, tmp_path, empty_data):
        """관측값 비어있어도 차트 파일 생성 (빈 차트)."""
        json_path = _write_json(tmp_path / "EMPTY.json", empty_data)
        out_path = tmp_path / "EMPTY.png"
        plot_series(json_path, out_path)
        assert out_path.exists()

    def test_creates_output_directory(self, tmp_path, sample_data):
        """출력 디렉토리가 없으면 자동 생성."""
        json_path = _write_json(tmp_path / "TEST01.json", sample_data)
        out_path = tmp_path / "subdir" / "TEST01.png"
        plot_series(json_path, out_path)
        assert out_path.exists()

    def test_chart_has_korean_and_english_title(self, tmp_path, sample_data):
        """한글 제목 + 영문 제목이 두 줄로 설정되는지 확인."""
        json_path = _write_json(tmp_path / "TEST01.json", sample_data)
        out_path = tmp_path / "TEST01.png"
        fig = plot_series(json_path, out_path)
        ax = fig.axes[0]
        title = ax.get_title()
        assert "테스트 시리즈" in title
        assert "(Test Series)" in title
        assert "\n" in title

    def test_chart_without_title_ko(self, tmp_path):
        """title_ko 없으면 기존 형식 (영문 제목 + series_id)."""
        data = {
            "series_id": "TEST99",
            "title": "English Only",
            "observations": [{"date": "2024-01-01", "value": 1.0}],
        }
        json_path = _write_json(tmp_path / "TEST99.json", data)
        out_path = tmp_path / "TEST99.png"
        fig = plot_series(json_path, out_path)
        ax = fig.axes[0]
        title = ax.get_title()
        assert "English Only" in title
        assert "TEST99" in title
        assert "\n" not in title

    def test_recent_months_filters_data(self, tmp_path, long_range_data):
        """recent_months 지정 시 최근 N개월 데이터만 차트에 포함."""
        json_path = _write_json(tmp_path / "LONG01.json", long_range_data)
        out_path = tmp_path / "LONG01_1y.png"
        fig = plot_series(json_path, out_path, recent_months=12)
        ax = fig.axes[0]
        lines = ax.get_lines()
        assert len(lines) == 1
        # 2년치 24포인트 중 최근 12개월만 포함
        assert len(lines[0].get_xdata()) == 12

    def test_recent_months_none_uses_all_data(self, tmp_path, long_range_data):
        """recent_months=None이면 전체 데이터를 두 색상으로 표시."""
        json_path = _write_json(tmp_path / "LONG01.json", long_range_data)
        out_path = tmp_path / "LONG01.png"
        fig = plot_series(json_path, out_path)
        ax = fig.axes[0]
        lines = ax.get_lines()
        # 파란색(1년 이전+연결점) + 초록색(최근 1년)으로 2개 라인
        assert len(lines) == 2
        total_points = (
            len(lines[0].get_xdata()) + len(lines[1].get_xdata()) - 1
        )  # 연결점 중복
        assert total_points == 24


# ---------------------------------------------------------------------------
# plot_all
# ---------------------------------------------------------------------------


class TestPlotAll:
    def test_generates_two_charts_per_json(self, data_dir, tmp_path):
        """JSON당 전체 + 최근 1년, 2개 차트 생성."""
        out_dir = tmp_path / "charts"
        results = plot_all(data_dir, out_dir)
        # 2개 JSON × 2개 차트 = 4개
        assert len(results) == 4
        assert (out_dir / "TEST01.png").exists()
        assert (out_dir / "TEST01_1y.png").exists()
        assert (out_dir / "TEST02.png").exists()
        assert (out_dir / "TEST02_1y.png").exists()

    def test_returns_output_paths(self, data_dir, tmp_path):
        """생성된 파일 경로 리스트 반환."""
        out_dir = tmp_path / "charts"
        results = plot_all(data_dir, out_dir)
        assert all(isinstance(p, Path) for p in results)
        assert all(p.exists() for p in results)

    def test_empty_data_dir(self, tmp_path):
        """JSON 파일 없는 디렉토리 → 빈 리스트."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        out_dir = tmp_path / "charts"
        results = plot_all(empty_dir, out_dir)
        assert results == []
