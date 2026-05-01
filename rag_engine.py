"""
rag_engine.py — The core RAG pipeline: embed → retrieve → generate.

This module owns:
  1. The embedding model (sentence-transformers, loaded once and cached)
  2. The retrieval step (vector search via VectorStore)
  3. The generation step (Groq LLM, with a demo fallback if no API key)
  4. Conversation memory for multi-turn chat
  5. Hybrid search (vector + multi-query expansion)
  6. Re-ranking (MMR + keyword boost)
  7. Query rewriting (LLM-based expansion)
  8. Context window management (token-budget trimming)

Design principles:
  - The embedding model is a module-level singleton to avoid reloading on
    every request.
  - Generation is streaming-capable (yields tokens as they arrive from Groq).
  - If no GROQ_API_KEY is present the engine runs in DEMO MODE, returning a
    simulated response that clearly explains the situation.
"""

import logging
import os
import re
import textwrap
import warnings
from typing import List, Dict, Any, Generator, Optional

# ── Suppress harmless warnings from transformers / huggingface_hub ────────────
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # Avoids deadlock warning
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings("ignore", message=".*position_ids.*")
warnings.filterwarnings("ignore", message=".*unauthenticated.*")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")

from sentence_transformers import SentenceTransformer

import config
from vector_store import VectorStore

logger = logging.getLogger(__name__)

# ── Embedding model singleton ─────────────────────────────────────────────────
_embedding_model: Optional[SentenceTransformer] = None


def _get_embedding_model() -> SentenceTransformer:
    """Lazy-load the embedding model (cached after first call)."""
    global _embedding_model
    if _embedding_model is None:
        import io, sys
        logger.info("Loading embedding model: %s", config.EMBEDDING_MODEL)
        _devnull = io.StringIO()
        _old_stdout, _old_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = _devnull
        try:
            _embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        finally:
            sys.stdout, sys.stderr = _old_stdout, _old_stderr
        logger.info("Embedding model loaded successfully.")
    return _embedding_model


# ── Embedding helpers ─────────────────────────────────────────────────────────

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Convert a list of strings into dense embedding vectors."""
    model = _get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]


# ── Conversation Memory ───────────────────────────────────────────────────────

class ConversationMemory:
    """
    Simple in-memory conversation store with automatic summarization
    when the context grows too large.
    """

    def __init__(self, max_messages: int = 10, max_summary_chars: int = 500):
        self.messages: List[Dict[str, str]] = []
        self.max_messages = max_messages
        self.max_summary_chars = max_summary_chars
        self.summary: str = ""

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self._summarize()

    def get_context(self) -> str:
        """Return formatted conversation history for the prompt."""
        parts = []
        if self.summary:
            parts.append(f"[Earlier conversation summary]: {self.summary}")
        for msg in self.messages:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{prefix}: {msg['content']}")
        return "\n".join(parts)

    def clear(self) -> None:
        self.messages.clear()
        self.summary = ""

    def _summarize(self) -> None:
        """Summarize older messages to keep context window manageable."""
        to_summarize = self.messages[: self.max_messages // 2]
        self.messages = self.messages[self.max_messages // 2 :]
        summary_text = " | ".join(
            f"{m['role']}: {m['content'][:80]}..." for m in to_summarize
        )
        self.summary = (self.summary + " " + summary_text)[: self.max_summary_chars]


# ── Query Rewriting ───────────────────────────────────────────────────────────

_REWRITE_PROMPT = textwrap.dedent("""
    Given the user query, generate up to 3 alternative phrasings that might
    retrieve better results from a document search system. Each variation
    should capture a different angle or use synonyms.

    User query: "{query}"

    Respond with ONLY the rewritten queries, one per line, no numbering or
    extra text. If the query is already very specific, just repeat it.
""").strip()


def rewrite_query(query: str) -> List[str]:
    """
    Use the LLM to generate query variations for better retrieval coverage.
    Returns a list including the original query + rewritten versions.
    """
    if not config.LLM_AVAILABLE:
        return [query]

    try:
        from groq import Groq
        groq_client = Groq(api_key=config.GROQ_API_KEY)

        response = groq_client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": _REWRITE_PROMPT.format(query=query)}],
            temperature=0.3,
            max_tokens=200,
        )

        text = response.choices[0].message.content.strip()
        variations = [line.strip() for line in text.split("\n") if line.strip()]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for v in ([query] + variations):
            v_lower = v.lower().strip(".?!")
            if v_lower not in seen:
                seen.add(v_lower)
                unique.append(v)
        return unique[:4]  # Original + up to 3 rewrites
    except Exception as exc:
        logger.warning("Query rewriting failed: %s", exc)
        return [query]


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    vector_store: VectorStore,
    top_k: int = config.TOP_K_RESULTS,
    doc_id: Optional[int] = None,
    source_filter: Optional[str] = None,
    university_id: Optional[int] = None,
    use_hybrid: bool = True,
) -> List[Dict[str, Any]]:
    """
    Embed the user query and retrieve the top-K most similar document chunks.

    When use_hybrid=True, the query is rewritten into multiple variations,
    each is embedded and searched, and results are merged, deduplicated,
    and re-ranked for better coverage.

    Args:
        query:         The user's natural-language question.
        vector_store:  Connected VectorStore instance.
        top_k:         Maximum number of chunks to retrieve.
        doc_id:        Optional document ID to limit search to one document.
        source_filter: Optional filename to limit search (legacy support).
        university_id: Optional university ID to limit search to one university.
        use_hybrid:    Whether to use multi-query hybrid search.

    Returns:
        List of result dicts: {text, source, page, chunk_index, doc_id, university_id, score}
        Sorted by descending cosine similarity score.
    """
    queries = rewrite_query(query) if use_hybrid else [query]
    all_results: List[Dict[str, Any]] = []

    for q in queries:
        query_vec = embed_query(q)
        results = vector_store.search(
            query_embedding=query_vec,
            top_k=top_k * 2,  # Over-fetch for re-ranking
            doc_id=doc_id,
            source_filter=source_filter,
            university_id=university_id,
        )
        all_results.extend(results)

    # Deduplicate by (doc_id, chunk_index)
    seen = set()
    deduped = []
    for r in all_results:
        key = (r.get("doc_id", 0), r.get("chunk_index", 0))
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # Re-rank: combine vector score with keyword overlap boost
    reranked = _rerank_chunks(query, deduped)

    # Filter low-quality results
    reranked = [r for r in reranked if r["score"] >= 0.20]

    logger.info("Retrieved %d relevant chunks for query (hybrid=%s).", len(reranked), use_hybrid)
    return reranked[:top_k]


def _rerank_chunks(query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Re-rank chunks using a lightweight keyword-overlap heuristic combined
    with the original vector similarity score (Maximal Marginal Relevance style).
    """
    query_tokens = set(_tokenize(query))
    scored = []

    for chunk in chunks:
        chunk_tokens = set(_tokenize(chunk["text"]))
        # Jaccard-like overlap score
        overlap = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)
        # Combine vector score (0-1) with keyword overlap (0-1), weighted
        combined = 0.6 * chunk["score"] + 0.4 * min(overlap, 1.0)
        scored.append({**chunk, "score": round(combined, 4)})

    # Sort by combined score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _tokenize(text: str) -> List[str]:
    """Simple tokenizer for keyword overlap scoring."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


# ── Context Window Management ─────────────────────────────────────────────────

_MAX_CONTEXT_TOKENS = 3000  # Rough token budget for context (leaves room for answer)
_AVG_CHARS_PER_TOKEN = 4


def trim_context(chunks: List[Dict[str, Any]], max_tokens: int = _MAX_CONTEXT_TOKENS) -> List[Dict[str, Any]]:
    """
    Trim chunks to fit within a token budget, keeping the most relevant ones.
    """
    max_chars = max_tokens * _AVG_CHARS_PER_TOKEN
    total_chars = 0
    trimmed = []

    for chunk in chunks:
        text_len = len(chunk["text"])
        if total_chars + text_len > max_chars and trimmed:
            break
        trimmed.append(chunk)
        total_chars += text_len

    return trimmed


# ── Prompt building ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = textwrap.dedent("""
    You are a precise, factual assistant. Your ONLY job is to answer the user's
    question using the context passages provided below. Follow these rules strictly:

    1. Base your answer EXCLUSIVELY on the provided context. Do not use outside knowledge.
    2. If the context does not contain enough information to answer, say so clearly.
    3. Cite the source file and page number when referencing specific information.
    4. Be concise, accurate, and well-structured. Use bullet points or numbered lists
       when appropriate to improve readability.
    5. Never fabricate information or speculate beyond the given context.
""").strip()


def _build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a numbered context block for the LLM prompt."""
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk["source"]
        page = chunk.get("page", 0)
        score = chunk.get("score", 0)
        page_info = f", page {page}" if page else ""
        blocks.append(
            f"[Context {i}] (source: {source}{page_info}, relevance: {score:.2f})\n"
            f"{chunk['text']}"
        )
    return "\n\n" + "\n\n---\n\n".join(blocks) + "\n"


def _build_conversation_aware_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    memory: Optional[ConversationMemory] = None,
) -> str:
    """Build the full user message including conversation history and context."""
    context_block = _build_context_block(chunks)
    parts = []

    if memory and (memory.messages or memory.summary):
        parts.append("Previous conversation:\n" + memory.get_context())
        parts.append("")

    parts.append(f"Context passages from the uploaded documents:\n{context_block}")
    parts.append(f"Question: {query}")
    parts.append("Please answer the question based solely on the context above.")

    return "\n\n".join(parts)


# ── Generation ────────────────────────────────────────────────────────────────

def generate_answer(
    query: str,
    chunks: List[Dict[str, Any]],
    memory: Optional[ConversationMemory] = None,
) -> Generator[str, None, None]:
    """
    Generate a streamed answer grounded in the retrieved chunks.

    If GROQ_API_KEY is not set, yields a demo response explaining the situation.

    Args:
        query:  The user's question.
        chunks: Retrieved context chunks from the vector store.
        memory: Optional conversation memory for multi-turn context.

    Yields:
        Successive string tokens of the LLM response.
    """
    # ── No context found ──────────────────────────────────────────────────────
    if not chunks:
        yield (
            "⚠️ **No relevant information found.**\n\n"
            "The uploaded documents do not appear to contain information related "
            "to your question. Please try:\n"
            "- Rephrasing your question\n"
            "- Uploading a document that covers this topic\n"
            "- Checking that the document was processed successfully"
        )
        return

    # Trim context to fit token budget
    chunks = trim_context(chunks)
    user_message = _build_conversation_aware_prompt(query, chunks, memory)

    # ── Demo mode (no API key) ────────────────────────────────────────────────
    if not config.LLM_AVAILABLE:
        yield _demo_response(query, chunks)
        return

    # ── Groq LLM streaming ────────────────────────────────────────────────────
    try:
        from groq import Groq
        groq_client = Groq(api_key=config.GROQ_API_KEY)

        stream = groq_client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1024,
            stream=True,
        )

        for chunk_event in stream:
            delta = chunk_event.choices[0].delta.content
            if delta:
                yield delta

    except Exception as exc:
        logger.error("Groq API error: %s", exc)
        yield (
            f"❌ **LLM Error:** {exc}\n\n"
            "Please check your GROQ_API_KEY in the .env file and try again."
        )


def _demo_response(query: str, chunks: List[Dict[str, Any]]) -> str:
    """Generate a demo response when no LLM API key is configured."""
    sources = list({c["source"] for c in chunks})
    top_chunk = chunks[0]["text"][:400] + "..." if len(chunks[0]["text"]) > 400 else chunks[0]["text"]

    return (
        f"🔑 **Demo Mode — LLM not configured**\n\n"
        f"Retrieval is working correctly! Found **{len(chunks)} relevant chunks** "
        f"from: *{', '.join(sources)}*\n\n"
        f"**Most relevant passage (relevance: {chunks[0]['score']:.2f}):**\n"
        f"> {top_chunk}\n\n"
        f"---\n"
        f"To enable full AI-generated answers:\n"
        f"1. Get a free API key at [console.groq.com](https://console.groq.com)\n"
        f"2. Add `GROQ_API_KEY=your_key` to the `.env` file\n"
        f"3. Restart the app"
    )


# ── LLM-based Query Classification ─────────────────────────────────────────────

DEPARTMENTS = ["general", "admissions", "academic", "finance", "hr", "it", "library", "other"]
PRIORITIES = ["low", "medium", "high", "urgent"]

_CLASSIFICATION_PROMPT = textwrap.dedent("""
    Classify the following query into a department and priority level.
    
    Query: "{query}"
    
    Respond in EXACTLY this format (no other text):
    department: <department>
    priority: <priority>
    
    Departments: general, admissions, academic, finance, hr, it, library, other
    Priorities: low (general info), medium (standard questions), high (time-sensitive), urgent (critical)
    
    Guidelines:
    - admissions: questions about enrollment, applications, registration
    - academic: courses, grades, exams, curriculum, faculty
    - finance: fees, payments, scholarships, financial aid
    - hr: employment, payroll, staff policies
    - it: technical issues, systems, software, accounts
    - library: books, resources, research materials
    - general: general policies, hours, contact info
    - other: anything that doesn't fit above
    
    - urgent: deadline-critical or system-down issues
    - high: needs response within hours
    - medium: standard response time ok
    - low: informational, no deadline
""").strip()


def classify_query(query: str) -> Dict[str, str]:
    """Use LLM to classify a query by department and priority."""
    if not config.LLM_AVAILABLE:
        return {"department": "general", "priority": "medium"}

    try:
        from groq import Groq
        groq_client = Groq(api_key=config.GROQ_API_KEY)

        response = groq_client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": _CLASSIFICATION_PROMPT.format(query=query)}],
            temperature=0.1,
            max_tokens=100,
        )

        text = response.choices[0].message.content.strip().lower()

        department = "general"
        priority = "medium"

        for line in text.split("\n"):
            if "department:" in line:
                dept_val = line.split("department:")[-1].strip()
                if dept_val in DEPARTMENTS:
                    department = dept_val
            elif "priority:" in line:
                pri_val = line.split("priority:")[-1].strip()
                if pri_val in PRIORITIES:
                    priority = pri_val

        logger.info("Classified query as department=%s, priority=%s", department, priority)
        return {"department": department, "priority": priority}

    except Exception as exc:
        logger.warning("Query classification failed: %s", exc)
        return {"department": "general", "priority": "medium"}


# ── Full RAG pipeline (convenience wrapper) ───────────────────────────────────

def answer(
    query: str,
    vector_store: VectorStore,
    top_k: int = config.TOP_K_RESULTS,
    doc_id: Optional[int] = None,
    source_filter: Optional[str] = None,
    university_id: Optional[int] = None,
    memory: Optional[ConversationMemory] = None,
    use_hybrid: bool = True,
) -> tuple[Generator[str, None, None], List[Dict[str, Any]]]:
    """
    End-to-end RAG: retrieve relevant chunks, then stream the generated answer.

    Args:
        query:         User's question.
        vector_store:  Connected VectorStore.
        top_k:         Number of chunks to retrieve.
        doc_id:        Optionally restrict retrieval to one document by ID.
        source_filter: Optionally restrict retrieval to one source file (legacy).
        university_id: Optionally restrict retrieval to one university.
        memory:        Optional conversation memory for multi-turn context.
        use_hybrid:    Whether to use multi-query hybrid search.

    Returns:
        (stream_generator, retrieved_chunks)
    """
    chunks = retrieve(
        query, vector_store, top_k=top_k, doc_id=doc_id,
        source_filter=source_filter, university_id=university_id,
        use_hybrid=use_hybrid,
    )
    stream = generate_answer(query, chunks, memory=memory)
    return stream, chunks
