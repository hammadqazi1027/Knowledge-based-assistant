"""
db.py — SQLite document metadata manager.

Tracks documents uploaded by admins with custom display names,
original filenames, upload timestamps, and chunk counts.
The `id` column serves as `doc_id` throughout the system, linking
metadata here to embeddings stored in Zilliz Cloud.

Database file: data/rag_pipeline.db (auto-created on first run)
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ── Database path ─────────────────────────────────────────────────────────────
_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "rag_pipeline.db"


def _get_conn() -> sqlite3.Connection:
    """Open a connection with row-factory enabled for dict-like access."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")       # Better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Initialisation ────────────────────────────────────────────────────────────

def init_docs_db() -> None:
    """Create the documents table if it doesn't exist."""
    conn = _get_conn()
    try:
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
        conn.commit()
        
        # Migration: Add university_id column if it doesn't exist
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN university_id INTEGER")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create indexes for query optimization
        _ensure_index(conn, "idx_docs_university", "CREATE INDEX IF NOT EXISTS idx_docs_university ON documents(university_id)")
        _ensure_index(conn, "idx_docs_name", "CREATE INDEX IF NOT EXISTS idx_docs_name ON documents(doc_name)")
        _ensure_index(conn, "idx_docs_created", "CREATE INDEX IF NOT EXISTS idx_docs_created ON documents(created_at DESC)")
        
        logger.info("Documents table initialised at %s", _DB_PATH)
    finally:
        conn.close()


def _ensure_index(conn: sqlite3.Connection, name: str, sql: str) -> None:
    """Create an index if it doesn't already exist."""
    try:
        conn.execute(sql)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Index may already exist


# ── CRUD operations ───────────────────────────────────────────────────────────

def add_document(
    doc_name: str,
    original_filename: str,
    uploaded_by: str,
    university_id: Optional[int] = None,
    chunk_count: int = 0,
    file_size_kb: float = 0.0,
    file_type: str = "",
) -> int:
    """
    Insert a new document record and return its `doc_id`.

    Args:
        doc_name:          Admin-assigned custom display name.
        original_filename: Original uploaded filename.
        uploaded_by:       Admin username who uploaded.
        university_id:     University this document belongs to.
        chunk_count:       Number of chunks stored in vector DB.
        file_size_kb:      File size in KB.
        file_type:         File extension (.pdf, .txt, .docx).

    Returns:
        The auto-generated document ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT INTO documents
                (doc_name, original_filename, uploaded_by, university_id, chunk_count,
                 file_size_kb, file_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_name, original_filename, uploaded_by, university_id, chunk_count,
             file_size_kb, file_type, now, now),
        )
        conn.commit()
        doc_id = cursor.lastrowid
        logger.info("Added document id=%d name='%s' university_id=%s", doc_id, doc_name, university_id)
        return doc_id
    finally:
        conn.close()


def get_document(doc_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single document by its ID. Returns None if not found."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_documents(university_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return all documents for a university, ordered by most recent first."""
    conn = _get_conn()
    try:
        if university_id:
            rows = conn.execute(
                "SELECT * FROM documents WHERE university_id = ? ORDER BY created_at DESC",
                (university_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_documents(query: str, university_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Search documents by custom name (case-insensitive LIKE match).

    Args:
        query: Search string — matches anywhere in doc_name.
        university_id: Optional university filter.

    Returns:
        Matching documents, ordered by most recent first.
    """
    conn = _get_conn()
    try:
        if university_id:
            rows = conn.execute(
                "SELECT * FROM documents WHERE doc_name LIKE ? AND university_id = ? ORDER BY created_at DESC",
                (f"%{query}%", university_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents WHERE doc_name LIKE ? ORDER BY created_at DESC",
                (f"%{query}%",),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_document(doc_id: int, **kwargs) -> bool:
    """
    Update one or more fields of a document record.

    Allowed kwargs: doc_name, chunk_count, file_size_kb, file_type.
    Returns True if the row was updated, False if doc_id was not found.
    """
    allowed = {"doc_name", "chunk_count", "file_size_kb", "file_type"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [doc_id]

    conn = _get_conn()
    try:
        cursor = conn.execute(
            f"UPDATE documents SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info("Updated document id=%d: %s", doc_id, list(fields.keys()))
        return updated
    finally:
        conn.close()


def delete_document(doc_id: int) -> bool:
    """
    Delete a document record by ID.
    Returns True if a row was actually deleted.
    """
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted document id=%d", doc_id)
        return deleted
    finally:
        conn.close()


def delete_all_documents() -> int:
    """Delete ALL document records. Returns the count of deleted rows."""
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM documents")
        conn.commit()
        logger.info("Deleted all %d document records.", cursor.rowcount)
        return cursor.rowcount
    finally:
        conn.close()
