# TODO · v1.2 修订清单

> 整合 3 份批判性 review 的发现（review #1 routine 模板 / review #2 学习材料 / review #3 系统级 — 后者完成后追加）。**这不是必做清单，是优先级 backlog**。完成 Phase 1（Day 1-90）真实使用后，再决定哪些值得 patch。

---

## P0 · 数据安全（已完成 ✓）

- ✓ `progress-tracker.html` 加导出/导入 JSON
- ✓ Footer 加备份警告

---

## P1 · 高频使用必修

### 1. Daily journal 拆分（已完成 ✓）
- ✓ 工作日 3 min 精简版
- ✓ 周末完整版
- ✓ 决策日附加版（指向 decision log）
- ✓ Pabrai 三问移出 daily

### 2. 新建支持模板（已完成 ✓）
- ✓ `routine/glossary.md` — 术语表
- ✓ `routine/watchlist.md` — Watchlist 跟踪
- ✓ `routine/onboarding-week-0.md` — Day 0 setup
- ✓ `routine/circuit-breaker.md` — 自动熔断机制

### 3. 周复盘加"低能量周"开关 ⏳
- Status: 待实施
- 改 `routine/weekly-review.md`，开头加：
  ```
  本周时间投入 < 5h？ ☐ 是 → 只填以下 3 题：
  1. 为什么没投入？
  2. 下周能修复吗？
  3. 一句话本周关键 takeaway
  ```
- "下周不做的事"从底部提到顶部

---

## P2 · 估值材料修订

### 4. `valuation-cheatsheet.html` 实操化 ⏳
- 反向 DCF 加 5 步 Excel/Sheets 步骤截图（或附公开模板 URL）
- "维持性 Capex" 加红色警告（±30% 误差是常态）
- 加 Bruce Greenwald 方法（剥离增长性 Capex = 营收增量 × 资本密度）
- ② P/E 百分位加"A 股 / 港股使用注意"小节：政策窗口（集采/反垄断/房地产）必须叠加标注
- ③ EV/EBIT 加"如何选 peers" 3 段：业务重叠 > 地理 > 规模量级，给 Costco peers worked example
- ④ Owner Earnings 标注：用 EV 是为跨资本结构可比，与 Buffett 1986 原义（用 Market Cap）有意偏离
- "4 选 3" 软化为"至少 2 个独立角度（cross-sectional + time-series）一致便宜，并解释剩下工具为何不便宜"
- 末尾加"工具失效场景表"：银行/保险（P/B + ROE + Texas Ratio）/ SaaS（Rule of 40 + LTV/CAC）/ Biotech（risk-adjusted NPV）/ 重资本周期（mid-cycle EPS）/ REIT（NAV + AFFO yield）

### 5. `failure-cases.html` 事实精确化 + A 股本地化 ⏳

修正：
- Bill Miller：mutual fund -55% vs 对冲账户接近归零（区分清楚）
- Einhorn：Athenahealth 全称 + AUM 数字加日期
- FTX：加 Sequoia "SBF 边打 LoL 边路演" DD 细节

合并 + 新增：
- 合并 LUNA + FTX → "加密信任结构崩塌" 1 个案例
- **新增案例 5：康美 / 康得新财务造假** — 验证"复杂会计 + 现金/利润背离" red flag
- **新增案例 6：乐视网（贾跃亭"生态化反"）** — A 股版叙事泡沫

每个案例加"示范作答提纲（200 字）"。

### 6. `canon-reading.html` 渠道 + 耗时校准 ⏳

具体 URL 替换"网上有 PDF"：
- Buffett Partnership Letters → `csinvesting.org/wp-content/uploads/2014/12/buffett-partnership-letters-1959-1969.pdf`
- Nomad Letters → `igyfoundation.org.uk` 官方公开页
- 段永平 → 雪球用户主页直链 + 推荐"段永平投资问答录"第三方整理本

Klarman 处理：
- 删《Margin of Safety》PDF 推荐（DMCA 风险）
- 替换为 Klarman MIT / Columbia 演讲 transcript + Baupost 摘选 letters

耗时校准：
- Oaktree 30 篇 memos 40h → 50h
- Berkshire 精读 10 封 25h → 40h
- Poor Charlie's Almanack 30h → 45h
- Damodaran 工具书 20h → 30h
- **总耗时 230h → 285h；标题改"6-8 个月"**

每个 tier 前加"产出范例（点击展开）"——示范一份合格 500 字读书笔记。

---

## P3 · 学习材料扩充

### 7. 补充缺失的经典文本 ⏳

加入 `canon-reading.html`：
- **Damodaran NYU Stern 公开课视频**（Valuation / Corporate Finance，免费）→ Tier 3 workhorse
- **Berkshire AGM transcripts 1994-2024**（CNBC Buffett Archive）→ Tier 1
- **Akre Capital "Three-Legged Stool"** + Akre Focus Fund letters → Tier 2
- **Hagstrom《巴菲特之道》** → Tier 0 导读
- **Pat Dorsey《护城河》**（《The Five Rules for Successful Stock Investing》+《The Little Book That Builds Wealth》）→ Tier 1
- **Joel Greenblatt《You Can Be a Stock Market Genius》** → Tier 2（special situations）
- **唐朝《价值投资实战手册》（一二三册）** → Tier 1 中文本土
- **张磊《价值》** → Tier 2 中文本土
- **Michael Mauboussin** 免费 paper 系列（Measuring the Moat / Capital Allocation）→ Tier 1 补充
- **Bruce Greenwald《Value Investing: From Graham to Buffett and Beyond》** → Tier 2

---

## P4 · Routine 系统性改进

### 8. 月度归因加 ex-ante 预测追踪 ⏳
- `monthly-attribution.md` 在归因表前加"本月开盘前的预测核对"
- 强制每次 thesis 落"预测"（X 在 Y 时间发生），月度只评测命中率
- 防 hindsight bias 讲故事

### 9. 季度重审加 worked example + 拆 8h ⏳
- "零基预算式重审"加 200 字 worked example（如 Costco）
- 8h 明确拆为 第 1 个周末 4h + 第 2 个周末 4h
- 每只持仓重审时长建议 30-40 min

### 10. 行为阈值改 personal baseline ⏳
- `weekly-review.md` 和 `monthly-attribution.md` 的"目标"列前 4 周写"—（基线收集中）"
- 第 5 周起脚本/手工算自己 75 分位
- 月度模板加"本月阈值回校"

### 11. 加 routine 间数据 rollup ⏳
- daily → weekly → monthly → quarterly 重复字段（情绪 / App 次数 / FOMO）
- 当前需要手动汇总 30 份 daily 算月均 — 极易放弃
- 选项 A：提供 Python 脚本（最小工具）
- 选项 B：放弃日级颗粒度，只保留周级以上
- 选项 C：用 Google Sheets / Notion DB

---

## P5 · 系统级（Review #3 已返回 ✓ 关键发现整合）

### Review #3 核心判断

> **整套系统当前是 *"看起来很完整的 23 份文档"*，但学习者被放在 router 位置——必须自己决定今天打开哪个文件、自己汇总跨文件数据、自己 patch 方法论。6 个月后还在用的概率 &lt; 10%。问题不是不努力，是系统的认知负担 + rollup 摩擦把人磨没了。**

### 已部分修复（本次 session 内完成）

- ✓ `methodology-patches.md` — 方法论修订的物理队列（解决"修订建议死在 markdown 里"）
- ✓ `routine/track-a-routine.md` — A 轨完整 routine（解决"降级路径有摩擦"）
- ✓ `dashboard.html` — 已创建（解决"多个文件 link 它但不存在"）

### 待 v1.2 修订（按 ROI 排序）

**patch-001（高）**：daily journal 行为元数据移到 weekly。daily 只留 3 行。
- 文件：`routine/daily-journal.md` + `routine/weekly-review.md`

**patch-002（高）**：monthly-attribution rollup 来源从 daily → weekly。weekly 末尾输出固定 schema 1 行。
- 文件：`routine/weekly-review.md` + `routine/monthly-attribution.md`

**patch-003（高）**：circuit-breaker 砍到 3 条核心。
- 保留：4 周 &lt; 6h → 轨道评估 / 单仓位 25% 回撤 / 单日情绪 ≥ 8 禁决策
- 砍掉：其余 24 条移到 v2.0

**patch-004（中）**：company-template § 12 自我审查 12 条 → 4 条。

**patch-005（中）**：feedback framework 维度 7 "诚实度" 改成看<strong>行为数据一致性</strong>，不看文字诚实度。

### v2.0 应该重新设计的（不在 v1.2 范围）

**信息架构：从"23 个文件" → "1 个状态机 + N 个 view"**

当前架构是"文件中心"——学习者必须自己当 router。v2.0 应该是"状态中心"：
- 一个 single source of truth（JSON / SQLite / Notion DB）
- 所有 markdown / html 是状态的 view
- 输入一次（CLI 答 5 题），所有 view 自动 update
- Rollup 不再"手抄汇总"，而是 `SELECT WHERE week=X`

预计 200 行 Python + JSON。**这是 v2.0 的核心交付**，不是 v1.2 的 patch。

### Review #3 完整保留/砍掉/重写清单

详见 `journals/reviews/review-3-system-level.md`（如归档）。简版：
- **保留**：index.html v1.1 / canon-reading / failure-cases / valuation-cheatsheet / company-template / decision-log / glossary / watchlist / automation
- **砍掉**：circuit-breaker 大部分规则 / daily journal 完整版 / company-template § 12 / onboarding Day 6 过载
- **重写**：daily-journal 改 3 行 / weekly-review 加 schema 输出 / monthly 改 4 weekly rollup / feedback 诚实度维度

### 关键警示（设计哲学层面）

> "新手 Day 30 面前有 3 条路：① 诚实降级到 A 轨 ② 假装继续 B 轨 ③ 退出整个系统。**当前系统让'诚实继续'成本最高，'自我欺骗'成本最低**——这是反向激励。"

→ 这是 v1.1 最大的失败模式。v1.2 patch-001 / patch-002 / patch-003 + 已建 track-a-routine.md 部分缓解，但根本解需要 v2.0 重构。

---

## 工作流：什么时候 patch 哪条

| 时机 | 建议 patch |
|---|---|
| Week 0 完成（Day 7） | P0 ✓（已完成）+ P5 入门级（系统级 review 出来后） |
| Phase 1 第 30 天 | P1.3（低能量周开关）— 实际体验后修订 |
| Phase 1 第 60 天 | P2.4 / P2.5（估值 cheatsheet + 失败案例 fixes）— 真正用上时修 |
| Phase 1 第 90 天（完成第一家公司）| P3（学习材料扩充）+ P4.8-4.11 |
| Phase 2 开始 | P2.6（经典文本渠道）— 不需要早做 |

**v1.2 不应该一次性出**。让 v1.1 在真实使用中暴露问题，按 ROI 排序 patch。

---

## 已知不修的（v1.1 设计选择）

- 加密章节不会扩充——v1.1 已经明确"非对称配置"定位，扩充等于违反这条
- 不会做"自动 thesis 生成 agent"——学习者必须手写
- 不会做"自动决策建议"——任何"应该买入"类输出都被设计层禁止
- 不会做"实盘下单 API 对接"——B 轨保留人工执行
- 不会做"完整 backtest 框架"——Qlib 等可选工具足够，不重复造轮子

---

## 修订流程

每次 patch v1.x → v1.(x+1)：
1. 在 `index.html` § 20 变更日志加一条
2. 把对应 patch 描述加到该文件顶部 comment
3. 写 `journals/methodology-revisions/v1.x-to-v1.(x+1).md`（短，记录 why）
4. 通知 Claude memory 更新（如有 design decision 变化）

---

> 这份 TODO 本身也是 living document。每次 review 都加新条目，每次 patch 都标 ✓。
> 永远不要追求"清空 TODO"——v1 的目标是"用 6 个月没崩"，不是"v1.99 完美"。
