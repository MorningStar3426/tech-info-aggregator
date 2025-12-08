"""
AI 模块：每日科技早报 + 幽默辣评推荐。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from openai import OpenAI
from pymongo.collection import Collection
from sqlalchemy import text

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from database import get_mongo_database, mysql_connection

logger = logging.getLogger(__name__)
_llm_client: Optional[OpenAI] = None


def _collection() -> Collection:
    return get_mongo_database("tech_crawler")["articles"]


def _is_llm_configured() -> bool:
    token = (LLM_API_KEY or "").strip()
    return bool(token) and "你的_ModelScope_Token" not in token


def get_llm_client() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        if not _is_llm_configured():
            raise RuntimeError("LLM_API_KEY 未设置或仍为占位符。")
        _llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    return _llm_client


def _call_llm(messages: List[Dict], max_tokens: int = 600) -> str:
    client = get_llm_client()
    response = client.chat.completions.create(
        model=LLM_MODEL_NAME,
        stream=False,
        messages=messages,
        temperature=0.4,
        max_tokens=max_tokens,
        extra_body={"enable_thinking": False},
    )
    return response.choices[0].message.content or ""


def generate_daily_flash(limit: int = 10) -> str:
    collection = _collection()
    headlines = [
        item.get("title", "科技速递")
        for item in collection.find({"title": {"$ne": None}})
        .sort("updated_at", -1)
        .limit(limit)
    ]
    if not headlines:
        return "大家早！资讯库空空如也，赶紧运行爬虫补货吧 ☕️"
    prompt = (
        "这里是今天最热的科技新闻标题："
        + json.dumps(headlines, ensure_ascii=False)
        + "。请扮演一个幽默、充满活力的科技博主，写一段 100 字左右的【早报广播词】。"
        "风格要轻松、口语化，用 Emoji，开头说“大家早！”。"
    )
    try:
        content = _call_llm(
            [
                {
                    "role": "system",
                    "content": "你是一名活力十足的科技博主，用中文输出广播词。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
        ).strip()
        if content:
            return content
    except Exception as exc:
        logger.error("生成每日早报失败: %s", exc)
    return "大家早！资讯火速赶来，但 AI 有点卡壳，稍后再试试 🔧"


def _load_user_interests(user_id: str) -> List[str]:
    with mysql_connection() as conn:
        row = conn.execute(
            text("SELECT interests FROM users WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
    if not row or not row[0]:
        return []
    try:
        interests = json.loads(row[0])
        return interests if isinstance(interests, list) else []
    except json.JSONDecodeError:
        return []


def _query_articles_by_tags(tags: Sequence[str], limit: int) -> List[Dict]:
    collection = _collection()
    cursor = collection.find({"tags": {"$in": list(tags)}}).sort("updated_at", -1).limit(
        limit
    )
    return list(cursor)


def _query_hot_articles(limit: int) -> List[Dict]:
    return list(_collection().find().sort("updated_at", -1).limit(limit))


def _query_mixed_candidates(limit: int) -> List[Dict]:
    collection = _collection()
    per_source = 5
    source_lists = {
        "juejin": list(
            collection.find({"source": "juejin"}).sort("updated_at", -1).limit(per_source)
        ),
        "github": list(
            collection.find({"source": "github"}).sort("updated_at", -1).limit(per_source)
        ),
        "hackernews": list(
            collection.find({"source": "hackernews"})
            .sort("updated_at", -1)
            .limit(per_source)
        ),
    }

    def sort_key(doc: Dict):
        ts = doc.get("updated_at")
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                pass
        return datetime.min

    mixed: List[Dict] = []
    for src in ["juejin", "github", "hackernews"]:
        pool = source_lists.get(src) or []
        if pool:
            mixed.append(pool.pop(0))

    remaining: List[Dict] = []
    for pool in source_lists.values():
        remaining.extend(pool)
    remaining.sort(key=sort_key, reverse=True)

    for doc in remaining:
        if len(mixed) >= limit:
            break
        mixed.append(doc)

    if len(mixed) < limit:
        extra = _query_hot_articles(limit * 2)
        seen_urls = {doc.get("url") for doc in mixed}
        for doc in extra:
            if doc.get("url") in seen_urls:
                continue
            mixed.append(doc)
            seen_urls.add(doc.get("url"))
            if len(mixed) >= limit:
                break
    return mixed[:limit]


def _build_late_prompt(candidates: List[Dict], user_tags: List[str]) -> str:
    formatted = []
    for idx, article in enumerate(candidates, 1):
        formatted.append(
            f"ID: {idx}\n"
            f"标题: {article.get('title')}\n"
            f"简介: {article.get('summary', '') or '暂无简介'}\n"
            f"标签: {', '.join(article.get('tags', [])) or '无'}\n"
            f"链接: {article.get('url')}"
        )
    instructions = (
        "你是一个毒舌、幽默、调皮的技术大V。"
        "请严格输出 JSON 数组，示例：[{\"index\":1,\"ai_comment\":\"...\",\"tag_match\":\"Python\"}]\n"
        "index 必须对应我提供的 ID，ai_comment 要中文俏皮话（≤40字），tag_match 用于说明命中的标签或填写“热门推荐”。"
    )
    return (
        f"{instructions}\n\n候选文章列表：\n{chr(10).join(formatted)}\n\n"
        f"用户关注标签：{', '.join(user_tags) if user_tags else '未指定'}\n"
        "请保证 JSON 顺序与 ID 顺序一致。"
    )


def _parse_json_response(content: str) -> List[Dict]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError as exc:
        logger.error("LLM JSON 解析失败: %s", exc)
        return []


def recommend_articles(
    user_id: str, interests: Optional[List[str]] = None, limit: int = 9
) -> Tuple[List[Dict], Optional[str]]:
    interests = interests or _load_user_interests(user_id)
    articles: List[Dict] = []
    seen_urls = set()
    if interests:
        tagged = _query_articles_by_tags(interests, limit)
        articles.extend(tagged)
        seen_urls.update({item.get("url") for item in tagged if item.get("url")})
    if len(articles) < limit:
        mixed = _query_mixed_candidates(limit)
        for item in mixed:
            url = item.get("url")
            if url and url in seen_urls:
                continue
            articles.append(item)
            if url:
                seen_urls.add(url)
            if len(articles) >= limit:
                break
    articles = articles[:limit]
    if not articles:
        return [], "文章池为空，请运行爬虫。"

    prompt = _build_late_prompt(articles, interests)
    diagnostic: Optional[str] = None
    try:
        raw = _call_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是一个毒舌、幽默、调皮的技术大V。只回复 JSON，并确保字段齐全。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
        llm_output = _parse_json_response(raw)
    except RuntimeError as exc:
        logger.warning("LLM 未配置: %s", exc)
        llm_output = []
        diagnostic = "LLM_API_KEY 未配置，已回退至热门推荐。"
    except Exception as exc:
        logger.error("LLM 调用失败: %s", exc)
        llm_output = []
        diagnostic = "AI 辣评生成失败，暂时展示热门推荐。"

    llm_map: Dict[int, Dict] = {}
    if llm_output:
        for entry in llm_output:
            idx = entry.get("index")
            if not isinstance(idx, int):
                continue
            if idx < 1 or idx > len(articles):
                continue
            if idx in llm_map:
                continue
            llm_map[idx] = entry

    results = []
    for idx, base in enumerate(articles, 1):
        entry = llm_map.get(idx)
        ai_comment = ""
        tag_match = None
        if entry:
            ai_comment = entry.get("ai_comment") or ""
            tag_match = entry.get("tag_match")
        if not ai_comment:
            ai_comment = f"来自{base.get('source','资讯')} 的热门推荐，别错过。"
        if not tag_match:
            tag_match = _resolve_tag_match(base, interests)
        results.append(
            {
                "title": base.get("title"),
                "url": base.get("url"),
                "top_image": base.get("top_image"),
                "ai_comment": ai_comment,
                "tag_match": tag_match,
            }
        )
    return results, diagnostic


def _resolve_tag_match(article: Dict, interests: Optional[List[str]]) -> str:
    tags = article.get("tags") or []
    if interests:
        for tag in tags:
            if tag in interests:
                return tag
    return "热门推荐"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(generate_daily_flash())
    print(recommend_articles("user_001"))
