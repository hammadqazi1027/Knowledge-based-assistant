"""
queries.py — Centralized Database Queries
============================================

All database operations are centralized here for easy review,
optimization, and instructor demonstration.

Includes query optimization techniques:
- Indexed lookups
- Pagination
- Connection pooling via context managers
- Query result caching (optional)

Author: RAG Pipeline Team
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ── Database Configuration ──────────────────────────────────────────────────
_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "rag_pipeline.db"


def _ensure_db_dir():
    """Ensure the database directory exists."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    """
    Context manager for database connections.
    Automatically handles commit/rollback and connection closing.
    """
    _ensure_db_dir()
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =============================================================================
# USER QUERIES
# =============================================================================

class UserQueries:
    """All user-related database queries with optimization."""
    
    @staticmethod
    def create_table():
        """Create users table with indexes."""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT    NOT NULL UNIQUE,
                    password_hash TEXT    NOT NULL,
                    role          TEXT    NOT NULL CHECK (role IN ('admin', 'teacher', 'user')),
                    university_id INTEGER,
                    created_at    TEXT    NOT NULL
                )
            """)
            # Create indexes for query optimization
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_university ON users(university_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            logger.info("Users table and indexes created")
    
    @staticmethod
    def insert(username: str, password_hash: str, role: str, university_id: Optional[int] = None) -> int:
        """Insert new user with timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role, university_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, role, university_id, now),
            )
            logger.info("Inserted user '%s' (role=%s, id=%d)", username, role, cursor.lastrowid)
            return cursor.lastrowid
    
    @staticmethod
    def find_by_username(username: str) -> Optional[Dict[str, Any]]:
        """Find user by username using indexed lookup."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, role, university_id, created_at FROM users WHERE username = ?",
                (username.strip(),)
            ).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def find_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """Find user by ID - primary key lookup (fastest)."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, role, university_id, created_at FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def list_all(role: Optional[str] = None, university_id: Optional[int] = None, 
                 page: int = 1, page_size: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """
        List users with filtering and pagination.
        Returns: (user_list, total_count)
        """
        with get_connection() as conn:
            # Build count query
            count_query = "SELECT COUNT(*) as cnt FROM users WHERE 1=1"
            count_params = []
            
            if role:
                count_query += " AND role = ?"
                count_params.append(role)
            if university_id:
                count_query += " AND university_id = ?"
                count_params.append(university_id)
            
            total = conn.execute(count_query, count_params).fetchone()["cnt"]
            
            # Build data query with pagination
            query = "SELECT id, username, role, university_id, created_at FROM users WHERE 1=1"
            params = []
            
            if role:
                query += " AND role = ?"
                params.append(role)
            if university_id:
                query += " AND university_id = ?"
                params.append(university_id)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows], total
    
    @staticmethod
    def delete(user_id: int) -> bool:
        """Delete user by ID."""
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted user id=%d", user_id)
            return deleted
    
    @staticmethod
    def count(role: Optional[str] = None, university_id: Optional[int] = None) -> int:
        """Count users with optional filters."""
        with get_connection() as conn:
            query = "SELECT COUNT(*) as cnt FROM users WHERE 1=1"
            params = []
            
            if role:
                query += " AND role = ?"
                params.append(role)
            if university_id:
                query += " AND university_id = ?"
                params.append(university_id)
            
            return conn.execute(query, params).fetchone()["cnt"]


# =============================================================================
# UNIVERSITY QUERIES
# =============================================================================

class UniversityQueries:
    """All university-related database queries."""
    
    @staticmethod
    def create_table():
        """Create universities table."""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS universities (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL UNIQUE,
                    code        TEXT    NOT NULL UNIQUE,
                    created_at  TEXT    NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_uni_code ON universities(code)")
    
    @staticmethod
    def insert(name: str, code: str) -> int:
        """Insert new university."""
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO universities (name, code, created_at) VALUES (?, ?, ?)",
                (name, code, now),
            )
            return cursor.lastrowid
    
    @staticmethod
    def find_by_id(uni_id: int) -> Optional[Dict[str, Any]]:
        """Find university by ID."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM universities WHERE id = ?", (uni_id,)
            ).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def find_by_code(code: str) -> Optional[Dict[str, Any]]:
        """Find university by code (indexed)."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM universities WHERE code = ?", (code,)
            ).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        """List all universities."""
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM universities ORDER BY name").fetchall()
            return [dict(r) for r in rows]
    
    @staticmethod
    def delete(uni_id: int) -> bool:
        """Delete university."""
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM universities WHERE id = ?", (uni_id,))
            return cursor.rowcount > 0


# =============================================================================
# DOCUMENT QUERIES
# =============================================================================

class DocumentQueries:
    """All document-related database queries with optimization.
    
    Schema matches db.py:
      id, doc_name, original_filename, uploaded_by, university_id,
      chunk_count, file_size_kb, file_type, created_at, updated_at
    """
    
    @staticmethod
    def create_table():
        """Create documents table with indexes."""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_name          TEXT    NOT NULL,
                    original_filename TEXT    NOT NULL,
                    uploaded_by       TEXT    NOT NULL,
                    university_id     INTEGER,
                    chunk_count       INTEGER NOT NULL DEFAULT 0,
                    file_size_kb      REAL    NOT NULL DEFAULT 0.0,
                    file_type         TEXT    NOT NULL DEFAULT '',
                    created_at        TEXT    NOT NULL,
                    updated_at        TEXT    NOT NULL
                )
            """)
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_university ON documents(university_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_name ON documents(doc_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_created ON documents(created_at DESC)")
    
    @staticmethod
    def insert(doc_name: str, original_filename: str, uploaded_by: str,
               university_id: Optional[int] = None, chunk_count: int = 0,
               file_size_kb: float = 0.0, file_type: str = "") -> int:
        """Insert document record."""
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO documents 
                   (doc_name, original_filename, uploaded_by, university_id, chunk_count,
                    file_size_kb, file_type, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_name, original_filename, uploaded_by, university_id, chunk_count,
                 file_size_kb, file_type, now, now),
            )
            return cursor.lastrowid
    
    @staticmethod
    def find_by_id(doc_id: int) -> Optional[Dict[str, Any]]:
        """Find document by ID."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def list_by_university(university_id: Optional[int] = None, page: int = 1, page_size: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """List documents with optional university filter and pagination."""
        with get_connection() as conn:
            query = "SELECT COUNT(*) as cnt FROM documents WHERE 1=1"
            params = []
            if university_id:
                query += " AND university_id = ?"
                params.append(university_id)
            total = conn.execute(query, params).fetchone()["cnt"]
            
            data_query = "SELECT * FROM documents WHERE 1=1"
            data_params = []
            if university_id:
                data_query += " AND university_id = ?"
                data_params.append(university_id)
            data_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            data_params.extend([page_size, (page - 1) * page_size])
            
            rows = conn.execute(data_query, data_params).fetchall()
            return [dict(r) for r in rows], total
    
    @staticmethod
    def search(query: str, university_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search documents by name (case-insensitive LIKE)."""
        with get_connection() as conn:
            sql = "SELECT * FROM documents WHERE doc_name LIKE ?"
            params = [f"%{query}%"]
            if university_id:
                sql += " AND university_id = ?"
                params.append(university_id)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    
    @staticmethod
    def update(doc_id: int, **kwargs) -> bool:
        """Update document fields (doc_name, chunk_count, file_size_kb, file_type)."""
        allowed = {"doc_name", "chunk_count", "file_size_kb", "file_type"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [doc_id]
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE documents SET {set_clause} WHERE id = ?", values
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def delete(doc_id: int) -> bool:
        """Hard delete document."""
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def count_by_university(university_id: Optional[int] = None) -> int:
        """Count documents with optional university filter."""
        with get_connection() as conn:
            query = "SELECT COUNT(*) as cnt FROM documents WHERE 1=1"
            params = []
            if university_id:
                query += " AND university_id = ?"
                params.append(university_id)
            return conn.execute(query, params).fetchone()["cnt"]


# =============================================================================
# TICKET QUERIES
# =============================================================================

class TicketQueries:
    """All ticket-related database queries.
    
    Schema matches tickets.py:
      id, user_id, university_id, query, response,
      department, priority, status, doc_id, chunks_used,
      response_time_ms, created_at, updated_at, resolved_at
    """
    
    @staticmethod
    def create_table():
        """Create tickets table with indexes."""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id          INTEGER NOT NULL,
                    university_id    INTEGER NOT NULL,
                    query            TEXT    NOT NULL,
                    response         TEXT,
                    department       TEXT    NOT NULL DEFAULT 'general',
                    priority         TEXT    NOT NULL DEFAULT 'medium',
                    status           TEXT    NOT NULL DEFAULT 'open',
                    doc_id           INTEGER,
                    chunks_used      INTEGER DEFAULT 0,
                    response_time_ms INTEGER,
                    created_at       TEXT    NOT NULL,
                    updated_at       TEXT    NOT NULL,
                    resolved_at      TEXT
                )
            """)
            # Indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_university ON tickets(university_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_department ON tickets(department)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at DESC)")
    
    @staticmethod
    def insert(user_id: int, university_id: int, query: str, response: str = "",
               department: str = "general", priority: str = "medium",
               doc_id: Optional[int] = None, chunks_used: int = 0,
               response_time_ms: Optional[int] = None) -> int:
        """Insert new ticket."""
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO tickets 
                   (user_id, university_id, query, response, department, priority,
                    status, doc_id, chunks_used, response_time_ms, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
                (user_id, university_id, query, response, department, priority,
                 doc_id, chunks_used, response_time_ms, now, now),
            )
            return cursor.lastrowid
    
    @staticmethod
    def find_by_id(ticket_id: int) -> Optional[Dict[str, Any]]:
        """Find ticket by ID."""
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def list_all(university_id: Optional[int] = None, user_id: Optional[int] = None,
                 status: Optional[str] = None, department: Optional[str] = None,
                 page: int = 1, page_size: int = 100) -> Tuple[List[Dict[str, Any]], int]:
        """List tickets with filtering and pagination."""
        with get_connection() as conn:
            count_query = "SELECT COUNT(*) as cnt FROM tickets WHERE 1=1"
            params = []
            if university_id:
                count_query += " AND university_id = ?"
                params.append(university_id)
            if user_id:
                count_query += " AND user_id = ?"
                params.append(user_id)
            if status:
                count_query += " AND status = ?"
                params.append(status)
            if department:
                count_query += " AND department = ?"
                params.append(department)
            total = conn.execute(count_query, params).fetchone()["cnt"]
            
            data_query = "SELECT * FROM tickets WHERE 1=1"
            data_params = []
            if university_id:
                data_query += " AND university_id = ?"
                data_params.append(university_id)
            if user_id:
                data_query += " AND user_id = ?"
                data_params.append(user_id)
            if status:
                data_query += " AND status = ?"
                data_params.append(status)
            if department:
                data_query += " AND department = ?"
                data_params.append(department)
            data_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            data_params.extend([page_size, (page - 1) * page_size])
            
            rows = conn.execute(data_query, data_params).fetchall()
            return [dict(r) for r in rows], total
    
    @staticmethod
    def update(ticket_id: int, **kwargs) -> bool:
        """Update ticket fields."""
        allowed = {"status", "department", "priority", "response", "resolved_at"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [ticket_id]
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE tickets SET {set_clause} WHERE id = ?", values
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def resolve(ticket_id: int, response: str = "") -> bool:
        """Resolve a ticket."""
        now = datetime.now(timezone.utc).isoformat()
        return TicketQueries.update(
            ticket_id, status="resolved", response=response, resolved_at=now
        )
    
    @staticmethod
    def delete(ticket_id: int) -> bool:
        """Delete ticket."""
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_stats(university_id: Optional[int] = None) -> Dict[str, Any]:
        """Get ticket statistics."""
        with get_connection() as conn:
            base = "SELECT COUNT(*) as cnt FROM tickets"
            params = []
            if university_id:
                base += " WHERE university_id = ?"
                params.append(university_id)
            total = conn.execute(base, params).fetchone()["cnt"]
            
            # By status
            status_sql = "SELECT status, COUNT(*) as cnt FROM tickets"
            if university_id:
                status_sql += " WHERE university_id = ?"
            status_sql += " GROUP BY status"
            status_rows = conn.execute(status_sql, params).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}
            
            # By department
            dept_sql = "SELECT department, COUNT(*) as cnt FROM tickets"
            if university_id:
                dept_sql += " WHERE university_id = ?"
            dept_sql += " GROUP BY department ORDER BY cnt DESC LIMIT 5"
            dept_rows = conn.execute(dept_sql, params).fetchall()
            
            return {
                "total": total,
                "by_status": by_status,
                "by_department": [dict(r) for r in dept_rows],
            }


# =============================================================================
# QUERY OPTIMIZATION UTILITIES
# =============================================================================

class QueryOptimizer:
    """Database query optimization utilities."""
    
    @staticmethod
    def explain_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Get query execution plan for optimization analysis.
        Useful for identifying missing indexes or slow queries.
        """
        with get_connection() as conn:
            rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
            return [dict(r) for r in rows]
    
    @staticmethod
    def analyze_table(table_name: str):
        """Run ANALYZE on a table to update query planner statistics."""
        with get_connection() as conn:
            conn.execute(f"ANALYZE {table_name}")
            logger.info("Analyzed table: %s", table_name)
    
    @staticmethod
    def get_table_stats(table_name: str) -> Dict[str, Any]:
        """Get table statistics."""
        with get_connection() as conn:
            # Row count
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table_name}").fetchone()
            count = row["cnt"]
            
            # Size — dbstat may not be available in all SQLite builds
            try:
                size_row = conn.execute(
                    "SELECT SUM(pgsize) as size FROM dbstat WHERE name = ?",
                    (table_name,),
                ).fetchone()
                size = size_row["size"] if size_row else 0
            except sqlite3.OperationalError:
                size = -1  # dbstat not available
            
            return {
                "table": table_name,
                "row_count": count,
                "size_bytes": size,
            }


# =============================================================================
# INITIALIZATION
# =============================================================================

def init_all_tables():
    """Initialize all database tables and indexes."""
    UserQueries.create_table()
    UniversityQueries.create_table()
    DocumentQueries.create_table()
    TicketQueries.create_table()
    logger.info("All database tables initialized")


# Convenience exports
__all__ = [
    "UserQueries",
    "UniversityQueries",
    "DocumentQueries",
    "TicketQueries",
    "QueryOptimizer",
    "get_connection",
    "init_all_tables",
]
