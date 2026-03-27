"""FRED 시리즈 데이터를 차트 이미지로 변환."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

matplotlib.use("Agg")

# 한글 폰트 설정
_KO_FONT: str | None = None
for name in [
    "NanumGothic",
    "Noto Sans CJK KR",
    "Noto Sans CJK JP",
    "Malgun Gothic",
    "AppleGothic",
]:
    if any(name in f.name for f in fm.fontManager.ttflist):
        _KO_FONT = name
        break


def load_series_data(json_path: str | Path) -> dict:
    """data/*.json 파일을 로드한다.

    Args:
        json_path: JSON 파일 경로

    Returns:
        {"series_id": str, "title": str, "observations": list[dict]}

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
    """
    path = Path(json_path)
    with path.open() as f:
        return json.load(f)


def plot_series(
    json_path: str | Path,
    output_path: str | Path,
    recent_months: int | None = None,
) -> Figure:
    """단일 시리즈 JSON을 읽어 라인 차트 PNG로 저장한다.

    Args:
        json_path: 입력 JSON 파일 경로
        output_path: 출력 PNG 파일 경로
        recent_months: 최근 N개월만 표시 (None이면 전체)

    Returns:
        생성된 matplotlib Figure 객체
    """
    data = load_series_data(json_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dates: list[datetime] = []
    values: list[float] = []
    for obs in data["observations"]:
        if obs["value"] is not None:
            dates.append(datetime.strptime(obs["date"], "%Y-%m-%d"))
            values.append(obs["value"])

    if recent_months is not None and dates:
        cutoff = dates[-1] - timedelta(days=recent_months * 30)
        filtered = [(d, v) for d, v in zip(dates, values) if d > cutoff]
        if filtered:
            dates = [x[0] for x in filtered]
            values = [x[1] for x in filtered]
        else:
            dates, values = [], []

    fig, ax = plt.subplots(figsize=(12, 5))
    if dates:
        if recent_months is not None:
            # 최근 N개월 차트: 초록색 단일 라인
            ax.plot(dates, values, linewidth=0.8, color="#e85d04")
        else:
            # 전체 기간 차트: 1년 이전 파란색 + 최근 1년 초록색
            one_year_ago = dates[-1] - timedelta(days=365)
            old_dates = [d for d, v in zip(dates, values) if d <= one_year_ago]
            old_values = [v for d, v in zip(dates, values) if d <= one_year_ago]
            new_dates = [d for d, v in zip(dates, values) if d > one_year_ago]
            new_values = [v for d, v in zip(dates, values) if d > one_year_ago]
            # 연결점: old 마지막 + new 첫 번째를 겹쳐서 끊김 방지
            if old_dates and new_dates:
                ax.plot(
                    old_dates + [new_dates[0]],
                    old_values + [new_values[0]],
                    linewidth=0.8,
                    color="#aaaaaa",
                )
                ax.plot(new_dates, new_values, linewidth=0.8, color="#e85d04")
            else:
                ax.plot(new_dates, new_values, linewidth=0.8, color="#e85d04")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=45)
    title_ko = data.get("title_ko")
    if title_ko:
        title_text = f"{title_ko}\n({data['title']})"
        font_props = {"fontfamily": _KO_FONT} if _KO_FONT else {}
        ax.set_title(title_text, **font_props)
    else:
        ax.set_title(f"{data['title']} ({data['series_id']})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return fig


def plot_all(data_dir: str | Path, output_dir: str | Path) -> list[Path]:
    """data_dir 내 모든 JSON 파일에 대해 전체 + 최근 1년 차트를 생성한다.

    Args:
        data_dir: JSON 파일들이 있는 디렉토리
        output_dir: 차트 이미지 출력 디렉토리

    Returns:
        생성된 PNG 파일 경로 리스트
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import re

    results: list[Path] = []
    for json_path in sorted(data_dir.glob("*.json")):
        stem = json_path.stem
        # 파생 파일(_1m, _1y) 및 analysis.json 건너뛰기
        if re.search(r"_\d+[my]$", stem) or stem == "analysis":
            continue
        # 전체 기간 차트
        full_path = output_dir / f"{json_path.stem}.png"
        plot_series(json_path, full_path)
        results.append(full_path)
        # 최근 1년 차트
        recent_path = output_dir / f"{json_path.stem}_1y.png"
        plot_series(json_path, recent_path, recent_months=12)
        results.append(recent_path)
    return results


def main() -> None:
    """data/*.json → charts/*.png 일괄 생성."""
    data_dir = Path("data")
    output_dir = Path("charts")

    if not data_dir.exists():
        print(
            f"Error: {data_dir}/ 디렉토리가 없습니다. 먼저 python -m fred 를 실행하세요."
        )
        return

    json_files = list(data_dir.glob("*.json"))
    if not json_files:
        print(f"Error: {data_dir}/ 에 JSON 파일이 없습니다.")
        return

    results = plot_all(data_dir, output_dir)
    for path in results:
        print(f"  {path}")
    print(f"\n{len(results)}개 차트 생성 완료 → {output_dir}/")


if __name__ == "__main__":
    main()
