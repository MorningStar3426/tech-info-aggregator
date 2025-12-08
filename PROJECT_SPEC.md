# 软件需求规格说明书 (Technical Specification Document)

**项目名称**：基于用户行为反馈的智能科技情报聚合系统
**版本**：V1.0.0
**适用对象**：AI 辅助编程工具
**日期**：2025-12-08

---

## 1. 项目概述 (Project Overview)

### 1.1 背景
本项目旨在开发一个智能化的技术资讯聚合平台。区别于传统的关键词检索，本系统利用**网络爬虫**获取多源异构数据，结合**大语言模型 (LLM)** 的语义理解能力，实现内容的自动摘要与清洗。同时，系统构建了**用户行为反馈闭环**，通过记录用户的点击行为，实时调整推荐策略，实现个性化分发。

### 1.2 核心功能
1.  **多源异构数据采集**：自动化抓取掘金 (Juejin)、Hacker News、GitHub Trending 等平台数据。
2.  **全文解析与清洗**：集成 NLP 工具提取网页正文，去除广告与无关 DOM 元素。
3.  **混合数据库架构**：采用 MySQL 存储结构化用户行为数据，MongoDB 存储非结构化文章数据。
4.  **AI 增强推荐引擎**：基于 RAG (Retrieval-Augmented Generation) 思想，利用 LLM 根据用户历史行为生成推荐列表及中文摘要。
5.  **交互式 Web 界面**：提供可视化操作界面，支持用户标签管理、内容浏览及兴趣反馈。

---

## 2. 系统架构设计 (System Architecture)

### 2.1 目录结构规范
项目文件结构需严格遵守以下规范：

```text
/project_root
│── config.py            # 全局配置文件 (API Keys, DB URLs)
│── database.py          # 数据库连接单例模式封装
│── crawler.py           # 爬虫与数据清洗核心逻辑
│── recommender.py       # AI 推荐算法与 LLM 交互逻辑
│── app.py               # Streamlit 前端主程序
│── requirements.txt     # 依赖包列表
└── PROJECT_SPEC.md      # 本文档
```

### 2.2 技术栈要求
*   **编程语言**: Python 3.9+
*   **Web 框架**: Streamlit, Streamlit-Extras
*   **数据存储**:
    *   Relational DB: MySQL (PyMySQL + SQLAlchemy Core)
    *   NoSQL DB: MongoDB (PyMongo)
*   **网络爬虫**: Requests, BeautifulSoup4, Newspaper3k (正文提取)
*   **人工智能**: OpenAI SDK (兼容 DeepSeek/Moonshot API 格式),python-dotenv

---

## 3. 数据库设计 (Database Schema)

### 3.1 MySQL 数据库设计
**库名**: `tech_rec_db`
**用途**: 存储用户画像与行为日志。

#### 表 1: `users` (用户表)
| 字段名 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `user_id` | VARCHAR(50) | PRIMARY KEY | 用户唯一标识 (如 'user_001') |
| `username` | VARCHAR(50) | NOT NULL | 用户名 |
| `interests` | TEXT | NULL | JSON 字符串，存储兴趣标签 (如 `["Python", "AI"]`) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | 创建时间 |

#### 表 2: `user_logs` (行为日志表)
| 字段名 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `log_id` | INT | PRIMARY KEY, AUTO_INCREMENT | 自增主键 |
| `user_id` | VARCHAR(50) | INDEX | 外键关联用户 |
| `article_title` | VARCHAR(255)| NOT NULL | 文章标题 (用于语义匹配) |
| `article_url` | TEXT | NOT NULL | 文章链接 |
| `action_type` | VARCHAR(20) | DEFAULT 'click' | 行为类型 (click, like, dislike) |
| `log_time` | TIMESTAMP | DEFAULT NOW() | 记录时间 |

### 3.2 MongoDB 数据库设计
**库名**: `tech_crawler`
**集合**: `articles_pool`
**用途**: 存储爬取的原始数据及清洗后的全文。

**Document 结构示例**:
```json
{
  "url": "https://...",             // 唯一索引 (Unique Index)
  "title": "DeepSeek V3 Released",
  "source": "Hacker News",
  "publish_date": "2023-12-08",
  "raw_tags": ["AI", "LLM"],
  "brief_summary": "...",           // 原始简介
  "full_text": "...",               // Newspaper3k 提取的纯文本 (截取前3000字符)
  "top_image": "https://..."        // 文章头图 URL
}
```

---

## 4. 功能模块详细说明 (Functional Specifications)

### 4.1 爬虫模块 (`crawler.py`)

#### 功能需求
1.  **通用正文提取器 (`fetch_article_content`)**:
    *   **输入**: URL 字符串。
    *   **处理**: 使用 `newspaper3k.Article` 下载并解析。
    *   **异常处理**: 必须包含 try-except 块，处理 403/404/Timeout 错误。
    *   **输出**: 包含 `text` (截取前3000字符) 和 `top_image` 的字典。若失败返回 None。

2.  **多源采集器 (`run_crawlers`)**:
    *   **源 A - 掘金后端热榜**:
        *   API: `https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot`
        *   逻辑: 提取前 10 条数据。
    *   **源 B - Hacker News Top Stories**:
        *   API: `https://hacker-news.firebaseio.com/v0/topstories.json` (获取 IDs) -> `https://hacker-news.firebaseio.com/v0/item/{id}.json` (获取详情)。
        *   逻辑: 获取前 10 条，且必须包含 URL 字段。
    *   **源 C - GitHub Trending**:
        *   URL: `https://github.com/trending`
        *   逻辑: 使用 BeautifulSoup 解析 HTML，提取 `h2 a` (项目名/链接) 和 `p` (描述)。

3.  **数据持久化**:
    *   获取数据后，立即调用 `fetch_article_content` 补全正文。
    *   使用 `pymongo.update_one` 的 `upsert=True` 模式存入 MongoDB，以 `url` 为去重键。

### 4.2 推荐算法模块 (`recommender.py`)

#### 功能需求
1.  **上下文构建**:
    *   从 MySQL 读取目标用户的 `interests` (JSON Load) 和最近 5 条 `user_logs`。
    *   从 MongoDB 随机采样 20-30 篇包含 `full_text` 的文章作为候选池。

2.  **LLM 交互逻辑 (ModelScope 适配版)**:
    *   **Client 初始化**:
        ```python
        from openai import OpenAI
        client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL"), # 对应魔搭社区 URL
            api_key=os.getenv("LLM_API_KEY")    # 对应魔搭 Token
        )
        ```
    *   **Prompt 构建**:
        *   **System**: "You are a tech recommendation engine. Output strictly valid JSON."
        *   **User**: "Context: {interests}, History: {click_history}. Candidates: {candidates}. ... Return JSON list."
    *   **API 调用 (关键配置)**:
        *   调用 `client.chat.completions.create`。
        *   **Model**: 使用环境变量 `LLM_MODEL_NAME`。
        *   **Extra Body**: 传入参数 `extra_body={"enable_thinking": False}`。
            *   *注意*：必须设置为 `False`，防止模型输出“思考过程”导致 JSON 解析失败。
        *   **Stream**: 设置 `stream=False`。
            *   *注意*：必须关闭流式输出，我们需要等待完整响应以进行 `json.loads` 解析。
    *   **解析逻辑**:
        *   获取 `response.choices[0].message.content`。
        *   去除 Markdown 代码块标记（如 ```json ... ```）。
        *   使用 `json.loads` 解析为 Python 列表。

3.  **容错处理**:
    *   如果 JSON 解析失败，捕获 `json.JSONDecodeError` 并返回空列表或备选数据，防止程序崩溃。

### 4.3 前端交互模块 (`app.py`)

#### 界面规范 (Streamlit)
1.  **侧边栏 (Settings)**:
    *   **用户切换**: 下拉框选择 `user_id`。
    *   **兴趣管理**: `st.multiselect` 组件，允许用户增删兴趣标签。变更时同步更新 MySQL。
    *   **数据控制**: 提供 "Run Crawler" 按钮，手动触发爬虫更新数据库。

2.  **主内容区 (Feed)**:
    *   **顶部**: "Refresh Recommendation" 按钮。点击后调用 `recommender.py`。
    *   **内容流**: 使用 `st.container` 循环展示推荐卡片。

#### 卡片组件设计
每张文章卡片需包含：
*   **头图**: `st.image` (若有)。
*   **标题**: `st.markdown("### Title")`。
*   **AI 摘要**: 使用引用块 `> Summary` 展示，突出其为 AI 生成。
*   **操作栏**:
    *   `[阅读原文]` 链接 (target="_blank")。
    *   `[👍 感兴趣]` 按钮。

#### 交互逻辑 (关键)
*   **点击反馈**:
    *   当用户点击 "👍" 时，**禁止** 使用 `st.rerun()` 刷新全页。
    *   应直接调用 MySQL 插入函数记录日志。
    *   使用 `st.toast("已记录偏好")` 进行轻量级提示。

---

## 5. 配置与常量 (Configuration)

在 `config.py` 中需要定义以下常量：

```python
load_dotenv()

# Database Config
MYSQL_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'), 
    'db': os.getenv('DB_NAME', 'tech_rec_db'),
    'charset': 'utf8mb4'
}
MONGO_URI = os.getenv('MONGO_URI')

# LLM Config
LLM_API_KEY = "你的_ModelScope_Token"
LLM_BASE_URL = "https://api-inference.modelscope.cn/v1"
LLM_MODEL_NAME = "deepseek-ai/DeepSeek-V3.2" # 或 "deepseek-ai/DeepSeek-R1"

# Crawler Config
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
```

---

## 6. 实施步骤 (Implementation Roadmap)

AI 助手请按以下顺序生成代码并进行验证：

1.  **Phase 1**: 编写 `database.py` 与 `db_init.py`，建立数据库表结构与索引。
2.  **Phase 2**: 编写 `crawler.py`，测试三个源的数据抓取与 `newspaper3k` 的解析功能，确保 MongoDB 中有数据。
3.  **Phase 3**: 编写 `recommender.py`，调试 LLM 的 Prompt，确保输出稳定的 JSON 格式。
4.  **Phase 4**: 编写 `app.py`，整合前后端，调试点击反馈与日志记录功能。

---