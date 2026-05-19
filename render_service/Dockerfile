# 独立渲染镜像：LibreOffice headless + 中文字体 + poppler。
# 由根 docker-compose 以 context=. 构建（dockerfile=render_service/Dockerfile），
# 故 COPY 路径相对仓库根。
FROM python:3.12-slim

# libreoffice-writer 足够处理 .docx → .pdf；poppler-utils 提供 pdftoppm 做预览图。
# fonts-noto-cjk 兜底中文；论文实际字体见下方 custom 字体说明。
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer libreoffice-core \
        poppler-utils \
        fonts-noto-cjk fonts-noto-cjk-extra \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    RENDER_MAX_CONCURRENCY=2 \
    RENDER_TIMEOUT=120

WORKDIR /app

# 字体保真：论文常用字体（宋体/黑体/楷体/Times New Roman 等）因版权不内置，
# 放入 render_service/fonts/ 后随镜像安装；清单须与 app/defaults.py 默认字体一致。
# 缺字体时 LibreOffice 会替换导致排版走样（详见 render_service/fonts/README.md）。
COPY render_service/fonts/ /usr/share/fonts/custom/
RUN fc-cache -f -v >/dev/null 2>&1 || true

COPY render_service/requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY render_service/ ./render_service/

EXPOSE 8001

# HTTP 同步渲染入口。异步队列消费者由 compose 另起一个服务跑
# `arq render_service.worker.WorkerSettings`（共用本镜像，Phase 3）。
CMD ["uvicorn", "render_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
