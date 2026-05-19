"""最小认证 + 会话归属校验。

设计为「可选开关」：AUTH_ENABLED 缺省 false → 行为与改造前完全一致
（单用户本地开发不受影响）；生产 compose 置 true 即启用账号 + 归属校验，
堵住「猜中 session UUID 即可访问任意会话」的漏洞。

口令哈希直接用 bcrypt（弃 passlib，免版本探测摩擦）。会话态用 Starlette
SessionMiddleware 的签名 Cookie（SECRET_KEY 注入），不另存服务端 session。
"""
import os

import bcrypt
from fastapi import APIRouter, Form, HTTPException, Request

from . import db

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").strip().lower() in ("1", "true", "yes")


def auth_enabled() -> bool:
    return AUTH_ENABLED


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def _verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def current_user(request: Request) -> dict | None:
    """读签名 Cookie 中的 uid → 用户；未登录/无 SessionMiddleware 时返回 None。"""
    try:
        uid = request.session.get("uid")
    except (AssertionError, AttributeError):
        return None
    if not uid:
        return None
    return db.get_user(int(uid))


async def require_owner(session_id: str, request: Request) -> None:
    """会话归属校验（敏感路由调用）。

    - 未启用鉴权：放行（保持原行为）。
    - 启用：必须登录；会话已有 owner 则必须是本人；
      无 owner（匿名/历史会话）放行（向后兼容）。
    """
    if not AUTH_ENABLED:
        return
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "未登录")
    import asyncio
    rec = await asyncio.to_thread(db.get_session, session_id)
    if rec and rec["owner_user_id"] is not None and rec["owner_user_id"] != user["id"]:
        raise HTTPException(403, "无权访问该会话")


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    if len(username) < 2 or len(password) < 6:
        raise HTTPException(400, "用户名至少 2 位、口令至少 6 位")
    import asyncio
    if await asyncio.to_thread(db.get_user_by_name, username):
        raise HTTPException(409, "用户名已存在")
    uid = await asyncio.to_thread(db.create_user, username, _hash_pw(password))
    return {"id": uid, "username": username}


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    import asyncio
    u = await asyncio.to_thread(db.get_user_by_name, username.strip())
    if not u or not _verify_pw(password, u["password_hash"]):
        raise HTTPException(401, "用户名或口令错误")
    request.session["uid"] = u["id"]
    return {"id": u["id"], "username": u["username"]}


@router.post("/logout")
async def logout(request: Request):
    try:
        request.session.clear()
    except (AssertionError, AttributeError):
        pass
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    return {"auth_enabled": AUTH_ENABLED, "user": current_user(request)}
