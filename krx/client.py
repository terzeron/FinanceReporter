"""KRX (한국거래소) 지수 데이터 클라이언트 — yfinance 래퍼."""

from __future__ import annotations

import json
import math
from pathlib import Path

import yfinance


class KrxClient:
    """KRX 지수 데이터 래퍼. yfinance를 사용한다."""

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

        # yfinance는 장 마감 전 당일 행을 NaN 종가로 반환하는 경우가 있다.
        # 그대로 두면 대시보드 최신값이 None으로 표시되므로 후행 결측치만 버린다.
        while observations and observations[-1]["value"] is None:
            observations.pop()

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

            try:
                if series["fetch_type"] == "index":
                    observations = self.get_index_history(series["symbol"])
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
