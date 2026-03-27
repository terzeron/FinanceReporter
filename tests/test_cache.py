"""파일 캐시 유틸리티 테스트."""

import json
import os
import time

from cache import is_fresh, load_cached


# ---------------------------------------------------------------------------
# is_fresh
# ---------------------------------------------------------------------------


class TestIsFresh:
    def test_nonexistent_file_is_not_fresh(self, tmp_path):
        """존재하지 않는 파일 → False."""
        assert is_fresh(tmp_path / "missing.json") is False

    def test_recent_file_is_fresh(self, tmp_path):
        """방금 생성된 파일 → True."""
        path = tmp_path / "data.json"
        path.write_text("{}")
        assert is_fresh(path, max_age_hours=24) is True

    def test_old_file_is_not_fresh(self, tmp_path):
        """max_age_hours를 0으로 설정하면 항상 stale."""
        path = tmp_path / "data.json"
        path.write_text("{}")
        assert is_fresh(path, max_age_hours=0) is False

    def test_expired_file_auto_invalidates(self, tmp_path):
        """24시간 이상 지난 파일은 자동 무효화."""
        path = tmp_path / "data.json"
        path.write_text("{}")
        old_time = time.time() - 25 * 3600
        os.utime(path, (old_time, old_time))
        assert is_fresh(path) is False

    def test_custom_max_age(self, tmp_path):
        """max_age_hours 커스텀 값 적용."""
        path = tmp_path / "data.json"
        path.write_text("{}")
        old_time = time.time() - 2 * 3600
        os.utime(path, (old_time, old_time))
        assert is_fresh(path, max_age_hours=1) is False
        assert is_fresh(path, max_age_hours=3) is True


# ---------------------------------------------------------------------------
# load_cached
# ---------------------------------------------------------------------------


class TestLoadCached:
    def test_loads_cached_json(self, tmp_path):
        """캐시된 JSON 파일 로드."""
        path = tmp_path / "data.json"
        data = {"series_id": "TEST", "value": 42}
        path.write_text(json.dumps(data))
        result = load_cached(path)
        assert result == data

    def test_returns_none_when_not_fresh(self, tmp_path):
        """캐시가 만료되면 None 반환."""
        path = tmp_path / "data.json"
        path.write_text("{}")
        assert load_cached(path, max_age_hours=0) is None

    def test_returns_none_when_missing(self, tmp_path):
        """파일 없으면 None 반환."""
        assert load_cached(tmp_path / "missing.json") is None

    def test_returns_none_when_expired(self, tmp_path):
        """24시간 경과 시 None 반환."""
        path = tmp_path / "data.json"
        path.write_text('{"key": "value"}')
        old_time = time.time() - 25 * 3600
        os.utime(path, (old_time, old_time))
        assert load_cached(path) is None
