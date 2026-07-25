"""경제지표 최근 데이터 추출 및 AI 동향 분석."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from cache import load_cached

FALLBACK_MESSAGE = (
    "<p>AI 분석을 이용할 수 없습니다. 모든 AI API 호출이 실패했습니다.</p>"
)

PROMPT_TEMPLATE = """\
당신은 경제 분석 전문가입니다. 아래는 주요 경제지표의 최근 1개월 추세(그룹별 정리)와 외신 뉴스 요약입니다.

[경제지표 추세 — 그룹별]
{data_summary}

[최근 주요 경제 뉴스 (Reuters, Bloomberg, CNBC, Yahoo Finance, WSJ)]
{news_summary}

위 지표와 뉴스를 바탕으로 경제 동향 분석을 한국어로 정확히 3단락으로 작성하세요.
- 구체적 수치를 나열하지 말고, 방향성(상승·하락·보합)과 흐름 위주로 해석하세요.
- 각 단락은 2~3문장으로 작성하세요.

1단락 (지표 종합 분석): 각 그룹별 지표 흐름을 종합하여 현재 금리·물가·고용·자산시장의 전반적 상태를 해석하세요.
2단락 (뉴스 종합 분석): 외신 뉴스에서 공통적으로 다루는 주요 테마와 시장이 주목하는 이슈를 요약하고, 주요 언론사(Reuters·Bloomberg·CNBC 등)가 각각 어떤 전망을 내놓았는지 한 문장씩 간략히 언급하세요.
3단락 (종합 전망): 지표 흐름과 뉴스 이슈를 함께 고려하여 향후 1개월~1분기 전망과 주의할 리스크를 제시하세요.

HTML 형식으로 3개의 <p> 태그로 작성하세요. 제목 태그는 포함하지 마세요."""

PROMPT_TEMPLATE_KR = """\
당신은 한국 경제 분석 전문가입니다. 아래는 한국 주요 경제지표의 최근 1개월 추세(그룹별 정리)와 외신 뉴스 요약입니다.

[경제지표 추세 — 그룹별]
{data_summary}

[최근 주요 경제 뉴스 (Reuters, Bloomberg, CNBC, Yahoo Finance, WSJ)]
{news_summary}

위 지표와 뉴스를 바탕으로 한국 경제 동향 분석을 한국어로 작성하세요.
- 구체적 수치를 나열하지 말고, 방향성(상승·하락·보합)과 흐름 위주로 해석하세요.
- 각 단락은 2~3문장으로 작성하세요.

1단락 (지표 종합 분석): 각 그룹별 지표 흐름을 종합하여 현재 금리·환율·물가·고용·주식시장의 전반적 상태를 해석하세요.
2단락 (뉴스 종합 분석): 외신 뉴스에서 "한국", "Korea", "Korean" 등 한국을 명시적으로 언급한 기사가 있는 경우에만 작성하세요. 해당 언론사가 한국 경제에 대해 내놓은 전망을 한 문장씩 간략히 언급하세요. 한국을 직접 언급한 외신이 없으면, 글로벌 동향이 한국에 간접적으로 영향을 줄 수 있다는 추론이라도 이 단락은 반드시 생략하세요.
3단락 (종합 전망): 지표 흐름과 뉴스 이슈를 함께 고려하여 통화정책 방향, 시장 흐름, 주의할 리스크를 제시하세요.

HTML 형식으로 <p> 태그로 작성하세요. 2단락을 생략할 경우 2개, 포함할 경우 3개의 <p> 태그로 작성하세요. 제목 태그는 포함하지 마세요."""

# US 시리즈 그룹 (FRED 15개 + Yahoo 7개)
US_SERIES_GROUPS: dict[str, list[str]] = {
    "금리·통화·환율": [
        "DGS2",
        "DGS10",
        "T10Y2Y",
        "TNX",
        "BAA10Y",
        "M2SL",
        "WALCL",
        "NFCI",
        "DXY",
    ],
    "물가·고용·경기": [
        "CPIAUCSL",
        "T5YIE",
        "UNRATE",
        "PAYEMS",
        "PSAVERT",
        "SAHMREALTIME",
    ],
    "심리·시장": ["UMCSENT", "HNFSEPUSSA", "VIX"],
    "천연자원": ["WTI", "GOLD", "SILVER", "COPPER"],
}

# KR 시리즈 그룹 (ECOS 12개 + KOSIS 9개 + KRX 5개)
KR_SERIES_GROUPS: dict[str, list[str]] = {
    "금리·환율·통화": [
        "BOK_BASE_RATE",
        "KR_TREASURY_3Y",
        "KR_TREASURY_10Y",
        "KR_CORP_BOND",
        "KRW_USD",
        "JPY_USD",
        "KRW_CNY",
        "KR_M2",
    ],
    "물가·고용·경기": [
        "KR_CPI",
        "KR_PPI",
        "KR_UNEMPLOYMENT",
        "KR_EMPLOYED",
        "KR_GDP",
        "KR_IPI",
        "KR_RETAIL",
        "KR_EXPORT",
        "KR_IMPORT",
    ],
    "심리·주택": [
        "KR_BSI",
        "KR_CSI",
        "KR_ESI",
        "KR_HOUSING_PRICE",
        "KR_HOUSING_PERMIT",
    ],
    "주식시장": ["KOSPI", "KOSDAQ"],
}


# ---------------------------------------------------------------------------
# 최근 데이터 추출
# ---------------------------------------------------------------------------


def extract_recent_data(
    json_path: str | Path,
    output_path: str | Path,
    days: int = 30,
) -> dict:
    """시리즈 JSON에서 최근 N일 데이터를 추출하여 저장한다.

    Args:
        json_path: 원본 시리즈 JSON 경로
        output_path: 출력 JSON 경로
        days: 추출할 최근 일수 (기본 30)

    Returns:
        추출된 데이터 dict
    """
    path = Path(json_path)
    with path.open() as f:
        data = json.load(f)

    observations = data["observations"]
    if observations:
        last_date = datetime.strptime(observations[-1]["date"], "%Y-%m-%d")
        cutoff = last_date - timedelta(days=days)
        filtered = [
            obs
            for obs in observations
            if datetime.strptime(obs["date"], "%Y-%m-%d") > cutoff
        ]
    else:
        filtered = []

    result = {
        "series_id": data["series_id"],
        "title": data["title"],
        "title_ko": data.get("title_ko"),
        "observations": filtered,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def extract_all_recent(
    data_dir: str | Path,
    days: int = 30,
) -> list[dict]:
    """data_dir 내 원본 JSON에서 최근 데이터를 일괄 추출한다.

    _1m, _1y 등 파생 파일은 건너뛴다.

    Args:
        data_dir: 데이터 디렉토리
        days: 추출할 최근 일수

    Returns:
        추출된 데이터 dict 리스트
    """
    data_dir = Path(data_dir)
    results: list[dict] = []

    for json_path in sorted(data_dir.glob("*.json")):
        stem = json_path.stem
        # 파생 파일 건너뛰기
        if re.search(r"_\d+[my]$", stem) or stem.startswith("analysis"):
            continue

        out_path = data_dir / f"{stem}_1m.json"
        cached = load_cached(out_path)
        if cached is not None:
            results.append(cached)
            continue

        result = extract_recent_data(json_path, out_path, days=days)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# 프롬프트 생성
# ---------------------------------------------------------------------------


def _summarize_series(data: dict) -> str:
    """단일 시리즈의 데이터를 방향성 요약으로 변환."""
    obs = [o for o in data["observations"] if o["value"] is not None]
    if not obs:
        return f"- {data.get('title_ko', data['title'])} ({data['series_id']}): 데이터 없음"

    values = [o["value"] for o in obs]
    name = data.get("title_ko") or data["title"]
    change = values[-1] - values[0]
    pct = (change / abs(values[0]) * 100) if values[0] != 0 else 0
    if abs(pct) < 0.5:
        direction = "보합"
    elif change > 0:
        direction = "상승"
    else:
        direction = "하락"
    return f"- {name} ({data['series_id']}): {direction}"


def _format_grouped_data(
    data_list: list[dict],
    groups: dict[str, list[str]],
) -> str:
    """시리즈를 그룹별로 묶어 프롬프트용 텍스트를 생성한다."""
    by_id = {d["series_id"]: _summarize_series(d) for d in data_list}
    lines: list[str] = []
    assigned: set[str] = set()

    for group_name, series_ids in groups.items():
        group_lines = [
            by_id[sid] for sid in series_ids if sid in by_id and sid not in assigned
        ]
        if group_lines:
            lines.append(f"▶ {group_name}")
            lines.extend(group_lines)
            assigned.update(sid for sid in series_ids if sid in by_id)

    remaining = [by_id[sid] for sid in by_id if sid not in assigned]
    if remaining:
        lines.append("▶ 기타")
        lines.extend(remaining)

    return "\n".join(lines) if lines else "(분석할 데이터가 없습니다)"


def _format_news(news_list: list[dict]) -> str:
    """뉴스 리스트를 프롬프트용 텍스트로 변환."""
    if not news_list:
        return "(최신 외신 뉴스 없음)"
    lines = []
    for article in news_list:
        source = article.get("source", "")
        title = article.get("title", "")
        text = article.get("text") or article.get("summary", "")
        date = article.get("published", "")
        line = f"[{source}] {title}"
        if date:
            line += f" ({date})"
        if text:
            line += f"\n  → {text}"
        lines.append(line)
    return "\n".join(lines)


def build_prompt(
    recent_data_list: list[dict],
    market: str = "us",
    news_list: list[dict] | None = None,
) -> str:
    """최근 데이터 리스트로 AI 분석용 프롬프트를 생성한다.

    Args:
        recent_data_list: extract_all_recent()의 반환값
        market: "us" 또는 "kr"
        news_list: NewsFetcher.fetch_all()의 반환값 (없으면 뉴스 섹션 비움)

    Returns:
        프롬프트 문자열
    """
    template = PROMPT_TEMPLATE_KR if market == "kr" else PROMPT_TEMPLATE
    groups = KR_SERIES_GROUPS if market == "kr" else US_SERIES_GROUPS

    if not recent_data_list:
        data_summary = "(분석할 데이터가 없습니다)"
    else:
        data_summary = _format_grouped_data(recent_data_list, groups)

    news_summary = _format_news(news_list) if news_list else "(최신 외신 뉴스 없음)"
    return template.format(data_summary=data_summary, news_summary=news_summary)


# ---------------------------------------------------------------------------
# AI API 호출
# ---------------------------------------------------------------------------


def _call_claude(prompt: str) -> str:
    """Anthropic Claude API 호출."""
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_chatgpt(prompt: str) -> str:
    """OpenAI ChatGPT API 호출."""
    import openai

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _call_gemini(prompt: str) -> str:
    """Google Gemini API 호출."""
    from google import genai

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text


def _ensure_html(text: str) -> str:
    """응답에 HTML 태그가 없으면 <p>로 감싼다."""
    if "<p>" in text.lower():
        return text
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    return "\n".join(f"<p>{p}</p>" for p in paragraphs)


def analyze_with_ai(
    prompt: str,
    data_dir: str | Path = Path("data"),
    market: str = "us",
) -> dict:
    """AI API로 경제 동향을 분석한다. Claude → ChatGPT → Gemini fallback.

    Args:
        prompt: 분석 프롬프트
        data_dir: analysis.json 캐시 디렉토리
        market: "us" 또는 "kr" (캐시 파일 분리)

    Returns:
        {"provider": str, "content": str, "generated_at": str}
    """
    data_dir = Path(data_dir)
    cache_name = "analysis_kr.json" if market == "kr" else "analysis.json"
    cache_path = data_dir / cache_name

    cached = load_cached(cache_path)
    if cached is not None:
        return cached

    apis = [
        ("claude", _call_claude),
        ("chatgpt", _call_chatgpt),
        ("gemini", _call_gemini),
    ]

    for provider, call_fn in apis:
        try:
            raw = call_fn(prompt)
            content = _ensure_html(raw)
            result = {
                "provider": provider,
                "content": content,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            data_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            return result
        except Exception as e:
            print(f"  ⚠️  {provider} 호출 실패: {type(e).__name__}: {e}")
            continue

    result = {
        "provider": "none",
        "content": FALLBACK_MESSAGE,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return result
