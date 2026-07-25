"""ECOS (한국은행 경제통계시스템) API 클라이언트 테스트."""

import json
from unittest.mock import patch, MagicMock

import pytest

from ecos.client import EcosClient, ECOS_SERIES, MAX_ROWS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """API 키가 설정된 EcosClient 인스턴스."""
    monkeypatch.setenv("ECOS_API_KEY", "test-ecos-key")
    return EcosClient()


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """requests.get 반환용 mock Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


SAMPLE_STAT_RESPONSE = {
    "StatisticSearch": {
        "list_total_count": 3,
        "row": [
            {
                "STAT_CODE": "722Y001",
                "STAT_NAME": "한국은행 기준금리",
                "ITEM_CODE1": "0101000",
                "ITEM_NAME1": "한국은행 기준금리",
                "UNIT_NAME": "연%",
                "TIME": "202401",
                "DATA_VALUE": "3.5",
            },
            {
                "STAT_CODE": "722Y001",
                "STAT_NAME": "한국은행 기준금리",
                "ITEM_CODE1": "0101000",
                "ITEM_NAME1": "한국은행 기준금리",
                "UNIT_NAME": "연%",
                "TIME": "202402",
                "DATA_VALUE": "3.5",
            },
            {
                "STAT_CODE": "722Y001",
                "STAT_NAME": "한국은행 기준금리",
                "ITEM_CODE1": "0101000",
                "ITEM_NAME1": "한국은행 기준금리",
                "UNIT_NAME": "연%",
                "TIME": "202403",
                "DATA_VALUE": "3.25",
            },
        ],
    }
}

SAMPLE_DAILY_RESPONSE = {
    "StatisticSearch": {
        "list_total_count": 2,
        "row": [
            {
                "STAT_CODE": "817Y002",
                "TIME": "20240301",
                "DATA_VALUE": "3.25",
            },
            {
                "STAT_CODE": "817Y002",
                "TIME": "20240302",
                "DATA_VALUE": "3.30",
            },
        ],
    }
}


# ---------------------------------------------------------------------------
# API 키 검증
# ---------------------------------------------------------------------------


class TestApiKey:
    def test_missing_api_key_raises(self, monkeypatch):
        """ECOS_API_KEY 미설정 시 ValueError."""
        monkeypatch.delenv("ECOS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ECOS_API_KEY"):
            EcosClient()

    def test_empty_api_key_raises(self, monkeypatch):
        """빈 문자열 API 키도 거부."""
        monkeypatch.setenv("ECOS_API_KEY", "")
        with pytest.raises(ValueError, match="ECOS_API_KEY"):
            EcosClient()

    def test_valid_api_key(self, client):
        """정상 API 키로 인스턴스 생성."""
        assert client is not None


# ---------------------------------------------------------------------------
# get_observations
# ---------------------------------------------------------------------------


class TestGetObservations:
    @patch("ecos.client.requests.get")
    def test_returns_observations(self, mock_get, client):
        """월간 데이터를 observations 리스트로 반환."""
        mock_get.return_value = _mock_response(SAMPLE_STAT_RESPONSE)
        result = client.get_observations("722Y001", "M", "202401", "202412", "0101000")
        assert len(result) == 3
        assert result[0]["date"] == "2024-01-01"
        assert result[0]["value"] == 3.5

    @patch("ecos.client.requests.get")
    def test_daily_date_format(self, mock_get, client):
        """일별 데이터의 날짜가 YYYY-MM-DD 형식."""
        mock_get.return_value = _mock_response(SAMPLE_DAILY_RESPONSE)
        result = client.get_observations(
            "817Y002", "D", "20240301", "20240302", "010190000"
        )
        assert result[0]["date"] == "2024-03-01"
        assert result[1]["date"] == "2024-03-02"

    @patch("ecos.client.requests.get")
    def test_missing_value_is_none(self, mock_get, client):
        """결측치 '-'는 None으로 변환."""
        data = {
            "StatisticSearch": {
                "list_total_count": 1,
                "row": [{"TIME": "202401", "DATA_VALUE": "-"}],
            }
        }
        mock_get.return_value = _mock_response(data)
        result = client.get_observations("722Y001", "M", "202401", "202401", "0101000")
        assert result[0]["value"] is None

    @patch("ecos.client.requests.get")
    def test_api_url_contains_key_and_params(self, mock_get, client):
        """API URL에 키와 파라미터가 올바르게 포함."""
        mock_get.return_value = _mock_response(SAMPLE_STAT_RESPONSE)
        client.get_observations("722Y001", "M", "202401", "202412", "0101000")
        url = mock_get.call_args[0][0]
        assert "test-ecos-key" in url
        assert "722Y001" in url
        assert "/M/" in url
        assert "0101000" in url

    @patch("ecos.client.requests.get")
    def test_row_limit_covers_full_daily_history(self, mock_get, client):
        """조회 건수 상한이 2000년 이후 일별 시리즈를 담을 만큼 커야 한다.

        ECOS는 요청 구간을 앞에서부터 잘라 반환하므로 상한이 모자라면
        가장 최신 데이터가 조용히 누락된다.
        """
        assert MAX_ROWS >= 20000
        mock_get.return_value = _mock_response(SAMPLE_DAILY_RESPONSE)
        client.get_observations("722Y001", "D", "20000101", "20991231", "0101000")
        assert f"/1/{MAX_ROWS}/" in mock_get.call_args[0][0]

    @patch("ecos.client.requests.get")
    def test_empty_response(self, mock_get, client):
        """빈 응답은 빈 리스트 반환."""
        data = {"StatisticSearch": {"list_total_count": 0, "row": []}}
        mock_get.return_value = _mock_response(data)
        result = client.get_observations("722Y001", "M", "202401", "202401", "0101000")
        assert result == []

    @patch("ecos.client.requests.get")
    def test_error_response_raises(self, mock_get, client):
        """ECOS 에러 응답 시 예외 발생."""
        data = {
            "RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}
        }
        mock_get.return_value = _mock_response(data)
        result = client.get_observations("INVALID", "M", "202401", "202401", "0000")
        assert result == []

    @patch("ecos.client.requests.get")
    def test_quarterly_date_format(self, mock_get, client):
        """분기 데이터 TIME='2024Q1' → '2024-01-01' 변환."""
        data = {
            "StatisticSearch": {
                "list_total_count": 1,
                "row": [{"TIME": "2024Q1", "DATA_VALUE": "1.5"}],
            }
        }
        mock_get.return_value = _mock_response(data)
        result = client.get_observations("111Y017", "Q", "2024Q1", "2024Q4", "10111")
        assert result[0]["date"] == "2024-01-01"


# ---------------------------------------------------------------------------
# ECOS_SERIES 정의 검증
# ---------------------------------------------------------------------------


class TestEcosSeries:
    def test_series_has_required_fields(self):
        """각 시리즈에 필수 필드가 있는지 확인."""
        for s in ECOS_SERIES:
            assert "stat_code" in s
            assert "item_code" in s
            assert "cycle" in s
            assert "series_id" in s
            assert "title" in s
            assert "title_ko" in s

    def test_contains_key_indicators(self):
        """주요 지표가 포함되어 있는지 확인."""
        ids = {s["series_id"] for s in ECOS_SERIES}
        assert "BOK_BASE_RATE" in ids
        assert "KR_TREASURY_3Y" in ids
        assert "KRW_USD" in ids
        assert "KR_CPI" in ids
        # 구 KOSIS 이관 지표
        assert "KR_UNEMPLOYMENT" in ids
        assert "KR_EXPORT" in ids
        assert "KR_PPI" in ids

    def test_base_rate_uses_daily_cycle(self):
        """기준금리는 일 주기여야 한다.

        월 주기 시리즈는 해당 월이 끝난 뒤에 공표되므로, 월 중에 이루어진
        기준금리 변경이 다음 달까지 대시보드에 반영되지 않는다.
        """
        base_rate = next(s for s in ECOS_SERIES if s["series_id"] == "BOK_BASE_RATE")
        assert base_rate["cycle"] == "D"

    def test_m2_uses_current_indicator_table(self):
        """M2는 신지표 통계표를 써야 한다.

        구지표(1.7.x, 101Y004 등)는 2004-09에 공표가 끝나 최신 데이터가
        없다. 신지표(1.1.x, 161Y006 = 평잔·원계열)로 조회한다.
        """
        m2 = next(s for s in ECOS_SERIES if s["series_id"] == "KR_M2")
        assert m2["stat_code"] == "161Y006"

    def test_period_format_matches_cycle(self):
        """cycle에 맞는 start/end 포맷을 쓴다 (D=YYYYMMDD, M=YYYYMM)."""
        expected_len = {"D": 8, "M": 6, "A": 4}
        for s in ECOS_SERIES:
            length = expected_len[s["cycle"]]
            for field in ("start", "end"):
                assert len(s[field]) == length, (
                    f"{s['series_id']}: cycle={s['cycle']}인데 "
                    f"{field}={s[field]!r} (길이 {length} 필요)"
                )


# ---------------------------------------------------------------------------
# fetch_all
# ---------------------------------------------------------------------------


class TestFetchAll:
    @patch("ecos.client.requests.get")
    def test_returns_all_series(self, mock_get, client, tmp_path):
        """모든 시리즈 데이터를 가져온다."""
        mock_get.return_value = _mock_response(SAMPLE_STAT_RESPONSE)
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(ECOS_SERIES)
        for data in results:
            assert "series_id" in data
            assert "title" in data
            assert "observations" in data

    @patch("ecos.client.requests.get")
    def test_saves_json_files(self, mock_get, client, tmp_path):
        """data_dir에 JSON 파일 저장."""
        mock_get.return_value = _mock_response(SAMPLE_STAT_RESPONSE)
        client.fetch_all(data_dir=tmp_path)
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == len(ECOS_SERIES)

    @patch("ecos.client.requests.get")
    def test_one_series_failure_does_not_abort_rest(self, mock_get, client, tmp_path):
        """시리즈 1개가 실패해도 나머지는 계속 수집한다."""

        def side_effect(url, timeout=None):
            if "722Y001" in url:
                raise RuntimeError("502 Server Error: Bad Gateway")
            return _mock_response(SAMPLE_STAT_RESPONSE)

        mock_get.side_effect = side_effect
        results = client.fetch_all(data_dir=tmp_path)

        by_id = {d["series_id"]: d for d in results}
        assert "BOK_BASE_RATE" not in by_id
        assert len(results) == len(ECOS_SERIES) - 1
        assert by_id["KR_CPI"]["observations"] != []

    @patch("ecos.client.requests.get")
    def test_failure_does_not_blank_existing_data(self, mock_get, client, tmp_path):
        """실패한 시리즈의 기존 파일을 빈 데이터로 덮어쓰지 않는다.

        덮어쓰면 일시적 장애 한 번에 차트가 통째로 비어버린다.
        """
        import os
        import time

        good = {
            "series_id": "BOK_BASE_RATE",
            "title": "Bank of Korea Base Rate",
            "title_ko": "한국은행 기준금리",
            "observations": [{"date": "2026-07-16", "value": 2.75}],
        }
        path = tmp_path / "BOK_BASE_RATE.json"
        path.write_text(json.dumps(good, ensure_ascii=False))
        stale = time.time() - 48 * 3600
        os.utime(path, (stale, stale))

        def side_effect(url, timeout=None):
            if "722Y001" in url:
                raise RuntimeError("502 Server Error: Bad Gateway")
            return _mock_response(SAMPLE_STAT_RESPONSE)

        mock_get.side_effect = side_effect
        client.fetch_all(data_dir=tmp_path)

        assert json.loads(path.read_text())["observations"] == good["observations"]

    @patch("ecos.client.requests.get")
    def test_uses_cache(self, mock_get, client, tmp_path):
        """캐시 유효 시 API 호출 건너뛴다."""
        mock_get.return_value = _mock_response(SAMPLE_STAT_RESPONSE)
        client.fetch_all(data_dir=tmp_path)
        mock_get.reset_mock()
        # 두 번째 호출 — 캐시 사용
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(ECOS_SERIES)
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestEcosMain:
    @patch("ecos.client.requests.get")
    def test_main_runs(self, mock_get, monkeypatch, tmp_path, capsys):
        """main() 실행 시 결과 출력."""
        from ecos.client import main as ecos_main

        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)
        mock_get.return_value = _mock_response(SAMPLE_STAT_RESPONSE)
        ecos_main()
        captured = capsys.readouterr()
        assert "완료" in captured.out
