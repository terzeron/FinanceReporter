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
    data_dir = Path("data")
    charts_dir = Path("charts")

    # 1. 데이터 수집
    print("=" * 50)
    print("[1/5] FRED 데이터 수집")
    print("=" * 50)
    from fred.client import main as fred_main

    fred_main()

    print()
    print("=" * 50)
    print("[2/5] Yahoo Finance 데이터 수집")
    print("=" * 50)
    from yahoo.client import main as yahoo_main

    yahoo_main()

    # 2. 차트 생성
    print()
    print("=" * 50)
    print("[3/5] 차트 생성")
    print("=" * 50)
    from fred.chart import plot_all

    results = plot_all(data_dir, charts_dir)
    print(f"{len(results)}개 차트 생성 → {charts_dir}/")

    # 3. 최근 1개월 데이터 추출
    print()
    print("=" * 50)
    print("[4/5] AI 경제 동향 분석")
    print("=" * 50)
    from analysis import extract_all_recent, build_prompt, analyze_with_ai

    recent = extract_all_recent(data_dir)
    print(f"{len(recent)}개 시리즈 최근 1개월 데이터 추출")

    prompt = build_prompt(recent)
    analysis = analyze_with_ai(prompt, data_dir=data_dir)
    print(f"분석 완료 (제공: {analysis['provider']})")

    # 4. 대시보드 생성
    print()
    print("=" * 50)
    print("[5/5] 대시보드 생성")
    print("=" * 50)
    from dashboard import build_dashboard

    index_path = build_dashboard(
        output_dir=output_dir,
        data_dir=data_dir,
        charts_dir=charts_dir,
        analysis=analysis,
    )
    print(f"대시보드 생성 완료 → {index_path}")


if __name__ == "__main__":
    main()
