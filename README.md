# 智能技术情报聚合平台

> 多源采集 · 个性推荐 · AI 总结 · Dify Iframe 助手  

## 功能概览

- **多源爬虫**：Selenium + Requests 抓取掘金（多分类）、GitHub Trending（多语言）、Hacker News，并自动补充头图（优先 OG 图，兜底 Picsum）。
- **内容聚合**：所有文章存入 MongoDB `articles` 集合，MySQL 则管理 `users`、`user_logs`，形成完整的用户—行为—内容闭环。
- **AI 双引擎**：
  - 内置 LLM（ModelScope/DeepSeek）生成每日科技早报与毒舌“AI 辣评”，通过 `/api/daily_flash`、`/api/recommend` 提供 JSON。
  - 侧边栏嵌入 Dify Iframe，实现“问答/助手”即时对话。
- **前端体验**：Bootstrap 5 + 原生 JS 构建响应式仪表盘；兴趣复选框、打字机早报、点赞 Toast、卡片式展示。

## 目录结构

```
.
├── config.py           # 环境变量加载（DB、LLM、Dify Token）
├── database.py         # MySQL / Mongo 单例封装
├── db_init.py          # 初始化 users / user_logs 表 & Mongo 索引
├── crawler.py          # 混合爬虫：掘金(Selenium)、GitHub/HN(Requests)
├── recommender.py      # 每日早报 + 辣评推荐 + 兴趣/多源策略
├── server.py           # Flask 路由：页面渲染 & REST API
├── static/             # CSS / JS（Bootstrap、交互逻辑、打字机特效）
├── templates/index.html# Bootstrap + Dify iframe 的主界面
├── TECH_WHITEPAPER.md  # 技术实现白皮书
├── DATA_STORE_DESIGN.md# 数据库与个性化设计说明
└── README.md
```

## 快速开始

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```
2. **配置环境变量 (`.env`)**
   ```
   DB_HOST=...
   DB_USER=...
   DB_PASSWORD=...
   MONGO_URI=...
   LLM_API_KEY=...        # ModelScope/DeepSeek Token
   DIFY_TOKEN=...         # Dify Chatbot ID
   ```
3. **初始化数据库**
   ```bash
   python db_init.py
   ```
4. **运行爬虫**
   ```bash
   python crawler.py
   ```
5. **启动后端**
   ```bash
   python server.py
   # 浏览器访问 http://localhost:8501
   ```

## API 摘要

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 渲染主界面，注入用户列表、兴趣标签、Dify Token |
| `/api/daily_flash` | GET | 返回每日科技早报（字符串） |
| `/api/recommend` | POST | 请求体 `{user_id, interests}`，返回带 `ai_comment` 的文章列表 |
| `/api/log_action` | POST | 请求体 `{user_id, url, title, action}`，写入 MySQL 行为日志 |

## 个性化推荐机制

1. **兴趣画像**：`users.interests` 存储 JSON 标签；前端复选框 + 即时参数让用户实时调整兴趣。
2. **候选筛选**：优先使用兴趣匹配结果，不足时 `_query_mixed_candidates()` 从三大来源各取 1+ 条补齐，保证多样性。
3. **AI 辣评**：向 LLM 发送带编号的候选列表，要求 JSON 返回 `{index, ai_comment, tag_match}`；按序号映射回文章生成卡片。
4. **行为回写**：点赞按钮调用 `/api/log_action`，记录 `user_logs`，为后续画像持续优化提供数据。

## 参考文档

- `TECH_WHITEPAPER.md`：项目整体技术实现白皮书（架构、模块、亮点）。
- `DATA_STORE_DESIGN.md`：MySQL / MongoDB 字段设计与推荐链路说明。
- `crawler.py` / `recommender.py`：核心逻辑实现，可结合白皮书对照阅读。

欢迎根据业务需求扩展爬虫渠道、LLM Prompt 或将 Dify Iframe 替换为其它助手服务。***
