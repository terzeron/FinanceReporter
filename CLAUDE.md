# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

외부 API(FRED, Yahoo Finance)를 이용해 경제/재무 지표를 수집하고, 차트 이미지를 생성하며, AI 분석과 함께 대시보드 HTML로 배포하는 Python 프로젝트.

## Environment Setup

- **Python**: 3.13, **uv**로 의존성 관리
- **direnv**: `.envrc`가 자동으로 `.venv` 활성화 및 `.env` 로드
- **의존성 추가**: `uv add <패키지>` / 개발용: `uv add --dev <패키지>`

## Commands

```bash
uv run pytest                                # 전체 테스트 (88개)
uv run python main.py --output-dir PATH      # 전체 파이프라인 실행 (데이터→차트→분석→대시보드)
uv run python -m fred                        # FRED 데이터만 수집
uv run python -m yahoo                       # Yahoo Finance 데이터만 수집
uv run python -c "from fred.chart import main; main()"  # 차트만 재생성
```

## Architecture

```
main.py              # 전체 파이프라인 오케스트레이터 (--output-dir 필수)
cache.py             # 파일 기반 캐시 유틸리티 (24시간 TTL 자동 만료)
analysis.py          # 최근 1개월 데이터 추출 + AI 경제 동향 분석
dashboard.py         # index.html 생성 + 차트 이미지 복사
fred/
  __init__.py        # FredClient 공개
  client.py          # FredClient 클래스 + FRED 15개 시리즈 수집
  chart.py           # 차트 생성 (전체+1년 2벌, 파란/초록 색상 구분)
  __main__.py        # python -m fred 엔트리포인트
yahoo/
  __init__.py        # YahooClient 공개
  client.py          # YahooClient 클래스 + Yahoo 5개 시리즈 수집
  __main__.py        # python -m yahoo 엔트리포인트
tests/
  test_client.py     # FRED 클라이언트 테스트 (requests mock)
  test_chart.py      # 차트 모듈 테스트 (tmp_path, 외부 의존 없음)
  test_yahoo_client.py # Yahoo 클라이언트 테스트 (yfinance mock)
  test_cache.py      # 캐시 유틸리티 테스트
  test_analysis.py   # 분석 모듈 테스트 (AI API mock)
  test_dashboard.py  # 대시보드 모듈 테스트
data/                # 중간 데이터 (*.json, *_1m.json, analysis.json)
charts/              # 차트 이미지 (*.png, *_1y.png)
```

## Data Pipeline

1. **데이터 수집**: FRED 15개 + Yahoo 5개 = 20개 시리즈 → `data/{id}.json`
2. **차트 생성**: 시리즈당 전체 + 1년 = 40개 PNG → `charts/`
3. **1개월 추출**: `data/{id}_1m.json` (AI 분석 입력용)
4. **AI 분석**: Claude → ChatGPT → Gemini fallback → `data/analysis.json`
5. **대시보드**: `index.html` + 차트 복사 → 지정 경로

## Key Design Decisions

- **캐싱**: 모든 중간산출물은 24시간 TTL로 자동 만료. `--force` 옵션 없음.
- **차트 색상**: 전체 기간 차트에서 1년 이전 파란색(#1f77b4), 최근 1년 초록색(#2ca02c). 1년 차트는 초록색.
- **차트 제목**: `title_ko` 있으면 "한글 제목\n(영문 제목)" 2줄 표시.
- **파생 파일 구분**: `_1m`, `_1y` 접미사 + `analysis.json`은 원본에서 제외 (정규식 `_\d+[my]$`).
- **AI fallback**: 3개 API 모두 실패 시 정적 fallback 메시지로 대시보드 정상 생성.
- **한글 폰트**: Noto Sans CJK > NanumGothic > Malgun Gothic > AppleGothic 순 자동 탐색.

## Environment Variables

- `FRED_API_KEY`: FRED API 키 (`.env`에서 로드, 미설정 시 `ValueError`)
- `ANTHROPIC_API_KEY`: Claude API 키 (AI 분석용, 선택)
- `OPENAI_API_KEY`: ChatGPT API 키 (AI 분석 fallback, 선택)
- `GOOGLE_API_KEY`: Gemini API 키 (AI 분석 fallback, 선택)
