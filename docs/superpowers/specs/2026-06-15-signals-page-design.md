# 信号 页 · 信号流前端 (Signals Hub) 设计

> Date: 2026-06-15 · Status: approved design, pre-plan · Branch: `feat/signals-frontend`

## 第一性原理

把后端「内容信号管道」(子系统 A)产出的**信号卡**,在 app 里给一个**能浏览的家**。守一条线:这是个**信号流 hub**,不是某一档播客的页——所以页面本身**源无关**,具体来源(小宇宙/播客)只是它下面的一个**栏**。

## 信息架构 (IA)

三层,1:1 对应管道的 source-adapter 架构:

```
📡 信号 (hub,源无关)
  └─ 板块 tabs(按来源类型):🎧 播客 [v1] · 📰 消息面/金十「即将」· 🐦 推特「即将」· 📊 数据「即将」
       └─ 栏(平台/节目):小宇宙 · 非共识的20分钟   ← 小宇宙 logo 在这一层
            └─ 信号卡(每张=一集):封面缩略图 + 支柱 chip + 来源 + 主旨摘要
                 └─ 展开:非共识 / 新角度 / 警惕 / 回听 + 🔗原集链接 + 📄转录全文(按需)
```

- **hub 头**:`📡 信号` + 源无关副标题(「把各处信号源替你过滤,只留非共识」)。**无任何具体节目/平台 logo**。
- **板块 tabs**:v1 只有 `🎧 播客` 是真的;`消息面/金十`、`推特`、`数据` 是**静态「即将」占位**(不接线),用来表达 hub 愿景。
- **播客栏**:子标题带 **小宇宙 logo** + 「小宇宙 · 非共识的20分钟」+「每天 08:00 自动更新」。
- **卡片**:节目封面缩略图(60px)+ 标题 + 支柱 chip + 「(小宇宙 logo)非共识的20分钟」+ 日期;外露主旨摘要。点开展开其余字段。

## v1 范围

1. 一个新页 `/signals`(导航项 `📡 信号`),只读,登录后可见(任意已登录用户,数据是共享内容)。
2. 只实现 **播客 / 小宇宙** 栏,渲染管道已产出的信号卡(`content_items` 里 `signal_card IS NOT NULL` 的)。
3. 卡片展开 = 信号卡 6 字段全文 + 原集外链 + **按需懒加载转录全文**。
4. 板块 tabs 里其它来源 = 静态「即将」(不查数据、不接线)。
5. 管道补两个字段(下节),让前端有封面 + 节目名。

## 不在本 spec 范围

- 消息面/金十、推特、数据等其它来源的 adapter 与接线(各自单独立项,只是 IA 已留位)。
- 筛选 / 搜索 / 已读未读 / 分页 / 任何写操作 / 一键存进 Notion。
- 一个平台下多档节目的分组(目前 播客=小宇宙=单档)。

## 数据模型变更(管道补 2 个字段)

`content_items` 加两列(**additive,可空**),给前端封面 + 节目名:

| 列 | 类型 | 来源(`__NEXT_DATA__`) |
|---|---|---|
| `image_url` | TEXT | `podcast.image.middlePicUrl`(节目封面,节目级,全集相同) |
| `show_title` | TEXT | `podcast.title`(如「非共识的20分钟」) |

- **`PgStore.init_schema`**:`CREATE TABLE` 含两列;并对已部署表 `ALTER TABLE content_items ADD COLUMN IF NOT EXISTS image_url TEXT` / `... show_title TEXT`(幂等,仿 app.py 既有 `ADD COLUMN IF NOT EXISTS` 模式)。
- **`ContentItem`**(models.py):加 `image_url: str | None = None`、`show_title: str | None = None`。
- **`parse_episodes`**(xiaoyuzhou.py):从 `podcast.image`/`podcast.title` 取值,塞进每个 `ContentItem`(节目级常量,所有集相同)。
- **`MemoryStore.add` / `PgStore.add`**:持久化这两列。
- **回填**:已处理的 Ep7 行(`image_url` 为 NULL)需一次性回填——部署时跑一小段:`list_items()` → `UPDATE content_items SET image_url=%s, show_title=%s WHERE source=%s AND external_id=%s`。前端对 NULL `image_url` 用兜底占位图,不崩。

## 后端 API(`app.py` 加 2 个只读端点)

- **`GET /api/signals`** → `{ items: [ {external_id, source, show_title, image_url, title, url, published_at, card} ] }`
  - `card` = `signal_card` JSONB 原样(6 字段)。
  - SQL:`SELECT external_id, source, show_title, image_url, title, url, published_at, signal_card FROM content_items WHERE signal_card IS NOT NULL ORDER BY published_at DESC NULLS LAST LIMIT 50`。
  - **不含 transcript**(可能几 KB)。
- **`GET /api/signals/<external_id>`** → 同上单条 + `transcript`(按需)。
  - SQL 加 `transcript`,`WHERE external_id=%s AND signal_card IS NOT NULL`;无则 404。
- 登录校验(`_current_user()`,未登录 401),纯 SELECT,复用 `_db()` / `RDC`,不写。
- `published_at` 用 `.isoformat()`。

## 前端(`web/`,新页 + 路由 + 导航 + 1 个 logo 资源)

- **`web/src/pages/Signals.tsx`**:`apiGet('/api/signals')` → 渲染 hub 头 + 板块 tabs + 播客栏 + 卡片列表。
  - 卡片点击 → 展开(本地 state);展开后点「转录全文」→ `apiGet('/api/signals/<eid>')` 懒加载 `transcript`,缓存进 state。
  - 空状态:「还没有信号卡——管道每天 08:00 自动更新」。转录区标注「机器转录,可能有错字」。
- **`web/src/App.tsx`**:加 lazy 路由 `{ path: "/signals", element: <Signals /> }`。
- **`web/src/app/Nav.tsx`**:`ITEMS` 加 `["/signals", "📡 信号"]`。
- **`web/src/lib/types.ts`**:`SignalCard`(6 字段)、`Signal`(meta + card)、`SignalDetail`(+transcript)。
- **来源元信息(前端静态小注册表)**:`SOURCE_META = { xiaoyuzhou: { category: "播客", platform: "小宇宙", logo: "/logos/xiaoyuzhou.png" } }`;板块 tabs 静态数组(播客 active;消息面/推特/数据 `soon:true`)。封面 + 节目名走每条数据的 `image_url`/`show_title`。
- **小宇宙 logo 资源**:`web/public/logos/xiaoyuzhou.png`(从 `xiaoyuzhoufm.com/apple-touch-icon.png` 下载一次,随前端打包,不在运行时外链平台站)。
- 样式复用现有 design tokens(`--accent`/`--bg-soft`/`.vi-card` 等);新增少量 class(栏头、tabs、缩略图)。

## 可见性 / 边界

- 登录后只读。付费集(无 `signal_card`)不展示。`error` 集不展示(无卡)。
- `image_url` 为 NULL → 兜底占位(通用图标),不崩。
- 转录可能很长 → 懒加载,默认折叠。

## 错误处理

- API 任一查询失败 → 标准 JSON 错误 + 合适状态码;前端显示「加载失败,稍后重试」。
- 详情 404(eid 不存在/无卡)→ 前端转录区显示「该集暂无转录」。
- 前端对缺失字段(任一信号卡字段为空)显示「—」,不崩。

## 测试

- **后端 pytest**(`server/portfolio-api/tests/`):
  - `parse_episodes` 从带 `podcast.image`/`podcast.title` 的 fixture 正确取 `image_url`/`show_title`(扩 `test_content_adapter.py`)。
  - `MemoryStore` round-trip 含新字段(扩 `test_content_store.py`)。
  - `/api/signals` 列表:只返回有卡的、按时间倒序、不含 transcript、未登录 401(可 mock `_db` 或用既有测试夹具风格)。
  - `/api/signals/<eid>`:含 transcript;不存在 → 404。
- **前端 Vitest**(`web/src/pages/`,仿现有页测试):
  - mock `apiGet('/api/signals')` → 渲染卡片(标题/支柱/封面/主旨)。
  - 点击展开 → 出现 6 字段;点转录 → 触发 `apiGet('/api/signals/<eid>')` 并显示。
  - 空数组 → 空状态文案。

## 部署

1. **管道改动**(models/adapter/store):rsync `content_pipeline/` → `/opt/value-investment-api/content_pipeline/`;跑一次 `PgStore().init_schema()`(加列)+ 回填脚本(填 Ep7 的 `image_url`/`show_title`)。
2. **后端 API**(app.py 加端点):rsync `server/` + `setup-api.sh`(它 `cp *.py`)+ `systemctl restart value-investment-api`(2 个只读端点,低风险)。
3. **前端**:`web/deploy.sh`(vite build + rsync)。
4. 顺序:先 1+2(让 `/api/signals` 可用)再 3(前端上线)。

## 验收标准 (Done = …)

1. 登录后,导航点 `📡 信号` → 看到 hub 头(源无关)+ 板块 tabs(播客 active,其它「即将」)+ 播客栏(小宇宙 logo + 非共识的20分钟)。
2. 播客栏下出现至少 1 张**真实**信号卡(Ep7),带节目封面缩略图 + 资金传导 chip + 主旨摘要。
3. 点卡片展开 → 6 字段全文 + 🔗到小宇宙听原集;点「转录全文」→ 懒加载出现转录(带「机器转录」标注)。
4. 付费集 / 无卡集不出现;封面缺失时用兜底图不崩。
5. 后端两个端点登录校验、纯只读;新两列 additive、已回填 Ep7。
6. 前端样式与现有页一致(深色 + accent),新增一个 `📡 信号` 导航项。
7. 其它板块 tab 是静态「即将」,点了不报错(无接线)。
