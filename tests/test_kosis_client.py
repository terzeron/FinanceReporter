"""KOSIS (통계청) API 클라이언트 테스트."""

from unittest.mock import patch, MagicMock

import pytest

from kosis.client import KosisClient, KOSIS_SERIES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """API 키가 설정된 KosisClient 인스턴스."""
    monkeypatch.setenv("KOSIS_API_KEY", "test-kosis-key")
    return KosisClient()


def _mock_response(json_data, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


SAMPLE_RESPONSE = [
    {
        "TBL_NM": "경제활동인구총괄",
        "PRD_DE": "202401",
        "TBL_ID": "DT_1DA7012S",
        "ITM_NM": "실업률",
        "DT": "2.8",
        "UNIT_NM": "%",
    },
    {
        "TBL_NM": "경제활동인구총괄",
        "PRD_DE": "202402",
        "TBL_ID": "DT_1DA7012S",
        "ITM_NM": "실업률",
        "DT": "2.7",
        "UNIT_NM": "%",
    },
    {
        "TBL_NM": "경제활동인구총괄",
        "PRD_DE": "202403",
        "TBL_ID": "DT_1DA7012S",
        "ITM_NM": "실업률",
        "DT": "2.6",
        "UNIT_NM": "%",
    },
]


# ---------------------------------------------------------------------------
# API 키 검증
# ---------------------------------------------------------------------------


class TestApiKey:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("KOSIS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="KOSIS_API_KEY"):
            KosisClient()

    def test_empty_api_key_raises(self, monkeypatch):
        monkeypatch.setenv("KOSIS_API_KEY", "")
        with pytest.raises(ValueError, match="KOSIS_API_KEY"):
            KosisClient()

    def test_valid_api_key(self, client):
        assert client is not None


# ---------------------------------------------------------------------------
# get_observations
# ---------------------------------------------------------------------------


class TestGetObservations:
    @patch("kosis.client.requests.get")
    def test_returns_observations(self, mock_get, client):
        """월간 데이터를 observations 리스트로 반환."""
        mock_get.return_value = _mock_response(SAMPLE_RESPONSE)
        result = client.get_observations(
            org_id="101",
            tbl_id="DT_1DA7012S",
            itm_id="T10",
            obj_l1="ALL",
            prd_se="M",
            start="202401",
            end="202403",
        )
        assert len(result) == 3
        assert result[0]["date"] == "2024-01-01"
        assert result[0]["value"] == 2.8

    @patch("kosis.client.requests.get")
    def test_missing_value_is_none(self, mock_get, client):
        """결측치 '-'는 None으로 변환."""
        data = [{"PRD_DE": "202401", "DT": "-"}]
        mock_get.return_value = _mock_response(data)
        result = client.get_observations(
            org_id="101",
            tbl_id="T",
            itm_id="I",
            obj_l1="ALL",
            prd_se="M",
            start="202401",
            end="202401",
        )
        assert result[0]["value"] is None

    @patch("kosis.client.requests.get")
    def test_quarterly_date(self, mock_get, client):
        """분기 데이터 PRD_DE='20241' → '2024-01-01'."""
        data = [{"PRD_DE": "20241", "DT": "1.5"}]
        mock_get.return_value = _mock_response(data)
        result = client.get_observations(
            org_id="301",
            tbl_id="T",
            itm_id="I",
            obj_l1="ALL",
            prd_se="Q",
            start="20241",
            end="20244",
        )
        assert result[0]["date"] == "2024-01-01"

    @patch("kosis.client.requests.get")
    def test_yearly_date(self, mock_get, client):
        """연간 데이터 PRD_DE='2024' → '2024-01-01'."""
        data = [{"PRD_DE": "2024", "DT": "100.0"}]
        mock_get.return_value = _mock_response(data)
        result = client.get_observations(
            org_id="101",
            tbl_id="T",
            itm_id="I",
            obj_l1="ALL",
            prd_se="A",
            start="2024",
            end="2024",
        )
        assert result[0]["date"] == "2024-01-01"

    @patch("kosis.client.requests.get")
    def test_api_params(self, mock_get, client):
        """API 호출 시 필수 파라미터가 포함."""
        mock_get.return_value = _mock_response(SAMPLE_RESPONSE)
        client.get_observations(
            org_id="101",
            tbl_id="DT_1DA7012S",
            itm_id="T10",
            obj_l1="ALL",
            prd_se="M",
            start="202401",
            end="202403",
        )
        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["apiKey"] == "test-kosis-key"
        assert params["orgId"] == "101"
        assert params["tblId"] == "DT_1DA7012S"

    @patch("kosis.client.requests.get")
    def test_error_response_returns_empty(self, mock_get, client):
        """에러 응답 시 빈 리스트."""
        mock_get.return_value = _mock_response({"err": "오류"})
        result = client.get_observations(
            org_id="101",
            tbl_id="T",
            itm_id="I",
            obj_l1="ALL",
            prd_se="M",
            start="202401",
            end="202401",
        )
        assert result == []


# ---------------------------------------------------------------------------
# KOSIS_SERIES 정의 검증
# ---------------------------------------------------------------------------


class TestKosisSeries:
    def test_series_has_required_fields(self):
        for s in KOSIS_SERIES:
            assert "series_id" in s
            assert "title" in s
            assert "title_ko" in s
            assert "org_id" in s
            assert "tbl_id" in s

    def test_contains_key_indicators(self):
        ids = {s["series_id"] for s in KOSIS_SERIES}
        assert "KR_UNEMPLOYMENT" in ids
        assert "KR_EXPORT" in ids


# ---------------------------------------------------------------------------
# fetch_all / main
# ---------------------------------------------------------------------------


class TestFetchAll:
    @patch("kosis.client.requests.get")
    def test_returns_all_series(self, mock_get, client, tmp_path):
        mock_get.return_value = _mock_response(SAMPLE_RESPONSE)
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(KOSIS_SERIES)

    @patch("kosis.client.requests.get")
    def test_uses_cache(self, mock_get, client, tmp_path):
        mock_get.return_value = _mock_response(SAMPLE_RESPONSE)
        client.fetch_all(data_dir=tmp_path)
        mock_get.reset_mock()
        results = client.fetch_all(data_dir=tmp_path)
        assert len(results) == len(KOSIS_SERIES)
        mock_get.assert_not_called()


class TestKosisMain:
    @patch("kosis.client.requests.get")
    def test_main_runs(self, mock_get, monkeypatch, tmp_path, capsys):
        from kosis.client import main as kosis_main

        monkeypatch.setenv("KOSIS_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)
        mock_get.return_value = _mock_response(SAMPLE_RESPONSE)
        kosis_main()
        captured = capsys.readouterr()
        assert "완료" in captured.out
