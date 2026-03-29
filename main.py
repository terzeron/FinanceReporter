#!/usr/bin/env python3
"""경제지표 대시보드 생성 파이프라인.

사용법:
    uv run python main.py --output-dir PATH
"""

import os
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
venv_python = here / ".venv" / "bin" / "python"

if not sys.prefix.startswith(str(here)):
    os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])

os.chdir(here)

from dotenv import load_dotenv

load_dotenv(here / ".env")

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="경제지표 대시보드 생성")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="출력 경로 (필수)"
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir

    # 디렉토리 구조: data/us, data/kr, charts/us, charts/kr
    us_data = Path("data/us")
    us_charts = Path("charts/us")
    kr_data = Path("data/kr")
    kr_charts = Path("charts/kr")

    def _run_step(label: str, fn, *args, **kwargs):
        """수집 단계를 실행하고, 실패 시 경고만 출력한다."""
        print("=" * 50)
        print(label)
        print("=" * 50)
        try:
            fn(*args, **kwargs)
        except Exception as e:
            print(f"⚠️  {label} 실패: {e}")
            print("  → 건너뛰고 다음 단계 진행")

    # ===== US 데이터 수집 =====
    from fred.client import main as fred_main

    _run_step("[1/8] FRED 데이터 수집", fred_main, data_dir=us_data)

    print()
    from yahoo.client import main as yahoo_main

    _run_step("[2/8] Yahoo Finance 데이터 수집", yahoo_main, data_dir=us_data)

    # ===== KR 데이터 수집 =====
    print()
    from ecos.client import main as ecos_main

    _run_step("[3/8] ECOS (한국은행) 데이터 수집", ecos_main, data_dir=kr_data)

    print()
    from krx.client import main as krx_main

    _run_step("[4/8] KRX (한국거래소) 데이터 수집", krx_main, data_dir=kr_data)

    # ===== 차트 생성 =====
    print()
    print("=" * 50)
    print("[5/8] US 차트 생성")
    print("=" * 50)
    from fred.chart import plot_all

    us_results = plot_all(us_data, us_charts)
    print(f"{len(us_results)}개 차트 생성 → {us_charts}/")

    print()
    print("=" * 50)
    print("[6/8] KR 차트 생성")
    print("=" * 50)
    kr_results = plot_all(kr_data, kr_charts)
    print(f"{len(kr_results)}개 차트 생성 → {kr_charts}/")

    # ===== AI 분석 =====
    print()
    print("=" * 50)
    print("[7/8] AI 경제 동향 분석")
    print("=" * 50)
    from analysis import extract_all_recent, build_prompt, analyze_with_ai

    # US 분석
    us_recent = extract_all_recent(us_data)
    print(f"US: {len(us_recent)}개 시리즈 최근 데이터 추출")
    us_prompt = build_prompt(us_recent, market="us")
    us_analysis = analyze_with_ai(us_prompt, data_dir=us_data, market="us")
    print(f"US 분석 완료 (제공: {us_analysis['provider']})")

    # KR 분석
    kr_recent = extract_all_recent(kr_data)
    print(f"KR: {len(kr_recent)}개 시리즈 최근 데이터 추출")
    kr_prompt = build_prompt(kr_recent, market="kr")
    kr_analysis = analyze_with_ai(kr_prompt, data_dir=kr_data, market="kr")
    print(f"KR 분석 완료 (제공: {kr_analysis['provider']})")

    # ===== 대시보드 생성 =====
    print()
    print("=" * 50)
    print("[8/8] 탭 대시보드 생성")
    print("=" * 50)
    from dashboard import build_tabbed_dashboard

    index_path = build_tabbed_dashboard(
        output_dir=output_dir,
        us_data_dir=us_data,
        us_charts_dir=us_charts,
        us_analysis=us_analysis,
        kr_data_dir=kr_data,
        kr_charts_dir=kr_charts,
        kr_analysis=kr_analysis,
    )
    print(f"대시보드 생성 완료 → {index_path}")


if __name__ == "__main__":
    main()
