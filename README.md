# 价值投资学习系统 · Value Investing Learning System

> 一套面向个人的、端到端的价值投资学习与（半自动化）交易方法论。
> 用 Markdown 写、用一个脚本生成静态网站、用一条命令（或合并 PR）部署上线。

这不是一份「投资建议」，而是一套**学习的脚手架**——把「消费内容 → 拆解框架 → 影响决策 → 复盘验证 → 修订方法论」做成可持续运转的闭环。重心：美股 ~50% / A股 ~30% / 加密 ≤20%（仓位 ≤5% 净资产）。

---

## 在线访问

整站是响应式 HTML，手机端友好。入口是 **Dashboard**（部署后访问你服务器的根路径 `/`）。

本地预览：

```bash
pip install -r requirements-build.txt
python build.py --serve     # → http://localhost:8000/dashboard.html
```

---

## 它包含什么

| 层 | 内容 |
|---|---|
| **方法论** | `index.html` — 21 章核心方法论 v1.1（Pabrai + Marks 起点、经典文本 vs 信号流、前 180 天禁 DCF…） |
| **学习** | 90/270/720 进度追踪、经典文本清单、失败案例研究、估值 4 工具 cheatsheet |
| **Routine** | 每日 / 每周 / 每月 / 每季模板、术语表、watchlist、Week 0 onboarding、自动熔断 governance |
| **研究** | 公司深度研究模板、决策日志、第一家公司 SOP |
| **反馈** | 批判性反馈框架（每日 status → 7 维度反馈） |
| **自动化** | M1 每日早报飞书 bot（yfinance + akshare + Claude + hermes send → 飞书） |

---

## 架构

```
Markdown 源文件  ──build.py──►  dist/ (静态站点)  ──rsync──►  服务器 nginx
     (你写)                       (生成物, 镜像结构)              (公网可访问)
```

- **写**：所有内容用 Markdown（好写、git 友好）。已有的交互页面（进度勾选等）是手写 HTML，带 localStorage。
- **构建**：`build.py` 把每个 `.md` 转成风格统一、移动端友好的 `.html`，复制现有 HTML，并把内部 `.md` 链接重写为 `.html`，输出到 `dist/`。
- **部署**：本地 `./deploy.sh` 一键，或合并 PR 到 `main` 由 GitHub Actions 自动部署。详见 [`DEPLOY.md`](DEPLOY.md)。

---

## 日常工作流

1. 改 / 新增 Markdown
2. `python build.py --serve` 本地预览
3. 提 PR → review → 合并到 `main`
4. GitHub Actions 自动构建 + 部署上线

新增任何 `.md` 都会被自动纳入网站，无需额外配置。

---

## 目录

```
.
├── index.html              # 方法论 v1.1（手写，富交互）
├── dashboard.html          # 总入口 hub
├── build.py                # 静态站点生成器
├── deploy.sh               # 本地一键部署
├── server-setup.sh         # 服务器初始化（幂等）
├── assets/style.css        # 共享设计系统
├── learning/               # 学习层（4 个交互 HTML）
├── routine/                # routine 模板 + governance（Markdown）
├── research/               # 公司研究 / 决策日志模板
├── feedback/               # 批判性反馈框架
├── automation/             # M1 每日早报 bot
└── .github/workflows/      # CI 自动部署
```

---

## 说明

- 这是个人学习项目，内容是教育性质的方法论整理，**不构成任何投资建议**。
- `journals/`、`.env`、`config.yaml` 等私有数据不进版本库（见 `.gitignore`）。
- 方法论是 living document：修订建议进 [`methodology-patches.md`](methodology-patches.md) 队列，季度末统一合入。
