"""
混合动力爬虫：掘金(Selenium) + GitHub/HN(Requests)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Selenium 相关模块
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from config import USER_AGENT
from database import get_mongo_database

logger = logging.getLogger(__name__)

# 掘金网页版分类地址
JUEJIN_URLS = {
    "后端": "https://juejin.cn/backend",
    "前端": "https://juejin.cn/frontend",
    "AI": "https://juejin.cn/ai",
    "Android": "https://juejin.cn/android",
}

GITHUB_TRENDING_URLS = {
    "all": "https://github.com/trending",
    "python": "https://github.com/trending/python",
    "java": "https://github.com/trending/java",
    "javascript": "https://github.com/trending/javascript",
}
HACKER_NEWS_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"


def _get_collection():
    return get_mongo_database("tech_crawler")["articles"]


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    my_proxy_port = 7897

    proxies = {
        "http": f"http://127.0.0.1:{my_proxy_port}",
        "https": f"http://127.0.0.1:{my_proxy_port}",
    }

    # 挂载代理
    session.proxies.update(proxies)

    return session


def _sanitize_seed(seed: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in seed)
    return cleaned or "tech"


def _placeholder_image(seed: str) -> str:
    return f"https://picsum.photos/seed/{_sanitize_seed(seed)}/800/400"


def _resolve_top_image(url: Optional[str], session: requests.Session, seed: str) -> str:
    if not url:
        return _placeholder_image(seed)
    try:
        resp = session.get(url, timeout=3)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("meta", property="og:image") or soup.find(
            "meta", attrs={"name": "og:image"}
        )
        if tag and tag.get("content"):
            content = tag.get("content").strip()
            if content:
                return content
    except Exception:
        pass
    return _placeholder_image(seed)


# ==========================================
# 核心修改：使用 Selenium 爬取掘金
# ==========================================
def crawl_juejin_selenium(limit_per_category: int = 15) -> List[Dict]:
    payloads: List[Dict] = []

    # 配置 Chrome 选项
    chrome_options = Options()
    # 如果想看着它爬，把下面这行注释掉；如果想后台静默爬，保留这行
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 伪装 User-Agent
    chrome_options.add_argument(f"user-agent={USER_AGENT}")

    try:
        # 自动安装并启动对应版本的 ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(15)

        for category_name, url in JUEJIN_URLS.items():
            logger.info(f"正在打开掘金【{category_name}】页面: {url}")
            try:
                driver.get(url)
                time.sleep(2) # 等待页面加载

                # 模拟滚动 2 次，加载更多数据
                for _ in range(2):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)

                # 提取文章列表 (掘金的 CSS 类名可能会变，这里使用相对通用的结构)
                # entry-list 下面的 item
                articles = driver.find_elements(By.CSS_SELECTOR, ".entry-list .entry")

                count = 0
                for article in articles:
                    if count >= limit_per_category:
                        break

                    try:
                        # 排除广告
                        if "advertisement" in article.get_attribute("class"):
                            continue

                        # 提取标题和链接
                        title_elem = article.find_element(By.CSS_SELECTOR, ".title-row a.title")
                        title = title_elem.text.strip()
                        link = title_elem.get_attribute("href")

                        # 提取摘要
                        try:
                            summary = article.find_element(By.CSS_SELECTOR, ".abstract a").text.strip()
                        except:
                            summary = f"{category_name} 热门文章"

                        # 提取封面图 (如果有)
                        try:
                            img_elem = article.find_element(By.CSS_SELECTOR, "img.lazy")
                            cover = img_elem.get_attribute("src")
                        except:
                            cover = None

                        if not title or not link:
                            continue

                        payloads.append({
                            "title": title,
                            "url": link,
                            "summary": summary[:300],
                            "source": "juejin",
                            "tags": [category_name],
                            "top_image": cover if cover else _placeholder_image(title),
                            "publish_date": datetime.utcnow().isoformat()
                        })
                        count += 1

                    except Exception as e:
                        continue # 跳过解析错误的单条

                logger.info(f"掘金【{category_name}】抓取完成，共 {count} 条")

            except Exception as e:
                logger.error(f"掘金【{category_name}】页面加载失败: {e}")

        driver.quit()

    except Exception as e:
        logger.error(f"Selenium 启动失败: {e}")

    return payloads


def crawl_github_trending(session: requests.Session, per_page: int = 10) -> List[Dict]:
    payloads: List[Dict] = []
    for label, url in GITHUB_TRENDING_URLS.items():
        time.sleep(1)
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("抓取 GitHub Trending %s 失败: %s", label, exc)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("article.Box-row")[:per_page]
        for row in rows:
            link = row.select_one("h2 a")
            desc = row.select_one("p")
            if not link:
                continue
            repo_path = link.get("href", "").strip()
            title = link.get_text(strip=True)
            repo_url = f"https://github.com{repo_path}"
            description = desc.get_text(strip=True) if desc else ""
            tags = ["GitHub Trending"]
            if label != "all":
                tags.append(label.capitalize())
            payloads.append(
                {
                    "title": title,
                    "url": repo_url,
                    "summary": description,
                    "source": "github",
                    "tags": tags,
                    "top_image": _resolve_top_image(repo_url, session, repo_path or title),
                    "publish_date": datetime.utcnow().isoformat(),
                }
            )
    return payloads


def crawl_hacker_news(session: requests.Session, limit: int = 20) -> List[Dict]:
    payloads: List[Dict] = []
    try:
        ids = session.get(HACKER_NEWS_TOP, timeout=10).json()[:limit]
    except Exception as exc:
        logger.error("获取 Hacker News ID 失败: %s", exc)
        return payloads
    for story_id in ids:
        detail_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        try:
            detail = session.get(detail_url, timeout=5).json()
        except Exception as exc:
            logger.warning("获取 Hacker News %s 失败: %s", story_id, exc)
            continue
        if not detail or "url" not in detail:
            continue
        story_url = detail["url"]
        payloads.append(
            {
                "title": detail.get("title", "Hacker News Story"),
                "url": story_url,
                "summary": "",
                "source": "hackernews",
                "tags": ["Hacker News"],
                "top_image": _resolve_top_image(story_url, session, str(story_id)),
                "publish_date": datetime.fromtimestamp(detail.get("time", 0)).isoformat()
                if detail.get("time")
                else None,
            }
        )
    return payloads


def _upsert_articles(payloads: List[Dict]):
    if not payloads:
        return
    collection = _get_collection()
    for doc in payloads:
        doc["updated_at"] = datetime.utcnow()
        collection.update_one({"url": doc["url"]}, {"$set": doc}, upsert=True)


def run_crawlers():
    session = _session()
    sources = []

    logger.info("🚀 启动混合爬虫...")

    # 1. 启动 Selenium 爬掘金
    logger.info("正在启动 Selenium 爬取掘金 (可能需要几秒钟启动浏览器)...")
    sources.extend(crawl_juejin_selenium())

    # 2. 启动 Requests 爬 GitHub
    logger.info("正在爬取 GitHub Trending...")
    sources.extend(crawl_github_trending(session))

    # 3. 启动 Requests 爬 Hacker News
    logger.info("正在爬取 Hacker News...")
    sources.extend(crawl_hacker_news(session))

    if not sources:
        logger.warning("❌ 本轮未抓取到任何数据！")
        return
    _upsert_articles(sources)
    logger.info("✅ 爬虫任务全部结束，共处理 %d 条记录。", len(sources))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_crawlers()