"""FRED API Client 테스트 — requests를 mock하여 외부 호출 없이 검증."""

import pytest
from unittest.mock import patch, MagicMock

from fred.client import FredClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """API 키가 설정된 FredClient 인스턴스."""
    monkeypatch.setenv("FRED_API_KEY", "test-api-key")
    return FredClient()


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """requests.get 반환용 mock Response 생성."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# API 키 검증
# ---------------------------------------------------------------------------


class TestApiKey:
    def test_missing_api_key_raises(self, monkeypatch):
        """FRED_API_KEY 미설정 시 ValueError 발생."""
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with pytest.raises(ValueError, match="FRED_API_KEY"):
            FredClient()

    def test_empty_api_key_raises(self, monkeypatch):
        """빈 문자열 API 키도 거부."""
        monkeypatch.setenv("FRED_API_KEY", "")
        with pytest.raises(ValueError, match="FRED_API_KEY"):
            FredClient()

    def test_valid_api_key(self, client):
        """정상 API 키로 인스턴스 생성."""
        assert client is not None


# ---------------------------------------------------------------------------
# search_series
# ---------------------------------------------------------------------------


class TestSearchSeries:
    SEARCH_RESPONSE = {
        "seriess": [
            {
                "id": "DGS10",
                "title": "10-Year Treasury Constant Maturity Rate",
                "frequency": "Daily",
            },
            {
                "id": "DGS30",
                "title": "30-Year Treasury Constant Maturity Rate",
                "frequency": "Daily",
            },
        ]
    }

    @patch("fred.client.requests.get")
    def test_returns_list_of_series(self, mock_get, client):
        """검색 결과를 시리즈 dict 리스트로 반환."""
        mock_get.return_value = _mock_response(self.SEARCH_RESPONSE)
        result = client.search_series("treasury")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "DGS10"

    @patch("fred.client.requests.get")
    def test_passes_query_and_limit(self, mock_get, client):
        """query와 limit이 요청 파라미터에 포함되는지 확인."""
        mock_get.return_value = _mock_response(self.SEARCH_RESPONSE)
        client.search_series("treasury", limit=50)
        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["search_text"] == "treasury"
        assert params["limit"] == 50
        assert params["file_type"] == "json"
        assert params["api_key"] == "test-api-key"

    @patch("fred.client.requests.get")
    def test_default_limit_is_1000(self, mock_get, client):
        """limit 기본값이 1000."""
        mock_get.return_value = _mock_response(self.SEARCH_RESPONSE)
        client.search_series("treasury")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["limit"] == 1000

    @patch("fred.client.requests.get")
    def test_empty_results(self, mock_get, client):
        """검색 결과 없을 때 빈 리스트 반환."""
        mock_get.return_value = _mock_response({"seriess": []})
        result = client.search_series("xyznonexistent")
        assert result == []

    @patch("fred.client.requests.get")
    def test_http_error_propagates(self, mock_get, client):
        """HTTP 에러 시 예외 전파."""
        mock_get.return_value = _mock_response({}, status_code=500)
        with pytest.raises(Exception, match="HTTP 500"):
            client.search_series("treasury")


# ---------------------------------------------------------------------------
# get_series
# ---------------------------------------------------------------------------


class TestGetSeries:
    SERIES_RESPONSE = {
        "seriess": [
            {
                "id": "DGS10",
                "title": "10-Year Treasury Constant Maturity Rate",
                "frequency": "Daily",
                "units": "Percent",
                "seasonal_adjustment": "Not Seasonally Adjusted",
            }
        ]
    }

    @patch("fred.client.requests.get")
    def test_returns_series_dict(self, mock_get, client):
        """단일 시리즈 메타데이터를 dict로 반환."""
        mock_get.return_value = _mock_response(self.SERIES_RESPONSE)
        result = client.get_series("DGS10")
        assert isinstance(result, dict)
        assert result["id"] == "DGS10"
        assert result["title"] == "10-Year Treasury Constant Maturity Rate"

    @patch("fred.client.requests.get")
    def test_passes_series_id_param(self, mock_get, client):
        """series_id가 요청 파라미터에 포함."""
        mock_get.return_value = _mock_response(self.SERIES_RESPONSE)
        client.get_series("DGS10")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["series_id"] == "DGS10"

    @patch("fred.client.requests.get")
    def test_http_error_propagates(self, mock_get, client):
        """존재하지 않는 시리즈 → HTTP 에러 전파."""
        mock_get.return_value = _mock_response({}, status_code=400)
        with pytest.raises(Exception):
            client.get_series("INVALID_ID")


# ---------------------------------------------------------------------------
# get_observations
# ---------------------------------------------------------------------------


class TestGetObservations:
    OBS_RESPONSE = {
        "observations": [
            {"date": "2024-01-01", "value": "4.25"},
            {"date": "2024-01-02", "value": "4.30"},
            {"date": "2024-01-03", "value": "."},
        ]
    }

    @patch("fred.client.requests.get")
    def test_returns_list_of_observations(self, mock_get, client):
        """관측값을 dict 리스트로 반환."""
        mock_get.return_value = _mock_response(self.OBS_RESPONSE)
        result = client.get_observations("DGS10")
        assert isinstance(result, list)
        assert len(result) == 3

    @patch("fred.client.requests.get")
    def test_numeric_values_converted_to_float(self, mock_get, client):
        """숫자 문자열은 float로 변환."""
        mock_get.return_value = _mock_response(self.OBS_RESPONSE)
        result = client.get_observations("DGS10")
        assert result[0]["value"] == 4.25
        assert result[1]["value"] == 4.30
        assert isinstance(result[0]["value"], float)

    @patch("fred.client.requests.get")
    def test_missing_value_converted_to_none(self, mock_get, client):
        """결측치 '.'은 None으로 변환."""
        mock_get.return_value = _mock_response(self.OBS_RESPONSE)
        result = client.get_observations("DGS10")
        assert result[2]["value"] is None

    @patch("fred.client.requests.get")
    def test_date_preserved_as_string(self, mock_get, client):
        """날짜는 YYYY-MM-DD 문자열 유지."""
        mock_get.return_value = _mock_response(self.OBS_RESPONSE)
        result = client.get_observations("DGS10")
        assert result[0]["date"] == "2024-01-01"

    @patch("fred.client.requests.get")
    def test_date_range_params(self, mock_get, client):
        """observation_start/end가 파라미터에 포함."""
        mock_get.return_value = _mock_response(self.OBS_RESPONSE)
        client.get_observations(
            "DGS10", observation_start="2024-01-01", observation_end="2024-12-31"
        )
        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["observation_start"] == "2024-01-01"
        assert params["observation_end"] == "2024-12-31"

    @patch("fred.client.requests.get")
    def test_date_range_omitted_when_none(self, mock_get, client):
        """날짜 미지정 시 파라미터에 포함하지 않음."""
        mock_get.return_value = _mock_response(self.OBS_RESPONSE)
        client.get_observations("DGS10")
        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert "observation_start" not in params
        assert "observation_end" not in params

    @patch("fred.client.requests.get")
    def test_empty_observations(self, mock_get, client):
        """관측값 없을 때 빈 리스트 반환."""
        mock_get.return_value = _mock_response({"observations": []})
        result = client.get_observations("DGS10")
        assert result == []

    @patch("fred.client.requests.get")
    def test_all_missing_values(self, mock_get, client):
        """모든 값이 결측치인 경우."""
        data = {
            "observations": [
                {"date": "2024-01-01", "value": "."},
                {"date": "2024-01-02", "value": "."},
            ]
        }
        mock_get.return_value = _mock_response(data)
        result = client.get_observations("DGS10")
        assert all(obs["value"] is None for obs in result)


# ---------------------------------------------------------------------------
# fred.client.main
# ---------------------------------------------------------------------------


class TestFredClientMain:
    """fred.client.main() CLI 엔트리포인트 테스트."""

    @patch("fred.client.requests.get")
    def test_fetches_and_saves(self, mock_get, monkeypatch, tmp_path, capsys):
        """데이터를 가져와서 JSON 파일로 저장."""
        from fred.client import main as fred_main, EXAMPLE_SERIES

        monkeypatch.setenv("FRED_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)

        # 시리즈 메타 응답
        def mock_get_fn(url, params=None):
            if "series/observations" in url:
                return _mock_response(
                    {
                        "observations": [
                            {"date": "2024-01-01", "value": "4.25"},
                        ]
                    }
                )
            elif "series/search" in url:
                return _mock_response({"seriess": []})
            else:
                # series 메타
                sid = params.get("series_id", "UNKNOWN")
                return _mock_response(
                    {
                        "seriess": [
                            {
                                "id": sid,
                                "title": f"Title {sid}",
                            }
                        ]
                    }
                )

        mock_get.side_effect = mock_get_fn

        fred_main()

        captured = capsys.readouterr()
        assert "완료" in captured.out
        # 최소 1개 파일 생성 확인
        data_dir = tmp_path / "data"
        assert data_dir.exists()
        json_files = list(data_dir.glob("*.json"))
        assert len(json_files) == len(EXAMPLE_SERIES)

    @patch("fred.client.requests.get")
    def test_uses_cache(self, mock_get, monkeypatch, tmp_path, capsys):
        """캐시 유효 시 API 호출 건너뛴다."""
        import json as json_mod
        from fred.client import main as fred_main, EXAMPLE_SERIES

        monkeypatch.setenv("FRED_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)

        # 캐시 파일 미리 생성
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        for sid in EXAMPLE_SERIES:
            data = {
                "series_id": sid,
                "title": f"Title {sid}",
                "title_ko": f"한글 {sid}",
                "observations": [{"date": "2024-01-01", "value": 1.0}],
            }
            (data_dir / f"{sid}.json").write_text(
                json_mod.dumps(data, ensure_ascii=False)
            )

        fred_main()

        captured = capsys.readouterr()
        assert "캐시 사용" in captured.out
        # API 호출 없어야 함
        mock_get.assert_not_called()

    @patch("fred.client.requests.get")
    def test_prints_no_data(self, mock_get, monkeypatch, tmp_path, capsys):
        """모든 관측값이 None이면 'no data' 출력."""
        from fred.client import main as fred_main

        monkeypatch.setenv("FRED_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)

        def mock_get_fn(url, params=None):
            if "series/observations" in url:
                return _mock_response(
                    {
                        "observations": [
                            {"date": "2024-01-01", "value": "."},
                        ]
                    }
                )
            else:
                sid = params.get("series_id", "X")
                return _mock_response(
                    {"seriess": [{"id": sid, "title": f"Title {sid}"}]}
                )

        mock_get.side_effect = mock_get_fn

        fred_main()

        captured = capsys.readouterr()
        assert "no data" in captured.out

    @patch("fred.client.requests.get")
    def test_if_name_main_guard(self, mock_get, monkeypatch, tmp_path):
        """if __name__ == '__main__' 가드를 통해 main() 실행."""
        import runpy

        monkeypatch.setenv("FRED_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)

        def mock_get_fn(url, params=None):
            if "series/observations" in url:
                return _mock_response(
                    {"observations": [{"date": "2024-01-01", "value": "1.0"}]}
                )
            else:
                sid = params.get("series_id", "X")
                return _mock_response(
                    {"seriess": [{"id": sid, "title": f"Title {sid}"}]}
                )

        mock_get.side_effect = mock_get_fn
        runpy.run_module("fred.client", run_name="__main__")
        assert (tmp_path / "data").exists()


class TestFredModuleEntrypoint:
    """python -m fred 엔트리포인트 테스트."""

    @patch("fred.client.requests.get")
    def test_run_as_module(self, mock_get, monkeypatch, tmp_path):
        """python -m fred로 실행."""
        import runpy

        monkeypatch.setenv("FRED_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)

        def mock_get_fn(url, params=None):
            if "series/observations" in url:
                return _mock_response(
                    {"observations": [{"date": "2024-01-01", "value": "1.0"}]}
                )
            else:
                sid = params.get("series_id", "X")
                return _mock_response(
                    {"seriess": [{"id": sid, "title": f"Title {sid}"}]}
                )

        mock_get.side_effect = mock_get_fn
        runpy.run_module("fred", run_name="__main__")
        assert (tmp_path / "data").exists()
