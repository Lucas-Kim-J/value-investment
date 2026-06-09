# 部署文档（DEPLOY.md）

本项目是一个**价值投资学习系统**的静态网站：本地用 Markdown / HTML 写内容，
通过 `python build.py` 构建出 `dist/` 目录（镜像仓库结构的静态站点），
再 rsync 到自己的服务器，由 nginx 在 80 端口提供访问。

> ⚠️ 本仓库为公开仓库。所有服务器具体信息（IP / 端口 / 用户名）**绝不**写进任何被提交的文件。
> 本地走 SSH 别名 `openclaw`（在 `~/.ssh/config` 中配置），CI 走 GitHub Secrets，文档里一律用占位符。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                              本地开发机                                │
│                                                                        │
│   写 / 改 markdown、html                                               │
│            │                                                           │
│            ▼                                                           │
│   python build.py  ──►  dist/  （生成的静态站点，镜像仓库结构）        │
│            │                                                           │
│            ▼                                                           │
│   rsync -avz --delete  (经 SSH 别名 openclaw)                          │
└────────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                              服务器 (nginx)                            │
│                                                                        │
│   web root: /var/www/value-investment/                                │
│   nginx listen 80  ──►  对外提供静态站点                              │
└──────────────────────────────────────────────────────────────────────┘

             ▲
             │  （同样的构建 + rsync 流程，由 CI 自动执行）
┌────────────┴─────────────────────────────────────────────────────────┐
│                          GitHub Actions                                │
│                                                                        │
│   PR 合并到 main  ──►  checkout  ──►  setup-python 3.12                │
│       ──►  pip install -r requirements-build.txt                       │
│       ──►  python build.py  ──►  rsync dist/ 到服务器                  │
│   （服务器信息全部来自 GitHub Secrets）                                │
└──────────────────────────────────────────────────────────────────────┘
```

一句话：**本地写 md → `build.py` 生成 `dist/` → rsync 到服务器 nginx**；
合并 PR 到 `main` 后，GitHub Actions 会自动完成同样的事。

---

## 首次设置

### 1. 服务器初始化

把 `server-setup.sh` 在服务器上以 root 运行一次，安装并配置 nginx：

```bash
ssh openclaw 'bash -s' < server-setup.sh
```

该脚本是幂等的，会：

- 安装 nginx
- 创建 web root `/var/www/value-investment/`
- 写入 nginx vhost（`listen 80 default_server`、`root /var/www/value-investment`、
  `index dashboard.html index.html`、`server_name _`、`location / { try_files ... }`）
- 启用该站点并删除 nginx 默认站点
- `nginx -t` 校验后 enable + restart nginx
- 若 ufw 处于 active 状态，放行 80 端口

> 前提：本地 `~/.ssh/config` 里已配置好 `openclaw` 别名（指向真实 Host / Port / User），
> 这样命令里就不会出现任何敏感信息。

### 2. 配置本地 SSH 别名（`~/.ssh/config`）

本地一键部署脚本 `deploy.sh` 依赖 SSH 别名 `openclaw`。在 `~/.ssh/config` 中加入：

```sshconfig
Host openclaw
    HostName <your-server-ip>
    Port <your-ssh-port>
    User <your-ssh-user>
    IdentityFile ~/.ssh/<your-private-key>
```

> 此文件在你本地，不会被提交，因此可以放真实值。

### 3. 生成 CI 专用部署密钥

为 GitHub Actions 生成一对**专用**的部署密钥（不要复用日常 SSH 密钥）：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/value-investment-deploy -C "value-investment-ci" -N ""
```

把**公钥**加到服务器的 `authorized_keys`：

```bash
ssh-copy-id -i ~/.ssh/value-investment-deploy.pub openclaw
# 或手动把 ~/.ssh/value-investment-deploy.pub 内容追加到服务器 ~/.ssh/authorized_keys
```

**私钥**（`~/.ssh/value-investment-deploy`）稍后填入 GitHub Secret `DEPLOY_SSH_KEY`。

### 4. 设置 4 个 GitHub Secrets

在仓库里设置以下 4 个 Secret（用 `gh` CLI 示例，值用占位符，请替换为真实值）：

```bash
# 部署私钥（CI 用来登录服务器）
gh secret set DEPLOY_SSH_KEY < ~/.ssh/value-investment-deploy

# 服务器地址（IP 或域名）
gh secret set DEPLOY_HOST --body "<your-server-ip>"

# SSH 端口
gh secret set DEPLOY_PORT --body "<your-ssh-port>"

# SSH 登录用户名
gh secret set DEPLOY_USER --body "<your-ssh-user>"
```

也可以在 GitHub 网页端：**Settings → Secrets and variables → Actions → New repository secret** 逐个添加。

---

## 日常部署

有两种方式，效果一致（都是 `build.py` + rsync）：

### 方式 A：本地一键部署

```bash
./deploy.sh
```

会自动：检查依赖 → `python3 build.py` → rsync `dist/` 到 `openclaw:/var/www/value-investment/`。

### 方式 B：合并 PR 到 main（自动）

把改动合并进 `main` 分支后，GitHub Actions 会自动构建并部署。
也可以在 **Actions 页面手动触发**（workflow_dispatch）。

---

## 推荐工作流

1. **写 / 改 markdown**（或 html）内容。
2. 本地 `python build.py`，在本地预览 `dist/` 确认效果。
3. 提交并发起 **Pull Request**。
4. Review 后 **合并到 `main`**。
5. GitHub Actions **自动部署**到服务器。

> 急用时也可以本地直接 `./deploy.sh`，绕过 CI 立即上线。

---

## 故障排查

### 站点打不开 / 80 端口不通

1. **云控制台安全组**：云服务器除了系统防火墙，还需要在**云厂商控制台的安全组 / 防火墙规则**里放行 80 端口（入站 TCP 80）。这是最常见的「nginx 正常但外网访问不了」原因。
2. **服务器系统防火墙（ufw）**：
   ```bash
   ssh openclaw 'sudo ufw status'
   ssh openclaw 'sudo ufw allow 80/tcp'
   ```

### nginx 状态检查

```bash
ssh openclaw 'sudo systemctl status nginx'   # 服务是否在跑
ssh openclaw 'sudo nginx -t'                 # 配置是否合法
ssh openclaw 'sudo systemctl restart nginx'  # 重启
ssh openclaw 'sudo tail -n 50 /var/log/nginx/error.log'  # 看错误日志
```

确认 web root 下确实有文件：

```bash
ssh openclaw 'ls -la /var/www/value-investment/'
```

### GitHub Actions 部署失败

- 打开仓库 **Actions** 标签页，点开失败的 **Deploy** workflow run，查看每一步日志。
- 常见原因：
  - `DEPLOY_SSH_KEY` 私钥内容不完整或与服务器上的公钥不匹配 → 重新设置 Secret。
  - `DEPLOY_HOST` / `DEPLOY_PORT` / `DEPLOY_USER` 填错 → 核对 Secrets。
  - `ssh-keyscan` 或 rsync 卡在 host key / 端口 → 确认端口对、服务器 SSH 可达。
  - `pip install -r requirements-build.txt` 失败 → 确认该文件存在且依赖（含 `markdown`）正确。

---

## 相关文件一览

| 文件 | 作用 |
| --- | --- |
| `build.py` | 构建脚本，生成 `dist/`（由另一个流程维护，本文档不涉及其实现） |
| `requirements-build.txt` | 构建依赖（含 `markdown`） |
| `deploy.sh` | 本地一键部署（走 SSH 别名 `openclaw`） |
| `.github/workflows/deploy.yml` | CI：push 到 main / 手动触发时自动构建并部署（走 Secrets） |
| `server-setup.sh` | 幂等的服务器初始化脚本（安装并配置 nginx） |
| `DEPLOY.md` | 本文档 |
