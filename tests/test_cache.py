"""파일 캐시 유틸리티 테스트."""

import json
import os
import time

from cache import is_fresh, load_cached, DEFAULT_MAX_AGE_HOURS


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

    def test_daily_cron_does_not_skip_previous_run(self, tmp_path):
        """전날 같은 시각에 쓴 파일은 stale이어야 한다.

        파이프라인은 매일 정시(07:00) cron으로 돈다. TTL이 정확히 24시간이면
        체크 시점의 파일 나이가 항상 23시간대라 '신선함'으로 판정돼 수집을
        건너뛰고, 결국 격일로만 갱신된다.
        """
        path = tmp_path / "data.json"
        path.write_text("{}")
        yesterday_same_time = time.time() - 23.5 * 3600
        os.utime(path, (yesterday_same_time, yesterday_same_time))
        assert is_fresh(path) is False

    def test_default_ttl_leaves_margin_for_daily_run(self):
        """기본 TTL은 24시간 미만이어야 한다 (cron 시각 흔들림 여유)."""
        assert DEFAULT_MAX_AGE_HOURS < 24

    def test_same_day_rerun_uses_cache(self, tmp_path):
        """같은 날 재실행은 캐시를 쓴다 (수동 재실행 시 불필요한 호출 방지)."""
        path = tmp_path / "data.json"
        path.write_text("{}")
        hours_ago = time.time() - 6 * 3600
        os.utime(path, (hours_ago, hours_ago))
        assert is_fresh(path) is True

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
