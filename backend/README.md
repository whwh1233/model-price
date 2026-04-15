# Model Price Backend

AI 模型定价 API 服务，基于 FastAPI 构建。所有接口走 v2 entity/offering 模型。

## 技术栈

- **Python** >= 3.12
- **FastAPI** - Web 框架
- **uvicorn** - ASGI 服务器
- **httpx** - 异步 HTTP 客户端
- **Playwright** - 浏览器自动化（用于爬虫）
- **Pydantic** - 数据验证
- **uv** - 包管理器

## 快速开始

```bash
uv sync
uv run playwright install chromium    # 首次运行需要
cp .env.example .env                  # 可选，按需修改
uv run main.py                        # http://localhost:8000
```

- API 文档: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v2/entities` | 获取模型列表（支持筛选、排序） |
| GET | `/api/v2/entities/{slug}` | 获取单个模型详情（含所有 offerings + 替代推荐） |
| GET | `/api/v2/search` | 模糊搜索 |
| GET | `/api/v2/compare?ids=a,b,c,d` | 对比最多 4 个模型 |
| GET | `/api/v2/stats` | 统计信息 |
| GET | `/api/v2/drift` | 最近一次刷新的 drift 报告 |
| POST | `/api/v2/refresh` | 触发全量刷新（providers + LiteLLM → entity store） |
| GET | `/api/health` | 健康检查（keepalive 每 10 分钟 ping） |
| POST | `/api/refresh` | 兼容别名，内部等价于 `POST /api/v2/refresh`（`?provider=` 参数被忽略） |

## 项目结构

```
backend/
├── main.py               # FastAPI 入口、/api/health、/api/refresh 兼容别名
├── api_v2.py             # /api/v2/* 路由
├── config.py             # 配置（pydantic-settings）
├── models/
│   ├── pricing.py        # Pricing / BatchPricing / ModelPricing（providers 中间产物）
│   └── v2.py             # 对前端冻结的 API 契约
├── providers/            # 价格数据源
│   ├── base.py           # BaseProvider + fallback 加载
│   ├── registry.py       # 并发协调
│   └── {aws_bedrock,azure_openai,openai,google_gemini,openrouter,xai}.py
├── services/
│   ├── entity_store.py   # 线程安全的 v2 实体内存存储
│   ├── offering_merger.py# providers 原始数据 + LiteLLM → EntityStoreSnapshot
│   ├── canonical.py      # provider_model_id 归一化
│   ├── litellm_registry.py
│   ├── alternatives.py   # 同档更便宜推荐
│   ├── drift_reporter.py
│   ├── refresh_scheduler.py  # 定时调 entity_store.refresh_from_pipeline
│   ├── openai_scraper.py     # providers/openai.py 的子进程 scraper
│   └── google_gemini_scraper.py
├── data/
│   ├── v2/               # 实体快照（entities.json / offerings.json / drift.json）
│   └── fallback/         # 单家 provider 网络失败的降级静态数据
└── pyproject.toml
```

**数据流**：`providers/*.fetch()` → `ProviderRegistry.fetch_all_grouped()` → `offering_merger.run_refresh_pipeline()` → `EntityStore.refresh_from_pipeline()` → `data/v2/*` → `/api/v2/*`

## 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 服务监听地址 |
| `PORT` | `8000` | 服务端口 |
| `RELOAD` | `true` | 开发模式热重载 |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | 允许的跨域来源 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `HTTP_TIMEOUT` | `60.0` | HTTP 请求超时（秒） |
| `AUTO_REFRESH_ENABLED` | `true` | 是否启用后台定时全量刷新 |
| `AUTO_REFRESH_INTERVAL_SECONDS` | `3600` | 定时刷新间隔（秒），默认每小时 |

完整配置见 `.env.example`。

## 数据获取方式

| 提供商 | 获取方式 | 技术方案 |
|--------|----------|----------|
| AWS Bedrock | 公开 API | httpx 异步请求 |
| Azure OpenAI | 公开 API | httpx + 分页 |
| OpenAI | 网页爬虫 | Playwright |
| Google Gemini | 网页爬虫 | Playwright |
| OpenRouter | 公开 API | httpx 异步请求 |
| xAI | 静态数据 | 硬编码 |

任何一家 scraper 失败时，`offering_merger` 自动降级到 `data/fallback/<provider>.json`。

## 开发

```bash
uv add <package-name>     # 添加依赖
uv run pytest             # 跑测试
uv tool run pyright       # 类型检查
```

### 添加新的数据提供商

1. 在 `providers/` 下创建新文件，继承 `BaseProvider`
2. 实现 `async def fetch()` 方法
3. 在 `providers/__init__.py` 中导入并注册
4. 可选：在 `data/fallback/<name>.json` 提供降级数据
