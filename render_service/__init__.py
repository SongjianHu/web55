"""独立渲染服务：LibreOffice headless 做域计算 + 高保真 PDF/预览。

与主应用解耦——主应用经 RENDER_SERVICE_URL 调用本服务的同步 HTTP，
或经 Redis 队列把渲染作为异步 job（Phase 3）。本服务不依赖主应用代码。
"""
