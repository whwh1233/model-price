# Model Price Frontend

静态前端，基于 React + TypeScript + Vite。页面数据来自 `public/v2-fallback.json`，浏览、搜索、详情和对比都不需要后端服务。

## 快速开始

```bash
npm install
npm run dev
```

本地地址：`http://localhost:5173`

## 构建

```bash
npm run build
```

构建会先运行 `scripts/build-v2-fallback.mjs`，把 `../backend/data/v2/entities.json` 和 `../backend/data/v2/offerings.json` 打包成 `public/v2-fallback.json`，然后输出到 `dist/`。

## 更新价格

在仓库根目录运行：

```bash
./scripts/update-prices.sh
```

这个脚本会刷新后端数据快照并重新生成前端静态快照。更新完成后正常构建/部署前端即可。

## 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `VITE_PUBLIC_BASE_URL` | `https://modelprice.closeai.space` | 复制链接和分享按钮使用的公开域名 |

## 脚本

```bash
npm run dev
npm run build
npm run test
npm run lint
```
