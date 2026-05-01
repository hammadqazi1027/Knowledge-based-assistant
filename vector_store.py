"""
vector_store.py — Zilliz Cloud (managed Milvus) integration.

Handles:
  - Auto-connecting using credentials from .env
  - Auto-creating the collection + index if they don't exist
  - Inserting chunks with their embeddings and doc_id
  - Cosine-similarity search (optionally scoped by doc_id)
  - Deleting chunks by doc_id
  - Listing indexed sources and collection statistics
"""

import logging
from typing import List, Dict, Any, Optional

from pymilvus import MilvusClient, DataType

import config

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Thin wrapper around MilvusClient that manages the RAG document collection.

    The collection schema:
      - id          : INT64  (auto-id primary key)
      - text        : VARCHAR(65535)  — the raw chunk text
      - embedding   : FLOAT_VECTOR(EMBEDDING_DIM)  — dense embedding
      - source      : VARCHAR(512)   — original filename (kept for display)
      - doc_id      : INT32          — links to documents.id in SQLite
      - chunk_index : INT32          — position within the document
      - page        : INT32          — page number (0 if unavailable)
    """

    # Maximum varchar length Milvus supports
    _MAX_TEXT_LEN = 65_535
    _MAX_SOURCE_LEN = 512

    def __init__(self) -> None:
        self._client: Optional[MilvusClient] = None
        self._collection = config.COLLECTION_NAME
        self._dim = config.EMBEDDING_DIM

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """
        Establish connection to Zilliz Cloud and ensure the collection exists.
        Raises a clear error if the connection fails.
        """
        try:
            logger.info("Connecting to Zilliz Cloud: %s", config.ZILLIZ_URI)
            self._client = MilvusClient(
                uri=config.ZILLIZ_URI,
                token=config.ZILLIZ_TOKEN,
            )
            # Quick connectivity check
            self._client.list_collections()
            logger.info("Connected successfully.")
        except Exception as exc:
            raise ConnectionError(
                f"Failed to connect to Zilliz Cloud at {config.ZILLIZ_URI}.\n"
                f"Please verify your ZILLIZ_URI and ZILLIZ_TOKEN in the .env file.\n"
                f"Error details: {exc}"
            ) from exc

        self._ensure_collection()

    @property
    def client(self) -> MilvusClient:
        if self._client is None:
            raise RuntimeError("VectorStore is not connected. Call connect() first.")
        return self._client

    # ── Schema & Collection ───────────────────────────────────────────────────

    def _ensure_collection(self) -> None:
        """Create the collection and COSINE index if they don't already exist."""
        existing = self.client.list_collections()
        
        if self._collection in existing:
            try:
                desc = self.client.describe_collection(self._collection)
                field_names = [f.get("name", "") for f in desc.get("fields", [])]
                
                if "university_id" not in field_names:
                    logger.info("Collection exists but missing university_id — recreating...")
                    try:
                        self.client.drop_collection(self._collection)
                        logger.info("Dropped old collection '%s'", self._collection)
                    except Exception as e:
                        logger.warning("Could not drop collection: %s", e)
                else:
                    logger.info("Collection '%s' already exists with correct schema.", self._collection)
                    return
            except Exception as e:
                logger.warning("Could not describe collection: %s", e)

        logger.info("Creating collection '%s' (dim=%d)...", self._collection, self._dim)

        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("text", DataType.VARCHAR, max_length=self._MAX_TEXT_LEN)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self._dim)
        schema.add_field("source", DataType.VARCHAR, max_length=self._MAX_SOURCE_LEN)
        schema.add_field("doc_id", DataType.INT32)
        schema.add_field("chunk_index", DataType.INT32)
        schema.add_field("page", DataType.INT32)
        schema.add_field("university_id", DataType.INT32)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )

        self.client.create_collection(
            collection_name=self._collection,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Collection '%s' created successfully.", self._collection)

    # ── Insert ────────────────────────────────────────────────────────────────

    def insert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        doc_id: int = 0,
        university_id: int = 0,
    ) -> int:
        """
        Insert chunks with their embeddings into the collection.

        Args:
            chunks:     List of chunk dicts (must have: text, source, chunk_index, page)
            embeddings: Parallel list of embedding vectors.
            doc_id:     The document ID from the SQLite metadata table.
            university_id: The university this document belongs to.

        Returns:
            Number of inserted records.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings."
            )

        rows = []
        for chunk, emb in zip(chunks, embeddings):
            text = chunk["text"][: self._MAX_TEXT_LEN]
            source = chunk["source"][: self._MAX_SOURCE_LEN]

            rows.append({
                "text": text,
                "embedding": emb,
                "source": source,
                "doc_id": int(doc_id),
                "chunk_index": int(chunk["chunk_index"]),
                "page": int(chunk.get("page", 0)),
                "university_id": int(university_id),
            })

        result = self.client.insert(collection_name=self._collection, data=rows)
        # pymilvus 2.4+ returns a MutationResult object; older versions return a dict
        if hasattr(result, "insert_count"):
            inserted = result.insert_count
        elif isinstance(result, dict):
            inserted = result.get("insert_count", len(rows))
        else:
            inserted = len(rows)
        logger.info("Inserted %d chunks for doc_id=%d.", inserted, doc_id)
        return inserted

    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        doc_id: Optional[int] = None,
        source_filter: Optional[str] = None,
        university_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Cosine-similarity search against stored embeddings.

        Args:
            query_embedding: Dense vector of the user query.
            top_k:           Number of results to return.
            doc_id:          Optional document ID to restrict results to one document.
            source_filter:   Optional filename to restrict results (legacy support).
            university_id:   Optional university ID to restrict results to one university.

        Returns:
            List of result dicts with keys: text, source, page, chunk_index, doc_id, university_id, score
        """
        search_kwargs = dict(
            collection_name=self._collection,
            data=[query_embedding],
            anns_field="embedding",
            search_params={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            output_fields=["text", "source", "chunk_index", "page", "doc_id", "university_id"],
        )

        filters = []
        if doc_id is not None:
            filters.append(f"doc_id == {doc_id}")
        if source_filter:
            filters.append(f'source == "{source_filter}"')
        if university_id is not None:
            filters.append(f"university_id == {university_id}")
        if filters:
            search_kwargs["filter"] = " && ".join(filters)

        hits = self.client.search(**search_kwargs)

        results = []
        for hit in hits[0]:
            results.append({
                "text": hit["entity"]["text"],
                "source": hit["entity"]["source"],
                "chunk_index": hit["entity"]["chunk_index"],
                "page": hit["entity"]["page"],
                "doc_id": hit["entity"].get("doc_id", 0),
                "university_id": hit["entity"].get("university_id", 0),
                "score": round(float(hit["distance"]), 4),
            })

        return results

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_by_doc_id(self, doc_id: int) -> int:
        """
        Delete all chunks belonging to a specific document ID.

        Args:
            doc_id: The document ID to remove.

        Returns:
            Number of deleted records.
        """
        try:
            result = self.client.delete(
                collection_name=self._collection,
                filter=f"doc_id == {doc_id}",
            )
            if hasattr(result, "delete_count"):
                deleted = result.delete_count
            elif isinstance(result, dict):
                deleted = result.get("delete_count", 0)
            else:
                deleted = 0
            logger.info("Deleted %d chunks for doc_id=%d.", deleted, doc_id)
            return deleted
        except Exception as exc:
            logger.warning("Delete for doc_id=%d raised: %s", doc_id, exc)
            return 0

    def delete_by_source(self, filename: str) -> int:
        """
        Delete all chunks belonging to a specific source file (legacy support).

        Args:
            filename: The source filename to remove.

        Returns:
            Number of deleted records.
        """
        try:
            result = self.client.delete(
                collection_name=self._collection,
                filter=f'source == "{filename}"',
            )
            if hasattr(result, "delete_count"):
                deleted = result.delete_count
            elif isinstance(result, dict):
                deleted = result.get("delete_count", 0)
            else:
                deleted = 0
            logger.info("Deleted %d chunks for source '%s'.", deleted, filename)
            return deleted
        except Exception as exc:
            logger.warning("Delete for '%s' raised: %s", filename, exc)
            return 0

    def clear_collection(self) -> None:
        """Drop and recreate the collection (deletes ALL data)."""
        try:
            self.client.drop_collection(self._collection)
            logger.info("Collection '%s' dropped.", self._collection)
        except Exception:
            pass  # Already gone
        self._ensure_collection()

    # ── Metadata queries ──────────────────────────────────────────────────────

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Return statistics about the collection.

        NOTE: Zilliz Cloud serverless has eventual consistency — `row_count`
        from `get_collection_stats` can lag behind actual inserts by many
        seconds.  We instead count by querying real rows (chunk_index >= 0),
        which reflects actual committed data immediately.

        Returns:
            Dict with: total_chunks (int), sources (list of unique filenames)
        """
        try:
            # Query all chunk-index-0 rows to get distinct source files
            source_rows = self.client.query(
                collection_name=self._collection,
                filter="chunk_index == 0",
                output_fields=["source", "doc_id"],
                limit=500,
            )
            sources = sorted({r["source"] for r in source_rows})

            # Count total chunks via a broad query (limit 16384 is Milvus max)
            if sources:
                total = 0
                for src in sources:
                    rows = self.client.query(
                        collection_name=self._collection,
                        filter=f'source == "{src}"',
                        output_fields=["chunk_index"],
                        limit=16384,
                    )
                    total += len(rows)
            else:
                total = 0

            return {"total_chunks": total, "sources": sources}
        except Exception as exc:
            logger.warning("Could not retrieve collection stats: %s", exc)
            return {"total_chunks": 0, "sources": []}

    def get_doc_chunk_count(self, doc_id: int) -> int:
        """Return the number of chunks stored for a specific doc_id."""
        try:
            rows = self.client.query(
                collection_name=self._collection,
                filter=f"doc_id == {doc_id}",
                output_fields=["chunk_index"],
                limit=16384,
            )
            return len(rows)
        except Exception:
            return 0

    def is_source_indexed(self, filename: str) -> bool:
        """Return True if at least one chunk from this file is already stored."""
        try:
            rows = self.client.query(
                collection_name=self._collection,
                filter=f'source == "{filename}"',
                output_fields=["chunk_index"],
                limit=1,
            )
            return len(rows) > 0
        except Exception:
            return False
