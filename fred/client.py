"""FRED REST API 클라이언트."""

from __future__ import annotations

import os

import requests

BASE_URL = "https://api.stlouisfed.org/fred/"


class FredClient:
    """FRED API 래퍼. 환경변수 FRED_API_KEY를 사용한다."""

    def __init__(self) -> None:
        api_key = os.environ.get("FRED_API_KEY", "")
        if not api_key:
            raise ValueError("FRED_API_KEY environment variable is not set")
        self._api_key = api_key

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """공통 GET 요청. file_type=json과 api_key를 자동 추가."""
        base_params = {"api_key": self._api_key, "file_type": "json"}
        if params:
            base_params.update(params)
        resp = requests.get(f"{BASE_URL}{endpoint}", params=base_params)
        resp.raise_for_status()
        return resp.json()

    def search_series(self, query: str, limit: int = 1000) -> list[dict]:
        """시리즈 검색.

        Args:
            query: 검색어
            limit: 최대 결과 수 (기본 1000)

        Returns:
            시리즈 메타데이터 dict 리스트
        """
        data = self._get("series/search", {"search_text": query, "limit": limit})
        return data.get("seriess", [])

    def get_series(self, series_id: str) -> dict:
        """단일 시리즈 메타데이터 조회.

        Args:
            series_id: FRED 시리즈 ID (예: "DGS10")

        Returns:
            시리즈 메타데이터 dict
        """
        data = self._get("series", {"series_id": series_id})
        return data["seriess"][0]

    def get_observations(
        self,
        series_id: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> list[dict]:
        """시리즈 관측값 조회.

        Args:
            series_id: FRED 시리즈 ID
            observation_start: 시작일 (YYYY-MM-DD), None이면 전체
            observation_end: 종료일 (YYYY-MM-DD), None이면 전체

        Returns:
            [{"date": "YYYY-MM-DD", "value": float | None}, ...] 리스트
        """
        params: dict = {"series_id": series_id}
        if observation_start is not None:
            params["observation_start"] = observation_start
        if observation_end is not None:
            params["observation_end"] = observation_end

        data = self._get("series/observations", params)
        return [_parse_observation(obs) for obs in data.get("observations", [])]


def _parse_observation(obs: dict) -> dict:
    """FRED 관측값의 value를 float 또는 None으로 변환."""
    raw = obs.get("value", ".")
    try:
        value = float(raw)
    except (ValueError, TypeError):
        value = None
    return {"date": obs["date"], "value": value}


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

EXAMPLE_SERIES = [
    # 기존
    "DGS10",
    "PSAVERT",
    "T10Y2Y",
    "SAHMREALTIME",
    "HNFSEPUSSA",
    # 상 우선순위
    "CPIAUCSL",
    "UNRATE",
    "PAYEMS",
    "T5YIE",
    "DGS2",
    # 중 우선순위
    "NFCI",
    "BAA10Y",
    "UMCSENT",
    "WALCL",
    "M2SL",
]

TITLE_KO: dict[str, str] = {
    "DGS10": "미국 10년물 국채 금리",
    "PSAVERT": "개인저축률",
    "T10Y2Y": "장단기 금리차 (10년-2년)",
    "SAHMREALTIME": "삼 룰 경기침체 지표",
    "HNFSEPUSSA": "신규 주택 판매",
    "CPIAUCSL": "미국 소비자물가지수(CPI)",
    "UNRATE": "미국 실업률",
    "PAYEMS": "미국 비농업 고용자수",
    "T5YIE": "5년 기대인플레이션(브레이크이븐)",
    "DGS2": "미국 2년물 국채 금리",
    "NFCI": "시카고 연은 국가금융여건지수",
    "BAA10Y": "Baa 회사채-10년 국채 스프레드",
    "UMCSENT": "미시간대 소비자심리지수",
    "WALCL": "연준 총자산",
    "M2SL": "M2 통화량",
}


def main(data_dir: str | Path | None = None) -> None:
    """예제 시리즈의 최신 관측값을 출력하고 data/*.json에 저장."""
    import json
    from pathlib import Path

    from cache import load_cached

    client = None
    if data_dir is None:
        data_dir = Path("data")
    else:
        data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    fetched = 0
    cached = 0
    for sid in EXAMPLE_SERIES:
        out_path = data_dir / f"{sid}.json"
        data = load_cached(out_path)
        if data is not None:
            cached += 1
            print(f"{sid}: 캐시 사용")
            continue

        if client is None:
            client = FredClient()
        meta = client.get_series(sid)
        observations = client.get_observations(sid)

        # 최신 관측값 출력
        latest = None
        for obs in reversed(observations):
            if obs["value"] is not None:
                latest = obs
                break
        if latest:
            print(f"{sid} ({meta['title']}): {latest['value']}  [{latest['date']}]")
        else:
            print(f"{sid} ({meta['title']}): no data")

        # JSON 파일 저장
        data = {
            "series_id": sid,
            "title": meta["title"],
            "title_ko": TITLE_KO.get(sid),
            "observations": observations,
        }
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        fetched += 1

    print(f"\n완료: {fetched}개 갱신, {cached}개 캐시 사용 → {data_dir}/")


if __name__ == "__main__":
    main()
