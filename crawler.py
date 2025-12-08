"""
多源网络爬虫，实现资讯抓取、正文解析与 MongoDB 持久化。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from newspaper import Article
from pymongo.collection import Collection

from config import USER_AGENT
from database import get_mongo_database

logger = logging.getLogger(__name__)


def _get_collection() -> Collection:
    db = get_mongo_database("tech_crawler")
    return db["articles_pool"]


def fetch_article_content(url: str) -> Optional[Dict[str, str]]:
    """
    使用 newspaper3k 抓取网页正文，限制在 3000 字符内。
    """
    article = Article(url)
    try:
        article.download()
        article.parse()
        text = (article.text or "").strip()
        top_image = article.top_image if article.top_image else None
        return {
            "text": text[:3000],
            "top_image": top_image,
        }
    except Exception as exc:
        logger.warning("正文解析失败 %s: %s", url, exc)
        return None


def _request_json(session: requests.Session, url: str):
    response = session.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def _crawl_juejin(session: requests.Session, limit: int = 10) -> List[Dict]:
    url = "https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot"
    payloads = []
    try:
        data = _request_json(session, url).get("data", [])[:limit]
        for item in data:
            article_info = item.get("article_info", {})
            article_id = article_info.get("article_id")
            if not article_id:
                continue
            payloads.append(
                {
                    "url": f"https://juejin.cn/post/{article_id}",
                    "title": article_info.get("title", "掘金热榜"),
                    "source": "Juejin",
                    "publish_date": datetime.fromtimestamp(
                        int(article_info.get("ctime", 0))
                    ).strftime("%Y-%m-%d")
                    if article_info.get("ctime")
                    else None,
                    "raw_tags": item.get("category", []),
                    "brief_summary": article_info.get("brief_content", "")[:280],
                }
            )
    except Exception as exc:
        logger.error("抓取掘金数据失败: %s", exc)
    return payloads


def _crawl_hacker_news(session: requests.Session, limit: int = 10) -> List[Dict]:
    ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    payloads = []
    try:
        story_ids = _request_json(session, ids_url)[:limit]
        for story_id in story_ids:
            try:
                detail_url = (
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                )
                detail = _request_json(session, detail_url)
            except Exception as exc:
                logger.warning("获取 Hacker News %s 失败: %s", story_id, exc)
                continue
            if not detail or "url" not in detail:
                continue
            payloads.append(
                {
                    "url": detail["url"],
                    "title": detail.get("title", "Hacker News Story"),
                    "source": "Hacker News",
                    "publish_date": datetime.fromtimestamp(
                        detail.get("time", 0)
                    ).strftime("%Y-%m-%d")
                    if detail.get("time")
                    else None,
                    "raw_tags": detail.get("topics", []),
                    "brief_summary": detail.get("title", "")[:280],
                }
            )
    except Exception as exc:
        logger.error("抓取 Hacker News 列表失败: %s", exc)
    return payloads


def _crawl_github_trending(session: requests.Session) -> List[Dict]:
    url = "https://github.com/trending"
    payloads = []
    try:
        html = session.get(url, timeout=10)
        html.raise_for_status()
        soup = BeautifulSoup(html.text, "html.parser")
        articles = soup.select("article.Box-row")[:10]
        for article in articles:
            link = article.select_one("h2 a")
            desc = article.select_one("p")
            if not link:
                continue
            repo_path = link.get("href", "").strip()
            payloads.append(
                {
                    "url": f"https://github.com{repo_path}",
                    "title": link.get_text(strip=True),
                    "source": "GitHub Trending",
                    "publish_date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "raw_tags": ["GitHub", "Trending"],
                    "brief_summary": desc.get_text(strip=True) if desc else "",
                }
            )
    except Exception as exc:
        logger.error("抓取 GitHub Trending 失败: %s", exc)
    return payloads


def _enrich_and_store(payloads: List[Dict]):
    collection = _get_collection()
    for payload in payloads:
        content = fetch_article_content(payload["url"])
        if content:
            payload["full_text"] = content["text"]
            if content.get("top_image") and not payload.get("top_image"):
                payload["top_image"] = content["top_image"]
        else:
            payload["full_text"] = ""
        payload["updated_at"] = datetime.utcnow()
        collection.update_one({"url": payload["url"]}, {"$set": payload}, upsert=True)


def run_crawlers():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    payloads = []
    payloads.extend(_crawl_juejin(session))
    payloads.extend(_crawl_hacker_news(session))
    payloads.extend(_crawl_github_trending(session))

    if not payloads:
        logger.warning("未获取到任何文章数据。")
        return

    _enrich_and_store(payloads)
    logger.info("爬虫任务完成，共处理 %d 篇文章。", len(payloads))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_crawlers()

