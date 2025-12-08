"""
数据库结构初始化脚本。

执行一次即可完成 MySQL 表和 MongoDB 索引创建。
"""
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TIMESTAMP,
    func,
    Index,
)

from database import get_mongo_database, get_mysql_engine


def init_mysql():
    metadata = MetaData()

    Table(
        "users",
        metadata,
        Column("user_id", String(50), primary_key=True),
        Column("username", String(50), nullable=False),
        Column("interests", Text, nullable=True),
        Column("created_at", TIMESTAMP, server_default=func.now()),
        mysql_charset="utf8mb4",
    )

    user_logs = Table(
        "user_logs",
        metadata,
        Column("log_id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", String(50), nullable=False),
        Column("article_title", String(255), nullable=False),
        Column("article_url", Text, nullable=False),
        Column("action_type", String(20), nullable=False, server_default="click"),
        Column("log_time", TIMESTAMP, server_default=func.now()),
        mysql_charset="utf8mb4",
    )
    Index("idx_user_logs_user_id", user_logs.c.user_id)

    engine = get_mysql_engine()
    metadata.create_all(engine, checkfirst=True)


def init_mongo():
    db = get_mongo_database("tech_crawler")
    collection = db["articles_pool"]
    collection.create_index("url", unique=True)


def main():
    init_mysql()
    init_mongo()
    print("MySQL 与 MongoDB 初始化完成。")


if __name__ == "__main__":
    main()

