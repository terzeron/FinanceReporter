"""파일 기반 캐시 유틸리티.

data/*.json 파일의 신선도를 체크하여 불필요한 API 호출을 방지한다.
기본 TTL은 24시간이며, 만료 시 자동으로 무효화된다.
"""

import json
import time
from pathlib import Path

DEFAULT_MAX_AGE_HOURS = 24


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
