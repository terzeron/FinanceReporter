"""KOSIS (통계청) API 클라이언트."""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests

BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

# KOSIS 분기 → 월 매핑 (5자리: YYYYQ)
_QUARTER_DIGIT_TO_MONTH = {"1": "01", "2": "04", "3": "07", "4": "10"}


class KosisClient:
    """KOSIS API 래퍼. 환경변수 KOSIS_API_KEY를 사용한다."""

    def __init__(self) -> None:
        api_key = os.environ.get("KOSIS_API_KEY", "")
        if not api_key:
            raise ValueError("KOSIS_API_KEY environment variable is not set")
        self._api_key = api_key

    def get_observations(
        self,
        org_id: str,
        tbl_id: str,
        itm_id: str,
        obj_l1: str,
        prd_se: str,
        start: str,
        end: str,
        obj_l2: str | None = None,
    ) -> list[dict]:
        """통계 데이터 조회.

        Args:
            org_id: 기관 코드 (예: "101")
            tbl_id: 통계표 ID (예: "DT_1DA7012S")
            itm_id: 항목 ID
            obj_l1: 분류1 (보통 "ALL")
            prd_se: 주기 (M/Q/A)
            start: 시작 시점
            end: 종료 시점
            obj_l2: 분류2 (선택)

        Returns:
            [{"date": "YYYY-MM-DD", "value": float | None}, ...]
        """
        params = {
            "method": "getList",
            "apiKey": self._api_key,
            "format": "json",
            "jsonVD": "Y",
            "orgId": org_id,
            "tblId": tbl_id,
            "itmId": itm_id,
            "objL1": obj_l1,
            "prdSe": prd_se,
            "startPrdDe": start,
            "endPrdDe": end,
        }
        if obj_l2 is not None:
            params["objL2"] = obj_l2

        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # 에러 응답: dict (정상은 list)
        if isinstance(data, dict):
            return []

        return [_parse_row(row) for row in data]

    def fetch_all(self, data_dir: str | Path | None = None) -> list[dict]:
        """KOSIS_SERIES에 정의된 모든 시리즈를 조회한다."""
        from cache import load_cached

        results: list[dict] = []
        for series in KOSIS_SERIES:
            sid = series["series_id"]

            if data_dir is not None:
                cached = load_cached(Path(data_dir) / f"{sid}.json")
                if cached is not None:
                    results.append(cached)
                    continue

            observations = self.get_observations(
                org_id=series["org_id"],
                tbl_id=series["tbl_id"],
                itm_id=series["itm_id"],
                obj_l1=series["obj_l1"],
                prd_se=series["prd_se"],
                start=series["start"],
                end=series["end"],
                obj_l2=series.get("obj_l2"),
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


def _parse_time(prd_de: str) -> str:
    """KOSIS PRD_DE를 YYYY-MM-DD로 변환.

    - YYYYMM → YYYY-MM-01 (월별)
    - YYYYQ (5자리) → YYYY-MM-01 (분기, Q=1~4)
    - YYYY (4자리) → YYYY-01-01 (연간)
    """
    if len(prd_de) == 6 and prd_de.isdigit():
        return f"{prd_de[:4]}-{prd_de[4:6]}-01"

    if len(prd_de) == 5 and prd_de[:4].isdigit():
        quarter = prd_de[4]
        month = _QUARTER_DIGIT_TO_MONTH.get(quarter, "01")
        return f"{prd_de[:4]}-{month}-01"

    if len(prd_de) == 4 and prd_de.isdigit():
        return f"{prd_de}-01-01"

    return prd_de


def _parse_row(row: dict) -> dict:
    """KOSIS row를 {date, value} 형식으로 변환."""
    raw = row.get("DT", "-")
    try:
        value = float(raw)
    except (ValueError, TypeError):
        value = None

    return {"date": _parse_time(row["PRD_DE"]), "value": value}


# ---------------------------------------------------------------------------
# 시리즈 정의
# ---------------------------------------------------------------------------

KOSIS_SERIES = [
    # 고용
    {
        "series_id": "KR_UNEMPLOYMENT",
        "title": "Korea Unemployment Rate",
        "title_ko": "실업률",
        "org_id": "101",
        "tbl_id": "DT_1DA7012S",
        "itm_id": "T10",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
    {
        "series_id": "KR_EMPLOYED",
        "title": "Korea Employed Persons",
        "title_ko": "취업자 수",
        "org_id": "101",
        "tbl_id": "DT_1DA7012S",
        "itm_id": "T20",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
    # 경기
    {
        "series_id": "KR_IPI",
        "title": "Korea Industrial Production Index",
        "title_ko": "산업생산지수",
        "org_id": "101",
        "tbl_id": "DT_1B0801",
        "itm_id": "T001",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
    {
        "series_id": "KR_RETAIL",
        "title": "Korea Retail Sales Index",
        "title_ko": "소매판매지수",
        "org_id": "101",
        "tbl_id": "DT_1C8015",
        "itm_id": "T001",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
    {
        "series_id": "KR_GDP",
        "title": "Korea GDP Growth Rate",
        "title_ko": "GDP 성장률",
        "org_id": "301",
        "tbl_id": "DT_200Y001",
        "itm_id": "T001",
        "obj_l1": "ALL",
        "prd_se": "Q",
        "start": "20201",
        "end": "20994",
    },
    # 물가
    {
        "series_id": "KR_PPI",
        "title": "Korea Producer Price Index",
        "title_ko": "생산자물가지수(PPI)",
        "org_id": "101",
        "tbl_id": "DT_1WPA001",
        "itm_id": "T001",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
    # 무역·대외
    {
        "series_id": "KR_EXPORT",
        "title": "Korea Exports",
        "title_ko": "수출액",
        "org_id": "101",
        "tbl_id": "DT_1B20001",
        "itm_id": "T001",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
    {
        "series_id": "KR_IMPORT",
        "title": "Korea Imports",
        "title_ko": "수입액",
        "org_id": "101",
        "tbl_id": "DT_1B20001",
        "itm_id": "T002",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
    # 주택
    {
        "series_id": "KR_HOUSING_PERMIT",
        "title": "Korea Housing Permits",
        "title_ko": "주택 인허가",
        "org_id": "116",
        "tbl_id": "DT_116_NEWJH001",
        "itm_id": "T001",
        "obj_l1": "ALL",
        "prd_se": "M",
        "start": "202001",
        "end": "209912",
    },
]


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(data_dir: str | Path | None = None) -> None:
    """KOSIS 데이터 조회 및 저장."""
    from cache import is_fresh

    if data_dir is None:
        data_dir = Path("data")
    else:
        data_dir = Path(data_dir)

    client = KosisClient()

    cached_ids = set()
    for series in KOSIS_SERIES:
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
