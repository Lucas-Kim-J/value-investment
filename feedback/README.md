# Feedback System

> 你最关键的需求：每天反馈学习 / 交易状态，得到批判性反馈。这套系统让这件事可执行。

---

## 工作流程

### 你做的（每天 ≤ 5 min）

1. 用 `status-template.md` 写每日 status（或者直接在和 Claude 的对话里粘贴模板填好的内容）
2. 把它发给 Claude（这个 session 或后续 session）
3. Claude 用 `critical-feedback-framework.md` 给你批判性反馈

### Claude 做的

- 用 7 个维度评估你的 status（见 framework）
- 不夸奖，不安慰，**直接指出问题**
- 关联回方法论 v1.1 / circuit-breaker.md / 你的历史 status（memory）
- 给出具体的"明日修订动作"

---

## 三种反馈节奏

### 🌅 每日反馈（daily check-in）

- **触发**：你提交今日 status
- **Claude 输出**：
  - 1 个"今日最大的盲点"
  - 1 个"如果继续这个模式 4 周后会怎样"的预测
  - 1 个明日修订动作（具体到几分钟做什么）
- **耗时**：你写 3 min + Claude 反馈 ~1 page

### 📊 周度反馈（weekly debrief）

- **触发**：你提交本周 weekly-review.md
- **Claude 输出**：
  - 本周 7 天 status 的模式识别（哪些行为重复出现）
  - 周复盘里"形式主义" vs "真实洞察" 的比例
  - 触发了哪些 circuit-breaker 接近线
  - 与上周 / 上月对比的方向
- **耗时**：你写 30 min + Claude 反馈 1-2 pages

### 🪞 月度归因反馈（monthly attribution review）

- **触发**：你提交月度 attribution + decision log 复盘
- **Claude 输出**：
  - ex-ante vs ex-post 预测命中率
  - 你的"运气 vs 能力"判断里多少是 hindsight bias
  - 你 thesis 的可证伪性如何（哪些是"模糊的看好"哪些是"具体可证伪"）
  - 给方法论 v1.x 的修订建议
- **耗时**：你写 2 h + Claude 反馈 2-3 pages

---

## 反馈的原则（Claude 视角）

### 我承诺

1. **直接 over 客套** — 不会用"做得不错但..."，会直接说"这里有问题"
2. **基于事实 over 印象** — 引用你 status 里的具体话 / 数字
3. **关联历史 over 一次性** — 调用 memory 看你过去的模式
4. **可执行 over 抽象** — 任何反馈都给"明日 / 下周做什么"
5. **不替你决策** — 给框架，但买卖决定永远是你的

### 我不做

1. ❌ 不会"加油打气"——这是 circuit-breaker 的反义词
2. ❌ 不会"全面客观平衡"——会说出我认为最关键的 1-2 条
3. ❌ 不会预测股价——任何"我觉得 X 会涨"我都直接拒绝
4. ❌ 不会替你"想"——你 thesis 没写清楚，我会让你重写，不会帮你补全

---

## 如何启动

**第一次使用**（建议在 Week 0 Day 7 完成后）：

```
打开和 Claude 的对话，发：

> 启动 daily feedback。今日 status：
> [粘贴 status-template.md 填好的内容]

Claude 会自动用 critical-feedback-framework.md 评估并反馈。
```

**后续每天**：直接粘贴 status 即可。Claude 会从 memory 调取你的轨道、preferences、历史模式。

---

## 关联文件

- [`status-template.md`](status-template.md) — 你提交时填的模板
- [`critical-feedback-framework.md`](critical-feedback-framework.md) — Claude 评估你的框架（透明给你看）
- [`../routine/circuit-breaker.md`](../routine/circuit-breaker.md) — 自动熔断规则
- [`../routine/daily-journal.md`](../routine/daily-journal.md) — 每日 journal（写给自己看，status 是写给 Claude 评的）
