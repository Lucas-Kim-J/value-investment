# M1 · Daily Briefing TG Bot

> 每日早报自动化的最小可用版本。**预计耗时**：从 0 到跑通 ~2-3h。

---

## 它做什么

每天定时（默认北京时间 07:25）拉取：
- 美股隔夜：SPX / IXIC / VIX / DXY / BTC / ETH
- 你的美股持仓涨跌
- 你的 A 股持仓涨跌 + 北向资金
- 你的 watchlist 财报日历（未来 7 天）

然后用 Claude 生成中文 ≤ 600 字晨报，推送到 Telegram。

---

## 你能不能用？

**这个版本适合**：
- 想最少时间搭起来（不需要自建数据库）
- 接受 yfinance / akshare 数据偶有错误的可接受程度（决策前永远 cross-check 一手源）
- 有 Telegram + Anthropic API key

**这个版本不适合**：
- 想要分钟级实时监控（这是日级的）
- 想做下单（这只是信息推送）
- 加密 24/7 监控（加密只在每日一次扫描）

---

## 安装步骤

### 1. Python 环境

```bash
# 需要 Python 3.11+
cd /Users/Zhuanz/Documents/code/value-investment/automation/daily-briefing

# 建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 装依赖
pip install -r requirements.txt
```

### 2. 拿三把钥匙

#### Anthropic API Key

- 去 [console.anthropic.com](https://console.anthropic.com)
- Settings → API Keys → Create Key
- 复制 `sk-ant-...`

#### Telegram Bot Token + Chat ID

- 在 Telegram 搜 `@BotFather`，发 `/newbot`
- 起名字（如 `LucasValueBriefing`）
- BotFather 会给你 `123456:ABC-DEF...` 这个 token
- 然后给你的 bot 发一条消息（任意内容）
- 浏览器打开 `https://api.telegram.org/bot<TOKEN>/getUpdates`
- 找到 `"chat":{"id":数字}` —— 这是你的 chat_id

### 3. 配置

```bash
# 复制示例
cp .env.example .env
cp config.example.yaml config.yaml

# 编辑 .env，填入三把钥匙
# 编辑 config.yaml，填入你的持仓 + watchlist
```

### 4. 本地试跑

```bash
python briefing.py
```

成功会推一条 Telegram 消息给你。

---

## 定时运行

### 选项 A：Mac 本地 cron（最简单）

```bash
crontab -e
# 加一行（北京时间 07:25 = UTC 23:25 前一天，调整成你机器的时区）
25 7 * * * cd /Users/Zhuanz/Documents/code/value-investment/automation/daily-briefing && .venv/bin/python briefing.py >> briefing.log 2>&1
```

缺点：电脑要开着。

### 选项 B：GitHub Actions（推荐，免费且免开机）

1. 把整个 `value-investment/` 推到一个 GitHub **私库**
2. 把 `automation/daily-briefing/github-actions-example.yml` 内容拷到 `.github/workflows/briefing.yml`
3. 在 GitHub repo Settings → Secrets and variables → Actions，加：
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. push 之后 Actions tab 看到工作流；可手动 trigger 测试

### 选项 C：远程 VPS

任何 $5/月 的小机器跑 cron。最稳。

---

## 文件结构

```
automation/daily-briefing/
├── README.md                       # 这份
├── briefing.py                     # 主脚本
├── requirements.txt                # Python 依赖
├── .env.example                    # 三把钥匙模板
├── .env                            # 你的真实 keys（gitignore）
├── config.example.yaml             # 持仓 / watchlist 模板
├── config.yaml                     # 你的真实配置（gitignore）
└── github-actions-example.yml      # GitHub Actions cron 示例
```

务必 `.gitignore` `.env` 和 `config.yaml`（这些有持仓和 API key）。

---

## 如何扩展

### 加新数据源

在 `briefing.py` 加新 `fetch_*` 函数 → 在 `build_briefing` 调用 → 传给 Claude prompt。

例子：
- 加 OpenInsider cluster buying：每周一次扫
- 加 Dataroma 13F diff：每季度一次
- 加 Glassnode BTC ETF 资金流：每日一次

### 改 prompt 风格

`build_briefing` 函数里的 prompt 控制输出风格。可以试：
- 加你方法论 §X 的引用作为 system context
- 加上周 status 让 Claude 做 trend 反馈
- 让 Claude 把异动事件关联到失败案例归因

### 改触发频率

cron 表达式改一改，或加多个工作流（如周末加一份周复盘提示）。

---

## 已知限制

- **yfinance 数据偶有错误**：分红日期、stock split 调整可能晚；只用于初筛
- **akshare 字段偶变**：A 股接口偶尔返回字段重命名，加 schema 校验
- **VIX / DXY 周末不更新**：处理 stale 数据
- **加密价格 24/7**：早报里加密只是 snapshot，不构成实时信号
- **Telegram 消息长度限制**：4096 字符。Claude prompt 限制 800 tokens 输出避免超长

---

## 与方法论的关系

这是 §17 自动化路线的 **M1**。完成后：
- **M2**（30 天后）：加 13F 监控（Dataroma diff）+ insider cluster buying
- **M3**（60 天后）：加 财报日历 highlight（不是 RAG）

**不在这个 bot 范围内**：决策建议、买卖信号。任何"建议买入"类输出都被 prompt 明确禁止。
