"""开发启动入口。

用法：
    python run.py            # 在仓库根目录运行

等价于 `uvicorn app.main:app --reload`。生产部署可直接：
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
