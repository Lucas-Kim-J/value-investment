# 知识沉淀飞轮 · 子系统 B 设计 (Knowledge Precipitation Flywheel)

> Date: 2026-06-13 · Status: approved design, pre-plan · Branch: `knowledge-flywheel`

## 第一性原理

一切为知识的**高效学习**。内容的消费在别处(播客 / 书 / letter / 通勤),这套系统**只做入口和沉淀,不做消费面、不做笔记 UI**——守住"不臃肿"。

## 飞轮全景与范围

```
优质信息源 → 你在别处消费 → 沉淀(笔记/洞察)
     ↑                              ↓
更准的源/AI辅助 ← hermes 越来越懂你 ← 知识进体系 + 可索引
```

这是两个相对独立的闭环:**信息源 A** 与 **沉淀 B**。本 spec **只覆盖 B**(飞轮的轴);A 单独立项,B 跑通后再做。B 设计透,等于把"知识存哪 / 怎么索引 / 怎么喂 AI"这个核心架构辩透。

## 已确认的决策

1. 先做 **B(沉淀闭环)**。
2. **Notion 当知识的家**(owner 是 Notion 重度用户),系统与 hermes 接进去,不另起炉灶。
3. **hermes 实时自动归档**:捕获当场判断归类/打标/双链,流水即成体系。
4. **专用极简 Notion 结构**(新建少量库,而非适配现有 bespoke 结构)。
5. 集成拓扑 **B(后端编排)**,并按 hermes 原生能力精化为 **hermes 自驱 + MCP 工具**:hermes 当大脑(判断),后端当手(确定性 Notion 写入);Notion 凭证留后端,hermes 不持有。

## 验收标准 (Done = …)

1. 你在**飞书**发一条想法 → hermes 判断"该记" → 几秒内 Notion 对应库出现一条 **Note**,带**正确的概念双链 + 标签 + 情境**;**只是提问**时不产生 Note。
2. **去重**:再记同一概念/源,复用已有页,不产生重复。
3. **不丢**:Notion 不可用时捕获落 PG `captures(status=pending)`,恢复后自动补写。
4. **读回路**:hermes 后续对话能体现"近期沉淀"(机制 A);跨会话记得定性的"你是谁"(机制 B)。
5. **连接**:命中已有 glossary/canon 时回填 `术语slug`/`canon_slug`(术语卡可选深跳到你的笔记)。
6. **不臃肿**:app **不新增**笔记浏览 UI(至多一个可选深链)。
7. **纪律**:结构化事实(持仓/已读数)不进任何记忆,仍由 PG 每次注入。

## 组件一:Notion 数据模型(3 库 + 双链 = 索引)

三类实体的双链关系图**本身就是"索引/体系"**。

### 【笔记 Notes】— 原子捕获(主入口)
| 属性 | 类型 | 必填 | 谁填 |
|---|---|---|---|
| 标题 | title | 是 | hermes 一句话摘要 |
| 内容 | text | 是 | 原文 + hermes 轻清洗 |
| 情境 | select | **是** | hermes:`自己想的/闲聊/播客/书/文章/会议/其他` |
| 概念 | relation→概念 | 否 | hermes 有合适的才链 |
| 来源 | relation→信息源 | 否 | hermes 仅在**可复用源**时才链 |
| 类型 | select | 是 | `思考/要点/疑问/反例/行动` |
| 标签 | multi-select | 是 | hermes |
| 时间 | date | 自动 | — |

### 【概念 Concepts】— 耐久知识节点(索引轴心)
名称 · 一句话定义(hermes) · 反向关联笔记 · `术语slug`(选填,链 app 术语库)

### 【信息源 Sources】— 溯源轴
标题 · 类型(书/播客/letter/文章) · 作者 · URL · 反向关联笔记 · `canon_slug`(选填,链 app 一手内容库)

### 核心原则
- **捕获零约束**:发什么都行(想法/闲聊/通勤听到的)。
- **结构 hermes 尽力而为**:能链概念/源就链,链不上靠**情境 + 标签**兜底,**绝不硬造**——避免 Sources 库被一次性东西塞爆。
- **检索三轴**:打开任一概念→相关笔记;打开任一源→从它学到的一切;标签=第三轴。
- **YAGNI**:只 3 库、每库最少属性,不上状态机/复杂工作流/多视图。

## 组件二:捕获 → 归档 数据流(hermes 自驱 + MCP)

```
你在飞书/web 发消息 → hermes(本就在收)
        │
        ▼
hermes 按 SOUL 指令判断:值得沉淀吗?
   ├─ 只是提问 → 正常回答,不记
   └─ 想法/要点/洞察 → 调 capture_note 工具(MCP)
                          │  结构化 JSON
                          ▼
              后端写入流:①Notion 写页+双链 ②PG captures 落库+去重 ③回填 slug 钩子
                          │
                          ▼
              回执 → hermes 在飞书/web 回「✅ 已记:〈标题〉· 概念《X》· #tag」
```

### `capture_note` MCP 工具契约
**入参**(hermes 产出的结构化 JSON):
```json
{
  "title": "一句话摘要",
  "clean_content": "轻清洗的原文",
  "type": "思考|要点|疑问|反例|行动",
  "situation": "自己想的|闲聊|播客|书|文章|会议|其他",
  "tags": ["机会成本"],
  "concepts": [
    {"name": "安全边际", "existing": true},
    {"name": "新概念X", "existing": false, "one_liner": "..."}
  ],
  "source": null,
  "insight": "他总把波动当风险——可强化这点"
}
```
**出参**:`{ ok, notion_page_id, concept_page_ids[], source_page_id?, receipt }`(receipt = 给用户的一句话回执)。

辅助工具(选):`list_concepts()` / `list_sources()` —— 让 hermes 链得准、少重复。

### 后端写入流职责(确定性,非 LLM)
- **概念/源去重**:按名称(模糊)在 PG 轻索引里查;existing→链已有页;new→建页(并维护索引)。
- **写 Note 页**:全属性 + 双链。
- **slug 回填**:概念命中 app glossary → 写 `术语slug`;源命中 canon → 写 `canon_slug`。
- **PG `captures` 落库**:作为持久缓冲(见错误处理)。
- **凭证**:Notion token 走 **Fernet 加密存储**(复用交易所密钥那套)。

### `vi-capture-note` skill
SKILL.md 指引 hermes **怎么按我们的 Notion schema 结构化**(标题/类型/情境/概念/标签/源/insight 的判据)+ 何时算"可复用源"+ no-fabrication。

## 组件三:读回路 —— hermes 怎么"越来越懂你"(飞轮闭合)

两层,互补:

### 机制 A — 近期上下文注入(自建,便宜)
后端在 hermes 每次调用时,从 PG 注入**近期沉淀摘要**(最近在记哪些概念 / 未决疑问 / 近期要点)。跟现在注入"学习画像"同一个口子顺手扩。让 hermes **当下**就贴你。

### 机制 B — hermes 原生记忆(配置,非自建)
hermes 的 agent loop **原生**积累"你是谁":
- 内置 `MEMORY.md` / `USER.md`(profile 级文件,永远开启,无状态 `-z` 也持久)。
- 开启 app-* profile 的 `memory` toolset + SOUL 指引("处理捕获/对话时,蒸馏并更新对该用户的理解")。
- **可选**:`hermes memory setup` 接 **mem0**(向量索引、可查询的长期记忆),若内置 MEMORY.md 的有界扁平文件不够用。
- 捕获/对话时 hermes **自动**更新记忆,我们**不写 insight 管道**。

### 纪律(硬约束,来自架构辩论)
**结构化事实(持仓 / 已读数 / 已掌握术语)永远留 PG、每次注入,绝不进记忆**——否则会复制 + 漂移(记"lucas 持有 NVDA"是负债)。记忆**只放定性**"你是谁"。

### 飞轮闭合
```
捕获 → PG/Notion ─┬─ 近期上下文(A) → hermes 当下更贴你
                  └─ 原生记忆(B)   → hermes 长期更懂你
                          ↓
   更懂你的 hermes → 归档更准 + 审视更犀利 +(以后)信息源推荐更准 = 接回闭环 A
```

## 与 app 已有层的连接
- app 已有**策展层**:glossary 术语库 + canon 一手内容库。
- `术语slug` / `canon_slug` 钩子把**策展层(馆长精选)** ↔ **个人层(随手沉淀)** 打通。
- hermes 看一个概念时,同时看到"方法论标准定义" + "lucas 个人记过/卡过什么" = 真正的个性化。
- **最小 app 触点**(守住不臃肿):app 里**不建**笔记浏览界面。顶多术语卡/canon 页加一个轻链「你的笔记(N)→」深跳 Notion。可选。

## 结合 vs 自建

**用 hermes 原生(不造轮子):**
- 机制 B「持续更懂你」= 开 `memory` toolset + SOUL +(可选)mem0。
- 调用 = hermes 调 MCP 工具(它本是 agent),非"后端调 run_skill 拿 JSON"。
- MCP / 记忆 / SOUL / sessions 全是 hermes v0.16 一等公民(已实测)。

**自己建(app 专属胶水):**
1. `capture_note` **MCP server** = Notion 写入流(schema + 去重 + slug 回填 + Fernet + PG 兜底)← 主工作量。
2. `vi-capture-note` **skill**。
3. **PG `captures` 表 + 机制 A 注入**。
4. 配置:**SOUL 增补 + 开 memory toolset + Notion token + `hermes mcp add`**。

## 错误处理
- **Notion 挂/限流** → 捕获已安全落 PG `captures`(status=`pending`),后台重试补写。**捕获永不丢**——这是选 B 的核心价值。
- **幂等**:每捕获一个 id,重试不产生重复 Notion 页。
- **hermes 误判分类** → 你直接在 Notion 改(那是你的家);或一句"纠正"命令。
- **no-fabrication** → 在 `vi-capture-note` / SOUL 一处权威声明。

## 测试
本仓刚接入 Vitest + pytest + TDD Guard,B 的确定性部分天然好测:
- **后端写入流**(pytest):概念/源去重逻辑、slug 回填映射、PG 缓冲状态机、capture JSON → Notion 属性映射 —— 纯函数或可 mock Notion 客户端,无需真 Notion。
- **MCP 契约**:入参校验、出参形状。
- LLM 判断(hermes 分类质量)不做单测,靠 mock 兜底 + 人工抽查。

## 留到实现阶段研究的细节(owner 已确认:细粒度逻辑实现时调研)
- MCP server 的形态:in-process(Flask 内)vs 独立进程;`hermes mcp add --command` vs `--url`。
- 飞书**入站**的确切接法(hermes 拥有飞书 bot;MCP 模型下应该 hermes 直接调工具即可,无需特殊路由——待实测确认)。
- 内置 `MEMORY.md` vs 接 mem0 的取舍(先内置,不够再 mem0)。
- Notion API 限流 / 批量建页 / relation 写入的实际行为。
- Notion 专用库的一次性建库脚本(or 手建 + 记 database_id)。

## 不在本 spec 范围
- 子系统 A(信息源聚合 / 持续获取 / 入口)—— 单独立项。
- app 内笔记浏览 UI —— 交给 Notion。
- hermes 多轮 session 化(目前无状态 `-z` 够用;真要连续性用 `--resume`)。
