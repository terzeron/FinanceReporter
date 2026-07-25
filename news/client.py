"""경제 뉴스 RSS 피드 수집 클라이언트."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

FEEDS_MAP: dict[str, dict[str, str]] = {
    "reuters": {
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "source": "Reuters",
    },
    "bloomberg": {
        "url": "https://feeds.bloomberg.com/markets/news.rss",
        "source": "Bloomberg",
    },
    "cnbc": {
        "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "source": "CNBC",
    },
    "yahoo_finance": {
        "url": "https://finance.yahoo.com/news/rssindex",
        "source": "Yahoo Finance",
    },
    "wsj": {
        "url": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
        "source": "MarketWatch/WSJ",
    },
}

MAX_PER_SOURCE = 3
FETCH_TIMEOUT = 5
ARTICLE_MAX_CHARS = 400

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FinanceNewsBot/1.0)",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
}


class NewsFetcher:
    """RSS 피드에서 경제 뉴스를 수집하고 기사 본문을 추출한다."""

    def fetch_feed(self, feed_id: str) -> list[dict]:
        """단일 RSS 피드에서 기사 목록을 가져온다.

        Args:
            feed_id: FEEDS_MAP에 정의된 피드 ID

        Returns:
            기사 dict 리스트 (source, title, summary, text, url, published)

        Raises:
            KeyError: FEEDS_MAP에 없는 feed_id
        """
        info = FEEDS_MAP[feed_id]
        feed = feedparser.parse(info["url"])

        articles = []
        for entry in feed.entries[:MAX_PER_SOURCE]:
            summary_html = getattr(entry, "summary", "") or ""
            summary = BeautifulSoup(summary_html, "html.parser").get_text(strip=True)
            summary = summary[:ARTICLE_MAX_CHARS] if summary else ""

            published = ""
            parsed = getattr(entry, "published_parsed", None)
            if parsed:
                try:
                    published = datetime(*parsed[:6]).strftime("%Y-%m-%d")
                except Exception:
                    pass

            articles.append(
                {
                    "source": info["source"],
                    "title": getattr(entry, "title", ""),
                    "summary": summary,
                    "text": summary,
                    "url": getattr(entry, "link", ""),
                    "published": published,
                }
            )

        return articles

    def fetch_article_text(self, url: str) -> str | None:
        """URL에서 기사 본문 텍스트를 추출한다. 실패 시 None 반환."""
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=FETCH_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            article = soup.find("article")
            if article:
                text = article.get_text(separator=" ", strip=True)
            else:
                paragraphs = [
                    p.get_text(strip=True)
                    for p in soup.find_all("p")
                    if len(p.get_text(strip=True)) > 80
                ]
                text = " ".join(paragraphs[:5])

            return text[:ARTICLE_MAX_CHARS] if text else None
        except Exception:
            return None

    def fetch_all(
        self,
        data_dir: str | Path | None = None,
        fetch_text: bool = True,
    ) -> list[dict]:
        """모든 피드에서 기사를 수집하고 본문을 추출한다.

        Args:
            data_dir: 캐시 JSON 저장 디렉토리 (None이면 저장하지 않음)
            fetch_text: 기사 URL에서 본문 추가 추출 여부

        Returns:
            기사 dict 리스트
        """
        from cache import load_cached

        cache_path = Path(data_dir) / "news.json" if data_dir is not None else None

        if cache_path is not None:
            cached = load_cached(cache_path)
            if cached is not None:
                return cached.get("articles", [])

        articles: list[dict] = []
        for feed_id in FEEDS_MAP:
            try:
                feed_articles = self.fetch_feed(feed_id)
                if fetch_text:
                    for article in feed_articles:
                        text = self.fetch_article_text(article["url"])
                        if text:
                            article["text"] = text
                articles.extend(feed_articles)
            except Exception:
                continue

        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({"articles": articles}, ensure_ascii=False, indent=2)
            )

        return articles


def main(data_dir: str | Path | None = None) -> None:
    """뉴스 RSS 피드 수집 및 저장."""
    from cache import is_fresh

    if data_dir is None:
        data_dir = Path("data/news")
    else:
        data_dir = Path(data_dir)

    cache_path = data_dir / "news.json"
    if is_fresh(cache_path):
        print("뉴스: 캐시 사용")
        return

    fetcher = NewsFetcher()
    articles = fetcher.fetch_all(data_dir=data_dir)
    sources = {a["source"] for a in articles}
    print(
        f"뉴스 수집 완료: {len(articles)}개 기사, {len(sources)}개 출처 → {data_dir}/"
    )


if __name__ == "__main__":
    main()
