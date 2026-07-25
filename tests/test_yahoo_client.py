"""Yahoo Finance 클라이언트 테스트 — yfinance를 mock하여 외부 호출 없이 검증."""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from yahoo.client import YahooClient, SERIES_MAP


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_history_df(dates: list[str], closes: list[float]) -> pd.DataFrame:
    """yfinance history() 반환 형식의 DataFrame 생성."""
    index = pd.DatetimeIndex(pd.to_datetime(dates), name="Date")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes],
            "Close": closes,
            "Volume": [0] * len(closes),
        },
        index=index,
    )


@pytest.fixture
def sample_df():
    """정상 시세 DataFrame."""
    return _make_history_df(
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [4.25, 4.30, 4.28],
    )


@pytest.fixture
def empty_df():
    """빈 DataFrame."""
    return pd.DataFrame(
        columns=["Open", "High", "Low", "Close", "Volume"],
        index=pd.DatetimeIndex([], name="Date"),
    )


@pytest.fixture
def client():
    """YahooClient 인스턴스."""
    return YahooClient()


# ---------------------------------------------------------------------------
# SERIES_MAP 정의 검증
# ---------------------------------------------------------------------------


class TestSeriesMap:
    def test_contains_required_symbols(self):
        """필수 심볼이 정의되어 있는지 확인."""
        assert "^TNX" in SERIES_MAP
        assert "^VIX" in SERIES_MAP
        assert "GC=F" in SERIES_MAP
        assert "SI=F" in SERIES_MAP
        assert "HG=F" in SERIES_MAP

    def test_each_entry_has_required_fields(self):
        """각 항목에 title, title_ko, series_id가 있는지 확인."""
        for symbol, info in SERIES_MAP.items():
            assert "title" in info, f"{symbol} missing title"
            assert "title_ko" in info, f"{symbol} missing title_ko"
            assert "series_id" in info, f"{symbol} missing series_id"


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    @patch("yahoo.client.yfinance.Ticker")
    def test_returns_observations_list(self, mock_ticker_cls, client, sample_df):
        """DataFrame을 observations 리스트로 변환."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        result = client.get_history("^TNX")
        assert len(result) == 3
        assert result[0]["date"] == "2024-01-02"
        assert result[0]["value"] == 4.25

    @patch("yahoo.client.yfinance.Ticker")
    def test_date_format_is_yyyy_mm_dd(self, mock_ticker_cls, client, sample_df):
        """날짜가 YYYY-MM-DD 문자열 형식인지 확인."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        result = client.get_history("^TNX")
        for obs in result:
            assert len(obs["date"]) == 10
            assert obs["date"][4] == "-"

    @patch("yahoo.client.yfinance.Ticker")
    def test_value_is_float(self, mock_ticker_cls, client, sample_df):
        """value가 float 타입인지 확인."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        result = client.get_history("^TNX")
        assert all(isinstance(obs["value"], float) for obs in result)

    @patch("yahoo.client.yfinance.Ticker")
    def test_empty_history_returns_empty_list(self, mock_ticker_cls, client, empty_df):
        """빈 DataFrame → 빈 리스트."""
        mock_ticker_cls.return_value.history.return_value = empty_df
        result = client.get_history("^TNX")
        assert result == []

    @patch("yahoo.client.yfinance.Ticker")
    def test_passes_period_parameter(self, mock_ticker_cls, client, sample_df):
        """period 파라미터가 yfinance에 전달되는지 확인."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        client.get_history("^TNX", period="5y")
        mock_ticker_cls.return_value.history.assert_called_once_with(period="5y")

    @patch("yahoo.client.yfinance.Ticker")
    def test_default_period_is_1y(self, mock_ticker_cls, client, sample_df):
        """기본 period가 1y인지 확인."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        client.get_history("^TNX")
        mock_ticker_cls.return_value.history.assert_called_once_with(period="1y")

    @patch("yahoo.client.yfinance.Ticker")
    def test_nan_values_converted_to_none(self, mock_ticker_cls, client):
        """NaN 값은 None으로 변환."""
        df = _make_history_df(["2024-01-02", "2024-01-03"], [4.25, float("nan")])
        mock_ticker_cls.return_value.history.return_value = df
        result = client.get_history("^TNX")
        assert result[0]["value"] == 4.25
        assert result[1]["value"] is None


# ---------------------------------------------------------------------------
# get_series_data
# ---------------------------------------------------------------------------


class TestGetSeriesData:
    @patch("yahoo.client.yfinance.Ticker")
    def test_returns_fred_compatible_format(self, mock_ticker_cls, client, sample_df):
        """FRED 호환 형식 (series_id, title, observations) 반환."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        result = client.get_series_data("^TNX")
        assert "series_id" in result
        assert "title" in result
        assert "observations" in result
        assert result["series_id"] == SERIES_MAP["^TNX"]["series_id"]
        assert result["title"] == SERIES_MAP["^TNX"]["title"]
        assert result["title_ko"] == SERIES_MAP["^TNX"]["title_ko"]

    @patch("yahoo.client.yfinance.Ticker")
    def test_observations_match_history(self, mock_ticker_cls, client, sample_df):
        """observations가 get_history 결과와 일치."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        result = client.get_series_data("^TNX")
        assert len(result["observations"]) == 3

    @patch("yahoo.client.yfinance.Ticker")
    def test_unknown_symbol_raises(self, mock_ticker_cls, client):
        """SERIES_MAP에 없는 심볼 → KeyError."""
        with pytest.raises(KeyError):
            client.get_series_data("INVALID")


# ---------------------------------------------------------------------------
# fetch_all
# ---------------------------------------------------------------------------


class TestFetchAll:
    @patch("yahoo.client.yfinance.Ticker")
    def test_returns_all_series(self, mock_ticker_cls, client, sample_df):
        """모든 시리즈 데이터를 가져온다."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        results = client.fetch_all()
        assert len(results) == len(SERIES_MAP)
        for data in results:
            assert "series_id" in data
            assert "title" in data
            assert "observations" in data

    @patch("yahoo.client.yfinance.Ticker")
    def test_saves_json_files(self, mock_ticker_cls, client, sample_df, tmp_path):
        """data_dir 지정 시 JSON 파일 저장."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        results = client.fetch_all(data_dir=tmp_path)
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == len(SERIES_MAP)

    @patch("yahoo.client.yfinance.Ticker")
    def test_json_file_content_matches(
        self, mock_ticker_cls, client, sample_df, tmp_path
    ):
        """저장된 JSON 내용이 반환값과 일치."""
        mock_ticker_cls.return_value.history.return_value = sample_df
        results = client.fetch_all(data_dir=tmp_path)
        for data in results:
            json_path = tmp_path / f"{data['series_id']}.json"
            loaded = json.loads(json_path.read_text())
            assert loaded["series_id"] == data["series_id"]
            assert loaded["title"] == data["title"]
            assert len(loaded["observations"]) == len(data["observations"])

    @patch("yahoo.client.yfinance.Ticker")
    def test_one_series_failure_does_not_abort_rest(
        self, mock_ticker_cls, client, sample_df, tmp_path
    ):
        """심볼 1개가 실패해도 나머지는 계속 수집한다."""
        broken = next(iter(SERIES_MAP))

        def history_side_effect(*a, **kw):
            if mock_ticker_cls.call_args[0][0] == broken:
                raise RuntimeError("yfinance 일시적 오류")
            return sample_df

        mock_ticker_cls.return_value.history.side_effect = history_side_effect
        results = client.fetch_all(data_dir=tmp_path)

        by_id = {d["series_id"]: d for d in results}
        assert SERIES_MAP[broken]["series_id"] not in by_id
        assert len(results) == len(SERIES_MAP) - 1
        others = [v["series_id"] for k, v in SERIES_MAP.items() if k != broken]
        assert all(by_id[sid]["observations"] for sid in others)

    @patch("yahoo.client.yfinance.Ticker")
    def test_uses_cache(self, mock_ticker_cls, client, sample_df, tmp_path):
        """캐시 유효 시 API 호출 건너뛴다."""
        # 먼저 데이터 저장
        mock_ticker_cls.return_value.history.return_value = sample_df
        client.fetch_all(data_dir=tmp_path)

        # 두 번째 호출 — 캐시에서 로드
        mock_ticker_cls.reset_mock()
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(SERIES_MAP)
        # yfinance Ticker가 호출되지 않아야 함
        mock_ticker_cls.assert_not_called()


# ---------------------------------------------------------------------------
# yahoo.client.main
# ---------------------------------------------------------------------------


class TestYahooClientMain:
    @patch("yahoo.client.yfinance.Ticker")
    def test_main_prints_results(
        self, mock_ticker_cls, tmp_path, sample_df, capsys, monkeypatch
    ):
        """main() 실행 시 결과 출력."""
        from yahoo.client import main as yahoo_main

        monkeypatch.chdir(tmp_path)
        mock_ticker_cls.return_value.history.return_value = sample_df

        yahoo_main()

        captured = capsys.readouterr()
        assert "완료" in captured.out

    @patch("yahoo.client.yfinance.Ticker")
    def test_main_uses_cache(
        self, mock_ticker_cls, tmp_path, sample_df, capsys, monkeypatch
    ):
        """캐시 유효 시 '캐시 사용' 출력."""
        from yahoo.client import main as yahoo_main

        monkeypatch.chdir(tmp_path)
        mock_ticker_cls.return_value.history.return_value = sample_df

        # 첫 실행 — 데이터 저장
        yahoo_main()
        mock_ticker_cls.reset_mock()

        # 두 번째 실행 — 캐시 사용
        yahoo_main()
        captured = capsys.readouterr()
        assert "캐시 사용" in captured.out

    @patch("yahoo.client.yfinance.Ticker")
    def test_main_prints_no_data(
        self, mock_ticker_cls, tmp_path, empty_df, capsys, monkeypatch
    ):
        """관측값 없으면 'no data' 출력."""
        from yahoo.client import main as yahoo_main

        monkeypatch.chdir(tmp_path)
        mock_ticker_cls.return_value.history.return_value = empty_df

        yahoo_main()

        captured = capsys.readouterr()
        assert "no data" in captured.out

    @patch("yahoo.client.yfinance.Ticker")
    def test_if_name_main_guard(
        self, mock_ticker_cls, tmp_path, sample_df, monkeypatch
    ):
        """if __name__ == '__main__' 가드를 통해 main() 실행."""
        import runpy

        monkeypatch.chdir(tmp_path)
        mock_ticker_cls.return_value.history.return_value = sample_df
        runpy.run_module("yahoo.client", run_name="__main__")
        assert (tmp_path / "data").exists()


class TestYahooModuleEntrypoint:
    """python -m yahoo 엔트리포인트 테스트."""

    @patch("yahoo.client.yfinance.Ticker")
    def test_run_as_module(self, mock_ticker_cls, tmp_path, sample_df, monkeypatch):
        """python -m yahoo로 실행."""
        import runpy

        monkeypatch.chdir(tmp_path)
        mock_ticker_cls.return_value.history.return_value = sample_df
        runpy.run_module("yahoo", run_name="__main__")
        assert (tmp_path / "data").exists()
