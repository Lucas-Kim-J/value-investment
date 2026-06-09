# M1 · 每日早报飞书 Bot

> 每日早报自动化的最小可用版本，通过**飞书**推送（服务器上的 `hermes send`）。
> **预计耗时**：从 0 到跑通 ~30 min（不需要任何 bot token）。

---

## 它做什么

每天定时拉取：
- 美股隔夜：SPX / IXIC / VIX / DXY / 10Y / BTC / ETH
- 你的美股持仓涨跌（|Δ|>2% 标记 ⚠️）
- 你的 A 股持仓涨跌 + 北向资金
- 你的 watchlist 财报日历（未来 7 天）

然后构建一份中文纯文本晨报，通过 `hermes send --to feishu` 发到你的飞书。
（可选 `--llm`：用 Claude 把数据写成 ≤500 字摘要；不加则用结构化纯文本，无需任何 API key。）

---

## 关键设计：飞书走 hermes，代码里没有 token

推送由服务器上的 **hermes** 完成——hermes 持有飞书凭证。本脚本只是把早报文本通过管道交给 `hermes send`：

```
briefing.py  ──stdout──►  hermes send --to feishu  ──►  你的飞书
```

所以这个 bot **不需要**任何 bot token / key / webhook。`hermes send --list`（在服务器上跑）可看所有可用目标。

---

## 在哪里运行

**在服务器上运行**（hermes 装在那里）。本地只能 `--dry-run` 预览文本，不能真正发送（本地没有 hermes）。

---

## 安装步骤（在服务器上）

### 1. Python 环境

```bash
cd <repo>/automation/daily-briefing      # 服务器上 clone 的仓库
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml：填你的持仓 + watchlist + feishu_target（默认 'feishu'）
# 如需 Claude 摘要：cp .env.example .env 并填 ANTHROPIC_API_KEY
```

### 3. 试跑

```bash
python briefing.py --dry-run      # 只打印，不发送（先看格式对不对）
python briefing.py                # 真发到飞书（通过 hermes send）
```

成功会在飞书收到一条早报。

---

## 定时运行

### 选项 A：hermes cron（hermes 原生，推荐）

```bash
hermes cron create --name daily-briefing --schedule "25 7 * * *" \
  --command "<repo>/automation/daily-briefing/run-and-send.sh"
hermes cron list        # 查看
```

### 选项 B：系统 cron

```bash
crontab -e
# 07:25 北京时间（按服务器时区调整；服务器多为 UTC，则用 25 23 * * *）
25 7 * * *  <repo>/automation/daily-briefing/run-and-send.sh >> /var/log/daily-briefing.log 2>&1
```

`run-and-send.sh` 是一个薄封装：`cd` 到本目录 → `python3 briefing.py`。

---

## 文件结构

```
automation/daily-briefing/
├── README.md              # 这份
├── briefing.py            # 主脚本（拉数据 → 构建文本 → hermes send）
├── run-and-send.sh        # cron 封装
├── requirements.txt       # Python 依赖（无 HTTP client，hermes 负责发送）
├── .env.example           # 可选 ANTHROPIC_API_KEY（仅 --llm 需要）
├── .env                   # 你的真实 key（gitignore）
├── config.example.yaml    # 持仓 / watchlist / feishu_target 模板
└── config.yaml            # 你的真实配置（gitignore）
```

务必 `.gitignore` `.env` 和 `config.yaml`（持仓 + key）。仓库已配好。

---

## 如何扩展

### 加新数据源
在 `briefing.py` 加 `fetch_*` 函数 → 在 `main()` 的 `data` 字典里调用 → 在 `build_text()`（或 Claude prompt）里渲染。

例子：OpenInsider cluster buying（周扫）、Dataroma 13F diff（季）、Glassnode BTC ETF 资金流（日）。

### 多个推送
`hermes send --list` 看目标。可以早报发飞书私聊，异动 alert 发某个群——给 `briefing.py --to feishu:oc_xxxx` 指定不同 chat。

### 改触发频率
改 cron 表达式，或加多个 job（如周末加一份周复盘提示）。

---

## 已知限制

- **yfinance 数据偶有错误**：分红日期、stock split 调整可能晚；只用于初筛，决策前回一手源 cross-check
- **akshare 字段偶变**：A 股接口偶尔重命名字段；脚本已 fail-soft，但留意空值
- **VIX / DXY 周末不更新**：会是 stale 数据
- **加密 24/7**：早报里只是 snapshot，不构成实时信号
- **飞书消息**：纯文本最稳；如需富文本卡片，未来可让 hermes 用 interactive card

---

## 与方法论的关系

这是 §17 自动化路线的 **M1**。完成后：
- **M2**（30 天后）：加 13F 监控（Dataroma diff）+ insider cluster buying，异动推飞书
- **M3**（60 天后）：加财报日历 highlight（不是 RAG）

**不在范围内**：决策建议、买卖信号。脚本与 prompt 都明确禁止任何"建议买入/卖出"类输出——它只汇总信息，决策回到 decision log。
