"""한국은행 ECOS API 클라이언트."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

BASE_URL = "http://ecos.bok.or.kr/api/StatisticSearch"

# 분기 → 월 매핑
_QUARTER_TO_MONTH = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10"}


class EcosClient:
    """ECOS API 래퍼. 환경변수 ECOS_API_KEY를 사용한다."""

    def __init__(self) -> None:
        api_key = os.environ.get("ECOS_API_KEY", "")
        if not api_key:
            raise ValueError("ECOS_API_KEY environment variable is not set")
        self._api_key = api_key

    def get_observations(
        self,
        stat_code: str,
        cycle: str,
        start: str,
        end: str,
        item_code: str,
        item_code2: str | None = None,
    ) -> list[dict]:
        """통계 데이터 조회.

        Args:
            stat_code: 통계표 코드 (예: "722Y001")
            cycle: 주기 (D/M/Q/A)
            start: 시작 시점 (YYYYMM, YYYYMMDD, YYYYQ1 등)
            end: 종료 시점
            item_code: 항목 코드 (예: "0101000")
            item_code2: 2차 항목 코드 (선택, 예: "I28A")

        Returns:
            [{"date": "YYYY-MM-DD", "value": float | None}, ...]
        """
        item_path = item_code
        if item_code2:
            item_path = f"{item_code}/{item_code2}"
        url = (
            f"{BASE_URL}/{self._api_key}/json/kr/1/10000"
            f"/{stat_code}/{cycle}/{start}/{end}/{item_path}"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # 에러 응답 처리
        if "RESULT" in data:
            return []

        rows = data.get("StatisticSearch", {}).get("row", [])
        return [_parse_row(row) for row in rows]

    def fetch_all(self, data_dir: str | Path | None = None) -> list[dict]:
        """ECOS_SERIES에 정의된 모든 시리즈를 조회한다.

        Args:
            data_dir: JSON 저장 디렉토리 (None이면 저장하지 않음)

        Returns:
            시리즈 데이터 dict 리스트
        """
        from cache import load_cached

        results: list[dict] = []
        for series in ECOS_SERIES:
            sid = series["series_id"]

            # 캐시 확인
            if data_dir is not None:
                cached = load_cached(Path(data_dir) / f"{sid}.json")
                if cached is not None:
                    results.append(cached)
                    continue

            observations = self.get_observations(
                stat_code=series["stat_code"],
                cycle=series["cycle"],
                start=series["start"],
                end=series["end"],
                item_code=series["item_code"],
                item_code2=series.get("item_code2"),
            )
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


def _parse_time(time_str: str) -> str:
    """ECOS TIME 필드를 YYYY-MM-DD로 변환.

    - YYYYMMDD → YYYY-MM-DD (일별)
    - YYYYMM → YYYY-MM-01 (월별)
    - YYYYQn → YYYY-MM-01 (분기)
    - YYYY → YYYY-01-01 (연간)
    """
    # 분기: 2024Q1 → 2024-01-01
    m = re.match(r"^(\d{4})(Q[1-4])$", time_str)
    if m:
        year, quarter = m.groups()
        month = _QUARTER_TO_MONTH[quarter]
        return f"{year}-{month}-01"

    if len(time_str) == 8 and time_str.isdigit():
        # 일별: 20240301 → 2024-03-01
        return f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]}"

    if len(time_str) == 6 and time_str.isdigit():
        # 월별: 202401 → 2024-01-01
        return f"{time_str[:4]}-{time_str[4:6]}-01"

    if len(time_str) == 4 and time_str.isdigit():
        # 연간: 2024 → 2024-01-01
        return f"{time_str}-01-01"

    return time_str


def _parse_row(row: dict) -> dict:
    """ECOS row를 {date, value} 형식으로 변환."""
    raw = row.get("DATA_VALUE", "-")
    try:
        value = float(raw)
    except (ValueError, TypeError):
        value = None

    return {"date": _parse_time(row["TIME"]), "value": value}


# ---------------------------------------------------------------------------
# 시리즈 정의
# ---------------------------------------------------------------------------

ECOS_SERIES = [
    # 금리
    {
        "stat_code": "722Y001",
        "item_code": "0101000",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "BOK_BASE_RATE",
        "title": "Bank of Korea Base Rate",
        "title_ko": "한국은행 기준금리",
    },
    {
        "stat_code": "817Y002",
        "item_code": "010190000",
        "cycle": "D",
        "start": "20200101",
        "end": "20991231",
        "series_id": "KR_TREASURY_3Y",
        "title": "Korea Treasury Bond 3Y Yield",
        "title_ko": "국고채 3년 금리",
    },
    {
        "stat_code": "817Y002",
        "item_code": "010200000",
        "cycle": "D",
        "start": "20200101",
        "end": "20991231",
        "series_id": "KR_TREASURY_10Y",
        "title": "Korea Treasury Bond 10Y Yield",
        "title_ko": "국고채 10년 금리",
    },
    {
        "stat_code": "817Y002",
        "item_code": "010300000",
        "cycle": "D",
        "start": "20200101",
        "end": "20991231",
        "series_id": "KR_CORP_BOND",
        "title": "Corporate Bond AA- Yield",
        "title_ko": "회사채 AA- 금리",
    },
    # 환율
    {
        "stat_code": "731Y001",
        "item_code": "0000001",
        "cycle": "D",
        "start": "20200101",
        "end": "20991231",
        "series_id": "KRW_USD",
        "title": "KRW/USD Exchange Rate",
        "title_ko": "원/달러 환율",
    },
    {
        "stat_code": "731Y001",
        "item_code": "0000053",
        "cycle": "D",
        "start": "20200101",
        "end": "20991231",
        "series_id": "KRW_CNY",
        "title": "KRW/CNY Exchange Rate",
        "title_ko": "원/위안 환율",
    },
    {
        "stat_code": "731Y001",
        "item_code": "0000002",
        "cycle": "D",
        "start": "20200101",
        "end": "20991231",
        "series_id": "JPY_USD",
        "title": "JPY/USD Exchange Rate",
        "title_ko": "엔/달러 환율",
    },
    # 물가
    {
        "stat_code": "901Y009",
        "item_code": "0",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_CPI",
        "title": "Korea Consumer Price Index",
        "title_ko": "소비자물가지수(CPI)",
    },
    # 통화·유동성
    {
        "stat_code": "101Y004",
        "item_code": "BBHA00",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_M2",
        "title": "Korea M2 Money Supply",
        "title_ko": "M2 통화량",
    },
    # 심리지표
    {
        "stat_code": "511Y002",
        "item_code": "FME",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_CSI",
        "title": "Consumer Sentiment Index",
        "title_ko": "소비자동향지수(CSI)",
    },
    {
        "stat_code": "512Y014",
        "item_code": "99988",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_BSI",
        "title": "Business Survey Index",
        "title_ko": "기업경기실사지수(BSI)",
    },
    {
        "stat_code": "513Y001",
        "item_code": "E1000",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_ESI",
        "title": "Economic Sentiment Index",
        "title_ko": "경제심리지수(ESI)",
    },
    # ------------------------------------------------------------------
    # 고용 (구 KOSIS → ECOS 이관)
    # ------------------------------------------------------------------
    {
        "stat_code": "901Y027",
        "item_code": "I61BC",
        "item_code2": "I28A",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_UNEMPLOYMENT",
        "title": "Korea Unemployment Rate",
        "title_ko": "실업률",
    },
    {
        "stat_code": "901Y027",
        "item_code": "I61BA",
        "item_code2": "I28A",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_EMPLOYED",
        "title": "Korea Employed Persons",
        "title_ko": "취업자 수",
    },
    # ------------------------------------------------------------------
    # 경기
    # ------------------------------------------------------------------
    {
        "stat_code": "901Y025",
        "item_code": "I31A",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_IPI",
        "title": "Korea Industrial Production Index",
        "title_ko": "산업생산지수",
    },
    {
        "stat_code": "901Y033",
        "item_code": "A00",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_RETAIL",
        "title": "Korea All Industry Production Index",
        "title_ko": "전산업생산지수",
    },
    # ------------------------------------------------------------------
    # 물가
    # ------------------------------------------------------------------
    {
        "stat_code": "404Y014",
        "item_code": "*AA",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_PPI",
        "title": "Korea Producer Price Index",
        "title_ko": "생산자물가지수(PPI)",
    },
    # ------------------------------------------------------------------
    # 무역·대외 (경상수지 내 상품수출/수입)
    # ------------------------------------------------------------------
    {
        "stat_code": "301Y017",
        "item_code": "SA110",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_EXPORT",
        "title": "Korea Goods Exports",
        "title_ko": "수출액",
    },
    {
        "stat_code": "301Y017",
        "item_code": "SA120",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_IMPORT",
        "title": "Korea Goods Imports",
        "title_ko": "수입액",
    },
    # ------------------------------------------------------------------
    # 주택
    # ------------------------------------------------------------------
    {
        "stat_code": "901Y062",
        "item_code": "P63A",
        "cycle": "M",
        "start": "200001",
        "end": "209912",
        "series_id": "KR_HOUSING_PRICE",
        "title": "Korea Housing Price Index",
        "title_ko": "주택매매가격지수",
    },
]

TITLE_KO: dict[str, str] = {s["series_id"]: s["title_ko"] for s in ECOS_SERIES}


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(data_dir: str | Path | None = None) -> None:
    """ECOS 데이터 조회 및 저장."""

    if data_dir is None:
        data_dir = Path("data")
    else:
        data_dir = Path(data_dir)

    client = EcosClient()

    # 캐시 상태 미리 확인
    cached_ids = set()
    for series in ECOS_SERIES:
        sid = series["series_id"]
        from cache import is_fresh

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
