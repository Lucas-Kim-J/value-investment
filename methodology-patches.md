# 方法论修订队列

> Review #3 指出：没有这个文件，所有"方法论修订建议"就死在 monthly / quarterly 文档里。**这里是 patch 的物理载体**。

---

## 用法

每次 monthly attribution / quarterly rebalance 提到"方法论 v1.x 哪条要改"时：
1. 把建议复制到本文件 **Pending** 区
2. 标 id + 提出日期 + 来源文件
3. 季度末 review 时，把 Pending 项分类到 Accepted / Rejected
4. Accepted 项<strong>真的</strong>修 `index.html`，并升版本号

---

## 修订流程

```
[Pending] → [季度 review] → [Accepted] → patch index.html → 升 v1.x → [已合入]
                          ↘ [Rejected] → 写明拒绝理由
```

**强制纪律**：每季度末 quarterly-rebalance 时<strong>必须</strong>review 这个文件，不允许跳过。

---

## Pending（待评审）

### patch-001
- **提出日期**：2026-06-08
- **来源**：Review #3（系统级批判）
- **建议**：把 daily journal 的行为元数据（情绪 / App 次数 / FOMO）从 daily 移到 weekly 一次性回答。daily 只保留 3 行（学到什么 / 投入小时 / 有无决策）。
- **理由**：daily 仪式感过载，新手 Day 3 就开始觉得"在填和学习无关的表"。一周回答一次"周均情绪"比每天问更诚实。
- **影响范围**：`routine/daily-journal.md` + `routine/weekly-review.md` + `feedback/critical-feedback-framework.md`
- **状态**：pending

### patch-002
- **提出日期**：2026-06-08
- **来源**：Review #3
- **建议**：monthly-attribution 从"汇总 30 份 daily"改为"汇总 4 份 weekly"。weekly-review 末尾输出一行固定 schema 结构化数据，monthly 直接 4 行加总。
- **理由**：30 文件手动 rollup 在物理上做不到，所以"日均情绪"一行注定凭印象拍。整个归因系统的数据基础是假的。
- **影响范围**：`routine/weekly-review.md`（加 schema 输出）+ `routine/monthly-attribution.md`（改 rollup 来源）
- **状态**：pending

### patch-003
- **提出日期**：2026-06-08
- **来源**：Review #3
- **建议**：circuit-breaker.md 砍掉大部分 Tier 1/3 规则。<strong>只保留 3 条</strong>：① 连续 4 周 &lt; 6h 触发轨道评估 ② 单仓位 &gt; 25% 回撤触发 thesis 重审 ③ 单日情绪 ≥ 8 当日禁决策。
- **理由**：27 条触发规则把新手第一周就吓退。其余规则在 Phase 2 / Phase 3 再加。
- **影响范围**：`routine/circuit-breaker.md`
- **状态**：pending

### patch-004
- **提出日期**：2026-06-08
- **来源**：Review #3
- **建议**：把 `company-template.md` § 12 自我审查 12 条 → 砍到 4 条最关键的（thesis 可证伪 / 反 thesis / 退出条件 / 最坏亏损金额）。
- **理由**：12 条自我审查是仪式，4 条是 governance。
- **影响范围**：`research/company-template.md`
- **状态**：pending

### patch-005
- **提出日期**：2026-06-08
- **来源**：Review #3
- **建议**：feedback framework 维度 7 "诚实度" 是反向陷阱（learner 会学会"写得显得诚实"）。改为看<strong>行为数据</strong>诚实度（时间投入 vs 决策次数 vs 读完页数的内部一致性），不是看文字诚实度。
- **影响范围**：`feedback/critical-feedback-framework.md` 维度 7
- **理由**：Goodhart's Law — 一旦衡量"文字诚实度"，它就不再是诚实度
- **状态**：pending

### patch-006
- **提出日期**：2026-06-08
- **来源**：Review #2（学习材料）
- **建议**：`canon-reading.html` 经典文本耗时上调 230h → 285h；subtitle 改"6-8 个月"。具体调整见 TODO-v1.2.md P2.6.
- **影响范围**：`learning/canon-reading.html`
- **状态**：pending

### patch-007
- **提出日期**：2026-06-08
- **来源**：Review #2
- **建议**：`failure-cases.html` 加 2 个 A 股本土案例（康美/康得新 + 乐视网），合并 LUNA+FTX 为"加密信任结构崩塌"1 个案例。
- **影响范围**：`learning/failure-cases.html`
- **状态**：pending

### patch-008
- **提出日期**：2026-06-08
- **来源**：Review #2
- **建议**：`valuation-cheatsheet.html` 末尾加"工具失效场景表"（银行/保险 / SaaS / Biotech / 重资本周期 / REIT）。
- **影响范围**：`learning/valuation-cheatsheet.html`
- **状态**：pending

---

## Accepted（已纳入下一版 v1.x）

> 等到累积 5+ Pending 后做一次合入，升 v1.1 → v1.2。

_(empty)_

---

## Rejected（明确不合入）

_(empty)_

---

## 已合入版本

### v1.0 → v1.1（2026-06）

参考 `index.html` § 20 变更日志。源自批判性 review v1.0 的 18 条修订。

---

## 反元规则

**不允许**：发现一条 patch 就立刻修 index.html。这会让方法论变成日记，没有稳定锚。

**允许**：发现紧急 bug（如数据错误 / 死链 / 严重逻辑漏洞）立即修。

**判断标准**：影响的是"想法"→ 进队列；影响的是"事实正确性"→ 立即修。
