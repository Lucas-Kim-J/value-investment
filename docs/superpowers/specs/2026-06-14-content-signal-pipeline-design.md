# 内容信号管道 · 子系统 A 第一实现 (Content Signal Pipeline)

> Date: 2026-06-14 · Status: approved design, pre-plan · Branch: `feat/content-signal-pipeline`

## 第一性原理

一切为**把外部内容压成可读的信号**,而不是占用你的时间去消费它。

你方法论里有一条硬纪律(`feedback/critical-feedback-framework.md`):**"听 podcast 的时间 > 读 letter 的时间 = 被娱乐占据的警告"**。所以本系统的核心设计反转是:**让系统替你"听"(转录 + 蒸馏),只把文字版的非共识信号递给你读**。播客从"分心源"被改造成"信号源"。

## 飞轮定位

你的知识沉淀飞轮 spec(`2026-06-13-knowledge-precipitation-flywheel-design.md`)把「**子系统 A:信息源聚合 / 持续获取**」明确留作单独立项。**本系统就是子系统 A 的第一个具体实现**;蒸馏产出的信号卡 schema 刻意对齐子系统 B 的 `capture_note` 契约,**预埋接回 B(Notion 沉淀)的口子**,将来飞轮可首次闭合。

```
子系统 A(本 spec)                          子系统 B(已设计)
内容源 → 抓取 → 转录 → 蒸馏(信号卡) → 飞书   ┄┄(未来 C 口子)┄→ capture_note → Notion 沉淀
```

## 已确认的决策

1. **产出 = A + B 一起**:出新集 → 飞书推**提醒**(A);同时自动转录 + 蒸馏 → 飞书推**结构化信号卡**(B)。
2. **建的是"架子"**:管道与源解耦;本期只实现**小宇宙**一个适配器作为第一条链路。
3. **通用化到"源适配器接口"这一层**(YAGNI):不为不存在的源预先实现适配器。
4. **转录引擎 = 本地 `faster-whisper`**(免费 / 私密,服务器自跑)。
5. **蒸馏 = Hermes skill `vi-podcast-distill`**(合既有 hermes-skill 架构 + "越来越懂你"记忆回路;hermes = 判断,后端 = 编排)。
6. **轮询 = 每天一次,北京时间 08:00(= UTC 00:00)**,与 M1 早报同档。
7. **C(沉淀进 Notion)本期不做**,但信号卡 schema 预留对齐口子。
8. **付费集(付费集)管道够不着**:只推提醒 + 链接,不尝试转录。

## 验收标准 (Done = …)

1. 《非共识的20分钟》出一集**免费**新集 → 当天 08:00 轮询发现 → 几秒内飞书收到 **A 提醒**(标题 + 链接);随后转录 + 蒸馏完成 → 飞书收到 **B 信号卡**(6 字段结构化)。
2. **付费集**:只收到 A 提醒并注明"付费集,需自听",**不**触发转录/蒸馏。
3. **去重**:同一集只处理一次;轮询重跑 / 进程重启不产生重复推送。
4. **不丢**:任一步失败,该集状态落 `error`,下次轮询自动重试;转录成功但蒸馏失败时,**转录全文不浪费**(已落库)。
5. **转录全文存库**,但**不每次推**(想钻原文时可取)。
6. **换源零改管道**:新增一个实现 `SourceAdapter` 的适配器即可接入新内容源,管道(转录/蒸馏/推送/存储/状态机)代码不动。
7. **适配器自愈式告警**:小宇宙页面结构变化导致解析失败时,抛明确错误 + 飞书告警"适配器需修",不拖垮整条管道。

## 组件 (每个一个清晰职责,可独立测)

### 【`SourceAdapter`】— 接口(这就是"架子")
```python
class SourceAdapter(Protocol):
    source: str                                   # 如 "xiaoyuzhou"
    def list_items(self) -> list[ContentItem]: ...     # 抓当前可见的内容项列表
    def fetch_media(self, item: ContentItem) -> Path: ...  # 下载音频到本地,返回路径
```
`ContentItem` = `{ source, external_id, title, published_at, url, is_paid, media_url? }`。
**接口下游的一切与源无关**——这是换源零改管道的保证。

### 【`XiaoyuzhouAdapter`】— 唯一实现(第一条链路)
- 抓节目页 `https://www.xiaoyuzhoufm.com/podcast/6978a31df828d4e9f2787d3d`,从页面内嵌的 `__NEXT_DATA__`(Next.js)JSON 解析单集列表。
- 进单集页解析:`external_id`(eid)、标题、发布时间、**付费标记**、**音频真实地址**(阿里云 CDN m4a,在 `__NEXT_DATA__` 的 episode 对象里)。
- `fetch_media` = 对免费集音频 URL 做 HTTP GET 落本地临时文件。
- 解析失败(结构变化)→ 抛 `AdapterParseError`,由 Orchestrator 捕获并告警。

### 【`Transcriber`】— 音频 → 文字
- `faster-whisper`(中文 large-v3;若服务器算力紧张降 medium),CPU 可跑(20min 集约 20–40min,日批足够)。
- 返回:`{ text, segments?[{start,end,text}] }`(时间戳供信号卡 `worth_relisten` 用)。

### 【`Distiller`】— 转录 → 信号卡
- 调用 Hermes skill `vi-podcast-distill`(后端编排:`hermes -p app-<user> --skills vi-podcast-distill`,喂转录 + 元数据,取回结构化 JSON)。
- skill 的 SKILL.md 固化:三支柱判据(第一性原理 / 资金传导 / 历史镜像)、"逼出非共识 + 可迁移角度"、对主播 crypto-宏观倾向与利益相关的 `caution`、no-fabrication。
- 输出严格符合**信号卡 schema**(下节)。

### 【`Deliverer`】— 推送到飞书
- 经 `hermes send --to feishu`(既有消息路径)。
- A 提醒:`new` 一发现即推。B 信号卡:蒸馏完成后推(渲染成飞书可读文本)。

### 【`Store`(PostgreSQL)】— 去重 + 状态 + 存档
- 表 `content_items`,主键 `(source, external_id)`(幂等键)。
- 字段:`title, url, published_at, is_paid, status, transcript(text), signal_card(jsonb), error_count, created_at, updated_at`。
- 转录全文 + 信号卡都落这里(满足"存着不每次推")。

### 【`Orchestrator`】— cron 入口,串起全部
轮询 → 与 PG 去重 → 对每个新项执行状态机(下节)。

## 数据流 + 状态机

```
cron(每天 08:00 北京时间)
   │
   ▼
adapter.list_items() ──→ 与 PG 比对,筛出未见过的 external_id
   │
   ├─ 新项落库 status=new → 立刻发 A 提醒 → notified
   │
   ├─ is_paid=true → skipped_paid(A 提醒注明"付费集,需自听",结束)
   │
   └─ 免费:
        downloading → transcribing → distilled → 发 B 信号卡 → delivered
                    └─(任一步异常)→ error(error_count++,下次轮询重试)
```
- **幂等**:全程以 `(source, external_id)` 为键;重跑 / 重启安全。
- **重试**:`error` 项下次轮询重入,达上限 N(默认 3)后告警停试。

## 信号卡 schema (B 的产出 · 预埋 C 口子)

```json
{
  "tldr": "一句话主旨",
  "non_consensus": "他和市场共识具体哪里不一样",
  "new_angle": "可迁移到你框架的角度",
  "pillar": "第一性原理 | 资金传导 | 历史镜像 | 无",
  "caution": "他可能错在哪 / 利益相关 / crypto-宏观倾向提醒",
  "worth_relisten": { "yes": true, "timestamps": ["12:30 关于…"] }
}
```
字段对齐子系统 B 的 `capture_note`(情境=播客 / insight / concepts),**将来接 C 几乎零改造**。

## 错误处理

- **小宇宙改版** → `AdapterParseError` → 飞书告警"适配器需修",不崩管道,其余项继续。
- **网络 / 下载失败** → 项停在 `downloading`,下次轮询重试。
- **转录失败** → `error` 重试;**蒸馏失败但转录已成** → 转录已落库,仅重试蒸馏。
- **付费集** → 干净跳过(`skipped_paid`),只发提醒。
- **幂等** → 任何重试不产生重复库行 / 重复推送(推送前检查状态)。

## 测试 (合既有 pytest + TDD Guard)

- **适配器**:保存一份真实节目页 / 单集页 HTML 作 fixture → 断言 `list_items` / 付费标记 / 音频 URL 解析正确(**无需联网**)。
- **状态机 + 去重**:纯函数 / 可 mock Store,覆盖 new→…→delivered、skipped_paid、error 重试、幂等。
- **Distiller 契约**:mock hermes 调用,断言输出严格符合信号卡 schema(必填字段 / 枚举值)。
- **Deliverer**:mock `hermes send`,断言 A / B 各自的渲染与触发时机。
- **转录质量**:不做单测,人工抽查。

## 运行时落位

- 新模块置于 `server/`(Python,复用既有 backend + PG + pytest 栈)。
- cron 入口:`python -m content_pipeline.run`(服务器 crontab,`TZ` 设亚洲/上海 或写 UTC `0 0 * * *`)。
- faster-whisper 模型文件随部署拉取(首次 ~1.5GB),本地缓存。
- 凭证(如未来需要)走既有 Fernet 加密存储那套。

## 留到实现阶段研究的细节

- ✅ 已确认(2026-06-14 实测):episodes 在 `props.pageProps.podcast.episodes[]`;字段 `eid`/`title`/`pubDate`/`duration`/`payType`(`FREE` vs `PAY_EPISODE*`)/`enclosure.url`。仅嵌入最近 ~15 集(日轮询足够)。
- 备注:episode 对象另有 `transcript`/`transcriptMediaId` 字段——若官方已提供转录,未来可作为跳过 whisper 的捷径(本期不依赖)。
- faster-whisper 在该服务器上的实际速度(CPU vs 是否有 GPU)→ 决定 large-v3 还是 medium。
- `hermes -p app-<user> --skills vi-podcast-distill` 的确切调用形态与 JSON 取回方式(对齐 hermes-skill 既有实践)。
- 飞书信号卡的排版(纯文本 vs 卡片消息)——看 `hermes send --to feishu` 支持到哪。
- cron 注册方式:服务器 crontab vs Hermes/ScheduleWakeup 既有调度设施。

## 不在本 spec 范围

- 第二个 / 第 N 个源适配器(YouTube / 公众号 / 其他播客)—— 接口已留,需要时各自实现。
- C:信号卡 → Notion `capture_note` 沉淀 —— 口子已预埋,单独接。
- 付费集解锁(需账号 / 购买)—— 明确不做。
- app 内任何浏览 UI —— 信号卡走飞书,全文走 PG。
