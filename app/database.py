# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
import sqlite3
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from app.models import Manuscript


def _get_app_dir() -> str:
    """数据目录基于可执行文件位置（非 _MEIPASS），确保数据持久化。"""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_DIR = _get_app_dir()
DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "teleprompter.db")
DOCS_DIR = os.path.join(DATA_DIR, "documents")

# 线程本地存储，每个线程复用一个连接
_local = threading.local()


def _get_persistent_connection() -> sqlite3.Connection:
    """获取当前线程的持久连接（首次调用时创建）。"""
    conn = getattr(_local, 'conn', None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.text_factory = str
        conn.execute("PRAGMA encoding = 'UTF-8'")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


@contextmanager
def get_connection():
    conn = _get_persistent_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise


def init_database():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manuscripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                cover_image TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Manuscript CRUD ───────────────────────────────────────────────


def list_manuscripts() -> list[Manuscript]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM manuscripts ORDER BY updated_at DESC"
        ).fetchall()
        return [_row_to_manuscript(r) for r in rows]


def get_manuscript(manuscript_id: int) -> Optional[Manuscript]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM manuscripts WHERE id = ?", (manuscript_id,)
        ).fetchone()
        return _row_to_manuscript(row) if row else None


def create_manuscript(title: str, content: str) -> Manuscript:
    now = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO manuscripts (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, content, now, now),
        )
        conn.commit()
        return get_manuscript(cursor.lastrowid)


def update_manuscript(manuscript_id: int, title: str, content: str) -> Optional[Manuscript]:
    now = now_iso()
    with get_connection() as conn:
        conn.execute(
            "UPDATE manuscripts SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (title, content, now, manuscript_id),
        )
        conn.commit()
        return get_manuscript(manuscript_id)


def delete_manuscript(manuscript_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM manuscripts WHERE id = ?", (manuscript_id,))
        conn.commit()
        return cursor.rowcount > 0


def search_manuscripts(query: str) -> list[Manuscript]:
    with get_connection() as conn:
        pattern = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM manuscripts WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC",
            (pattern, pattern),
        ).fetchall()
        return [_row_to_manuscript(r) for r in rows]


# ─── Settings ──────────────────────────────────────────────────────


def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row and row["value"] is not None else default


def set_setting(key: str, value: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


# ─── Helpers ───────────────────────────────────────────────────────


def _row_to_manuscript(row: sqlite3.Row) -> Manuscript:
    return Manuscript(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        cover_image=row["cover_image"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
