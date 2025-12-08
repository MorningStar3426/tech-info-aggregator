"""
AI 推荐模块：聚合用户行为、候选文章并调用 LLM 生成推荐结果。
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Tuple

from openai import OpenAI
from pymongo.collection import Collection
from sqlalchemy import text

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from database import get_mongo_database, mysql_connection

logger = logging.getLogger(__name__)
_llm_client: Optional[OpenAI] = None


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


def _load_user_profile(user_id: str) -> Dict:
    interests: List[str] = []
    history: List[Dict] = []
    with mysql_connection() as conn:
        result = conn.execute(
            text("SELECT interests FROM users WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
        if result and result[0]:
            try:
                interests = json.loads(result[0])
            except json.JSONDecodeError:
                interests = []
        log_rows = conn.execute(
            text(
                """
                SELECT article_title, article_url, action_type, log_time
                FROM user_logs
                WHERE user_id = :user_id
                ORDER BY log_time DESC
                LIMIT 5
                """
            ),
            {"user_id": user_id},
        ).fetchall()
        for row in log_rows:
            history.append(
                {
                    "title": row.article_title,
                    "url": row.article_url,
                    "action": row.action_type,
                    "time": row.log_time.isoformat() if row.log_time else None,
                }
            )
    return {"interests": interests, "history": history}


def _sample_candidates(sample_size: int = 25) -> List[Dict]:
    collection: Collection = get_mongo_database("tech_crawler")["articles_pool"]
    pipeline = [
        {"$match": {"full_text": {"$exists": True, "$ne": ""}}},
        {"$sample": {"size": sample_size}},
    ]
    try:
        return list(collection.aggregate(pipeline))
    except Exception as exc:
        logger.error("候选文章抽样失败: %s", exc)
        return []


def _fallback_from_candidates(
    candidates: List[Dict], limit: int = 8, reason: str = ""
) -> List[Dict]:
    fallback = []
    for cand in candidates[:limit]:
        if not cand.get("url"):
            continue
        fallback.append(
            {
                "title": cand.get("title"),
                "url": cand.get("url"),
                "summary": cand.get("brief_summary", ""),
                "reason": reason or "基于候选池的默认推荐",
                "top_image": cand.get("top_image"),
                "source": cand.get("source"),
            }
        )
    return fallback


def _build_prompt(interests: List[str], history: List[Dict], candidates: List[Dict]) -> str:
    candidate_payload = []
    for c in candidates:
        candidate_payload.append(
            {
                "title": c.get("title"),
                "url": c.get("url"),
                "summary": c.get("brief_summary"),
                "tags": c.get("raw_tags"),
            }
        )
    payload = {
        "interests": interests,
        "history": history,
        "candidates": candidate_payload,
    }
    instructions = (
        "请基于候选文章与用户兴趣输出 JSON 数组，每个元素包含 "
        "title, url, summary, reason 字段，并按相关性降序排列。"
    )
    return f"{instructions}\n\n上下文: {json.dumps(payload, ensure_ascii=False)}"


def _parse_llm_response(content: str) -> List[Dict]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error("LLM 返回 JSON 解析失败: %s", exc)
        return []


def _call_llm(prompt: str) -> List[Dict]:
    client = get_llm_client()
    response = client.chat.completions.create(
        model=LLM_MODEL_NAME,
        stream=False,
        messages=[
            {
                "role": "system",
                "content": "You are a tech recommendation engine. Output strictly valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
        extra_body={"enable_thinking": False},
    )
    content = response.choices[0].message.content
    if not content:
        return []
    return _parse_llm_response(content)


def recommend_articles(
    user_id: str, sample_size: int = 25
) -> Tuple[List[Dict], Optional[str]]:
    profile = _load_user_profile(user_id)
    candidates = _sample_candidates(sample_size)
    if not candidates:
        return [], "MongoDB 中没有可用文章，请先运行爬虫。"

    prompt = _build_prompt(profile["interests"], profile["history"], candidates)
    try:
        llm_results = _call_llm(prompt)
    except RuntimeError as exc:
        logger.warning("LLM 未配置: %s", exc)
        return (
            _fallback_from_candidates(candidates, reason="LLM 未配置，展示热门候选"),
            "LLM_API_KEY 未配置，已退回候选池默认排序。",
        )
    except Exception as exc:
        logger.error("LLM 调用失败: %s", exc)
        return (
            _fallback_from_candidates(candidates, reason="LLM 调用失败，展示热门候选"),
            f"LLM 调用失败：{exc}",
        )
    if not llm_results:
        return (
            _fallback_from_candidates(candidates, reason="LLM 无响应，展示热门候选"),
            "LLM 未返回有效内容，已使用默认推荐。",
        )

    candidate_map = {c["url"]: c for c in candidates}
    recommendations = []
    for item in llm_results:
        url = item.get("url")
        if not url or url not in candidate_map:
            continue
        base = candidate_map[url]
        recommendations.append(
            {
                "title": base.get("title") or item.get("title"),
                "url": url,
                "summary": item.get("summary") or base.get("brief_summary", ""),
                "reason": item.get("reason", ""),
                "top_image": base.get("top_image"),
                "source": base.get("source"),
            }
        )
    if not recommendations:
        return (
            _fallback_from_candidates(
                candidates, reason="LLM 推荐缺少有效链接，展示热门候选"
            ),
            "LLM 推荐结果缺少有效链接，已使用默认推荐。",
        )
    return recommendations, None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(recommend_articles("user_001"))
