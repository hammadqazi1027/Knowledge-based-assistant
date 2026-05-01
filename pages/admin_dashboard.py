"""
pages/admin_dashboard.py — Admin management dashboard.

Features:
  - User management (create/delete users, assign universities)
  - University management
  - Ticket tracking and analytics
  - System overview
  - Hardcoded super-admin support
"""

import time
import logging
from typing import Dict, Any, List, Optional

import streamlit as st

logger = logging.getLogger(__name__)


def _init_admin_state():
    """Initialize admin-specific session state."""
    defaults = {
        "admin_tab": "users",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_admin_dashboard():
    """Main entry point — called from app.py router."""
    _init_admin_state()

    is_hardcoded = st.session_state.get("is_hardcoded_admin", False)

    _render_sidebar(is_hardcoded)

    title_col, spacer_col, logout_col = st.columns([4, 2, 1])
    with title_col:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:1rem;">
            <span style="font-size:2.5rem; filter: drop-shadow(0 0 10px rgba(139,92,246,0.5));">📋</span>
            <div>
                <h1 style="
                    font-size: 1.75rem;
                    font-weight: 800;
                    font-family: 'Space Grotesk', sans-serif;
                    margin: 0;
                    background: linear-gradient(135deg, var(--accent), var(--accent-2));
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                ">Admin Dashboard</h1>
                <p style="font-size:0.85rem; color:var(--text-muted); margin:0;">Manage users, universities & analytics</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with spacer_col:
        badge = "🔐 Super Admin" if is_hardcoded else "🔐 Admin"
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:0.75rem; height:100%; padding-top:0.8rem;">
            <span style="font-size:0.75rem; color:var(--text-muted); background:rgba(139,92,246,0.1); padding:4px 10px; border-radius:6px;">
                {badge}
            </span>
            <span style="font-size:0.75rem; color:var(--text-muted);">
                <b style="color:var(--text-primary);">{st.session_state.username}</b>
            </span>
        </div>
        """, unsafe_allow_html=True)
    with logout_col:
        st.markdown("<div style='padding-top:0.45rem;'></div>", unsafe_allow_html=True)
        if st.button("🚪 Logout", key="header_logout_btn", use_container_width=True):
            from app import logout
            logout()

    tab_users, tab_universities, tab_tickets, tab_analytics = st.tabs([
        "👥 Users",
        "🏛️ Universities",
        "🎫 Tickets",
        "📊 Analytics",
    ])

    with tab_users:
        _render_users_tab()

    with tab_universities:
        _render_universities_tab()

    with tab_tickets:
        _render_tickets_tab()

    with tab_analytics:
        _render_analytics_tab()


def _render_sidebar(is_hardcoded: bool):
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
                filter: drop-shadow(0 0 15px rgba(139,92,246,0.5));
            ">🧠</div>
            <div style="
                font-size: 1.1rem;
                font-weight: 700;
                color: var(--text-primary);
                font-family: 'Space Grotesk', sans-serif;
            ">AI Knowledge Base</div>
            <div style="
                font-size: 0.75rem;
                color: var(--accent-light);
                margin-top: 4px;
                text-transform: uppercase;
                letter-spacing: 0.1em;
            ">Admin Panel</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="glass-card" style="margin-bottom: 1rem; text-align: center;">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.25rem;">Logged in as</div>
            <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">🔐 {st.session_state.username}</div>
            <div style="font-size:0.75rem; color:var(--accent-light); margin-top:4px;">{'Super Administrator' if is_hardcoded else 'Administrator'}</div>
        </div>
        """, unsafe_allow_html=True)

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


# ── Users Tab ─────────────────────────────────────────────────────────────────

def _render_users_tab():
    from auth import list_users, register_user, delete_user, get_user_count
    from university import list_universities

    st.markdown("""
    <div class="glass-card" style="margin-bottom: 1.5rem;">
        <p style="color:#8b84ff; font-size:0.9rem; margin:0;">
            👥 Manage user accounts. Create new accounts, assign universities, and remove existing ones.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    col1, col2, col3 = st.columns(3)
    col1.metric("🔐 Admins", get_user_count("admin"))
    col2.metric("👨‍🏫 Teachers", get_user_count("teacher"))
    col3.metric("👤 Users", get_user_count("user"))

    st.divider()

    # Create new user
    st.markdown('<div class="section-title">➕ Create Account</div>', unsafe_allow_html=True)
    universities = list_universities()
    uni_options = {"None": None}
    uni_options.update({f"{u['name']} ({u['code']})": u['id'] for u in universities})

    with st.form("create_user_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 2])
        new_username = c1.text_input("Username", placeholder="Enter username")
        new_password = c2.text_input("Password", type="password", placeholder="Min 4 chars")
        c3, c4 = st.columns([2, 2])
        new_role = c3.selectbox("Role", ["user", "teacher", "admin"])
        new_uni = c4.selectbox("University", options=list(uni_options.keys()))
        if st.form_submit_button("Create Account", use_container_width=True):
            if new_username and new_password:
                try:
                    university_id = uni_options.get(new_uni)
                    register_user(new_username.strip(), new_password, new_role, university_id=university_id)
                    st.success(f"✅ Created {new_role} account: {new_username}")
                    time.sleep(0.5)
                    st.rerun()
                except ValueError as e:
                    st.error(f"❌ {e}")
            else:
                st.error("Please fill in username and password.")

    st.divider()

    # List existing users
    st.markdown('<div class="section-title">📋 All Accounts</div>', unsafe_allow_html=True)
    users = list_users()

    for user in users:
        col_info, col_action = st.columns([4, 1])
        with col_info:
            role_icons = {"admin": "🔐", "teacher": "👨‍🏫", "user": "👤"}
            badge_classes = {"admin": "badge-admin", "teacher": "badge-teacher", "user": "badge-user"}
            role_badge = role_icons.get(user["role"], "👤")
            badge_class = badge_classes.get(user["role"], "badge-user")
            st.markdown(f"""
            <div class="list-item" style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight:500; color:#e8eaf0;">
                    {role_badge} {user['username']}
                </span>
                <span class="badge {badge_class}">{user['role']}</span>
            </div>
            """, unsafe_allow_html=True)
        with col_action:
            if user["username"] != st.session_state.username:
                if st.button("🗑️", key=f"del_user_{user['id']}"):
                    delete_user(user["id"])
                    st.rerun()
            else:
                st.caption("(you)")


# ── Universities Tab ───────────────────────────────────────────────────────────

def _render_universities_tab():
    from university import list_universities, add_university, delete_university

    st.markdown("""
    <div class="glass-card" style="margin-bottom: 1.5rem;">
        <p style="color:#8b84ff; font-size:0.9rem; margin:0;">
            🏛️ Manage universities for multi-tenant data isolation.
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("add_university_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        new_name = c1.text_input("University Name", placeholder="e.g., University of Technology")
        new_code = c2.text_input("Code", placeholder="e.g., UOT", max_chars=10)
        if st.form_submit_button("➕ Add University", use_container_width=True):
            if new_name and new_code:
                try:
                    add_university(new_name, new_code)
                    st.success(f"✅ Added {new_name}")
                    time.sleep(0.5)
                    st.rerun()
                except ValueError as e:
                    st.error(f"❌ {e}")
            else:
                st.error("Please fill in both name and code.")

    st.divider()

    universities = list_universities()
    st.markdown(f'<div class="section-title">📋 {len(universities)} Universities</div>', unsafe_allow_html=True)

    for uni in universities:
        col_info, col_action = st.columns([4, 1])
        with col_info:
            st.markdown(f"""
            <div class="list-item" style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight:600; color:#e8eaf0;">🏛️ {uni['name']}</span>
                <span class="badge badge-admin">{uni['code']}</span>
            </div>
            """, unsafe_allow_html=True)
        with col_action:
            if st.button("🗑️", key=f"del_uni_{uni['id']}"):
                delete_university(uni['id'])
                st.rerun()


# ── Tickets Tab ────────────────────────────────────────────────────────────────

def _render_tickets_tab():
    from tickets import list_tickets, update_ticket, get_ticket_stats, VALID_STATUSES
    from university import list_universities

    st.markdown("""
    <div class="glass-card" style="margin-bottom: 1.5rem;">
        <p style="color:#8b84ff; font-size:0.9rem; margin:0;">
            🎫 Track and manage user queries across all universities.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    universities = list_universities()
    uni_options = {"All Universities": None}
    uni_options.update({f"{u['name']}": u['id'] for u in universities})

    with col1:
        filter_uni = st.selectbox("University", options=list(uni_options.keys()), key="ticket_filter_uni")
    with col2:
        filter_status = st.selectbox("Status", options=["All"] + list(VALID_STATUSES), key="ticket_filter_status")
    with col3:
        limit = st.number_input("Limit", min_value=10, max_value=500, value=50, step=10)

    university_id = uni_options.get(filter_uni)
    status = None if filter_status == "All" else filter_status

    tickets = list_tickets(university_id=university_id, status=status, limit=limit)

    stats = get_ticket_stats(university_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎫 Total", stats["total"])
    c2.metric("📥 Open", stats["by_status"].get("open", 0))
    c3.metric("🔧 In Progress", stats["by_status"].get("in_progress", 0))
    c4.metric("✅ Resolved", stats["by_status"].get("resolved", 0))

    st.divider()

    if not tickets:
        st.info("No tickets found.")
        return

    for ticket in tickets:
        status_badge = {
            "open": "badge-open",
            "in_progress": "badge-in_progress",
            "resolved": "badge-resolved",
            "closed": "badge",
        }.get(ticket['status'], "badge")
        
        with st.expander(
            f"🎫 #{ticket['id']} - {ticket['query'][:60]}{'...' if len(ticket['query']) > 60 else ''}",
            expanded=False,
        ):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.markdown(f"**Query:** {ticket['query']}")
                if ticket.get('response'):
                    st.markdown(f"**Response:** {ticket['response'][:500]}{'...' if len(ticket['response']) > 500 else ''}")
                st.markdown(f"""
                <div style="margin-top:0.5rem;">
                    <span class="badge {status_badge}">{ticket['status']}</span>
                    <span style="font-size:0.8rem; color:var(--text-muted); margin-left:0.75rem;">
                        {ticket['department']} · {ticket['priority']} priority
                    </span>
                </div>
                """, unsafe_allow_html=True)
            with col_action:
                new_status = st.selectbox(
                    "Update Status",
                    options=list(VALID_STATUSES),
                    index=list(VALID_STATUSES).index(ticket['status']),
                    key=f"ticket_status_{ticket['id']}",
                )
                if st.button("Update", key=f"update_ticket_{ticket['id']}"):
                    update_ticket(ticket['id'], status=new_status)
                    st.success("✅ Updated!")
                    time.sleep(0.5)
                    st.rerun()


# ── Analytics Tab ──────────────────────────────────────────────────────────────

def _render_analytics_tab():
    from tickets import get_ticket_stats, list_tickets
    from university import list_universities
    from db import list_documents
    from auth import get_user_count

    st.markdown("""
    <div class="glass-card" style="margin-bottom: 1.5rem;">
        <p style="color:#8b84ff; font-size:0.9rem; margin:0;">
            📊 Analytics dashboard showing system-wide metrics.
        </p>
    </div>
    """, unsafe_allow_html=True)

    universities = list_universities()
    uni_options = {"All Universities": None}
    uni_options.update({f"{u['name']}": u['id'] for u in universities})

    selected_uni = st.selectbox("Filter by University", options=list(uni_options.keys()), key="analytics_uni_filter")
    university_id = uni_options.get(selected_uni)

    stats = get_ticket_stats(university_id)
    docs = list_documents(university_id)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📘 Documents", len(docs))
    col2.metric("👥 Users", get_user_count(university_id=university_id))
    col3.metric("🎫 Queries", stats["total"])
    col4.metric("✅ Resolved", stats["by_status"].get("resolved", 0))

    st.divider()

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown('<div class="section-title">📊 Queries by Status</div>', unsafe_allow_html=True)
        status_data = stats["by_status"]
        if any(status_data.values()):
            import plotly.express as px
            fig = px.pie(
                values=list(status_data.values()),
                names=list(status_data.keys()),
                color_discrete_map={
                    "open": "#ff6b6b",
                    "in_progress": "#ffd93d",
                    "resolved": "#48cfad",
                    "closed": "#5a6178",
                },
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#e8eaf0")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No query data yet.")

    with col_chart2:
        st.markdown('<div class="section-title">🏢 Queries by Department</div>', unsafe_allow_html=True)
        dept_data = stats["by_department"]
        if dept_data:
            import plotly.express as px
            fig = px.bar(
                x=[d["department"] for d in dept_data],
                y=[d["cnt"] for d in dept_data],
                labels={"x": "Department", "y": "Queries"},
                color=[d["cnt"] for d in dept_data],
                color_continuous_scale="Purples",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e8eaf0",
                xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No department data yet.")

    st.divider()
    st.markdown('<div class="section-title">📚 Document Statistics</div>', unsafe_allow_html=True)

    if docs:
        total_chunks = sum(d.get("chunk_count", 0) for d in docs)
        total_size = sum(d.get("file_size_kb", 0) for d in docs)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Chunks", total_chunks)
        col2.metric("Total Size", f"{total_size:.1f} KB")
        col3.metric("Avg Chunks/Doc", f"{total_chunks / len(docs):.1f}" if docs else 0)

        for doc in docs[:10]:
            st.markdown(f"""
            <div class="list-item">
                <span style="font-weight:500; color:#e8eaf0;">📄 {doc['doc_name']}</span>
                <span style="font-size:0.72rem; color:#5a6178; margin-left: 1rem;">
                    {doc['chunk_count']} chunks · {doc['file_size_kb']:.1f} KB
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No documents uploaded yet.")
