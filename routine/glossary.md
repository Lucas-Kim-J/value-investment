# 术语表 Glossary

> 模板里出现的专有名词都在这里。一句话定义 + 关联到详细解释。

---

## 估值与判断

**反向 DCF (Reverse DCF)**
不算"公司值多少"，而是用 Goal Seek 反推"当前股价隐含的未来增长率是多少"。→ [详细](../learning/valuation-cheatsheet.html#tool-1)

**历史 P/E 百分位 (P/E percentile)**
当前 P/E 在过去 10 年分布中的位置。0-25% = 历史最便宜区间。→ [详细](../learning/valuation-cheatsheet.html#tool-2)

**EV/EBIT 同行对比**
跨资本结构 / 折旧政策更公允的相对估值。同行最便宜 30% + ROIC 不输平均 = 候选。→ [详细](../learning/valuation-cheatsheet.html#tool-3)

**Owner Earnings**
Buffett 定义：净利润 + 折旧摊销 - 维持性 Capex - 营运资金变化。最接近"实际可分配现金"。

**Owner Earnings Yield vs 10Y**
把公司当债券看：OE / EV 这个"现金回报率"对比 10 年美债收益率。差额 > +4% 是合理 hurdle。→ [详细](../learning/valuation-cheatsheet.html#tool-4)

**Pabrai 3 问**
决策前必答三问：① 最坏亏多少（金额）② 能承受吗 ③ 赔率 ≥ 2:1。任一 no → 不下注。

**三角验证**
4 个估值工具中至少 3 个给"便宜"信号才进入深度研究。

---

## 投资框架

**B 轨**
~10h/周节奏：5-10 个股 + 季度深度研究 + 半自动化 signals/execution。→ [详细](../index.html#intro)

**Dhandho**
Pabrai 框架："Heads I win big, tails I don't lose much"。低风险 + 高不确定性下的非对称下注。

**Scuttlebutt**
Phil Fisher 提出的"小道消息调研法"——访谈用户/前员工/竞品销售/上下游获取一手信息。

**护城河 (Moat)**
持久的竞争优势来源：品牌 / 网络效应 / 转换成本 / 规模 / 专利 / 数据。

**能力圈 (Circle of Competence)**
只投你能看懂的；圈大小不重要，圈边界清晰最重要。

**经典文本 vs 持续信号流**
v1.1 的核心分类——前者一次性学完，后者订阅 + 定期消费。→ [详细](../index.html#canon)

---

## 财务指标

**ROIC (Return on Invested Capital)**
税后营业利润 / 投入资本。判断生意质量优于 ROE（不被杠杆扭曲）。> 15% 持续 5 年 = 优质生意。

**ROE (Return on Equity)**
净利润 / 股东权益。被杠杆放大，需配合负债率看。

**FCF Yield**
自由现金流 / 市值。和债券收益率可比。

**EV (Enterprise Value)**
市值 + 净负债。"如果你买下整家公司付的真金白银"。

**TTM / NTM**
TTM = Trailing Twelve Months（过去 12 个月）；NTM = Next Twelve Months（未来 12 个月预期）。

---

## 会计红旗工具

**Beneish M-Score**
财务造假概率打分。> -2.22 是高风险（M-Score 数值越高越像造假）。

**Altman Z-Score**
破产风险打分。< 1.81 是高风险区间。

**Piotroski F-Score**
盈利质量打分，0-9 分。低 P/B 股票配合 F-Score ≥ 7 是经典 deep value 筛选。

---

## 行为金融

**损失厌恶 (Loss Aversion)**
亏损的痛 ≈ 2.5 × 同等金额收益的喜。让人过早卖盈利 + 过晚卖亏损。

**锚定 (Anchoring)**
你的买入价不是市场关心的，但你的大脑会拿它做参考点。

**处置效应 (Disposition Effect)**
倾向"卖盈持亏"，结果组合越来越烂。

**FOMO (Fear of Missing Out)**
错过别人赚钱的痛。会推你在下一个泡沫顶接盘。

**Survivorship Bias**
只看到幸存者的成功，忽略消失的失败者。→ [详细](../index.html#failures)

**Hindsight Bias**
"我早知道" —— 事后觉得当时的事件本可预测。归因时最大的陷阱。

**承诺一致性 (Commitment Consistency)**
对自己曾经的判断 / 仓位过度坚持，即使新信息出现。

---

## 归因与复盘

**ex-ante / ex-post**
ex-ante = "事前"（决策时的预测）；ex-post = "事后"（结果出来后的解读）。**归因必须用 ex-ante 锚**，否则就是讲故事。

**运气 vs 能力 (Luck vs Skill)**
能力 = 仓位变化的原因正是你 ex-ante 预测的；运气 = 仓位变化的原因和你 thesis 无关。

**Personal Baseline**
"应然阈值"拍脑袋；正确做法是前 4 周只记录不评判，第 5 周用自己前 4 周的 75 分位作初始阈值。

**零基预算式重审**
假装今天第一次看到每只持仓，价格是当前价格——还会买吗？防锚定 + 禀赋效应。

---

## 信息源

**13F filing**
美国 SEC 要求 AUM > $100M 机构每季度披露持仓。**45 天时滞**——用来理解 thesis 不是 clone trade。

**fund letter**
基金致投资者信。质量参差，重点看"作者怎么写亏的钱"——这部分不易伪装。

**AGM (Annual General Meeting)**
年度股东大会。Berkshire AGM Q&A 是教学黄金。

**Sohn / Robin Hood Conference**
年度 fund manager 公开演讲推荐池（YouTube 免费）。

---

## 自动化

**M1 / M2 / M3**
方法论 §17 的自动化分阶段：M1 = 每日早报 TG bot；M2 = 13F 监控；M3 = 财报日历 + 季报 highlight。

**RAG (Retrieval-Augmented Generation)**
向量化文档让 LLM 做问答。**v1.1 砍掉**——小用户的 thesis 涉及 5-20 家公司，直接读 10-K 反而能建立段落记忆。

---

> 术语缺漏？编辑此文件加上去。这是 living document，每次发现新术语都补一条。
