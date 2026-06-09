# server/ — 输入端口后端

> 这是「网站作为输入端口」的服务端。把网站从只读变成可输入：登录 → 记录持仓 → 服务器持久化 → （下一步）hermes 生成规范报告。

---

## 架构

```
浏览器                          nginx (:80)                    Flask API (127.0.0.1:8787)
login.html / portfolio.html ──► 静态文件                       gunicorn, systemd
        │                       location /api/  ──proxy──►     value-investment-api.service
        └── fetch /api/* ───────────────────────────────────► PostgreSQL (value_investment)
                                                               holdings / reports 表，按 username 隔离
```

- **登录**：访问码白名单（无注册）。`POST /api/login {code}` → 命中白名单则下发签名 session cookie。
- **存储**：PostgreSQL（事务保证，不会被误删文件抹掉）；每日 `pg_dump` 自动备份。
- **存储隔离**：每个访问码对应一个用户，数据按 username 隔离，互不可见。
- **公开只读站不受影响**：`dashboard.html` / `index.html` 等照常公开；只有 `/api/*` 数据需要 session。

---

## 安全模型（关键）

**真实密钥只存在服务器，永不进仓库：**

| 内容 | 位置（服务器） | 进仓库？ |
|---|---|---|
| 访问码 → 用户 映射 | `/etc/value-investment/access-codes.json` | ❌ gitignore |
| Flask session 签名密钥 | `/etc/value-investment/api.env` (`VI_SECRET_KEY`) | ❌ gitignore |
| DB 连接串（含密码） | `/etc/value-investment/api.env` (`VI_DATABASE_URL`) | ❌ gitignore |
| 用户持仓 / 报告数据 | PostgreSQL `value_investment`（holdings / reports 表）| ❌ 不在仓库 |
| 数据库备份 | `/var/backups/value-investment/*.sql.gz`（每日 pg_dump，留 30 份）| ❌ 不在仓库 |
| 占位示例 | `server/portfolio-api/access-codes.example.json` | ✅ 仅占位符 |

`access-codes.json` 形如：

```json
{ "<access-code-a>": "usera", "<access-code-b>": "userb" }
```

> ⚠️ **TLS**：当前是 HTTP + session cookie。同网段嗅探有理论风险。存真实持仓建议尽快加 TLS（上域名走 Let's Encrypt，或自签证书）。

---

## 安装 / 更新

```bash
# 1) 把 server/ 同步到服务器
rsync -avz server/ openclaw:/root/vi-server/

# 2a) PostgreSQL + 建库/角色 + 每日备份 cron（先于 api）
ssh openclaw 'bash /root/vi-server/portfolio-api/setup-db.sh'

# 2b) 安装 API（venv + flask + gunicorn + psycopg2 + systemd + nginx vhost）
ssh openclaw 'bash /root/vi-server/portfolio-api/setup-api.sh'

# 3) 写入真实访问码（只在服务器做，永不提交；下面是占位符，换成你的真实码）
ssh openclaw 'cat > /etc/value-investment/access-codes.json' <<EOF
{ "<code-for-user-a>": "usera", "<code-for-user-b>": "userb" }
EOF
ssh openclaw 'chmod 600 /etc/value-investment/access-codes.json && systemctl restart value-investment-api'
```

nginx 需要把 `/api/` 反代到 `127.0.0.1:8787`（见 `server-setup.sh` / 主仓库 nginx 配置）。

---

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/login` | body `{code}` → 设 session；401 if 无效 |
| POST | `/api/logout` | 清 session |
| GET | `/api/me` | `{user}`（未登录则 null） |
| GET | `/api/holdings` | 当前用户持仓（401 未登录） |
| PUT | `/api/holdings` | body `{holdings:[...]}` 覆盖保存 |
| GET | `/api/report` | 最近一次生成的规范报告（无则 null） |
| POST | `/api/report` | 调服务器上的 hermes 按方法论生成规范报告（~30-90s） |
| POST | `/api/report/push` | 把报告推送到飞书（仅白名单用户，目前仅 `lucas`） |
| GET | `/api/health` | 健康检查 |

holding 字段（轻量版）：`market, ticker, name, buy_date, cost, position_pct, note`。

---

## 运维

```bash
systemctl status value-investment-api          # 服务状态
journalctl -u value-investment-api -n 50       # 日志
systemctl restart value-investment-api         # 重启
sudo -u postgres psql value_investment -c '\dt'                                    # 看表
sudo -u postgres psql value_investment -c 'SELECT username,count(*) FROM holdings GROUP BY username'
ls -lh /var/backups/value-investment/          # 每日备份（03:10）
/opt/value-investment-api/backup-db.sh         # 手动备份一次
# 恢复某个备份：
gunzip -c /var/backups/value-investment/vi-YYYYMMDD-HHMMSS.sql.gz | sudo -u postgres psql value_investment
```

---

## 规范报告（已实现）

`POST /api/report` 把当前用户的持仓组织成结构化输入 + 嵌入方法论核心（`METHODOLOGY_CONTEXT`），交给服务器上的 **hermes**（`hermes -z`）按方法论生成中文 markdown 规范报告（组合总览 / 逐仓位审视 / 组合层面 / 纪律提醒 / 下一步该补什么），不给买卖建议。报告存 PostgreSQL `reports` 表（按 username upsert）。异步：`POST /api/report` 起后台任务秒回 `{status:running}`，前端每 3s 轮询 `GET /api/report` 直到 `done`（避免长请求被中间网络掐断）。`POST /api/report/push` 经 `hermes send --to feishu` 推送（飞书白名单目前仅 `lucas`）。

报告生成调用 LLM，耗时 ~30-90s：
- gunicorn `--timeout 300`（systemd unit）
- nginx `/api/` `proxy_read_timeout 300s`（`nginx-value-investment.conf`）

**下一步**：把「决策日志 / 学习笔记」也做成输入并纳入报告输入，让报告基于「持仓 + thesis + 学习」更完整。
