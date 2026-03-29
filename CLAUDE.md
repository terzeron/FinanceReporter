# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

외부 API(FRED, Yahoo Finance, ECOS, KOSIS, KRX)를 이용해 미국·한국 경제/재무 지표를 수집하고, 차트 이미지를 생성하며, AI 분석과 함께 탭 대시보드 HTML로 배포하는 Python 프로젝트.

## Environment Setup

- **Python**: 3.13, **uv**로 의존성 관리
- **direnv**: `.envrc`가 자동으로 `.venv` 활성화 및 `.env` 로드
- **의존성 추가**: `uv add <패키지>` / 개발용: `uv add --dev <패키지>`

## Commands

```bash
uv run pytest                                # 전체 테스트 (168개)
uv run python main.py --output-dir PATH      # 전체 파이프라인 실행 (US+KR 데이터→차트→분석→탭 대시보드)
uv run python -m fred                        # FRED 데이터만 수집
uv run python -m yahoo                       # Yahoo Finance 데이터만 수집
uv run python -m ecos                        # ECOS (한국은행) 데이터만 수집
uv run python -m kosis                       # KOSIS (통계청) 데이터만 수집
uv run python -m krx                         # KRX (한국거래소) 데이터만 수집
uv run python -c "from fred.chart import main; main()"  # 차트만 재생성
```

## Architecture

```
main.py              # 전체 파이프라인 오케스트레이터 (--output-dir 필수, 9단계)
cache.py             # 파일 기반 캐시 유틸리티 (24시간 TTL 자동 만료)
analysis.py          # 최근 1개월 데이터 추출 + AI 경제 동향 분석 (US/KR 분리)
dashboard.py         # 탭 대시보드 HTML 생성 (US/KR 탭) + 차트 이미지 복사
fred/
  __init__.py        # FredClient 공개
  client.py          # FredClient 클래스 + FRED 15개 시리즈 수집
  chart.py           # 차트 생성 (전체+1년 2벌, 색상 구분) — 범용 모듈
  __main__.py        # python -m fred 엔트리포인트
yahoo/
  __init__.py        # YahooClient 공개
  client.py          # YahooClient 클래스 + Yahoo 5개 시리즈 수집
  __main__.py        # python -m yahoo 엔트리포인트
ecos/
  __init__.py        # EcosClient 공개
  client.py          # EcosClient 클래스 + ECOS 12개 시리즈 수집 (금리, 환율, CPI, M2, 심리지표)
  __main__.py        # python -m ecos 엔트리포인트
kosis/
  __init__.py        # KosisClient 공개
  client.py          # KosisClient 클래스 + KOSIS 9개 시리즈 수집 (고용, 경기, 물가, 무역, 주택)
  __main__.py        # python -m kosis 엔트리포인트
krx/
  __init__.py        # KrxClient 공개
  client.py          # KrxClient 클래스 + KRX 5개 시리즈 수집 (KOSPI, KOSDAQ, 투자자별, 공매도)
  __main__.py        # python -m krx 엔트리포인트
tests/
  test_client.py     # FRED 클라이언트 테스트 (requests mock)
  test_chart.py      # 차트 모듈 테스트 (tmp_path, 외부 의존 없음)
  test_yahoo_client.py # Yahoo 클라이언트 테스트 (yfinance mock)
  test_ecos_client.py  # ECOS 클라이언트 테스트 (requests mock)
  test_kosis_client.py # KOSIS 클라이언트 테스트 (requests mock)
  test_krx_client.py   # KRX 클라이언트 테스트 (pykrx mock)
  test_cache.py      # 캐시 유틸리티 테스트
  test_analysis.py   # 분석 모듈 테스트 (AI API mock, US/KR 분리)
  test_dashboard.py  # 대시보드 모듈 테스트 (탭 UI 포함)
data/
  us/                # US 중간 데이터 (FRED + Yahoo JSON)
  kr/                # KR 중간 데이터 (ECOS + KOSIS + KRX JSON)
charts/
  us/                # US 차트 이미지
  kr/                # KR 차트 이미지
```

## Data Pipeline

1. **US 데이터 수집**: FRED 15개 + Yahoo 5개 = 20개 시리즈 → `data/us/{id}.json`
2. **KR 데이터 수집**: ECOS 12개 + KOSIS 9개 + KRX 5개 = 26개 시리즈 → `data/kr/{id}.json`
3. **차트 생성**: 시리즈당 전체 + 1년 = US 40개 + KR 52개 PNG → `charts/us/`, `charts/kr/`
4. **1개월 추출**: `data/{us,kr}/{id}_1m.json` (AI 분석 입력용)
5. **AI 분석**: US/KR 별도 프롬프트·캐시 → `data/us/analysis.json`, `data/kr/analysis_kr.json`
6. **탭 대시보드**: US/KR 탭 `index.html` + 차트 복사 → 지정 경로

## Key Design Decisions

- **캐싱**: 모든 중간산출물은 24시간 TTL로 자동 만료. `--force` 옵션 없음.
- **차트 색상**: 전체 기간 차트에서 1년 이전 회색(#aaaaaa), 최근 1년 주황색(#e85d04). 1년 차트는 주황색.
- **차트 제목**: `title_ko` 있으면 "한글 제목\n(영문 제목)" 2줄 표시.
- **파생 파일 구분**: `_1m`, `_1y` 접미사 + `analysis*.json`은 원본에서 제외.
- **AI fallback**: 3개 API 모두 실패 시 정적 fallback 메시지로 대시보드 정상 생성.
- **한글 폰트**: Noto Sans CJK > NanumGothic > Malgun Gothic > AppleGothic 순 자동 탐색.
- **탭 대시보드**: US 탭(기본 활성) / KR 탭, JavaScript 탭 전환.
- **데이터 분리**: `data/us/`, `data/kr/` 서브디렉토리로 시장별 데이터 격리.

## Environment Variables

- `FRED_API_KEY`: FRED API 키 (`.env`에서 로드, 미설정 시 `ValueError`)
- `ECOS_API_KEY`: 한국은행 ECOS API 키 (KR 수집용, 미설정 시 `ValueError`)
- `KOSIS_API_KEY`: 통계청 KOSIS API 키 (KR 수집용, 미설정 시 `ValueError`)
- `ANTHROPIC_API_KEY`: Claude API 키 (AI 분석용, 선택)
- `OPENAI_API_KEY`: ChatGPT API 키 (AI 분석 fallback, 선택)
- `GOOGLE_API_KEY`: Gemini API 키 (AI 분석 fallback, 선택)
