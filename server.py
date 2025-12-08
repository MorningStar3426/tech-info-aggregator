"""
Flask 主程序：提供页面渲染与 RESTful API。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

from flask import Flask, jsonify, render_template, request
from sqlalchemy import text

from crawler import JUEJIN_URLS
from database import mysql_connection
from recommender import generate_daily_flash, recommend_articles

app = Flask(__name__)


def _fetch_users() -> List[Dict]:
    with mysql_connection() as conn:
        rows = conn.execute(
            text("SELECT user_id, username, interests FROM users ORDER BY created_at ASC")
        ).fetchall()
    users = []
    for row in rows:
        interests: List[str] = []
        if row.interests:
            try:
                interests = json.loads(row.interests)
            except json.JSONDecodeError:
                interests = []
        users.append(
            {"user_id": row.user_id, "username": row.username, "interests": interests}
        )
    return users


def _available_tags(users: List[Dict]) -> List[str]:
    tags = set()
    for user in users:
        tags.update(user.get("interests", []))
    tags.update(JUEJIN_URLS.keys())
    tags.update({"GitHub Trending", "Python", "Java", "Javascript", "Hacker News"})
    return sorted(tag for tag in tags if tag)


@app.route("/", methods=["GET"])
def index():
    users = _fetch_users()
    if not users:
        return "请先在 MySQL 中创建用户数据。", 500
    tags = _available_tags(users)

    # ⚠️ 新增：从环境变量读取 Dify Token
    dify_token = os.getenv("DIFY_TOKEN", "")

    # ⚠️ 修改：把 dify_token 传给模板
    return render_template("index.html", users=users, available_tags=tags, dify_token=dify_token)


@app.get("/api/daily_flash")
def api_daily_flash():
    message = generate_daily_flash()
    return jsonify({"message": message})


@app.post("/api/recommend")
def api_recommend():
    payload = request.get_json(force=True) or {}
    user_id = payload.get("user_id")
    interests = payload.get("interests") or []
    if not user_id:
        return jsonify({"message": "缺少 user_id"}), 400
    items, diagnostic = recommend_articles(user_id, interests)
    response = {"items": items}
    if diagnostic:
        response["message"] = diagnostic
    return jsonify(response)


@app.post("/api/log_action")
def api_log_action():
    payload = request.get_json(force=True) or {}
    user_id = payload.get("user_id")
    url = payload.get("url")
    title = payload.get("title")
    action = payload.get("action", "like")
    if not all([user_id, url, title]):
        return jsonify({"message": "缺少必要字段"}), 400
    with mysql_connection() as conn:
        conn.execute(
            text(
                """
                INSERT INTO user_logs (user_id, article_title, article_url, action_type)
                VALUES (:user_id, :title, :url, :action)
                """
            ),
            {"user_id": user_id, "title": title, "url": url, "action": action},
        )
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8501"))
    app.run(host="0.0.0.0", port=port, debug=True)
