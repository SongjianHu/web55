# 部署与本地开发（多服务）

改造后为多服务：`web`（主应用）+ `render`（LibreOffice 渲染）+ `redis`
（队列/进度/会话消息）+ `caddy`（HTTPS 反代）+ 两个 arq worker。
所有新依赖**均可选**：未配置时自动降级，单机原生开发零摩擦。

## 一、本地 Windows 开发（推荐：原生热重载 + 容器化渲染）

```powershell
# 1) 仅用容器跑 redis + render，端口发布到 localhost
docker compose -f docker-compose.dev.yml up -d --build

# 2) 配好 .env（至少 ANTHROPIC_API_KEY）。REDIS_URL/RENDER_SERVICE_URL 已在 .env.example 默认指向 localhost
copy .env.example .env   # 然后填 ANTHROPIC_API_KEY

# 3) 原生跑主应用（改 app/ 代码即时热重载）
python run.py

# 4)（可选）批量异步：另开终端跑 web worker
.\.venv\Scripts\arq app.worker.WorkerSettings
```

不想用 Docker？**直接 `python run.py` 即可**：无 Redis→批量走同步、会话消息不持久化；
无 render→“高保真PDF”按钮返回友好提示。其余功能与改造前完全一致。

## 二、Ubuntu 生产部署

```bash
cp .env.example .env
#  必改：ANTHROPIC_API_KEY、SECRET_KEY（随机串）、可选 SITE_ADDRESS=你的域名
#  字体保真：把论文真实字体放进 render_service/fonts/（见该目录 README.md）

docker compose up -d --build         # caddy→web→{redis,render}+两个 worker
curl -k https://localhost/health     # {"status":"ok","redis":"ok","render":"configured",...}
```

- 生产默认 `AUTH_ENABLED=true`：首个账号注册
  `curl -k -X POST https://你的域名/auth/register -F username=… -F password=…`
- 数据卷（备份这三处即可）：`./sessions`、`./data`(SQLite)、redis-data 卷。
- 会话超 `SESSION_TTL_DAYS`(默认14) 天自动清理（目录+DB+Redis）。

## 三、关键环境变量（见 .env.example 注释）

| 变量 | 作用 | 缺省 |
|---|---|---|
| `ANTHROPIC_API_KEY` | LLM（必填） | — |
| `REDIS_URL` | 队列/进度/会话消息 | 空=降级 |
| `RENDER_SERVICE_URL` | 渲染服务地址 | 空=降级 |
| `AUTH_ENABLED` | 账号+会话归属校验 | false（生产 compose 置 true） |
| `SECRET_KEY` | 签名 Cookie 密钥 | 生产必改 |
| `SESSION_TTL_DAYS` | 会话保留天数 | 14 |
| `SITE_ADDRESS` | Caddy 域名（自动 HTTPS） | localhost（自签） |

## 四、复现构建（可选强化）

首次镜像构建成功后，在 web 容器内固化精确版本：

```bash
docker compose exec web pip freeze > requirements.lock
# CI/生产改用 pip install -r requirements.lock
```
