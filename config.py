"""
config.py — Load and validate all environment variables for the RAG pipeline.

All settings are read from the .env file in the project root.
Clear, actionable error messages are raised if required values are missing.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env file from the project root ─────────────────────────────────────
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)


def _require(key: str) -> str:
    """Read a required environment variable or raise a descriptive error."""
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: '{key}'\n"
            f"Please add it to your .env file at: {_env_path}"
        )
    return value


def _optional(key: str, default: str) -> str:
    """Read an optional environment variable, falling back to a default."""
    return os.getenv(key, "").strip() or default


# ── Zilliz Cloud ──────────────────────────────────────────────────────────────
ZILLIZ_URI: str = _require("ZILLIZ_URI")
ZILLIZ_TOKEN: str = _require("ZILLIZ_TOKEN")

# ── LLM ──────────────────────────────────────────────────────────────────────
# GROQ_API_KEY is optional; the app runs in demo mode without it.
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
LLM_MODEL: str = _optional("LLM_MODEL", "llama-3.3-70b-versatile")

# ── Embedding ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = _optional("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM: int = int(_optional("EMBEDDING_DIM", "384"))

# ── Milvus Collection ─────────────────────────────────────────────────────────
COLLECTION_NAME: str = _optional("COLLECTION_NAME", "rag_documents")

# ── RAG Tuning ────────────────────────────────────────────────────────────────
TOP_K_RESULTS: int = int(_optional("TOP_K_RESULTS", "5"))
CHUNK_SIZE: int = int(_optional("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(_optional("CHUNK_OVERLAP", "200"))

# ── Derived flags ─────────────────────────────────────────────────────────────
LLM_AVAILABLE: bool = bool(GROQ_API_KEY)


def print_config_summary() -> None:
    """Print a non-sensitive summary of the current configuration."""
    print("─" * 50)
    print("RAG Pipeline Configuration")
    print("─" * 50)
    print(f"  Zilliz URI      : {ZILLIZ_URI}")
    print(f"  Collection      : {COLLECTION_NAME}")
    print(f"  Embedding model : {EMBEDDING_MODEL}  (dim={EMBEDDING_DIM})")
    print(f"  LLM model       : {LLM_MODEL}")
    print(f"  LLM available   : {LLM_AVAILABLE}")
    print(f"  Chunk size      : {CHUNK_SIZE} chars  (overlap={CHUNK_OVERLAP})")
    print(f"  Top-K results   : {TOP_K_RESULTS}")
    print("─" * 50)
