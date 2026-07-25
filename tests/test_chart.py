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

    def test_skips_derived_files(self, tmp_path):
        """파생 파일(_1m, _1y)과 analysis.json은 건너뛴다."""
        data = {
            "series_id": "A",
            "title": "Series A",
            "observations": [{"date": "2024-01-01", "value": 1.0}],
        }
        (tmp_path / "A.json").write_text(json.dumps(data))
        (tmp_path / "A_1m.json").write_text(json.dumps(data))
        (tmp_path / "A_1y.json").write_text(json.dumps(data))
        (tmp_path / "analysis.json").write_text("{}")

        out_dir = tmp_path / "charts"
        results = plot_all(tmp_path, out_dir)
        assert len(results) == 2

    def test_series_order_controls_chart_sequence(self, tmp_path):
        """series_order 지정 시 해당 순서로 차트가 생성된다."""
        for sid in ("GOLD", "SILVER", "COPPER"):
            (tmp_path / f"{sid}.json").write_text(
                json.dumps(
                    {
                        "series_id": sid,
                        "title": sid,
                        "observations": [{"date": "2024-01-01", "value": 1.0}],
                    }
                )
            )
        out_dir = tmp_path / "charts"
        results = plot_all(tmp_path, out_dir, series_order=["GOLD", "SILVER", "COPPER"])
        stems = [p.stem.replace("_1y", "") for p in results]
        gold_idx = stems.index("GOLD")
        silver_idx = stems.index("SILVER")
        copper_idx = stems.index("COPPER")
        assert gold_idx < silver_idx < copper_idx

    def test_series_order_unlisted_appended_alphabetically(self, tmp_path):
        """series_order 미포함 파일은 알파벳순으로 뒤에 추가된다."""
        for sid in ("GOLD", "AAA", "ZZZ"):
            (tmp_path / f"{sid}.json").write_text(
                json.dumps(
                    {
                        "series_id": sid,
                        "title": sid,
                        "observations": [{"date": "2024-01-01", "value": 1.0}],
                    }
                )
            )
        out_dir = tmp_path / "charts"
        results = plot_all(tmp_path, out_dir, series_order=["GOLD"])
        stems = [p.stem.replace("_1y", "") for p in results]
        assert stems.index("GOLD") < stems.index("AAA")
        assert stems.index("GOLD") < stems.index("ZZZ")

    def test_series_order_none_falls_back_to_alphabetical(self, data_dir, tmp_path):
        """series_order=None이면 기존 알파벳 순서로 처리한다."""
        out_dir = tmp_path / "charts"
        results = plot_all(data_dir, out_dir, series_order=None)
        assert len(results) == 4  # data_dir fixture의 TEST01, TEST02

    def test_smooth_series_generates_chart(self, tmp_path):
        """smooth_series에 포함된 시리즈는 차트가 생성된다."""
        data = {
            "series_id": "KR_BSI",
            "title": "BSI",
            "observations": [
                {"date": f"2024-0{m}-01", "value": float(m * 10)} for m in range(1, 7)
            ],
        }
        (tmp_path / "KR_BSI.json").write_text(json.dumps(data))
        out_dir = tmp_path / "charts"
        results = plot_all(tmp_path, out_dir, smooth_series={"KR_BSI"})
        assert (out_dir / "KR_BSI.png").exists()
        assert len(results) == 2

    def test_skips_empty_series_in_plot_all(self, tmp_path):
        """관측값이 없는 시리즈는 차트를 건너뛴다."""
        (tmp_path / "EMPTY.json").write_text(
            json.dumps({"series_id": "EMPTY", "title": "E", "observations": []})
        )
        (tmp_path / "NORMAL.json").write_text(
            json.dumps(
                {
                    "series_id": "NORMAL",
                    "title": "N",
                    "observations": [{"date": "2024-01-01", "value": 1.0}],
                }
            )
        )
        out_dir = tmp_path / "charts"
        results = plot_all(tmp_path, out_dir)
        assert not (out_dir / "EMPTY.png").exists()
        assert (out_dir / "NORMAL.png").exists()
        assert len(results) == 2

    def test_skips_all_null_observations(self, tmp_path):
        """모든 값이 None인 시리즈도 차트를 건너뛴다."""
        (tmp_path / "NULL.json").write_text(
            json.dumps(
                {
                    "series_id": "NULL",
                    "title": "N",
                    "observations": [{"date": "2024-01-01", "value": None}],
                }
            )
        )
        out_dir = tmp_path / "charts"
        results = plot_all(tmp_path, out_dir)
        assert results == []

    def test_smooth_sigma_full_chart_gray_orange(self, tmp_path, long_range_data):
        """smooth_sigma 전체 차트는 일반 차트와 동일하게 회색+주황 2라인으로 표시된다."""
        json_path = _write_json(tmp_path / "LONG01.json", long_range_data)
        out_path = tmp_path / "LONG01_smooth.png"
        fig = plot_series(json_path, out_path, smooth_sigma=2.0)
        ax = fig.axes[0]
        assert len(ax.get_lines()) == 2  # 회색(1년 이전) + 주황(최근 1년)

    def test_smooth_sigma_recent_chart_single_line(self, tmp_path, long_range_data):
        """smooth_sigma 최근 1년 차트는 주황 단일 라인."""
        json_path = _write_json(tmp_path / "LONG01.json", long_range_data)
        out_path = tmp_path / "LONG01_smooth_1y.png"
        fig = plot_series(json_path, out_path, recent_months=12, smooth_sigma=2.0)
        ax = fig.axes[0]
        assert len(ax.get_lines()) == 1


class TestPlotSeriesEdgeCases:
    def test_recent_months_all_filtered_out(self, tmp_path):
        """recent_months 필터 후 데이터가 모두 cutoff 이전이면 빈 차트 생성."""
        # cutoff = dates[-1] - recent_months*30 = 2020-01-02 - 0일 = 2020-01-02
        # 두 날짜 모두 cutoff 이하이므로 filtered가 비게 됨
        data = {
            "series_id": "OLD",
            "title": "Old Data Only",
            "observations": [
                {"date": "2020-01-01", "value": 1.0},
                {"date": "2020-01-02", "value": 2.0},
            ],
        }
        json_path = _write_json(tmp_path / "OLD.json", data)
        out_path = tmp_path / "OLD.png"
        # recent_months=0 → cutoff = dates[-1] - 0일 = 2020-01-02
        # d > cutoff 이 되는 데이터가 없음 → dates, values = [], []
        fig = plot_series(json_path, out_path, recent_months=0)
        assert out_path.exists()
        # 데이터가 없으므로 라인 없음
        assert len(fig.axes[0].get_lines()) == 0

    def test_all_data_within_one_year(self, tmp_path):
        """전체 기간 차트에서 1년 이내 데이터만 있으면 new 라인만."""
        data = {
            "series_id": "NEW",
            "title": "Recent Only",
            "observations": [
                {"date": "2024-11-01", "value": 1.0},
                {"date": "2024-12-01", "value": 2.0},
                {"date": "2025-01-01", "value": 3.0},
            ],
        }
        json_path = _write_json(tmp_path / "NEW.json", data)
        out_path = tmp_path / "NEW.png"
        fig = plot_series(json_path, out_path)  # recent_months=None → 전체
        lines = fig.axes[0].get_lines()
        # old 데이터 없으므로 라인 1개 (new만)
        assert len(lines) == 1

    def test_all_data_before_one_year(self, tmp_path):
        """전체 기간 차트에서 최근 1년 이내 데이터가 없으면 old(회색) 라인만."""
        # dates[-1]이 2020-01-03, one_year_ago = 2019-01-03
        # 모든 날짜 > 2019-01-03 이므로... 아니, <= 체크임
        # old: d <= one_year_ago, new: d > one_year_ago
        # one_year_ago = 2020-01-03 - 365 = 2019-01-03
        # 모든 데이터가 2020년이므로 전부 new → old 빈 → elif new_dates 분기
        # old만 테스트하려면 dates[-1] - 365일 이후 데이터가 없어야 함
        # 즉 모든 데이터가 같은 날짜이고, 그 날짜가 dates[-1] - 365 이하
        # 사실상 단일 포인트에서만 가능: dates[-1] = dates[0], d <= d-365는 False
        # → old만 되려면 모든 d <= dates[-1] - 365여야 함
        # dates[-1] = 2022-01-01, one_year_ago = 2021-01-01
        # d=2020-01-01 <= 2021-01-01 ✓, d=2020-06-01 <= 2021-01-01 ✓,
        # d=2021-01-01 <= 2021-01-01 ✓ (old!)
        # d=2022-01-01 > 2021-01-01 (new)
        # → 마지막 데이터는 항상 new (자기 자신 - 365일보다 크므로)
        # 따라서 old만 되려면 데이터가 1포인트 이하... 아님
        # dates[-1]에서 365일 빼면 one_year_ago. dates[-1] > one_year_ago는 항상 참.
        # 그러므로 dates[-1]은 항상 new에 포함됨 → old_only 분기(105행)에
        # 도달하려면 new_dates가 비어야 하지만 dates[-1]이 항상 new → 불가능.
        #
        # 라인 105는 현재 코드에서 도달 불가능(dead code).
        # 대신 old+new 둘 다 있는 2라인 케이스를 검증한다.
        data = {
            "series_id": "MIXED",
            "title": "Mixed Data",
            "observations": [
                {"date": "2020-01-01", "value": 1.0},
                {"date": "2020-06-01", "value": 2.0},
                {"date": "2021-06-01", "value": 3.0},
                {"date": "2022-01-01", "value": 4.0},
            ],
        }
        json_path = _write_json(tmp_path / "MIXED.json", data)
        out_path = tmp_path / "MIXED.png"
        fig = plot_series(json_path, out_path)
        lines = fig.axes[0].get_lines()
        # old + new 모두 있으므로 2개 라인
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# chart.main
# ---------------------------------------------------------------------------


class TestChartMain:
    def test_main_no_data_dir(self, tmp_path, monkeypatch, capsys):
        """data 디렉토리 없으면 에러 메시지 출력."""
        from fred.chart import main as chart_main

        monkeypatch.chdir(tmp_path)
        chart_main()
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_main_empty_data_dir(self, tmp_path, monkeypatch, capsys):
        """data 디렉토리에 JSON이 없으면 에러 메시지 출력."""
        from fred.chart import main as chart_main

        (tmp_path / "data").mkdir()
        monkeypatch.chdir(tmp_path)
        chart_main()
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_main_generates_charts(self, tmp_path, monkeypatch, capsys):
        """정상 실행 시 차트 생성."""
        from fred.chart import main as chart_main

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        data = {
            "series_id": "X",
            "title": "X Series",
            "observations": [{"date": "2024-01-01", "value": 1.0}],
        }
        (data_dir / "X.json").write_text(json.dumps(data))
        monkeypatch.chdir(tmp_path)
        chart_main()
        captured = capsys.readouterr()
        assert "차트 생성 완료" in captured.out
        assert (tmp_path / "charts" / "X.png").exists()

    def test_if_name_main_guard(self, tmp_path, monkeypatch):
        """if __name__ == '__main__' 가드를 통해 main() 실행."""
        import runpy

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        data = {
            "series_id": "Z",
            "title": "Z Series",
            "observations": [{"date": "2024-01-01", "value": 1.0}],
        }
        (data_dir / "Z.json").write_text(json.dumps(data))
        monkeypatch.chdir(tmp_path)
        runpy.run_module("fred.chart", run_name="__main__")
        assert (tmp_path / "charts" / "Z.png").exists()
