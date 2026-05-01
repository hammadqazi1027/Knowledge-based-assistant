"""
pages/login.py — Role-based login and user registration UI.

Features:
  - Admin / Teacher / User tab toggle
  - Login form with error handling
  - Hardcoded super-admin support (superadmin / admin12345)
  - Self-registration with university selection (User role only)
  - Back to landing navigation
"""

import streamlit as st
from auth import authenticate, register_user, HARDCODED_ADMIN
from university import list_universities


def render_login_page():
    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Home", key="login_back_btn"):
            st.session_state.page = "landing"
            st.rerun()

    # ── Header ──
    st.markdown("""
    <div style="text-align:center; padding: 1.5rem 0 2rem; position:relative; z-index:1;">
        <div style="
            font-size: 3.5rem;
            margin-bottom: 0.75rem;
            animation: float 4s ease-in-out infinite;
            filter: drop-shadow(0 0 20px rgba(139,92,246,0.4));
        ">🔐</div>
        <h1 style="
            font-size: 2.2rem;
            font-weight: 800;
            font-family: 'Space Grotesk', sans-serif;
            margin-bottom: 0.25rem;
        ">
            <span class="gradient-text">Welcome Back</span>
        </h1>
        <p style="color: var(--text-muted); font-size: 1rem; margin:0;">
            Sign in to access your dashboard
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, form_col, _ = st.columns([1, 1.4, 1])

    with form_col:
        # Map role to tab index
        role_tab_map = {"admin": 0, "teacher": 1, "user": 2}
        default_tab = role_tab_map.get(st.session_state.get("login_role_tab", "user"), 2)
        tabs = st.tabs(["🔐 Admin", "👨‍🏫 Teacher", "👤 User"])

        roles = ["admin", "teacher", "user"]
        for tab_idx, tab in enumerate(tabs):
            role = roles[tab_idx]
            with tab:
                _render_login_form(role)
                if role == "user":
                    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
                    _render_register_form()


def _render_login_form(role: str):
    """Render login form for a given role."""
    role_labels = {
        "admin": "Administrator",
        "teacher": "Teacher",
        "user": "User",
    }
    role_desc = {
        "admin": "Manage users, universities & system analytics",
        "teacher": "Upload & manage documents for your university",
        "user": "Ask questions & explore your university's knowledge base",
    }
    role_color = {"admin": "#8b5cf6", "teacher": "#f59e0b", "user": "#10b981"}
    role_label = role_labels.get(role, role.capitalize())
    color = role_color.get(role, "#8b5cf6")

    st.markdown(f"""
    <div class="glass-card" style="margin-bottom: 1.5rem; padding: 1.5rem; border-left: 3px solid {color};">
        <div style="
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.15em;
            margin-bottom: 0.25rem;
            font-weight: 700;
        ">Sign in as {role_label}</div>
        <div style="
            font-size: 1.1rem;
            color: var(--text-primary);
            font-weight: 600;
            margin-bottom: 0.25rem;
        ">{role_desc[role]}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.form(f"login_form_{role}", clear_on_submit=False):
        username = st.text_input(
            "Username",
            key=f"login_user_{role}",
            placeholder=f"Enter your {role} username",
        )
        password = st.text_input(
            "Password",
            type="password",
            key=f"login_pass_{role}",
            placeholder="Enter your password"
        )
        
        # Super-admin hint for admin tab
        if role == "admin":
            st.markdown("""
            <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:0.75rem; padding:0.5rem; background:rgba(139,92,246,0.05); border-radius:6px; border:1px solid rgba(139,92,246,0.1);">
                💡 <strong>Super Admin:</strong> superadmin / admin12345
            </div>
            """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button(f"Sign In →", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
                return

            user = authenticate(username.strip(), password)
            if user is None:
                st.error("Invalid username or password.")
                return

            # Hardcoded superadmin can access admin panel
            if user.get("is_hardcoded") and role == "admin":
                st.session_state.authenticated = True
                st.session_state.username = user["username"]
                st.session_state.role = user["role"]
                st.session_state.user_id = user["id"]
                st.session_state.university_id = user.get("university_id")
                st.session_state.is_hardcoded_admin = True
                st.session_state.page = role
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
                return

            if user["role"] != role:
                st.error(f"This account is not a {role} account. Please use the correct tab.")
                return

            st.session_state.authenticated = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.session_state.user_id = user["id"]
            st.session_state.university_id = user.get("university_id")
            st.session_state.is_hardcoded_admin = False
            st.session_state.page = role
            st.success(f"Welcome, {user['username']}!")
            st.rerun()


def _render_register_form():
    """Render self-registration form (User role only)."""
    universities = list_universities()

    if not universities:
        st.warning("No universities available. Please contact an administrator.")
        return

    with st.expander("✨ Create New Account", expanded=False):
        st.markdown("""
        <div style="margin-bottom: 1rem;">
            <p style="color: var(--text-muted); font-size: 0.9rem; margin: 0;">
                Register a new <strong style="color: var(--accent);">User</strong> account and select your university 
                to access its documents.
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("register_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_user = st.text_input("Username", key="reg_user", placeholder="Choose username")
            with col2:
                new_pass = st.text_input("Password", type="password", key="reg_pass", placeholder="Min 4 chars")
            
            new_pass2 = st.text_input("Confirm Password", type="password", key="reg_pass2", placeholder="Re-enter password")
            
            uni_options = {f"{u['name']} ({u['code']})": u['id'] for u in universities}
            selected_uni = st.selectbox(
                "🏛️ Select Your University",
                options=list(uni_options.keys()),
                key="reg_university",
            )
            
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            reg_submitted = st.form_submit_button("Create Account →", use_container_width=True)

            if reg_submitted:
                if not new_user or not new_pass:
                    st.error("Please fill in all fields.")
                    return
                if new_pass != new_pass2:
                    st.error("Passwords do not match.")
                    return
                try:
                    university_id = uni_options.get(selected_uni)
                    register_user(new_user.strip(), new_pass, role="user", university_id=university_id)
                    st.success(f"Account created! You can now sign in as '{new_user.strip()}'.")
                except ValueError as e:
                    st.error(f"{e}")
