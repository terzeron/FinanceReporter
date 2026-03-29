"""KRX (한국거래소) 데이터 클라이언트 — yfinance + pykrx 래퍼."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import yfinance
from pykrx import stock


class KrxClient:
    """KRX 데이터 래퍼. 지수는 yfinance, 투자자/공매도는 pykrx를 사용한다."""

    def get_index_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> list[dict]:
        """지수 종가를 observations 리스트로 반환 (yfinance 사용).

        Args:
            symbol: Yahoo Finance 티커 (예: "^KS11" = KOSPI)
            period: 조회 기간 (기본 "5y")

        Returns:
            [{"date": "YYYY-MM-DD", "value": float | None}, ...]
        """
        ticker = yfinance.Ticker(symbol)
        df = ticker.history(period=period)

        if df.empty:
            return []

        observations: list[dict] = []
        for date, row in df.iterrows():
            raw = row["Close"]
            value = None if (isinstance(raw, float) and math.isnan(raw)) else float(raw)
            observations.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "value": value,
                }
            )
        return observations

    def get_trading_by_investor(
        self,
        market: str,
        investor: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """투자자별 순매수 금액을 observations 리스트로 반환 (pykrx).

        Args:
            market: "KOSPI" 또는 "KOSDAQ"
            investor: "개인", "외국인", "기관계" 등
            start/end: YYYYMMDD

        Returns:
            [{"date": "YYYY-MM-DD", "value": float}, ...]
        """
        if end is None:
            end = datetime.now().strftime("%Y%m%d")
        if start is None:
            start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        df = stock.get_market_trading_value_by_date(start, end, market)
        if df.empty or investor not in df.columns:
            return []

        observations: list[dict] = []
        for date, row in df.iterrows():
            observations.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "value": float(row[investor]),
                }
            )
        return observations

    def get_short_selling(
        self,
        market: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """공매도 거래대금을 observations 리스트로 반환 (pykrx).

        Args:
            market: "KOSPI" 또는 "KOSDAQ"
            start/end: YYYYMMDD

        Returns:
            [{"date": "YYYY-MM-DD", "value": float}, ...]
        """
        if end is None:
            end = datetime.now().strftime("%Y%m%d")
        if start is None:
            start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        df = stock.get_shorting_value_by_date(start, end, market)
        if df.empty:
            return []

        col = "공매도거래대금" if "공매도거래대금" in df.columns else df.columns[0]
        observations: list[dict] = []
        for date, row in df.iterrows():
            observations.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "value": float(row[col]),
                }
            )
        return observations

    def fetch_all(self, data_dir: str | Path | None = None) -> list[dict]:
        """KRX_SERIES에 정의된 모든 시리즈를 조회한다."""
        from cache import load_cached

        results: list[dict] = []
        for series in KRX_SERIES:
            sid = series["series_id"]

            if data_dir is not None:
                cached = load_cached(Path(data_dir) / f"{sid}.json")
                if cached is not None:
                    results.append(cached)
                    continue

            fetch_type = series["fetch_type"]
            try:
                if fetch_type == "index":
                    observations = self.get_index_history(series["symbol"])
                elif fetch_type == "trading":
                    observations = self.get_trading_by_investor(
                        series["market"], series["investor"]
                    )
                elif fetch_type == "shorting":
                    observations = self.get_short_selling(series["market"])
                else:
                    observations = []
            except Exception as e:
                print(f"  ⚠️  {sid} 수집 실패: {e}")
                observations = []

            data = {
                "series_id": sid,
                "title": series["title"],
                "title_ko": series["title_ko"],
                "observations": observations,
            }
            results.append(data)

        if data_dir is not None:
            data_dir = Path(data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            from cache import load_cached

            for data in results:
                out_path = data_dir / f"{data['series_id']}.json"
                if not out_path.exists() or not load_cached(out_path):
                    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        return results


# ---------------------------------------------------------------------------
# 시리즈 정의
# ---------------------------------------------------------------------------

KRX_SERIES = [
    # 지수 (yfinance)
    {
        "series_id": "KOSPI",
        "title": "KOSPI Index",
        "title_ko": "코스피",
        "fetch_type": "index",
        "symbol": "^KS11",
    },
    {
        "series_id": "KOSDAQ",
        "title": "KOSDAQ Index",
        "title_ko": "코스닥",
        "fetch_type": "index",
        "symbol": "^KQ11",
    },
    # 투자자별 매매 (pykrx)
    {
        "series_id": "KOSPI_FOREIGN",
        "title": "KOSPI Foreign Investor Net Purchase",
        "title_ko": "코스피 외국인 순매수",
        "fetch_type": "trading",
        "market": "KOSPI",
        "investor": "외국인",
    },
    {
        "series_id": "KOSPI_INST",
        "title": "KOSPI Institutional Net Purchase",
        "title_ko": "코스피 기관 순매수",
        "fetch_type": "trading",
        "market": "KOSPI",
        "investor": "기관계",
    },
    # 공매도 (pykrx)
    {
        "series_id": "KOSPI_SHORT",
        "title": "KOSPI Short Selling Amount",
        "title_ko": "코스피 공매도 거래대금",
        "fetch_type": "shorting",
        "market": "KOSPI",
    },
]


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(data_dir: str | Path | None = None) -> None:
    """KRX 데이터 조회 및 저장."""
    from cache import is_fresh

    if data_dir is None:
        data_dir = Path("data")
    else:
        data_dir = Path(data_dir)

    client = KrxClient()

    cached_ids = set()
    for series in KRX_SERIES:
        sid = series["series_id"]
        if is_fresh(data_dir / f"{sid}.json"):
            cached_ids.add(sid)

    results = client.fetch_all(data_dir=data_dir)

    for data in results:
        sid = data["series_id"]
        if sid in cached_ids:
            print(f"{sid}: 캐시 사용")
        else:
            obs = data["observations"]
            if obs:
                latest = obs[-1]
                print(
                    f"{sid} ({data['title_ko']}): {latest['value']}  [{latest['date']}]"
                )
            else:
                print(f"{sid} ({data['title_ko']}): no data")

    fetched = len(results) - len(cached_ids)
    print(f"\n완료: {fetched}개 갱신, {len(cached_ids)}개 캐시 사용 → {data_dir}/")
