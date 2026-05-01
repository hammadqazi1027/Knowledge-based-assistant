"""
auth.py — Role-based authentication for the RAG pipeline.

Provides:
  - SQLite-backed user storage
  - bcrypt password hashing
  - Default admin seeding
  - Role enforcement: "admin", "teacher", "user"
  - Hardcoded super-admin credentials
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import bcrypt

logger = logging.getLogger(__name__)

# ── Database path ──────────────────────────────────────────────────────────
_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "rag_pipeline.db"

# Updated roles to include teacher
VALID_ROLES = ("admin", "teacher", "user")

# Hardcoded super-admin credentials (for system-level access)
HARDCODED_ADMIN = {
    "username": "superadmin",
    "password": "admin12345",
    "email": "superadmin@system.com"
}


def _get_conn() -> sqlite3.Connection:
    """Open a connection with row-factory enabled."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Initialisation ─────────────────────────────────────────────────────────

def init_auth_db() -> None:
    """Create the users table if it doesn't exist."""
    conn = _get_conn()
    try:
        # Check if table exists with old schema (role CHECK missing 'teacher')
        needs_recreate = False
        try:
            conn.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                        ("__schema_test__", "x", "teacher", "x"))
            conn.execute("DELETE FROM users WHERE username = ?", ("__schema_test__",))
            conn.commit()
        except sqlite3.IntegrityError:
            needs_recreate = True
            conn.rollback()
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            pass
        
        if needs_recreate:
            logger.info("Migrating users table to support 'teacher' role...")
            # Save existing data
            rows = conn.execute("SELECT id, username, password_hash, role, university_id, created_at FROM users").fetchall()
            existing_users = [dict(r) for r in rows]
            # Drop and recreate
            conn.execute("DROP TABLE users")
            conn.commit()
            conn.execute("""
                CREATE TABLE users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT    NOT NULL UNIQUE,
                    password_hash TEXT    NOT NULL,
                    role          TEXT    NOT NULL CHECK (role IN ('admin', 'teacher', 'user')),
                    university_id INTEGER,
                    created_at    TEXT    NOT NULL
                )
            """)
            # Restore data
            for u in existing_users:
                conn.execute(
                    "INSERT INTO users (id, username, password_hash, role, university_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (u["id"], u["username"], u["password_hash"], u["role"], u.get("university_id"), u["created_at"]),
                )
            conn.commit()
            logger.info("Migrated %d users to new schema.", len(existing_users))
        else:
            # Create table if it doesn't exist
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
            conn.commit()
        
        # Create indexes for query optimization
        _ensure_index(conn, "idx_users_university", "CREATE INDEX IF NOT EXISTS idx_users_university ON users(university_id)")
        _ensure_index(conn, "idx_users_role", "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        _ensure_index(conn, "idx_users_username", "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        
        logger.info("Users table initialised at %s", _DB_PATH)
    finally:
        conn.close()


def _ensure_index(conn: sqlite3.Connection, name: str, sql: str) -> None:
    """Create an index if it doesn't already exist."""
    try:
        conn.execute(sql)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Index may already exist


def seed_default_admin() -> None:
    """
    Create default demo accounts for each role if they don't exist.
    Creates: admin, teacher, and user demo accounts.
    """
    from university import list_universities
    
    conn = _get_conn()
    try:
        universities = list_universities()
        default_uni_id = universities[0]["id"] if universities else None
        
        demo_accounts = [
            ("admin", "admin123", "admin"),
            ("teacher", "teacher123", "teacher"),
            ("user", "user123", "user"),
        ]
        
        now = datetime.now(timezone.utc).isoformat()
        created_any = False
        
        for username, password, role in demo_accounts:
            # Check if this specific demo account already exists
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row["cnt"] > 0:
                continue
            
            _hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            conn.execute(
                "INSERT INTO users (username, password_hash, role, university_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, _hash, role, default_uni_id, now),
            )
            logger.info("Created demo %s account: %s / %s", role, username, password)
            created_any = True
        
        if created_any:
            conn.commit()
    finally:
        conn.close()


# ── Registration ──────────────────────────────────────────────────────────

def register_user(username: str, password: str, role: str = "user", university_id: Optional[int] = None) -> int:
    """
    Register a new user with a hashed password.
    
    Args:
        username: Unique login name.
        password: Plain-text password (will be hashed).
        role:     "admin", "teacher", or "user".
        university_id: The university this user belongs to.
    
    Returns:
        The new user's ID.
    """
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty.")
    if len(password) < 4:
        raise ValueError("Password must be at least 4 characters.")
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of: {VALID_ROLES}")

    _hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, university_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, _hash, role, university_id, now),
        )
        conn.commit()
        user_id = cursor.lastrowid
        logger.info("Registered user '%s' (role=%s, id=%d).", username, role, user_id)
        return user_id
    except sqlite3.IntegrityError:
        raise ValueError(f"Username '{username}' is already taken.")
    finally:
        conn.close()


# ── Authentication ─────────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Verify credentials and return user info.
    Supports both database users and hardcoded super-admin.
    """
    # Check hardcoded super-admin first
    if username == HARDCODED_ADMIN["username"] and password == HARDCODED_ADMIN["password"]:
        return {
            "id": -1,  # Special ID for hardcoded admin
            "username": HARDCODED_ADMIN["username"],
            "role": "admin",
            "university_id": None,
            "is_hardcoded": True,
        }
    
    # Check database users
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        if not row:
            return None

        if bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "university_id": row["university_id"],
                "is_hardcoded": False,
            }
        return None
    finally:
        conn.close()


# ── User management ───────────────────────────────────────────────────────

def list_users(role: Optional[str] = None, university_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List all users, optionally filtered."""
    conn = _get_conn()
    try:
        query = "SELECT id, username, role, university_id, created_at FROM users WHERE 1=1"
        params = []
        
        if role:
            query += " AND role = ?"
            params.append(role)
        if university_id:
            query += " AND university_id = ?"
            params.append(university_id)
        
        query += " ORDER BY created_at"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    """Delete a user by ID. Returns True if deleted."""
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted user id=%d.", user_id)
        return deleted
    finally:
        conn.close()


def get_user_count(role: Optional[str] = None, university_id: Optional[int] = None) -> int:
    """Count users with optional filters."""
    conn = _get_conn()
    try:
        query = "SELECT COUNT(*) as cnt FROM users WHERE 1=1"
        params = []
        
        if role:
            query += " AND role = ?"
            params.append(role)
        if university_id:
            query += " AND university_id = ?"
            params.append(university_id)
        
        row = conn.execute(query, params).fetchone()
        return row["cnt"]
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, role, university_id, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
