"""KRX (한국거래소) 데이터 클라이언트 테스트 — yfinance/pykrx를 mock."""

from unittest.mock import patch

import pandas as pd
import pytest

from krx.client import KrxClient, KRX_SERIES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_yf_df(dates: list[str], closes: list[float]) -> pd.DataFrame:
    """yfinance history() 반환 형식의 DataFrame."""
    index = pd.DatetimeIndex(pd.to_datetime(dates), name="Date")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 10 for c in closes],
            "Low": [c - 10 for c in closes],
            "Close": closes,
            "Volume": [1000] * len(closes),
        },
        index=index,
    )


@pytest.fixture
def sample_yf():
    return _make_yf_df(
        ["2024-01-02", "2024-01-03", "2024-01-04"], [2650.0, 2660.0, 2655.0]
    )


@pytest.fixture
def client():
    return KrxClient()


# ---------------------------------------------------------------------------
# get_index_history (yfinance)
# ---------------------------------------------------------------------------


class TestGetIndexHistory:
    @patch("krx.client.yfinance.Ticker")
    def test_returns_observations(self, mock_ticker_cls, client, sample_yf):
        mock_ticker_cls.return_value.history.return_value = sample_yf
        result = client.get_index_history("^KS11")
        assert len(result) == 3
        assert result[0]["date"] == "2024-01-02"
        assert result[0]["value"] == 2650.0

    @patch("krx.client.yfinance.Ticker")
    def test_empty_df(self, mock_ticker_cls, client):
        mock_ticker_cls.return_value.history.return_value = pd.DataFrame()
        result = client.get_index_history("^KS11")
        assert result == []

    @patch("krx.client.yfinance.Ticker")
    def test_drops_trailing_nan_close(self, mock_ticker_cls, client):
        """마지막 미완결 행(Close=NaN)은 버린다.

        yfinance는 장 마감 전 당일 행을 NaN 종가로 반환하는 경우가 있어,
        그대로 두면 대시보드 최신값이 None으로 표시된다.
        """
        df = _make_yf_df(
            ["2024-01-02", "2024-01-03", "2024-01-04"],
            [2650.0, 2660.0, float("nan")],
        )
        mock_ticker_cls.return_value.history.return_value = df
        result = client.get_index_history("^KS11")
        assert len(result) == 2
        assert result[-1]["date"] == "2024-01-03"
        assert result[-1]["value"] == 2660.0

    @patch("krx.client.yfinance.Ticker")
    def test_keeps_interior_nan_close(self, mock_ticker_cls, client):
        """중간 결측치는 유지한다 (차트 연속성 판단은 소비자 몫)."""
        df = _make_yf_df(
            ["2024-01-02", "2024-01-03", "2024-01-04"],
            [2650.0, float("nan"), 2655.0],
        )
        mock_ticker_cls.return_value.history.return_value = df
        result = client.get_index_history("^KS11")
        assert len(result) == 3
        assert result[1]["value"] is None


# ---------------------------------------------------------------------------
# KRX_SERIES / fetch_all
# ---------------------------------------------------------------------------


class TestKrxSeries:
    def test_series_has_required_fields(self):
        for s in KRX_SERIES:
            assert "series_id" in s
            assert "title" in s
            assert "title_ko" in s
            assert "fetch_type" in s

    def test_contains_key_indicators(self):
        ids = {s["series_id"] for s in KRX_SERIES}
        assert "KOSPI" in ids
        assert "KOSDAQ" in ids

    def test_only_index_series_remain(self):
        """투자자별 매매·공매도 지표는 제거됐다 (KRX 로그인 요구로 수집 불가)."""
        ids = {s["series_id"] for s in KRX_SERIES}
        assert ids == {"KOSPI", "KOSDAQ"}
        assert all(s["fetch_type"] == "index" for s in KRX_SERIES)


class TestFetchAll:
    @patch("krx.client.yfinance.Ticker")
    def test_returns_all_series(self, mock_ticker_cls, client, tmp_path, sample_yf):
        mock_ticker_cls.return_value.history.return_value = sample_yf
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(KRX_SERIES)

    @patch("krx.client.yfinance.Ticker")
    def test_uses_cache(self, mock_ticker_cls, client, tmp_path, sample_yf):
        mock_ticker_cls.return_value.history.return_value = sample_yf
        client.fetch_all(data_dir=tmp_path)
        mock_ticker_cls.reset_mock()
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(KRX_SERIES)
        mock_ticker_cls.assert_not_called()
