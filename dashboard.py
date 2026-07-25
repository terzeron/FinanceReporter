"""경제지표 대시보드 HTML 생성."""

import json
import shutil
from pathlib import Path

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>경제지표 대시보드</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 16px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ text-align: center; margin-bottom: 24px; font-size: 1.6rem; color: #1a1a1a; }}
.analysis {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.analysis h2 {{ font-size: 1.1rem; margin-bottom: 12px; color: #555; }}
.analysis p {{ margin-bottom: 12px; line-height: 1.7; font-size: 0.95rem; }}
.analysis .meta {{ font-size: 0.8rem; color: #999; margin-top: 8px; }}
.card {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.card h3 {{ font-size: 1rem; margin-bottom: 12px; color: #1a1a1a; }}
.card .guide {{ font-size: 0.85rem; color: #666; margin-top: 8px; line-height: 1.5; }}
.chart-pair {{ display: flex; gap: 12px; }}
.chart-pair img {{ flex: 1; min-width: 0; max-width: 50%; height: auto; border-radius: 8px; border: 1px solid #eee; }}
@media (max-width: 768px) {{
  .chart-pair {{ flex-direction: column; }}
  .chart-pair img {{ max-width: 100%; }}
  body {{ padding: 8px; }}
  h1 {{ font-size: 1.3rem; }}
}}
footer {{ text-align: center; color: #999; font-size: 0.8rem; margin-top: 32px; padding: 16px; }}
</style>
</head>
<body>
<div class="container">
<h1>경제지표 대시보드</h1>

<div class="analysis">
<h2>AI 경제 동향 분석</h2>
{analysis_content}
<div class="meta">분석 제공: {provider} | 생성: {generated_at}</div>
</div>

{cards}

<footer>경제지표 대시보드 — 데이터: FRED, Yahoo Finance</footer>
</div>
</body>
</html>"""

CARD_TEMPLATE = """\
<div class="card">
<h3>{title_ko} ({title})</h3>
<div class="chart-pair">
<img src="charts/{series_id}.png?v={cache_bust}" alt="{title_ko} 전체 기간">
<img src="charts/{series_id}_1y.png?v={cache_bust}" alt="{title_ko} 최근 1년">
</div>
<p class="guide">{guide}</p>
</div>"""

CHART_GUIDES: dict[str, str] = {
    "DGS10": "▲ 상승 → 채권 가격 하락, 대출금리 상승 압력\n▼ 하락 → 안전자산 선호 또는 경기 둔화 기대",
    "DGS2": "▲ 급등 → 추가 긴축 기대, 기준금리 인상 전망\n▼ 급락 → 금리 인하 기대, 경기 둔화 반영",
    "T10Y2Y": "▲ 양(+) → 정상 수익률 곡선, 경기 확장 신호\n▼ 음(-)/역전 → 경기침체 선행 신호, 0 근처는 경계 구간",
    "T5YIE": "▲ 상승 → 시장의 인플레이션 기대 확대, 2% 초과 시 금리 인상 압력\n▼ 하락 → 인플레이션 기대 완화, 디플레이션 우려 가능",
    "PSAVERT": "▲ 상승 → 소비 위축·불안심리, 경기 둔화 가능성\n▼ 하락 → 소비 확대 또는 실질소득 감소",
    "SAHMREALTIME": "▲ 0.5 이상 → 경기침체 신호 (삼 룰 발동)\n▼ 낮을수록 → 고용시장 안정, 경기 확장 지속",
    "HNFSEPUSSA": "▲ 증가 → 주택 공급 과잉 또는 수요 둔화\n▼ 감소 → 수요 강세 또는 공급 부족",
    "CPIAUCSL": "▲ 가속 상승 → 인플레이션 압력, 금리 인상 요인\n▼ 둔화·하락 → 물가 안정, 금리 인하 여건 조성",
    "UNRATE": "▲ 상승 → 고용 악화, 경기 둔화\n▼ 하락 → 노동시장 개선, 삼 룰과 함께 해석",
    "PAYEMS": "▲ 20만+ 증가 → 건강한 고용, 경기 확장\n▼ 10만 미만 증가 → 둔화 신호, 경기 정점 가능성",
    "NFCI": "▲ 양(+) → 금융여건 긴축, 신용 스트레스 경고\n▼ 음(-) → 금융여건 완화, 유동성 풍부",
    "BAA10Y": "▲ 확대 → 신용 위험 증가, 기업 자금조달 비용 상승\n▼ 축소 → 시장 안정, 위험선호 심리",
    "UMCSENT": "▲ 상승 → 소비자 낙관, 소비 확대 기대\n▼ 하락 → 비관심리, 소비 위축 가능성",
    "WALCL": "▲ 증가 → 연준 유동성 공급(QE), 위험자산 우호적\n▼ 감소 → 유동성 회수(QT), 위험자산 압박",
    "M2SL": "▲ 급증 → 유동성 과잉, 인플레이션 압력\n▼ 감소 → 유동성 위축, 디레버리징 신호",
    "TNX": "▲ 상승 → DGS10과 동일, 장중 실시간 금리 상승 반영\n▼ 하락 → 안전자산 매수세, 경기 둔화 기대",
    "VIX": "▲ 30 이상 → 시장 공포, 급등 시 단기 바닥 신호일 수도\n▼ 20 이하 → 시장 안정, 낮은 변동성",
    "GOLD": "▲ 상승 → 인플레이션 헤지·안전자산 수요, 달러 약세 동반\n▼ 하락 → 금리 상승·달러 강세 압력, 위험선호",
    "DXY": "▲ 상승 → 달러 강세, 신흥국·원자재 약세 압력\n▼ 하락 → 위험자산·원자재 우호적",
    "WTI": "▲ 상승 → 에너지 인플레이션 압력, CPI 상승 요인\n▼ 하락 → 경기 둔화 또는 공급 증가",
}


def generate_html(analysis: dict, series_list: list[dict]) -> str:
    """분석 결과와 시리즈 목록으로 대시보드 HTML을 생성한다.

    Args:
        analysis: {"provider": str, "content": str, "generated_at": str}
        series_list: [{"series_id": str, "title": str, "title_ko": str}, ...]

    Returns:
        HTML 문자열
    """
    import time

    cache_bust = int(time.time())
    cards = "\n".join(
        CARD_TEMPLATE.format(
            series_id=s["series_id"],
            title=s["title"],
            title_ko=s.get("title_ko") or s["title"],
            guide=CHART_GUIDES.get(s["series_id"], "").replace("\n", "<br>"),
            cache_bust=cache_bust,
        )
        for s in series_list
    )

    return HTML_TEMPLATE.format(
        analysis_content=analysis["content"],
        provider=analysis.get("provider", "unknown"),
        generated_at=analysis.get("generated_at", ""),
        cards=cards,
    )


def build_dashboard(
    output_dir: str | Path,
    data_dir: str | Path,
    charts_dir: str | Path,
    analysis: dict,
) -> Path:
    """대시보드를 출력 디렉토리에 생성한다.

    Args:
        output_dir: 출력 디렉토리 (index.html + charts/)
        data_dir: 시리즈 JSON 디렉토리
        charts_dir: 차트 PNG 디렉토리
        analysis: AI 분석 결과 dict

    Returns:
        생성된 index.html 경로
    """
    output_dir = Path(output_dir)
    data_dir = Path(data_dir)
    charts_dir = Path(charts_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 시리즈 목록 수집 (원본 JSON만, 파생 파일 제외)
    import re

    series_list: list[dict] = []
    for json_path in sorted(data_dir.glob("*.json")):
        stem = json_path.stem
        if re.search(r"_\d+[my]$", stem) or stem.startswith("analysis"):
            continue
        with json_path.open() as f:
            data = json.load(f)
        series_list.append(
            {
                "series_id": data["series_id"],
                "title": data["title"],
                "title_ko": data.get("title_ko"),
            }
        )

    # HTML 생성
    html = generate_html(analysis, series_list)
    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    # 차트 이미지 복사
    out_charts = output_dir / "charts"
    out_charts.mkdir(exist_ok=True)
    _sync_charts(charts_dir, out_charts)

    return index_path


def _sync_charts(src_dir: Path, out_dir: Path) -> None:
    """차트 PNG를 복사하고, 소스에 없는 PNG는 출력 디렉토리에서 제거한다.

    복사만 하면 지표를 제거하거나 이름을 바꿀 때마다 배포 디렉토리에
    고아 PNG가 영구히 남는다.
    """
    current = set()
    for png in src_dir.glob("*.png"):
        shutil.copy2(png, out_dir / png.name)
        current.add(png.name)

    for png in out_dir.glob("*.png"):
        if png.name not in current:
            png.unlink()


# ---------------------------------------------------------------------------
# KR 차트 가이드
# ---------------------------------------------------------------------------

CHART_GUIDES_KR: dict[str, str] = {
    "BOK_BASE_RATE": "▲ 인상 → 대출금리 상승, 부동산·주식 압박\n▼ 인하 → 유동성 확대, 위험자산 우호",
    "KR_TREASURY_3Y": "▲ 상승 → 시장금리 상승, 채권 가격 하락\n▼ 하락 → 금리 인하 기대, 안전자산 선호",
    "KR_TREASURY_10Y": "▲ 상승 → 장기 인플레이션 기대 확대\n▼ 하락 → 경기 둔화 우려, 장기 금리 하락 추세",
    "KR_CORP_BOND": "▲ 확대 → 신용 위험 증가, 기업 자금조달 비용 상승\n▼ 축소 → 신용시장 안정",
    "KRW_USD": "▲ 상승(원화 약세) → 수입물가 상승, 수출 경쟁력 개선\n▼ 하락(원화 강세) → 수입물가 하락, 외국인 투자 유입",
    "KRW_CNY": "▲ 상승 → 위안화 대비 원화 약세\n▼ 하락 → 위안화 대비 원화 강세",
    "JPY_USD": "▲ 상승(엔화 약세) → 일본 수출 경쟁력 강화, 한국 수출 압박\n▼ 하락(엔화 강세) → 안전자산 선호",
    "KR_CPI": "▲ 상승 → 인플레이션 압력, 금리 인상 요인\n▼ 둔화 → 물가 안정, 금리 인하 여건",
    "KR_M2": "▲ 급증 → 유동성 과잉, 자산가격 상승 압력\n▼ 둔화 → 유동성 위축, 디레버리징",
    "KR_CSI": "▲ 상승 → 소비자 낙관, 소비 확대 기대\n▼ 하락 → 비관심리, 소비 위축 가능성",
    "KR_BSI": "▲ 100 이상 → 기업 경기 낙관\n▼ 100 미만 → 기업 경기 비관",
    "KR_ESI": "▲ 상승 → 경제 전반 심리 개선\n▼ 하락 → 경제 전반 심리 위축",
    "KR_UNEMPLOYMENT": "▲ 상승 → 고용 악화, 경기 둔화\n▼ 하락 → 노동시장 개선",
    "KR_EMPLOYED": "▲ 증가 → 고용 확대, 경기 회복\n▼ 감소 → 고용 둔화, 경기 위축",
    "KR_IPI": "▲ 상승 → 제조업 경기 회복\n▼ 하락 → 산업 생산 둔화",
    "KR_RETAIL": "▲ 상승 → 소비 확대\n▼ 하락 → 소비 위축",
    "KR_GDP": "▲ 양(+) → 경제 성장\n▼ 음(-) → 경기 침체",
    "KR_PPI": "▲ 상승 → 원가 상승 압력, CPI 선행\n▼ 하락 → 원가 하락, 디플레이션 우려",
    "KR_EXPORT": "▲ 증가 → 수출 호조, 경기 회복\n▼ 감소 → 수출 둔화, 경기 위축",
    "KR_IMPORT": "▲ 증가 → 내수 확대 또는 원자재 가격 상승\n▼ 감소 → 내수 위축",
    "KR_HOUSING_PRICE": "▲ 상승 → 주택시장 과열, 규제 강화 가능성\n▼ 하락 → 주택시장 냉각, 규제 완화 기대",
    "KOSPI": "▲ 상승 → 경기 회복 기대, 외국인 매수세\n▼ 하락 → 경기 둔화 우려, 자본 유출",
    "KOSDAQ": "▲ 상승 → 성장주 선호, 위험선호 심리\n▼ 하락 → 위험회피, 중소형주 약세",
}


# ---------------------------------------------------------------------------
# 탭 대시보드
# ---------------------------------------------------------------------------

TABBED_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>경제지표 대시보드</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 16px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ text-align: center; margin-bottom: 16px; font-size: 1.6rem; color: #1a1a1a; }}
.tabs {{ display: flex !important; justify-content: center; gap: 8px; margin-bottom: 24px; }}
.tabs a.tab {{ display: inline-block !important; padding: 10px 32px; border: 1px solid #ddd; border-radius: 8px; background: #fff; cursor: pointer; font-size: 1rem; font-weight: 600; color: #666; transition: all 0.2s; text-decoration: none; }}
.tabs a.tab:hover {{ background: #eee; }}
.tabs a.tab.active {{ background: #1a1a1a; color: #fff; border-color: #1a1a1a; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.analysis {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.analysis h2 {{ font-size: 1.1rem; margin-bottom: 12px; color: #555; }}
.analysis p {{ margin-bottom: 12px; line-height: 1.7; font-size: 0.95rem; }}
.analysis .meta {{ font-size: 0.8rem; color: #999; margin-top: 8px; }}
.card {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.card h3 {{ font-size: 1rem; margin-bottom: 12px; color: #1a1a1a; }}
.card .guide {{ font-size: 0.85rem; color: #666; margin-top: 8px; line-height: 1.5; }}
.chart-pair {{ display: flex; gap: 12px; }}
.chart-pair img {{ flex: 1; min-width: 0; max-width: 50%; height: auto; border-radius: 8px; border: 1px solid #eee; }}
@media (max-width: 768px) {{
  .chart-pair {{ flex-direction: column; }}
  .chart-pair img {{ max-width: 100%; }}
  body {{ padding: 8px; }}
  h1 {{ font-size: 1.3rem; }}
}}
footer {{ text-align: center; color: #999; font-size: 0.8rem; margin-top: 32px; padding: 16px; }}
</style>
</head>
<body>
<div class="container">
<h1>경제지표 대시보드</h1>

<div class="tabs">
<a href="#" class="tab active" data-tab="us">US 미국</a>
<a href="#" class="tab" data-tab="kr">KR 한국</a>
</div>

<div id="tab-us" class="tab-content active">
<div class="analysis">
<h2>AI 경제 동향 분석 (미국)</h2>
{us_analysis_content}
<div class="meta">분석 제공: {us_provider} | 생성: {us_generated_at}</div>
</div>
{us_cards}
</div>

<div id="tab-kr" class="tab-content">
<div class="analysis">
<h2>AI 경제 동향 분석 (한국)</h2>
{kr_analysis_content}
<div class="meta">분석 제공: {kr_provider} | 생성: {kr_generated_at}</div>
</div>
{kr_cards}
</div>

<footer>경제지표 대시보드 — 데이터: FRED, Yahoo Finance, ECOS, KOSIS, KRX</footer>
</div>
<script>
document.querySelectorAll('a.tab').forEach(function(btn) {{
  btn.addEventListener('click', function(e) {{
    e.preventDefault();
    document.querySelectorAll('.tab-content').forEach(function(c) {{ c.classList.remove('active'); }});
    document.querySelectorAll('a.tab').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  }});
}});
</script>
</body>
</html>"""

CARD_TEMPLATE_SUBDIR = """\
<div class="card">
<h3>{title_ko} ({title})</h3>
<div class="chart-pair">
<img src="charts/{subdir}/{series_id}.png?v={cache_bust}" alt="{title_ko} 전체 기간">
<img src="charts/{subdir}/{series_id}_1y.png?v={cache_bust}" alt="{title_ko} 최근 1년">
</div>
<p class="guide">{guide}</p>
</div>"""


def _build_cards(
    series_list: list[dict],
    guides: dict[str, str],
    subdir: str,
    cache_bust: int,
) -> str:
    """시리즈 목록으로 카드 HTML을 생성한다."""
    return "\n".join(
        CARD_TEMPLATE_SUBDIR.format(
            series_id=s["series_id"],
            title=s["title"],
            title_ko=s.get("title_ko") or s["title"],
            guide=guides.get(s["series_id"], "").replace("\n", "<br>"),
            subdir=subdir,
            cache_bust=cache_bust,
        )
        for s in series_list
    )


def generate_tabbed_html(
    us_analysis: dict,
    us_series: list[dict],
    kr_analysis: dict,
    kr_series: list[dict],
) -> str:
    """US/KR 탭 대시보드 HTML을 생성한다."""
    import time

    cache_bust = int(time.time())
    us_cards = _build_cards(us_series, CHART_GUIDES, "us", cache_bust)
    kr_cards = _build_cards(kr_series, CHART_GUIDES_KR, "kr", cache_bust)

    return TABBED_HTML_TEMPLATE.format(
        us_analysis_content=us_analysis["content"],
        us_provider=us_analysis.get("provider", "unknown"),
        us_generated_at=us_analysis.get("generated_at", ""),
        us_cards=us_cards,
        kr_analysis_content=kr_analysis["content"],
        kr_provider=kr_analysis.get("provider", "unknown"),
        kr_generated_at=kr_analysis.get("generated_at", ""),
        kr_cards=kr_cards,
    )


def _collect_series(
    data_dir: Path,
    series_order: list[str] | None = None,
) -> list[dict]:
    """data_dir에서 시리즈 메타데이터를 수집한다."""
    import re

    by_id: dict[str, dict] = {}
    for json_path in data_dir.glob("*.json"):
        stem = json_path.stem
        if re.search(r"_\d+[my]$", stem) or stem.startswith("analysis"):
            continue
        with json_path.open() as f:
            data = json.load(f)
        if not any(o["value"] is not None for o in data.get("observations", [])):
            continue
        by_id[data["series_id"]] = {
            "series_id": data["series_id"],
            "title": data["title"],
            "title_ko": data.get("title_ko"),
        }

    if series_order:
        ordered = [by_id[sid] for sid in series_order if sid in by_id]
        remaining = sorted(
            (s for sid, s in by_id.items() if sid not in set(series_order)),
            key=lambda s: s["series_id"],
        )
        return ordered + remaining
    return sorted(by_id.values(), key=lambda s: s["series_id"])


def build_tabbed_dashboard(
    output_dir: str | Path,
    us_data_dir: str | Path,
    us_charts_dir: str | Path,
    us_analysis: dict,
    kr_data_dir: str | Path,
    kr_charts_dir: str | Path,
    kr_analysis: dict,
    us_series_order: list[str] | None = None,
    kr_series_order: list[str] | None = None,
) -> Path:
    """US/KR 탭 대시보드를 출력 디렉토리에 생성한다."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    us_series = _collect_series(Path(us_data_dir), series_order=us_series_order)
    kr_series = _collect_series(Path(kr_data_dir), series_order=kr_series_order)

    html = generate_tabbed_html(us_analysis, us_series, kr_analysis, kr_series)
    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    # 차트 이미지 복사 (서브디렉토리 분리)
    for subdir, charts_dir in [("us", us_charts_dir), ("kr", kr_charts_dir)]:
        out_charts = output_dir / "charts" / subdir
        out_charts.mkdir(parents=True, exist_ok=True)
        _sync_charts(Path(charts_dir), out_charts)

    # us/kr 분리 이전의 flat 레이아웃 잔재를 정리한다.
    for png in (output_dir / "charts").glob("*.png"):
        png.unlink()

    return index_path
