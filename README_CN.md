<div align="center">

<img src="frontend/public/logo.png" alt="Model Price" width="72" />

# Model Price

**并排对比 650+ 大模型 — 真实价格，真实能力。**

[modelprice.closeai.space](https://modelprice.closeai.space) · 为每天读 config 多过读官网的开发者打造

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react&logoColor=white)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tests](https://img.shields.io/badge/tests-118%20passing-brightgreen?style=flat-square)](#测试)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[English](README.md) · [简体中文](README_CN.md)

</div>

![首页](docs/screenshots/home-dark.png)

---

## 为什么做这个

每家 LLM 厂商都用自己的格式、自己的单位、自己的 cache 语义、自己的营销话术发布价格。想回答"这个功能用 Sonnet 4.5 还是 DeepSeek V3 更好"——结果打开六个 tab 配一张 Excel。

Model Price 把这件事收敛到 **一个键盘优先的页面**，它：

- 收录 **650+ 个模型**，覆盖 Anthropic、OpenAI、Google、xAI、Meta、DeepSeek、Moonshot AI、阿里云、Z.AI、MiniMax、Mistral、Cohere 以及其他 40+ 家厂商
- 所有价格统一换算到 **每 100 万 token**，横向数字可以直接对比
- 数据源自社区维护的 **LiteLLM 注册表** + 各 provider 直接抓取；需要更新时手动跑一次快照生成，不需要常驻后端服务
- **跨 provider 去重**：同一个 "Claude Sonnet 4.5" 是**一个** entity + 多个 offering（Anthropic / Bedrock / OpenRouter），而不是三行重复
- **可分享**：每个模型都有 `/m/:slug`，每次对比都有 `/compare/:ids`，都是干净 URL，粘到推特或微信都能打开

## 界面

### 首页 — 浏览、筛选 650+ 模型

![暗色首页](docs/screenshots/home-dark.png)

### Drawer — 零点击即可看到详情 + 同档更便宜的替代品

![详情 drawer](docs/screenshots/drawer-dark.png)

### 对比页 — 最多 4 个模型并排，共同能力高亮

![对比](docs/screenshots/compare-dark.png)

### ⌘K 命令面板 — 纯客户端模糊搜索，零网络

![命令面板](docs/screenshots/command-palette-dark.png)

### 亮色主题 — 温暖的 off-white，不是机关单位灰

<table>
<tr>
<td><img src="docs/screenshots/home-light.png" alt="亮色首页" /></td>
<td><img src="docs/screenshots/entity-page-light.png" alt="亮色详情页" /></td>
</tr>
</table>

## 亮点

- **键盘优先** — `⌘K` 打开模糊搜索面板，`↑↓` 导航、`Enter` 进入、`⌘C` 复制 `model_id`、`⌘D` 加入对比。全部客户端运行。
- **纯静态展示** — 每次访问都直接从 bundled `v2-fallback.json` snapshot 渲染；浏览、搜索、详情、对比都不需要后端服务。
- **"同档更便宜"推荐** — 每个详情页自动列出 3 个替代品，按 `能力重叠 × 价格节省` 打分（Jaccard over capability sets + input 价差加权）。算法在 `backend/services/alternatives.py`，构建 snapshot 时前端脚本里再跑一遍保持一致。
- **Drift report** — 每次刷新都生成 `drift.json`，列出匹配不上的 provider 模型、价差 > 5% 的条目、新增/移除的 entity。自愈式数据质量。
- **官方源链接** — 每个详情页都跳到厂商官方 pricing 和 docs 页面。我们提供索引，厂商提供事实。
- **暗色 / 亮色 / 跟随系统**主题切换，**EN / 中文**双语，都持久化到 localStorage。
- **Open Graph + Twitter Card** 元标签 + 自定义 OG 图片——粘到 X、Slack、微信（复制链接）、Discord、飞书都有漂亮 preview card。

## 工作原理

```
         ┌────────────────────────────────────────────────┐
         │  LiteLLM 注册表（单一真相源）                   │
         │  github.com/BerriAI/litellm                    │
         └────────────────┬───────────────────────────────┘
                          │  每次 refresh 拉 raw JSON
                          ▼
         ┌────────────────────────────────────────────────┐
         │  Canonical Entity 层                            │
         │  slug、family、maker、context、capabilities、    │
         │  modalities、primary_offering_provider          │
         └────────────────┬───────────────────────────────┘
                          │  通过反向 alias 表路由
                          ▼
  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
  │ Anthropic│ Bedrock  │  Azure   │  OpenAI  │OpenRouter│ xAI/etc. │
  │  fetch() │  fetch() │  fetch() │  fetch() │  fetch() │  fetch() │
  └────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┘
       └──────────┴──────────┴────┬─────┴──────────┴──────────┘
                                  ▼
                  ┌──────────────────────────────────┐
                  │  Offering Merger                 │
                  │  每条 provider 记录按严格的       │
                  │  slug + prefix + version 规则    │
                  │  映射到 canonical_id             │
                  └──────────────┬───────────────────┘
                                 ▼
                  ┌──────────────────────────────────┐
                  │  entities.json + offerings.json  │
                  │  + drift.json（数据质量告警）     │
                  └──────────────┬───────────────────┘
                                 ▼
                  ┌──────────────────────────────────┐
                  │  v2-fallback.json 快照           │
                  │  打包进静态前端                  │
                  └──────────────────────────────────┘
```

**两层数据模型**：**Entity**（逻辑模型，如 `claude-sonnet-4-5`）+ **Offering**（一个具体的 `(entity, provider)` 报价对，有自己的价格和更新时间）。同一个 `claude-sonnet-4-5` 是一个 entity + 三个 offering（Anthropic / Bedrock / OpenRouter），**不是**三行同名的独立条目。

## 技术栈

| 层 | 技术 |
|---|---|
| **数据生成** | Python 3.12, Pydantic v2, httpx, Playwright（Provider 爬虫）, pytest；FastAPI 入口保留为开发/调试工具 |
| **前端** | React 19, TypeScript 5.9, Vite 7, React Router 7, vitest + @testing-library/react + happy-dom |
| **数据** | LiteLLM `model_prices_and_context_window.json` + 各 provider 直接 API / 爬取，合并为 entity/offering JSON 文件，作为静态 snapshot 和 SPA 一起打包 |
| **部署** | Vercel 静态前端（`release` 分支 push 自动部署） |

## 本地开发

### 更新价格快照

```bash
./scripts/update-prices.sh
```

这会重新拉 LiteLLM、跑 provider scraper，写入 `backend/data/v2/entities.json` / `offerings.json` / `drift.json`，再生成前端使用的 `frontend/public/v2-fallback.json`。

### 前端

```bash
cd frontend
npm install

npm run dev                           # http://localhost:5173
npm test                              # 32 个前端测试
npm run build                         # 打包到 dist/
```

前端只读取 `frontend/public/v2-fallback.json`。通过 `VITE_PUBLIC_BASE_URL` 可以覆盖 "Copy Link" 和 "Share on X" 用的 public 域名（默认 `https://modelprice.closeai.space`）。

### 数据校对

```bash
cd backend
uv run --active python scripts/sanity_check.py
```

对 ~80 个主流大厂模型跑 hit-rate 校验。当前 **79% 命中率**——漏掉的是长尾边缘 case，记录在 `drift.json` 里。

### 重新生成 OG 封面图

```bash
cd backend
uv run --active python scripts/generate_og_cover.py
```

生成 `frontend/public/og-cover.png`（1200×630）。文案或配色改了就重跑一次。

### 生成 README 截图

```bash
cd backend
uv run --active python scripts/take_screenshots.py
```

用 Playwright Chromium 截生产站 —— home / drawer / 详情页 / 对比 / ⌘K 面板，暗色和亮色都截。

## 测试

**168 个测试**，全部 hermetic，完整套件 ~3 秒跑完：

- **数据生成（pytest，136 个）** — `slugify` / `strip_version_suffix`、家族识别顺序（防 "Codex 在 GPT 之前" 和 "Cogito 在 Llama 之前" 两个回归）、canonical resolver 级联、offering merger helpers、`compute_alternatives` 排序数学、`/api/v2/*` 契约测试（FastAPI `TestClient`）
- **前端（vitest + @testing-library/react + happy-dom，32 个）** — `formatPrice` / `formatContext` / `formatPct`、`CompareBasketProvider`（4 个容量上限、sessionStorage 持久化、provider 范围保护）、`ThemeProvider`（dark/light/system 循环、`matchMedia` 监听、`<html data-theme>` 同步）、`LocaleProvider`（默认 EN、`{name}` 插值、`<html lang>` 同步）

运行：

```bash
cd backend && uv run pytest
cd frontend && npm test
```

## 部署

`release` 分支是生产分支。

- **Vercel** 每次 `release` push 自动构建部署前端。配置在 `frontend/vercel.json`，catch-all rewrite 到 `index.html` 让 React Router 深链接生效。
- 生产站不需要 Render 后端和 keepalive；价格更新由 `./scripts/update-prices.sh` 手动生成静态快照后随前端一起部署。

上一版（v1）生产 tip 打了 tag `release-v1-backup` 作为回滚点。v1 路由（`/api/models`、`/api/providers`、`/api/families`、`/api/stats`、`/api/refresh/metadata`）已于 2026-04-15 移除。

## 设计文档

v2 重构的完整设计文档在 [`docs/plans/2026-04-14-v2-redesign-design.md`](docs/plans/2026-04-14-v2-redesign-design.md) —— 记录了产品定位（D 快查 + A 对比作为地基、C "同档更便宜" 作为差异化杀手锏）、目标用户（独立开发者 + 工具链开发者）、单点突破（⌘K + 可分享 URL）、两层数据模型、冷启动策略，以及所有明确不做的非目标。

v2 API 契约冻结在 [`docs/plans/v2-api-contract.md`](docs/plans/v2-api-contract.md)。

## 许可

MIT — 见 [LICENSE](LICENSE)。

数据来源：[BerriAI/litellm](https://github.com/BerriAI/litellm)（MIT）。感谢 LiteLLM 社区维护的注册表让这个站点成为可能。
