"""
Village 360 — Main Application Entry Point
Rural Healthcare Multilingual AI Feedback Agent

Free-Tier-Only Architecture:
- Primary STT: Faster-Whisper multilingual model running locally on CPU
- Translation Engine: Meta NLLB-200 distilled 600M INT8 via CTranslate2 (100% Offline CPU)
- Optional Text Intelligence: Cloudflare Workers AI
- Zero paid API dependencies
"""
import os
import streamlit as st
from database.db import init_db, get_backend
from agent.state_manager import init_agent_state
from agent.conversation import render_conversation_step
from admin.dashboard import render_admin_dashboard
from services.cloudflare_ai import is_configured
from services.local_transcription import get_local_stt_model_name
from services.translation import get_engine_name
from auth.supabase_auth import (
    auth_required,
    ensure_auth,
    render_login_page,
    sign_out,
)

# 1. Page Configuration
st.set_page_config(
    page_title="Village 360 · AI Feedback Agent",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject World-Class SaaS Custom Styling (Linear/Stripe/Vercel inspired)
def inject_custom_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --primary-teal: #0D9488;
        --primary-teal-dark: #0F766E;
        --accent-emerald: #10B981;
        --bg-page: #F8FAFC;
        --card-bg: #FFFFFF;
        --text-slate-900: #0F172A;
        --text-slate-600: #475569;
        --border-subtle: #E2E8F0;
    }

    /* Overall Page Background & Typography */
    .stApp {
        background-color: var(--bg-page) !important;
        color: var(--text-slate-900) !important;
        font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* Hide default decoration bar */
    header[data-testid="stHeader"] {
        background-color: rgba(248, 250, 252, 0.85) !important;
        backdrop-filter: blur(10px) !important;
        border-bottom: 1px solid var(--border-subtle) !important;
    }

    /* Village 360 Hero Brand Header */
    .v360-hero {
        background: linear-gradient(135deg, #0F172A 0%, #134E4A 55%, #0F172A 100%);
        border-radius: 20px;
        padding: 24px 30px;
        margin-bottom: 24px;
        color: #FFFFFF;
        box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.12);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .v360-brand-left {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .v360-logo-icon {
        width: 48px;
        height: 48px;
        border-radius: 14px;
        background: linear-gradient(135deg, #0D9488, #10B981);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.6rem;
        box-shadow: 0 4px 12px rgba(13, 148, 136, 0.35);
    }
    .v360-hero-title {
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.2;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .v360-hero-badge {
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(13, 148, 136, 0.3);
        color: #5EEAD4;
        padding: 3px 8px;
        border-radius: 6px;
        border: 1px solid rgba(94, 234, 212, 0.4);
    }
    .v360-hero-subtitle {
        font-size: 0.85rem;
        color: #CBD5E1;
        margin-top: 2px;
        font-weight: 400;
    }
    .v360-badges-container {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }
    .v360-pill {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 6px 14px;
        border-radius: 30px;
        font-size: 0.78rem;
        font-weight: 600;
        backdrop-filter: blur(8px);
    }
    .v360-pill.live {
        background: rgba(16, 185, 129, 0.15);
        color: #6EE7B7;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .v360-pill.info {
        background: rgba(255, 255, 255, 0.08);
        color: #E2E8F0;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .v360-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10B981;
        box-shadow: 0 0 8px #10B981;
        display: inline-block;
        animation: v360-pulse 2s infinite;
    }
    @keyframes v360-pulse {
        0% { opacity: 0.6; transform: scale(0.9); }
        50% { opacity: 1; transform: scale(1.15); }
        100% { opacity: 0.6; transform: scale(0.9); }
    }

    /* Streamlit Buttons Styling */
    .stButton>button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 9px 20px !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    .stButton>button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
    }

    /* Primary Button: Gradient Teal/Emerald Background with crisp WHITE text */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #0D9488 0%, #10B981 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(13, 148, 136, 0.28) !important;
    }
    .stButton>button[kind="primary"] p,
    .stButton>button[kind="primary"] span,
    .stButton>button[kind="primary"] div {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    .stButton>button[kind="primary"]:hover {
        background: linear-gradient(135deg, #0F766E 0%, #059669 100%) !important;
        color: #FFFFFF !important;
    }
    .stButton>button[kind="primary"]:hover p,
    .stButton>button[kind="primary"]:hover span {
        color: #FFFFFF !important;
    }

    /* Secondary Button: Dark Navy/Black Background with crisp WHITE text */
    .stButton>button[kind="secondary"],
    .stButton>button:not([kind="primary"]) {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05) !important;
    }
    .stButton>button[kind="secondary"] p,
    .stButton>button[kind="secondary"] span,
    .stButton>button[kind="secondary"] div,
    .stButton>button:not([kind="primary"]) p,
    .stButton>button:not([kind="primary"]) span,
    .stButton>button:not([kind="primary"]) div {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    .stButton>button[kind="secondary"]:hover,
    .stButton>button:not([kind="primary"]):hover {
        background-color: #0F172A !important;
        border-color: #475569 !important;
        color: #FFFFFF !important;
    }
    .stButton>button[kind="secondary"]:hover p,
    .stButton>button:not([kind="primary"]):hover p {
        color: #FFFFFF !important;
    }

    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 16px !important;
        padding: 18px 20px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06) !important;
        border-color: #CBD5E1 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #64748B !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        letter-spacing: -0.02em !important;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: transparent !important;
        border-bottom: 2px solid #E2E8F0 !important;
        padding-bottom: 2px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        padding: 8px 18px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: #64748B !important;
        background-color: transparent !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        color: #0D9488 !important;
        border-bottom: 3px solid #0D9488 !important;
        background-color: rgba(13, 148, 136, 0.05) !important;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        color: #0F172A !important;
    }
    div[data-testid="stExpander"] {
        border: none !important;
    }

    /* Sidebar Clean Styling: White Background with Crisp Dark/Black Text */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] {
        padding-top: 1.5rem !important;
    }

    /* Force all text in sidebar to be crisp dark slate / black on white background */
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] small,
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
        color: #0F172A !important;
    }

    /* Sidebar Navigation Radio Options Container */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] {
        background-color: #F8FAFC !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 14px !important;
        padding: 14px 16px !important;
        margin-bottom: 12px !important;
    }

    /* Radio Group Title (Navigation Menu: / Choose View:) */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] > label,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] > label p,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] > label span,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] > label div[data-testid="stMarkdownContainer"] p {
        color: #334155 !important;
        font-size: 0.8rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        margin-bottom: 8px !important;
    }

    /* Radio Items (Text beside circle for Patient Feedback, Admin Dashboard, etc.) */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label p,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label span,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p {
        color: #0F172A !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        line-height: 1.4 !important;
    }

    /* Hover state on radio item */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:hover p {
        color: #0D9488 !important;
    }

    /* Radio circle accent */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] input[type="radio"]:checked + div {
        border-color: #0D9488 !important;
        background-color: #0D9488 !important;
    }

    /* Sidebar captions and secondary info text */
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] .stCaption p {
        color: #64748B !important;
        font-size: 0.78rem !important;
    }

    /* Radio in main container */
    div[data-testid="stRadio"] label p,
    div[data-testid="stRadio"] label span {
        color: #0F172A !important;
    }

    /* Progress bar */
    div[data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #0D9488, #10B981) !important;
        border-radius: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Apply global styling
inject_custom_theme()

# 3. Initialize Database and Agent Session State
init_db()
init_agent_state()

# 3b. Authentication gate (PostgreSQL/Supabase mode).
current_user = {}
if auth_required():
    current_user = ensure_auth() or {}
    if not current_user:
        render_login_page()
        st.stop()

# 4. Sidebar: Modern Village 360 Brand & Controls
st.sidebar.markdown("""
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 4px 0;">
    <div style="background: linear-gradient(135deg, #0D9488, #10B981); color: white; border-radius: 12px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; box-shadow: 0 2px 8px rgba(13,148,136,0.35);">🩺</div>
    <div>
        <div style="font-weight: 800; font-size: 1.25rem; color: #0F172A; letter-spacing: -0.02em; line-height: 1.1;">Village 360</div>
        <div style="font-size: 0.72rem; color: #64748B; font-weight: 500;">AI Healthcare Feedback</div>
    </div>
</div>
""", unsafe_allow_html=True)

if current_user:
    camp_label = current_user.get("camp_name") or current_user.get("camp_id") or "—"
    role_label = "Administrator" if current_user.get("role") == "admin" else "Camp Staff"
    st.sidebar.markdown(f"""
    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 10px 14px; margin-bottom: 14px;">
        <div style="font-weight: 700; font-size: 0.85rem; color: #0F172A;">👤 {current_user.get('email') or 'Signed in'}</div>
        <div style="font-size: 0.75rem; color: #64748B; margin-top: 2px;"><code>{role_label}</code> · Camp: <strong>{camp_label}</strong></div>
    </div>
    """, unsafe_allow_html=True)
    if st.sidebar.button("🚪 Sign Out", width="stretch"):
        sign_out()
        st.rerun()

app_mode = st.sidebar.radio(
    "Navigation Menu:",
    options=["🗣️ Patient Feedback Agent", "📊 Admin Dashboard", "ℹ️ System Status & Diagnostics"],
    index=0
)

st.sidebar.divider()

# Mode Status Badge
cf_status = is_configured()
st.sidebar.markdown(f"""
<div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 12px; padding: 12px; margin-bottom: 12px;">
    <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #065F46; font-size: 0.85rem;">
        <span style="width: 8px; height: 8px; border-radius: 50%; background: #10B981; display: inline-block;"></span>
        Local Whisper speech recognition
    </div>
    <div style="font-size: 0.75rem; color: #047857; margin-top: 4px;">
        Model: {get_local_stt_model_name()}. Audio is transcribed locally; records save to SQLite.
    </div>
</div>
""", unsafe_allow_html=True)

# Technical architecture details in sidebar
st.sidebar.markdown("""
<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px; font-size: 0.74rem; color: #64748B; space-y: 4px;">
    <div><strong>Linguistic:</strong> Hindi (हिंदी) & Telugu (తెలుగు)</div>
    <div style="margin-top: 4px;"><strong>Translation:</strong> Meta NLLB-200 INT8 (CPU)</div>
    <div style="margin-top: 4px;"><strong>Database:</strong> Local SQLite</div>
    <div style="margin-top: 4px;"><strong>Cost Tier:</strong> 100% Free / Zero Paid APIs</div>
</div>
""", unsafe_allow_html=True)

# Top Brand Hero Banner
st.markdown("""
<div class="v360-hero">
    <div class="v360-brand-left">
        <div class="v360-logo-icon">🩺</div>
        <div>
            <div class="v360-hero-title">
                Village 360
                <span class="v360-hero-badge">AI Agent</span>
            </div>
            <div class="v360-hero-subtitle">Rural Healthcare Multilingual Voice Feedback & Sentiment Analysis</div>
        </div>
    </div>
    <div class="v360-badges-container">
        <div class="v360-pill live">
            <span class="v360-dot"></span>
            <strong>Meta NLLB-200 INT8</strong> · Offline CPU
        </div>
        <div class="v360-pill info">
            🎙️ <strong>Local Whisper STT</strong>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 5. View Routing
if app_mode == "🗣️ Patient Feedback Agent":
    render_conversation_step()

elif app_mode == "📊 Admin Dashboard":
    if auth_required():
        render_admin_dashboard()
        st.stop()

    admin_pass = os.getenv("ADMIN_PASSWORD", "")
    if admin_pass:
        auth_key = "admin_authenticated"
        if not st.session_state.get(auth_key, False):
            st.markdown("""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 24px; max-width: 480px; margin: 40px auto; box-shadow: 0 4px 16px rgba(0,0,0,0.04);">
                <h3 style="margin-top: 0; color: #0F172A; font-weight: 700;">🔒 Administrator Authentication</h3>
                <p style="color: #64748B; font-size: 0.85rem;">Please enter administrative password to access clinical reports and analytics.</p>
            </div>
            """, unsafe_allow_html=True)
            entered_pw = st.text_input("Enter Admin Password:", type="password")
            if st.button("Log In", type="primary"):
                if entered_pw == admin_pass:
                    st.session_state[auth_key] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        else:
            if st.sidebar.button("🚪 Log Out Admin", width="stretch"):
                st.session_state[auth_key] = False
                st.rerun()
            render_admin_dashboard()
    else:
        render_admin_dashboard()

elif app_mode == "ℹ️ System Status & Diagnostics":
    st.markdown("### ℹ️ System Architecture & Model Diagnostics")
    st.caption("Detailed overview of the 100% Free-Tier Offline Multilingual AI Pipeline.")

    st.markdown("""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin: 20px 0;">
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 0.75rem; font-weight: 700; color: #0D9488; text-transform: uppercase;">Acoustic Recognition</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #0F172A; margin: 4px 0;">Local Faster-Whisper</div>
            <div style="font-size: 0.8rem; color: #64748B;">Runs on this computer's CPU; patient audio is not uploaded.</div>
        </div>
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 0.75rem; font-weight: 700; color: #10B981; text-transform: uppercase;">Neural Translation</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #0F172A; margin: 4px 0;">Meta NLLB-200 INT8</div>
            <div style="font-size: 0.8rem; color: #64748B;">Full-sentence Telugu/Hindi to English running offline on CPU (~450ms).</div>
        </div>
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 0.75rem; font-weight: 700; color: #3B82F6; text-transform: uppercase;">Persistence Layer</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #0F172A; margin: 4px 0;">SQLite Embedded</div>
            <div style="font-size: 0.8rem; color: #64748B;">English answers are stored; raw audio is discarded.</div>
        </div>
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 0.75rem; font-weight: 700; color: #8B5CF6; text-transform: uppercase;">Cost & Privacy</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #0F172A; margin: 4px 0;">$0.00 / Zero Paid APIs</div>
            <div style="font-size: 0.8rem; color: #64748B;">100% Free-Tier architecture ensuring zero recurring budget costs.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.subheader("Optional Cloudflare Text Analysis Status")
    from services.cloudflare_ai import _cfg
    acct = _cfg("CLOUDFLARE_ACCOUNT_ID")
    has_token = bool(_cfg("CLOUDFLARE_API_TOKEN"))
    masked_acct = f"{acct[:4]}...{acct[-4:]}" if len(acct) >= 8 else ("Configured" if acct else "Not set")

    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.write(f"- **Cloudflare Account ID:** `{masked_acct}`")
        st.write(f"- **Cloudflare API Token:** `{'Configured (Hidden)' if has_token else 'Not set'}`")
    with col_stat2:
        st.write(f"- **Text Analysis:** {'Configured' if cf_status else 'Not configured (local analysis fallback)'}")
        st.write(f"- **Translation Engine:** `{get_engine_name()}`")
