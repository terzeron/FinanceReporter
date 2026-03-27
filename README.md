# Finance Dashboard

FRED, Yahoo Finance 데이터를 수집하여 경제지표 차트와 AI 분석을 포함한 대시보드를 생성합니다.

## 수집 지표

### FRED (15개)

| series_id    | 한글 제목                        |
| ------------ | -------------------------------- |
| DGS10        | 미국 10년물 국채 금리            |
| DGS2         | 미국 2년물 국채 금리             |
| T10Y2Y       | 장단기 금리차 (10년-2년)         |
| T5YIE        | 5년 기대인플레이션(브레이크이븐) |
| CPIAUCSL     | 미국 소비자물가지수(CPI)         |
| UNRATE       | 미국 실업률                      |
| PAYEMS       | 미국 비농업 고용자수             |
| PSAVERT      | 개인저축률                       |
| SAHMREALTIME | 삼 룰 경기침체 지표              |
| HNFSEPUSSA   | 신규 주택 판매                   |
| NFCI         | 시카고 연은 국가금융여건지수     |
| BAA10Y       | Baa 회사채-10년 국채 스프레드    |
| UMCSENT      | 미시간대 소비자심리지수          |
| WALCL        | 연준 총자산                      |
| M2SL         | M2 통화량                        |

### Yahoo Finance (5개)

| series_id | 심볼     | 한글 제목             |
| --------- | -------- | --------------------- |
| TNX       | ^TNX     | 미국 10년물 국채 금리 |
| VIX       | ^VIX     | 변동성 지수           |
| GOLD      | GC=F     | 금 선물               |
| DXY       | DX-Y.NYB | 달러 인덱스           |
| WTI       | CL=F     | WTI 원유 선물         |

## 설치

```bash
uv sync
```

## 환경 변수 (.env)

```
FRED_API_KEY=your_fred_api_key
ANTHROPIC_API_KEY=your_anthropic_key    # AI 분석용 (선택)
OPENAI_API_KEY=your_openai_key          # fallback (선택)
GOOGLE_API_KEY=your_google_key          # fallback (선택)
```

## 실행

```bash
# 전체 파이프라인: 데이터 수집 → 차트 생성 → AI 분석 → 대시보드
uv run python main.py --output-dir ~/public_html/finance

# 개별 실행
uv run python -m fred         # FRED 데이터만 수집
uv run python -m yahoo        # Yahoo Finance 데이터만 수집
```

## 캐싱

모든 중간산출물(`data/*.json`, `data/analysis.json`)은 24시간 TTL로 자동 만료됩니다.
24시간 이내 재실행 시 캐시를 사용하여 API 호출을 건너뜁니다.

## 테스트

```bash
uv run pytest -v   # 88개 테스트
```

## 출력물

- `data/*.json` — 원본 시리즈 데이터
- `data/*_1m.json` — 최근 1개월 데이터 (AI 분석 입력)
- `data/analysis.json` — AI 경제 동향 분석 결과
- `charts/*.png` — 전체 기간 차트 (1년 이전 파란색, 최근 1년 초록색)
- `charts/*_1y.png` — 최근 1년 차트 (초록색)
- `{output-dir}/index.html` — 반응형 대시보드 (AI 분석 + 차트 카드 + 해석 가이드)
