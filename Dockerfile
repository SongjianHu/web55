# ───────────────────────────────────────────────────────────────
# web 主应用镜像（多阶段）
#   阶段 A：node 构建 frontend/ → static/
#   阶段 B：python:3.12-slim 运行 FastAPI
# 渲染不在本镜像内（LibreOffice 在独立 render 镜像，见 render_service/Dockerfile）。
# ───────────────────────────────────────────────────────────────

# ── 阶段 A：前端构建 ──
FROM node:20-slim AS frontend
WORKDIR /build
# vite.config.js: build.outDir = '../static' → 相对 frontend/，故输出到 /build/static
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend/ ./frontend/
RUN cd frontend && npm run build
# 产物：/build/static/{index.html,assets/}

# ── 阶段 B：Python 运行时 ──
FROM python:3.12-slim AS runtime

# pymupdf / rapidocr_onnxruntime 运行所需的最小系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用层缓存（requirements 不变则不重装）
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# 应用代码 + 前端构建产物
COPY app/ ./app/
COPY knowledge/ ./knowledge/
COPY --from=frontend /build/static/ ./static/

# 运行时数据目录（compose 会以卷覆盖；此处建空目录保证非卷场景也能跑）
RUN mkdir -p /app/sessions /app/data

EXPOSE 8000

# 生产形态：不带 --reload；worker 数由 compose 用环境变量注入（默认 2）
ENV WEB_CONCURRENCY=2
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY}"]
