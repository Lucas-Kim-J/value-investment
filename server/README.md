# server/ — 输入端口后端

> 这是「网站作为输入端口」的服务端。把网站从只读变成可输入：登录 → 记录持仓 → 服务器持久化 → （下一步）hermes 生成规范报告。

---

## 架构

```
浏览器                          nginx (:80)                    Flask API (127.0.0.1:8787)
login.html / portfolio.html ──► 静态文件                       gunicorn, systemd
        │                       location /api/  ──proxy──►     value-investment-api.service
        └── fetch /api/* ───────────────────────────────────► 每用户 JSON 存储
                                                               /var/lib/value-investment/holdings-<user>.json
```

- **登录**：访问码白名单（无注册）。`POST /api/login {code}` → 命中白名单则下发签名 session cookie。
- **存储隔离**：每个访问码对应一个用户，每个用户一个 JSON 文件，互不可见。
- **公开只读站不受影响**：`dashboard.html` / `index.html` 等照常公开；只有 `/api/*` 数据需要 session。

---

## 安全模型（关键）

**真实密钥只存在服务器，永不进仓库：**

| 内容 | 位置（服务器） | 进仓库？ |
|---|---|---|
| 访问码 → 用户 映射 | `/etc/value-investment/access-codes.json` | ❌ gitignore |
| Flask session 签名密钥 | `/etc/value-investment/api.env` (`VI_SECRET_KEY`) | ❌ gitignore |
| 用户持仓数据 | `/var/lib/value-investment/holdings-<user>.json` | ❌ 不在仓库 |
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

# 2) 安装（venv + flask + gunicorn + systemd + 随机 secret）
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
| GET | `/api/health` | 健康检查 |

holding 字段（轻量版）：`market, ticker, name, buy_date, cost, position_pct, note`。

---

## 运维

```bash
systemctl status value-investment-api          # 服务状态
journalctl -u value-investment-api -n 50       # 日志
systemctl restart value-investment-api         # 重启
ls -la /var/lib/value-investment/              # 看各用户数据文件
```

---

## 下一步（报告生成）

持仓数据就位后，下一阶段：`POST /api/report` → 把该用户的持仓（+ 未来的决策日志 / 学习笔记）组织成结构化输入，交给服务器上的 **hermes**（`hermes -z` 或 `hermes send`）按方法论生成规范报告，并可推送飞书。hermes 飞书白名单目前仅 `lucas`。
