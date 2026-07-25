"""FRED 시리즈 데이터를 차트 이미지로 변환."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
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


def _gaussian_smooth(values: list[float], sigma: float) -> list[float]:
    n = max(int(3 * sigma), 1)
    x = np.arange(-n, n + 1)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    arr = np.array(values, dtype=float)
    padded = np.pad(arr, n, mode="edge")
    return np.convolve(padded, kernel, mode="valid").tolist()


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
    smooth_sigma: float | None = None,
) -> Figure:
    """단일 시리즈 JSON을 읽어 라인 차트 PNG로 저장한다.

    Args:
        json_path: 입력 JSON 파일 경로
        output_path: 출력 PNG 파일 경로
        recent_months: 최근 N개월만 표시 (None이면 전체)
        smooth_sigma: Gaussian 스무딩 sigma (None이면 원본 표시)

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
        if smooth_sigma is not None and len(values) >= 2:
            smoothed = _gaussian_smooth(values, smooth_sigma)
            if recent_months is not None:
                ax.plot(dates, smoothed, linewidth=1.5, color="#e85d04")
            else:
                one_year_ago = dates[-1] - timedelta(days=365)
                old_d = [d for d in dates if d <= one_year_ago]
                old_s = [v for d, v in zip(dates, smoothed) if d <= one_year_ago]
                new_d = [d for d in dates if d > one_year_ago]
                new_s = [v for d, v in zip(dates, smoothed) if d > one_year_ago]
                if old_d and new_d:
                    ax.plot(
                        old_d + [new_d[0]],
                        old_s + [new_s[0]],
                        linewidth=1.5,
                        color="#aaaaaa",
                    )
                    ax.plot(new_d, new_s, linewidth=1.5, color="#e85d04")
                else:
                    ax.plot(
                        new_d or old_d, new_s or old_s, linewidth=1.5, color="#e85d04"
                    )
        elif recent_months is not None:
            # 최근 N개월 차트: 단일 라인
            ax.plot(dates, values, linewidth=0.8, color="#e85d04")
        else:
            # 전체 기간 차트: 1년 이전 회색 + 최근 1년 주황색
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


def plot_all(
    data_dir: str | Path,
    output_dir: str | Path,
    series_order: list[str] | None = None,
    smooth_series: set[str] | None = None,
) -> list[Path]:
    """data_dir 내 모든 JSON 파일에 대해 전체 + 최근 1년 차트를 생성한다.

    Args:
        data_dir: JSON 파일들이 있는 디렉토리
        output_dir: 차트 이미지 출력 디렉토리
        series_order: series_id 순서 목록. 지정하면 해당 순서로 처리하고
                      목록에 없는 파일은 알파벳순으로 뒤에 추가한다.
        smooth_series: 이동평균을 오버레이할 series_id 집합.

    Returns:
        생성된 PNG 파일 경로 리스트
    """
    import re

    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_json = {
        p.stem: p
        for p in data_dir.glob("*.json")
        if not re.search(r"_\d+[my]$", p.stem) and not p.stem.startswith("analysis")
    }

    if series_order:
        ordered = [all_json[sid] for sid in series_order if sid in all_json]
        remaining = sorted(
            p for sid, p in all_json.items() if sid not in set(series_order)
        )
        json_paths = ordered + remaining
    else:
        json_paths = sorted(all_json.values())

    results: list[Path] = []
    for json_path in json_paths:
        with json_path.open() as f:
            raw = json.load(f)
        if not any(o["value"] is not None for o in raw.get("observations", [])):
            continue
        sid = json_path.stem
        sigma = 2.0 if (smooth_series and sid in smooth_series) else None
        full_path = output_dir / f"{sid}.png"
        plot_series(json_path, full_path, smooth_sigma=sigma)
        results.append(full_path)
        recent_path = output_dir / f"{sid}_1y.png"
        plot_series(json_path, recent_path, recent_months=12, smooth_sigma=sigma)
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
