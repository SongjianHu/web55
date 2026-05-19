"""SQLite 元数据库（durable 真相源）：users / sessions / library。

为何 SQLite：小范围低并发，零运维；用 SQLAlchemy 抽象，将来要 PG 迁移成本低。
为何 WAL：读写并发更好，崩溃恢复更稳。

同步引擎，DB 操作经 asyncio.to_thread 在路由里调用（SQLite 单次操作亚毫秒，
此规模无需 async 驱动）。未建库时 init_db() 幂等建表。
"""
import os
import time
from pathlib import Path

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR") or (BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

_engine = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


class Base(DeclarativeBase):
    pass


def _now_ms() -> int:
    return int(time.time() * 1000)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[int] = mapped_column(BigInteger, default=_now_ms)


class SessionRec(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=_now_ms)
    last_active_at: Mapped[int] = mapped_column(BigInteger, default=_now_ms, index=True)


class LibraryItem(Base):
    __tablename__ = "library"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="")  # openalex / zotero
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[int] = mapped_column(BigInteger, default=_now_ms)


def init_db() -> None:
    Base.metadata.create_all(_engine)


def session() -> Session:
    return Session(_engine, future=True)


# ── 同步 DAL（路由层用 asyncio.to_thread 包裹）──

def create_user(username: str, password_hash: str) -> int:
    with session() as s:
        u = User(username=username, password_hash=password_hash)
        s.add(u)
        s.commit()
        return u.id


def get_user_by_name(username: str) -> dict | None:
    with session() as s:
        u = s.scalar(select(User).where(User.username == username))
        if not u:
            return None
        return {"id": u.id, "username": u.username, "password_hash": u.password_hash}


def get_user(user_id: int) -> dict | None:
    with session() as s:
        u = s.get(User, user_id)
        return {"id": u.id, "username": u.username} if u else None


def upsert_session(session_id: str, owner_user_id: int | None, filename: str) -> None:
    with session() as s:
        rec = s.get(SessionRec, session_id)
        now = _now_ms()
        if rec is None:
            s.add(SessionRec(
                session_id=session_id, owner_user_id=owner_user_id,
                filename=filename, created_at=now, last_active_at=now,
            ))
        else:
            rec.last_active_at = now
            if filename:
                rec.filename = filename
        s.commit()


def touch_session(session_id: str) -> None:
    with session() as s:
        rec = s.get(SessionRec, session_id)
        if rec:
            rec.last_active_at = _now_ms()
            s.commit()


def get_session(session_id: str) -> dict | None:
    with session() as s:
        rec = s.get(SessionRec, session_id)
        if not rec:
            return None
        return {
            "session_id": rec.session_id,
            "owner_user_id": rec.owner_user_id,
            "filename": rec.filename,
            "last_active_at": rec.last_active_at,
        }


def expired_session_ids(older_than_ms: int) -> list[str]:
    with session() as s:
        rows = s.scalars(
            select(SessionRec.session_id).where(SessionRec.last_active_at < older_than_ms)
        ).all()
        return list(rows)


def delete_session(session_id: str) -> None:
    with session() as s:
        rec = s.get(SessionRec, session_id)
        if rec:
            s.delete(rec)
            s.commit()
