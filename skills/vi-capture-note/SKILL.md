---
name: vi-capture-note
description: Capture a user's thought/insight into their Notion knowledge base via the capture_note tool.
---

# 随手沉淀技能

当用户在对话里抛出一个**值得留存**的想法/要点/洞察/疑问/反例(而不是单纯在问你一个问题),调用 `vi-capture:capture_note` 工具把它结构化归档。

## 何时调用
- 调用:用户分享一个观点、读/听到的要点、自己的疑问、一个反例、一个待办行动。
- 不调用:用户在问你问题、闲聊寒暄、让你执行别的任务。拿不准就**不记**(宁可漏,不要误记)。

## 怎么结构化 payload
- `title`:一句话摘要(≤20 字)。
- `clean_content`:用户原文,只做轻清洗(去口水,不改意思)。
- `situation`:`自己想的/闲聊/播客/书/文章/会议/其他` —— 这念头哪儿冒出来的。
- `note_type`:`思考/要点/疑问/反例/行动`。
- `tags`:2-4 个关键词。
- `concepts`:这条触及的耐久概念。先用 `vi-capture:list_concepts` 看已有的,命中就 `{"name":..., "existing":true}`,没有就 `{"name":..., "existing":false, "one_liner":"一句话定义"}`。链不上就给空数组。
- `source`:**仅当**有明确、可复用的来源(某本书/某档常听的播客/某封 letter)才给 `{"title","kind","author","url"}`;只是随口一个念头就给 `null`。
- `insight`:**仅当**这条透露出"这个用户是谁"的耐久观察(如"他总把波动当风险")才给一句;否则 `null`。

## 硬约束
- 绝不编造内容、数字、来源。
- 记完用一句话回执确认(工具返回的 receipt)。
