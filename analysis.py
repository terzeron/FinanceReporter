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
당신은 경제 분석 전문가입니다. 아래는 주요 경제지표의 최근 1개월 데이터입니다.

{data_summary}

위 데이터를 종합적으로 분석하여 다음을 포함하는 경제 동향 분석을 한국어로 작성하세요:
1. 현재 경제 상황 요약 (금리, 변동성, 자산 시장 흐름)
2. 주요 지표 간 상관관계 및 시사점
3. 향후 전망 및 주의할 점
4. 향후 1개월~1분기 경제 전망 (금리 방향, 인플레이션 흐름, 자산시장 시나리오 등 구체적으로)

HTML 형식으로 4개의 <p> 태그로 작성하세요. 제목 태그는 포함하지 마세요."""


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
        if re.search(r"_\d+[my]$", stem) or stem == "analysis":
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
    """단일 시리즈의 데이터를 텍스트 요약으로 변환."""
    obs = [o for o in data["observations"] if o["value"] is not None]
    if not obs:
        return f"- {data.get('title_ko', data['title'])} ({data['series_id']}): 데이터 없음"

    values = [o["value"] for o in obs]
    name = data.get("title_ko") or data["title"]
    return (
        f"- {name} ({data['series_id']}): "
        f"기간 {obs[0]['date']} ~ {obs[-1]['date']}, "
        f"시작 {values[0]:.2f}, 종료 {values[-1]:.2f}, "
        f"최고 {max(values):.2f}, 최저 {min(values):.2f}, "
        f"변동폭 {values[-1] - values[0]:+.2f}"
    )


def build_prompt(recent_data_list: list[dict]) -> str:
    """최근 데이터 리스트로 AI 분석용 프롬프트를 생성한다.

    Args:
        recent_data_list: extract_all_recent()의 반환값

    Returns:
        프롬프트 문자열
    """
    if not recent_data_list:
        return PROMPT_TEMPLATE.format(data_summary="(분석할 데이터가 없습니다)")

    summaries = [_summarize_series(d) for d in recent_data_list]
    return PROMPT_TEMPLATE.format(data_summary="\n".join(summaries))


# ---------------------------------------------------------------------------
# AI API 호출
# ---------------------------------------------------------------------------


def _call_claude(prompt: str) -> str:
    """Anthropic Claude API 호출."""
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
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
) -> dict:
    """AI API로 경제 동향을 분석한다. Claude → ChatGPT → Gemini fallback.

    Args:
        prompt: 분석 프롬프트
        data_dir: analysis.json 캐시 디렉토리

    Returns:
        {"provider": str, "content": str, "generated_at": str}
    """
    data_dir = Path(data_dir)
    cache_path = data_dir / "analysis.json"

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
        except Exception:
            continue

    result = {
        "provider": "none",
        "content": FALLBACK_MESSAGE,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return result
