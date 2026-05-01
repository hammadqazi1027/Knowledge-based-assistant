"""
pages/user_dashboard.py — User-facing document search and Q&A dashboard.

Features:
  - Browse and search available documents by admin-assigned names
  - Select a specific document for querying
  - Chat interface with streaming LLM responses
  - Source citations under each answer
  - Answers scoped strictly to the selected document/university
  - Ticket tracking for user queries
  - Conversation memory for multi-turn chat
"""

import time
import logging
from typing import List, Dict, Any, Optional

import streamlit as st

logger = logging.getLogger(__name__)


# ── Session state ─────────────────────────────────────────────────────────────

def _init_user_state():
    """Initialize user-specific session state."""
    defaults = {
        "vs": None,
        "vs_connected": False,
        "vs_error": "",
        "user_selected_doc": None,
        "user_messages": [],
        "user_doc_search": "",
        "show_ticket_history": False,
        "conversation_memory": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Initialize conversation memory if not present
    if st.session_state.get("conversation_memory") is None:
        from rag_engine import ConversationMemory
        st.session_state.conversation_memory = ConversationMemory()


def _get_vector_store():
    """Connect to Zilliz Cloud once per session (with retry)."""
    if st.session_state.get("vs_connected"):
        return st.session_state.get("vs")

    from vector_store import VectorStore
    import time as _time

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        vs = VectorStore()
        try:
            vs.connect()
            st.session_state.vs = vs
            st.session_state.vs_connected = True
            st.session_state.vs_error = ""
            return vs
        except Exception as exc:
            if attempt < max_retries:
                _time.sleep(2)
                continue
            st.session_state.vs_error = str(exc)
            st.session_state.vs_connected = False
            return None


# ── Main render ───────────────────────────────────────────────────────────────

def render_user_dashboard():
    """Main entry point — called from app.py router."""
    _init_user_state()
    vs = _get_vector_store()

    _render_sidebar(vs)

    # ── Top bar: Title + Status + Logout ──
    sel = st.session_state.user_selected_doc
    title_col, spacer_col, logout_col = st.columns([4, 2, 1])
    with title_col:
        st.markdown("""
        <h1 style="
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #fff 20%, #6c63ff 60%, #48cfad 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
        ">💬 Ask Questions</h1>
        """, unsafe_allow_html=True)
    with spacer_col:
        db_icon = "🟢" if st.session_state.vs_connected else "🔴"
        doc_badge = f"📄 {sel['doc_name']}" if sel else "📚 All Docs"
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:0.75rem; padding-top:0.8rem;">
            <span style="font-size:0.78rem; color:#5a6178;">{db_icon} Zilliz</span>
            <span style="font-size:0.78rem; color:#5a6178;">
                👤 <b style="color:#e8eaf0;">{st.session_state.username}</b>
            </span>
        </div>
        """, unsafe_allow_html=True)
    with logout_col:
        st.markdown("<div style='padding-top:0.45rem;'></div>", unsafe_allow_html=True)
        if st.button("🚪 Logout", key="header_logout_btn", use_container_width=True):
            from app import logout
            logout()

    _render_main_area(vs)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(vs):
    import db

    with st.sidebar:
        # Header
        st.markdown("""
        <div style="
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            margin-bottom: 1rem;
        ">
            <div style="font-size:1.1rem; font-weight:700; color:#e8eaf0;">🧠 RAG Pipeline</div>
            <div style="font-size:0.75rem; color:#5a6178; margin-top:2px;">User Panel</div>
        </div>
        """, unsafe_allow_html=True)

        # User info
        st.markdown(f"""
        <div style="
            background: rgba(72,207,173,0.08);
            border: 1px solid rgba(72,207,173,0.15);
            border-radius: 10px;
            padding: 0.6rem 0.8rem;
            margin-bottom: 1rem;
        ">
            <div style="font-size:0.68rem; color:#5a6178; text-transform:uppercase; letter-spacing:0.08em;">Logged in as</div>
            <div style="font-size:0.95rem; font-weight:600; color:#e8eaf0;">👤 {st.session_state.username}</div>
            <div style="font-size:0.72rem; color:#48cfad; margin-top:2px;">User</div>
        </div>
        """, unsafe_allow_html=True)

        # Connection status
        if not st.session_state.vs_connected:
            st.markdown(
                '<div class="status-card err">'
                '<div class="status-label">Database</div>'
                '<div class="status-value">❌ Disconnected</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("🔄 Retry"):
                st.session_state.vs_connected = False
                st.session_state.vs = None
                st.rerun()
            st.divider()

        # ── Document Browser ──
        st.markdown("## 📚 Documents")

        search_query = st.text_input(
            "🔍 Search documents",
            value=st.session_state.get("user_doc_search", ""),
            key="doc_search_input",
            placeholder="Type to filter by name…",
        )
        st.session_state.user_doc_search = search_query

        university_id = st.session_state.get("university_id")
        
        # If user has no university_id, show all documents
        filter_by_university = university_id is not None
        
        if search_query.strip():
            docs = db.search_documents(search_query.strip(), university_id=university_id if filter_by_university else None)
        else:
            docs = db.list_documents(university_id=university_id if filter_by_university else None)

        if not docs:
            if search_query:
                st.caption("No documents match your search.")
            else:
                st.caption("No documents available for your university.")
            st.divider()
        else:
            all_selected = st.session_state.user_selected_doc is None
            if st.button(
                f"{'🔘' if all_selected else '⚪'} All Documents ({len(docs)})",
                key="select_all_docs",
                use_container_width=True,
            ):
                st.session_state.user_selected_doc = None
                st.session_state.user_messages = []
                if st.session_state.get("conversation_memory"):
                    st.session_state.conversation_memory.clear()
                st.rerun()

            st.divider()

            for doc in docs:
                is_selected = (
                    st.session_state.user_selected_doc is not None
                    and st.session_state.user_selected_doc.get("id") == doc["id"]
                )
                icon = "🔘" if is_selected else "⚪"

                if st.button(
                    f"{icon} {doc['doc_name']}",
                    key=f"select_doc_{doc['id']}",
                    use_container_width=True,
                    help=f"{doc['original_filename']} · {doc['chunk_count']} chunks · {doc['file_size_kb']} KB",
                ):
                    st.session_state.user_selected_doc = doc
                    st.session_state.user_messages = []
                    if st.session_state.get("conversation_memory"):
                        st.session_state.conversation_memory.clear()
                    st.rerun()

                st.caption(f"   {doc['chunk_count']} chunks · {doc['file_type']}")

        st.divider()

        # Selected doc indicator
        sel = st.session_state.user_selected_doc
        if sel:
            st.markdown(f"""
            <div style="
                background: rgba(108,99,255,0.08);
                border: 1px solid rgba(108,99,255,0.15);
                border-radius: 10px;
                padding: 0.6rem 0.8rem;
            ">
                <div style="font-size:0.68rem; color:#5a6178; text-transform:uppercase; letter-spacing:0.08em;">Querying</div>
                <div style="font-size:0.9rem; font-weight:600; color:#8b84ff;">📄 {sel['doc_name']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="
                background: rgba(72,207,173,0.06);
                border: 1px solid rgba(72,207,173,0.12);
                border-radius: 10px;
                padding: 0.6rem 0.8rem;
            ">
                <div style="font-size:0.68rem; color:#5a6178; text-transform:uppercase; letter-spacing:0.08em;">Querying</div>
                <div style="font-size:0.9rem; font-weight:600; color:#48cfad;">📚 All Documents</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        if st.session_state.user_messages:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.user_messages = []
                if st.session_state.get("conversation_memory"):
                    st.session_state.conversation_memory.clear()
                st.rerun()

        st.divider()

        if st.button("🎫 My Tickets", use_container_width=True):
            st.session_state.show_ticket_history = not st.session_state.get("show_ticket_history", False)

        if st.button("🚪 Logout", use_container_width=True):
            from app import logout
            logout()


# ── Ticket History ─────────────────────────────────────────────────────────────

def _render_ticket_history():
    from tickets import list_tickets
    
    st.markdown('<div class="section-title">🎫 Your Query History</div>', unsafe_allow_html=True)
    
    user_id = st.session_state.get("user_id")
    tickets = list_tickets(user_id=user_id, limit=20)
    
    if not tickets:
        st.info("You haven't made any queries yet.")
        return
    
    for ticket in tickets:
        status_badge = {
            "open": "badge-open",
            "in_progress": "badge-in_progress",
            "resolved": "badge-resolved",
            "closed": "badge",
        }.get(ticket['status'], "badge")
        
        with st.expander(
            f"🎫 #{ticket['id']} - {ticket['query'][:50]}{'...' if len(ticket['query']) > 50 else ''}",
            expanded=False,
        ):
            st.markdown(f"**Query:** {ticket['query']}")
            if ticket.get('response'):
                st.markdown(f"**Response:** {ticket['response'][:300]}{'...' if len(ticket['response']) > 300 else ''}")
            st.markdown(f'<span class="badge {status_badge}">{ticket["status"]}</span>', unsafe_allow_html=True)
            st.caption(
                f"Department: {ticket['department']} | "
                f"Priority: {ticket['priority']} | "
                f"Created: {ticket['created_at'][:10]}"
            )


# ── Main Area ─────────────────────────────────────────────────────────────────

def _render_main_area(vs):
    """Render the chat interface."""
    
    if st.session_state.get("show_ticket_history"):
        if st.button("← Back to Chat"):
            st.session_state.show_ticket_history = False
            st.rerun()
        _render_ticket_history()
        return

    sel = st.session_state.user_selected_doc
    if sel:
        doc_label = sel["doc_name"]
        doc_detail = f"{sel['original_filename']} · {sel['chunk_count']} chunks"
    else:
        doc_label = "All Documents"
        doc_detail = "Querying across all your university's documents"

    st.markdown(f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
    ">
        <span style="
            background: rgba(108,99,255,0.1);
            border: 1px solid rgba(108,99,255,0.2);
            border-radius: 8px;
            padding: 4px 12px;
            font-size: 0.82rem;
            font-weight: 600;
            color: #8b84ff;
        ">📄 {doc_label}</span>
        <span style="font-size:0.78rem; color:#5a6178;">{doc_detail}</span>
    </div>
    """, unsafe_allow_html=True)

    # Onboarding
    if not st.session_state.user_messages:
        import db
        docs = db.list_documents()
        if not st.session_state.vs_connected:
            st.warning("⚠️ Database not connected. Please wait or contact an admin.")
        elif not docs:
            st.info("📭 No documents available yet. Please ask an admin to upload some documents.")
        else:
            st.info(f"💡 **Ready!** Ask a question below — I'll answer using {'**' + doc_label + '**' if sel else 'all available documents'}.")

    # Render existing messages
    for msg in st.session_state.user_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                _render_sources(msg["sources"])

    # Chat input
    can_chat = st.session_state.vs_connected
    if query := st.chat_input(
        f"Ask about {doc_label}…" if can_chat else "Database not connected…",
        disabled=not can_chat,
    ):
        _handle_query(query, vs)


# ── Query handler ─────────────────────────────────────────────────────────────

def _handle_query(query: str, vs):
    """Process a user query and stream the answer."""
    import rag_engine
    import tickets
    import time as _time

    st.session_state.user_messages.append({"role": "user", "content": query, "sources": []})
    with st.chat_message("user"):
        st.markdown(query)

    sel = st.session_state.user_selected_doc
    doc_id = sel["id"] if sel else None
    university_id = st.session_state.get("university_id")
    user_id = st.session_state.get("user_id")

    # Only filter by university if user has one assigned
    filter_university_id = university_id if university_id is not None else None

    # Get conversation memory
    memory = st.session_state.get("conversation_memory")

    start_time = _time.time()

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        sources: List[Dict[str, Any]] = []

        with st.spinner("🔍 Searching documents…"):
            try:
                stream, sources = rag_engine.answer(
                    query, vs, doc_id=doc_id, university_id=filter_university_id,
                    memory=memory, use_hybrid=True,
                )
            except Exception as exc:
                err = f"❌ Retrieval error: {exc}"
                response_placeholder.markdown(err)
                st.session_state.user_messages.append({"role": "assistant", "content": err, "sources": []})
                return

        for token in stream:
            full_response += token
            response_placeholder.markdown(full_response + "▌")

        response_placeholder.markdown(full_response)

        if sources:
            _render_sources(sources)

    st.session_state.user_messages.append({
        "role": "assistant",
        "content": full_response,
        "sources": sources,
    })

    # Update conversation memory
    if memory:
        memory.add("user", query)
        memory.add("assistant", full_response)

    # Create ticket for this query
    try:
        classification = rag_engine.classify_query(query) if full_response else {"department": "general", "priority": "medium"}
        response_time_ms = int((_time.time() - start_time) * 1000)

        tickets.create_ticket(
            user_id=user_id,
            university_id=university_id,
            query=query,
            response=full_response,
            department=classification.get("department", "general"),
            priority=classification.get("priority", "medium"),
            doc_id=doc_id,
            chunks_used=len(sources),
            response_time_ms=response_time_ms,
        )
    except Exception as e:
        logger.warning("Failed to create ticket: %s", e)


# ── Source citation ───────────────────────────────────────────────────────────

def _render_sources(sources: List[Dict[str, Any]]):
    """Render expandable source citations."""
    with st.expander(f"📚 Sources ({len(sources)} chunks used)", expanded=False):
        for i, src in enumerate(sources, 1):
            page_info = f" · page {src['page']}" if src.get("page") else ""
            score_pct = int(src["score"] * 100)

            st.markdown(
                f"**[{i}]** `{src['source']}`{page_info} "
                f"— relevance **{score_pct}%**"
            )
            st.caption(src["text"][:300] + ("…" if len(src["text"]) > 300 else ""))
            if i < len(sources):
                st.divider()
