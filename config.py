"""
系统级配置常量。

所有敏感信息优先从 .env 环境变量读取，保持部署灵活性。
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Database Config
MYSQL_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME", "tech_rec_db"),
    "charset": "utf8mb4",
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# LLM Config
LLM_API_KEY = os.getenv("LLM_API_KEY", "你的_ModelScope_Token")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api-inference.modelscope.cn/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-ai/DeepSeek-V3.2")

# Crawler Config
USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    ),
)

