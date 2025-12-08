"""
数据库连接封装。

提供 MySQL (SQLAlchemy + PyMySQL) 与 MongoDB (pymongo) 的单例实例，避免重复创建连接。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional
from urllib.parse import quote_plus

from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config import MONGO_URI, MYSQL_CONFIG

_mysql_engine: Optional[Engine] = None
_mongo_client: Optional[MongoClient] = None


def _build_mysql_url(config: dict) -> str:
    password = config.get("password") or ""
    quoted_password = quote_plus(password)
    return (
        f"mysql+pymysql://{config['user']}:{quoted_password}"
        f"@{config['host']}/{config['db']}?charset={config['charset']}"
    )


def get_mysql_engine(**overrides) -> Engine:
    """
    返回全局 MySQL Engine；支持覆盖部分配置，一般用于测试。
    """
    global _mysql_engine
    if _mysql_engine is None or overrides:
        config = {**MYSQL_CONFIG, **overrides}
        url = _build_mysql_url(config)
        _mysql_engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    return _mysql_engine


@contextmanager
def mysql_connection(**overrides) -> Generator:
    """
    提供 MySQL 连接上下文管理器，自动回收连接。
    """
    engine = get_mysql_engine(**overrides)
    with engine.begin() as connection:
        yield connection


def get_mongo_client(uri: Optional[str] = None) -> MongoClient:
    global _mongo_client
    if _mongo_client is None or uri:
        _mongo_client = MongoClient(uri or MONGO_URI, serverSelectionTimeoutMS=5000)
    return _mongo_client


def get_mongo_database(name: str = "tech_crawler"):
    return get_mongo_client()[name]
