"""
university.py — Multi-tenant university management.

Provides:
  - University CRUD operations
  - University-based data isolation
  - Seed default universities on first run
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "rag_pipeline.db"


def _get_conn() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_universities_db() -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS universities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                code        TEXT    NOT NULL UNIQUE,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.commit()
        logger.info("Universities table initialised.")
    finally:
        conn.close()


def seed_default_universities() -> None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM universities").fetchone()
        if row["cnt"] > 0:
            return

        now = datetime.now(timezone.utc).isoformat()
        defaults = [
            ("University of Technology", "UOT"),
            ("National University", "NU"),
            ("City University", "CU"),
        ]
        for name, code in defaults:
            conn.execute(
                "INSERT INTO universities (name, code, created_at) VALUES (?, ?, ?)",
                (name, code, now),
            )
        conn.commit()
        logger.info("Seeded %d default universities.", len(defaults))
    finally:
        conn.close()


def add_university(name: str, code: str) -> int:
    name = name.strip()
    code = code.strip().upper()
    if not name or not code:
        raise ValueError("University name and code are required.")

    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO universities (name, code, created_at) VALUES (?, ?, ?)",
            (name, code, now),
        )
        conn.commit()
        uni_id = cursor.lastrowid
        logger.info("Added university id=%d name='%s'", uni_id, name)
        return uni_id
    except sqlite3.IntegrityError as e:
        if "name" in str(e):
            raise ValueError(f"University '{name}' already exists.")
        raise ValueError(f"University code '{code}' already exists.")
    finally:
        conn.close()


def list_universities() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, code, created_at FROM universities ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_university(uni_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, name, code, created_at FROM universities WHERE id = ?", (uni_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_university(uni_id: int) -> bool:
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM universities WHERE id = ?", (uni_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted university id=%d", uni_id)
        return deleted
    finally:
        conn.close()
