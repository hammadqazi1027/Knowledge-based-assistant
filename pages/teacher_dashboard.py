"""
pages/teacher_dashboard.py — Teacher document management dashboard.

Features:
  - Upload documents for the teacher's assigned university
  - Automatic chunking + embedding + vector storage
  - View and delete documents belonging to the teacher's university
  - Database connection status
"""

import time
import logging
from typing import Dict, Any, List, Optional

import streamlit as st

logger = logging.getLogger(__name__)


def _get_vector_store():
    """Connect to Zilliz Cloud once per session (with retry for transient gRPC issues)."""
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


def _init_teacher_state():
    """Initialize teacher-specific session state."""
    defaults = {
        "vs": None,
        "vs_connected": False,
        "vs_error": "",
        "teacher_tab": "upload",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_teacher_dashboard():
    """Main entry point — called from app.py router."""
    _init_teacher_state()
    vs = _get_vector_store()

    # Get teacher's university info
    university_id = st.session_state.get("university_id")
    university_name = "Unknown University"
    if university_id:
        from university import get_university
        uni = get_university(university_id)
        if uni:
            university_name = uni["name"]

    _render_sidebar(vs, university_name)

    title_col, spacer_col, logout_col = st.columns([4, 2, 1])
    with title_col:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:1rem;">
            <span style="font-size:2.5rem; filter: drop-shadow(0 0 10px rgba(245,158,11,0.5));">👨‍🏫</span>
            <div>
                <h1 style="
                    font-size: 1.75rem;
                    font-weight: 800;
                    font-family: 'Space Grotesk', sans-serif;
                    margin: 0;
                    background: linear-gradient(135deg, #f59e0b, #fbbf24);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                ">Teacher Dashboard</h1>
                <p style="font-size:0.85rem; color:var(--text-muted); margin:0;">Upload and manage documents for your university</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with spacer_col:
        db_icon = "🟢" if st.session_state.vs_connected else "🔴"
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:0.75rem; height:100%; padding-top:0.8rem;">
            <span style="font-size:0.75rem; color:var(--text-muted); background:rgba(245,158,11,0.1); padding:4px 10px; border-radius:6px;">
                {db_icon} Vector DB
            </span>
            <span style="font-size:0.75rem; color:var(--text-muted);">
                🔐 <b style="color:var(--text-primary);">{st.session_state.username}</b>
            </span>
        </div>
        """, unsafe_allow_html=True)
    with logout_col:
        st.markdown("<div style='padding-top:0.45rem;'></div>", unsafe_allow_html=True)
        if st.button("🚪 Logout", key="header_logout_btn", use_container_width=True):
            from app import logout
            logout()

    # University banner
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(245,158,11,0.08), rgba(245,158,11,0.03));
        border: 1px solid rgba(245,158,11,0.15);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.5rem;
    ">
        <div style="display:flex; align-items:center; gap:0.75rem;">
            <span style="font-size:1.5rem;">🏛️</span>
            <div>
                <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.1em;">Your University</div>
                <div style="font-size:1.1rem; font-weight:600; color:var(--text-primary);">{university_name}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if university_id is None:
        st.error("⚠️ You are not assigned to any university. Please contact an administrator.")
        return

    tab_upload, tab_manage = st.tabs([
        "📂 Upload Documents",
        "🗂️ Manage Documents",
    ])

    with tab_upload:
        _render_upload_tab(vs, university_id)

    with tab_manage:
        _render_manage_tab(vs, university_id)


def _render_sidebar(vs, university_name: str):
    with st.sidebar:
        st.markdown("""
        <div style="
            padding: 1rem 0;
            margin-bottom: 1rem;
            text-align: center;
        ">
            <div style="
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                filter: drop-shadow(0 0 15px rgba(245,158,11,0.5));
            ">🧠</div>
            <div style="
                font-size: 1.1rem;
                font-weight: 700;
                color: var(--text-primary);
                font-family: 'Space Grotesk', sans-serif;
            ">AI Knowledge Base</div>
            <div style="
                font-size: 0.75rem;
                color: #fbbf24;
                margin-top: 4px;
                text-transform: uppercase;
                letter-spacing: 0.1em;
            ">Teacher Panel</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="glass-card" style="margin-bottom: 1rem; text-align: center;">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.25rem;">Logged in as</div>
            <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">👨‍🏫 {st.session_state.username}</div>
            <div style="font-size:0.75rem; color:#fbbf24; margin-top:4px;">Teacher · {university_name}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("## ⚡ System Status")

        if st.session_state.vs_connected:
            st.markdown("""
            <div class="status-card ok">
                <div class="status-label">Vector Database</div>
                <div class="status-value">✅ Connected</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-card err">
                <div class="status-label">Vector Database</div>
                <div class="status-value">❌ Disconnected</div>
            </div>
            """, unsafe_allow_html=True)
            if st.session_state.vs_error:
                with st.expander("Error details"):
                    st.code(st.session_state.vs_error)
            if st.button("🔄 Retry Connection"):
                st.session_state.vs_connected = False
                st.session_state.vs = None
                st.rerun()

        st.markdown("## 🤖 AI Engine")
        import config as cfg
        if cfg.LLM_AVAILABLE:
            st.markdown("""
            <div class="status-card ok">
                <div class="status-label">Groq LLM</div>
                <div class="status-value">✅ Active</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-card warn">
                <div class="status-label">LLM</div>
                <div class="status-value">⚠️ Demo Mode</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            from app import logout
            logout()


# ── Upload Tab ────────────────────────────────────────────────────────────────

def _render_upload_tab(vs, university_id: int):
    if not st.session_state.vs_connected:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding: 3rem;">
            <div style="font-size:3rem; margin-bottom:1rem;">⚠️</div>
            <div style="color:var(--danger); font-weight:600;">Database Not Connected</div>
            <div style="color:var(--text-muted); font-size:0.9rem;">Cannot upload documents without database connection.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("""
    <div class="glass-card" style="margin-bottom: 1.5rem;">
        <div style="display:flex; align-items:center; gap:1rem;">
            <span style="font-size:2rem;">📤</span>
            <div>
                <div style="font-weight:600; color:var(--text-primary); font-size:1.1rem;">Upload Documents</div>
                <div style="color:var(--text-muted); font-size:0.85rem;">PDF, TXT, or DOCX files • Automatic chunking & embedding</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        label="Drop files here",
        type=["pdf", "txt", "docx"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="teacher_file_uploader",
    )

    if not uploaded_files:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding: 3rem; border: 2px dashed var(--border-hover);">
            <div style="font-size:3rem; margin-bottom:1rem; opacity:0.5;">📁</div>
            <div style="color:var(--text-muted); font-size:1rem;">Drag & drop files or click to browse</div>
            <div style="color:var(--text-muted); font-size:0.85rem; margin-top:0.5rem;">PDF, TXT, DOCX supported</div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("""
    <div style="
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
    ">📝 Document Names</div>
    """, unsafe_allow_html=True)

    custom_names = {}
    for uf in uploaded_files:
        default_name = uf.name.rsplit(".", 1)[0]
        size_kb = round(len(uf.getvalue()) / 1024, 1)
        custom_names[uf.name] = st.text_input(
            f"📄 {uf.name} ({size_kb} KB)",
            value=default_name,
            key=f"teacher_custom_name_{uf.name}",
            placeholder="Enter a display name for this document",
        )

    st.divider()

    if st.button("⚡ Process & Upload to Database", use_container_width=True, key="teacher_process_btn"):
        _process_and_upload(uploaded_files, custom_names, vs, university_id)


def _process_and_upload(uploaded_files, custom_names, vs, university_id):
    """Process each file: chunk → embed → store in Zilliz + SQLite."""
    import rag_engine
    from document_processor import chunk_document
    import db

    success_count = 0
    progress_bar = st.progress(0, text="Starting...")

    for idx, uf in enumerate(uploaded_files):
        filename = uf.name
        doc_name = custom_names.get(filename, filename).strip() or filename
        progress = (idx) / len(uploaded_files)
        progress_bar.progress(progress, text=f"Processing {filename}...")

        uf.seek(0)
        file_bytes = uf.read()

        if not file_bytes:
            st.error(f"❌ '{filename}' appears to be empty.")
            continue

        file_size_kb = round(len(file_bytes) / 1024, 1)
        file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        status_container = st.container()
        with status_container:
            st.write(f"**📄 {doc_name}** (`{filename}`, {file_size_kb} KB)")

            # Step 1: Chunk
            with st.spinner("Chunking document…"):
                try:
                    chunks = chunk_document(file_bytes, filename)
                    st.write(f"  ✅ Created **{len(chunks)} chunks**")
                except Exception as exc:
                    st.error(f"  ❌ Chunking failed: {exc}")
                    continue

            # Step 2: Embed
            with st.spinner(f"Embedding {len(chunks)} chunks…"):
                try:
                    texts = [c["text"] for c in chunks]
                    embeddings = rag_engine.embed_texts(texts)
                    st.write(f"  ✅ Embedded **{len(embeddings)} vectors** (dim={len(embeddings[0])})")
                except Exception as exc:
                    st.error(f"  ❌ Embedding failed: {exc}")
                    continue

            # Step 3: Register in SQLite metadata
            try:
                doc_id = db.add_document(
                    doc_name=doc_name,
                    original_filename=filename,
                    uploaded_by=st.session_state.username,
                    university_id=university_id,
                    chunk_count=len(chunks),
                    file_size_kb=file_size_kb,
                    file_type=f".{file_type}",
                )
                st.write(f"  ✅ Registered as doc_id=**{doc_id}**")
            except Exception as exc:
                st.error(f"  ❌ Metadata save failed: {exc}")
                continue

            # Step 4: Insert into Zilliz with doc_id and university_id
            with st.spinner("Uploading to vector database…"):
                try:
                    inserted = vs.insert_chunks(chunks, embeddings, doc_id=doc_id, university_id=university_id)
                    st.write(f"  ✅ Stored **{inserted} vectors** in Zilliz Cloud")
                    db.update_document(doc_id, chunk_count=inserted)
                except Exception as exc:
                    st.error(f"  ❌ Vector insert failed: {exc}")
                    db.delete_document(doc_id)
                    continue

            success_count += 1

    progress_bar.progress(1.0, text="Done!")

    if success_count > 0:
        st.success(f"✅ **{success_count}/{len(uploaded_files)}** document(s) uploaded successfully!")
        time.sleep(1.5)
        st.rerun()


# ── Manage Tab ────────────────────────────────────────────────────────────────

def _render_manage_tab(vs, university_id: int):
    import db

    docs = db.list_documents(university_id=university_id)

    if not docs:
        st.info("📭 No documents uploaded yet for your university. Go to the **Upload** tab to add some!")
        return

    st.markdown(f'<div class="section-title">{len(docs)} Document(s)</div>', unsafe_allow_html=True)

    for doc in docs:
        with st.container():
            st.markdown(f"""
            <div class="list-item">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                    <div>
                        <span style="font-size:1.05rem; font-weight:600; color:#e8eaf0;">
                            📄 {doc['doc_name']}
                        </span>
                        <span style="font-size:0.72rem; color:#5a6178; margin-left:0.75rem;">
                            {doc['original_filename']}
                        </span>
                    </div>
                    <div style="display:flex; gap:1rem; margin-top:0.25rem;">
                        <span style="font-size:0.75rem; color:#48cfad;">
                            📊 {doc['chunk_count']} chunks
                        </span>
                        <span style="font-size:0.75rem; color:#5a6178;">
                            💾 {doc['file_size_kb']} KB
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_rename, col_delete = st.columns([1, 1])

            # Rename
            with col_rename:
                with st.popover("✏️ Rename"):
                    new_name = st.text_input(
                        "New name",
                        value=doc["doc_name"],
                        key=f"teacher_rename_{doc['id']}",
                    )
                    if st.button("Save", key=f"teacher_save_rename_{doc['id']}"):
                        if new_name.strip():
                            db.update_document(doc["id"], doc_name=new_name.strip())
                            st.success("✅ Renamed!")
                            time.sleep(0.5)
                            st.rerun()

            # Delete
            with col_delete:
                with st.popover("🗑️ Delete"):
                    st.warning(f"Delete **{doc['doc_name']}**? This removes all embeddings and cannot be undone.")
                    if st.button("⚠️ Confirm Delete", key=f"teacher_confirm_del_{doc['id']}"):
                        _delete_document(doc, vs)


def _delete_document(doc: Dict[str, Any], vs):
    """Delete a document from both Zilliz and SQLite."""
    import db

    with st.spinner("Deleting…"):
        if vs and st.session_state.vs_connected:
            vs.delete_by_doc_id(doc["id"])
        db.delete_document(doc["id"])

    st.success(f"✅ Deleted **{doc['doc_name']}**")
    time.sleep(1)
    st.rerun()
