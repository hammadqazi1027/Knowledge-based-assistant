"""
tickets.py — Ticket tracking system for queries.

Provides:
  - Ticket CRUD operations
  - Query tracking and analytics
  - Status management (open, in_progress, resolved, closed)
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "rag_pipeline.db"

VALID_STATUSES = ("open", "in_progress", "resolved", "closed")
VALID_PRIORITIES = ("low", "medium", "high", "urgent")
VALID_DEPARTMENTS = ("general", "admissions", "academic", "finance", "hr", "it", "library", "other")


def _get_conn() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_tickets_db() -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                university_id   INTEGER NOT NULL,
                query           TEXT    NOT NULL,
                response        TEXT,
                department      TEXT    NOT NULL DEFAULT 'general',
                priority        TEXT    NOT NULL DEFAULT 'medium',
                status          TEXT    NOT NULL DEFAULT 'open',
                doc_id          INTEGER,
                chunks_used     INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                created_at      TEXT    NOT NULL,
                updated_at      TEXT    NOT NULL,
                resolved_at     TEXT
            )
        """)
        # Create indexes for query optimization
        _ensure_index(conn, "idx_tickets_university", "CREATE INDEX IF NOT EXISTS idx_tickets_university ON tickets(university_id)")
        _ensure_index(conn, "idx_tickets_user", "CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id)")
        _ensure_index(conn, "idx_tickets_status", "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        _ensure_index(conn, "idx_tickets_department", "CREATE INDEX IF NOT EXISTS idx_tickets_department ON tickets(department)")
        _ensure_index(conn, "idx_tickets_created", "CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at DESC)")
        
        conn.commit()
        logger.info("Tickets table initialised.")
    finally:
        conn.close()


def _ensure_index(conn: sqlite3.Connection, name: str, sql: str) -> None:
    """Create an index if it doesn't already exist."""
    try:
        conn.execute(sql)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Index may already exist


def create_ticket(
    user_id: int,
    university_id: int,
    query: str,
    response: str = "",
    department: str = "general",
    priority: str = "medium",
    doc_id: Optional[int] = None,
    chunks_used: int = 0,
    response_time_ms: Optional[int] = None,
) -> int:
    if department not in VALID_DEPARTMENTS:
        department = "general"
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        cursor = conn.execute("""
            INSERT INTO tickets
                (user_id, university_id, query, response, department, priority,
                 status, doc_id, chunks_used, response_time_ms, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
        """, (user_id, university_id, query, response, department, priority,
              doc_id, chunks_used, response_time_ms, now, now))
        conn.commit()
        ticket_id = cursor.lastrowid
        logger.info("Created ticket id=%d for user=%d", ticket_id, user_id)
        return ticket_id
    finally:
        conn.close()


def get_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_tickets(
    university_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM tickets WHERE 1=1"
        params = []

        if university_id:
            query += " AND university_id = ?"
            params.append(university_id)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if department:
            query += " AND department = ?"
            params.append(department)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_ticket(ticket_id: int, **kwargs) -> bool:
    allowed = {"status", "department", "priority", "response", "resolved_at"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [ticket_id]

    conn = _get_conn()
    try:
        cursor = conn.execute(f"UPDATE tickets SET {set_clause} WHERE id = ?", values)
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info("Updated ticket id=%d: %s", ticket_id, list(fields.keys()))
        return updated
    finally:
        conn.close()


def resolve_ticket(ticket_id: int, response: str = "") -> bool:
    now = datetime.now(timezone.utc).isoformat()
    return update_ticket(
        ticket_id,
        status="resolved",
        response=response,
        resolved_at=now,
    )


def close_ticket(ticket_id: int) -> bool:
    return update_ticket(ticket_id, status="closed")


def delete_ticket(ticket_id: int) -> bool:
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted ticket id=%d", ticket_id)
        return deleted
    finally:
        conn.close()


def get_ticket_stats(university_id: Optional[int] = None) -> Dict[str, Any]:
    conn = _get_conn()
    try:
        base_query = "SELECT COUNT(*) as cnt, status FROM tickets"
        params = []
        if university_id:
            base_query += " WHERE university_id = ?"
            params.append(university_id)
        base_query += " GROUP BY status"

        rows = conn.execute(base_query, params).fetchall()
        stats = {s: 0 for s in VALID_STATUSES}
        for row in rows:
            stats[row["status"]] = row["cnt"]

        total_query = "SELECT COUNT(*) as total FROM tickets"
        if university_id:
            total_query += " WHERE university_id = ?"
        total_row = conn.execute(total_query, params if university_id else []).fetchone()

        dept_query = "SELECT COUNT(*) as cnt, department FROM tickets"
        if university_id:
            dept_query += " WHERE university_id = ?"
        dept_query += " GROUP BY department ORDER BY cnt DESC LIMIT 5"
        dept_rows = conn.execute(dept_query, params if university_id else []).fetchall()

        return {
            "total": total_row["total"] if total_row else 0,
            "by_status": stats,
            "by_department": [dict(r) for r in dept_rows],
        }
    finally:
        conn.close()


def get_recent_tickets(university_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    return list_tickets(university_id=university_id, limit=limit)
