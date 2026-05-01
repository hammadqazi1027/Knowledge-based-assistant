"""
app.py — Landing page + session router for the RAG Pipeline.

This is the main entry point. It:
  1. Initialises databases (SQLite for users + docs)
  2. Routes authenticated users to their dashboards
  3. Shows a landing page with login CTAs for unauthenticated visitors

Run with:
  streamlit run app.py
"""

# ── Suppress warnings BEFORE heavy imports ────────────────────────────────────
import os
import warnings
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
warnings.filterwarnings("ignore", message=".*torchvision.*")
warnings.filterwarnings("ignore", message=".*position_ids.*")
# ─────────────────────────────────────────────────────────────────────────────

import logging
import streamlit as st

# ── Page config — MUST be first Streamlit call ────────────────────────────────
# Sidebar should be expanded when authenticated (dashboards), collapsed on landing
_sidebar_state = "expanded" if st.session_state.get("authenticated") else "collapsed"
st.set_page_config(
    page_title="RAG Pipeline",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state=_sidebar_state,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

# ── Init databases on first load ──────────────────────────────────────────────
from auth import init_auth_db, seed_default_admin
from db import init_docs_db
from university import init_universities_db, seed_default_universities
from tickets import init_tickets_db

init_auth_db()
init_docs_db()
init_universities_db()
init_tickets_db()
seed_default_universities()
seed_default_admin()


# ── Global CSS ────────────────────────────────────────────────────────────────
def inject_global_css():
    st.markdown("""
    <style>
    /* ── Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap');

    /* ── Animations ── */
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes glow {
        0%, 100% { box-shadow: 0 0 20px rgba(108,99,255,0.3); }
        50% { box-shadow: 0 0 40px rgba(108,99,255,0.5); }
    }

    /* ── Root tokens ── */
    :root {
        --bg-primary:    #050508;
        --bg-secondary:  #0c0d12;
        --bg-tertiary:   #12141c;
        --bg-card:       rgba(255,255,255,0.02);
        --bg-card-hover: rgba(255,255,255,0.05);
        --accent:        #8b5cf6;
        --accent-light:  #a78bfa;
        --accent-2:      #06b6d4;
        --accent-3:      #ec4899;
        --accent-4:      #10b981;
        --danger:        #ef4444;
        --warn:          #f59e0b;
        --success:       #10b981;
        --text-primary:  #f1f5f9;
        --text-secondary:#94a3b8;
        --text-muted:    #64748b;
        --border:        rgba(255,255,255,0.05);
        --border-hover:  rgba(139,92,246,0.3);
        --radius:        16px;
        --radius-sm:     10px;
        --glass-bg:      rgba(255,255,255,0.02);
        --glass-border:  rgba(255,255,255,0.06);
    }

    /* ── Global ── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text-primary);
        scroll-behavior: smooth;
    }
    .stApp {
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0a0a12 50%, var(--bg-primary) 100%);
        background-attachment: fixed;
    }

    /* ── Animated background pattern ── */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: 
            radial-gradient(ellipse at 20% 20%, rgba(139,92,246,0.08) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 80%, rgba(6,182,212,0.06) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(236,72,153,0.04) 0%, transparent 60%);
        pointer-events: none;
        z-index: 0;
    }

    /* Hide footer and minimize header */
    footer { visibility: hidden; }
    header { visibility: hidden; height: 0 !important; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%) !important;
        border-right: 1px solid var(--border);
        box-shadow: 4px 0 30px rgba(0,0,0,0.3);
    }
    [data-testid="stSidebar"] > div {
        padding-top: 1rem;
    }
    [data-testid="stSidebar"] .stMarkdown h2 {
        color: var(--accent-light);
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
        font-family: 'Space Grotesk', sans-serif;
    }

    /* ── Sidebar toggle ── */
    [data-testid="collapsedControl"] {
        position: fixed !important;
        top: 1rem !important;
        left: 1rem !important;
        background: linear-gradient(135deg, rgba(139,92,246,0.2), rgba(6,182,212,0.1)) !important;
        border: 1px solid rgba(139,92,246,0.3) !important;
        border-radius: 12px !important;
        padding: 10px 14px !important;
        backdrop-filter: blur(20px) !important;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
        z-index: 999999 !important;
    }
    [data-testid="collapsedControl"]:hover {
        background: linear-gradient(135deg, rgba(139,92,246,0.3), rgba(6,182,212,0.2)) !important;
        transform: scale(1.05);
        box-shadow: 0 0 30px rgba(139,92,246,0.3);
    }
    [data-testid="collapsedControl"] svg {
        fill: var(--accent-light) !important;
        width: 22px !important;
        height: 22px !important;
    }

    /* ── Main content area ── */
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, var(--accent), #7c3aed) !important;
        color: #fff !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        padding: 0.65rem 1.75rem !important;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
        letter-spacing: 0.02em;
        box-shadow: 0 4px 15px rgba(139,92,246,0.25);
        position: relative;
        overflow: hidden;
    }
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        transition: left 0.5s;
    }
    .stButton > button:hover::before {
        left: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(139,92,246,0.4);
    }
    .stButton > button:active { 
        transform: translateY(-1px); 
    }

    /* ── Secondary buttons ── */
    .stButton > button[kind="secondary"] {
        background: transparent !important;
        border: 1px solid var(--border-hover) !important;
        color: var(--text-primary) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: rgba(139,92,246,0.1) !important;
        border-color: var(--accent) !important;
    }

    /* ── Cards ── */
    .glass-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
        border: 1px solid var(--glass-border);
        border-radius: var(--radius);
        padding: 1.5rem;
        backdrop-filter: blur(20px);
        transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
        position: relative;
        overflow: hidden;
    }
    .glass-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(139,92,246,0.5), transparent);
    }
    .glass-card:hover {
        border-color: var(--border-hover);
        transform: translateY(-4px);
        box-shadow: 0 20px 50px rgba(0,0,0,0.3), 0 0 30px rgba(139,92,246,0.1);
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)) !important;
        border: 2px dashed rgba(139,92,246,0.3) !important;
        border-radius: var(--radius) !important;
        transition: all 0.3s ease;
        padding: 1.5rem !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--accent) !important;
        background: rgba(139,92,246,0.05) !important;
        box-shadow: 0 0 30px rgba(139,92,246,0.1);
    }
    [data-testid="stFileUploader"] section {
        gap: 0.5rem;
    }

    /* ── Chat messages ── */
    [data-testid="stChatMessage"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        margin-bottom: 1rem;
        padding: 1rem 1.25rem !important;
        transition: all 0.3s ease;
        animation: fadeInUp 0.4s ease-out;
    }
    [data-testid="stChatMessage"]:hover { 
        background: rgba(255,255,255,0.05) !important; 
        border-color: var(--border-hover);
    }
    [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"] {
        background: linear-gradient(135deg, var(--accent-2), var(--accent)) !important;
    }
    [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
        background: linear-gradient(135deg, var(--accent), var(--accent-3)) !important;
    }

    /* ── Chat input ── */
    [data-testid="stChatInput"] {
        border-radius: var(--radius) !important;
        overflow: hidden;
    }
    [data-testid="stChatInput"] textarea {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        padding: 1rem !important;
        transition: all 0.3s ease;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(139,92,246,0.15), 0 0 30px rgba(139,92,246,0.1) !important;
    }

    /* ── Tabs ── */
    .stTabs {
        width: 100%;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
        border-radius: var(--radius-sm);
        padding: 6px;
        gap: 6px;
        border: 1px solid var(--border);
        height: auto !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-family: 'Inter', sans-serif !important;
        padding: 10px 20px !important;
        color: var(--text-secondary) !important;
        transition: all 0.3s ease !important;
        height: auto !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(139,92,246,0.1) !important;
        color: var(--text-primary) !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--accent), #7c3aed) !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(139,92,246,0.3) !important;
    }

    /* ── Text input ── */
    .stTextInput, .stTextInput div {
        width: 100% !important;
    }
    .stTextInput input {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        padding: 0.75rem 1rem !important;
        transition: all 0.3s ease !important;
    }
    .stTextInput input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(139,92,246,0.15) !important;
    }
    .stTextInput input::placeholder {
        color: var(--text-muted) !important;
    }

    /* ── Selectbox ── */
    .stSelectbox [data-baseweb="select"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
    }
    .stSelectbox [data-baseweb="select"]:hover {
        border-color: var(--border-hover) !important;
    }

    /* ── Number input ── */
    .stNumberInput input {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.25rem;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    [data-testid="stMetric"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--accent), var(--accent-2), var(--accent-3));
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    [data-testid="stMetric"]:hover::before {
        opacity: 1;
    }
    [data-testid="stMetric"]:hover {
        border-color: var(--border-hover);
        transform: translateY(-2px);
    }
    [data-testid="stMetric"] label {
        color: var(--text-secondary) !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        font-family: 'Space Grotesk', sans-serif !important;
    }

    /* ── Status cards ── */
    .status-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-sm);
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
        position: relative;
    }
    .status-card.ok   { 
        border-left: 3px solid var(--success);
        background: linear-gradient(135deg, rgba(16,185,129,0.05), transparent);
    }
    .status-card.warn { 
        border-left: 3px solid var(--warn);
        background: linear-gradient(135deg, rgba(245,158,11,0.05), transparent);
    }
    .status-card.err  { 
        border-left: 3px solid var(--danger);
        background: linear-gradient(135deg, rgba(239,68,68,0.05), transparent);
    }
    .status-label { 
        font-size: 0.7rem; 
        text-transform: uppercase; 
        color: var(--text-muted); 
        letter-spacing: 0.1em;
        font-weight: 600;
    }
    .status-value { 
        font-size: 1rem; 
        font-weight: 600; 
        color: var(--text-primary); 
    }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    [data-testid="stExpander"]:hover {
        border-color: var(--border-hover) !important;
    }
    [data-testid="stExpander"] summary {
        padding: 1rem 1.25rem !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: rgba(139,92,246,0.05);
    }

    /* ── Popover ── */
    [data-testid="stPopover"] > div {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        box-shadow: 0 20px 50px rgba(0,0,0,0.4) !important;
    }

    /* ── Form ── */
    .stForm {
        background: linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem;
        backdrop-filter: blur(10px);
    }

    /* ── Dataframe ── */
    .stDataFrame {
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        overflow: hidden;
    }

    /* ── Divider ── */
    hr { 
        border-color: var(--border) !important; 
        margin: 1.5rem 0 !important; 
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { 
        background: linear-gradient(180deg, var(--accent), var(--accent-2));
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover { 
        background: linear-gradient(180deg, var(--accent-light), var(--accent));
    }

    /* ── Toast/Alert ── */
    .stToast, .stAlert {
        border-radius: var(--radius-sm) !important;
        backdrop-filter: blur(20px);
    }
    .stSuccess {
        background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(16,185,129,0.05)) !important;
        border: 1px solid rgba(16,185,129,0.3) !important;
    }
    .stError {
        background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(239,68,68,0.05)) !important;
        border: 1px solid rgba(239,68,68,0.3) !important;
    }
    .stWarning {
        background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(245,158,11,0.05)) !important;
        border: 1px solid rgba(245,158,11,0.3) !important;
    }
    .stInfo {
        background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(139,92,246,0.05)) !important;
        border: 1px solid rgba(139,92,246,0.3) !important;
    }

    /* ── Plotly charts ── */
    .plotly-graph-div {
        background: transparent !important;
    }

    /* ── Info text ── */
    .stMarkdown p {
        color: var(--text-secondary);
        line-height: 1.7;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: var(--text-primary);
        font-family: 'Space Grotesk', sans-serif;
    }

    /* ── Custom classes ── */
    .feature-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        animation: float 3s ease-in-out infinite;
    }
    .glow-text {
        text-shadow: 0 0 20px currentColor;
    }
    .gradient-text {
        background: linear-gradient(135deg, var(--accent), var(--accent-2), var(--accent-3));
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: gradientShift 3s ease infinite;
    }
    .card-hover-effect {
        transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
    }
    .card-hover-effect:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 25px 60px rgba(0,0,0,0.4), 0 0 40px rgba(139,92,246,0.15);
    }

    /* ── Loading spinner ── */
    .stSpinner > div {
        border-color: var(--accent) transparent transparent transparent !important;
    }

    /* ── Progress bar ── */
    .stProgress > div > div {
        background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
        border-radius: 10px !important;
    }
    .stProgress > div {
        background: rgba(255,255,255,0.05) !important;
        border-radius: 10px !important;
    }

    /* ── Badges / Pills ── */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .badge-admin { background: rgba(139,92,246,0.15); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3); }
    .badge-teacher { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
    .badge-user { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
    .badge-open { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
    .badge-resolved { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
    .badge-in_progress { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }

    /* ── Particle canvas for landing ── */
    #particles-canvas {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 0;
    }

    /* ── Section titles ── */
    .section-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 1.5rem;
        position: relative;
        display: inline-block;
    }
    .section-title::after {
        content: '';
        position: absolute;
        bottom: -6px;
        left: 0;
        width: 40px;
        height: 3px;
        background: linear-gradient(90deg, var(--accent), var(--accent-2));
        border-radius: 2px;
    }

    /* ── Toast animation ── */
    @keyframes slideInRight {
        from { opacity: 0; transform: translateX(30px); }
        to { opacity: 1; transform: translateX(0); }
    }
    .toast-enter {
        animation: slideInRight 0.4s ease-out;
    }

    /* ── Avatar circles ── */
    .avatar-circle {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1rem;
        color: white;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        box-shadow: 0 0 15px rgba(139,92,246,0.3);
    }

    /* ── List items ── */
    .list-item {
        background: linear-gradient(135deg, rgba(255,255,255,0.025), rgba(255,255,255,0.01));
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        transition: all 0.3s ease;
    }
    .list-item:hover {
        border-color: var(--border-hover);
        background: rgba(255,255,255,0.04);
        transform: translateX(4px);
    }

    /* ── Tooltip ── */
    .tooltip {
        position: relative;
    }
    .tooltip::after {
        content: attr(data-tooltip);
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(-6px);
        background: var(--bg-secondary);
        color: var(--text-primary);
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 0.75rem;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: all 0.2s ease;
        border: 1px solid var(--border);
    }
    .tooltip:hover::after {
        opacity: 1;
        transform: translateX(-50%) translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
def init_session_state():
    defaults = {
        "authenticated": False,
        "username": "",
        "role": "",
        "user_id": None,
        "university_id": None,
        "login_role_tab": "user",
        "page": "landing",
        "is_hardcoded_admin": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Logout helper ─────────────────────────────────────────────────────────────
def logout():
    for key in ["authenticated", "username", "role", "user_id", "university_id", "is_hardcoded_admin"]:
        st.session_state[key] = "" if isinstance(st.session_state.get(key), str) else None
    st.session_state["authenticated"] = False
    st.session_state["page"] = "landing"
    # Clear any dashboard-specific state
    for key in list(st.session_state.keys()):
        if key.startswith(("admin_", "user_", "teacher_", "vs")) or key == "conversation_memory":
            del st.session_state[key]
    st.rerun()


# ── Landing page ──────────────────────────────────────────────────────────────
def render_landing():
    # ── Particle Background + Hero Section ──
    st.markdown("""
    <div style="position:relative; text-align:center; padding: 3rem 1rem 2rem; overflow:hidden;">
        <!-- Animated gradient orbs -->
        <div style="position:absolute; top:-100px; left:-100px; width:400px; height:400px; background:radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%); border-radius:50%; animation: float 8s ease-in-out infinite; z-index:0;"></div>
        <div style="position:absolute; bottom:-50px; right:-50px; width:300px; height:300px; background:radial-gradient(circle, rgba(6,182,212,0.12) 0%, transparent 70%); border-radius:50%; animation: float 10s ease-in-out infinite reverse; z-index:0;"></div>
        <div style="position:absolute; top:50%; left:50%; width:500px; height:500px; transform:translate(-50%,-50%); background:radial-gradient(circle, rgba(236,72,153,0.06) 0%, transparent 60%); border-radius:50%; z-index:0;"></div>
        
        <div style="position:relative; z-index:1;">
            <div style="font-size: 5rem; margin-bottom: 1rem; animation: float 4s ease-in-out infinite; filter: drop-shadow(0 0 30px rgba(139,92,246,0.4));">🧠</div>
            
            <h1 style="
                font-size: 3.8rem;
                font-weight: 900;
                font-family: 'Space Grotesk', sans-serif;
                margin-bottom: 0.5rem;
                line-height: 1.1;
                color: #fff;
                letter-spacing: -0.02em;
            ">
                <span class="gradient-text">AI Knowledge</span><br>Assistant
            </h1>
            
            <h2 style="
                font-size: 1.4rem;
                font-weight: 400;
                color: #94a3b8;
                margin-bottom: 1.5rem;
                letter-spacing: 0.05em;
            ">Organizational Intelligence Powered by RAG</h2>
            
            <p style="
                color: #64748b;
                font-size: 1.15rem;
                max-width: 650px;
                margin: 0 auto 3rem;
                line-height: 1.8;
            ">
                Upload your organizational documents and get instant, accurate answers 
                to any question. Powered by advanced AI with strict document-grounded responses.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Stats Bar ──
    st.markdown("""
    <div style="
        display: flex;
        justify-content: center;
        gap: 2rem;
        margin-bottom: 3rem;
        flex-wrap: wrap;
    ">
        <div class="glass-card" style="text-align:center; padding: 1.25rem 2rem; min-width: 140px;">
            <div style="font-size:2.2rem; font-weight:800; color:#8b5cf6; font-family:'Space Grotesk',sans-serif; line-height:1;">100%</div>
            <div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.5rem;">Document Grounded</div>
        </div>
        <div class="glass-card" style="text-align:center; padding: 1.25rem 2rem; min-width: 140px;">
            <div style="font-size:2.2rem; font-weight:800; color:#06b6d4; font-family:'Space Grotesk',sans-serif; line-height:1;">&lt;1s</div>
            <div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.5rem;">Response Time</div>
        </div>
        <div class="glass-card" style="text-align:center; padding: 1.25rem 2rem; min-width: 140px;">
            <div style="font-size:2.2rem; font-weight:800; color:#ec4899; font-family:'Space Grotesk',sans-serif; line-height:1;">Multi</div>
            <div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.5rem;">University Support</div>
        </div>
        <div class="glass-card" style="text-align:center; padding: 1.25rem 2rem; min-width: 140px;">
            <div style="font-size:2.2rem; font-weight:800; color:#10b981; font-family:'Space Grotesk',sans-serif; line-height:1;">RAG</div>
            <div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.5rem;">AI Pipeline</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Feature Cards ──
    cols = st.columns(3, gap="large")

    features = [
        ("🚀", "Smart Document Upload", "#8b5cf6",
         "Upload PDFs, DOCX, and TXT files. Automatic chunking and semantic embedding for intelligent retrieval."),
        ("🔍", "Semantic Search", "#06b6d4",
         "Natural language queries with context-aware retrieval. Find exactly what you need, not just keyword matches."),
        ("💬", "AI-Powered Answers", "#ec4899",
         "Get precise, sourced answers with full traceability. Every response cites its document sources."),
    ]

    for col, (icon, title, color, desc) in zip(cols, features):
        with col:
            st.markdown(f"""
            <div class="glass-card card-hover-effect" style="text-align: center; min-height: 280px; display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 3.5rem; margin-bottom: 1rem; filter: drop-shadow(0 0 15px {color}40); animation: float 4s ease-in-out infinite;">{icon}</div>
                <h3 style="
                    font-size: 1.2rem;
                    font-weight: 700;
                    color: #f1f5f9;
                    margin-bottom: 0.75rem;
                    font-family: 'Space Grotesk', sans-serif;
                ">{title}</h3>
                <p style="
                    color: #64748b;
                    font-size: 0.9rem;
                    line-height: 1.6;
                    margin: 0;
                ">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)

    # ── Additional Features Row ──
    st.markdown("""
    <div style="margin-bottom: 3rem;">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; max-width: 900px; margin: 0 auto;">
            <div class="glass-card" style="text-align:center; padding: 1.25rem 1rem;">
                <div style="font-size:1.75rem; margin-bottom:0.5rem;">🏛️</div>
                <div style="font-weight:600; color:#f1f5f9; font-size:0.85rem;">Multi-University</div>
                <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">Data Isolation</div>
            </div>
            <div class="glass-card" style="text-align:center; padding: 1.25rem 1rem;">
                <div style="font-size:1.75rem; margin-bottom:0.5rem;">🎫</div>
                <div style="font-weight:600; color:#f1f5f9; font-size:0.85rem;">Ticket Tracking</div>
                <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">Query Analytics</div>
            </div>
            <div class="glass-card" style="text-align:center; padding: 1.25rem 1rem;">
                <div style="font-size:1.75rem; margin-bottom:0.5rem;">📊</div>
                <div style="font-weight:600; color:#f1f5f9; font-size:0.85rem;">Analytics</div>
                <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">Admin Dashboard</div>
            </div>
            <div class="glass-card" style="text-align:center; padding: 1.25rem 1rem;">
                <div style="font-size:1.75rem; margin-bottom:0.5rem;">🔐</div>
                <div style="font-weight:600; color:#f1f5f9; font-size:0.85rem;">Role-Based</div>
                <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">Access Control</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Login CTAs ──
    st.markdown("""
    <div style="text-align:center; margin-bottom: 2rem;">
        <div style="font-size:0.8rem; color:#64748b; text-transform:uppercase; letter-spacing:0.15em; margin-bottom:1.5rem;">
            Get Started
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_spacer1, col_admin, col_gap1, col_teacher, col_gap2, col_user, col_spacer2 = st.columns([1, 1, 0.3, 1, 0.3, 1, 1])

    with col_admin:
        if st.button("🔐 Admin Portal", key="landing_admin_btn", use_container_width=True):
            st.session_state.login_role_tab = "admin"
            st.session_state.page = "login"
            st.rerun()
        st.markdown("""<div style="text-align:center; margin-top:0.5rem;"><span style="font-size:0.75rem; color:var(--text-muted);">Manage users & universities</span></div>""", unsafe_allow_html=True)

    with col_teacher:
        if st.button("👨‍🏫 Teacher Portal", key="landing_teacher_btn", use_container_width=True):
            st.session_state.login_role_tab = "teacher"
            st.session_state.page = "login"
            st.rerun()
        st.markdown("""<div style="text-align:center; margin-top:0.5rem;"><span style="font-size:0.75rem; color:var(--text-muted);">Upload documents for your uni</span></div>""", unsafe_allow_html=True)

    with col_user:
        if st.button("👤 User Portal", key="landing_user_btn", use_container_width=True):
            st.session_state.login_role_tab = "user"
            st.session_state.page = "login"
            st.rerun()
        st.markdown("""<div style="text-align:center; margin-top:0.5rem;"><span style="font-size:0.75rem; color:var(--text-muted);">Ask questions & get answers</span></div>""", unsafe_allow_html=True)

    # ── Tech Stack ──
    st.markdown("<div style='height:4rem'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="
        text-align: center;
        padding: 2rem;
        border-top: 1px solid var(--border);
        position: relative;
        z-index: 1;
    ">
        <div style="
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.2em;
            margin-bottom: 1rem;
        ">Powered By</div>
        <div style="
            display: flex;
            justify-content: center;
            gap: 2.5rem;
            flex-wrap: wrap;
        ">
            <div style="display:flex; align-items:center; gap:0.5rem; color:var(--text-secondary); font-size:0.9rem; font-weight:500;">
                <span style="font-size:1.2rem;">⚡</span> Zilliz Cloud
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem; color:var(--text-secondary); font-size:0.9rem; font-weight:500;">
                <span style="font-size:1.2rem;">🤖</span> Groq LLM
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem; color:var(--text-secondary); font-size:0.9rem; font-weight:500;">
                <span style="font-size:1.2rem;">🔮</span> Sentence Transformers
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem; color:var(--text-secondary); font-size:0.9rem; font-weight:500;">
                <span style="font-size:1.2rem;">🎈</span> Streamlit
            </div>
        </div>
        <div style="margin-top: 2rem; font-size: 0.75rem; color: var(--text-muted);">
            © 2024 AI Knowledge Assistant. Built for organizational intelligence.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Router ────────────────────────────────────────────────────────────────────
def main():
    init_session_state()
    inject_global_css()

    # ── If authenticated, route to correct dashboard ──
    if st.session_state.authenticated:
        role = st.session_state.role
        if role == "admin":
            from pages.admin_dashboard import render_admin_dashboard
            render_admin_dashboard()
        elif role == "teacher":
            from pages.teacher_dashboard import render_teacher_dashboard
            render_teacher_dashboard()
        else:
            from pages.user_dashboard import render_user_dashboard
            render_user_dashboard()
        return

    # ── Unauthenticated routing ──
    page = st.session_state.get("page", "landing")
    if page == "login":
        from pages.login import render_login_page
        render_login_page()
    else:
        render_landing()


if __name__ == "__main__":
    main()
