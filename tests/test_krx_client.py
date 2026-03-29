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


def _make_trading_df(dates: list[str]) -> pd.DataFrame:
    """pykrx 투자자별 매매 반환 형식의 DataFrame."""
    index = pd.DatetimeIndex(pd.to_datetime(dates), name="날짜")
    return pd.DataFrame(
        {
            "개인": [100, 200, 300],
            "외국인": [-50, -100, -150],
            "기관계": [-50, -100, -150],
        },
        index=index,
    )


def _make_shorting_df(dates: list[str]) -> pd.DataFrame:
    """pykrx 공매도 반환 형식의 DataFrame."""
    index = pd.DatetimeIndex(pd.to_datetime(dates), name="날짜")
    return pd.DataFrame(
        {
            "공매도거래대금": [1000, 2000, 3000],
            "총거래대금": [100000, 200000, 300000],
        },
        index=index,
    )


@pytest.fixture
def sample_yf():
    return _make_yf_df(
        ["2024-01-02", "2024-01-03", "2024-01-04"], [2650.0, 2660.0, 2655.0]
    )


@pytest.fixture
def sample_trading():
    return _make_trading_df(["2024-01-02", "2024-01-03", "2024-01-04"])


@pytest.fixture
def sample_shorting():
    return _make_shorting_df(["2024-01-02", "2024-01-03", "2024-01-04"])


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


# ---------------------------------------------------------------------------
# get_trading_by_investor (pykrx)
# ---------------------------------------------------------------------------


class TestGetTradingByInvestor:
    @patch("krx.client.stock.get_market_trading_value_by_date")
    def test_returns_observations(self, mock_fn, client, sample_trading):
        mock_fn.return_value = sample_trading
        result = client.get_trading_by_investor("KOSPI", "외국인")
        assert len(result) == 3
        assert result[0]["value"] == -50

    @patch("krx.client.stock.get_market_trading_value_by_date")
    def test_unknown_investor_returns_empty(self, mock_fn, client, sample_trading):
        mock_fn.return_value = sample_trading
        result = client.get_trading_by_investor("KOSPI", "존재안함")
        assert result == []


# ---------------------------------------------------------------------------
# get_short_selling (pykrx)
# ---------------------------------------------------------------------------


class TestGetShortSelling:
    @patch("krx.client.stock.get_shorting_value_by_date")
    def test_returns_observations(self, mock_fn, client, sample_shorting):
        mock_fn.return_value = sample_shorting
        result = client.get_short_selling("KOSPI")
        assert len(result) == 3
        assert result[0]["value"] == 1000


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


class TestFetchAll:
    @patch("krx.client.stock.get_shorting_value_by_date")
    @patch("krx.client.stock.get_market_trading_value_by_date")
    @patch("krx.client.yfinance.Ticker")
    def test_returns_all_series(
        self,
        mock_ticker_cls,
        mock_trading,
        mock_shorting,
        client,
        tmp_path,
        sample_yf,
        sample_trading,
        sample_shorting,
    ):
        mock_ticker_cls.return_value.history.return_value = sample_yf
        mock_trading.return_value = sample_trading
        mock_shorting.return_value = sample_shorting
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(KRX_SERIES)

    @patch("krx.client.stock.get_shorting_value_by_date")
    @patch("krx.client.stock.get_market_trading_value_by_date")
    @patch("krx.client.yfinance.Ticker")
    def test_uses_cache(
        self,
        mock_ticker_cls,
        mock_trading,
        mock_shorting,
        client,
        tmp_path,
        sample_yf,
        sample_trading,
        sample_shorting,
    ):
        mock_ticker_cls.return_value.history.return_value = sample_yf
        mock_trading.return_value = sample_trading
        mock_shorting.return_value = sample_shorting
        client.fetch_all(data_dir=tmp_path)
        mock_ticker_cls.reset_mock()
        mock_trading.reset_mock()
        mock_shorting.reset_mock()
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(KRX_SERIES)
        mock_ticker_cls.assert_not_called()
