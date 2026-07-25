"""파일 기반 캐시 유틸리티.

data/*.json 파일의 신선도를 체크하여 불필요한 API 호출을 방지한다.
TTL이 만료되면 자동으로 무효화된다.
"""

import json
import time
from pathlib import Path

# 파이프라인은 매일 정시 cron으로 돈다. TTL이 정확히 24시간이면 체크 시점의
# 파일 나이가 항상 23시간대라 '신선함'으로 판정돼 수집을 건너뛰고, 결국
# 격일로만 갱신된다. 20시간이면 매일 갱신되면서 같은 날 재실행은 캐시를 쓴다.
DEFAULT_MAX_AGE_HOURS = 20


def is_fresh(
    path: str | Path,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> bool:
    """파일이 캐시로서 유효한지 확인한다.

    Args:
        path: 확인할 파일 경로
        max_age_hours: 최대 유효 시간 (시간 단위, 기본 24)

    Returns:
        캐시가 유효하면 True
    """
    path = Path(path)
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < max_age_hours * 3600


def load_cached(
    path: str | Path,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> dict | None:
    """캐시가 유효하면 JSON을 로드하고, 아니면 None을 반환한다.

    Args:
        path: JSON 파일 경로
        max_age_hours: 최대 유효 시간

    Returns:
        캐시된 dict 또는 None
    """
    if not is_fresh(path, max_age_hours=max_age_hours):
        return None
    path = Path(path)
    with path.open() as f:
        return json.load(f)
