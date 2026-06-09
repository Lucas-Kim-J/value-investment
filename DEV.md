# 本地开发 Local Dev

一条命令在本地把整套产品跑起来（静态站 + 输入端口 API + PostgreSQL），镜像生产结构。

## 前置
- Docker + Docker Compose
- Python 3.11+（用来跑 `build.py` 生成静态站）+ `pip install -r requirements-build.txt`

## 启动

```bash
./dev.sh
```

它会：① `python build.py` 生成 `dist/` ② `docker compose up` 起 db + api + nginx。

打开 **http://localhost:8080/** 。登录页 `/login.html`，本地访问码：`dev` 或 `lucas-dev`（仅本地有效，见 `dev/access-codes.dev.json`）。

## 说明
- **数据**：本地用 docker volume `vi_pgdata` 里的 PostgreSQL，和生产完全隔离。
- **报告 / 分析**：本地没有 `hermes`（LLM 在服务器上），所以 `VI_REPORT_MODE=mock` 返回占位报告。要测真实生成需在服务器。
- 改了 markdown / HTML：重跑 `python build.py`（或 `./dev.sh`）即可，nginx 挂载 `dist/`。
- 改了后端 `app.py`：`docker compose up -d --build api` 重建。

## 常用
```bash
docker compose logs -f          # 看日志
docker compose down             # 停（数据保留）
docker compose down -v          # 停并清空本地 DB
docker compose exec db psql -U vi_app value_investment -c '\dt'   # 看表
```

## 与生产的关系
- 同一份 `app.py` 跑在本地容器和生产 venv。
- 生产部署见 [`DEPLOY.md`](DEPLOY.md) 与 [`server/README.md`](server/README.md)。
- 本地用来快速验证前端 + API + DB 逻辑；LLM 相关功能在服务器验证。
