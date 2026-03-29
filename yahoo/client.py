"""Yahoo Finance 데이터 클라이언트."""

from __future__ import annotations

import json
import math
from pathlib import Path

import yfinance

SERIES_MAP: dict[str, dict[str, str]] = {
    "^TNX": {
        "series_id": "TNX",
        "title": "10-Year Treasury Yield",
        "title_ko": "미국 10년물 국채 금리",
    },
    "^VIX": {
        "series_id": "VIX",
        "title": "CBOE Volatility Index",
        "title_ko": "변동성 지수",
    },
    "GC=F": {
        "series_id": "GOLD",
        "title": "Gold Futures",
        "title_ko": "금 선물",
    },
    "DX-Y.NYB": {
        "series_id": "DXY",
        "title": "US Dollar Index",
        "title_ko": "달러 인덱스",
    },
    "CL=F": {
        "series_id": "WTI",
        "title": "WTI Crude Oil Futures",
        "title_ko": "WTI 원유 선물",
    },
}


class YahooClient:
    """yfinance 래퍼. FRED 모듈과 동일한 데이터 형식으로 변환한다."""

    def get_history(self, symbol: str, period: str = "1y") -> list[dict]:
        """심볼의 히스토리를 observations 리스트로 반환.

        Args:
            symbol: Yahoo Finance 티커 심볼 (예: "^TNX")
            period: 조회 기간 (기본 "1y")

        Returns:
            [{"date": "YYYY-MM-DD", "value": float | None}, ...]
        """
        ticker = yfinance.Ticker(symbol)
        df = ticker.history(period=period)

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

    def get_series_data(self, symbol: str, period: str = "1y") -> dict:
        """심볼의 데이터를 FRED 호환 형식으로 반환.

        Args:
            symbol: SERIES_MAP에 정의된 Yahoo Finance 티커 심볼
            period: 조회 기간

        Returns:
            {"series_id": str, "title": str, "observations": list[dict]}

        Raises:
            KeyError: SERIES_MAP에 없는 심볼
        """
        info = SERIES_MAP[symbol]
        observations = self.get_history(symbol, period=period)
        return {
            "series_id": info["series_id"],
            "title": info["title"],
            "title_ko": info["title_ko"],
            "observations": observations,
        }

    def fetch_all(
        self,
        period: str = "max",
        data_dir: str | Path | None = None,
    ) -> list[dict]:
        """SERIES_MAP에 정의된 모든 시리즈를 조회한다.

        Args:
            period: 조회 기간
            data_dir: JSON 저장 디렉토리 (None이면 저장하지 않음)

        Returns:
            시리즈 데이터 dict 리스트
        """
        from cache import load_cached

        results: list[dict] = []
        for symbol, info in SERIES_MAP.items():
            sid = info["series_id"]
            # 캐시 확인
            if data_dir is not None:
                cached = load_cached(Path(data_dir) / f"{sid}.json")
                if cached is not None:
                    results.append(cached)
                    continue

            data = self.get_series_data(symbol, period=period)
            results.append(data)

        if data_dir is not None:
            data_dir = Path(data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            for data in results:
                out_path = data_dir / f"{data['series_id']}.json"
                if not out_path.exists() or not load_cached(out_path):
                    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        return results


def main(data_dir: str | Path | None = None) -> None:
    """Yahoo Finance 데이터 조회 및 data/*.json 저장."""
    from cache import is_fresh

    if data_dir is None:
        data_dir = Path("data")
    else:
        data_dir = Path(data_dir)
    client = YahooClient()

    # 캐시 상태 미리 확인 (로그용)
    cached_ids = set()
    for info in SERIES_MAP.values():
        sid = info["series_id"]
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
                print(f"{sid} ({data['title']}): {latest['value']}  [{latest['date']}]")
            else:
                print(f"{sid} ({data['title']}): no data")

    fetched = len(results) - len(cached_ids)
    print(f"\n완료: {fetched}개 갱신, {len(cached_ids)}개 캐시 사용 → {data_dir}/")


if __name__ == "__main__":
    main()
