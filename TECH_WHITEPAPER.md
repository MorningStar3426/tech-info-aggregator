# 智能技术情报聚合平台 · 技术实现白皮书

## 1. 项目概述（Overview）

智能技术情报聚合平台是一套面向开发者的多源资讯系统，融合了混合爬虫、用户画像、AI 摘要与低代码助手能力。通过对掘金、GitHub Trending、Hacker News 等渠道的自动抓取与聚合，它解决了“信息茧房、资讯冗余、缺乏个性化表达”等痛点。系统输出包含两大关键体验：**每日科技早报**（广播式总览）与**AI 辣评推荐**（毒舌式个性化点评），辅以前端的兴趣选择与 Dify AI 助手，实现“内容获取 + AI 互动 + 用户反馈”的闭环。

## 2. 技术栈架构（Tech Stack）

| 层级 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | Bootstrap 5 + Jinja2 + 原生 ES6 | `templates/index.html` 负责布局与 Dify Iframe；`static/js/main.js` 实现 AJAX、打字机、Toast；`static/css/style.css` 定制样式 |
| 后端 | Flask | `server.py` 提供页面与 `/api/daily_flash`、`/api/recommend`、`/api/log_action` 接口，使用 SQLAlchemy 文本查询 MySQL |
| 数据层 | MySQL + MongoDB | MySQL 存储用户/兴趣/日志（`db_init.py`），MongoDB 存储文章池（`database.py` 单例封装） |
| 爬虫 | Selenium + Requests + BeautifulSoup | `crawler.py` 通过 Selenium 爬掘金、Requests 爬 GitHub/HN，并补全 OG 图或 Picsum 占位图 |
| AI 集成 | OpenAI SDK (ModelScope/DeepSeek) + Dify Iframe | `recommender.py` 调用 LLM 生成广播词和辣评；`templates/index.html` Iframe 引入 Dify Chatbot（Token 来自 `server.py` 环境变量） |

数据流：爬虫写入 Mongo -> Flask 调用 `recommender.py` 获取 JSON -> 前端 `main.js` 渲染卡片 -> 用户行为写回 MySQL -> Dify Iframe 供即时 AI 对话。

## 3. 核心功能模块（Core Modules）

### 3.1 爬虫系统
* **掘金**：`crawler.py` 中的 `crawl_juejin_selenium()` 使用 Headless Chrome，模拟滚动、过滤广告、抓取 `.entry-list .entry` 卡片，生成 `title/url/summary/top_image/tags`，来源标记为 `juejin`。
* **GitHub Trending**：Requests + BeautifulSoup 解析 `article.Box-row`，补齐 `og:image` 失败则使用 Picsum，占位 URL 为 `https://picsum.photos/seed/{repo}/800/400`。
* **Hacker News**：先取 Top stories ID，再逐条抓 `item/{id}` JSON，调 OG 图或 Picsum，覆盖 `source="hackernews"`。
* **数据落库**：所有文章写入 Mongo `articles` 集合，通过 `_upsert_articles()` 以 URL 为键 upsert，保证幂等。

### 3.2 数据库设计
* **MySQL**：`users(user_id, username, interests, created_at)`；`user_logs(log_id, user_id, article_title, article_url, action_type, log_time)`；`db_init.py` 使用 SQLAlchemy 元数据建表并创建 `idx_user_logs_user_id` 索引。
* **MongoDB**：`articles` 集合保存 `title/url/summary/source/tags/top_image/publish_date/updated_at`，`db_init.py` 创建 URL 唯一索引。连接由 `database.py` 提供。

### 3.3 情报聚合与渲染
* **每日科技早报**：`recommender.py::generate_daily_flash()` 取最新十条标题，构造幽默广播 Prompt，调用 LLM 返回文本；`/api/daily_flash` 提供 JSON；前端 `fetchDailyFlash()` 触发打字机效果逐字显示。
* **AI 辣评推荐**：`recommend_articles()` 先按兴趣调 `_query_articles_by_tags()`，不足则 `_query_mixed_candidates()` 从三源各取至少一条再补最新文章；生成编号 Prompt（ID 1..n），要求 LLM 输出 `{"index": n, "ai_comment": "...", "tag_match": "..."}`，解析后用序号映射回文章并降级到默认文案时仍保留原始 `source`。
* **前端渲染**：`main.js` 根据 `/api/recommend` 返回的列表创建卡片，包括头图、标题、AI 辣评、原文链接、点赞按钮，并在空状态下提示“点击看点有意思的 🤓”。

### 3.4 用户画像系统
* 服务器端 `server.py` 渲染模板时注入 `users`，前端通过 `window.APP_USERS` 缓存；`syncUserInterests()` 根据当前用户回填复选框。
* 兴趣选择逻辑：页面初始展示当前用户的兴趣；用户勾选/取消后无需写回服务器，直接作为 `/api/recommend` 请求体中的 `interests` 参数，LLM 即时获得新画像。
* 行为日志：点赞按钮调用 `/api/log_action`，Flask 记录 `user_logs`，为后续画像迭代提供数据。

### 3.5 AI 助手集成（重点）
* **iframe 集成**：`templates/index.html` 侧边栏新增一块 600px 高的卡片，使用 `<iframe src="https://udify.app/chatbot/{{ dify_token }}">` 加载 Dify 提供的 Chatbot。`server.py` 在渲染时从环境变量读取 `DIFY_TOKEN`，注入 Jinja 参数，确保部署时无需修改模板即可切换 Bot。
* **Token 传递**：Dify Token 不写死在前端，而是通过 `.env` -> `server.py` -> 模板参数 -> iframe URL 的链路动态注入，满足安全与切换需求。
* **AI 双模驱动**：Dify Iframe 面向运营/客服场景，随时答疑；`recommender.py` 面向内容生成，负责毒舌点评与早报播报，两者互不干扰但共享页面体验。

## 4. 关键代码逻辑（Key Logic）

* **Flask 路由**：`server.py` 定义四个核心端点。`GET /` 渲染页面并注入 `users/available_tags/dify_token`；`GET /api/daily_flash` 返回广播词；`POST /api/recommend` 调用 `recommend_articles()` 输出卡片 JSON；`POST /api/log_action` 将点赞行为写入 MySQL。
* **前端 `main.js`**：
  * `fetchDailyFlash()` -> `renderTypewriter()`：实现 40ms 间隔的打字机效果与闪烁光标。
  * `requestRecommendations()`：禁用按钮、POST JSON、渲染卡片、处理 warning Toast。
  * `renderCards()`：使用模板字符串拼装卡片 DOM，绑定 `like-btn`，点赞后调用 `/api/log_action` 并显示 Bootstrap Toast。
  * `syncUserInterests()`：阅读 `window.APP_USERS` 与当前 `<select>` 值同步复选框状态，确保兴趣选择与用户切换一致。

## 5. 项目亮点（Highlights）

1. **混合爬虫与媒体丰富度**：Selenium + Requests 的组合既能处理动态页面又能保持高效；OG 图解析 + Picsum 占位实现“每卡必图”，提升视觉一致性。
2. **多源候选与序号匹配**：`_query_mixed_candidates()` 保证每批推荐包含掘金/GitHub/HN，顺序匹配彻底解决了 LLM 返回 URL 不一致的问题，增强鲁棒性。
3. **AI 双重集成**：平台内置的 LLM 辣评与 Dify Iframe 形成“自动内容 + 人机互动”的双引擎，既能展示 AI 产出，又可让用户即时与 Bot 对话，降低集成成本。
4. **响应式与交互体验**：Bootstrap 5 + 自定义 CSS + 原生 JS 打造轻量且灵活的前端；打字机、Toast、按钮状态等细节表现出色，适合作为演示/路演项目。
5. **配置驱动与可运维性**：核心凭证（DB、LLM、Dify Token）均来源 `.env`；`requirements.txt` 纯 Python 依赖、`db_init.py` 一键建库、`server.py` 单命令启动，方便在多环境部署与迭代。
