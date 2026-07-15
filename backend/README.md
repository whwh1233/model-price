# Model Price Data Generator

这里保留价格抓取、归一化和快照生成逻辑。生产站不需要部署这个目录里的 FastAPI 服务；前端只读取 `frontend/public/v2-fallback.json`。

## 更新数据

推荐在仓库根目录运行：

```bash
./scripts/update-prices.sh
```

只跑后端快照生成：

```bash
uv sync
uv run playwright install chromium
uv run python scripts/refresh_snapshot.py
```

生成结果：

- `data/v2/entities.json`
- `data/v2/offerings.json`
- `data/v2/drift.json`

前端快照由 `frontend/scripts/build-v2-fallback.mjs` 从这些文件生成。

## 数据流

`providers/*.fetch()` → `ProviderRegistry.fetch_all_grouped()` → `offering_merger.run_refresh_pipeline()` → `data/v2/*` → `frontend/public/v2-fallback.json`

## 数据源

| 提供商 | 获取方式 |
|--------|----------|
| AWS Bedrock | 公开 API |
| Azure OpenAI | 公开 API + 分页 |
| OpenAI | Playwright 抓 pricing 页面 |
| Google Gemini | Playwright 抓 pricing 页面 |
| OpenRouter | 公开 API |
| xAI | 静态 fallback |

任何一家 scraper 失败时，`offering_merger` 会降级到 `data/fallback/<provider>.json`。

## 开发/调试

FastAPI 入口仍然保留，方便本地调试 API 或跑旧测试：

```bash
uv run main.py
uv run pytest
```
