# 项目开发规格说明书：智能技术情报聚合平台 v2.0

## 1. 项目概述

* **目标**：通过多源爬虫聚合前沿技术资讯，并利用 LLM 生成“每日早报”与“辣评推荐”，帮助用户摆脱信息茧房。
* **系统特性**：
  * **幽默/毒舌风格**：AI 输出不再是枯燥摘要，而是人格化点评。
  * **前后端解耦**：采用 Flask + Bootstrap，自定义 UI/交互。
  * **多源采集**：掘金多分类、GitHub Trending 多语言、Hacker News。

## 2. 技术栈

| 层级 | 组件 |
| --- | --- |
| 后端 | Python 3.9+, Flask, SQLAlchemy, PyMySQL, PyMongo |
| 前端 | HTML5, CSS3, Bootstrap 5, 原生 ES6 |
| 爬虫 | Requests, BeautifulSoup4 |
| AI | OpenAI SDK（ModelScope API 格式，DeepSeek-V3.2） |
| 数据库 | MySQL（用户/兴趣/日志）、MongoDB（文章池） |

## 3. 目录结构

```text
/tech_rec_project
│── config.py
│── database.py
│── db_init.py
│── crawler.py
│── recommender.py
│── server.py
│── requirements.txt
│── PROJECT_SPEC.md
│── templates/
│   └── index.html
└── static/
    ├── css/style.css
    └── js/main.js
```

## 4. 功能模块

### 4.1 配置（config.py & .env）
* 所有敏感信息从 `.env` 通过 `python-dotenv` 加载。
* ModelScope 兼容配置：
  * `LLM_BASE_URL = https://api-inference.modelscope.cn/v1`
  * `LLM_MODEL_NAME = deepseek-ai/DeepSeek-V3.2`
  * `LLM_API_KEY` 来源于魔搭 Token。

### 4.2 爬虫（crawler.py）
* **掘金分类**：`{'后端': 1, '前端': 6809637767543255054, 'AI': 6809637773935378440, 'Android': 6809635626879549454}`，每类取 Top20。
* **GitHub Trending**：抓取全站、Python、Java、JavaScript 四个榜单，每榜 Top10。
* **Hacker News**：Top20 stories。
* 所有文章存入 MongoDB `articles` 集合，`url` 为去重键，字段包含 `title/url/summary/source/tags/top_image/publish_date`。

### 4.3 AI 引擎（recommender.py）
* **generate_daily_flash**：从 Mongo 挑选 10 个标题，向 LLM 索要“大家早！”开头的 100 字广播词（含 Emoji）。
* **recommend_articles**：
  * 输入：`user_id` + 兴趣标签（若为空则使用 MySQL 中的兴趣）。
  * 文章筛选：优先匹配标签，不足时回退热门文章，保证非空。
  * Prompt：系统强调“毒舌、幽默、调皮的大V”，输出 JSON，字段 `title/url/ai_comment/tag_match`，`ai_comment` ≤ 40 字。
  * 容错：LLM 未配置或异常时使用 fallback（默认推荐语）。

### 4.4 后端 API（server.py）
* `GET /`：渲染首页，注入用户列表与可选标签。
* `GET /api/daily_flash`：返回早报文本。
* `POST /api/recommend`：接收 `{user_id, interests}`，调用推荐模块返回 JSON 列表。
* `POST /api/log_action`：记录 `{user_id, url, title, action}` 至 MySQL `user_logs`。

### 4.5 前端（templates/index.html + static/*）
* **布局**：顶部早报 Hero + 左侧设置（用户选择、兴趣复选框、CTA）+ 右侧三列卡片流。
* **卡片**：头图（无则占位）、标题、AI 辣评 `<blockquote>`、底部链接+点赞按钮。
* **交互**：
  * “每日早报”采用打字机特效（30~50ms/字符 + 闪烁光标）。
  * “看点有意思的🤓”按钮触发 AJAX，局部刷新卡片。
  * 点赞按钮调用 `/api/log_action`，使用 Bootstrap Toast 提示。

## 5. 实施步骤

1. `db_init.py` 初始化 MySQL 表与 Mongo 索引，配置 `.env`。
2. 运行 `python crawler.py`，保证 Mongo 数据量 50+。
3. 实现并验证 AI 模块（`generate_daily_flash`、`recommend_articles`），在无 LLM 情况下确保 fallback。
4. 编写 Flask `server.py` 与前端资源，联调 `/api/daily_flash`、`/api/recommend`、`/api/log_action`。
5. 通过 `flask --app server run` 或 `python server.py` 启动系统，确认爬虫/AI/前端联动。

