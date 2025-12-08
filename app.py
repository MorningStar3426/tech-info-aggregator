"""
Streamlit 前端：提供用户管理、爬虫触发与推荐展示。
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List

import streamlit as st
from sqlalchemy import text

from crawler import run_crawlers
from database import mysql_connection
from recommender import recommend_articles

logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="智能科技情报聚合", layout="wide")


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


def _update_interests(user_id: str, interests: List[str]):
    with mysql_connection() as conn:
        conn.execute(
            text("UPDATE users SET interests = :interests WHERE user_id = :user_id"),
            {"user_id": user_id, "interests": json.dumps(interests, ensure_ascii=False)},
        )


def _insert_user_log(user_id: str, title: str, url: str, action: str = "like"):
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


def _render_sidebar(users: List[Dict]) -> Dict:
    st.sidebar.header("Settings")

    user_ids = [user["user_id"] for user in users]
    selected_user = st.sidebar.selectbox("用户", options=user_ids)
    user_data = next(user for user in users if user["user_id"] == selected_user)

    st.sidebar.subheader("兴趣管理")
    tag_added_key = f"tag-added-{selected_user}"
    if tag_added_key in st.session_state:
        st.sidebar.success(f"已添加新标签：{st.session_state.pop(tag_added_key)}")
    available_tags = sorted(
        {tag for user in users for tag in user["interests"]} | set(user_data["interests"])
    )
    selected_interests = st.sidebar.multiselect(
        "兴趣标签",
        options=available_tags,
        default=user_data["interests"],
    )
    if set(selected_interests) != set(user_data["interests"]):
        _update_interests(selected_user, selected_interests)
        st.sidebar.success("兴趣标签已更新")
    with st.sidebar.form(key=f"add-tag-form-{selected_user}"):
        new_tag = st.text_input("新增标签")
        add_clicked = st.form_submit_button("添加标签")
    if add_clicked and new_tag:
        normalized = new_tag.strip()
        if normalized:
            if normalized in selected_interests:
                st.sidebar.info("该标签已存在")
            else:
                updated = selected_interests + [normalized]
                _update_interests(selected_user, updated)
                st.session_state[tag_added_key] = normalized
                st.rerun()

    st.sidebar.subheader("数据控制")
    if st.sidebar.button("Run Crawler"):
        with st.spinner("爬虫运行中..."):
            run_crawlers()
        st.sidebar.success("爬虫已运行完成")

    return user_data


def _render_recommendations(user_id: str):
    st.title("AI 技术资讯推荐")
    if "current_user" not in st.session_state:
        st.session_state.current_user = user_id
    if st.session_state.current_user != user_id:
        st.session_state.current_user = user_id
        st.session_state.pop("recommendations", None)
        st.session_state.pop("recommendations_info", None)

    if st.button("Refresh Recommendation"):
        with st.spinner("AI 正在生成推荐..."):
            items, diagnostic = recommend_articles(user_id)
        st.session_state["recommendations"] = items
        st.session_state["recommendations_info"] = diagnostic

    recommendations = st.session_state.get("recommendations", [])
    diagnostic = st.session_state.get("recommendations_info")
    if not recommendations:
        if diagnostic:
            st.warning(diagnostic)
        st.info("点击【Refresh Recommendation】获取新推荐。")
        return
    if diagnostic:
        st.warning(diagnostic)

    for idx, article in enumerate(recommendations):
        with st.container():
            if article.get("top_image"):
                st.image(article["top_image"], use_column_width=True)
            st.markdown(f"### {article.get('title')}")
            summary = article.get("summary") or "暂无摘要"
            st.markdown(f"> {summary}")
            if article.get("reason"):
                st.caption(f"推荐理由：{article['reason']}")
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(
                    f'<a href="{article["url"]}" target="_blank">阅读原文</a>',
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("👍 感兴趣", key=f"like-{user_id}-{idx}"):
                    _insert_user_log(user_id, article.get("title", ""), article["url"], "like")
                    st.toast("已记录偏好")


def main():
    users = _fetch_users()
    if not users:
        st.error("请先在 MySQL 中创建至少一个用户。")
        return
    user_data = _render_sidebar(users)
    _render_recommendations(user_data["user_id"])


if __name__ == "__main__":
    main()
